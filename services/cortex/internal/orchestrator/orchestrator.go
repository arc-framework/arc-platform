package orchestrator

import "context"

// RunBootstrap seeds all platform infrastructure dependencies (Postgres, NATS,
// Pulsar, Redis). This is a stub — the real implementation is added in TASK-030.
func RunBootstrap(_ context.Context) error {
	return nil
}
