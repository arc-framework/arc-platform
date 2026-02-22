package config

import (
	"os"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Note: t.Parallel() is intentionally omitted in this package.
// These tests share process-global environment variables; t.Setenv in
// TestLoad_EnvOverride would race with any concurrent reader.

func TestLoad_Defaults(t *testing.T) {
	cfg, err := Load("")
	require.NoError(t, err)

	assert.Equal(t, 8081, cfg.Server.Port)
	assert.Equal(t, "arc-widow:4317", cfg.Telemetry.OTLPEndpoint)
	assert.Equal(t, "arc-cortex", cfg.Telemetry.ServiceName)
	assert.Equal(t, "arc-oracle", cfg.Bootstrap.Postgres.Host)
	assert.Equal(t, "nats://arc-flash:4222", cfg.Bootstrap.NATS.URL)
	assert.Equal(t, "arc-system", cfg.Bootstrap.Pulsar.Tenant)
	assert.Equal(t, "arc-sonic", cfg.Bootstrap.Redis.Host)
}

func TestLoad_EnvOverride(t *testing.T) {
	t.Setenv("CORTEX_SERVER_PORT", "9090")
	t.Setenv("CORTEX_BOOTSTRAP_POSTGRES_HOST", "my-db")
	t.Setenv("CORTEX_BOOTSTRAP_NATS_URL", "nats://custom:4222")

	cfg, err := Load("")
	require.NoError(t, err)

	assert.Equal(t, 9090, cfg.Server.Port)
	assert.Equal(t, "my-db", cfg.Bootstrap.Postgres.Host)
	assert.Equal(t, "nats://custom:4222", cfg.Bootstrap.NATS.URL)
}

func TestLoad_InvalidFile(t *testing.T) {
	_, err := Load("/nonexistent/path/config.yaml")
	assert.Error(t, err)
}

func TestLoad_EnvIsolation(t *testing.T) {
	// Ensure a previous test's env vars don't leak — each sub-test uses t.Setenv
	// which auto-cleans via t.Cleanup.
	require.Empty(t, os.Getenv("CORTEX_SERVER_PORT"))

	cfg, err := Load("")
	require.NoError(t, err)
	assert.Equal(t, 8081, cfg.Server.Port)
}
