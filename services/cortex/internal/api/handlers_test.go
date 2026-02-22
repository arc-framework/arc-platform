package api

import (
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"arc-framework/cortex/internal/orchestrator"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// noopLogger returns a slog.Logger that discards all output — keeps test output clean.
func noopLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

func init() {
	gin.SetMode(gin.TestMode)
}

// fakeOrchestrator is a test double that implements orchestratorService.
type fakeOrchestrator struct {
	inProgress   bool
	ready        bool
	deepProbes   map[string]orchestrator.ProbeResult
	bootstrapErr error
	// bootstrapDelay simulates slow bootstrap so async tests can verify 202.
	bootstrapDelay time.Duration
}

func (f *fakeOrchestrator) IsBootstrapInProgress() bool {
	return f.inProgress
}

func (f *fakeOrchestrator) IsReady() bool {
	return f.ready
}

func (f *fakeOrchestrator) RunBootstrap(_ context.Context) (*orchestrator.BootstrapResult, error) {
	if f.bootstrapDelay > 0 {
		time.Sleep(f.bootstrapDelay)
	}
	if f.bootstrapErr != nil {
		return nil, f.bootstrapErr
	}
	return &orchestrator.BootstrapResult{
		Status: orchestrator.StatusOK,
		Phases: map[string]orchestrator.PhaseResult{},
	}, nil
}

func (f *fakeOrchestrator) RunDeepHealth(_ context.Context) map[string]orchestrator.ProbeResult {
	if f.deepProbes != nil {
		return f.deepProbes
	}
	return map[string]orchestrator.ProbeResult{}
}

// newTestEngine builds a minimal Gin engine with only the given handler — no
// middleware — for isolated handler testing.
func newTestEngine(method, path string, h gin.HandlerFunc) *gin.Engine {
	r := gin.New()
	r.Handle(method, path, h)
	return r
}

// --- Bootstrap handler ---

func TestBootstrap_202WhenNotRunning(t *testing.T) {
	t.Parallel()

	fake := &fakeOrchestrator{inProgress: false, bootstrapDelay: 50 * time.Millisecond}
	handler := &Handler{orchestrator: fake}

	engine := newTestEngine(http.MethodPost, "/api/v1/bootstrap", handler.Bootstrap)

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/api/v1/bootstrap", nil)
	engine.ServeHTTP(w, req)

	assert.Equal(t, http.StatusAccepted, w.Code)

	var body map[string]string
	require.NoError(t, json.NewDecoder(w.Body).Decode(&body))
	assert.Equal(t, "accepted", body["status"])
}

func TestBootstrap_409WhenInProgress(t *testing.T) {
	t.Parallel()

	fake := &fakeOrchestrator{inProgress: true}
	handler := &Handler{orchestrator: fake}

	engine := newTestEngine(http.MethodPost, "/api/v1/bootstrap", handler.Bootstrap)

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/api/v1/bootstrap", nil)
	engine.ServeHTTP(w, req)

	assert.Equal(t, http.StatusConflict, w.Code)

	var body map[string]string
	require.NoError(t, json.NewDecoder(w.Body).Decode(&body))
	assert.Equal(t, "in-progress", body["status"])
}

// --- Health handler ---

func TestHealth_AlwaysReturns200(t *testing.T) {
	t.Parallel()

	fake := &fakeOrchestrator{}
	handler := &Handler{orchestrator: fake}

	engine := newTestEngine(http.MethodGet, "/health", handler.Health)

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	engine.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var body map[string]string
	require.NoError(t, json.NewDecoder(w.Body).Decode(&body))
	assert.Equal(t, "healthy", body["status"])
	assert.Equal(t, "shallow", body["mode"])
}

// --- DeepHealth handler ---

func TestDeepHealth_200WhenAllHealthy(t *testing.T) {
	t.Parallel()

	fake := &fakeOrchestrator{
		deepProbes: map[string]orchestrator.ProbeResult{
			"postgres": {Name: "postgres", OK: true},
			"nats":     {Name: "nats", OK: true},
			"pulsar":   {Name: "pulsar", OK: true},
			"redis":    {Name: "redis", OK: true},
		},
	}
	handler := &Handler{orchestrator: fake}

	engine := newTestEngine(http.MethodGet, "/health/deep", handler.DeepHealth)

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/health/deep", nil)
	engine.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var body map[string]interface{}
	require.NoError(t, json.NewDecoder(w.Body).Decode(&body))
	assert.Equal(t, "healthy", body["status"])
}

func TestDeepHealth_503WhenAnyUnhealthy(t *testing.T) {
	t.Parallel()

	fake := &fakeOrchestrator{
		deepProbes: map[string]orchestrator.ProbeResult{
			"postgres": {Name: "postgres", OK: true},
			"nats":     {Name: "nats", OK: false, Error: "connection refused"},
			"pulsar":   {Name: "pulsar", OK: true},
			"redis":    {Name: "redis", OK: true},
		},
	}
	handler := &Handler{orchestrator: fake}

	engine := newTestEngine(http.MethodGet, "/health/deep", handler.DeepHealth)

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/health/deep", nil)
	engine.ServeHTTP(w, req)

	assert.Equal(t, http.StatusServiceUnavailable, w.Code)

	var body map[string]interface{}
	require.NoError(t, json.NewDecoder(w.Body).Decode(&body))
	assert.Equal(t, "unhealthy", body["status"])
}

func TestDeepHealth_503WhenAllUnhealthy(t *testing.T) {
	t.Parallel()

	fake := &fakeOrchestrator{
		deepProbes: map[string]orchestrator.ProbeResult{
			"postgres": {Name: "postgres", OK: false, Error: "timeout"},
			"nats":     {Name: "nats", OK: false, Error: "timeout"},
			"pulsar":   {Name: "pulsar", OK: false, Error: "timeout"},
			"redis":    {Name: "redis", OK: false, Error: "timeout"},
		},
	}
	handler := &Handler{orchestrator: fake}

	engine := newTestEngine(http.MethodGet, "/health/deep", handler.DeepHealth)

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/health/deep", nil)
	engine.ServeHTTP(w, req)

	assert.Equal(t, http.StatusServiceUnavailable, w.Code)
}

// --- Ready handler ---

func TestReady_503BeforeBootstrap(t *testing.T) {
	t.Parallel()

	fake := &fakeOrchestrator{ready: false}
	handler := &Handler{orchestrator: fake}

	engine := newTestEngine(http.MethodGet, "/ready", handler.Ready)

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/ready", nil)
	engine.ServeHTTP(w, req)

	assert.Equal(t, http.StatusServiceUnavailable, w.Code)

	var body map[string]interface{}
	require.NoError(t, json.NewDecoder(w.Body).Decode(&body))
	assert.Equal(t, false, body["ready"])
}

func TestReady_200AfterBootstrap(t *testing.T) {
	t.Parallel()

	fake := &fakeOrchestrator{ready: true}
	handler := &Handler{orchestrator: fake}

	engine := newTestEngine(http.MethodGet, "/ready", handler.Ready)

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/ready", nil)
	engine.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var body map[string]interface{}
	require.NoError(t, json.NewDecoder(w.Body).Decode(&body))
	assert.Equal(t, true, body["ready"])
}

// --- Recovery middleware ---

func TestRecoveryMiddleware_Returns500OnPanic(t *testing.T) {
	t.Parallel()

	engine := gin.New()
	engine.Use(Recovery(noopLogger()))
	engine.GET("/panic", func(c *gin.Context) {
		panic("intentional test panic")
	})

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/panic", nil)
	engine.ServeHTTP(w, req)

	assert.Equal(t, http.StatusInternalServerError, w.Code)

	var body map[string]string
	require.NoError(t, json.NewDecoder(w.Body).Decode(&body))
	assert.Equal(t, "error", body["status"])
}

// --- NewRouter integration smoke test ---

func TestNewRouter_RoutesRegistered(t *testing.T) {
	t.Parallel()

	fake := &fakeOrchestrator{ready: true, deepProbes: map[string]orchestrator.ProbeResult{
		"postgres": {Name: "postgres", OK: true},
	}}
	router := NewRouter(fake)

	cases := []struct {
		method string
		path   string
		want   int
	}{
		{http.MethodGet, "/health", http.StatusOK},
		{http.MethodGet, "/ready", http.StatusOK},
		{http.MethodPost, "/api/v1/bootstrap", http.StatusAccepted},
	}

	for _, tc := range cases {
		w := httptest.NewRecorder()
		req := httptest.NewRequest(tc.method, tc.path, strings.NewReader(""))
		router.Handler().ServeHTTP(w, req)
		assert.Equal(t, tc.want, w.Code, "route %s %s", tc.method, tc.path)
	}
}
