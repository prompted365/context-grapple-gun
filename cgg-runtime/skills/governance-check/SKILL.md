---
name: governance-check
description: |
  Compact governance status check — signal store, queue state, mandate status. Designed as a /loop target for continuous monitoring.

  CENTROID:
  on-demand read-only governance state snapshot

  IS:
  - compact status dashboard across mandate, signals, queue, and cadence
  - /loop-compatible polling surface for continuous monitoring
  - single-pass read of canonical summary files

  IS NOT:
    collapse_zones:
      - governance mutator (never writes to signal, queue, mandate, or audit surfaces)
      - signal triage (classification belongs to /siren; governance-check only displays counts)
      - queue promoter (queue.jsonl belongs to /review pipeline)
      - judgment surface (never evaluates whether state warrants action — only surfaces it)
      - deep scan (one-pass summary read only; no multi-file reconstruction)
    sibling_overlaps:
      - /siren (signal dashboard — deeper, triage-capable)
      - /statusline (ambient radar — same data, passive render)
      - /review (judgment over the same queue surface)

  WHEN:
  - when a compact governance snapshot is needed inside another flow
  - when running as a /loop target for continuous monitoring
  - when an action recommendation is needed without opening /siren or /review

  NOT WHEN:
  - when action is intended (use /siren, /review, or /governance-mandate-cycle)
  - during /cadence (cadence writes state; governance-check reads — same boundary cannot do both)
  - when deep reconstruction is needed (raw ledger scanning is governance-layer work)

  RELATES TO:
  - /statusline (ambient observability — statusline renders passively; governance-check responds to an explicit poll)
  - /siren (signal ops — governance-check surfaces counts; /siren classifies and triages)
  - /governance-mandate-cycle (action surface — governance-check flags pending mandate; mandate-cycle consumes it)

  ARGS:
    stance: dispatch
    off_envelope: proceed-with-note
    # off_envelope rationale: /governance-check is read-only; an undeclared arg
    # cannot cause state damage. proceed-with-note lets future ray additions
    # surface without blocking Architect flow.
    core_dispatch_rays:
      - ""  → full snapshot (mandate + signals + queue + cadence)
    secondary_modulation_axes:
      - verbosity: compact | verbose
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
