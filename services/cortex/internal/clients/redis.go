package clients

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/sony/gobreaker"

	"arc-framework/cortex/internal/config"
	"arc-framework/cortex/internal/orchestrator"
)

const redisProbeName = "arc-sonic"

// redisPinger is the interface used by RedisClient for health probing.
// It is implemented by the real go-redis client and by test doubles.
type redisPinger interface {
	PingResult(ctx context.Context) (string, error)
	Close() error
}

// realRedisPinger wraps a *redis.Client and adapts it to the redisPinger
// interface. The wrapper exists so tests can inject a fake without needing to
// construct a real *redis.StatusCmd.
type realRedisPinger struct {
	client *redis.Client
}

func (r *realRedisPinger) PingResult(ctx context.Context) (string, error) {
	return r.client.Ping(ctx).Result()
}

func (r *realRedisPinger) Close() error {
	return r.client.Close()
}

// RedisClient wraps a go-redis connection with a circuit breaker and exposes a
// Probe method for readiness / health checks.
type RedisClient struct {
	cfg    config.RedisConfig
	cb     *gobreaker.CircuitBreaker
	pinger redisPinger
}

// NewRedisClient creates a RedisClient. No connection is opened at construction
// time; the real go-redis client is built lazily on the first Probe call.
func NewRedisClient(cfg config.RedisConfig, cb *gobreaker.CircuitBreaker) *RedisClient {
	return &RedisClient{
		cfg: cfg,
		cb:  cb,
	}
}

// Probe sends a PING command to Redis and validates the PONG response. The call
// is wrapped in the circuit breaker; after 3 consecutive failures the breaker
// opens and subsequent calls return immediately with "circuit open".
func (c *RedisClient) Probe(ctx context.Context) orchestrator.ProbeResult {
	start := time.Now()

	_, err := c.cb.Execute(func() (any, error) {
		p := c.pinger
		if p == nil {
			p = &realRedisPinger{
				client: redis.NewClient(&redis.Options{
					Addr:     fmt.Sprintf("%s:%d", c.cfg.Host, c.cfg.Port),
					Password: c.cfg.Password,
					DB:       c.cfg.DB,
				}),
			}
			defer p.Close() //nolint:errcheck
		}

		val, err := p.PingResult(ctx)
		if err != nil {
			return nil, fmt.Errorf("ping: %w", err)
		}
		if val != "PONG" {
			return nil, fmt.Errorf("unexpected PING response: %q", val)
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
			Name:      redisProbeName,
			OK:        false,
			LatencyMs: latency,
			Error:     errMsg,
		}
	}

	return orchestrator.ProbeResult{
		Name:      redisProbeName,
		OK:        true,
		LatencyMs: latency,
	}
}
