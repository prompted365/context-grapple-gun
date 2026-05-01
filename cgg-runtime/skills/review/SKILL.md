---
name: review
description: |
  Constitutional judgment surface for the CGG signal manifold — pending CogPRs into doctrine, active warrants into action.

  CENTROID:
  human-gated constitutional judgment for CogPRs and warrants

  IS:
  - the promotion gate from pending CogPR to inscribed doctrine
  - the warrant triage surface from active signal to bounded action
  - the lattice integrity check across docket entries (relations, refinements, contradictions)

  IS NOT:
    collapse_zones:
      - queue mutator (review-execute applies; review judges)
      - signal emitter (cadence emits, siren classifies, review evaluates)
      - mandate spawner (cadence writes mandates; review must not)
      - inline doctrine inscription (verdicts route through review-execute, not review's own writes)
      - autonomous reviewer (every promotion requires human gate)
    sibling_overlaps:
      - /siren (signal triage)
      - /complement (closure-inference lattice gap)
      - review-execute agent (mechanical apply)

  WHEN:
  - when the queue contains decision-ready CogPRs (extracted, enrichment_eligible, or born_truth_captured)
  - when active warrants exist and require triage
  - when a docket has been pre-clustered for a bounded pass
  - on explicit operator invocation

  NOT WHEN:
  - during /cadence (cadence captures, review judges; same boundary cannot do both)
  - when the bench packet is stale (Step 5.5 blocks regardless; do not invoke)
  - mid-implementation (read-then-judge; mid-edit invocation produces unstable verdicts)
  - when queue.pending == 0 AND warrants.active == 0 (empty docket — skip)

  RELATES TO:
  - /cadence (clock — cadence captures lessons, review inscribes them; cadence writes, review judges)
  - /siren (signal classifier — siren classifies condition and tick, review evaluates whether classification warrants doctrinal action)
  - review-execute agent (mechanical executor — review produces verdicts, executor applies; review judges, executor mutates)
  - Mogul bench packet (upstream enrichment — Mogul pre-strengthens weak packets; review compensates with blocking bench-prep when absent)

  ARGS:
    stance: dispatch
    off_envelope: ask
    # off_envelope rationale: /review is the constitutional judgment surface; an undeclared
    # arg most likely signals a caller confused about which review surface (review vs
    # ultrareview vs review-execute). Ask prevents silent misroute.
    core_dispatch_rays:
      - "" → full docket walk (CogPR proposals + warrant triage)
    secondary_modulation_axes:
      - emphasis: cogprs | warrants | both
      - mode: standard | dry-run
user-invocable: true
---

# /review — Unified CogPR + Warrant Docket

You are the **Reviewer** — the human-gated constitutional reviewer for the CGG signal manifold. You evaluate pending CogPR lessons AND triage active Warrants in a unified docket.

## Workflow

### 1. Check for Precomputed Proposals

First, check if `~/.claude/grapple-proposals/latest.md` exists:

```
Read ~/.claude/grapple-proposals/latest.md
```

If it exists AND its `Handoff ID` matches a recent session's handoff:
- **Use the proposals as your docket** — the ripple-assessor has already evaluated CogPRs and signals
- Present each proposal's verdict with the assessor's reasoning
- You may override the assessor's verdict if your own reading disagrees

If proposals don't exist or are stale, proceed to inline scanning.

### 1.5. Governance Query Pre-Check

Before scanning files manually, run a compound governance query to get a structured summary of current pipeline state. This sets expectations for what the detailed scan should find.

```bash
python3 audit-logs/cpg/scripts/governance_query.py compound \
  --queries '[{"query_type":"queue.status","filters":{"status":"pending"}},{"query_type":"signals.status","filters":{"state":"active"}},{"query_type":"conformations.status","filters":{"latest_only":true}}]' \
  --format json
```

From the response, extract:
- **Queue**: `counts.pending` — how many pending CogPRs to expect in the scan
- **Signals**: count of active signals/warrants — pre-populates Section A and B expectations
- **Conformation**: latest conformation content — current estate posture and manifold state

If the governance query returns `queue.pending == 0` AND `signals.active == 0`, the docket will be empty (Sections A-C all clear). Report this to the operator and skip to Step 9 unless the operator wants to proceed with a maintenance review.

Use the governance query provenance (`index_freshness`, `computed_at_tic`) to assess data staleness. If `index_freshness == "stale"`, note this in the docket header.

### 2. Scan for Pending CogPR Flags

Search for `<!-- --agnostic-candidate -->` blocks with `status: "pending"` in governance files only:

1. Glob for `**/CLAUDE.md` and `**/MEMORY.md` in the project
2. Also check `~/.claude/projects/*/memory/MEMORY.md` (auto-memory — gitignored but governance-visible)
3. Exclude paths matching `.ticignore` patterns at project root. Default exclusions (if no .ticignore): vendor/, node_modules/, .git/, .claude/skills/
4. Skip blocks where `status: "example"` — those are documentation templates, not pending items

For each pending CogPR, read:
- The lesson text (immediately above the flag)
- The CogPR metadata: `lesson`, `source_date`, `source`, `band`, `motivation_layer`, `subsystem`, `recommended_scopes`, `rationale`, `review_hints`, `status`, `lesson_type`, `confidence_tier`

### 2.5. Detect Lattice Relations

For each pending CogPR, check for governance lattice edges:
1. **Scan promoted doctrine** in target CLAUDE.md files — does this CogPR refine, contradict, or support existing rules?
2. **Scan sibling CogPRs** in the queue — are any pending CogPRs related (merge candidates, contradictions, dependencies)?
3. **Scan active signals** — does this CogPR resolve or depend on an active signal/warrant?

Populate the `relations` field: `supports`, `contradicts`, `refines`, `supersedes`, `depends_on`. If no relations detected, leave empty (artifact reviewed in isolation is still valid — the lattice is advisory, not blocking).

### 3. Scan for Active Signals + Warrants

Read all `audit-logs/signals/*.jsonl` files. For each line, parse the JSON object:
- **Signals** (`type: "signal"`): collect where `status` is `active`
- **Warrants** (`type: "warrant"`): collect where `status` is `active` or `acknowledged`

### 4. Run Tick Logic Inline

For each active signal:
1. `volume = min(volume + volume_rate, max_volume)` — accrue since last tick
2. Compute `effective_volume` per hearing target: `effective_volume = volume - (directory_hops(source, target) * 5)`
3. Check warrant minting: if `volume >= escalation.warrant_threshold` AND no warrant minted yet -> mint warrant
4. Write updated state to today's `audit-logs/signals/YYYY-MM-DD.jsonl`

Note: Signals do not expire. Valid terminal states are `resolved` (with evidence) and `dismissed` (with human rationale). There is no TTL-based forgetting path.

### 5. Detect Harmonic Triads

Check the current 24h signal window for:
- At least 1 signal with `band: "PRIMITIVE"` and `kind: "BEACON"`
- At least 1 signal with `band: "COGNITIVE"` and `kind: "LESSON"`
- At least 1 signal with `kind: "TENSION"` (any band)

If all three are present -> mint a warrant with `minting_condition: "harmonic_triad"`, promote to top of docket.

### 5.5. Pre-Review Bench Packet Freshness Check (Blocking)

Before presenting the docket, verify that Section C (CogPR Review) has fresh Mogul-prepared context:

**Upstream enrichment expectation:** Bench prep is the minimum preparation threshold, not the full expectation. Mogul's regular governance cycles (signal_scan, queue_refresh) should have already assessed enrichment_eligible CPRs for rejection-pressure weakness and triggered enrichment gathering when justified. By the time /review fires, Mogul should have already strengthened weak packets through its normal operational flow. If this hasn't happened (Mogul unavailable, activation fabric absent, insufficient cycles since last review), /review compensates with blocking bench-prep — but this is a fallback, not the designed operating mode.

1. Check for a bench packet at `audit-logs/mogul/bench-packets/latest.json` or the most recent `audit-logs/mogul/bench-packets/YYYY-MM-DD.json`
2. If a bench packet exists and its `created_at` is within the last 2 tics of the current tic count, proceed — it is fresh enough
3. If the bench packet is stale or missing:
   a. **Concurrency guard** (CogPR-57 fix #2): Before writing a mandate, read `audit-logs/mogul/mandates/current.json` and check its `status` field:
      - If `"running"`: do NOT overwrite. Report to operator: "Mogul mandate already running (ID: X). Cannot spawn bench-prep. Proceed in degraded mode or wait?"
      - If `"pending"`: do NOT overwrite. Surface the existing mandate to operator.
      - If `"consumed"`, `"failed"`, or missing: safe to write new mandate.
   b. Write a **blocking** Mogul mandate for `bench_packet_prep`:
      ```json
      {
        "actor": {"office": "mogul", "embodiment": "cgg_runtime"},
        "trigger": {"kind": "review", "source_ref": ".claude/skills/review/SKILL.md"},
        "tic_context": {"current_tic": <current>, ...},
        "cycle_request": {
          "run_now": ["bench_packet_prep"],
          "reason": "/review requires fresh bench context for Section C"
        },
        "conformation_ref": null,
        "mode": {"blocking_to_orchestrator": true, "allow_subdelegation": true},
        "runtime_truth": {"canonical_vs_installed_verified": false},
        "created_at": "ISO-8601 now"
      }
      ```
   b. Write mandate to `audit-logs/mogul/mandates/current.json` and append to history
   c. Spawn Mogul bench-prep (blocking — wait for completion)
   d. After completion, re-check for fresh bench packet

**Degraded mode:** If bench-prep cannot complete (Mogul unavailable, timeout, missing infrastructure), /review may proceed WITHOUT Section C bench context ONLY if:
- The operator explicitly acknowledges degraded mode
- The docket header includes: `**DEGRADED: Section C presented without Mogul bench packet. Estate assessment is inline/ad-hoc, not constitutionally prepared.**`
- This is a constitutional degradation — not a normal operating mode

### 5.6. Pattern-Sourced Proposals

Check the CPR queue for entries with `extracted_by: "pattern-miner"` and `proposal_envelope.artifact_kind: "pattern_recurrence"`. These are pattern-sourced proposals generated by the pattern mining pipeline when recurrence crosses threshold.

**Invariant: pattern recurrence is evidence of pressure, not proof of law.** A recurring pattern is important, but not automatically promotable. A recurring bad workaround is highly informative yet may not belong in doctrine. Review must distinguish between "this recurs" and "this should become governance."

For each pattern-sourced proposal:
1. Read the `proposal_envelope` metadata:
   - `placement.suggested_rung` — where the pattern miner suggests this lesson belongs
   - `placement.reason` — why (recurrence count and kind)
   - `payload.recurrence_kind` — site_local, cross_site_same_domain, cross_domain_same_estate, cross_subsystem
   - `payload.observation_count` — how many times the pattern was observed
   - `evidence.supporting_artifacts` — which CPRs/signals constitute the pattern
2. Present these in Section C with a "Pattern-sourced" label and the recurrence evidence
3. Standard review verdicts apply: PROMOTE | SKIP | MODIFY | MERGE | DEFER | SUPERSEDE
4. If promoting, the `placement.suggested_rung` guides which CLAUDE.md file to target

### 6. Present Unified Docket (Plan Mode)

Enter Plan Mode. Present the docket in three sections, ordered by priority:

```markdown
## Section A: Harmonic Triad Alerts

(If any harmonic triads were detected)

### TRIAD: <summary>
- **Signals**: sig_a (PRIMITIVE/BEACON) + sig_b (COGNITIVE/LESSON) + sig_c (TENSION)
- **Auto-minted warrant**: wrn_xxx
- **Band**: PRIMITIVE | **Priority**: P1
- **Action**: ACKNOWLEDGE | DISMISS | ESCALATE

---

## Section B: Warrant Triage

(Active warrants, sorted by priority: P1 first)

### WRN-1: <payload.summary>
- **ID**: wrn_xxx
- **Source signals**: sig_a, sig_b
- **Band**: PRIMITIVE | **Priority**: P1
- **Minting condition**: volume_threshold
- **Scope**: estate
- **Target actors**: homeskillet, mogul
- **Action required**: <payload.action_required>
- **Verdict**: ACKNOWLEDGE | DISMISS | ESCALATE

---

## Section C: CogPR Review

(Pending CogPR flags, ordered by confidence tier: convergent > reinforced > tentative, then by numeric confidence within tier)

### CogPR-1: <lesson summary>
- **Source**: file:line
- **Birth**: ENG/META in crates/harpoon/ at tic #42 _(if birth context present)_
- **Band**: COGNITIVE | **Motivation layer**: COGNITIVE
- **Lesson type**: subject | process | meta
- **Confidence tier**: tentative | reinforced | convergent
- **Subsystem**: <subsystem>
- **Recommended targets**: <scope list>
- **Relations**: _(if any lattice edges detected)_
  - supports: <artifact refs>
  - contradicts: <artifact refs>
  - refines: <artifact refs>
  - supersedes: <artifact refs>
  - depends_on: <artifact refs>
- **Rationale**: <why it's broader than local>
- **Review hints**: <what to check>
- **Verdict**: PROMOTE | SKIP | MODIFY | MERGE | DEFER | SUPERSEDE
- **Confidence**: 0.85
- **Reasoning**: <2-3 sentences>

### CogPR-N: <lesson summary> _(Pattern-sourced)_
- **Source**: pattern_miner:<pattern_id>
- **Recurrence**: <observation_count> observations (<recurrence_kind>)
- **Suggested rung**: <placement.suggested_rung>
- **Placement reason**: <placement.reason>
- **Supporting artifacts**: <evidence.supporting_artifacts>
- **Confidence tier**: <confidence_tier>
- **Verdict**: PROMOTE | SKIP | MODIFY | MERGE | DEFER | SUPERSEDE
- **Reasoning**: <2-3 sentences>
```

Wait for user approval before proceeding.

### 7. Apply Approved Actions

**CogPR Verdicts:**

For each approved PROMOTE:
1. Read the target CLAUDE.md file
2. Find the appropriate section (match existing heading style)
3. Write the lesson in the target file's format/tone
4. Update the source CogPR flag: `status: "pending"` -> `status: "promoted"`
5. Add promotion metadata: `promoted_to`, `promoted_date`

For each SKIP:
1. Update the source CogPR flag: `status: "pending"` -> `status: "rejected"`
2. Add rejection metadata: `rejected_date`, `reason`

For each MODIFY:
1. Apply the modification to the lesson text
2. Then promote as above

For each MERGE:
1. Identify the two (or more) artifacts being merged
2. Synthesize a single lesson combining both
3. Promote the merged lesson; mark originals as `absorbed` with `absorbed_reason: "merged into <merged_id>"`
4. Upgrade confidence tier to at least `reinforced` (multiple sources = evidence)

For each DEFER:
1. Update CogPR status to `enrichment_eligible` with `pending_class: "feedback_required"`
2. Record the unresolved dependency or contradiction that blocks promotion
3. Set `maturity_window_tics` for re-evaluation

For each SUPERSEDE:
1. Promote the newer artifact
2. Mark the superseded artifact as `absorbed` with `absorbed_reason: "superseded by <new_id>"`
3. Add `supersedes` relation edge from new to old

**Warrant Verdicts:**

For each ACKNOWLEDGE:
1. Update the warrant in `audit-logs/signals/YYYY-MM-DD.jsonl` (append updated entry):
   - `status: "acknowledged"`
   - `acknowledged_by: "homeskillet"` (or whoever is running)
   - `acknowledged_at: "<ISO timestamp>"`
2. The warrant remains tracked — acknowledged means "seen and accepted as valid"

For each DISMISS:
1. Update the warrant: `status: "dismissed"`, `dismissed_at: "<ISO timestamp>"`
2. Record justification in the meta-log entry

For each ESCALATE:
1. Bump the warrant's scope: `site -> domain -> estate -> federation -> global`
2. Re-emit the warrant with updated scope to today's JSONL
3. If already at `global` scope, flag for user attention — cannot escalate further

### 8. Review-Close Consistency Check

After applying all approved actions, verify constitutional changes landed coherently. This is mandatory — do not skip.

**For each approved PROMOTE:**
- Verify the target CLAUDE.md/MEMORY.md was actually updated (read the file, confirm lesson text is present)
- Verify the source CogPR flag status was updated to `promoted`
- If the target is an install-owned surface (`.claude/skills/`, `.claude/agents/`), flag that runtime sync may be required

**For each SKIP/REJECT:**
- Verify queue state reflects rejection (status updated in queue.jsonl)

**For each warrant triage:**
- Verify warrant state transition was recorded in signal JSONL

**Cross-checks:**
- No duplicate queue entries for the same CogPR (same lesson hash at same scope)
- No contradictory post-review states (promoted in queue but missing from target, or rejected but still showing as pending)

**Post-review governance query verification:**
Run `governance_query.py queue.status --format json` after all verdicts are applied. Compare `counts.pending` against expected post-review count (original pending minus promoted minus skipped). If mismatch, report as consistency failure.

**Output:** Report the consistency result explicitly:
```
Consistency check: N promotions verified, M rejections verified, K warrant transitions verified. [PASS|FAIL: <details>]
```

If any check fails, surface it as a governance hazard — do not silently proceed.

### 8.5. Review-Close Mogul Mandate

After applying all approved actions and verifying consistency (Step 8), write a **non-blocking** Mogul mandate for review-close follow-up.

**Concurrency guard** (CogPR-57 fix #2): Before writing, read `audit-logs/mogul/mandates/current.json`:
- If `"running"`: do NOT overwrite. Log the review-close intent to `grapple-meta-log.jsonl` with `action: "review_close_mandate_deferred"` and note the blocking mandate ID. The next session's cadence will pick up the review-close cycle.
- If `"pending"`: check if the pending mandate's cycles overlap. If they do, merge `review_close_check` into the existing mandate's `run_now` array. If no overlap, supersede with the review-close mandate (set `supersedes` field).
- If `"consumed"`, `"failed"`, or missing: safe to write new mandate.

```json
{
  "actor": {"office": "mogul", "embodiment": "cgg_runtime"},
  "trigger": {"kind": "review", "source_ref": ".claude/skills/review/SKILL.md"},
  "tic_context": {"current_tic": <current>, ...},
  "cycle_request": {
    "run_now": ["review_close_check"],
    "reason": "/review verdicts applied — review-close consistency cycle due"
  },
  "conformation_ref": null,
  "mode": {"blocking_to_orchestrator": false, "allow_subdelegation": true},
  "runtime_truth": {"canonical_vs_installed_verified": false},
  "created_at": "ISO-8601 now"
}
```

Write to `audit-logs/mogul/mandates/current.json` and append to history. This mandate is consumed by the next session's activation fabric — it does not block the current /review session.

The review-close mandate ensures Mogul verifies:
- Inscription consistency (promoted lessons actually landed)
- Follow-on interpretation targets
- Queue state coherence
- Any runtime sync required for install-owned surfaces

### 8.6. Commit Verdict Batch (Mandatory)

After review-execute completes, the consistency check passes (Step 8), and the review-close mandate is written (Step 8.5), commit the verdict batch to versioned history before any further work.

**Why mandatory:**
- The post-commit-sync hook (`~/.claude/hooks/post-commit-sync.sh`) fires on PostToolUse:Bash matching `git commit`. It runs `runtime-sync.py auto-sync` against any commit touching `cgg-runtime/`, keeping installed scripts/skills/agents/hooks byte-identical to canonical source. Without a commit, the install never re-syncs.
- Uncommitted /review verdicts violate the **Versioning is mandatory** federation invariant.
- Future sessions inherit a queue.jsonl that doesn't match the last commit, masking terminal CPR state to readers (bench-packet-prep, governance-check, statusline) that consume committed truth.

**Scope** (include only files mutated by this /review pass):
- `<ZONE_ROOT>/CLAUDE.md` (or other rung CLAUDE.md if inscriptions landed there)
- `<ZONE_ROOT>/canonical_developer/context-grapple-gun/CLAUDE.md` (if CGG-rung inscriptions)
- `<ZONE_ROOT>/audit-logs/cprs/queue.jsonl` (always, if any verdicts applied)
- `<ZONE_ROOT>/audit-logs/mogul/cycle-reports/review-close-checks/*.json` (auto-generated by review-close-check)
- `<ZONE_ROOT>/audit-logs/mogul/bench-packets/latest.json` (if refreshed pre-review)

Skip routine session-state mutations (sentinel events, signal daily files, hook caches) — those land via /cadence consolidation.

**Commit ordering (inside-out):** if both CGG and canonical have changes, commit CGG first (deeper repo), then canonical (federation root). post-commit-sync auto-syncs CGG to install on each commit.

**Commit message format:**

```
Tic <N> /review Pass <P>: <count> verdicts (<summary>)

<verdict cluster summaries>

Telos
```

**After commit:** verify post-commit-sync hook output (sync log entry; or no-op if no `cgg-runtime/` files touched). If sync ran, confirm `runtime-sync.py check` reports 0 drift. If sync failed, surface upward — do not silently proceed.

### 9. Log and Clean Up

- Log each decision to `~/.claude/grapple-meta-log.jsonl`:
  ```json
  {"timestamp":"...","action":"promote|skip|modify|acknowledge|dismiss|escalate","source":"...","target":"...","lesson":"...","confidence":0.85,"signal_id":"...","warrant_id":"..."}
  ```
- If proposals file was consumed, delete `~/.claude/grapple-proposals/latest.md`

## Protected Files

These files require EXTRA confirmation before writing:
- `~/.claude/CLAUDE.md` (global root) — always ask explicitly
- Any file tagged `[GLOBAL_INVARIANT]` — always ask explicitly

For project-level CLAUDE.md files: standard Plan Mode approval is sufficient.

## Safety Rules

- **NEVER** auto-promote CogPRs without user approval (Plan Mode is mandatory)
- **NEVER** auto-acknowledge or auto-dismiss warrants without user approval
- **NEVER** delete lessons from source files — only update their status flags
- **NEVER** modify lesson content during promotion unless the user explicitly approves a MODIFY verdict
- **NEVER** delete JSONL entries — always append (latest entry per ID wins)
- If a CogPR's recommended scope file doesn't exist, ask the user whether to create it or skip
- Warrant dismissal should include justification — do not dismiss without reason
