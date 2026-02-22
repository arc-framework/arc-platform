package clients

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/sony/gobreaker"

	"arc-framework/cortex/internal/config"
	"arc-framework/cortex/internal/orchestrator"
)

const probeName = "arc-oracle"

// dbPinger abstracts the pgxpool.Pool methods used in Probe so that tests
// can inject a fake without standing up a real database.
type dbPinger interface {
	Ping(ctx context.Context) error
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Close()
}

// PostgresClient wraps a pgx connection pool with a circuit breaker.
type PostgresClient struct {
	cfg     config.PostgresConfig
	cb      *gobreaker.CircuitBreaker
	connect func(ctx context.Context, cfg config.PostgresConfig) (dbPinger, error)
}

// NewPostgresClient creates a PostgresClient that lazily opens a pgx pool on
// the first call to Probe. The circuit breaker is applied around each probe
// attempt. No connection is made at construction time.
func NewPostgresClient(cfg config.PostgresConfig, cb *gobreaker.CircuitBreaker) *PostgresClient {
	return &PostgresClient{
		cfg:     cfg,
		cb:      cb,
		connect: realConnect,
	}
}

// Probe pings the Postgres server and verifies the schema_migrations table
// exists in the public schema. It wraps the check in the circuit breaker so
// that persistent failures trip the breaker after three consecutive errors.
func (c *PostgresClient) Probe(ctx context.Context) orchestrator.ProbeResult {
	start := time.Now()

	_, err := c.cb.Execute(func() (any, error) {
		pool, err := c.connect(ctx, c.cfg)
		if err != nil {
			return nil, err
		}
		defer pool.Close()

		if err := pool.Ping(ctx); err != nil {
			return nil, fmt.Errorf("ping: %w", err)
		}

		var exists int
		row := pool.QueryRow(ctx,
			"SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='schema_migrations'",
		)
		if err := row.Scan(&exists); err != nil {
			return nil, fmt.Errorf("schema_migrations table not found: %w", err)
		}

		return nil, nil
	})

	latency := time.Since(start).Milliseconds()

	if err != nil {
		errMsg := err.Error()
		if errors.Is(err, gobreaker.ErrOpenState) {
			errMsg = "circuit open"
		}
		return orchestrator.ProbeResult{
			Name:      probeName,
			OK:        false,
			LatencyMs: latency,
			Error:     errMsg,
		}
	}

	return orchestrator.ProbeResult{
		Name:      probeName,
		OK:        true,
		LatencyMs: latency,
	}
}

// realConnect opens a pgxpool.Pool using the provided PostgresConfig.
func realConnect(ctx context.Context, cfg config.PostgresConfig) (dbPinger, error) {
	dsn := fmt.Sprintf(
		"postgres://%s:%s@%s:%d/%s?sslmode=%s",
		cfg.User, cfg.Password, cfg.Host, cfg.Port, cfg.DB, cfg.SSLMode,
	)

	poolCfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("parsing postgres DSN: %w", err)
	}
	poolCfg.MaxConns = cfg.MaxConns

	pool, err := pgxpool.NewWithConfig(ctx, poolCfg)
	if err != nil {
		return nil, fmt.Errorf("opening postgres pool: %w", err)
	}

	return pool, nil
}
