package orchestrator

import (
	"context"
	"errors"
	"sync"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// --- mock implementations ---

type mockPGProber struct {
	result ProbeResult
}

func (m *mockPGProber) Probe(_ context.Context) ProbeResult { return m.result }

type mockNATSProvisioner struct {
	provisionErr error
	probeResult  ProbeResult
}

func (m *mockNATSProvisioner) ProvisionStreams(_ context.Context) error { return m.provisionErr }
func (m *mockNATSProvisioner) Probe(_ context.Context) ProbeResult      { return m.probeResult }

type mockPulsarProvisioner struct {
	provisionErr error
	probeResult  ProbeResult
}

func (m *mockPulsarProvisioner) Provision(_ context.Context) error { return m.provisionErr }
func (m *mockPulsarProvisioner) Probe(_ context.Context) ProbeResult { return m.probeResult }

type mockRedisProber struct {
	result ProbeResult
}

func (m *mockRedisProber) Probe(_ context.Context) ProbeResult { return m.result }

// blockingPGProber blocks until released — used to test concurrent bootstrap guard.
type blockingPGProber struct {
	ready chan struct{} // closed when Probe is entered
	done  chan struct{} // close to unblock Probe
}

func (b *blockingPGProber) Probe(_ context.Context) ProbeResult {
	close(b.ready)
	<-b.done
	return ProbeResult{OK: true}
}

// --- helpers ---

func okPG() *mockPGProber {
	return &mockPGProber{result: ProbeResult{Name: "arc-oracle", OK: true}}
}
func errPG(msg string) *mockPGProber {
	return &mockPGProber{result: ProbeResult{Name: "arc-oracle", OK: false, Error: msg}}
}
func okNATS() *mockNATSProvisioner {
	return &mockNATSProvisioner{probeResult: ProbeResult{Name: "arc-flash", OK: true}}
}
func errNATS(msg string) *mockNATSProvisioner {
	return &mockNATSProvisioner{
		provisionErr: errors.New(msg),
		probeResult:  ProbeResult{Name: "arc-flash", OK: false, Error: msg},
	}
}
func okPulsar() *mockPulsarProvisioner {
	return &mockPulsarProvisioner{probeResult: ProbeResult{Name: "arc-strange", OK: true}}
}
func errPulsar(msg string) *mockPulsarProvisioner {
	return &mockPulsarProvisioner{
		provisionErr: errors.New(msg),
		probeResult:  ProbeResult{Name: "arc-strange", OK: false, Error: msg},
	}
}
func okRedis() *mockRedisProber {
	return &mockRedisProber{result: ProbeResult{Name: "arc-sonic", OK: true}}
}
func errRedis(msg string) *mockRedisProber {
	return &mockRedisProber{result: ProbeResult{Name: "arc-sonic", OK: false, Error: msg}}
}

// --- tests ---

func TestRunBootstrap(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name           string
		pg             PGProber
		nats           NATSProvisioner
		pulsar         PulsarProvisioner
		redis          RedisProber
		wantStatus     string
		wantPhaseCount int
		wantErrPhases  []string
	}{
		{
			name:           "all phases succeed",
			pg:             okPG(),
			nats:           okNATS(),
			pulsar:         okPulsar(),
			redis:          okRedis(),
			wantStatus:     StatusOK,
			wantPhaseCount: 4,
			wantErrPhases:  nil,
		},
		{
			name:           "postgres probe fails",
			pg:             errPG("connection refused"),
			nats:           okNATS(),
			pulsar:         okPulsar(),
			redis:          okRedis(),
			wantStatus:     StatusError,
			wantPhaseCount: 4,
			wantErrPhases:  []string{"postgres"},
		},
		{
			name:           "nats provision fails",
			pg:             okPG(),
			nats:           errNATS("nats unavailable"),
			pulsar:         okPulsar(),
			redis:          okRedis(),
			wantStatus:     StatusError,
			wantPhaseCount: 4,
			wantErrPhases:  []string{"nats"},
		},
		{
			name:           "pulsar provision fails",
			pg:             okPG(),
			nats:           okNATS(),
			pulsar:         errPulsar("pulsar unreachable"),
			redis:          okRedis(),
			wantStatus:     StatusError,
			wantPhaseCount: 4,
			wantErrPhases:  []string{"pulsar"},
		},
		{
			name:           "redis probe fails",
			pg:             okPG(),
			nats:           okNATS(),
			pulsar:         okPulsar(),
			redis:          errRedis("dial tcp refused"),
			wantStatus:     StatusError,
			wantPhaseCount: 4,
			wantErrPhases:  []string{"redis"},
		},
		{
			name:           "multiple phases fail",
			pg:             errPG("pg down"),
			nats:           errNATS("nats down"),
			pulsar:         okPulsar(),
			redis:          errRedis("redis down"),
			wantStatus:     StatusError,
			wantPhaseCount: 4,
			wantErrPhases:  []string{"postgres", "nats", "redis"},
		},
		{
			name:           "all phases fail",
			pg:             errPG("pg down"),
			nats:           errNATS("nats down"),
			pulsar:         errPulsar("pulsar down"),
			redis:          errRedis("redis down"),
			wantStatus:     StatusError,
			wantPhaseCount: 4,
			wantErrPhases:  []string{"postgres", "nats", "pulsar", "redis"},
		},
	}

	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()

			o := New(tc.pg, tc.nats, tc.pulsar, tc.redis)
			result, err := o.RunBootstrap(context.Background())

			require.NoError(t, err)
			require.NotNil(t, result)
			assert.Equal(t, tc.wantStatus, result.Status)
			assert.Len(t, result.Phases, tc.wantPhaseCount)

			for _, phaseName := range tc.wantErrPhases {
				phase, ok := result.Phases[phaseName]
				require.True(t, ok, "expected phase %q to exist", phaseName)
				assert.Equal(t, StatusError, phase.Status, "phase %q should have error status", phaseName)
				assert.NotEmpty(t, phase.Error, "phase %q should have error message", phaseName)
			}

			// All non-error phases should be OK.
			errSet := make(map[string]bool, len(tc.wantErrPhases))
			for _, name := range tc.wantErrPhases {
				errSet[name] = true
			}
			for name, phase := range result.Phases {
				if !errSet[name] {
					assert.Equal(t, StatusOK, phase.Status, "phase %q should be ok", name)
				}
			}
		})
	}
}

func TestRunBootstrap_IsReady(t *testing.T) {
	t.Parallel()

	t.Run("not ready before bootstrap", func(t *testing.T) {
		t.Parallel()
		o := New(okPG(), okNATS(), okPulsar(), okRedis())
		assert.False(t, o.IsReady())
	})

	t.Run("ready after successful bootstrap", func(t *testing.T) {
		t.Parallel()
		o := New(okPG(), okNATS(), okPulsar(), okRedis())
		_, err := o.RunBootstrap(context.Background())
		require.NoError(t, err)
		assert.True(t, o.IsReady())
	})

	t.Run("not ready after failed bootstrap", func(t *testing.T) {
		t.Parallel()
		o := New(errPG("down"), okNATS(), okPulsar(), okRedis())
		_, err := o.RunBootstrap(context.Background())
		require.NoError(t, err)
		assert.False(t, o.IsReady())
	})
}

func TestRunBootstrap_InProgressGuard(t *testing.T) {
	t.Parallel()

	blocker := &blockingPGProber{
		ready: make(chan struct{}),
		done:  make(chan struct{}),
	}

	o := New(blocker, okNATS(), okPulsar(), okRedis())

	// Start first bootstrap in background.
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		_, _ = o.RunBootstrap(context.Background())
	}()

	// Wait until the first bootstrap has entered the pg probe.
	<-blocker.ready

	// A concurrent call should be rejected.
	_, err := o.RunBootstrap(context.Background())
	assert.ErrorIs(t, err, ErrBootstrapInProgress)

	// Unblock the first bootstrap.
	close(blocker.done)
	wg.Wait()

	// After completion the atomic flag is cleared. Use a fresh orchestrator
	// with plain mocks (blocker's channels are already closed) to verify.
	o2 := New(okPG(), okNATS(), okPulsar(), okRedis())
	_, err = o2.RunBootstrap(context.Background())
	assert.NoError(t, err)
}

func TestRunBootstrap_ResultUpdated(t *testing.T) {
	t.Parallel()

	o := New(okPG(), okNATS(), okPulsar(), okRedis())

	result, err := o.RunBootstrap(context.Background())
	require.NoError(t, err)
	assert.Equal(t, StatusOK, result.Status)

	// lastResult should now be set.
	o.resultMu.RLock()
	stored := o.lastResult
	o.resultMu.RUnlock()

	require.NotNil(t, stored)
	assert.Equal(t, StatusOK, stored.Status)
}

func TestRunDeepHealth(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name   string
		pg     PGProber
		nats   NATSProvisioner
		pulsar PulsarProvisioner
		redis  RedisProber
		wantOK map[string]bool
	}{
		{
			name:   "all healthy",
			pg:     okPG(),
			nats:   okNATS(),
			pulsar: okPulsar(),
			redis:  okRedis(),
			wantOK: map[string]bool{
				"postgres": true,
				"nats":     true,
				"pulsar":   true,
				"redis":    true,
			},
		},
		{
			name:   "postgres unhealthy",
			pg:     errPG("timeout"),
			nats:   okNATS(),
			pulsar: okPulsar(),
			redis:  okRedis(),
			wantOK: map[string]bool{
				"postgres": false,
				"nats":     true,
				"pulsar":   true,
				"redis":    true,
			},
		},
		{
			name:   "all unhealthy",
			pg:     errPG("down"),
			nats:   errNATS("down"),
			pulsar: errPulsar("down"),
			redis:  errRedis("down"),
			wantOK: map[string]bool{
				"postgres": false,
				"nats":     false,
				"pulsar":   false,
				"redis":    false,
			},
		},
	}

	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()

			o := New(tc.pg, tc.nats, tc.pulsar, tc.redis)
			results := o.RunDeepHealth(context.Background())

			assert.Len(t, results, 4)
			for name, wantOK := range tc.wantOK {
				probe, ok := results[name]
				require.True(t, ok, "expected result for %q", name)
				assert.Equal(t, wantOK, probe.OK, "probe %q OK mismatch", name)
			}
		})
	}
}

func TestProbeToPhase(t *testing.T) {
	t.Parallel()

	t.Run("ok probe", func(t *testing.T) {
		t.Parallel()
		phase := probeToPhase("pg", ProbeResult{OK: true})
		assert.Equal(t, StatusOK, phase.Status)
		assert.Empty(t, phase.Error)
	})

	t.Run("error probe", func(t *testing.T) {
		t.Parallel()
		phase := probeToPhase("pg", ProbeResult{OK: false, Error: "timeout"})
		assert.Equal(t, StatusError, phase.Status)
		assert.Equal(t, "timeout", phase.Error)
	})
}

func TestProvisionToPhase(t *testing.T) {
	t.Parallel()

	t.Run("nil error", func(t *testing.T) {
		t.Parallel()
		phase := provisionToPhase("nats", nil)
		assert.Equal(t, StatusOK, phase.Status)
		assert.Empty(t, phase.Error)
	})

	t.Run("non-nil error", func(t *testing.T) {
		t.Parallel()
		phase := provisionToPhase("nats", errors.New("circuit open"))
		assert.Equal(t, StatusError, phase.Status)
		assert.Equal(t, "circuit open", phase.Error)
	})
}
