# /loop Integration Patterns for CGG Governance

Design document for session-scoped governance polling via Claude Code's `/loop` facility.

## /loop Properties

- Session-scoped (dies on exit)
- 3-day max expiry
- Minute granularity
- Runs a prompt or slash command on a recurring interval
- Default interval: 10 minutes

## Governance Polling Patterns

### 1. Signal Health Check

```
/loop 30m /siren
```

**Purpose:** Periodic signal dashboard refresh. Catches volume accrual, decay state changes, and warrant eligibility thresholds without waiting for the next cadence.

**When to use:** Long implementation sessions where governance attention might drift. The 30m interval balances signal freshness against context consumption.

**What it surfaces:** Active signal count, warrant status, harmonic triads, volume/decay deltas since last check.

### 2. CogPR Queue Monitor

```
/loop 30m Check audit-logs/cprs/queue.jsonl for enrichment_eligible CPRs and report count + status summary
```

**Purpose:** Detect when CogPRs have matured past their enrichment window or accumulated enough tics to advance.

**When to use:** Sessions focused on implementation where governance maintenance might be deferred. The monitor ensures temporal maturity gates don't slip unnoticed.

**What it surfaces:** CPR counts by status (pending, enrichment_eligible, enrichment_needed, promotable), tic distance to next review window.

### 3. Ladder Coherence Pulse

```
/loop 60m Scan CLAUDE.md chain from cwd upward. Report any parent/child contradictions, missing references, or demotion pressure. Brief summary only.
```

**Purpose:** Lightweight coherence check between cadence boundaries. Not a full ladder audit — a pulse check that detects gross incoherence.

**When to use:** After editing CLAUDE.md at any rung, to catch upstream/downstream contradictions before they compound.

**Interval:** 60m is appropriate — ladder coherence changes slowly relative to signal state.

### 4. Enrichment Check-and-Fulfill

```
/loop 45m Read audit-logs/cprs/queue.jsonl. For each enrichment_eligible CPR, check if cross-zone pattern evidence exists in MEMORY.md files. Report findings.
```

**Purpose:** Proactive enrichment gathering that runs between Mogul activations. Searches for cross-zone pattern evidence that would strengthen CPR review packets.

**When to use:** When Mogul mandates include enrichment cycles but the agent hasn't been activated yet. The loop pre-gathers evidence.

**Boundary:** Read-only. The loop reports findings — it does not write to governance surfaces.

### 5. Runtime Drift Watch

```
/loop 60m Compare sha256 of canonical vs installed for: agents/mogul.md, skills/cadence/SKILL.md, hooks/posttool-microscan.sh. Report any drift.
```

**Purpose:** Continuous runtime sync validation. Detects when installed surfaces diverge from canonical without waiting for the next init-governance run.

**When to use:** Active CGG development sessions where canonical sources are being modified. Catches forgotten syncs.

## Design Constraints

### Session-scoped is correct for governance polling

Governance polling should NOT be persistent (cron/daemon). Reasons:
- Governance state only matters when an agent session is active
- Persistent polling without an active session would produce findings with no actor to consume them
- Session-scoped polling naturally aligns with the cadence lifecycle: session start → work → polling → cadence → session end

### Interval selection heuristic

| Signal type | Recommended interval | Rationale |
|-------------|---------------------|-----------|
| Signal health | 30m | Signals accrue per-tic; 30m catches meaningful deltas |
| Queue state | 30m | Temporal maturity gates have tic-scale granularity |
| Ladder coherence | 60m | CLAUDE.md chain changes slowly |
| Runtime drift | 60m | Source files change infrequently |
| Enrichment gathering | 45m | Balance between freshness and context cost |

### Context budget awareness

Each loop invocation consumes context. A 30m loop in a 4-hour session fires ~8 times. Keep loop prompts short and outputs concise. Prefer structured summaries over verbose reports.

### Mogul boundary

Loops are NOT a substitute for Mogul mandates. They provide between-mandate visibility. When a loop detects actionable state (enrichable CPRs, drift, coherence breaks), the correct response is to escalate to Mogul via mandate — not to act directly from the loop.

## Integration with Existing Hooks

Loops complement hooks but serve different purposes:

| Mechanism | Trigger | Scope | Action |
|-----------|---------|-------|--------|
| Hook (PostToolUse) | Every Edit/Write | Per-tool | Microscan staging |
| Hook (SessionStart) | Session start | Once | Context restore |
| Hook (UserPromptSubmit) | Every prompt | Per-prompt | Gate check |
| Loop | Time interval | Periodic | Status polling |
| Mogul mandate | Cadence/explicit | Per-activation | Heavy governance |

Loops fill the gap between hook-driven micro-events and mandate-driven macro-cycles.
