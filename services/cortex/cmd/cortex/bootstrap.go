package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"time"

	"arc-framework/cortex/internal/orchestrator"
	"arc-framework/cortex/internal/telemetry"

	"github.com/spf13/cobra"
)

var bootstrapCmd = &cobra.Command{
	Use:   "bootstrap",
	Short: "Run one-shot platform bootstrap and exit",
	Long: `Bootstrap seeds all platform infrastructure dependencies:
Postgres schemas, NATS streams, Pulsar topics, and Redis configuration.

The command runs once, prints a JSON result to stdout, and exits 0 on
success or non-zero on failure. The full bootstrap logic is implemented
in TASK-030; this wires the CLI entry point.`,
	RunE: runBootstrap,
}

func runBootstrap(cmd *cobra.Command, args []string) error {
	ctx := context.Background()

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

	if err := orchestrator.RunBootstrap(ctx); err != nil {
		printResult("error", err.Error())
		return fmt.Errorf("bootstrap failed: %w", err)
	}

	printResult("ok", "")
	slog.Info("bootstrap completed successfully")
	return nil
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
