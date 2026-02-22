package orchestrator

import (
	"context"
	"errors"
	"log/slog"
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

// PGProber is satisfied by *clients.PostgresClient.
type PGProber interface {
	Probe(ctx context.Context) ProbeResult
}

// NATSProvisioner is satisfied by *clients.NATSClient.
type NATSProvisioner interface {
	ProvisionStreams(ctx context.Context) error
	Probe(ctx context.Context) ProbeResult
}

// PulsarProvisioner is satisfied by *clients.PulsarClient.
type PulsarProvisioner interface {
	Provision(ctx context.Context) error
	Probe(ctx context.Context) ProbeResult
}

// RedisProber is satisfied by *clients.RedisClient.
type RedisProber interface {
	Probe(ctx context.Context) ProbeResult
}

// Orchestrator runs bootstrap phases and health probes.
type Orchestrator struct {
	pg     PGProber
	nats   NATSProvisioner
	pulsar PulsarProvisioner
	redis  RedisProber

	bootstrapInProgress atomic.Bool
	lastResult          *BootstrapResult
	resultMu            sync.RWMutex
}

// New constructs an Orchestrator with the given clients. The concrete client
// types satisfy the interfaces defined in this package.
func New(pg PGProber, nats NATSProvisioner, pulsar PulsarProvisioner, redis RedisProber) *Orchestrator {
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

	slog.InfoContext(ctx, "bootstrap started")

	// Use a plain errgroup (no context) so a phase failure does not cancel
	// the context passed to sibling phases.
	var g errgroup.Group

	g.Go(func() error {
		probe := o.pg.Probe(ctx)
		phase := probeToPhase("postgres", probe)
		logPhase(ctx, phase)
		result.Lock()
		result.Phases["postgres"] = phase
		result.Unlock()
		return nil
	})

	g.Go(func() error {
		err := o.nats.ProvisionStreams(ctx)
		phase := provisionToPhase("nats", err)
		logPhase(ctx, phase)
		result.Lock()
		result.Phases["nats"] = phase
		result.Unlock()
		return nil
	})

	g.Go(func() error {
		err := o.pulsar.Provision(ctx)
		phase := provisionToPhase("pulsar", err)
		logPhase(ctx, phase)
		result.Lock()
		result.Phases["pulsar"] = phase
		result.Unlock()
		return nil
	})

	g.Go(func() error {
		probe := o.redis.Probe(ctx)
		phase := probeToPhase("redis", probe)
		logPhase(ctx, phase)
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
		slog.WarnContext(ctx, "bootstrap completed with errors", "status", result.Status)
	} else {
		span.SetStatus(codes.Ok, "")
		slog.InfoContext(ctx, "bootstrap completed", "status", result.Status)
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

// logPhase emits a trace-correlated log for a bootstrap phase result.
// Errors log at WARN so they are visible without being fatal.
func logPhase(ctx context.Context, p PhaseResult) {
	if p.Status == StatusOK {
		slog.InfoContext(ctx, "bootstrap phase ok", "phase", p.Name)
		return
	}
	slog.WarnContext(ctx, "bootstrap phase failed", "phase", p.Name, "error", p.Error)
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
