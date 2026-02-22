package main

import (
	"fmt"
	"log/slog"
	"os"
	"strings"

	"arc-framework/cortex/internal/config"
	"arc-framework/cortex/internal/telemetry"

	"github.com/spf13/cobra"
)

var (
	cfgFile  string
	logLevel string

	// cfg is populated by PersistentPreRunE and shared with all subcommands.
	cfg *config.Config

	// app holds all wired dependencies; populated by PersistentPreRunE.
	app *AppContext
)

var rootCmd = &cobra.Command{
	Use:   "cortex",
	Short: "A.R.C. Cortex — platform bootstrap service",
	Long: `Cortex is the A.R.C. platform bootstrap service.
It seeds infrastructure dependencies (Postgres, NATS, Pulsar, Redis)
and exposes a health/status HTTP API.`,
	SilenceUsage: true,
}

func init() {
	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "path to config file (YAML)")
	rootCmd.PersistentFlags().StringVar(&logLevel, "log-level", "info", "log level (debug, info, warn, error)")

	rootCmd.PersistentPreRunE = func(cmd *cobra.Command, args []string) error {
		initLogger(logLevel)

		var err error
		cfg, err = config.Load(cfgFile)
		if err != nil {
			return fmt.Errorf("loading config: %w", err)
		}

		// --log-level flag takes precedence over value in config file.
		if cmd.Flags().Changed("log-level") {
			cfg.Telemetry.LogLevel = logLevel
		} else if cfg.Telemetry.LogLevel != "" {
			// Re-init logger with config file value if the flag was not explicitly set.
			initLogger(cfg.Telemetry.LogLevel)
		}

		app, err = buildAppContext(cfg)
		if err != nil {
			return fmt.Errorf("building app context: %w", err)
		}

		return nil
	}

	rootCmd.AddCommand(serverCmd)
	rootCmd.AddCommand(bootstrapCmd)
}

// Execute is the entry point called by main.
func Execute() {
	if err := rootCmd.Execute(); err != nil {
		os.Exit(1)
	}
}

func initLogger(level string) {
	var lvl slog.Level
	switch strings.ToLower(level) {
	case "debug":
		lvl = slog.LevelDebug
	case "warn", "warning":
		lvl = slog.LevelWarn
	case "error":
		lvl = slog.LevelError
	default:
		lvl = slog.LevelInfo
	}

	handler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: lvl})
	slog.SetDefault(slog.New(telemetry.NewTraceHandler(handler)))
}
