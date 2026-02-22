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

// TeeHandler fans out each log record to multiple slog.Handlers.
// Used to write logs to both stdout (JSONHandler) and the OTEL log pipeline.
type TeeHandler struct {
	handlers []slog.Handler
}

// NewTeeHandler returns a handler that forwards every record to all given handlers.
func NewTeeHandler(handlers ...slog.Handler) *TeeHandler {
	return &TeeHandler{handlers: handlers}
}

// Enabled returns true if any child handler is enabled for the given level.
func (t *TeeHandler) Enabled(ctx context.Context, level slog.Level) bool {
	for _, h := range t.handlers {
		if h.Enabled(ctx, level) {
			return true
		}
	}
	return false
}

// Handle delivers the record to every enabled child handler.
// Records are cloned before each delivery to prevent mutation races.
func (t *TeeHandler) Handle(ctx context.Context, r slog.Record) error {
	for _, h := range t.handlers {
		if h.Enabled(ctx, r.Level) {
			h.Handle(ctx, r.Clone()) //nolint:errcheck
		}
	}
	return nil
}

// WithAttrs returns a new TeeHandler with the attrs propagated to all children.
func (t *TeeHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	handlers := make([]slog.Handler, len(t.handlers))
	for i, h := range t.handlers {
		handlers[i] = h.WithAttrs(attrs)
	}
	return &TeeHandler{handlers: handlers}
}

// WithGroup returns a new TeeHandler with the group propagated to all children.
func (t *TeeHandler) WithGroup(name string) slog.Handler {
	handlers := make([]slog.Handler, len(t.handlers))
	for i, h := range t.handlers {
		handlers[i] = h.WithGroup(name)
	}
	return &TeeHandler{handlers: handlers}
}
