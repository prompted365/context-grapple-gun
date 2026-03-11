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

#### Step 0.5: Emit Tic

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

Every emitted tic event must include:

| Field | Description |
|-------|-------------|
| `type` | Always `"tic"` |
| `tic` | ISO-8601 timestamp |
| `tic_zone` | Zone name only (never raw `.ticzone` JSON) |
| `cadence_position` | `"downbeat"` or `"syncopate"` |
| `count_mode` | `"counted"` or `"ignored"` |
| `count_reason` | Short reason string (e.g. `"normal"`, `"experimental_arena_closeout"`, `"rehearsal"`) |
| `domain_counter_before` | Counter value before this event |
| `domain_counter_after` | Counter value after (same as before if ignored) |
| `global_counter_before` | Counter value before this event |
| `global_counter_after` | Counter value after (same as before if ignored) |

#### Important clarification

An ignored tic is still a tic event. It answers "did something happen?", "when?", "under what mode?" — but it does **not** answer "did canonical tic reality advance?" Only counted tics answer that.

#### Counting rule

- If `count_mode == "counted"`: increment both counters (`after = before + 1`)
- If `count_mode == "ignored"`: keep counters unchanged (`after = before`), still append the tic event

**Counting rule (SUBSTRATE INVARIANT):** The canonical tic count is the physical number of counted tic entries across all `$ZONE_ROOT/audit-logs/tics/*.jsonl` files — entries where `count_mode == "counted"` (or entries without `count_mode` for backwards compatibility with pre-schema tics). Determined by JSON-parsing — never by grep, never by reading an embedded counter field from a previous entry. The global counter file (`~/.claude/cgg-tic-counter.json`) is a cached mirror of this physical truth, not an independent state machine.

**Zone root anchoring (SUBSTRATE INVARIANT):** All audit-store paths MUST resolve from the zone root (the directory containing `.ticzone`), never from cwd. Determine the zone root first:
```bash
ZONE_ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
# Walk up to find .ticzone if CLAUDE_PROJECT_DIR is not set
while [ "$ZONE_ROOT" != "/" ] && [ ! -f "$ZONE_ROOT/.ticzone" ]; do ZONE_ROOT=$(dirname "$ZONE_ROOT"); done
```

#### Ticignored mode awareness

When the current operation is marked experimental, rehearsal, dry-run, sandboxed, or otherwise excluded from canonical progression, emit `count_mode: "ignored"` and do **not** advance the counted tic counters. This applies even if the event is operationally real in wall-clock time.

Timestamps are observational; counted tic progression is canonical.

#### Atomic tic append

Never build tic JSON by interpolating raw `.ticzone` file contents directly into shell `printf`. Instead: derive the zone **name** only, serialize one JSON object, append it with a single `O_APPEND` write.

**Script path**: If `cadence-ops.py` is available (via `resolve_script`), call it instead of the inline Python below. It handles tic emission, conformation, and mandate in one invocation. The inline Python is the fallback when the script is unavailable.

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
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "tic" and obj.get("count_mode", "counted") == "counted":
                    total += 1
    return total

before = counted_tics()

# Set this from cadence mode resolution:
# "counted" for normal downbeat/syncopate
# "ignored" for experimental/rehearsal/sandbox
count_mode = "counted"
count_reason = "cadence"

after = before + 1 if count_mode == "counted" else before

event = {
    "type": "tic",
    "tic": now,
    "tic_zone": zone_name,
    "cadence_position": "downbeat",
    "count_mode": count_mode,
    "count_reason": count_reason,
    "domain_counter_before": before,
    "domain_counter_after": after,
    "global_counter_before": before,
    "global_counter_after": after
}

path = TIC_DIR / f"{today}.jsonl"
fd = os.open(str(path), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
try:
    os.write(fd, (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
finally:
    os.close(fd)

counter_path = Path.home() / ".claude" / "cgg-tic-counter.json"
counter_path.parent.mkdir(parents=True, exist_ok=True)
tmp = counter_path.with_suffix(".tmp")
tmp.write_text(json.dumps({"count": after, "last_tic": now}) + "\n", encoding="utf-8")
tmp.replace(counter_path)

print(f"Tic emitted at {now} [{count_mode}]")
print(f"Canonical count: {before} -> {after}")
PY
```

Report:
- Counted: `Tic #AFTER (physical) at YYYY-MM-DDTHH:MM:SSZ`
- Ignored: `Tic emitted at YYYY-MM-DDTHH:MM:SSZ [ignored — <reason>] (canonical count unchanged at #BEFORE)`

#### Step 1: Signal Manifold Hygiene
Execute `/siren tick`. Ensure volume has accrued, decay has been applied, and thresholds are checked.

#### Step 1.5: Snapshot Conformation
Execute `/siren conformation` to capture the system's total state at this tic boundary.

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

### Phase 2: PLAN MODE — The Handoff (Steps 3-4)

#### Step 3: Enter Plan Mode
Use the `EnterPlanMode` tool to switch to Claude Code's native plan mode. This is mandatory and mechanical — call the tool, do not just declare the shift.

#### Step 4: Write the Handoff as the Plan
Generate a NEW native plan. The plan content IS the handoff — a **bridge surface** carrying session state between contexts, not authoring truth or constitutional record. This is the ONE AND ONLY place the handoff gets written. Claude Code auto-saves the plan to `~/.claude/plans/` when approved, and references it in the next session.

The plan must include:
- `<!-- cgg-handoff -->` block with handoff_id, project_dir, trigger_version, generated_at
- User Intent, Agent Interpretation, Interpretation Concerns
- Working State (citation-laden, file:line references)
- Session Learning & ROI with Time Saved Estimates
- Friction (Signals): any new `<!-- --signal -->` blocks for unresolved technical debt
- Next Actions (concrete, numbered)
- Conformation summary
- Cadence due markers (see below)
- `<!-- cgg-evaluate -->` trigger block at the very bottom — `pending_cprs_expected` must match the exact number of CogPRs from Step 2

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

#### Step 2: Emit Tic (lightweight)

**Script path**: If `cadence-ops.py` is available (via `resolve_script`), call it instead of the inline Python below. It handles tic emission, conformation, and mandate in one invocation. The inline Python is the fallback when the script is unavailable.

Same emit/count semantics as downbeat (see "Tic emission semantics" above). Resolve zone root, count physical tics, determine count_mode, append atomically.

Use the same atomic append pattern from Step 0.5, with these differences:
- `cadence_position`: `"syncopate"` (not `"downbeat"`)
- `count_mode`: `"counted"` for normal syncopate, `"ignored"` for experimental/rehearsal/sandbox closeout
- `count_reason`: e.g. `"emergency_syncopate"` or `"experimental_arena_closeout"`

The python3 script from Step 0.5 applies identically — just change `cadence_position`, `count_mode`, and `count_reason` values.

Note: `cadence_position` is `"syncopate"`, not `"downbeat"`. This distinguishes emergency exits from planned epoch boundaries.

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

## Next Actions
<Concrete next steps. Max 5 items.>

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
