package clients

import (
	"context"
	"errors"
	"testing"

	"github.com/stretchr/testify/assert"
)

// mockRedisPinger is a test double for redisPinger.
type mockRedisPinger struct {
	pingVal string
	pingErr error
}

func (m *mockRedisPinger) PingResult(_ context.Context) (string, error) {
	return m.pingVal, m.pingErr
}

func (m *mockRedisPinger) Close() error { return nil }

func TestRedisProbe(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name       string
		pingVal    string
		pingErr    error
		wantOK     bool
		wantErrSub string
	}{
		{
			name:    "success — PING returns PONG",
			pingVal: "PONG",
			wantOK:  true,
		},
		{
			name:       "failure — PING returns error",
			pingErr:    errors.New("connection refused"),
			wantOK:     false,
			wantErrSub: "connection refused",
		},
		{
			name:       "failure — PING returns unexpected value",
			pingVal:    "WHOOPS",
			wantOK:     false,
			wantErrSub: "unexpected PING response",
		},
	}

	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()

			cb := NewCircuitBreaker("redis-test-" + tc.name)
			client := &RedisClient{
				cb:     cb,
				pinger: &mockRedisPinger{pingVal: tc.pingVal, pingErr: tc.pingErr},
			}

			result := client.Probe(context.Background())

			assert.Equal(t, redisProbeName, result.Name)
			assert.Equal(t, tc.wantOK, result.OK)
			if tc.wantErrSub != "" {
				assert.Contains(t, result.Error, tc.wantErrSub)
			}
			if tc.wantOK {
				assert.Empty(t, result.Error)
			}
		})
	}
}

func TestRedisProbeCircuitBreaker_OpensAfterThreeFailures(t *testing.T) {
	t.Parallel()

	cb := NewCircuitBreaker("redis-cb-open-test")
	mock := &mockRedisPinger{pingErr: errors.New("connection refused")}
	client := &RedisClient{cb: cb, pinger: mock}

	// Three consecutive failures should trip the breaker.
	for i := range 3 {
		result := client.Probe(context.Background())
		assert.False(t, result.OK, "probe %d should fail", i+1)
		assert.NotEqual(t, "circuit open", result.Error,
			"probe %d should not be circuit-open yet", i+1)
	}

	// The 4th call must be rejected immediately by the open breaker.
	result := client.Probe(context.Background())
	assert.False(t, result.OK)
	assert.Equal(t, "circuit open", result.Error)
}
