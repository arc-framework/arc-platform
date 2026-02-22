package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"time"

	"arc-framework/cortex/internal/clients"
	"arc-framework/cortex/internal/orchestrator"
	"arc-framework/cortex/internal/telemetry"

	"github.com/sony/gobreaker"
	"github.com/spf13/cobra"
)

var bootstrapCmd = &cobra.Command{
	Use:   "bootstrap",
	Short: "Run one-shot platform bootstrap and exit",
	Long: `Bootstrap seeds all platform infrastructure dependencies:
Postgres schemas, NATS streams, Pulsar topics, and Redis configuration.

The command runs once, prints a JSON result to stdout, and exits 0 on
success or non-zero on failure.`,
	RunE: runBootstrap,
}

func runBootstrap(cmd *cobra.Command, args []string) error {
	ctx, cancel := context.WithTimeout(context.Background(), cfg.Bootstrap.Timeout)
	defer cancel()

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

	slog.Info("starting bootstrap")

	// Build circuit breakers with default settings (3 consecutive failures trip
	// the breaker). TASK-040 will move this wiring into a proper DI layer.
	cbSettings := gobreaker.Settings{Name: "bootstrap"}
	pg := clients.NewPostgresClient(cfg.Bootstrap.Postgres, gobreaker.NewCircuitBreaker(cbSettings))
	nats := clients.NewNATSClient(cfg.Bootstrap.NATS, gobreaker.NewCircuitBreaker(cbSettings))
	pulsar := clients.NewPulsarClient(cfg.Bootstrap.Pulsar, gobreaker.NewCircuitBreaker(cbSettings))
	redis := clients.NewRedisClient(cfg.Bootstrap.Redis, gobreaker.NewCircuitBreaker(cbSettings))

	o := orchestrator.New(pg, nats, pulsar, redis)

	result, err := o.RunBootstrap(ctx)
	if err != nil {
		printResult("error", err.Error())
		return fmt.Errorf("bootstrap failed: %w", err)
	}

	if result.Status == orchestrator.StatusError {
		printBootstrapResult(result)
		return fmt.Errorf("bootstrap completed with errors")
	}

	printBootstrapResult(result)
	slog.Info("bootstrap completed successfully")
	return nil
}

func printBootstrapResult(result *orchestrator.BootstrapResult) {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(result); err != nil {
		fmt.Fprintf(os.Stdout, `{"status":%q}`+"\n", result.Status)
	}
}

func printResult(status, errMsg string) {
	result := map[string]string{"status": status}
	if errMsg != "" {
		result["error"] = errMsg
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(result); err != nil {
		// Fallback to plain text if JSON encoding somehow fails.
		fmt.Fprintf(os.Stdout, `{"status":%q}`+"\n", status)
	}
}
