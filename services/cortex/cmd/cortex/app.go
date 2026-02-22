package main

import (
	"context"
	"log/slog"

	"arc-framework/cortex/internal/api"
	"arc-framework/cortex/internal/clients"
	"arc-framework/cortex/internal/config"
	"arc-framework/cortex/internal/orchestrator"
	"arc-framework/cortex/internal/telemetry"

	"github.com/sony/gobreaker"
)

// AppContext holds all constructed application dependencies shared across
// subcommands. It is built once in PersistentPreRunE and referenced by
// server.go and bootstrap.go.
type AppContext struct {
	cfg          *config.Config
	otelProvider *telemetry.Provider
	orchestrator *orchestrator.Orchestrator
	router       *api.Router
}

// buildAppContext constructs all application dependencies from cfg:
//  1. Initialises the OTEL provider (best-effort, non-fatal)
//  2. Creates one circuit breaker per client
//  3. Creates the four infrastructure clients
//  4. Creates the orchestrator
//  5. Creates the HTTP router
func buildAppContext(cfg *config.Config) (*AppContext, error) {
	app := &AppContext{cfg: cfg}

	// OTEL is best-effort: a missing collector must never block startup.
	// When OTLPEndpoint is empty, telemetry is disabled entirely — this avoids
	// the SDK's 10s periodic-reader noise when no collector is running locally.
	if cfg.Telemetry.OTLPEndpoint == "" {
		slog.Info("OTEL telemetry disabled (no endpoint configured)")
	} else {
		tp, err := telemetry.InitProvider(
			context.Background(),
			cfg.Telemetry.OTLPEndpoint,
			cfg.Telemetry.ServiceName,
			cfg.Telemetry.OTLPInsecure,
		)
		if err != nil {
			slog.Warn("OTEL provider init failed — telemetry disabled", "err", err)
		} else {
			app.otelProvider = tp
			// Fan out: keep stdout (existing TraceHandler+JSONHandler) and add OTEL logs.
			slog.SetDefault(slog.New(telemetry.NewTeeHandler(
				slog.Default().Handler(),
				tp.LogHandler,
			)))
		}
	}

	// One circuit breaker per client so each dependency trips independently.
	pgCB := gobreaker.NewCircuitBreaker(gobreaker.Settings{Name: "postgres"})
	natsCB := gobreaker.NewCircuitBreaker(gobreaker.Settings{Name: "nats"})
	pulsarCB := gobreaker.NewCircuitBreaker(gobreaker.Settings{Name: "pulsar"})
	redisCB := gobreaker.NewCircuitBreaker(gobreaker.Settings{Name: "redis"})

	pg := clients.NewPostgresClient(cfg.Bootstrap.Postgres, pgCB)
	nats := clients.NewNATSClient(cfg.Bootstrap.NATS, natsCB)
	pulsar := clients.NewPulsarClient(cfg.Bootstrap.Pulsar, pulsarCB)
	redis := clients.NewRedisClient(cfg.Bootstrap.Redis, redisCB)

	app.orchestrator = orchestrator.New(pg, nats, pulsar, redis)
	app.router = api.NewRouter(app.orchestrator)

	return app, nil
}
