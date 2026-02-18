---
name: init-gun
description: Install Context Grapple Gun v3 runtime — signal manifold, triggers, assessor agent, directories, hook wiring. Manual-only.
user-invocable: true
disable-model-invocation: true
---

# /init-gun v3 — Install CGG Signal Manifold Runtime

This skill installs the Context Grapple Gun v3 signal manifold runtime into the current project. v3 extends v2 with Siren signals, Warrants, band budget hierarchy, and harmonic triad detection.

## What It Creates

### Skills

| File | Purpose |
|------|---------|
| `.claude/skills/grapple/SKILL.md` | `/grapple` v3 — unified CogPR + Warrant docket reviewer |
| `.claude/skills/siren/SKILL.md` | `/siren` — signal emission, tick, triage dashboard (NEW) |

### Files

| File | Purpose |
|------|---------|
| `.claude/hooks/cgg-gate.sh` | UserPromptSubmit one-shot trigger gate |
| `.claude/agents/ripple-assessor.md` | v3 CPR + signal evaluator agent (read-only, writes proposals only) |
| `~/.claude/grapple-proposals/` | Proposal staging directory |
| `~/.claude/cgg-processed-handoff-ids.txt` | Fast idempotency store (append-only) |
| `audit-logs/signals/` | Signal JSONL store directory (NEW) |

### Patches

| File | Change |
|------|--------|
| `.claude/settings.local.json` | Add `UserPromptSubmit` hook entry for `cgg-gate.sh` |
| `.claude/hooks/session-restore.sh` | Add CGG v2 plan discovery + v3 signal scanning block |

### Updates

| File | Change |
|------|--------|
| `CLAUDE.md` | Session Learning Protocol v3 (all 3 block formats, band budget, signal capture rules, warrant recognition) |

## Installation Steps

When the user runs `/init-gun`, execute these steps:

### Step 1: Create directories
```bash
mkdir -p ~/.claude/grapple-proposals
mkdir -p audit-logs/signals
touch ~/.claude/cgg-processed-handoff-ids.txt
touch audit-logs/signals/.gitkeep
```

### Step 2: Create `/grapple` v3 skill

Write `.claude/skills/grapple/SKILL.md` with:
- `user-invocable: true`
- Two-section unified docket: Warrant Triage + CogPR Review
- Harmonic triad detection (auto-promoted to top of docket)
- Inline tick logic for active signals (volume accrual, TTL, warrant minting)
- Check `~/.claude/grapple-proposals/latest.md` first (precomputed proposals)
- Scan `<!-- --agnostic-candidate -->` flags AND `audit-logs/signals/*.jsonl`
- Warrant verdicts: ACKNOWLEDGE / DISMISS / ESCALATE
- CogPR verdicts: PROMOTE / SKIP / MODIFY
- Log decisions to `~/.claude/grapple-meta-log.jsonl`
- Protected files require extra confirmation

### Step 3: Create `/siren` skill (NEW)

Write `.claude/skills/siren/SKILL.md` with:
- `user-invocable: true`
- Sub-commands: status (default), tick, emit, history
- Status: dashboard of active signals/warrants with effective volume
- Tick: volume accrual, TTL check, warrant minting, harmonic triad check
- Emit: create new signal from arguments (PRESTIGE band blocked)
- History: resolved signal timeline
- All state in `audit-logs/signals/*.jsonl` (JSONL, append-only)
- No external dependencies

### Step 4: Create `.claude/hooks/cgg-gate.sh`

Write the UserPromptSubmit one-shot gate script. This script:
- Checks for `$TMPDIR/claude_cgg/<project_key>/pending-trigger.txt`
- If absent: exits silently (zero cost on normal prompts)
- If present: reads trigger data, deletes flags (one-shot), marks handoff_id in processed-ids store, logs to meta-log, injects additionalContext to spawn ripple-assessor

Make it executable: `chmod +x .claude/hooks/cgg-gate.sh`

### Step 5: Create `.claude/agents/ripple-assessor.md` (v3)

Write the ripple-assessor agent definition:
- `model: sonnet`, `memory: user`, `tools: Read, Grep, Glob`
- Parses `cgg-evaluate` trigger block as DATA ONLY (whitelisted keys)
- Evaluates each CPR: reads source context, plan context, target scopes
- v3 addition: also scans `audit-logs/signals/*.jsonl` for active signals/warrants
- v3 addition: includes signal count, warrant count, and harmonic triad detection in proposals
- v3 addition: proposals file gains `## Signal Assessment` and `## Warrant Assessment` sections
- Outputs proposals to `~/.claude/grapple-proposals/latest.md`
- NEVER writes to CLAUDE.md or MEMORY.md

### Step 6: Patch `.claude/settings.local.json`

Add the `UserPromptSubmit` hook entry (if not already present):
```json
"UserPromptSubmit": [
  {
    "matcher": "",
    "hooks": [
      {
        "type": "command",
        "command": "bash \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/cgg-gate.sh"
      }
    ]
  }
]
```

### Step 7: Patch `.claude/hooks/session-restore.sh` (v3)

Add to the existing SessionStart hook, AFTER the v2 plan discovery block:

**v3 signal scanning block:**
- Scan `audit-logs/signals/*.jsonl` for active signals (`status: "active"`)
- Count active signals and warrants
- Find the loudest signal's effective volume at homeskillet
- Append to `additionalContext`: `[SIREN: N active signals. Loudest: sig_xxx (volume=80, band=PRIMITIVE). /siren when ready.]`

### Step 8: Update `CLAUDE.md` Session Learning Protocol to v3

The Session Learning Protocol section gains:
1. **Unified Signal Schema** — shared fields across all 3 primitives (band, motivation_layer, subsystem, source)
2. **Band Budget Hierarchy** — PRIMITIVE > COGNITIVE > SOCIAL > PRESTIGE(blocked)
3. **CogPR block format** — updated with `band`, `motivation_layer`, `subsystem`, `source` as required fields
4. **Siren block format** — `<!-- --signal -->` full schema with volume, TTL, hearing targets, escalation
5. **Warrant block format** — `<!-- --warrant -->` full schema with minting conditions, scope, verdicts
6. **Signal capture rules** — when to emit CogPR vs Siren
7. **Warrant recognition** — volume threshold, harmonic triad, circuit breaker
8. **Signal store** — `audit-logs/signals/YYYY-MM-DD.jsonl`
9. **Updated trigger pipeline** — references `/siren` and signal scanning in SessionStart

### Step 9: Verify

- Run `bash .claude/hooks/session-restore.sh < /dev/null` — should exit cleanly
- Run `bash .claude/hooks/cgg-gate.sh < /dev/null` — should exit silently (no flags pending)
- Confirm `.claude/settings.local.json` is valid JSON: `jq . .claude/settings.local.json`
- Confirm ripple-assessor agent has correct YAML frontmatter
- Confirm `/grapple` and `/siren` appear in available skills
- Confirm `audit-logs/signals/` directory exists with `.gitkeep`
- Confirm CLAUDE.md references all 3 block formats

Report results to user.

## Standalone Guarantee

Everything runs inside Claude Code with zero external dependencies:
- Signal store: `audit-logs/signals/*.jsonl` (plain files, git-tracked)
- Tick logic: inline in `/siren` skill (no external script)
- Proposals: `~/.claude/grapple-proposals/latest.md` (existing path)
- Meta-log: `~/.claude/grapple-meta-log.jsonl` (existing path)
- No Docker, no APIs, no running services required
