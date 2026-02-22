package telemetry

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestInitProvider_UnreachableCollector(t *testing.T) {
	// Verifies InitProvider does not panic or error when the collector is down.
	// The gRPC dial is non-blocking so the connection attempt happens in the
	// background — from the caller's perspective setup always succeeds.
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	p, err := InitProvider(ctx, "localhost:19999", "arc-cortex-test", true)
	require.NoError(t, err)
	require.NotNil(t, p)

	shutCtx, shutCancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer shutCancel()
	assert.NoError(t, p.Shutdown(shutCtx))
}
