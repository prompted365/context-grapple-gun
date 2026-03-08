# Mogul Headless Enforcement Patterns

Design document for leveraging Claude Code hook events to automate Mogul mandate execution.

## Available Hook Events (2.1.69+)

| Event | When it fires | CGG use case |
|-------|--------------|--------------|
| `TeammateIdle` | When a spawned teammate has no work | Trigger non-blocking Mogul cycles |
| `TaskCompleted` | When a background agent finishes | Post-mandate synthesis, mandate chaining |
| `InstructionsLoaded` | When CLAUDE.md loads into context | Governance surface change detection |

All events include `agent_id` and `agent_type` fields — enabling Mogul-specific routing.

## Pattern 1: TeammateIdle → Non-Blocking Mandate

When a teammate (including Mogul) goes idle, check if pending mandates exist and auto-trigger.

```json
{
  "hooks": {
    "TeammateIdle": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/mogul-idle-trigger.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**Hook script logic:**
1. Read `agent_type` from stdin JSON
2. If agent_type is NOT "mogul", check for pending mandate at `audit-logs/mogul/mandates/current.json`
3. If mandate exists with `status: "pending"` and `mode.blocking_to_orchestrator: false`:
   - Output `{"continue": true}` to keep the session alive
   - Log "mandate available for non-blocking execution" to microscan staging
4. If no mandate or mandate already started: output `{"continue": false}` (let idle proceed)

**Why TeammateIdle, not SessionStart:** SessionStart fires once. TeammateIdle fires whenever a teammate has capacity — natural trigger for background governance work.

## Pattern 2: TaskCompleted → Mandate Chain

When Mogul finishes a mandate cycle, chain to the next due cycle if the mandate allows.

```json
{
  "hooks": {
    "TaskCompleted": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/mogul-chain-check.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**Hook script logic:**
1. Read `agent_id` and `agent_type` from stdin
2. If the completed agent was Mogul (match agent_type or agent_id pattern):
   - Read mandate `current.json`
   - Check if `cycle_request.run_now` has unexecuted cycles
   - If yes: update mandate status, log chain continuation
   - If no: mark mandate completed, archive to history

**Boundary:** The hook detects and logs — it does not spawn Mogul. The interactive orchestrator reads the hook output and decides whether to re-activate.

## Pattern 3: InstructionsLoaded → Governance Surface Watch

When CLAUDE.md or rules files load, detect governance surface changes that might indicate drift or manual edits.

```json
{
  "hooks": {
    "InstructionsLoaded": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/governance-surface-watch.sh",
            "timeout": 3
          }
        ]
      }
    ]
  }
}
```

**Hook script logic:**
1. Hash the loaded governance surfaces
2. Compare against last-known hashes (stored in `.microscan-staging.jsonl`)
3. If changed since last check: stage a microscan finding for Mogul
4. Particularly watch for convention block presence/absence in project CLAUDE.md

## Implementation Priority

| Pattern | Priority | Complexity | Value |
|---------|----------|------------|-------|
| TeammateIdle → mandate trigger | High | Low (simple existence check) | Enables automatic Mogul activation |
| TaskCompleted → chain check | Medium | Medium (mandate parsing + state update) | Enables multi-cycle mandates without manual re-trigger |
| InstructionsLoaded → surface watch | Low | Low (hash comparison) | Nice-to-have; microscan already covers most cases |

## Architectural Constraints

### Hooks are physics, not reasoning

Hooks detect conditions and stage findings. They do NOT:
- Spawn agents directly (hooks can't invoke the Agent tool)
- Make governance decisions
- Modify CLAUDE.md or MEMORY.md
- Execute mandate cycles

The hook-to-Mogul path is: hook detects condition → stages finding → interactive orchestrator reads finding → orchestrator spawns Mogul with mandate.

### Agent ID filtering

TeammateIdle and TaskCompleted fire for ALL teammates, not just Mogul. The hook must filter by `agent_type` to avoid false triggers. Mogul's agent_type is `"mogul"` when spawned via `subagent_type: mogul`.

### Mandate state machine

```
pending → started → (cycle_1 complete → cycle_2 complete → ...) → completed
                  ↘ error (if cycle fails)
```

The TaskCompleted hook advances the state machine. The TeammateIdle hook checks for opportunities to start.

### Cost awareness

Each hook invocation has overhead (process spawn, JSON parse). Keep hooks under 2 seconds. The mandate existence check is a single `stat` + `jq` call — well within budget.
