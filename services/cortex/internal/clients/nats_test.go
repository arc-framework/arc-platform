package clients

import (
	"context"
	"errors"
	"testing"

	"github.com/nats-io/nats.go"
	"github.com/sony/gobreaker"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"arc-framework/cortex/internal/config"
)

// fakeJS is a test double for jsContext. It records calls and returns
// preconfigured responses.
type fakeJS struct {
	// streamInfoErr is keyed by stream name; a nil value means "stream exists".
	streamInfoErr map[string]error

	addStreamErr    error
	updateStreamErr error

	addStreamCalls    []string
	updateStreamCalls []string
}

func (f *fakeJS) StreamInfo(stream string, _ ...nats.JSOpt) (*nats.StreamInfo, error) {
	err, ok := f.streamInfoErr[stream]
	if !ok || err == nil {
		return &nats.StreamInfo{}, nil
	}
	return nil, err
}

func (f *fakeJS) AddStream(cfg *nats.StreamConfig, _ ...nats.JSOpt) (*nats.StreamInfo, error) {
	f.addStreamCalls = append(f.addStreamCalls, cfg.Name)
	return &nats.StreamInfo{}, f.addStreamErr
}

func (f *fakeJS) UpdateStream(cfg *nats.StreamConfig, _ ...nats.JSOpt) (*nats.StreamInfo, error) {
	f.updateStreamCalls = append(f.updateStreamCalls, cfg.Name)
	return &nats.StreamInfo{}, f.updateStreamErr
}

// makeNATSClient builds a NATSClient backed by the provided fakeJS.
func makeNATSClient(js jsContext, cb *gobreaker.CircuitBreaker) *NATSClient {
	return &NATSClient{
		url: "nats://localhost:4222",
		cb:  cb,
		newJS: func(_ string) (jsContext, func(), error) {
			return js, func() {}, nil
		},
	}
}

// makeNATSClientWithConnErr builds a NATSClient whose connection always fails.
func makeNATSClientWithConnErr(connErr error, cb *gobreaker.CircuitBreaker) *NATSClient {
	return &NATSClient{
		url: "nats://localhost:4222",
		cb:  cb,
		newJS: func(_ string) (jsContext, func(), error) {
			return nil, func() {}, connErr
		},
	}
}

func TestNewNATSClient(t *testing.T) {
	t.Parallel()

	cb := NewCircuitBreaker("new-nats-test")
	cfg := config.NATSConfig{URL: "nats://arc-flash:4222"}
	client := NewNATSClient(cfg, cb)

	assert.NotNil(t, client)
	assert.Equal(t, "nats://arc-flash:4222", client.url)
	assert.NotNil(t, client.newJS)
}

func TestProvisionStreams_AllNew(t *testing.T) {
	t.Parallel()

	js := &fakeJS{
		streamInfoErr: map[string]error{
			"AGENT_COMMANDS": nats.ErrStreamNotFound,
			"AGENT_EVENTS":   nats.ErrStreamNotFound,
			"SYSTEM_METRICS": nats.ErrStreamNotFound,
		},
	}

	client := makeNATSClient(js, NewCircuitBreaker("provision-all-new"))
	err := client.ProvisionStreams(context.Background())

	require.NoError(t, err)
	assert.ElementsMatch(t, []string{"AGENT_COMMANDS", "AGENT_EVENTS", "SYSTEM_METRICS"}, js.addStreamCalls)
	assert.Empty(t, js.updateStreamCalls)
}

func TestProvisionStreams_AllExisting(t *testing.T) {
	t.Parallel()

	// nil errors in streamInfoErr mean the stream exists.
	js := &fakeJS{
		streamInfoErr: map[string]error{
			"AGENT_COMMANDS": nil,
			"AGENT_EVENTS":   nil,
			"SYSTEM_METRICS": nil,
		},
	}

	client := makeNATSClient(js, NewCircuitBreaker("provision-all-existing"))
	err := client.ProvisionStreams(context.Background())

	require.NoError(t, err)
	assert.Empty(t, js.addStreamCalls)
	assert.ElementsMatch(t, []string{"AGENT_COMMANDS", "AGENT_EVENTS", "SYSTEM_METRICS"}, js.updateStreamCalls)
}

func TestProvisionStreams_AddStreamError(t *testing.T) {
	t.Parallel()

	addErr := errors.New("server unavailable")
	js := &fakeJS{
		streamInfoErr: map[string]error{
			"AGENT_COMMANDS": nats.ErrStreamNotFound,
			"AGENT_EVENTS":   nats.ErrStreamNotFound,
			"SYSTEM_METRICS": nats.ErrStreamNotFound,
		},
		addStreamErr: addErr,
	}

	client := makeNATSClient(js, NewCircuitBreaker("provision-add-err"))
	err := client.ProvisionStreams(context.Background())

	require.Error(t, err)
	assert.Contains(t, err.Error(), "server unavailable")
}

func TestProvisionStreams_CircuitBreakerOpensAfterThreeFailures(t *testing.T) {
	t.Parallel()

	connErr := errors.New("dial tcp: connection refused")
	cb := NewCircuitBreaker("provision-cb-open")
	client := makeNATSClientWithConnErr(connErr, cb)

	for i := range 3 {
		err := client.ProvisionStreams(context.Background())
		require.Error(t, err, "attempt %d should fail", i+1)
		assert.NotContains(t, err.Error(), "circuit open",
			"circuit should not be open yet on attempt %d", i+1)
	}

	// The 4th call must be rejected by the open circuit breaker.
	err := client.ProvisionStreams(context.Background())
	require.Error(t, err)
	assert.Contains(t, err.Error(), "circuit open")
}

func TestProbe_Success(t *testing.T) {
	t.Parallel()

	// AGENT_COMMANDS exists; StreamInfo returns successfully.
	js := &fakeJS{
		streamInfoErr: map[string]error{
			"AGENT_COMMANDS": nil,
		},
	}

	client := makeNATSClient(js, NewCircuitBreaker("probe-success"))
	result := client.Probe(context.Background())

	assert.Equal(t, natsProbeNameConst, result.Name)
	assert.True(t, result.OK)
	assert.Empty(t, result.Error)
}

func TestProbe_StreamNotFoundIsOK(t *testing.T) {
	t.Parallel()

	// Streams not yet provisioned — NATS is up, stream just missing.
	js := &fakeJS{
		streamInfoErr: map[string]error{
			"AGENT_COMMANDS": nats.ErrStreamNotFound,
		},
	}

	client := makeNATSClient(js, NewCircuitBreaker("probe-stream-not-found"))
	result := client.Probe(context.Background())

	assert.Equal(t, natsProbeNameConst, result.Name)
	assert.True(t, result.OK)
	assert.Empty(t, result.Error)
}

func TestProbe_ConnectionFailure(t *testing.T) {
	t.Parallel()

	connErr := errors.New("connection refused")
	client := makeNATSClientWithConnErr(connErr, NewCircuitBreaker("probe-conn-fail"))
	result := client.Probe(context.Background())

	assert.Equal(t, natsProbeNameConst, result.Name)
	assert.False(t, result.OK)
	assert.Contains(t, result.Error, "connection refused")
}

func TestProbe_CircuitOpenAfterThreeFailures(t *testing.T) {
	t.Parallel()

	connErr := errors.New("connection refused")
	cb := NewCircuitBreaker("probe-cb-open")
	client := makeNATSClientWithConnErr(connErr, cb)

	for i := range 3 {
		result := client.Probe(context.Background())
		assert.False(t, result.OK, "probe %d should fail", i+1)
		assert.NotEqual(t, "circuit open", result.Error,
			"probe %d should not be circuit-open yet", i+1)
	}

	result := client.Probe(context.Background())
	assert.False(t, result.OK)
	assert.Equal(t, "circuit open", result.Error)
}
