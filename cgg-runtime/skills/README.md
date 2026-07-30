# CGG Runtime Skills — v5 Surface

This directory contains canonical skill source. Repository presence does not automatically grant public plugin admission.

The v5 public plugin manifest exposes a curated set from `.claude-plugin/plugin.json`:

## Primary

| Skill | Authority |
|---|---|
| `cadence` | Epoch boundary, canonical tic, handoff seal |
| `review` | Human constitutional judgment over proposed learning and warrants |
| `siren` | Signal manifold visibility and operations |
| `statusline` | Bounded statusline installation |
| `governance-check` | Governance state inspection |
| `governance-mandate-cycle` | Mandate-cycle control surface |

## Compatibility wrappers

- `cadence-downbeat`
- `cadence-syncopate`
- `grapple`

These remain public for continuity while the primary command ownership above stays canonical.

## Present but not publicly admitted

Experimental, internal, deprecated, and curriculum surfaces may remain in the repository for source history, evaluation, or future work. They are not exposed merely because they have a `SKILL.md`.

Homeskillet Academy is currentness-held under issue #13. The legacy `/init-governance` skill is separately held under issue #14 because its direct-copy/settings-patch contract predates the v5 installer. Both remain intentionally excluded from the public manifest until reconciled.

Deprecated trees use `deprec_*` naming or carry explicit deprecation notes. The distribution validator rejects their accidental admission.

## Source / installed / loaded distinction

```text
this directory (canonical source)
  → npm payload or source checkout
  → mode-specific managed target
  → Claude Code plugin cache / loaded inventory
```

Behavioral truth is the loaded runtime. Canonical source remains intent until install, validation, and inventory verification complete.
