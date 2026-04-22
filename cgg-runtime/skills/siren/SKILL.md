---
name: siren
description: |
  Signal emission, tick advancement, and triage dashboard for the CGG v3 signal manifold. Operational companion to /review.

  CENTROID:
  operational interface to the signal manifold state machine

  IS:
  - the place signals are emitted, ticked, updated, and triaged
  - the dashboard for active signal state and effective volume
  - the snapshot/diff surface for conformation records

  IS NOT:
    collapse_zones:
      - doctrine judgment (review evaluates; siren operates — never decides whether a signal warrants inscription)
      - queue mutator (queue.jsonl belongs to review pipeline; siren must not write to CogPR queue)
      - mandate spawner (cadence writes mandates; siren carries signals, not mandates)
      - warrant auto-acknowledger (warrants require /review human gate; siren mints via threshold but never acks)
      - CogPR extractor (extraction is cpr-extract-hook territory; siren emits signals, never CogPRs)
      - timestamp-based transition driver (tic is the time authority — timestamps are observability only)
    sibling_overlaps:
      - /review (warrant triage)
      - /cadence (tic authority)
      - archivist (typed-record persistence)

  WHEN:
  - when session start reports active signals to triage
  - when an actor needs to emit a new signal for a persistent condition
  - when tic has advanced and signals need volume accrual or decay
  - when a signal's state needs to change (acknowledged/working/resolved/dismissed)
  - when a conformation snapshot is needed at a tic boundary
  - on explicit operator invocation

  NOT WHEN:
  - during /cadence (cadence writes tic events; siren ticks against them; same boundary cannot do both)
  - when the correct surface is /review (CogPR promotion or warrant judgment — route there)
  - mid-constitutional-modification (siren records condition; doctrine change belongs to /review)
  - for ephemeral in-session state (signals represent persistent conditions, not transient observations)

  RELATES TO:
  - /review (constitutional judgment — siren operates the manifold; review judges what must become doctrine or bounded action)
  - /cadence (session epoch boundary — cadence advances the tic count; siren ticks signals against the advanced count)
  - /complement (response-geometry inference — different surface; complement is local closure, siren is manifold ops)
  - archivist (typed-record persistence — archivist is downstream; siren is the live operational store)

  ARGS:
    stance: dispatch
    off_envelope: ask
    # off_envelope rationale: /siren is the signal manifold operational surface.
    # Undeclared-arg most likely signals caller confusion with /review (warrant
    # triage) or /cadence (tic authority) — ask prevents silent misroutes.
    core_dispatch_rays:
      - ""                   → status (dashboard)
      - "tick"               → advance volume accrual and decay
      - "emit"               → create new signal (kind/band/subsystem/message)
      - "update"             → signal state transition (signal_id + status)
      - "history"            → resolved/dismissed view
      - "conformation"       → tic-boundary snapshot
      - "conformation diff"  → diff two snapshots
    secondary_modulation_axes:
      - scope: all | active | warrants-only
      - target_actor: interactive_orchestrator | <role>
user-invocable: true
---

# /siren — Signal Manifold Operations

You are the **Siren** — the operational dashboard for the CGG v3 signal manifold. You emit, tick, route, and triage active signals. Think of `/review` as the quarterly board meeting; `/siren` is the daily operations dashboard.

## Constitutional Principles

1. **Signals do not expire.** A signal represents a persistent condition. Conditions do not disappear because attention paused. Remove from active only via `resolved` (evidence) or `dismissed` (human rationale).
2. **Tic is the time authority.** All state transitions, decay, and accrual are measured in tic counts. Timestamps are tracked for observability and audit only — never for handling logic.
3. **Signals may decay, not die.** Unreinforced signals lose effective volume over time but remain queryable. Renewed evidence re-amplifies them.
4. **Warrant eligibility is kind-gated.** By default only BEACON and TENSION can mint warrants. Configurable via `.ticzone` `signal_governance.warrant_eligible_kinds`.
5. **PRIMITIVE signals are always audible.** Effective volume for PRIMITIVE band has a floor at `hearing_threshold + 1` regardless of topological muffling.

## Signal Store

All signals and warrants are stored as JSONL at `audit-logs/signals/YYYY-MM-DD.jsonl`. One JSON object per line. Each object has a top-level `type` field: `"signal"` or `"warrant"`.

## Valid Signal States

```
active      = condition present, volume accruing per tic, decaying if unreinforced
acknowledged = condition seen by an actor, still accruing
working     = condition actively being addressed (volume frozen, no warrant minting)
warranted   = obligation minted (volume frozen)
resolved    = condition verified fixed (terminal — requires evidence)
dismissed   = explicitly rejected with rationale (terminal — requires human gate)
```

Not valid: `expired` — amnesia is not a lifecycle event.

## Sub-commands

Parse the user's arguments after `/siren` to determine the sub-command. Default (no args) = status.

---

### `/siren` (default — Status Dashboard)

1. Scan `audit-logs/signals/*.jsonl` for all entries where `status` is `active`, `acknowledged`, or `working`
2. Also scan project CLAUDE.md and MEMORY.md files for inline `<!-- --signal -->` blocks (these are informational — the JSONL store is authoritative)
3. Run tick logic inline (see Tick section below) to update volumes
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

# | ID        | Band      | Kind    | Vol  | Eff.Vol | Decay | Status
1 | sig_xxx   | PRIMITIVE | BEACON  | 80   | 75      | 0     | active
2 | sig_yyy   | COGNITIVE | LESSON  | 45   | 39      | -4    | active
3 | sig_zzz   | COGNITIVE | TENSION | 62   | 50      | 0     | active

Warrants:
# | ID        | Band      | Pri | Minting Condition  | Status
1 | wrn_aaa   | PRIMITIVE | P1  | volume_threshold   | active

Commands: /siren emit | /siren tick | /siren update | /siren history | /review
```

Effective volume is computed per hearing target from zone configuration:

1. Read `.ticzone` for `governance_actors` — each entry has `role` and `threshold`
2. If `governance_actors` is absent, use safe defaults: `{"homeskillet": {"role": "interactive_orchestrator", "threshold": 40}}`
3. For each actor, compute:
```
effective_volume = volume - (directory_hops(source, project_root) * muffling_per_hop)
if band == "PRIMITIVE":
    effective_volume = max(effective_volume, actor_threshold + 1)
```
4. Dashboard displays effective volume for the primary actor (first entry or interactive_orchestrator role)

Actor targets must be read from zone configuration. Hardcoded actor lists are invalid outside development environments. If `governance_actors` is absent, use the safe default above and emit a warning: "No governance_actors in .ticzone — using development defaults."

---

### `/siren tick`

Advance the tick cycle for tickable signals:

1. Read all signals from `audit-logs/signals/*.jsonl` (latest entry per ID wins)
2. Read `.ticzone` for `signal_governance` config (warrant_eligible_kinds, decay_rate_per_tic)
3. **Only tick signals where `status` is `active` or `acknowledged`.** Do NOT tick, accrue volume, or mint warrants for signals where `status` is `working`, `resolved`, `warranted`, or `dismissed`.
4. For each tickable signal:
   a. **Accrue**: `volume = min(volume + volume_rate, max_volume)`
   b. **Decay**: If this signal has not received a reinforcing emission (a new emit with the same dedup ID) since the last tick, apply decay: `volume = max(0, volume - decay_rate_per_tic)`. Default `decay_rate_per_tic` is from `.ticzone` (default 2). Decay is applied AFTER accrual — a ticked signal that was also re-emitted this cycle gains net volume; an unreinforced signal may lose volume.
   c. `tick_count += 1`
   d. `last_tick_at = current ISO timestamp` (observability only — not used for state transitions)
   e. Compute `effective_volume` per hearing target using distance model + PRIMITIVE floor
   f. **Warrant check** (kind-gated): if `kind` is in `warrant_eligible_kinds` (default: BEACON, TENSION) AND `volume >= escalation.warrant_threshold` AND `escalation.warrant_id` is empty → mint a warrant
5. Check for harmonic triads (see definition above). If triad detected → mint a warrant with `minting_condition: "harmonic_triad"`
6. Write updated signal state back to today's JSONL file (append new state lines; do NOT modify old lines — JSONL is append-only, latest entry per ID wins)
7. Write any new warrants to today's JSONL file
8. Report what changed:

```
SIREN TICK (YYYY-MM-DDTHH:MM | tic #N)
Ticked: N signals
Volume changes: sig_xxx 68->80, sig_yyy 45->43 (decay -2)
Decayed below hearing: sig_zzz (vol=12, threshold=40)
Warrants minted: wrn_aaa (volume_threshold on sig_xxx)
Ineligible for warrant: sig_bbb (kind=LESSON, not in warrant_eligible_kinds)
Harmonic triads: 0
```

**Decay semantics:**
- A signal at volume 0 is still `active` — it has not been resolved or dismissed, just quiet.
- If a decayed signal receives a new emission (same dedup key), volume snaps back to the emission volume. The condition reasserted.
- Signals below all hearing thresholds are still in the store and still ticked — they're just inaudible until reinforced.

---

### `/siren emit <kind> <band> <subsystem> <message>`

Create a new signal from arguments:

1. Parse arguments:
   - `kind`: BEACON | LESSON | OPPORTUNITY | TENSION (required)
   - `band`: PRIMITIVE | COGNITIVE | SOCIAL (required — PRESTIGE is blocked)
   - `subsystem`: string (required)
   - `message`: remaining text = `payload.signature`
2. **Block PRESTIGE band** — if user specifies PRESTIGE, refuse with: "PRESTIGE band is governance-blocked. Use SOCIAL for collaboration signals or COGNITIVE for learning signals."
3. Read `.ticzone` for `signal_governance.warrant_eligible_kinds` (default: ["BEACON", "TENSION"])
4. Build signal object:
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
     "hearing_targets": "__read from .ticzone governance_actors — see zone config__",
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
5. **Zombie guard** (warrant-eligible kinds only): if `max_volume < escalation.warrant_threshold`, clamp `warrant_threshold` down to `max_volume` and warn the operator.
6. **Non-warrant kinds**: if `kind` is not in `warrant_eligible_kinds`, set `escalation.warrant_threshold` to `null` — these signals cannot warrant via volume. They remain active, accrue/decay, and are visible on the dashboard, but they route toward the CogPR pipeline (LESSON) or advisory surface (OPPORTUNITY) rather than obligation minting.
7. Defaults can be overridden — if the user provides additional context like `volume:50` or `decay:5`, honor those overrides
8. Write to `audit-logs/signals/YYYY-MM-DD.jsonl` (append)
9. Report:
   ```
   Signal emitted: sig_xxx
   Band: COGNITIVE | Kind: LESSON | Volume: 30/100 | Warrant: ineligible (LESSON)
   Payload: "<message>"
   ```
   or for warrant-eligible:
   ```
   Signal emitted: sig_xxx
   Band: PRIMITIVE | Kind: BEACON | Volume: 30/100 | Warrant threshold: 80
   Payload: "<message>"
   ```

---

### `/siren update <signal_id> status=<new_status>`

Update a signal's status (optimistic lock / semaphore for multi-session coordination):

1. Parse arguments:
   - `signal_id`: the full signal ID (e.g., `sig_2026-02-18T15:54Z_ecotone_push_pathway_gap`)
   - `status`: new status value — must be one of: `active`, `acknowledged`, `working`, `resolved`, `dismissed`
   - Optional `note`: free-text reason for the status change
2. Read the signal's latest state from `audit-logs/signals/*.jsonl` (latest entry per ID wins)
3. If signal not found, report error and exit
4. **Dismissed requires rationale**: if `status=dismissed` and no `note` provided, refuse with: "Dismissal requires a rationale. Use: /siren update <id> status=dismissed note='reason'"
5. Build updated signal object with the new status + optional fields:
   - If `status=working`: set `working_since` to current ISO timestamp
   - If `status=resolved`: set `resolved_at` to current ISO timestamp, `resolution_note` to the note
   - If `status=dismissed`: set `dismissed_at` to current ISO timestamp, `dismissal_rationale` to the note
6. Append the updated signal to today's `audit-logs/signals/YYYY-MM-DD.jsonl` (never modify old lines)
7. Report:
   ```
   Signal updated: sig_xxx
   Status: active -> working
   Note: "Implementing outbound signal emission"
   ```

**Use case:** When beginning work on a signal's root cause, mark it `working` to prevent other sessions from ticking its volume or minting warrants. When done, mark it `resolved`.

---

### `/siren history`

Show resolved/dismissed signal history:

1. Read all `audit-logs/signals/*.jsonl` files
2. Filter entries by status: `resolved`, `warranted`, `dismissed`
3. Group by date
4. Present:

```
SIREN HISTORY

2026-02-18:
  sig_xxx (PRIMITIVE/BEACON) -> warranted -> wrn_aaa (acknowledged)
  sig_yyy (COGNITIVE/LESSON) -> dismissed (rationale: "addressed in v2 refactor")

2026-02-17:
  sig_zzz (COGNITIVE/TENSION) -> resolved
```

---

### `/siren conformation`

Snapshot the current system conformation — the total state at the latest tic boundary:

1. Compute physical tic count and latest entry:
   ```bash
   python3 -c "
   import json, glob
   entries = []
   for f in sorted(glob.glob('audit-logs/tics/*.jsonl')):
       for line in open(f):
           d = json.loads(line)
           if d.get('type') == 'tic':
               entries.append(d)
   print(f'{len(entries)}|{json.dumps(entries[-1]) if entries else \"{}\"}')"
   ```
   Parse the output: count before `|` is the physical tic count, JSON after `|` is the last tic entry for zone/timestamp metadata.
2. Read all signals from `audit-logs/signals/*.jsonl` — latest entry per ID, filter `status` in (`active`, `acknowledged`, `working`)
3. Read all warrants from `audit-logs/signals/*.jsonl` — latest entry per ID where `type: "warrant"`, filter `status` in (`active`, `acknowledged`)
4. Scan for pending CogPR flags using the zone scan rule:
   - Glob `**/CLAUDE.md` and `**/MEMORY.md` (not all .md files)
   - Also check `~/.claude/projects/*/memory/MEMORY.md`
   - Exclude paths matching `.ticignore` (default: vendor/, node_modules/,
     .git/, .claude/skills/)
   - Skip blocks with `status: "example"`
5. Read `.ticzone` for zone configuration
6. Compute rule fingerprints: read `CLAUDE.md` and `~/.claude/CLAUDE.md`, record file size and line count as change indicators
7. Create `audit-logs/conformations/` directory if absent
8. Write snapshot to `audit-logs/conformations/tic-<physical_count>.json`
   where `physical_count` is from the inline Python above, NOT any `tic_count_project` field from a JSONL entry:

```json
{
  "type": "conformation",
  "tic_count_physical": 1,
  "tic": "2026-02-25T03:33:00Z",
  "tic_zone": "my-project",
  "snapshot_at": "2026-02-25T04:00:00Z",
  "active_signals": [
    {"id": "sig_xxx", "kind": "BEACON", "band": "PRIMITIVE", "volume": 80, "status": "active", "subsystem": "ruvector"}
  ],
  "active_warrants": [
    {"id": "wrn_xxx", "band": "PRIMITIVE", "priority": 1, "minting_condition": "volume_threshold", "status": "active"}
  ],
  "pending_cogprs": [
    {"source": "CLAUDE.md:283", "lesson": "one-line summary", "band": "COGNITIVE", "subsystem": "cgg", "recommended_scopes": ["~/.claude/CLAUDE.md"]}
  ],
  "zone": {
    "name": "my-project",
    "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL", "PRESTIGE"],
    "muffling_per_hop": 5,
    "signal_governance": {
      "warrant_eligible_kinds": ["BEACON", "TENSION"],
      "decay_rate_per_tic": 2,
      "primitive_audibility_mode": "threshold_floor"
    }
  },
  "rules_in_force": {
    "site": {"file": "CLAUDE.md", "lines": 450, "bytes": 28000},
    "global": {"file": "~/.claude/CLAUDE.md", "lines": 120, "bytes": 8000}
  },
  "counts": {
    "active_signals": 1,
    "active_warrants": 0,
    "pending_cogprs": 3,
    "resolved_signals_since_last_tic": 1
  }
}
```

9. Report:

```
CONFORMATION at tic #1 (physical count)
Zone: my-project
Active signals: 1 | Active warrants: 0 | Pending CogPRs: 3
Rules: project CLAUDE.md (450 lines) | global CLAUDE.md (120 lines)
Snapshot written: audit-logs/conformations/tic-1.json
```

---

### `/siren conformation diff [tic_a] [tic_b]`

Diff two conformation snapshots:

1. Read `audit-logs/conformations/tic-<a>.json` and `audit-logs/conformations/tic-<b>.json`
   - If only one argument given, diff that tic against the latest snapshot
   - If no arguments, diff the two most recent snapshots
   - If a snapshot file is missing, report error
2. Compare each section:

**Signals:**
- New signals (in B but not A)
- Removed signals (in A but not B — resolved/dismissed)
- Changed signals (same ID, different volume/status)

**Warrants:**
- Minted (in B but not A)
- Dismissed (in A but not B)

**CogPRs:**
- New (in B but not A)
- Promoted (in A with status pending, absent in B — moved to rules)
- Rejected (in A with status pending, absent in B — removed)

**Rules:**
- Line count delta (indicates rule file was modified)

3. Report:

```
CONFORMATION DIFF: tic #1 -> tic #2

Signals:
  + sig_new_xxx (COGNITIVE/LESSON, volume 30) — NEW
  - sig_old_yyy (COGNITIVE/TENSION) — RESOLVED
  ~ sig_existing (volume 25->45)

Warrants:
  + wrn_aaa (P1, volume_threshold) — MINTED

CogPRs:
  + "New lesson about X" (CLAUDE.md:100) — NEW
  v "Old lesson about Y" — PROMOTED to ~/.claude/CLAUDE.md

Rules:
  ~ project CLAUDE.md: 430->450 lines (+20)
  = global CLAUDE.md: unchanged
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
- **NEVER** auto-acknowledge or auto-dismiss warrants — those require `/review` human gate
- **NEVER** use timestamps for state transition logic — tic count is the time authority
- Signal IDs must be unique — use timestamp + subsystem + hash
- Warrant minting is deterministic — same conditions always produce the same warrant
- Signals do not expire — conditions persist until resolved or dismissed
- Non-warrant-eligible signals (LESSON, OPPORTUNITY by default) cannot mint warrants via volume threshold
