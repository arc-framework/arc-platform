package api

import (
	"log/slog"
	"net/http"

	_ "arc-framework/cortex/docs" // register generated Swagger spec

	"github.com/gin-gonic/gin"
	swaggerFiles "github.com/swaggo/files"
	ginSwagger "github.com/swaggo/gin-swagger"
)

// Router wraps a configured Gin engine and exposes it as an http.Handler.
type Router struct {
	engine *gin.Engine
}

// NewRouter constructs a Router with the full middleware chain and all routes
// registered. The middleware order follows the spec (FR-3):
//  1. Recovery — panic → 500
//  2. FridayOTEL — trace context per request
//  3. RequestLogger — structured request/response logging
func NewRouter(o orchestratorService) *Router {
	gin.SetMode(gin.ReleaseMode)
	engine := gin.New()

	engine.Use(Recovery(slog.Default()))
	engine.Use(FridayOTEL("arc-cortex"))
	engine.Use(RequestLogger(slog.Default()))

	h := &Handler{orchestrator: o}

	v1 := engine.Group("/api/v1")
	v1.POST("/bootstrap", h.Bootstrap)

	engine.GET("/health", h.Health)
	engine.GET("/health/deep", h.DeepHealth)
	engine.GET("/ready", h.Ready)

	// API docs — http://localhost:8081/api-docs
	engine.GET("/api-docs", func(c *gin.Context) {
		c.Redirect(http.StatusMovedPermanently, "/api-docs/index.html")
	})
	engine.GET("/api-docs/*any", ginSwagger.WrapHandler(swaggerFiles.Handler))

	return &Router{engine: engine}
}

// Handler returns the underlying http.Handler for use with net/http servers.
func (r *Router) Handler() http.Handler {
	return r.engine
}
