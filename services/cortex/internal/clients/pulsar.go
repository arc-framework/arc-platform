package clients

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"net/http"
	"time"

	"github.com/sony/gobreaker"

	"arc-framework/cortex/internal/config"
	"arc-framework/cortex/internal/orchestrator"
)

const pulsarProbeName = "arc-strange"

// topicSpec describes a single partitioned topic to provision.
type topicSpec struct {
	namespace  string
	topic      string
	partitions int
}

var requiredNamespaces = []string{"events", "logs", "audit"}

var requiredTopics = []topicSpec{
	{namespace: "events", topic: "agent-lifecycle", partitions: 3},
	{namespace: "logs", topic: "application", partitions: 4},
	{namespace: "audit", topic: "command-log", partitions: 1},
}

// PulsarClient provisions Pulsar tenants, namespaces, and topics via the
// Pulsar admin REST API, with a circuit breaker around all outbound calls.
type PulsarClient struct {
	adminURL string
	tenant   string
	cb       *gobreaker.CircuitBreaker
	httpDo   func(req *http.Request) (*http.Response, error)
}

// NewPulsarClient constructs a PulsarClient. No HTTP calls are made at
// construction time; they happen lazily inside Provision and Probe.
func NewPulsarClient(cfg config.PulsarConfig, cb *gobreaker.CircuitBreaker) *PulsarClient {
	return &PulsarClient{
		adminURL: cfg.AdminURL,
		tenant:   cfg.Tenant,
		cb:       cb,
		httpDo:   http.DefaultClient.Do,
	}
}

// Provision creates the tenant, namespaces, and topics required by the ARC
// platform. The operation is idempotent: HTTP 409 responses are treated as
// success. The entire sequence is wrapped in the circuit breaker.
func (c *PulsarClient) Provision(ctx context.Context) error {
	_, err := c.cb.Execute(func() (any, error) {
		if err := c.createTenant(ctx); err != nil {
			return nil, err
		}

		for _, ns := range requiredNamespaces {
			if err := c.createNamespace(ctx, ns); err != nil {
				return nil, err
			}
		}

		for _, spec := range requiredTopics {
			if err := c.createTopic(ctx, spec); err != nil {
				return nil, err
			}
		}

		return nil, nil
	})

	if err != nil {
		if errors.Is(err, gobreaker.ErrOpenState) {
			return fmt.Errorf("circuit open: %w", err)
		}
		return err
	}
	return nil
}

// Probe checks that the Pulsar admin API is reachable by listing tenants.
func (c *PulsarClient) Probe(ctx context.Context) orchestrator.ProbeResult {
	start := time.Now()

	_, err := c.cb.Execute(func() (any, error) {
		url := fmt.Sprintf("%s/admin/v2/tenants", c.adminURL)
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
		if err != nil {
			return nil, fmt.Errorf("building probe request: %w", err)
		}

		resp, err := c.httpDo(req)
		if err != nil {
			return nil, fmt.Errorf("probe request: %w", err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			return nil, fmt.Errorf("probe returned HTTP %d", resp.StatusCode)
		}

		return nil, nil
	})

	latency := time.Since(start).Milliseconds()

	if err != nil {
		errMsg := err.Error()
		if errors.Is(err, gobreaker.ErrOpenState) {
			errMsg = "circuit open"
		}
		return orchestrator.ProbeResult{
			Name:      pulsarProbeName,
			OK:        false,
			LatencyMs: latency,
			Error:     errMsg,
		}
	}

	return orchestrator.ProbeResult{
		Name:      pulsarProbeName,
		OK:        true,
		LatencyMs: latency,
	}
}

// createTenant issues a PUT to create the configured tenant.
// 204 = created, 409 = already exists (treated as success).
func (c *PulsarClient) createTenant(ctx context.Context) error {
	url := fmt.Sprintf("%s/admin/v2/tenants/%s", c.adminURL, c.tenant)
	body := []byte(`{"allowedClusters":["standalone"]}`)

	return c.putResource(ctx, url, body, fmt.Sprintf("tenant %s", c.tenant))
}

// createNamespace issues a PUT to create a namespace under the configured tenant.
func (c *PulsarClient) createNamespace(ctx context.Context, namespace string) error {
	url := fmt.Sprintf("%s/admin/v2/namespaces/%s/%s", c.adminURL, c.tenant, namespace)
	return c.putResource(ctx, url, nil, fmt.Sprintf("namespace %s/%s", c.tenant, namespace))
}

// createTopic issues a PUT to create a partitioned topic.
// The request body is the partition count as a plain JSON integer.
func (c *PulsarClient) createTopic(ctx context.Context, spec topicSpec) error {
	url := fmt.Sprintf("%s/admin/v2/persistent/%s/%s/%s/partitions",
		c.adminURL, c.tenant, spec.namespace, spec.topic)
	body := []byte(fmt.Sprintf("%d", spec.partitions))

	return c.putResource(ctx, url, body,
		fmt.Sprintf("topic persistent://%s/%s/%s", c.tenant, spec.namespace, spec.topic))
}

// putResource sends a PUT request with an optional body. HTTP 204 and 409 are
// treated as success; any other status code is an error.
func (c *PulsarClient) putResource(ctx context.Context, url string, body []byte, label string) error {
	var req *http.Request
	var err error

	if len(body) > 0 {
		req, err = http.NewRequestWithContext(ctx, http.MethodPut, url, bytes.NewReader(body))
	} else {
		req, err = http.NewRequestWithContext(ctx, http.MethodPut, url, nil)
	}
	if err != nil {
		return fmt.Errorf("building request for %s: %w", label, err)
	}

	if len(body) > 0 {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.httpDo(req)
	if err != nil {
		return fmt.Errorf("PUT %s: %w", label, err)
	}
	defer resp.Body.Close()

	switch resp.StatusCode {
	case http.StatusNoContent, http.StatusConflict:
		return nil
	default:
		return fmt.Errorf("PUT %s returned HTTP %d", label, resp.StatusCode)
	}
}
