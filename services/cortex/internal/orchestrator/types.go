package orchestrator

import "sync"

// BootstrapResult is the aggregate result of a full bootstrap run.
// sync.Mutex is embedded so the orchestrator can write phases concurrently
// from multiple goroutines without external locking.
type BootstrapResult struct {
	sync.Mutex
	Status string                 `json:"status"` // "ok", "error", "in-progress"
	Phases map[string]PhaseResult `json:"phases"`
}

// PhaseResult represents the outcome of a single bootstrap phase.
type PhaseResult struct {
	Name   string `json:"name"`
	Status string `json:"status"` // "ok", "error", "skipped"
	Error  string `json:"error,omitempty"`
}

// ProbeResult is returned by RunDeepHealth for each dependency.
type ProbeResult struct {
	Name      string `json:"name"`
	OK        bool   `json:"ok"`
	LatencyMs int64  `json:"latencyMs"`
	Error     string `json:"error,omitempty"`
}
