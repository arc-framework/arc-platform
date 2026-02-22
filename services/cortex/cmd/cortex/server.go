package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"arc-framework/cortex/internal/telemetry"

	"github.com/gin-gonic/gin"
	"github.com/spf13/cobra"
)

var serverCmd = &cobra.Command{
	Use:   "server",
	Short: "Start the Cortex HTTP API server",
	Long: `Start the Cortex HTTP server on the configured port (default :8081).

The server exposes the full platform bootstrap API and initialises OTEL
telemetry on startup. It shuts down cleanly on SIGTERM or SIGINT.`,
	RunE: runServer,
}

func runServer(cmd *cobra.Command, args []string) error {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	// Initialise OTEL provider. A missing/unreachable collector is non-fatal —
	// InitProvider dials non-blocking, so startup continues regardless.
	tp, err := telemetry.InitProvider(
		ctx,
		cfg.Telemetry.OTLPEndpoint,
		cfg.Telemetry.ServiceName,
		cfg.Telemetry.OTLPInsecure,
	)
	if err != nil {
		slog.Warn("OTEL provider init failed — telemetry disabled", "err", err)
	} else {
		defer func() {
			shutCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			if shutErr := tp.Shutdown(shutCtx); shutErr != nil {
				slog.Warn("OTEL shutdown error", "err", shutErr)
			}
		}()
	}

	// Placeholder Gin router — full API added in TASK-031.
	gin.SetMode(gin.ReleaseMode)
	router := gin.New()
	router.Use(gin.Recovery())

	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "healthy"})
	})

	addr := fmt.Sprintf(":%d", cfg.Server.Port)
	srv := &http.Server{
		Addr:         addr,
		Handler:      router,
		ReadTimeout:  cfg.Server.ReadTimeout,
		WriteTimeout: cfg.Server.WriteTimeout,
	}

	// Start the server in a goroutine so we can listen for shutdown signals.
	serverErr := make(chan error, 1)
	go func() {
		slog.Info("cortex server listening", "addr", addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			serverErr <- err
		}
	}()

	select {
	case err := <-serverErr:
		return fmt.Errorf("server error: %w", err)
	case <-ctx.Done():
		slog.Info("shutdown signal received")
	}

	shutCtx, cancel := context.WithTimeout(context.Background(), cfg.Server.ShutdownTimeout)
	defer cancel()

	if err := srv.Shutdown(shutCtx); err != nil {
		return fmt.Errorf("graceful shutdown failed: %w", err)
	}

	slog.Info("server stopped cleanly")
	return nil
}
