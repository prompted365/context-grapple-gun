---
name: init-cogpr
description: Install CogPR conventions — /grapple integration, proposal consumption, promotion workflow. Manual-only.
user-invocable: true
disable-model-invocation: true
---

# /init-cogpr — Install Cognitive Pull Request Conventions

This skill installs the CogPR (Cognitive Pull Request) conventions into the current project, enabling the full CPR lifecycle: flag → evaluate → propose → approve → promote.

## What It Creates/Updates

### Creates

| File | Purpose |
|------|---------|
| `.claude/skills/grapple/SKILL.md` | The `/grapple` skill — human-gated CPR merger/reviewer |

### Updates

| File | Change |
|------|--------|
| `CLAUDE.md` | Add CPR flag format reference + capture rules |

## Installation Steps

### Step 1: Install `/grapple` skill

Copy `cogpr/claude-code/skills/grapple/SKILL.md` to `.claude/skills/grapple/SKILL.md` in the project.

### Step 2: Add CPR conventions to CLAUDE.md

Add the following to the project's CLAUDE.md (in or near the Session Learning Protocol section):

#### Capture Rules

1. **Write lessons at your operational level** — nearest existing CLAUDE.md up the tree, or MEMORY.md as fallback
2. **Match existing format** — use the heading style and tone already in the target file
3. **Flag CPRs for broader lessons** — add the flag immediately after the lesson text

#### CPR Flag Format

```html
<!-- --agnostic-candidate
  lesson: "one-line lesson summary"
  source_date: "YYYY-MM-DD"
  recommended_scopes:
    - "path/to/broader/CLAUDE.md"
  rationale: "why this is broader than local"
  review_hints: "what to check when evaluating"
  status: "pending"
-->
```

Valid status values: `pending` | `promoted` | `rejected`. Only `/grapple` changes status (human gate).

#### Protected Files

Never touch autonomously:
- `~/.claude/CLAUDE.md` (global root)
- Any file tagged `[GLOBAL_INVARIANT]`
- Only `/grapple` with explicit user approval can write to these

### Step 3: Verify

- Confirm `/grapple` appears in available skills list
- Confirm CPR flag format is documented in CLAUDE.md

Report results to user.
