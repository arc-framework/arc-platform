package api

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"arc-framework/cortex/internal/orchestrator"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// --- Mock client implementations ---

// mockPGProber immediately returns a successful probe.
type mockPGProber struct{}

func (m *mockPGProber) Probe(_ context.Context) orchestrator.ProbeResult {
	return orchestrator.ProbeResult{Name: "postgres", OK: true, LatencyMs: 1}
}

// mockNATSProvisioner immediately succeeds provisioning and probe.
type mockNATSProvisioner struct{}

func (m *mockNATSProvisioner) ProvisionStreams(_ context.Context) error { return nil }
func (m *mockNATSProvisioner) Probe(_ context.Context) orchestrator.ProbeResult {
	return orchestrator.ProbeResult{Name: "nats", OK: true, LatencyMs: 1}
}

// mockPulsarProvisioner immediately succeeds provisioning and probe.
type mockPulsarProvisioner struct{}

func (m *mockPulsarProvisioner) Provision(_ context.Context) error { return nil }
func (m *mockPulsarProvisioner) Probe(_ context.Context) orchestrator.ProbeResult {
	return orchestrator.ProbeResult{Name: "pulsar", OK: true, LatencyMs: 1}
}

// mockRedisProber immediately returns a successful probe.
type mockRedisProber struct{}

func (m *mockRedisProber) Probe(_ context.Context) orchestrator.ProbeResult {
	return orchestrator.ProbeResult{Name: "redis", OK: true, LatencyMs: 1}
}

// --- Integration test ---

// TestBootstrapFlow_202ThenReady verifies the full bootstrap happy-path:
//  1. POST /api/v1/bootstrap → 202 Accepted
//  2. GET /ready eventually → 200 OK once background bootstrap completes
func TestBootstrapFlow_202ThenReady(t *testing.T) {
	t.Parallel()

	o := orchestrator.New(
		&mockPGProber{},
		&mockNATSProvisioner{},
		&mockPulsarProvisioner{},
		&mockRedisProber{},
	)

	router := NewRouter(o)
	srv := httptest.NewServer(router.Handler())
	defer srv.Close()

	client := srv.Client()

	// Step 1: POST /api/v1/bootstrap → 202
	resp, err := client.Post(srv.URL+"/api/v1/bootstrap", "application/json", strings.NewReader(""))
	require.NoError(t, err)
	defer resp.Body.Close()

	assert.Equal(t, http.StatusAccepted, resp.StatusCode, "bootstrap should return 202 Accepted")

	var bootstrapBody map[string]string
	require.NoError(t, json.NewDecoder(resp.Body).Decode(&bootstrapBody))
	assert.Equal(t, "accepted", bootstrapBody["status"])

	// Step 2: poll GET /ready until 200 (bootstrap runs in background goroutine)
	deadline := time.Now().Add(5 * time.Second)
	var lastCode int
	for time.Now().Before(deadline) {
		r, err := client.Get(srv.URL + "/ready")
		require.NoError(t, err)
		r.Body.Close()

		lastCode = r.StatusCode
		if lastCode == http.StatusOK {
			break
		}

		time.Sleep(50 * time.Millisecond)
	}

	assert.Equal(t, http.StatusOK, lastCode, "GET /ready should return 200 after bootstrap completes")
}
