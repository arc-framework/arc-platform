package clients

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/nats-io/nats.go"
	"github.com/sony/gobreaker"

	"arc-framework/cortex/internal/config"
	"arc-framework/cortex/internal/orchestrator"
)

const natsProbeNameConst = "arc-flash"

// streamSpec describes a single JetStream stream to provision.
type streamSpec struct {
	name      string
	subjects  []string
	retention nats.RetentionPolicy
	maxAge    time.Duration
}

// requiredStreams lists the three streams Cortex must provision on NATS.
var requiredStreams = []streamSpec{
	{
		name:      "AGENT_COMMANDS",
		subjects:  []string{"agent.*.cmd"},
		retention: nats.LimitsPolicy,
		maxAge:    24 * time.Hour,
	},
	{
		name:      "AGENT_EVENTS",
		subjects:  []string{"agent.*.event", "agent.*.status"},
		retention: nats.InterestPolicy,
		maxAge:    168 * time.Hour,
	},
	{
		name:      "SYSTEM_METRICS",
		subjects:  []string{"metrics.>"},
		retention: nats.LimitsPolicy,
		maxAge:    6 * time.Hour,
	},
}

// jsContext is the subset of nats.JetStreamContext used in stream management.
// Defining an interface here allows test doubles to be injected without a live
// NATS server.
type jsContext interface {
	StreamInfo(stream string, opts ...nats.JSOpt) (*nats.StreamInfo, error)
	AddStream(cfg *nats.StreamConfig, opts ...nats.JSOpt) (*nats.StreamInfo, error)
	UpdateStream(cfg *nats.StreamConfig, opts ...nats.JSOpt) (*nats.StreamInfo, error)
}

// NATSClient manages JetStream stream provisioning and health probing for the
// arc-flash (NATS) dependency.
type NATSClient struct {
	url    string
	cb     *gobreaker.CircuitBreaker
	newJS  func(url string) (jsContext, func(), error)
}

// NewNATSClient constructs a NATSClient. No connection is made at construction
// time; connections are opened lazily inside ProvisionStreams and Probe.
func NewNATSClient(cfg config.NATSConfig, cb *gobreaker.CircuitBreaker) *NATSClient {
	return &NATSClient{
		url:   cfg.URL,
		cb:    cb,
		newJS: realNewJS,
	}
}

// ProvisionStreams connects to NATS JetStream and creates or updates the three
// required streams. It is idempotent: existing streams are updated rather than
// errored. The entire operation is wrapped in the circuit breaker.
func (c *NATSClient) ProvisionStreams(ctx context.Context) error {
	_, err := c.cb.Execute(func() (any, error) {
		js, cleanup, err := c.newJS(c.url)
		if err != nil {
			return nil, fmt.Errorf("connecting to NATS: %w", err)
		}
		defer cleanup()

		for _, spec := range requiredStreams {
			if err := provisionStream(js, spec); err != nil {
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

// Probe verifies NATS connectivity and returns a ProbeResult. A missing stream
// is not treated as a failure — NATS being reachable is what matters here.
func (c *NATSClient) Probe(ctx context.Context) orchestrator.ProbeResult {
	start := time.Now()

	_, err := c.cb.Execute(func() (any, error) {
		js, cleanup, err := c.newJS(c.url)
		if err != nil {
			return nil, fmt.Errorf("connecting to NATS: %w", err)
		}
		defer cleanup()

		// A missing stream means NATS is up but streams haven't been
		// provisioned yet — that's fine for a health check.
		_, infoErr := js.StreamInfo(requiredStreams[0].name)
		if infoErr != nil && !errors.Is(infoErr, nats.ErrStreamNotFound) {
			return nil, fmt.Errorf("stream info: %w", infoErr)
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
			Name:      natsProbeNameConst,
			OK:        false,
			LatencyMs: latency,
			Error:     errMsg,
		}
	}

	return orchestrator.ProbeResult{
		Name:      natsProbeNameConst,
		OK:        true,
		LatencyMs: latency,
	}
}

// provisionStream creates the stream if it does not exist, or updates it if it
// does. nats.ErrStreamNotFound signals "create"; any other error is returned.
func provisionStream(js jsContext, spec streamSpec) error {
	cfg := &nats.StreamConfig{
		Name:      spec.name,
		Subjects:  spec.subjects,
		Retention: spec.retention,
		MaxAge:    spec.maxAge,
	}

	_, err := js.StreamInfo(spec.name)
	switch {
	case errors.Is(err, nats.ErrStreamNotFound):
		if _, addErr := js.AddStream(cfg); addErr != nil {
			return fmt.Errorf("creating stream %s: %w", spec.name, addErr)
		}
	case err != nil:
		return fmt.Errorf("querying stream %s: %w", spec.name, err)
	default:
		if _, updErr := js.UpdateStream(cfg); updErr != nil {
			return fmt.Errorf("updating stream %s: %w", spec.name, updErr)
		}
	}
	return nil
}

// realNewJS opens a real NATS connection and returns a JetStreamContext plus a
// cleanup function that drains and closes the connection.
func realNewJS(url string) (jsContext, func(), error) {
	nc, err := nats.Connect(url)
	if err != nil {
		return nil, func() {}, fmt.Errorf("nats connect %s: %w", url, err)
	}

	js, err := nc.JetStream()
	if err != nil {
		nc.Close()
		return nil, func() {}, fmt.Errorf("nats jetstream context: %w", err)
	}

	return js, func() { nc.Close() }, nil
}
