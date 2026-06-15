---
name: cadence
description: |
  Session epoch boundary event — emits canonical tic, captures lessons, writes handoff.

  CENTROID:
  session epoch boundary event

  IS:
  - the ONE place the handoff is written; the clock of the governance system

  IS NOT:
    collapse_zones:
      - memory write
      - signal emitter
      - CogPR extractor
      - Mogul spawner
      - inline governance mutation
    sibling_overlaps:
      - /review worker
      - /siren ticker
      - chore executor

  WHEN:
  - once per tic at session end
  - on mid-session epoch boundaries when posture shifts materially

  NOT WHEN:
  - during chores (chores are appetizer, real work happens alongside)
  - after single-step edits
  - when the active plan already covers the thread

  RELATES TO:
  - /review (governance judgment — not a /review worker; /cadence is the clock, /review is the judge)
  - /siren (signal ops — not a /siren ticker; /cadence writes, /siren classifies)
  - Mogul mandate (cadence writes, Mogul consumes)

  ARGS:
    stance: dispatch
    off_envelope: ask
    # off_envelope rationale: /cadence is load-bearing; an undeclared arg may indicate
    # a caller who is confused about skill identity — ask prevents silent misfires.
    core_dispatch_rays:
      - ""           → downbeat (full session hygiene)
      - "double-time" → syncopate (≤5% context emergency variant)
    secondary_modulation_axes:
      - detail: normal | high
      - emphasis: governance | production | projection
user-invocable: true
disallowed-tools:
  - Agent
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

Parse the JSON output to extract (keys are at the **top level** of the JSON object — there is no `result` wrapper):
- `tic.counter_after` — the new tic count
- `tic.timestamp` — the tic timestamp
- `tic.counter_before` — the prior tic count (work_tic for handoff title)
- `conformation.summary` — signal/warrant/cogpr counts
- `mandate` — mandate status and due cycles
- `cockpit_intent` — T2b I-B emission receipt: `{emitted, intent_id, reason}` (or `{emitted: false, error}` on fail-soft failure; never blocks cadence)

**Anti-pattern (do not write):** `data.get('result', {}).get('tic', {})` — cadence-ops emits `tic`, `conformation`, and `mandate` as top-level keys, not nested under `result`. A parser that walks `result.*` returns `None` for every field; re-invoking cadence-ops to "retry" on the None values emits a phantom tic on top of the legitimate one. Use `data['tic']['counter_after']` etc. directly. (Inscribed tic 266 post phantom-tic incident; refines CGG "Subagent Delegation — Schema Contracts" KI.)

**Cockpit-intent emission (T2b I-B, tic 267).** `cadence-ops.py` step 4 emits a `cockpit.intent` envelope with `intent_class: observe` after the tic + conformation + mandate writes. Every counted /cadence produces an explicit declared-state envelope in addition to the conformation snapshot — composes with federation KI *Declared operational state must persist to a governed audit surface*. The emission is fail-soft: import or POST errors land in `result["cockpit_intent"]` but never block cadence output. See `audit-logs/governance/cockpit-intent-t2b-invocation-discipline-spec-tic264.md` §I-B. Posture is sourced from the `--posture` arg (or inferred from environment); mode defaults to `LITE` for non-interactive cadence emissions. Emission appends to `audit-logs/cockpit/intents/YYYY-MM-DD.jsonl` via the Python emitter library (`cgg-runtime/scripts/lib/cockpit_intent_emit.py`) which writes byte-shape-parity rows with the T2a vite POST endpoint.

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

**Step 3a — Read the active plan file FIRST (Look-First gate, mandatory).**
Before invoking `EnterPlanMode`, locate the most-recent file in `~/.claude/plans/` (by mtime) and **Read it via the Read tool**. The Claude Code plan-write surface (`Updated plan` / native plan UI write) is hard-gated by the harness: it refuses to update a plan file unless that file has been Read in the current session. Globbing, `ls`, or referring to it from prior context does not satisfy the gate — only an explicit Read tool invocation does. Skipping this step produces a `File has not been read yet. Read it first before writing to it.` error mid-write, costing the session a retry and a stalled plan emission. The Read also feeds Discernment-at-Penning Discipline (below) — same act, two purposes.

```bash
# Locate by mtime
ACTIVE_PLAN=$(ls -t ~/.claude/plans/*.md 2>/dev/null | head -1)
echo "Active plan file: $ACTIVE_PLAN"
# Then Read tool: Read(file_path=$ACTIVE_PLAN)
```

**Step 3b — Invoke EnterPlanMode.**
Use the `EnterPlanMode` tool to switch to Claude Code's native plan mode. This is mandatory and mechanical — call the tool, do not just declare the shift.

#### Step 4: Write the Handoff as the Plan
Generate a NEW native plan. The plan content IS the handoff — a **bridge surface** carrying session state between contexts, not authoring truth or constitutional record. This is the ONE AND ONLY place the handoff gets written. Claude Code auto-saves the plan to `~/.claude/plans/` when approved, and references it in the next session.

##### Handoff Title Format: work-tic vs entry-tic (mandatory)

A close handoff names TWO tics, not one: the tic the session **worked under** and the tic emitted by /cadence for the **next session's entry**. Naming only one collapses the distinction and propagates off-kilter framing into future sessions.

**Cadence tic semantics:**
- Session opens at `current_tic = N` (just-emitted by prior session's /cadence).
- Session WORKS at tic N throughout (all activity happens at tic N).
- Session's /cadence at close emits tic N → N+1; emission is the close marker.
- Next session opens at `current_tic = N+1`.

**Required title format:**

```
tic{work_tic}-close-for-tic{entry_tic}-entry
```

Where:
- `work_tic` = the tic the session actually worked under = `counter_before` from cadence-ops output (or `current_tic` from the system reminder at session open).
- `entry_tic` = the tic emitted by this /cadence for the next session = `counter_after` from cadence-ops output.

Both must appear explicitly. Both are derivable from cadence-ops.py's top-level JSON output (`tic.counter_before` and `tic.counter_after`) — read them rather than inferring from context. (No `result.` prefix; see Step 0.5 anti-pattern note.)

**Forbidden anti-pattern:**

Titles like `tic{emitted_tic}-close` alone (e.g., `tic264-close` immediately after emitting tic 264). This conflates emission-tic with work-tic. Downstream readers — next session's framing, /review docket attribution, audit-log narration, conformation references — all inherit the title's tic number as the canonical work-tic. Mis-labeling silently shifts the federation's perception of when work happened by one tic, which compounds across review cycles.

**Verification at next /cadence (Architect-locked falsification test):**
- ✓ Correct if the next handoff title says `tic{N}-close-for-tic{N+1}-entry` (where N is the work-tic).
- ✗ Bug recurrence if the next handoff title says `tic{N+1}-close` alone (using the emitted tic as the headline tic).

<!-- landed-from cpr_tic_framing_convention_off_kilter_work_tic_vs_emission_tic_tic262 (tic 263 birth, /review at next-session pending). Architect-locked verbatim convention quoted at handoff body; cross-tic n≥3 framing drift evidence across tics 261-263. Runtime parity patch landed under Governance Tool Urgency Triage (code/template-wrong, doctrine incomplete) per handoff Production Next Actions #6. Band: COGNITIVE. Domain rung: CGG. Promotion adjudication: pending /review. -->

##### C47 Generation Suffix Convention for Orchestrator State Entries

Any State-of-the-Federation publication or orchestrator-voice state entry (handoff signature, ReBru block author line, orchestrator-authored bench-packet annotation, inscription signature) must carry a two-fact signature naming **both** load-bearing identities:

1. **Durable entity-role** — the orchestrator's stable federation identity (`ent_homeskillet`, `SkySkillet`, or whichever ent-id the orchestrator is acting under).
2. **Model-of-record at writing time** — the generation suffix encoding the Claude model class that authored the entry (`c47` = Claude Opus 4.7; `c46` = Claude Opus 4.6; `c45` = Claude Opus 4.5; future models extend the suffix forward).

**Convention example**: `ent_homeskillet-c47` or `SkySkillet-c47`. Both halves are mandatory: entity-role alone loses model provenance; model alone loses orchestrator identity.

**Why both halves**: orchestrator state entries are read across many sessions and many model generations. The entity-role tells future readers which orchestrator instance authored the entry; the model suffix tells them which generation produced it (decisive when interpreting voice, scope assumptions, or known model-class behavioral biases). A signature carrying only one fact silently strips half the load-bearing provenance.

**Where it appears**: handoff signatures (footer or signature block), orchestrator-voice ReBru block authors, State-of-the-Federation publication signature lines, any inscription where "who wrote this and on which model" is load-bearing for later interpretation.

<!-- landed-from cpr_c47_generation_suffix_convention_for_orchestrator_state_entries_tic274 (PROMOTE-SPEC at /review tic 278; doctrine inscribed at canonical_developer/context-grapple-gun/CLAUDE.md; skill body extension owed at tic 280 per Verdict-Shape KI). Band: COGNITIVE. Domain rung: CGG. -->

##### ARGUMENTS as Session Projection Steering Surface

The Architect uses the `/cadence` ARGUMENTS string as a **forward-projection steering surface**, not just a session-end hygiene step. The ARGUMENTS string carries: (1) what should be prioritized at the next session start (e.g., "Phase α launch + blocking-β decision presentation"), (2) what authoring direction to apply (e.g., "extend dial-based config pattern from landmass to physics + world"), (3) what the rationalization should foreground (e.g., "recommended-and-why + post-implementation configurability"), and (4) implicit acknowledgment of which prior frame has converged.

**Handoff authoring discipline**: when the cadence is invoked with non-empty ARGUMENTS, the handoff author must **metabolize** the ARGUMENTS into the Session Projection section — not paraphrase them as Working State, not drop them into a flat list. Working State captures what the session *did*; Session Projection captures what the next session *should aim for*. ARGUMENTS belong in Session Projection.

This is the cadence skill functioning as an Architect-side projection-steering mechanism, not just a session-end emission. The handoff inherits the Architect's evolving intent through ARGUMENTS rather than waiting for the next session to surface it from cold context.

<!-- promoted from cpr_cadence_arguments_as_session_projection_steering_tic202 (tic 202→246, /review Pass 3a). Cross-tic exercised across tics 202+. Routed to cadence/SKILL.md per recommended_scopes. Band: COGNITIVE. Domain rung: CGG. -->

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

#### Discernment-at-Penning Discipline (mandatory; lowest-cost moment)

The carry-forward rules above are not a passive copy — they require active discernment AT THE MOMENT OF PENNING THE NEW HANDOFF. This step has the lowest cost and the highest accuracy: the prior session's completion state is in current context. Deferring it makes the next session re-derive completion state from git log + audit logs, which is multi-x more expensive and error-prone.

The discipline:

1. **Read the prior plan file** (whatever its current name in `~/.claude/plans/`). It is the source-of-truth for what was carried into this session. If multiple plan files exist, take the most recent by mtime.

2. **For each Active Roadmap Goal, Production Next Action, and Deferred Goal in the prior plan**, assess current completion state against this session's actual work:
   - Did this session complete it? → mark `Completed` in this handoff (either drop from Active or move to a brief acknowledgment in Session Learning).
   - Did this session advance it but not finish? → carry forward as `Active` with updated "last touched tic" and "next concrete step" reflecting the new state.
   - Did this session render it obsolete or superseded by new work? → mark `Superseded` with a one-line pointer to the superseding item.
   - Did this session leave it untouched and conditions still hold? → carry forward unchanged.
   - Did this session leave it untouched but conditions changed? → either re-scope (rewrite the next step) or move to Deferred (with reason and re-eval tic).

3. **Carry forward with status updated explicitly.** Every prior item must appear in one of: Active (rewritten or unchanged), Completed (with brief acknowledgment), Deferred (with reason + re-eval tic), Superseded (with pointer). NEVER silently drop. NEVER silently duplicate (a goal cannot appear in both Active and Deferred — pick one).

4. **The discernment cost is paid once, NOW.** If you defer it, the next session pays it as re-derivation: walking git log since the prior handoff's `generated_at`, reading audit logs, opening files to check state. That re-derivation costs significantly more than doing it now while the session's work is still in active context. The substrate exists to absorb coordination so participants experience freedom without losing coherence — silently dropping items shifts coordination cost forward in time, where it compounds.

The discipline is already practiced naturally by attentive writers. Naming it explicitly prevents drift when a future session has a less-attentive writer or when context pressure makes shortcuts attractive.

#### Long-Form Artifact Authoring Discipline (paired in-session + headless analytical pass)

For long-form analytical or autobiographical artifacts (state-of-the-federation reports, autobiographies, multi-tic retrospectives), pairing **direct in-session authoring** with a **headless `claude -p` analytical pass** produces measurably better output than either alone.

- The in-session author operates with continuity of voice and active session memory.
- The headless pass operates on fresh context with structured analytical instructions and surfaces quantified observations the direct draft can miss (manifold counts, retrospective deltas, regime arcs).
- Companion artifacts (analytical sibling alongside narrative voice) should be committed as siblings rather than absorbed monolithically — preserving both lenses.

Promoted from `cpr_headless_claude_p_as_analytical_co_author_tic173` (tic 173 → tic 188 review). Source: tic 173 insights-report companion to state-of-federation autobiography. Apply when a deliverable spans multiple tics or requires both narrative coherence and quantitative scope. Band: COGNITIVE.

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

#### Cross-Cadence Rail Manufacturing (optional)

When the next session needs a hot-and-ready swarm at SessionStart — i.e., the closing tic anticipates a multi-lane parallel execution wave in the next tic — the prior session's /cadence is the lowest-cost moment to **manufacture the rails** the next session will consume. The pattern decouples discovery (this tic, parallelizable, lead-supervised) from execution (next tic, hook-kicked-off, dependency-DAG-ordered) across the cadence boundary.

This step is **optional**. Invoke only when the next-session work surface is large enough that cold-start RTCH inside the next session would saturate context before parallel execution begins. For routine tic boundaries, skip this step entirely — manufacturing rails for a session that does not need them is overhead.

**Two coupled primitives** (full doctrine: CGG_CLAUDE.md § *Cross-Cadence-Rails + Inbox-Marker-Dependency-Satisfaction Primitive*):

1. **Cross-Cadence-Rails** — dispatch parallel `/tactical-hydration` lanes during the current /cadence, terminate each with `/consolidate`, and write the harvested packets to a stable rails directory (`audit-logs/swarm-rails/tic{entry_tic}/`) the next session will read at SessionStart. Rail packets carry RTCH selected_surfaces, slice baskets, dependency declarations, and risk maps authored while context is hot — the next session reads the rails, never re-derives.

2. **Inbox-Marker-Dependency-Satisfaction** — a DAG node structure in the next session's inbox marker (e.g., `audit-logs/agent-mailboxes/ent_homeskillet/inbound/swarm-tic{entry_tic}/`) declaring `dependencies: [rail-T1, rail-T2, …]` where each dependency is a `status: complete` signal written by the corresponding rail's `/consolidate` step. The next session's hook-derived dispatcher reads the DAG and fires only when all declared dependencies are satisfied — converting sequential guesswork into governed dependency-ordered parallel execution.

**Authoring sequence at /cadence close** (when invoked):

1. Identify the next-session execution lanes that need pre-hydrated context (typically 3-6 lanes; if fewer, rails overhead exceeds benefit).
2. For each lane, spawn a parallel `/tactical-hydration` subagent scoped to the lane's surfaces. Each lane is independent; spawn in parallel.
3. Each subagent terminates with `/consolidate` writing a rail packet to `audit-logs/swarm-rails/tic{entry_tic}/rail-{lane-id}-{lane-name}.md`.
4. Write the inbox marker for the next session at `audit-logs/agent-mailboxes/ent_homeskillet/inbound/swarm-tic{entry_tic}/` with `dependencies:` listing each rail-lane-id and `consumer:` naming the dispatch hook.
5. Each completed rail emits a `status: complete` marker (`audit-logs/swarm-rails/tic{entry_tic}/rail-{lane-id}.marker`).
6. Reference the rails directory in the handoff (Session Projection or Production Next Actions section): "Rails manufactured at `audit-logs/swarm-rails/tic{entry_tic}/`; next session SessionStart dispatcher consumes via inbox-marker DAG."

**Cross-reference**: this pattern is the cadence-side of the cross-cadence rails primitive. The swarm-side (next session's consumption of the rails) is documented in `cgg-runtime/skills/swarm/SKILL.md` under the **Cross-Cadence Rails Swarm** geometry. The cadence side manufactures; the swarm side consumes — same primitive, two sides.

**When to use**: large multi-lane next-tic execution (≥3 parallel lanes); next-session work surface known at current /cadence; rails-authoring cost (~5-10 min of parallel subagent dispatch) cheaper than next-session cold-start RTCH cost.

**When NOT to use**: routine tic boundaries; next-session work surface unknown at current /cadence (rails would speculate); single-lane next-tic work (no parallelism to govern).

<!-- landed-from cpr_parallel_rtch_consolidate_rails_for_next_swarm_with_inbox_marker_dependency_signaling_tic277 (PROMOTE-SPEC at /review tic 278; doctrine inscribed at canonical_developer/context-grapple-gun/CLAUDE.md; skill body extension owed at tic 280 per Verdict-Shape KI; cross-tic n=2 validated tic 277 authoring → tic 278 execution). Band: COGNITIVE. Domain rung: CGG. -->

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

#### Standing-Pointer Priority Calibration (light; epoch-boundary)

The boot-injection standing pointers (`audit-logs/boot-injections/active.jsonl`) carry a `priority` field the renderer (`boot-injection.py`) **sorts** by — lowest-priority pointers seal first when the boot budget is exceeded. But **a relative priority is meaningful only if it was authored relative to the active set** (cgg-ledger#priority-is-calibrated-at-cadence-not-boot, /review 421): a number guessed in isolation — or a missing field defaulting to 50 — is accidental placement around a default attractor, not a real ranking.

**Cold boot cannot calibrate** (no session context, no forward direction — it can only render), and a per-write lint on every ad-hoc writer would cage a being-authored judgment into a compliance artifact (constrain-vs-cultivate). The relational writer with the fullest context + forward direction is **/cadence** — it sees the whole session and writes the projection, so calibrating which standing-pointers survive the next boot's budget is the **same future-self-rehydration stewardship as the handoff itself**. The renderer sorts; cadence justifies placement.

At the epoch boundary — only when standing pointers were added/changed this tic, or a pointer has been repeatedly sealed:
1. Read the active set (`boot-injection.py render --tic <N> --audience orchestrator` shows the priority-ordered + sealed-manifest result; `active.jsonl` is the truth).
2. Calibrate each touched pointer's `priority` **against the active set** (not in isolation) — what must survive the next boot's budget vs. what may seal first.
3. Record a one-line `priority_basis` on the record (why this placement, relative to which siblings) — the relational justification, not just the number.
4. A **repeatedly-sealed** record (it keeps losing the budget) is **flagged for the next cadence pass** to re-evaluate (retire / re-prioritize / promote to a standing brief), never auto-promoted on excitement.

**Lock:** *Priority is relative only if written relationally. The renderer sorts; the writer with fullest context — cadence — justifies placement.* Missing priority = neutral fallback (50) until the next cadence calibration. This is calibration (cultivation), **not a gate** — never block the handoff on a missing `priority_basis`.

<!-- landed-from cpr_priority_is_calibrated_at_cadence_not_boot_tic421 (/review 421 PROMOTE -> cgg-ledger#priority-is-calibrated-at-cadence-not-boot; impl gate tic 422). Band: COGNITIVE. Domain rung: CGG. -->

The user sees this plan in Claude Code's native plan UI with approve/edit/reject/clear options. When approved and context cleared, the plan persists and becomes the active state for the next session.

The session does NOT end until the human acts on the plan. The human may:
- **Approve + clear context** — plan persists, next session picks it up via `implement_plan`
- **Edit** — modify the handoff before approving
- **Continue working** — exit plan mode and keep going

The ripple-assessor runs HEADLESS on next session start (background, non-blocking via cgg-gate.sh hook). It writes proposals to `~/.claude/grapple-proposals/latest.md` — keeping its ~10k tokens OUT of the runtime context window. The completion notification is informational only ('proposals ready for /review when ready') — it does NOT demand immediate attention. Proposals are consumed when the user invokes `/review`, not before.

---

## Handoff Retrieval Map Section

Decision briefs, meta-analyses, peer review captures — land them in the inbox envelope. The handoff must include a Retrieval Map section that teaches future-me the retrieval patterns (commands + thread_id + envelope_id) and points at the inbox as the first substrate to check, not as an afterthought.

<!-- promoted from CogPR-N (tic B->R). Source: <source_file>. <additional context if present in the CogPR>. -->

## Multi-Abstraction-Layer Handoff Preservation

When a session produces CogPR candidates that span multiple abstraction layers, the handoff must preserve each layer distinctly. The extraction pipeline can cluster, split, or promote selectively at /review time — but it cannot reconstitute lost layering. Preservation is cheap (a few extra bullet points per candidate); collapse is irreversible. This block demonstrates its own pattern: it names the preservation rule, the authoring discipline, the anti-pattern it closes, and the meta-validation fact.

<!-- promoted from CogPR-N (tic B->R). Source: <source_file>. <additional context if present in the CogPR>. -->

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

### Handoff Three Co-Equal Lanes

When a cadence handoff carries an Architect-pending decision, format the handoff's position as three co-equal lanes: (1) position, (2) rationale, (3) steelmanned opposition with multiple counter-arguments. Do NOT collapse the adversarial lane into a tiebreaker summary — preserve the tension for Architect review. This extends the existing surprise-assessment invariant (CogPR on review dockets requiring honest novelty assessment) from review surfaces to handoff surfaces: the handoff is ALSO a judgment surface, and the recommendation is weaker when it silently absorbs its opposition. The adversarial lane names what the recommendation is NOT addressing — opposition 1 (scope), opposition 2 (premature inscription), opposition 3 (staging-duration as signal), opposition 4 (framing-bias of the recommender). Each must make its strongest case. The Architect then decides with full access to both lanes rather than a pre-collapsed recommendation. The cost is handoff density; the benefit is epistemic honesty that survives into the next session.

<!-- promoted from CogPR-N (tic B->R). Source: <source_file>. <additional context if present in the CogPR>. -->

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

**Step 3a — Read the active plan file FIRST (Look-First gate, mandatory).**
Before invoking `EnterPlanMode`, locate the most-recent file in `~/.claude/plans/` (by mtime) and **Read it via the Read tool**. The plan-write surface is hard-gated by the harness: it refuses to update a plan file unless that file has been Read in the current session. Skipping this step produces a `File has not been read yet. Read it first before writing to it.` error mid-write. Same gate, same fix as the downbeat path — even in emergency syncopate cadence, this 1-tool-call cost is mandatory.

**Step 3b — Invoke EnterPlanMode.**
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

## Down-Lane / Lifecycle Routing (FORWARD — tic 378)

> **Status: FORWARD** (not wired). Living-Corpus trancheset (`audit-logs/governance/doctrine-lifecycle-living-corpus-trancheset-spec-tic378.md`); model `autonomous_kernel/doctrine-lifecycle-spec.md`.

- **IS-NOT (today):** Step-2 lesson extraction is a *location* decision (which CLAUDE.md / MEMORY.md) and presumes the up-lane (capture → promotion). Demotion appears once, buried in the optional deep-audit; there is no capture-time lifecycle routing.
- **Forward:** capture also classifies *lifecycle intent* (candidate / held / needs-down-audit) and routes a `lifecycle_state` alongside location; the deep-audit's demotion-pressure becomes a first-class down-lane cycle, not an optional aside.
- **Discipline:** capture is a proposal; doctrine-LAW routes through /review; no inline demotion.
