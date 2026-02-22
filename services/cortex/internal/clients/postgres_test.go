package clients

import (
	"context"
	"errors"
	"testing"

	"github.com/jackc/pgx/v5"
	"github.com/sony/gobreaker"
	"github.com/stretchr/testify/assert"

	"arc-framework/cortex/internal/config"
)

// mockRow implements pgx.Row for use in tests.
type mockRow struct {
	scanErr error
	val     any
}

func (r *mockRow) Scan(dest ...any) error {
	if r.scanErr != nil {
		return r.scanErr
	}
	if len(dest) > 0 {
		if ptr, ok := dest[0].(*int); ok {
			if v, ok := r.val.(int); ok {
				*ptr = v
			}
		}
	}
	return nil
}

// mockDB implements dbPinger for use in tests.
type mockDB struct {
	pingErr  error
	queryRow pgx.Row
	closed   bool
}

func (m *mockDB) Ping(_ context.Context) error   { return m.pingErr }
func (m *mockDB) Close()                         { m.closed = true }
func (m *mockDB) QueryRow(_ context.Context, _ string, _ ...any) pgx.Row {
	return m.queryRow
}

// makeClient returns a PostgresClient with a stubbed connect function.
func makeClient(db dbPinger, connectErr error, cb *gobreaker.CircuitBreaker) *PostgresClient {
	return &PostgresClient{
		cfg: config.PostgresConfig{},
		cb:  cb,
		connect: func(_ context.Context, _ config.PostgresConfig) (dbPinger, error) {
			return db, connectErr
		},
	}
}

func TestProbe(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name       string
		pingErr    error
		scanErr    error
		connectErr error
		wantOK     bool
		wantErrSub string
	}{
		{
			name:    "success — ping ok and schema_migrations table exists",
			wantOK:  true,
			scanErr: nil,
			pingErr: nil,
		},
		{
			name:       "failure — ping error",
			pingErr:    errors.New("connection refused"),
			wantOK:     false,
			wantErrSub: "ping",
		},
		{
			name:       "failure — schema_migrations table absent",
			scanErr:    errors.New("no rows in result set"),
			wantOK:     false,
			wantErrSub: "schema_migrations",
		},
		{
			name:       "failure — connect error",
			connectErr: errors.New("dial error"),
			wantOK:     false,
			wantErrSub: "dial error",
		},
	}

	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()

			cb := NewCircuitBreaker("test-" + tc.name)

			var client *PostgresClient
			if tc.connectErr != nil {
				client = makeClient(nil, tc.connectErr, cb)
			} else {
				db := &mockDB{
					pingErr:  tc.pingErr,
					queryRow: &mockRow{scanErr: tc.scanErr, val: 1},
				}
				client = makeClient(db, nil, cb)
			}

			result := client.Probe(context.Background())

			assert.Equal(t, "arc-oracle", result.Name)
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

func TestProbeCircuitBreaker_OpensAfterThreeFailures(t *testing.T) {
	t.Parallel()

	cb := NewCircuitBreaker("cb-open-test")

	pingErr := errors.New("connection refused")
	makeFailingClient := func() *PostgresClient {
		return makeClient(&mockDB{
			pingErr:  pingErr,
			queryRow: &mockRow{val: 1},
		}, nil, cb)
	}

	client := makeFailingClient()

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

func TestNewCircuitBreaker(t *testing.T) {
	t.Parallel()

	cb := NewCircuitBreaker("unit-test")
	assert.NotNil(t, cb)
	assert.Equal(t, "unit-test", cb.Name())
}
