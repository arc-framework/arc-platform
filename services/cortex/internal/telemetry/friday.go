package telemetry

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// Provider holds the OTEL trace and metric providers and their shutdown func.
type Provider struct {
	shutdown func(context.Context) error
}

// InitProvider initialises the OTEL TracerProvider and MeterProvider targeting
// arc-friday-collector at the given endpoint. Dial is non-blocking — an
// unreachable collector does not prevent startup.
func InitProvider(ctx context.Context, endpoint, serviceName string, useInsecure bool) (*Provider, error) {
	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceName(serviceName),
			semconv.ServiceVersion("0.1.0"),
			semconv.ServiceNamespace("arc"),
		),
		resource.WithHost(),
		resource.WithProcess(),
	)
	if err != nil {
		return nil, fmt.Errorf("building OTEL resource: %w", err)
	}

	connOpts := []grpc.DialOption{}
	if useInsecure {
		connOpts = append(connOpts, grpc.WithTransportCredentials(insecure.NewCredentials()))
	}

	// Shared gRPC connection for both exporters — reduces OS resource use.
	conn, err := grpc.NewClient(endpoint, connOpts...)
	if err != nil {
		return nil, fmt.Errorf("creating gRPC client for OTEL: %w", err)
	}

	// ── Trace exporter ──────────────────────────────────────────────────────
	traceExporter, err := otlptracegrpc.New(ctx, otlptracegrpc.WithGRPCConn(conn))
	if err != nil {
		conn.Close() //nolint:errcheck
		return nil, fmt.Errorf("creating trace exporter: %w", err)
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(traceExporter),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.TraceContext{})

	// ── Metric exporter ─────────────────────────────────────────────────────
	metricExporter, err := otlpmetricgrpc.New(ctx, otlpmetricgrpc.WithGRPCConn(conn))
	if err != nil {
		tp.Shutdown(ctx) //nolint:errcheck
		conn.Close()     //nolint:errcheck
		return nil, fmt.Errorf("creating metric exporter: %w", err)
	}

	mp := sdkmetric.NewMeterProvider(
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(metricExporter,
			sdkmetric.WithInterval(10*time.Second),
		)),
		sdkmetric.WithResource(res),
	)
	otel.SetMeterProvider(mp)

	// Downgrade SDK export errors (e.g. collector temporarily unreachable) from INFO
	// to WARN so they don't flood logs during collector restarts. The gRPC client
	// reconnects automatically — no action is needed on export failure.
	otel.SetErrorHandler(otel.ErrorHandlerFunc(func(err error) {
		slog.Warn("otel export error (will retry)", "err", err)
	}))

	shutdown := func(ctx context.Context) error {
		// Export failures (e.g. collector unreachable) are intentionally swallowed —
		// OTEL must not impact service availability. Only conn.Close is propagated
		// since it indicates an OS resource leak.
		mp.Shutdown(ctx) //nolint:errcheck
		tp.Shutdown(ctx) //nolint:errcheck
		return conn.Close()
	}

	return &Provider{shutdown: shutdown}, nil
}

// Shutdown flushes and closes all OTEL exporters. ctx should have a deadline.
func (p *Provider) Shutdown(ctx context.Context) error {
	return p.shutdown(ctx)
}
