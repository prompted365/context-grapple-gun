# Context Grapple Gun — Domain CLAUDE.md

## Epistemic Volatility Notice

Claude Code hook format, plugin manifest schema, and install semantics are **externally versioned by Anthropic**. Treat as a volatile contract surface. Do not promote session-inferred schema understanding to doctrine without validating against current docs/schema.

All schema-specific sections below (Hook Format, Plugin Hooks, etc.) reflect the format as of the last validated check. They may become stale when Claude Code updates.

<!-- promoted from CogPR-15 (tic 9→11). Refines CogPR-1 and CogPR-4 by version-banding them. Source: tic-8 post-session analysis. -->

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

Downstream surfaces (INSTALL.md, academy guide, init-governance SKILL.md) updated to current format at tic 2.

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

## Plugin Declaration Surface (CGG-Specific)

CGG 4.0.0 demonstrated that component declarations placed in proprietary plugin.json fields (`components`, `install`, `claude_code`) did not register and were replaced in 4.0.1 by marketplace-based declaration. For this repo, the supported fix was `marketplace.json` + `strict: false` plus marketplace-based install flow.

This is a CGG-scope declaration-surface lesson, not federation law. The self-hosting marketplace pattern is the validated install mechanism for plugins with non-standard component paths.

<!-- promoted from CogPR-13 (tic 8→11, arena-refined). Supersedes CogPR-14. Source: npx context-grapple-gun install failure → fix at lib/installer.mjs + .claude-plugin/marketplace.json. -->

## npm Distribution Wrapper

CGG is distributed via npm as `context-grapple-gun`. The npm package is a zero-dep CLI wrapper — `npx context-grapple-gun install` clones the repo and registers the plugin via the self-hosting marketplace pattern. The runtime stays in the plugin; npm orchestrates install only.

- Published: 4.0.0 (initial), 4.0.1 (marketplace fix)
- npm auth requires granular access token with publish scope

<!-- promoted from CogPR-11 (tic 7→11). Source: session planning — user request for npm publishable package. -->

## Subagent Delegation — Schema Contracts

When delegating hook creation or script writing to subagents, include the target script's JSON output schema in the prompt. Subagents that parse another script's output without knowing the schema will write incorrect field paths.

**Failure mode**: Agent wrote `d.get('drifted',0)` but runtime-sync.py nests under `summary.drifted`.

<!-- promoted from CogPR-12 (tic 8→11). Source: canonical/.claude/hooks/federation-sync-check.sh:37. -->

## Mandate Consumption Discipline

If a cadence mandate exists when a session closes, the session must invoke Mogul or explicitly defer. Mandates generated by cadence hooks but not consumed create governance gap windows — cycles queue up but no scan occurs within the session that owns them.

Three consecutive unexecuted mandates at tics 13-15 demonstrated the structural pattern. The activation fabric now handles consumption, but the obligation to invoke or defer is doctrinal.

<!-- promoted from CogPR-26 (tic 16→19). Source: 3 consecutive unexecuted mandates at tics 13, 14, 15. Band: COGNITIVE. -->

## Lead Context as Binding Constraint

Lead context accumulation — not advocate turn count — is the binding budget constraint in governed arenas. The lead receives ALL advocate outputs: N advocates × M turns each = N×M messages accumulating in lead context. Advocate budgets are local (bounded per-agent), but lead context is global (accumulates across all agents).

The routing function must check lead context ceiling across all regimes before spawning.

<!-- promoted from CogPR-32 (tic 21→22, arena-sourced T3G). All three advocates independently identified this as the binding constraint. Band: COGNITIVE. -->

## Coordination Overhead Accounting

Coordination overhead (nudges, retries, phase-transition messages) is lead-side cost, not advocate-side cost. Advocate budgets should price reasoning depth only. Conflating coordination with advocacy inflates budget estimates.

This accounting correction changed the LIBERAL regime derivation from 28 to ~22 turns/advocate — coordination overhead was incorrectly counted as advocate budget consumption.

<!-- promoted from CogPR-35 (tic 21→22, arena-sourced T3G). All three advocates independently confirmed this accounting principle. Band: COGNITIVE. -->

## Epistemic Triangulation Geometry

Epistemic triangulation (coincidence/mechanism/counterfactual) is an effective geometry for hypothesis-testing arenas. Each angle tests a different failure mode of the claim:
- **Coincidence** — could the evidence be explained by chance or confounding?
- **Mechanism** — is there a causal pathway connecting the claim to the evidence?
- **Counterfactual** — what would we expect to observe if the claim were false?

Use this geometry when the arena question is a testable hypothesis rather than a design choice.

<!-- promoted from arena-marketplace-0 (tic 9→25, arena-sourced marketplace-epistemic-triangulation). Process lesson — reinforced confidence tier. Band: COGNITIVE. -->
