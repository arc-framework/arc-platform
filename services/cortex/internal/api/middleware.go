package api

import (
	"log/slog"
	"net/http"
	"runtime/debug"
	"time"

	"github.com/gin-gonic/gin"
	"go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin"
)

// Recovery returns a middleware that recovers from panics, logs the stack trace,
// and returns a 500 to the client so the server continues serving.
func Recovery(logger *slog.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		defer func() {
			if r := recover(); r != nil {
				stack := debug.Stack()
				logger.Error("panic recovered",
					"panic", r,
					"stack", string(stack),
					"method", c.Request.Method,
					"path", c.Request.URL.Path,
				)
				c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{
					"status": "error",
					"error":  "internal server error",
				})
			}
		}()
		c.Next()
	}
}

// FridayOTEL returns a middleware that injects OTEL trace context into each
// request using otelgin. The serviceName is attached to each span.
func FridayOTEL(serviceName string) gin.HandlerFunc {
	return otelgin.Middleware(serviceName)
}

// RequestLogger returns a middleware that emits a structured slog line for
// every request with method, path, status, and latency.
func RequestLogger(logger *slog.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		c.Next()
		logger.Info("request",
			"method", c.Request.Method,
			"path", c.Request.URL.Path,
			"status", c.Writer.Status(),
			"latency_ms", time.Since(start).Milliseconds(),
			"client_ip", c.ClientIP(),
		)
	}
}
