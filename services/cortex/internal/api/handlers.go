package api

import (
	"context"
	"net/http"

	"arc-framework/cortex/internal/orchestrator"

	"github.com/gin-gonic/gin"
)

// orchestratorService is the subset of *orchestrator.Orchestrator used by the
// HTTP handlers. Declaring it as an interface allows test doubles to be injected.
type orchestratorService interface {
	RunBootstrap(ctx context.Context) (*orchestrator.BootstrapResult, error)
	RunDeepHealth(ctx context.Context) map[string]orchestrator.ProbeResult
	IsReady() bool
	IsBootstrapInProgress() bool
}

// Handler holds the dependencies shared across all HTTP handlers.
type Handler struct {
	orchestrator orchestratorService
}

// Bootstrap handles POST /api/v1/bootstrap.
// It returns 202 immediately when a new bootstrap run is started, or 409 if one
// is already in progress. The actual bootstrap work runs in a background goroutine.
func (h *Handler) Bootstrap(c *gin.Context) {
	if h.orchestrator.IsBootstrapInProgress() {
		c.JSON(http.StatusConflict, gin.H{"status": "in-progress"})
		return
	}
	go func() {
		//nolint:errcheck
		h.orchestrator.RunBootstrap(context.Background()) //nolint:contextcheck
	}()
	c.JSON(http.StatusAccepted, gin.H{"status": "accepted"})
}

// Health handles GET /health.
// It always returns 200 — this is the liveness probe.
func (h *Handler) Health(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status": "healthy",
		"mode":   "shallow",
	})
}

// DeepHealth handles GET /health/deep.
// It probes all 4 backing services and returns 200 only when every probe is OK.
func (h *Handler) DeepHealth(c *gin.Context) {
	probes := h.orchestrator.RunDeepHealth(c.Request.Context())

	allOK := true
	for _, p := range probes {
		if !p.OK {
			allOK = false
			break
		}
	}

	status := "healthy"
	code := http.StatusOK
	if !allOK {
		status = "unhealthy"
		code = http.StatusServiceUnavailable
	}

	c.JSON(code, gin.H{
		"status":       status,
		"dependencies": probes,
	})
}

// Ready handles GET /ready.
// It returns 200 only after a successful bootstrap; 503 otherwise.
func (h *Handler) Ready(c *gin.Context) {
	if h.orchestrator.IsReady() {
		c.JSON(http.StatusOK, gin.H{"ready": true})
		return
	}
	c.JSON(http.StatusServiceUnavailable, gin.H{"ready": false})
}
