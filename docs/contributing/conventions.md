# Conventions

Coding, git, container, observability, and naming conventions for the A.R.C. Platform monorepo.

## Go (CLI, Cortex, SDK)

- Follow [Effective Go](https://go.dev/doc/effective_go) and enforce with `golangci-lint`.
- Dependency injection via functional options — no global mutable state. Example:

  ```go
  type Service struct { ... }
  type Option func(*Service)
  func WithTimeout(d time.Duration) Option { return func(s *Service) { s.timeout = d } }
  func New(opts ...Option) *Service { ... }
  ```

- Table-driven tests with `t.Parallel()` at the top of every sub-test:

  ```go
  func TestFoo(t *testing.T) {
      t.Parallel()
      cases := []struct{ name, input, want string }{ ... }
      for _, tc := range cases {
          tc := tc
          t.Run(tc.name, func(t *testing.T) {
              t.Parallel()
              // ...
          })
      }
  }
  ```

- Use `lipgloss.Width()` instead of `len()` for measuring terminal string widths — ANSI escape
  codes inflate `len()` counts.
- File paths follow XDG Base Directory spec — never hardcode `~/.arc`; use
  `os.UserConfigDir()` / `os.UserCacheDir()`.
- Errors use the platform `ArcError` type and propagate through `ErrorBoundary` for themed
  rendering. Never swallow errors with `_`.

## Python (Reasoner, Voice, SDK)

- Lint with `ruff check src/` and type-check with `mypy src/`. Both must pass before a PR is
  mergeable.
- Use pytest with fixtures for all test setup — avoid module-level state and `setUp`/`tearDown`
  patterns. Mark async tests with `asyncio_mode = "auto"` in `pyproject.toml` (no explicit
  `@pytest.mark.asyncio` needed).
- Validate all external data at the boundary using Pydantic models. Never pass raw `dict` objects
  between internal layers.
- Structured logging via OTEL — use `logging.getLogger(__name__)` with the OTEL log handler
  configured at startup. Never use `print()` for diagnostic output in production paths.
- Keep `src/` as a proper package (`__init__.py`) so imports are absolute:
  `from src.models import Foo`, not `from models import Foo`.

## Git

- No AI co-author lines — never append `Co-Authored-By:` or any AI attribution to commits.
  Commit messages describe what changed and why, not who (human or AI) wrote the change.
- Branch names are kebab-case and prefixed with the issue or spec number:
  `016-voice-system`, `017-pre-release`, `fix-1234-healthcheck-timeout`.
- Commit messages use the conventional commits format:
  `feat(voice): add TTS endpoint`, `fix(reasoner): handle empty context window`,
  `chore(ci): remove stale 016-voice-system branch from voice-images.yml`.
- Commits that only touch `docs/` use the `docs(...)` prefix; commits that only touch CI use
  `ci(...)`.

## Docker

- All containers run as a non-root user. Add `USER nonroot:nonroot` (distroless) or create a
  dedicated user in the Dockerfile and switch with `USER appuser`.
- Use multi-stage builds to keep runtime images free of build tools. The build stage installs
  compilers, the runtime stage copies only the compiled artifact.
- Base images:
  - Go services: `gcr.io/distroless/static-debian12` (runtime)
  - Python services: `python:3.12-slim` (runtime)
  - Never use `:latest` tags for base images in production Dockerfiles — pin to a digest or a minor
    version tag.
- Expose only the port the service actually binds. Document the port in `service.yaml`.

## OTEL

- Every HTTP handler gets a span. For FastAPI, use the `opentelemetry-instrumentation-fastapi`
  auto-instrumentation at startup. For Go, wrap each `http.Handler` with
  `otelhttp.NewHandler(...)`.
- Use structured logging throughout — key-value pairs, not interpolated strings:

  ```python
  logger.info("request received", extra={"user_id": user_id, "model": model})
  ```

  ```go
  slog.Info("request received", "user_id", userID, "model", model)
  ```

- Every new service must export traces to the OTEL collector (`arc-friday-collector`) at
  `OTEL_EXPORTER_OTLP_ENDPOINT` (default `http://arc-friday-collector:4317`). Configure via
  environment variable, never hardcoded.

## Naming

Service identity has three layers that must be kept distinct:

| Layer | Example | Used in |
|-------|---------|---------|
| Role directory | `services/reasoner/` | Monorepo path, Docker Compose service name |
| Codename | `Sherlock` | Docs, changelogs, human communication |
| Image name | `arc-reasoner` | GHCR, `docker pull`, `service.yaml` |

Never use a codename as a directory name or image name. Never use a role directory name as a human
label. The mapping is defined in `service.yaml` (`codename:` field) and in the CLAUDE.md service
table.

When referencing a service in code, configuration, or CI, use the role name (e.g.,
`arc-reasoner`, `services/reasoner`). Use the codename only in prose documentation and commit
messages where the human context is clear.
