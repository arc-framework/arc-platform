package clients

import (
	"context"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"arc-framework/cortex/internal/config"
)

// pulsarFixedHandler returns a handler that responds with statusCode to every
// request.
func pulsarFixedHandler(statusCode int) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(statusCode)
	}
}

// makePulsarClient constructs a PulsarClient wired to the given test server.
func makePulsarClient(srv *httptest.Server) *PulsarClient {
	cfg := config.PulsarConfig{
		AdminURL: srv.URL,
		Tenant:   "arc-system",
	}
	cb := NewCircuitBreaker("pulsar-test")
	client := NewPulsarClient(cfg, cb)
	client.httpDo = srv.Client().Do
	return client
}

// makePulsarClientWithCB constructs a PulsarClient wired to the given test
// server with an explicit circuit breaker (useful for CB-open tests).
func makePulsarClientWithCB(srv *httptest.Server, cbName string) *PulsarClient {
	cfg := config.PulsarConfig{
		AdminURL: srv.URL,
		Tenant:   "arc-system",
	}
	cb := NewCircuitBreaker(cbName)
	client := NewPulsarClient(cfg, cb)
	client.httpDo = srv.Client().Do
	return client
}

func TestNewPulsarClient(t *testing.T) {
	t.Parallel()

	cb := NewCircuitBreaker("new-pulsar-test")
	cfg := config.PulsarConfig{
		AdminURL:   "http://arc-strange:8080",
		ServiceURL: "pulsar://arc-strange:6650",
		Tenant:     "arc-system",
	}
	client := NewPulsarClient(cfg, cb)

	assert.NotNil(t, client)
	assert.Equal(t, "http://arc-strange:8080", client.adminURL)
	assert.Equal(t, "arc-system", client.tenant)
	assert.NotNil(t, client.httpDo)
}

func TestProvision_AllNew(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(pulsarFixedHandler(http.StatusNoContent))
	defer srv.Close()

	client := makePulsarClient(srv)
	err := client.Provision(context.Background())

	require.NoError(t, err)
}

func TestProvision_AllExisting(t *testing.T) {
	t.Parallel()

	// 409 on every resource — should be treated as success.
	srv := httptest.NewServer(pulsarFixedHandler(http.StatusConflict))
	defer srv.Close()

	client := makePulsarClient(srv)
	err := client.Provision(context.Background())

	require.NoError(t, err)
}

func TestProvision_ServerError(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(pulsarFixedHandler(http.StatusInternalServerError))
	defer srv.Close()

	client := makePulsarClient(srv)
	err := client.Provision(context.Background())

	require.Error(t, err)
	assert.Contains(t, err.Error(), "HTTP 500")
}

func TestProvision_CircuitBreakerOpensAfterThreeFailures(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(pulsarFixedHandler(http.StatusInternalServerError))
	defer srv.Close()

	client := makePulsarClientWithCB(srv, "provision-pulsar-cb-open")

	for i := range 3 {
		err := client.Provision(context.Background())
		require.Error(t, err, "attempt %d should fail", i+1)
		assert.NotContains(t, err.Error(), "circuit open",
			"circuit should not be open yet on attempt %d", i+1)
	}

	// The 4th call must be rejected by the open circuit breaker.
	err := client.Provision(context.Background())
	require.Error(t, err)
	assert.Contains(t, err.Error(), "circuit open")
}

func TestProvision_CorrectEndpointsAreCalled(t *testing.T) {
	t.Parallel()

	var paths []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		paths = append(paths, r.Method+" "+r.URL.Path)
		w.WriteHeader(http.StatusNoContent)
	}))
	defer srv.Close()

	client := makePulsarClient(srv)
	err := client.Provision(context.Background())
	require.NoError(t, err)

	assert.Contains(t, paths, "PUT /admin/v2/tenants/arc-system")
	assert.Contains(t, paths, "PUT /admin/v2/namespaces/arc-system/events")
	assert.Contains(t, paths, "PUT /admin/v2/namespaces/arc-system/logs")
	assert.Contains(t, paths, "PUT /admin/v2/namespaces/arc-system/audit")
	assert.Contains(t, paths, "PUT /admin/v2/persistent/arc-system/events/agent-lifecycle/partitions")
	assert.Contains(t, paths, "PUT /admin/v2/persistent/arc-system/logs/application/partitions")
	assert.Contains(t, paths, "PUT /admin/v2/persistent/arc-system/audit/command-log/partitions")
}

func TestPulsarProbe_Success(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet && r.URL.Path == "/admin/v2/tenants" {
			w.WriteHeader(http.StatusOK)
			return
		}
		w.WriteHeader(http.StatusNotFound)
	}))
	defer srv.Close()

	client := makePulsarClient(srv)
	result := client.Probe(context.Background())

	assert.Equal(t, pulsarProbeName, result.Name)
	assert.True(t, result.OK)
	assert.Empty(t, result.Error)
}

func TestPulsarProbe_Failure(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(pulsarFixedHandler(http.StatusServiceUnavailable))
	defer srv.Close()

	client := makePulsarClient(srv)
	result := client.Probe(context.Background())

	assert.Equal(t, pulsarProbeName, result.Name)
	assert.False(t, result.OK)
	assert.NotEmpty(t, result.Error)
}

func TestPulsarProbe_CircuitOpenAfterThreeFailures(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(pulsarFixedHandler(http.StatusServiceUnavailable))
	defer srv.Close()

	client := makePulsarClientWithCB(srv, "probe-pulsar-cb-open")

	for i := range 3 {
		result := client.Probe(context.Background())
		assert.False(t, result.OK, "probe %d should fail", i+1)
		assert.NotEqual(t, "circuit open", result.Error,
			"probe %d should not be circuit-open yet", i+1)
	}

	result := client.Probe(context.Background())
	assert.False(t, result.OK)
	assert.Equal(t, "circuit open", result.Error)
}

// TestProvision_StopsOnFirstError verifies that provisioning halts immediately
// after the first non-2xx/409 response and does not continue to later steps.
func TestProvision_StopsOnFirstError(t *testing.T) {
	t.Parallel()

	var callCount atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		callCount.Add(1)
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()

	client := makePulsarClient(srv)
	err := client.Provision(context.Background())

	require.Error(t, err)
	// Only the tenant creation should have been attempted (1 call) before halting.
	assert.Equal(t, int32(1), callCount.Load())
}
