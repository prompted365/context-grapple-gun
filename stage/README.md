# stage/

Prepared but inert artifacts for CGG governed reasoning.

Artifacts here are **not runtime-active by default**.
They are referenceable, promotable, and inspectable.

## Lifecycle

| State | Meaning | Behavior |
|-------|---------|----------|
| **staged** | Inert. Reference-only. | No tics, signals, warrants, or cadence events. |
| **armed** | Selected for a specific run. | Generator copies/links into a show surface. |
| **live** | Promoted into runtime or explicitly loaded. | Normal cadence participation. |

## Rule

> Nothing in `stage/` executes by presence.
> Everything in `stage/` executes by reference.

## Directory Structure

```
stage/
  specs/              # Show specifications (YAML). Versioned.
  templates/          # Reusable arena/demo patterns. Versioned.
    arenas/           # Governed reasoning primitives
  shows/              # Generated per-show projections. IGNORED by git+cadence.
  examples/           # Reference artifacts (committed, not live).
```

## Generation

Show surfaces are **generated from runtime truth**, not hand-maintained.

```
python3 scripts/generate-stage.py --spec specs/my-show.yaml
```

This produces `shows/<show-id>/` from canonical sources scoped to that show.

## Invariants

- **Runtime is authoritative.** Stage is a projection, not a source of truth.
- **Spec is versioned.** Generated output is disposable.
- **Stage does not pollute cadence.** `.stage.ticignore` keeps the manifold clean.
- **Generated shows mirror runtime.** Regenerate to stay current.
