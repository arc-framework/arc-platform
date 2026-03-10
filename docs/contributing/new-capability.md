# Adding a New Capability

A capability is a named, opt-in group of services that can be activated by a tier preset or by an
explicit entry in `arc.yaml`. Follow these six steps.

## Checklist

### 1. Define the capability name and its required services in `services/profiles.yaml`

Add an entry under the `capabilities:` key. The name must be lowercase and kebab-case.

```yaml
capabilities:
  my-capability:
    services: [my-service-a, my-service-b]
    description: "One-line description of what this capability provides"
    # requires: [other-capability]   # optional: list capabilities that must also be active
```

Use `requires` when your capability depends on another (e.g., `voice` requires `reasoner` because
the voice agent calls the LLM bridge).

### 2. Add the capability's services to `services/profiles.yaml`

Each service listed under `services:` must either already exist in the monorepo or be created as
part of this change. For new services, follow [Adding a New Service](./new-service.md) before
returning to this step.

Verify that all referenced services have a `services/<name>/service.yaml` and a `Dockerfile`.

### 3. Add the capability to the appropriate tier preset(s) in `profiles.yaml`

If the capability should be active for a standard tier, add it to the `capabilities:` list for that
tier. The standard upgrade path is `think → reason → ultra-instinct`.

```yaml
reason:
  description: 'Core + reasoning engine — standard development stack'
  capabilities:
    - reasoner
    - my-capability    # add here if it belongs in reason and above
```

If it is only relevant for `ultra-instinct`, the wildcard `capabilities: '*'` already covers it —
no change to tier presets is needed.

### 4. Test locally

Start the capability in isolation to verify the services come up and the health checks pass:

```bash
# Start a specific tier that includes your capability
make dev PROFILE=reason

# Or start only the capability's services directly (if you know the compose service names)
make dev-health
```

Check that all new services appear healthy in `make dev-health` output before proceeding.

### 5. Write docs page(s) for the new services and update the sidebar

For each new service the capability introduces, create a docs page under `docs/services/` (see step
6 of [Adding a New Service](./new-service.md)). Then add all new pages to the Services sidebar in
`docs/.vitepress/config.ts`.

If the capability itself warrants a concept page (e.g., explaining when to use it and what it
costs), add a page under `docs/guide/` and link it from the sidebar.

### 6. Write an ARD if the capability introduces new architectural decisions

If activating this capability introduces a new dependency type, a new communication pattern, or a
constraint that future contributors need to know about, write an Architecture Decision Record in
`docs/ard/`. Name it `CAPABILITY-<NAME>.md` (all caps) and follow the existing ARD format.

Update the `ardSidebar()` function in `docs/.vitepress/config.ts` to include the new file, so it
appears in the Architecture section of the docs site.
