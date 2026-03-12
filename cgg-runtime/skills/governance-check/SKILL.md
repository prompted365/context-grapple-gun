---
name: governance-check
description: "Compact governance status check — signal store, queue state, mandate status. Designed as a /loop target for continuous monitoring."
user-invocable: true
---

# /governance-check — Governance Status Dashboard

Lightweight status check for governance surfaces. Returns a compact summary suitable for repeated polling via `/loop`.

## Usage

- **`/governance-check`** — one-shot status report
- **`/loop 10m /governance-check`** — continuous monitoring every 10 minutes

## Checks (sequential, compact output)

### 1. Mandate Status
Read `audit-logs/mogul/mandates/current.json`:
- If `status: "pending"`: report "MANDATE PENDING: {mandate_id} — cycles: {run_now}"
- If `status: "started"`: report "MANDATE RUNNING: {mandate_id}"
- If `status: "completed"` or `status: "deferred"`: report "MANDATE CLEAR"
- If file missing: report "NO MANDATE"

### 2. Signal Status
Scan `audit-logs/signals/*.jsonl` for active signals:
- Count signals by state (active, acknowledged, working, warranted)
- Report loudest signal (highest volume)
- Report any active warrants
- Format: "SIGNALS: {active} active, {warranted} warranted. Loudest: {id} (vol={volume}, band={band})"
- If no active signals: "SIGNALS: all clear"

### 3. Queue Status
Run `python3 audit-logs/cprs/build_queue_index.py --json 2>/dev/null` or read `audit-logs/cprs/queue-index.json`:
- Report pending CPR count
- Report total entries
- Format: "QUEUE: {pending} pending, {total} total"

### 4. Cadence Status
Read `.ticzone` for current tic and due dates:
- Report current tic
- Report next due cycles (review, mining, ladder, deep)
- Flag any overdue cycles
- Format: "TIC: {current}. Due: review@{N}, mining@{N}, ladder@{N}"

## Output Format

Emit exactly one compact block:

```
--- governance-check @ tic {N} ---
MANDATE: {status}
SIGNALS: {summary}
QUEUE:   {summary}
CADENCE: {summary}
---
```

If any check shows actionable state, append:

```
ACTION NEEDED: {what} — run {command}
```

Examples:
- `ACTION NEEDED: pending mandate — run /governance-mandate-cycle`
- `ACTION NEEDED: 3 pending CPRs overdue for review — run /review`
- `ACTION NEEDED: active warrant — run /siren`

## Constraints

- Read-only — never modifies any file
- Compact output — designed for repeated polling, not deep analysis
- No agent spawning — direct file reads only
- If a file is missing or unreadable, report "UNAVAILABLE" for that check, do not error
