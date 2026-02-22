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
//
// @Summary      Trigger platform bootstrap
// @Description  Starts a bootstrap run in the background. All 4 phases (Postgres, NATS, Pulsar, Redis) run concurrently. Returns 202 immediately; poll /ready or /health/deep to track completion.
// @Tags         bootstrap
// @Produce      json
// @Success      202  {object}  object{status=string}  "Bootstrap accepted — run started"
// @Failure      409  {object}  object{status=string}  "Bootstrap already in progress"
// @Router       /api/v1/bootstrap [post]
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
//
// @Summary      Liveness probe
// @Description  Always returns 200. Indicates the process is alive. Use /health/deep for dependency health.
// @Tags         health
// @Produce      json
// @Success      200  {object}  object{status=string,mode=string}
// @Router       /health [get]
func (h *Handler) Health(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status": "healthy",
		"mode":   "shallow",
	})
}

// DeepHealth handles GET /health/deep.
// It probes all 4 backing services and returns 200 only when every probe is OK.
//
// @Summary      Deep dependency health
// @Description  Probes Postgres, NATS, Pulsar, and Redis concurrently. Returns 503 if any probe fails.
// @Tags         health
// @Produce      json
// @Success      200  {object}  object{status=string,dependencies=object}  "All dependencies healthy"
// @Failure      503  {object}  object{status=string,dependencies=object}  "One or more dependencies unhealthy"
// @Router       /health/deep [get]
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
//
// @Summary      Bootstrap readiness
// @Description  Returns 200 only after a successful bootstrap run completes. Use as a Kubernetes readiness probe.
// @Tags         health
// @Produce      json
// @Success      200  {object}  object{ready=bool}  "Bootstrap complete — service ready"
// @Failure      503  {object}  object{ready=bool}  "Bootstrap not yet complete"
// @Router       /ready [get]
func (h *Handler) Ready(c *gin.Context) {
	if h.orchestrator.IsReady() {
		c.JSON(http.StatusOK, gin.H{"ready": true})
		return
	}
	c.JSON(http.StatusServiceUnavailable, gin.H{"ready": false})
}
