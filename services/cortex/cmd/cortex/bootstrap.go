package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"time"

	"arc-framework/cortex/internal/orchestrator"

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

	if app.otelProvider != nil {
		defer func() {
			shutCtx, shutCancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer shutCancel()
			if err := app.otelProvider.Shutdown(shutCtx); err != nil {
				slog.Warn("OTEL shutdown error", "err", err)
			}
		}()
	}

	slog.Info("starting bootstrap")

	result, err := app.orchestrator.RunBootstrap(ctx)
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
