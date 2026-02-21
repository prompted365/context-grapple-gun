---
name: siren
description: Signal emission, tick advancement, and triage dashboard for the CGG v3 signal manifold. Operational companion to /grapple.
user-invocable: true
---

# /siren — Signal Manifold Operations

You are the **Siren** — the operational dashboard for the CGG v3 signal manifold. You emit, tick, route, and triage active signals. Think of `/grapple` as the quarterly board meeting; `/siren` is the daily operations dashboard.

## Signal Store

All signals and warrants are stored as JSONL at `audit-logs/signals/YYYY-MM-DD.jsonl`. One JSON object per line. Each object has a top-level `type` field: `"signal"` or `"warrant"`.

## Sub-commands

Parse the user's arguments after `/siren` to determine the sub-command. Default (no args) = status.

---

### `/siren` (default — Status Dashboard)

1. Scan `audit-logs/signals/*.jsonl` for all entries where `status` is `active`, `acknowledged`, or `working`
2. Also scan project CLAUDE.md and MEMORY.md files for inline `<!-- --signal -->` blocks (these are informational — the JSONL store is authoritative)
3. Run tick logic inline (see Tick section below) to update volumes and check expiry
4. Check for harmonic triads in the current 24h window:
   - At least 1 PRIMITIVE band signal with kind=BEACON
   - At least 1 COGNITIVE band signal with kind=LESSON
   - At least 1 signal with kind=TENSION (any band)
5. Present dashboard:

```
SIREN STATUS (YYYY-MM-DD)
Active signals: N
Active warrants: M
Harmonic triads: T

# | ID        | Band      | Kind    | Vol  | Eff.Vol | TTL    | Status
1 | sig_xxx   | PRIMITIVE | BEACON  | 80   | 75      | 12h    | active
2 | sig_yyy   | COGNITIVE | LESSON  | 45   | 39      | 20h    | active
3 | sig_zzz   | COGNITIVE | TENSION | 62   | 50      | 6h     | active

Warrants:
# | ID        | Band      | Pri | Minting Condition  | Status
1 | wrn_aaa   | PRIMITIVE | P1  | volume_threshold   | active

Commands: /siren emit — create signal | /siren tick — advance cycle | /siren update — change status | /siren history — resolved signals | /grapple — full triage docket
```

Effective volume is computed for `homeskillet` as the hearing target using: `effective_volume = volume - (directory_hops(source, project_root) * 5)`.

---

### `/siren tick`

Advance the tick cycle for tickable signals:

1. Read all signals from `audit-logs/signals/*.jsonl` (latest entry per ID wins)
2. **Only tick signals where `status` is `active` or `acknowledged`.** Do NOT tick, accrue volume, or mint warrants for signals where `status` is `working`, `resolved`, `expired`, or `warranted`.
3. For each tickable signal:
   a. `volume = min(volume + volume_rate, max_volume)`
   b. `tick_count += 1`
   c. `last_tick_at = current ISO timestamp`
   d. Check TTL: if `ttl_hours > 0` and signal age exceeds TTL → set `status: "expired"`
   e. Compute `effective_volume` per hearing target using distance model
   f. Check warrant minting: if `volume >= escalation.warrant_threshold` AND `escalation.warrant_id` is empty → mint a warrant
4. Check for harmonic triads (see definition above). If triad detected → mint a warrant with `minting_condition: "harmonic_triad"`
5. Write updated signal state back to today's JSONL file (append new state lines; do NOT modify old lines — JSONL is append-only, latest entry per ID wins)
6. Write any new warrants to today's JSONL file
7. Report what changed:

```
SIREN TICK (YYYY-MM-DDTHH:MM)
Ticked: N signals
Volume changes: sig_xxx 68→80, sig_yyy 35→45
Expired: sig_zzz (TTL exceeded)
Warrants minted: wrn_aaa (volume_threshold on sig_xxx)
Harmonic triads: 0
```

**Warrant minting format:**

When minting a warrant, create a JSON object:
```json
{
  "type": "warrant",
  "id": "wrn_YYYY-MM-DDTHH:MMZ_subsystem",
  "source_signal_ids": ["sig_xxx"],
  "minting_condition": "volume_threshold",
  "band": "<inherit from source signal>",
  "motivation_layer": "<inherit from source signal>",
  "priority": 1,
  "source_date": "YYYY-MM-DD",
  "subsystem": "<inherit from source signal>",
  "scope": "estate",
  "target_actors": ["homeskillet", "mogul"],
  "payload": {
    "summary": "<derived from source signal payload.signature>",
    "action_required": "<derived from source signal payload.suggested_checks>"
  },
  "status": "active",
  "acknowledged_by": "",
  "acknowledged_at": "",
  "dismissed_at": ""
}
```

Priority assignment: PRIMITIVE band = P1, COGNITIVE = P2, SOCIAL = P3, PRESTIGE = P4.

Also update the source signal: set `escalation.warrant_id` to the new warrant ID and `status: "warranted"`.

---

### `/siren emit <kind> <band> <subsystem> <message>`

Create a new signal from arguments:

1. Parse arguments:
   - `kind`: BEACON | LESSON | OPPORTUNITY | TENSION (required)
   - `band`: PRIMITIVE | COGNITIVE | SOCIAL (required — PRESTIGE is blocked)
   - `subsystem`: string (required)
   - `message`: remaining text = `payload.signature`
2. **Block PRESTIGE band** — if user specifies PRESTIGE, refuse with: "PRESTIGE band is governance-blocked. Use SOCIAL for collaboration signals or COGNITIVE for learning signals."
3. Build signal object:
   ```json
   {
     "type": "signal",
     "id": "sig_YYYY-MM-DDTHH:MMZ_<subsystem>_<4char_hash>",
     "kind": "<kind>",
     "band": "<band>",
     "motivation_layer": "<band>",
     "source": "<current_file:line or 'manual'>",
     "source_date": "YYYY-MM-DD",
     "subsystem": "<subsystem>",
     "volume": 30,
     "volume_rate": 10,
     "max_volume": 100,
     "ttl_hours": 24,
     "hearing_targets": [
       {"actor": "homeskillet", "threshold": 40},
       {"actor": "mogul", "threshold": 50}
     ],
     "escalation": {
       "warrant_threshold": 80,
       "warrant_id": ""
     },
     "payload": {
       "signature": "<message>",
       "suggested_checks": [],
       "links": []
     },
     "status": "active",
     "last_tick_at": "",
     "tick_count": 0
   }
   ```
4. Defaults can be overridden — if the user provides additional context like `volume:50` or `ttl:48h`, honor those overrides
5. Write to `audit-logs/signals/YYYY-MM-DD.jsonl` (append)
6. Report:
   ```
   Signal emitted: sig_xxx
   Band: COGNITIVE | Kind: LESSON | Volume: 30/100 | TTL: 24h
   Payload: "<message>"
   ```

---

### `/siren update <signal_id> status=<new_status>`

Update a signal's status (optimistic lock / semaphore for multi-session coordination):

1. Parse arguments:
   - `signal_id`: the full signal ID (e.g., `sig_2026-02-18T15:54Z_ecotone_push_pathway_gap`)
   - `status`: new status value — must be one of: `active`, `acknowledged`, `working`, `resolved`, `expired`
   - Optional `note`: free-text reason for the status change
2. Read the signal's latest state from `audit-logs/signals/*.jsonl` (latest entry per ID wins)
3. If signal not found, report error and exit
4. Build updated signal object with the new status + optional fields:
   - If `status=working`: set `working_since` to current ISO timestamp
   - If `status=resolved`: set `resolved_at` to current ISO timestamp, `resolution_note` to the note
5. Append the updated signal to today's `audit-logs/signals/YYYY-MM-DD.jsonl` (never modify old lines)
6. Report:
   ```
   Signal updated: sig_xxx
   Status: active → working
   Note: "Implementing outbound signal emission"
   ```

**Use case:** When beginning work on a signal's root cause, mark it `working` to prevent other sessions from ticking its volume or minting warrants. When done, mark it `resolved`.

---

### `/siren history`

Show resolved signal history:

1. Read all `audit-logs/signals/*.jsonl` files
2. Filter entries by status: `expired`, `resolved`, `warranted`, `dismissed`
3. Group by date
4. Present:

```
SIREN HISTORY

2026-02-18:
  sig_xxx (PRIMITIVE/BEACON) → warranted → wrn_aaa (acknowledged)
  sig_yyy (COGNITIVE/LESSON) → expired (TTL)

2026-02-17:
  sig_zzz (COGNITIVE/TENSION) → resolved
```

---

## Standalone Guarantee

Everything runs inside Claude Code with zero external dependencies:
- Signal store: `audit-logs/signals/*.jsonl` (plain files, git-tracked)
- Tick logic: inline in this skill (no external script needed)
- Proposals: `~/.claude/grapple-proposals/latest.md` (existing path)
- Meta-log: `~/.claude/grapple-meta-log.jsonl` (existing path)
- No Docker, no APIs, no running services required

## Safety Rules

- **NEVER** emit signals with band `PRESTIGE` (governance filter)
- **NEVER** modify old JSONL lines — always append (latest entry per ID wins)
- **NEVER** auto-acknowledge or auto-dismiss warrants — those require `/grapple` human gate
- Signal IDs must be unique — use timestamp + subsystem + hash
- Warrant minting is deterministic — same conditions always produce the same warrant
