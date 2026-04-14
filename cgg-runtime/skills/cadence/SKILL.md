---
name: cadence
description: Session epoch boundary — emits canonical tic, captures lessons, writes handoff. Default is downbeat; use "double-time" for emergency syncopate.
user-invocable: true
---

# /cadence

Unified session boundary command. Dispatches based on arguments:

- **`/cadence`** (no args) — full downbeat. Same as the former `/cadence-downbeat`.
- **`/cadence double-time`** — emergency syncopate. Minimal tic + handoff in <=5% context window. Same as the former `/cadence-syncopate`.

Parse the user's arguments after `/cadence` to determine the mode. Default (no args) = downbeat.

---

## Mode: Downbeat (default)

When the user invokes `/cadence` with no arguments (or explicitly says "downbeat"), execute the System Shutdown & Hygiene Sequence. All steps are sequential — do not queue them.

### Phase 1: ENG/DIRECT — Operational Writes (Steps 0-2)

All operational mutation happens here. These are the writes that MUST complete before the handoff.

#### Step 0: Reconcile Native Plan State
Locate the active plan file in `~/.claude/plans/`. Evaluate its status based on the spirit of the original goal. Explicitly mark it 100% 'Completed', 'Superseded', or leave it 'Active' only if the exact thread must resume.

#### Step 0.5: Emit Tic + Conformation + Mandate (unified)

**Primary path (MANDATORY when available):** Run `cadence-ops.py` — it handles tic emission, conformation snapshot, and mandate cascade in one deterministic invocation. This is the ONLY correct path for conformation writing. Do NOT write conformations inline or delegate to `/siren conformation` — LLM-approximated signal counts produce stale data (validated: tic-101 reported 2305 active signals instead of 0 because inline code counted raw JSONL lines without last-write-wins dedup).

```bash
# Resolve cadence-ops.py location
ZONE_ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
while [ "$ZONE_ROOT" != "/" ] && [ ! -f "$ZONE_ROOT/.ticzone" ]; do ZONE_ROOT=$(dirname "$ZONE_ROOT"); done

CADENCE_OPS=""
for candidate in \
  "$ZONE_ROOT/vendor/context-grapple-gun/cgg-runtime/scripts/cadence-ops.py" \
  "$ZONE_ROOT/canonical_developer/context-grapple-gun/cgg-runtime/scripts/cadence-ops.py" \
  "${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/cgg-runtime/scripts/cadence-ops.py}" \
  "$HOME/.claude/cgg-runtime/scripts/cadence-ops.py"; do
  [ -n "$candidate" ] && [ -f "$candidate" ] && CADENCE_OPS="$candidate" && break
done

# Run it (handles tic + conformation + mandate)
python3 "$CADENCE_OPS" --zone-root "$ZONE_ROOT" --mode downbeat
```

Parse the JSON output to extract:
- `result.tic.counter_after` — the new tic count
- `result.tic.timestamp` — the tic timestamp
- `result.conformation.summary` — signal/warrant/cogpr counts
- `result.mandate` — mandate status and due cycles

Report: `Tic #COUNTER_AFTER (physical) at TIMESTAMP`

**Fallback path (only if cadence-ops.py is not found):** Use the inline Python tic emission below, then call `/siren conformation` for the snapshot. This is inferior because `/siren conformation` relies on LLM signal counting.

<details>
<summary>Inline tic emission fallback (expand only if cadence-ops.py unavailable)</summary>

### Tic emission semantics

A tic event and a counted tic are **not the same thing**.

- **Emit**: write a tic event to the zone audit surface (always, for traceability)
- **Count**: advance canonical tic reality counters (only when not ignored)

Use this law:

- Default cadence runs emit **counted** tics
- Experimental / rehearsal / sandbox / explicitly ignored runs emit tics with `count_mode: "ignored"`
- Ignored tics are written for traceability but do **not** advance canonical counters

Canonical reality is determined by counted tic progression, not by timestamps.

#### Required fields on every tic event

| Field | Description |
|-------|-------------|
| `type` | Always `"tic"` |
| `tic` | ISO-8601 timestamp |
| `tic_zone` | Zone name only (never raw `.ticzone` JSON) |
| `cadence_position` | `"downbeat"` or `"syncopate"` |
| `count_mode` | `"counted"` or `"ignored"` |
| `count_reason` | Short reason string |
| `domain_counter_before` | Counter value before this event |
| `domain_counter_after` | Counter value after (same as before if ignored) |
| `global_counter_before` | Counter value before this event |
| `global_counter_after` | Counter value after (same as before if ignored) |

**Counting rule (SUBSTRATE INVARIANT):** The canonical tic count is the physical number of counted tic entries across all `$ZONE_ROOT/audit-logs/tics/*.jsonl` files — entries where `count_mode == "counted"`. Determined by JSON-parsing — never by grep, never by reading an embedded counter field.

```python
python3 - <<'PY'
import json, os, glob
from datetime import datetime, timezone
from pathlib import Path

ZONE_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
TIC_DIR = ZONE_ROOT / "audit-logs" / "tics"
TIC_DIR.mkdir(parents=True, exist_ok=True)

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
today = now[:10]

ticzone_path = ZONE_ROOT / ".ticzone"
zone_name = "canonical"
if ticzone_path.exists():
    try:
        zone_obj = json.loads(ticzone_path.read_text())
        zone_name = zone_obj.get("name", zone_name)
    except Exception:
        pass

def counted_tics():
    total = 0
    for f in glob.glob(str(TIC_DIR / "*.jsonl")):
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line: continue
                try: obj = json.loads(line)
                except json.JSONDecodeError: continue
                if obj.get("type") == "tic" and obj.get("count_mode", "counted") == "counted":
                    total += 1
    return total

before = counted_tics()
count_mode = "counted"
count_reason = "cadence"
after = before + 1 if count_mode == "counted" else before

event = {
    "type": "tic", "tic": now, "tic_zone": zone_name,
    "cadence_position": "downbeat", "count_mode": count_mode,
    "count_reason": count_reason,
    "domain_counter_before": before, "domain_counter_after": after,
    "global_counter_before": before, "global_counter_after": after
}

path = TIC_DIR / f"{today}.jsonl"
fd = os.open(str(path), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
try: os.write(fd, (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
finally: os.close(fd)

counter_path = Path.home() / ".claude" / "cgg-tic-counter.json"
counter_path.parent.mkdir(parents=True, exist_ok=True)
tmp = counter_path.with_suffix(".tmp")
tmp.write_text(json.dumps({"count": after, "last_tic": now}) + "\n", encoding="utf-8")
tmp.replace(counter_path)

print(f"Tic emitted at {now} [{count_mode}]")
print(f"Canonical count: {before} -> {after}")
PY
```

After inline tic emission, execute `/siren conformation` as a fallback conformation writer.

</details>

#### Step 1: Signal Manifold Hygiene (skip if cadence-ops.py ran)
If `cadence-ops.py` was used in Step 0.5, signal state is already captured in the conformation — skip `/siren tick`. Only execute `/siren tick` if the inline fallback was used.

#### Step 2: Extract Lessons (CogPRs)
Did we establish a new rule or optimize a workflow? If yes, capture it as a `<!-- --agnostic-candidate -->` block using the COGNITIVE band. Route based on truth-state (see write rule below).

Include birth context when available:
- `posture`: current session posture (e.g., "ENG/DIRECT", "OPS/META")
- `cwd_context`: working directory relative to project root
- `birth_tic`: the tic number from Step 0.5

These fields are optional. Omit if posture is not in use.

Write to the nearest governance file based on truth-state:
1. **Born truth** (new lesson, observation, CogPR candidate) → write to MEMORY.md
   - Check CWD for MEMORY.md — write there if found
   - Walk up parent directories toward project root
   - Fall back to auto-memory (`~/.claude/projects/*/memory/MEMORY.md`)
2. **In-force truth** (constitutional correction, rule amendment) → write to CLAUDE.md
   - Only when the lesson IS a law change, not when it might become one
3. **Housekeeping exception** — if the lesson corrects an already-local CLAUDE.md entry
   (e.g., fixing a methylated block, updating a line reference), write the correction
   in-place to that same CLAUDE.md

When writing to a subdir CLAUDE.md, ensure the project root CLAUDE.md
indexes it (add a reference in any existing "subdirectory guides" section).

#### Step 2.5: Routing Decision Batch Capture

Review the session's delegations. For each non-trivial delegation (anything beyond direct conversation), append a routing decision record to `audit-logs/routing/decisions.jsonl`. Include: pressure class, intake class, weight, mode selected, recipient(s), and reason. Mark outcome as null — backfill happens next session or at review.

Schema per entry:
```json
{
  "decision_id": "tic-{TIC}-seq-{N}",
  "tic": 134,
  "timestamp": "ISO-8601",
  "actor": "ent_homeskillet",
  "input": {
    "pressure_class": "endogenous | exogenous",
    "source_description": "one-liner",
    "intake_class": "map | harpoon | quiver | reject | unclassified",
    "weight": "light | medium | heavy"
  },
  "routing": {
    "mode": "direct | split | spec_swarm | envelope",
    "recipient_count": 1,
    "recipients": ["entity_names"],
    "envelope_id": "or null",
    "spec_ref": "path or null"
  },
  "context": {
    "session_tic": 134,
    "active_signals": 5,
    "pending_cprs": 0,
    "inbox_depth": 0,
    "reason": "one-liner: why this mode was selected"
  },
  "outcome": null
}
```

This is a 2-minute journaling step. If the session had zero delegations, skip. When routing decisions are captured, add to Next Actions: "Backfill routing decision outcomes from prior session (N decisions pending)."

### Phase 2: PLAN MODE — The Handoff (Steps 3-4)

#### Step 3: Enter Plan Mode
Use the `EnterPlanMode` tool to switch to Claude Code's native plan mode. This is mandatory and mechanical — call the tool, do not just declare the shift.

#### Step 4: Write the Handoff as the Plan
Generate a NEW native plan. The plan content IS the handoff — a **bridge surface** carrying session state between contexts, not authoring truth or constitutional record. This is the ONE AND ONLY place the handoff gets written. Claude Code auto-saves the plan to `~/.claude/plans/` when approved, and references it in the next session.

The plan is a **context grapple gun projection** — it carries two structurally distinct payloads across the session boundary:

1. **Governance State** (auto-captured) — tic, signals, conformations, mandate, queue status. This is the sidecar. It feeds hooks and governance cycles.
2. **Session Projection** (human-validated) — roadmap goals, production intent, creative direction. This is the grapple. It carries what the human actually wants to accomplish across N sessions.

The structural separation is load-bearing. Without it, governance chores (queue_refresh, signal_scan) and production goals (test the pipeline, build the adapter) render as a flat list — and governance chores win attention because they auto-trigger via hooks while production goals silently decay.

The plan must include:
- `<!-- cgg-handoff -->` block with handoff_id, project_dir, trigger_version, generated_at
- User Intent, Agent Interpretation, Interpretation Concerns
- Working State (citation-laden, file:line references)
- **Session Projection** (see below)
- Session Learning & ROI with Time Saved Estimates
- Friction (Signals): any new `<!-- --signal -->` blocks for unresolved technical debt
- **Governance Next Actions** (concrete, numbered — governance chores only). **Git cycle gate:** run `scripts/git-cycle.sh` before writing this section. If any repos are dirty, unpushed, or diverged, add "Resolve git cycle: [repo list]" as the FIRST governance next action. The pre-planmode hook also surfaces this, but the hook may fire before the session's final commits land — the handoff is the authoritative checkpoint.
- Conformation summary
- Cadence due markers (see below)
- `<!-- cgg-evaluate -->` trigger block at the very bottom — `pending_cprs_expected` must match the exact number of CogPRs from Step 2

#### Session Projection (mandatory section)

The Session Projection is the primary activation payload of the handoff. It answers: "What is the human trying to accomplish that spans sessions?" This section is NOT auto-generated from governance state — it requires session context awareness and human validation.

```markdown
## Session Projection

### Active Roadmap Goals
<!-- Goals that span multiple sessions. Carry forward until explicitly completed or deferred. -->
1. [GOAL] — status, last touched tic, next concrete step
2. [GOAL] — status, last touched tic, next concrete step

### Production Next Actions
<!-- The actual work. These are NOT governance chores. -->
1. [ACTION] — concrete, scoped, ready to execute
2. [ACTION] — concrete, scoped, ready to execute

### Deferred Goals
<!-- Goals intentionally parked with reason and re-evaluation tic. -->
- [GOAL] — reason, re-eval at tic N
```

**Authoring rules:**
- Active Roadmap Goals persist across handoffs until explicitly completed or deferred. They are NOT dropped when a session ends without touching them.
- Production Next Actions are the session's real work queue. Governance chores (mandate consumption, signal scans) go in the separate Governance Next Actions section.
- Deferred Goals carry a re-evaluation tic. When `current_tic >= re_eval_tic`, the goal resurfaces to Active.
- The projection section is positioned BEFORE governance sections in the handoff to establish priority — the grapple fires first, the sidecar follows.
- When the prior handoff included a Session Projection, carry forward its Active Roadmap Goals verbatim unless status changed. Do not silently drop goals.

#### Mogul Mandate Cascade

After computing due markers (below), write a Mogul activation mandate for any newly-due cycles. This is the primary clock trigger for governance maintenance — /cadence computes what became due, writes the mandate, and lets the next session's activation fabric consume it.

**Mandate operator semantics:** Due cycles in `run_now` are not merely report tasks. The mandate authorizes Mogul to materially advance the governance pipeline within mandate bounds — decomposing cycles into subordinate work, spawning bounded subagents, advancing enrichment when evidence supports it, and synthesizing results. /cadence remains the clock; Mogul is the operator.

**Do NOT spawn Mogul during /cadence.** /cadence runs during session flush/exit. Spawning heavy maintenance here risks context exhaustion. The mandate is consumed by SessionStart or first-prompt in the next session.

**Do NOT run governance maintenance inline.** /cadence is the clock, not the worker.

Steps:
1. Compute which cycles are newly due at CURRENT_TIC (see due marker formulas below)
2. Build `cycle_request.run_now` array from due cycles
3. **Merge-before-write** (non-lossy mandate lifecycle):
   - If `mandate-write.py` is available (via resolve_script), call it — it handles merge semantics automatically
   - If not available, apply merge inline:
     - Read existing mandate at `$ZONE_ROOT/audit-logs/mogul/mandates/current.json`
     - If existing status is `pending` or `running`: **merge** — absorb existing `run_now` cycles, record old `mandate_id` in `merged_from`
     - If existing status is `consumed`, `failed`, or `superseded`: safe to write fresh, record old `mandate_id` in `supersedes`
     - If no existing mandate: write fresh
4. Write mandate to `$ZONE_ROOT/audit-logs/mogul/mandates/current.json`:
   ```json
   {
     "mandate_id": "tic-CURRENT_TIC-YYYYMMDDTHHMMSS",
     "status": "pending",
     "supersedes": [],
     "merged_from": [],
     "actor": {"office": "mogul", "embodiment": "cgg_runtime"},
     "trigger": {"kind": "cadence", "source_ref": ".claude/skills/cadence/SKILL.md"},
     "tic_context": {
       "current_tic": CURRENT_TIC,
       "review_due_tic": ...,
       "memory_mining_due_tic": ...,
       "ladder_audit_due_tic": ...,
       "deep_audit_due_tic": ...
     },
     "cycle_request": {
       "run_now": ["queue_refresh", ...],
       "reason": "Tic CURRENT_TIC — cycles due: ..."
     },
     "conformation_ref": "<path to latest conformation or null>",
     "mode": {"blocking_to_orchestrator": false, "allow_subdelegation": true},
     "runtime_truth": {"canonical_vs_installed_verified": false},
     "created_at": "ISO-8601 now",
     "started_at": null,
     "completed_at": null,
     "error": null
   }
   ```
5. Append the mandate to `$ZONE_ROOT/audit-logs/mogul/mandates/history/YYYY-MM-DD.jsonl`
6. Create the directories if they don't exist (`audit-logs/mogul/mandates/history/`)
7. Note in the handoff: "Mogul mandate written for cycles: [list]"

#### Cadence Due Markers

Include a `## Cadence Due` section in the handoff with tic-sum-derived operational due markers. These are not hard deadlines — they are audit cadence hints tied to the current tic count (`CURRENT_TIC` from Step 0.5):

```markdown
## Cadence Due

- **review_due_tic**: <CURRENT_TIC + 1> (queue + signal scan)
- **memory_mining_due_tic**: <next multiple of 3 after CURRENT_TIC>
- **ladder_audit_due_tic**: <next multiple of 5 after CURRENT_TIC>
- **deep_audit_due_tic**: <next multiple of 8 after CURRENT_TIC>
```

Compute each marker deterministically:
- `review_due_tic = current_tic + 1` (every tic)
- `memory_mining_due_tic = current_tic + (3 - current_tic % 3)` if `current_tic % 3 != 0`, else `current_tic + 3`
- `ladder_audit_due_tic = current_tic + (5 - current_tic % 5)` if `current_tic % 5 != 0`, else `current_tic + 5`
- `deep_audit_due_tic = current_tic + (8 - current_tic % 8)` if `current_tic % 8 != 0`, else `current_tic + 8`

These markers make governance pressure visible and auditable. SessionStart hooks may reference them to determine which audit cycles are due.

**Deep audit due marker**: When `deep_audit_due_tic` equals the current tic, Mogul should be delegated a deep audit cycle: multi-rung ladder coherence scan (via ladder-auditor), manifestation pressure scan (via manifestation-tracker), sibling duplication check, overbroad abstraction detection, demotion pressure review. The deep audit produces an execution artifact packet and stages review material if intervention is needed.

The user sees this plan in Claude Code's native plan UI with approve/edit/reject/clear options. When approved and context cleared, the plan persists and becomes the active state for the next session.

The session does NOT end until the human acts on the plan. The human may:
- **Approve + clear context** — plan persists, next session picks it up via `implement_plan`
- **Edit** — modify the handoff before approving
- **Continue working** — exit plan mode and keep going

The ripple-assessor runs HEADLESS on next session start (background, non-blocking via cgg-gate.sh hook). It writes proposals to `~/.claude/grapple-proposals/latest.md` — keeping its ~10k tokens OUT of the runtime context window. The completion notification is informational only ('proposals ready for /review when ready') — it does NOT demand immediate attention. Proposals are consumed when the user invokes `/review`, not before.

---

## Handoff Consumption Protocol

When a new session receives a handoff plan (via `implement_plan` or plan-mode exit), the plan carries two distinct payloads: the **Session Projection** (what the human wants to accomplish) and the **Governance State** (what the system needs to maintain). The projection is the primary work queue; governance is the sidecar.

### Session-start ordering

1. **Surface the Session Projection** from the handoff as the primary work context. Active Roadmap Goals and Production Next Actions are the session's real agenda. Present them first and visibly — not buried in governance receipts.
2. **Consume the Mogul mandate** (mechanical cycles script-routed, deliberative cycles team-routed). This is governance overhead — handle it compactly, do not let it displace the projection.
3. **Proceed with the user's intent.** If the user's message is "implement the plan," the Production Next Actions ARE the plan. Execute them in priority order, checking each against current state before acting (items may have been completed in prior sessions). Governance Next Actions execute in background or after production work unless explicitly prioritized.

### Session Projection carry-forward rules

- **Active Roadmap Goals** persist across handoffs by default. They are only dropped when explicitly completed, explicitly deferred (with re-eval tic), or explicitly superseded.
- **Production Next Actions** carry forward if incomplete. Completed items are marked done; new items from the current session append after carried items.
- **Deferred Goals** resurface to Active when `current_tic >= re_eval_tic`.
- **Governance Next Actions** do NOT carry forward — they are recomputed each cadence from mandate state and due markers. Stale governance chores from prior handoffs are dropped.

### Priority inversion guard

If governance chores are consuming session attention at the expense of production goals for 2+ consecutive sessions, that IS a signal — the governance overhead is displacing the work the system exists to enable. Surface it as a friction signal in the handoff. The substrate exists to absorb coordination so participants experience freedom without losing coherence — if governance is the bottleneck, the substrate is failing.

---

## Mode: Double-Time (emergency syncopate)

When the user invokes `/cadence double-time`, execute the emergency session boundary. Produces a valid handoff in minimal turns. Tic + conformation + plan (no assessor, no mandate).

### Phase 1: ENG/DIRECT — Operational Writes (Steps 1-2)

All operational mutation happens here. These are the writes that MUST complete before the handoff.

#### Step 1: Raise Autocompact Ceiling

If `CLAUDE_ENV_FILE` is available, temporarily push the autocompact boundary higher to prevent compaction mid-syncopate:

```
echo 'export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=95' >> "$CLAUDE_ENV_FILE"
```

This buys headroom. The next session's SessionStart hook will reset it to 80%.

#### Step 2: Emit Tic + Conformation (lightweight)

**Primary path (MANDATORY when available):** Run `cadence-ops.py --mode syncopate` — same script as downbeat but with syncopate mode. Handles tic + conformation in one deterministic call (mandate is skipped by default for syncopate).

```bash
python3 "$CADENCE_OPS" --zone-root "$ZONE_ROOT" --mode syncopate
```

Use the same `$CADENCE_OPS` resolution from the downbeat Step 0.5 section.

**Fallback:** If `cadence-ops.py` is unavailable, use the inline Python from the downbeat fallback section with `cadence_position: "syncopate"` and `count_reason: "emergency_syncopate"`.

### Phase 2: PLAN MODE — The Handoff (Steps 3-4)

#### Step 3: Enter Plan Mode

Use the `EnterPlanMode` tool to switch to Claude Code's native plan mode. This is mandatory and mechanical — call the tool, do not just declare the shift.

#### Step 4: Write the Handoff as the Plan

Generate a NEW native plan. The plan content IS the handoff — a **bridge surface** carrying session state between contexts, not authoring truth or constitutional record. This is the ONE AND ONLY place the handoff gets written. Claude Code auto-saves the plan to `~/.claude/plans/` when approved, and references it in the next session.

Keep it COMPACT (each section 5 lines max):

```markdown
# [YYYY-MM-DDTHH:MM] syncopate-<topic>

<!-- cgg-handoff
  handoff_id: "YYYY-MM-DDTHH:MM:SSZ-syncopate-<topic>"
  project_dir: "/absolute/path/to/project"
  trigger_version: 1
  generated_at: "ISO-8601 timestamp"
-->

## Status: Active

## Working State (compact)
<What was being worked on — files touched, decisions made, blockers hit. Max 5 lines.>

## Session Projection (compact)
<Active roadmap goals + production next actions. Max 5 items total. Carry forward from prior handoff.>

## Governance Next Actions
<Governance chores only. Max 3 items.>

## Carried Signals
<List active signal IDs + volumes from memory. If unknown, write "See /siren status".>
```

Do NOT include: User Intent, Agent Interpretation, Interpretation Concerns, Lessons, Friction, Verification, or cgg-evaluate trigger blocks. Those are downbeat luxuries.

The user sees this plan in Claude Code's native plan UI with approve/edit/reject/clear options. When approved and context cleared, the plan persists and becomes the active state for the next session.

The session does NOT end until the human acts on the plan. The human may:
- **Approve + clear context** — plan persists, next session picks it up via `implement_plan`
- **Edit** — modify the handoff before approving
- **Continue working** — exit plan mode and keep going

This is the constitutional gate — no context clear without human sign-off via the native plan UI.

### What Double-Time Skips (and why)

| Skipped | Why | Recovery path |
|---------|-----|---------------|
| Signal tick (`/siren tick`) | Too expensive at 5% | Next downbeat or manual `/siren tick` |
| Conformation snapshot | Depends on tick | Next downbeat |
| CogPR extraction (Step 2 of downbeat) | Requires reading full context | Lessons stay inline, picked up next `/review` |
| Ripple assessor | Runs headless on next session start | cgg-gate.sh triggers it |

The double-time is a valid handoff — the next session gets Next Actions via the plan and can run a full downbeat when context is fresh.
