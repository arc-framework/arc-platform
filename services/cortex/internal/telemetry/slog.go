package telemetry

import (
	"context"
	"log/slog"

	"go.opentelemetry.io/otel/trace"
)

// TraceHandler wraps a slog.Handler and injects "trace_id" and "span_id"
// into every log record that carries an active span via its context.
// Use slog.InfoContext(ctx, …) / slog.WarnContext(ctx, …) etc. to get
// automatic trace correlation in SigNoz Logs.
type TraceHandler struct {
	slog.Handler
}

// NewTraceHandler wraps h with trace-context injection.
func NewTraceHandler(h slog.Handler) *TraceHandler {
	return &TraceHandler{Handler: h}
}

// Handle extracts the active OTEL span from ctx and adds trace_id / span_id
// before delegating to the wrapped handler.
func (t *TraceHandler) Handle(ctx context.Context, r slog.Record) error {
	span := trace.SpanFromContext(ctx)
	if sc := span.SpanContext(); sc.IsValid() {
		r.AddAttrs(
			slog.String("trace_id", sc.TraceID().String()),
			slog.String("span_id", sc.SpanID().String()),
		)
	}
	return t.Handler.Handle(ctx, r)
}

// WithAttrs satisfies slog.Handler; wraps the inner handler.
func (t *TraceHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	return &TraceHandler{Handler: t.Handler.WithAttrs(attrs)}
}

// WithGroup satisfies slog.Handler; wraps the inner handler.
func (t *TraceHandler) WithGroup(name string) slog.Handler {
	return &TraceHandler{Handler: t.Handler.WithGroup(name)}
}
