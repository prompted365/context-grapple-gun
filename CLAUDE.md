# Context Grapple Gun — Domain CLAUDE.md

## Hook Format Requirement (Current)

The hook format has changed multiple times. The **current** format requires:

1. Each event contains an array of **matcher groups**
2. Each matcher group has an optional `matcher` (regex string) and a `hooks` array
3. `matcher` is a **regex string** matching tool names (e.g. `"Bash"`, `"Edit|Write"`)
4. For match-all: **omit `matcher` entirely**, or use `"*"`
5. `"matcher": {}` (object) is **invalid** in current versions

**Correct format (match-all — omit matcher):**
```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "path/to/hook.sh"
          }
        ]
      }
    ]
  }
}
```

**Correct format (filtered — regex string matcher):**
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "path/to/hook.sh"
          }
        ]
      }
    ]
  }
}
```

**Broken formats (do NOT use):**
- `{"type":"command","command":"..."}` directly in event array (pre-2.1.58 flat format)
- `{"matcher":{},"hooks":[...]}` with object matcher (pre-2.1.72 format)

Reference: [Hooks docs](https://code.claude.com/docs/en/hooks) | [Settings schema](https://json.schemastore.org/claude-code-settings.json)

**Impact**: INSTALL.md bootstrap prompt, academy guide, and init-governance SKILL.md all need updating. See `PLAN-hook-doc-update.md`.

### Hook types available

- `"type": "command"` — runs a shell command, receives JSON on stdin
- `"type": "http"` — POSTs JSON to a URL endpoint (added 2.1.63)

### CGG-relevant hook events (2.1.69+)

- `InstructionsLoaded` — fires when CLAUDE.md or `.claude/rules/*.md` loaded into context
- `TeammateIdle` / `TaskCompleted` — support `{"continue": false}` to stop teammates
- Hook events now include `agent_id` and `agent_type` fields

### Other capabilities

- `${CLAUDE_SKILL_DIR}` — skills can reference their own directory (2.1.69)
- `/reload-plugins` — activate plugin changes without restart (2.1.69)
- Shared project configs across worktrees (2.1.63)

<!-- promoted from CogPR-1 (tic 1), updated tic 2 after second format break. Source: ~/.claude/projects/-Users-breydentaylor-canonical/memory/MEMORY.md -->
