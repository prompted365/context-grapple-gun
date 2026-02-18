# CGG Runtime — Trigger Pipeline

Automated between-session lesson evaluation for Claude Code.

## Components

| File | Purpose |
|------|---------|
| `hooks/cgg-gate.sh` | UserPromptSubmit one-shot gate |
| `hooks/session-restore-patch.sh` | SessionStart plan discovery + trigger extraction |
| `agents/ripple-assessor.md` | Fresh CPR evaluator (sonnet, read-only) |
| `skills/init-gun/SKILL.md` | Installer skill |
| `skills/grapple/SKILL.md` | CPR merger/reviewer (overlap with cogpr package) |

## Requires

- Claude Code CLI with hooks support
- `cogpr` package (or at minimum the `/grapple` skill to consume proposals)

## How It Works

1. Session ends → PreCompact writes plan file with `cgg-evaluate` trigger block
2. Next session starts → SessionStart hook discovers plan, extracts trigger to flag files
3. First prompt → UserPromptSubmit gate fires once, spawns ripple-assessor in background
4. Assessor reads plan, evaluates CPRs, writes proposals to `~/.claude/grapple-proposals/latest.md`
5. User runs `/grapple` → reviews proposals, approves/rejects, promotions applied

## Safety

- One-shot: trigger fires exactly once per handoff_id
- Idempotent: restart won't re-evaluate (handoff_id tracked in `~/.claude/cgg-processed-handoff-ids.txt`)
- Project-scoped: plan file `project_dir` must match current project
- Read-only assessor: ripple-assessor can only write to proposals file
- Human gate: all promotions require explicit approval via `/grapple`
