---
name: init-gun
description: Install Context Grapple Gun v2 runtime — triggers, assessor agent, directories, hook wiring. Manual-only.
user-invocable: true
disable-model-invocation: true
---

# /init-gun — Install CGG v2 Runtime

This skill installs the Context Grapple Gun v2 trigger payload architecture into the current project.

## Prerequisites

- Claude Code CLI
- `cogpr` package installed (or install after with `/init-cogpr`)

## What It Creates

### Files

| File | Purpose |
|------|---------|
| `.claude/hooks/cgg-gate.sh` | UserPromptSubmit one-shot trigger gate |
| `.claude/agents/ripple-assessor.md` | Fresh CPR evaluator agent (read-only, writes proposals only) |
| `~/.claude/grapple-proposals/` | Proposal staging directory |
| `~/.claude/cgg-processed-handoff-ids.txt` | Fast idempotency store (append-only) |

### Patches

| File | Change |
|------|--------|
| `.claude/settings.local.json` | Add `UserPromptSubmit` hook entry for `cgg-gate.sh` |
| `.claude/hooks/session-restore.sh` | Add project-scoped plan matching + trigger extraction + CPR queue injection |

### Updates

| File | Change |
|------|--------|
| `CLAUDE.md` | Session Learning Protocol v2 (capture-only + plan schema + trigger rules) |

## Installation Steps

When the user runs `/init-gun`, execute these steps:

### Step 1: Create directories
```bash
mkdir -p ~/.claude/grapple-proposals
touch ~/.claude/cgg-processed-handoff-ids.txt
```

### Step 2: Install hook and agent files

Copy from the CGG submodule (or vendor directory) into the project:
- `cgg-runtime/hooks/cgg-gate.sh` → `.claude/hooks/cgg-gate.sh` (chmod +x)
- `cgg-runtime/agents/ripple-assessor.md` → `.claude/agents/ripple-assessor.md`

If no submodule is available, create the files inline using the templates in this package.

### Step 3: Patch `.claude/settings.local.json`

Add the `UserPromptSubmit` hook entry (create the file if it doesn't exist):
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

### Step 4: Patch SessionStart hook

If `.claude/hooks/session-restore.sh` exists, merge the CGG v2 plan discovery logic from `cgg-runtime/hooks/session-restore-patch.sh`.

If no SessionStart hook exists, copy `session-restore-patch.sh` as `.claude/hooks/session-restore.sh` and add the SessionStart hook entry to settings.local.json.

### Step 5: Update `CLAUDE.md` Session Learning Protocol

Add/replace the Session Learning Protocol section with v2 rules:

1. **Capture only** — write local lessons + CPR flags during session; do NOT evaluate cross-scope promotions
2. **Citation-laden plan exit** — context-exit plans use structured headers: User Intent, Agent Interpretation, Interpretation Concerns, Working State, Lessons Discovered, Next Actions
3. **`cgg-handoff` header** — required on all context-exit plans
4. **`cgg-evaluate` trigger block** — required ONLY when pending CPR flags exist
5. **Protected scope rules** — global CLAUDE.md and `[GLOBAL_INVARIANT]` files never touched autonomously

### Step 6: Verify

```bash
bash .claude/hooks/session-restore.sh < /dev/null  # should exit clean
bash .claude/hooks/cgg-gate.sh < /dev/null          # should exit silent
jq . .claude/settings.local.json                     # should be valid JSON
```

Report results to user.
