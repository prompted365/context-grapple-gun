# Package Shape

This rendered package is the active Frederick Grant runtime.

```text
frederick-grant-runtime/
├── SKILL.md
├── README.md
├── profile/
├── stages/
├── scripts/
├── reference/
├── templates/
├── tools/
└── evals/
```

`profile/` stores identity and negative contours. `stages/` stores the workflow. `scripts/` stores copy/paste prompt surfaces. `reference/` stores source boundaries and receipts. `templates/` stores structured artifacts. `tools/` stores methods, not retained outputs.

## Canonical install paths

- **Canonical authoring location**: `canonical_developer/context-grapple-gun/cgg-runtime/skills/frederick-grant-runtime/` (relative to federation root).
- **Runtime install location**: `~/.claude/skills/frederick-grant-runtime/` (synced via `runtime-sync.py sync`).

The skill follows the multi-file pattern. `runtime-sync.py` recurses skill subdirectories so all sub-files (`profile/`, `stages/`, `scripts/`, `reference/`, `templates/`, `tools/`, `evals/`, `README.md`) install alongside `SKILL.md`. Drift is reported per-file (surface name `skill:frederick-grant-runtime:<rel_path>`).

## Authoring vs runtime

Authoring material lives in the canonical location and may be edited directly. Runtime is downstream of authoring; do not edit `~/.claude/skills/frederick-grant-runtime/` directly — edit canonical and re-sync. The federation's `Conductor-Score-Runtime Parity` invariant applies: byte-identical post-sync is the proof that authoring and runtime agree.
