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

## Plugin Hook Registration

Plugins must register hooks in `hooks/hooks.json` at the plugin root — listing hooks in `plugin.json` components alone is insufficient. Use `${CLAUDE_PLUGIN_ROOT}` to reference scripts within the plugin directory.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/posttool-microscan.sh"
          }
        ]
      }
    ]
  }
}
```

Reference: [Plugin docs](https://code.claude.com/docs/en/plugins)

<!-- promoted from CogPR-4 (tic 3→5). Source: code.claude.com/docs/en/plugins. Validated by hooks/hooks.json creation. -->

## Agent Tool (formerly Task)

The `Task` tool was renamed to `Agent` in Claude Code 2.1.63. All CGG agent frontmatter must use `Agent`, not `Task`.

- **Frontmatter**: `tools: Read, Grep, Glob, Agent, Bash`
- **Spawn restriction**: `Agent(subagent-name)` restricts which subagents can be spawned
- The `Task` alias may still work but should not be relied upon

<!-- promoted from CogPR-5 (tic 3→5). Source: code.claude.com/docs/en/sub-agents. Applied to mogul.md at f26f21b. -->

## JSONL Atomic Writes (PRIMITIVE)

All JSONL append-only files (`audit-logs/**/*.jsonl`) must use atomic append to prevent corruption from concurrent writers (hooks, session-start, Mogul cycles).

**Required pattern**: write to temp file, then atomic rename/append — never direct `>>` append from concurrent processes.

- Scripts: use `scripts/lib/atomic-append.sh`
- Python: use `scripts/lib/atomic_append.py`
- All 10 JSONL-writing hooks/scripts have been patched to use these libraries

**Failure mode**: concurrent session-start hooks interleaving JSON lines, producing invalid JSONL. Observed at tic 1 and tic 4 on `mandates/history/*.jsonl`.

<!-- promoted from CogPR-8 (tic 4→5). Band: PRIMITIVE. Source: audit-logs/mogul/mandates/history/2026-03-08.jsonl corruption incident. -->

## Review Execution Delegation

After `/review` docket is approved, dispatch execution to a `review-execute` subordinate agent — never execute promotions inline in the interactive path.

**Flow:**
1. Present the docket (judgment) → human approves
2. Spawn `review-execute` agent (background, `subagent_type: general-purpose`) with the full verdict table
3. Report completion in one line when notified

**Dispatch payload:** approved verdict table + file targets + review_tic number. The agent reads MEMORY.md for lesson text, writes promoted sections, updates `queue.jsonl` and MEMORY.md metadata. `queue.jsonl` update is the completion gate.

**Fallback:** If `review-execute.md` agent spec is unavailable, spawn a generic background agent with the same instructions.

<!-- promoted from CogPR-9 (tic 5→6). Source: session observation — review-execute.md agent spec at cgg-runtime/agents/review-execute.md. -->
