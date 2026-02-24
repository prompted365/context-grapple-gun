# CGG Runtime v3 — Signal Manifold Trigger Pipeline

Automated between-session lesson evaluation and signal management for Claude Code.

## What's New in v3

- **`/siren` skill**: Signal emission, tick advancement, warrant minting, triage dashboard
- **Signal store**: `audit-logs/signals/*.jsonl` — append-only JSONL for signals and warrants
- **Harmonic triad detection**: PRIMITIVE BEACON + COGNITIVE LESSON + TENSION = auto-warrant
- **Unified docket**: `/grapple` now reviews both CogPR promotions AND warrant triage
- **Signal scanning hook**: SessionStart scans signal store, reports active signals in context
- **v3 ripple-assessor**: Evaluates CPRs + scans signals + detects triads

## Components

| File | Purpose |
|------|---------|
| `hooks/cgg-gate.sh` | UserPromptSubmit one-shot gate |
| `hooks/session-restore-patch.sh` | SessionStart plan discovery + signal scanning (v3) |
| `agents/ripple-assessor.md` | Fresh CPR + signal evaluator (sonnet, read-only) |
| `skills/init-gun/SKILL.md` | v3 master installer |
| `skills/init-cogpr/SKILL.md` | v3 convention installer (overlap with cogpr package) |
| `skills/grapple/SKILL.md` | v3 unified docket (overlap with cogpr package) |
| `skills/siren/SKILL.md` | Signal emission + triage dashboard (NEW) |
| `skills/grapple-cog-cycle-session/SKILL.md` | Standardized session shutdown & handoff sequence (NEW) |

## Requires

- Claude Code CLI with hooks support
- `cogpr` package (or at minimum the `/grapple` skill to consume proposals)

## How It Works

1. Session ends -> PreCompact writes plan file with `cgg-evaluate` trigger block
2. Next session starts -> SessionStart hook discovers plan + scans `audit-logs/signals/` for active signals
3. First prompt -> UserPromptSubmit gate fires once, spawns ripple-assessor in background
4. Assessor reads plan, evaluates CPRs + signals, writes proposals to `~/.claude/grapple-proposals/latest.md`
5. User runs `/grapple` -> reviews unified docket (Warrants + CPRs), approves/rejects
6. User runs `/siren` -> operational dashboard for signal management between `/grapple` reviews

## Signal Lifecycle

```
Emit signal (/siren emit)
  -> volume accrues per tick (/siren tick)
  -> effective_volume computed per hearing target (distance model)
  -> volume crosses warrant_threshold -> warrant minted automatically
  -> /grapple presents warrant in triage docket
  -> human ACKNOWLEDGEs / DISMISSes / ESCALATEs
```

## Standalone Guarantee

Everything runs inside Claude Code with zero external dependencies:
- Signal store: `audit-logs/signals/*.jsonl` (plain files, git-tracked)
- Tick logic: inline in `/siren` skill
- Proposals: `~/.claude/grapple-proposals/latest.md`
- Meta-log: `~/.claude/grapple-meta-log.jsonl`
- No Docker, no APIs, no running services required

## Safety

- One-shot: trigger fires exactly once per handoff_id
- Idempotent: restart won't re-evaluate (handoff_id tracked)
- Project-scoped: plan file `project_dir` must match current project
- Read-only assessor: ripple-assessor can only write to proposals file
- Human gate: all promotions and warrant verdicts require explicit approval via `/grapple`
- PRESTIGE band blocked: governance filter prevents emission
- Append-only JSONL: signal history is never overwritten
