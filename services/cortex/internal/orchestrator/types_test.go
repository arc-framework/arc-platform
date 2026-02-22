package orchestrator

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestBootstrapResult_ZeroValueIsUsable(t *testing.T) {
	t.Parallel()

	var r BootstrapResult

	// Embedded mutex must be lock/unlock-able on a zero-value struct.
	r.Lock()
	r.Status = "" // touch a field to satisfy SA2001 (non-empty critical section)
	r.Unlock()

	// Phases map is nil by design; the orchestrator initialises it in TASK-030.
	assert.Nil(t, r.Phases)
	assert.Empty(t, r.Status)
}

func TestBootstrapResult_JSONShape(t *testing.T) {
	t.Parallel()

	r := BootstrapResult{
		Status: "ok",
		Phases: map[string]PhaseResult{
			"db": {Name: "db", Status: "ok"},
		},
	}

	data, err := json.Marshal(&r)
	require.NoError(t, err)

	var got map[string]any
	require.NoError(t, json.Unmarshal(data, &got))

	assert.Equal(t, "ok", got["status"])
	phases, ok := got["phases"].(map[string]any)
	require.True(t, ok)
	db, ok := phases["db"].(map[string]any)
	require.True(t, ok)
	assert.Equal(t, "db", db["name"])
	assert.Equal(t, "ok", db["status"])
	// "error" field must be absent when empty (omitempty).
	_, hasError := db["error"]
	assert.False(t, hasError)
}

func TestPhaseResult_JSONShape(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name        string
		input       PhaseResult
		wantError   bool
		errorAbsent bool
	}{
		{
			name:        "no error field when empty",
			input:       PhaseResult{Name: "nats", Status: "ok"},
			errorAbsent: true,
		},
		{
			name:      "error field present when set",
			input:     PhaseResult{Name: "postgres", Status: "error", Error: "connection refused"},
			wantError: true,
		},
		{
			name:        "skipped status",
			input:       PhaseResult{Name: "pulsar", Status: "skipped"},
			errorAbsent: true,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()

			data, err := json.Marshal(tc.input)
			require.NoError(t, err)

			var got map[string]any
			require.NoError(t, json.Unmarshal(data, &got))

			assert.Equal(t, tc.input.Name, got["name"])
			assert.Equal(t, tc.input.Status, got["status"])

			_, hasError := got["error"]
			if tc.wantError {
				assert.True(t, hasError)
				assert.Equal(t, tc.input.Error, got["error"])
			}
			if tc.errorAbsent {
				assert.False(t, hasError)
			}
		})
	}
}

func TestProbeResult_JSONShape(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name        string
		input       ProbeResult
		wantError   bool
		errorAbsent bool
	}{
		{
			name:        "healthy probe",
			input:       ProbeResult{Name: "redis", OK: true, LatencyMs: 3},
			errorAbsent: true,
		},
		{
			name:      "unhealthy probe with error",
			input:     ProbeResult{Name: "nats", OK: false, LatencyMs: 0, Error: "timeout"},
			wantError: true,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()

			data, err := json.Marshal(tc.input)
			require.NoError(t, err)

			var got map[string]any
			require.NoError(t, json.Unmarshal(data, &got))

			assert.Equal(t, tc.input.Name, got["name"])
			assert.Equal(t, tc.input.OK, got["ok"])
			assert.Equal(t, float64(tc.input.LatencyMs), got["latencyMs"])

			_, hasError := got["error"]
			if tc.wantError {
				assert.True(t, hasError)
				assert.Equal(t, tc.input.Error, got["error"])
			}
			if tc.errorAbsent {
				assert.False(t, hasError)
			}
		})
	}
}
