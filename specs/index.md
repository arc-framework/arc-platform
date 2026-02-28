# A.R.C. Platform — Specs

This is the searchable spec documentation site for the A.R.C. Platform. It publishes all feature
specifications, implementation plans, and task breakdowns from the `specs/` directory as a
statically rendered site with full-text search and mermaid diagram support.

## Spec Index

| Feature | Name | Status | Link |
|---------|------|--------|------|
| 001 | OTEL Setup | Implemented | [spec](001-otel-setup/spec.md) |
| 002 | Cortex Setup | Implemented | [spec](002-cortex-setup/spec.md) |
| 003 | Messaging Setup | Implemented | [spec](003-messaging-setup/spec.md) |
| 004 | Dev Setup | Implemented | [spec](004-dev-setup/spec.md) |
| 005 | Data Layer | Implemented | [spec](005-data-layer/spec.md) |
| 006 | Platform Control | Implemented | [spec](006-platform-control/spec.md) |
| 007 | Voice Stack | Implemented | [spec](007-voice-stack/spec.md) |
| 008 | Specs Site | Implemented | [spec](008-specs-site/spec.md) |

## Local Development

```bash
cd docs/specs
npm install       # first time only
npm run dev
```

The dev server starts at http://localhost:5173/arc-platform/specs-site/ with live reload enabled.
