package orchestrator

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"golang.org/x/sync/errgroup"
)

// ErrBootstrapInProgress is returned when RunBootstrap is called while a
// bootstrap is already running.
var ErrBootstrapInProgress = errors.New("bootstrap already in progress")

// pgProber is satisfied by *clients.PostgresClient.
type pgProber interface {
	Probe(ctx context.Context) ProbeResult
}

// natsProvisioner is satisfied by *clients.NATSClient.
type natsProvisioner interface {
	ProvisionStreams(ctx context.Context) error
	Probe(ctx context.Context) ProbeResult
}

// pulsarProvisioner is satisfied by *clients.PulsarClient.
type pulsarProvisioner interface {
	Provision(ctx context.Context) error
	Probe(ctx context.Context) ProbeResult
}

// redisProber is satisfied by *clients.RedisClient.
type redisProber interface {
	Probe(ctx context.Context) ProbeResult
}

// Orchestrator runs bootstrap phases and health probes.
type Orchestrator struct {
	pg     pgProber
	nats   natsProvisioner
	pulsar pulsarProvisioner
	redis  redisProber

	bootstrapInProgress atomic.Bool
	lastResult          *BootstrapResult
	resultMu            sync.RWMutex
}

// New constructs an Orchestrator with the given clients. The concrete client
// types satisfy the interfaces defined in this package.
func New(pg pgProber, nats natsProvisioner, pulsar pulsarProvisioner, redis redisProber) *Orchestrator {
	return &Orchestrator{
		pg:     pg,
		nats:   nats,
		pulsar: pulsar,
		redis:  redis,
	}
}

// RunBootstrap runs all 4 bootstrap phases concurrently. A phase failure is
// recorded in BootstrapResult but does not cancel the other phases. Returns
// ErrBootstrapInProgress if a bootstrap is already running.
func (o *Orchestrator) RunBootstrap(ctx context.Context) (*BootstrapResult, error) {
	if !o.bootstrapInProgress.CompareAndSwap(false, true) {
		return nil, ErrBootstrapInProgress
	}
	defer o.bootstrapInProgress.Store(false)

	result := &BootstrapResult{
		Status: StatusInProgress,
		Phases: make(map[string]PhaseResult),
	}

	ctx, span := otel.Tracer("arc-cortex").Start(ctx, "cortex.bootstrap")
	defer span.End()

	// Use a plain errgroup (no context) so a phase failure does not cancel
	// the context passed to sibling phases.
	var g errgroup.Group

	g.Go(func() error {
		probe := o.pg.Probe(ctx)
		phase := probeToPhase("postgres", probe)
		result.Lock()
		result.Phases["postgres"] = phase
		result.Unlock()
		return nil
	})

	g.Go(func() error {
		err := o.nats.ProvisionStreams(ctx)
		phase := provisionToPhase("nats", err)
		result.Lock()
		result.Phases["nats"] = phase
		result.Unlock()
		return nil
	})

	g.Go(func() error {
		err := o.pulsar.Provision(ctx)
		phase := provisionToPhase("pulsar", err)
		result.Lock()
		result.Phases["pulsar"] = phase
		result.Unlock()
		return nil
	})

	g.Go(func() error {
		probe := o.redis.Probe(ctx)
		phase := probeToPhase("redis", probe)
		result.Lock()
		result.Phases["redis"] = phase
		result.Unlock()
		return nil
	})

	// g.Wait() never returns an error because all goroutines return nil.
	_ = g.Wait()

	// Determine overall status.
	result.Status = StatusOK
	for _, phase := range result.Phases {
		if phase.Status == StatusError {
			result.Status = StatusError
			break
		}
	}

	span.SetAttributes(attribute.String("bootstrap.status", result.Status))
	if result.Status == StatusError {
		span.SetStatus(codes.Error, "one or more bootstrap phases failed")
	} else {
		span.SetStatus(codes.Ok, "")
	}

	o.resultMu.Lock()
	o.lastResult = result
	o.resultMu.Unlock()

	return result, nil
}

// RunDeepHealth probes all 4 clients concurrently and returns a map of
// dependency name to ProbeResult.
func (o *Orchestrator) RunDeepHealth(ctx context.Context) map[string]ProbeResult {
	results := make(map[string]ProbeResult, 4)
	var mu sync.Mutex
	var g errgroup.Group

	g.Go(func() error {
		probe := o.pg.Probe(ctx)
		mu.Lock()
		results["postgres"] = probe
		mu.Unlock()
		return nil
	})

	g.Go(func() error {
		probe := o.nats.Probe(ctx)
		mu.Lock()
		results["nats"] = probe
		mu.Unlock()
		return nil
	})

	g.Go(func() error {
		probe := o.pulsar.Probe(ctx)
		mu.Lock()
		results["pulsar"] = probe
		mu.Unlock()
		return nil
	})

	g.Go(func() error {
		probe := o.redis.Probe(ctx)
		mu.Lock()
		results["redis"] = probe
		mu.Unlock()
		return nil
	})

	_ = g.Wait()
	return results
}

// IsBootstrapInProgress returns true while a bootstrap run is active.
func (o *Orchestrator) IsBootstrapInProgress() bool {
	return o.bootstrapInProgress.Load()
}

// IsReady returns true if the last bootstrap completed with StatusOK.
func (o *Orchestrator) IsReady() bool {
	o.resultMu.RLock()
	defer o.resultMu.RUnlock()
	return o.lastResult != nil && o.lastResult.Status == StatusOK
}

// probeToPhase converts a ProbeResult to a PhaseResult.
func probeToPhase(name string, p ProbeResult) PhaseResult {
	if p.OK {
		return PhaseResult{Name: name, Status: StatusOK}
	}
	return PhaseResult{Name: name, Status: StatusError, Error: p.Error}
}

// provisionToPhase converts a provision error to a PhaseResult.
func provisionToPhase(name string, err error) PhaseResult {
	if err == nil {
		return PhaseResult{Name: name, Status: StatusOK}
	}
	return PhaseResult{Name: name, Status: StatusError, Error: err.Error()}
}
