# Plan: CGG Documentation Update for Claude Code 2.1.58–2.1.71

**Posture**: ENG/DIRECT
**Scope**: canonical_developer/context-grapple-gun/
**Prepared**: 2026-03-08, tic 1 canonical session

---

## Context: What Changed (2.1.58 → 2.1.71)

### Release Map

| Version | Date | Significance |
|---------|------|-------------|
| 2.1.58 | Feb 25 | Remote Control expansion |
| 2.1.59 | Feb 26 | Auto-memory (`/memory`), `/copy` command, improved multi-agent memory release |
| 2.1.61 | Feb 26 | Windows config corruption fix |
| 2.1.62 | Feb 27 | Prompt suggestion cache fix |
| **2.1.63** | **Feb 28** | **HTTP hooks**, `/simplify`, `/batch`, shared project configs across worktrees, MCP opt-out env var, many memory leak fixes |
| 2.1.66 | Mar 4 | (empty changelog) |
| **2.1.68** | **Mar 4** | Opus 4.6 defaults to medium effort, "ultrathink" keyword, removed Opus 4/4.1 |
| **2.1.69** | **Mar 5** | **MASSIVE**: `InstructionsLoaded` hook event, `agent_id`/`agent_type` in hook events, `${CLAUDE_SKILL_DIR}` variable, `/reload-plugins`, worktree field in statusline hooks, security fixes, 50+ bug fixes |
| 2.1.70 | Mar 6+ | ToolSearch third-party gateway support, empty-reply fix |
| 2.1.71 | Mar 7+ | Latest stable |

Versions 2.1.60, 2.1.64, 2.1.65, 2.1.67 — no public GitHub releases (internal/hotfix builds).

### CGG-Relevant New Capabilities

1. **HTTP hooks** (2.1.63) — hooks can now POST JSON to a URL endpoint instead of running shell commands. Type: `"http"` with a URL target.
2. **`InstructionsLoaded` hook event** (2.1.69) — fires when CLAUDE.md or `.claude/rules/*.md` files are loaded into context. CGG could use this for governance loading validation.
3. **`agent_id` and `agent_type` in hook events** (2.1.69) — hooks now receive subagent identity. CGG hooks (gate, microscan) could use this for per-agent policy.
4. **`${CLAUDE_SKILL_DIR}` variable** (2.1.69) — skills can reference their own directory. CGG skills should use this instead of hardcoded paths.
5. **`/reload-plugins` command** (2.1.69) — activate plugin changes without restart. Relevant to CGG install flow.
6. **Worktree field in status line hooks** (2.1.69) — name, path, branch, original repo dir.
7. **`TeammateIdle` and `TaskCompleted` hooks** (2.1.69) — support `{"continue": false}` to stop teammates. Governance hook surface for team dispatch.
8. **Shared project configs across worktrees** (2.1.63) — CGG governance surfaces in `.claude/` are now shared.
9. **Security fix**: nested skill discovery no longer loads from gitignored dirs like `node_modules` (2.1.69).
10. **Plugin hooks fixes** (2.1.69) — Stop/SessionEnd hooks now fire after `/plugin` operations; duplicate command template collision fixed.

### Hook Format History (Critical)

The hook format has evolved through **three** breaking changes:

**Era 1 — Pre-2.0.37 (legacy)**: Flat command objects directly in event arrays
```json
{"hooks":{"SessionStart":[{"type":"command","command":"..."}]}}
```

**Era 2 — 2.0.46 through 2.1.58**: Matcher-wrapped with `matcher` as object
```json
{"hooks":{"SessionStart":[{"matcher":{},"hooks":[{"type":"command","command":"..."}]}]}}
```

**Era 3 — Current (post-2.1.71)**: Matcher is a **regex string**, not an object. Omit for match-all.
```json
{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"..."}]}]}}
```
With filtering:
```json
{"hooks":{"PostToolUse":[{"matcher":"Edit|Write","hooks":[{"type":"command","command":"..."}]}]}}
```

**2.1.63+**: HTTP hook type added alongside command type
```json
{"matcher":"Edit|Write","hooks":[{"type":"http","url":"https://..."}]}
```

Reference: [Hooks docs](https://code.claude.com/docs/en/hooks) | [Settings schema](https://json.schemastore.org/claude-code-settings.json)

---

## Problem: Doc Audit Findings

### Files using OLD (broken) hook format:

| File | Lines | Impact |
|------|-------|--------|
| `INSTALL.md` | 267–319 | **Bootstrap prompt** — any manual install produces dead hooks |
| `INSTALL.md` | 593–596 | Manual install script section |
| `academy/chapters/guides/installing-cgg.md` | 148–162 | **Educational guide** — teaches wrong format |
| `cgg-runtime/skills/init-governance/SKILL.md` | 301–338 | **User-facing skill** — produces wrong format |

### Files correctly documenting new format:

| File | Lines | Status |
|------|-------|--------|
| `CLAUDE.md` (domain root) | 3–42 | Correct, but has stale "still uses old format" note |

### No circular documentation references detected.

The `.claude-plugin/plugin.json` manifest uses a separate plugin format (not settings.json format) — not affected.

---

## Plan: Execution Steps

### Step 1: Update INSTALL.md hook format examples

**DONE** (tic 2) — Both user-scope and project-scope examples updated to Era 3. Manual install comment block also updated.

**File**: `INSTALL.md`
**Lines**: 267–319

Replace both user-scope and project-scope examples with matcher-wrapped format:

**User scope (lines 269–292):**
```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/session-restore-patch.sh"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/cgg-gate.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/posttool-microscan.sh"
          }
        ]
      }
    ]
  }
}
```

**Project scope (lines 296–319):** Same structure with `.claude/hooks/...` paths.

**Also update**: Lines 593–596 comment block to reference the matcher-wrapped format.

### Step 2: Update academy installing guide

**DONE** (tic 2) — Step 9 example updated to Era 3 matcher-group format.

**File**: `academy/chapters/guides/installing-cgg.md`
**Lines**: 148–162

Replace Step 9 settings.local.json example with matcher-wrapped format.

### Step 3: Update init-governance skill

**DONE** (tic 2) — Both user and project scope examples updated to Era 3.

**File**: `cgg-runtime/skills/init-governance/SKILL.md`
**Lines**: 301–338

Replace both user and project scope examples with matcher-wrapped format.

### Step 4: Update domain CLAUDE.md

**DONE** (tic 2) — CLAUDE.md already updated with:
- Correct current format (regex string matcher, omit for match-all)
- Both broken formats documented
- HTTP hook type
- CGG-relevant hook events (InstructionsLoaded, TeammateIdle, TaskCompleted)
- New capabilities (${CLAUDE_SKILL_DIR}, /reload-plugins, shared worktree configs)

### Step 5: ~~Add new capabilities section to domain CLAUDE.md~~

**DONE** (tic 2) — merged into Step 4 update.

### Step 6: Validate

**DONE** (tic 2) — Grep validated all `"type": "command"` occurrences are inside `"hooks":[]` wrappers. No remaining flat-format hooks in user-facing docs. `"matcher":{}` only appears in CLAUDE.md/PLAN as documentation of the broken format.

1. Run `jq` syntax check on all JSON examples in modified files
2. Cross-check that every hook format example across CGG docs is matcher-wrapped
3. Verify no other files reference the old format (grep for `"type": "command"` without sibling `"matcher"`)

### Step 7: Log

**DONE** (tic 2) — Entry appended to `~/.claude/grapple-meta-log.jsonl`.

Append update entry to `~/.claude/grapple-meta-log.jsonl` documenting the doc update.

---

## Out of Scope (deferred)

- Updating INSTALL.md to document HTTP hooks as an install option (new feature, not a fix)
- Adding `InstructionsLoaded` hook to CGG pipeline (requires design)
- Updating CGG hooks to use `agent_id`/`agent_type` (requires design)
- Updating skills to use `${CLAUDE_SKILL_DIR}` (separate PR)

---

## Dependencies

- Must be on Claude Code >= 2.1.71 (post-restart) to validate
- No cross-lane dependencies — this is purely within `canonical_developer/context-grapple-gun/`
- This plan cleans up the downstream debt from CogPR-1 (promoted this session)
