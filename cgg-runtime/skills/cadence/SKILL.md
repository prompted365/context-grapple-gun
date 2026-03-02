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
Record the canonical downbeat timestamp.

**Counting rule (SUBSTRATE INVARIANT):** The canonical tic count is the physical number of `type=tic` entries across all `audit-logs/tics/*.jsonl` files, determined by JSON-parsing — never by grep, never by reading an embedded `tic_count_project` field from a previous entry. The global counter file (`~/.claude/cgg-tic-counter.json`) is a cached mirror of this physical truth, not an independent state machine.

1. Append tic record to `audit-logs/tics/YYYY-MM-DD.jsonl`:
   `{"type": "tic", "tic": "<ISO-8601 now>", "tic_zone": "<name from .ticzone>", "cadence_position": "downbeat", "scope": "project"}`
   Note: `tic_count_project` and `tic_count_global` are omitted — they are advisory and the canonical count is physical truth.
2. Reconcile counters from physical truth:
   ```bash
   PHYS=$(python3 -c "import json,glob; print(sum(1 for f in glob.glob('audit-logs/tics/*.jsonl') for l in open(f) if json.loads(l).get('type')=='tic'))")
   ```
3. Write global counter atomically (cached mirror of physical truth):
   ```bash
   TMP="$HOME/.claude/cgg-tic-counter.json.tmp.$$"
   printf '{"count": %d, "last_tic": "%s"}\n' "$PHYS" "$NOW" > "$TMP"
   mv "$TMP" "$HOME/.claude/cgg-tic-counter.json"
   ```
4. Report: `Tic #PHYS (physical) at YYYY-MM-DDTHH:MM:SSZ`

#### Step 1: Signal Manifold Hygiene
Execute `/siren tick`. Ensure volume has accrued, TTLs are cleared, and thresholds are checked.

#### Step 1.5: Snapshot Conformation
Execute `/siren conformation` to capture the system's total state at this tic boundary.

#### Step 2: Extract Lessons (CogPRs)
Did we establish a new rule or optimize a workflow? If yes, IMMEDIATELY write the `<!-- --agnostic-candidate -->` block into the nearest CLAUDE.md or MEMORY.md. Use the COGNITIVE band.

Include birth context when available:
- `posture`: current session posture (e.g., "ENG/DIRECT", "OPS/META")
- `cwd_context`: working directory relative to project root
- `birth_tic`: the tic number from Step 0.5

These fields are optional. Omit if posture is not in use.

Write to the nearest governance file up the directory tree:
1. Check CWD for CLAUDE.md — write there if found
2. Walk up parent directories toward project root
3. If no subdir CLAUDE.md exists — write to project root CLAUDE.md
4. Operational memory (not law) — write to MEMORY.md instead

When writing to a subdir CLAUDE.md, ensure the project root CLAUDE.md
indexes it (add a reference in any existing "subdirectory guides" section).

### Phase 2: PLAN MODE — The Handoff (Steps 3-4)

#### Step 3: Enter Plan Mode
Use the `EnterPlanMode` tool to switch to Claude Code's native plan mode. This is mandatory and mechanical — call the tool, do not just declare the shift.

#### Step 4: Write the Handoff as the Plan
Generate a NEW native plan. The plan content IS the handoff — this is the ONE AND ONLY place the handoff gets written. Claude Code auto-saves the plan to `~/.claude/plans/` when approved, and references it in the next session.

The plan must include:
- `<!-- cgg-handoff -->` block with handoff_id, project_dir, trigger_version, generated_at
- User Intent, Agent Interpretation, Interpretation Concerns
- Working State (citation-laden, file:line references)
- Session Learning & ROI with Time Saved Estimates
- Friction (Signals): any new `<!-- --signal -->` blocks for unresolved technical debt
- Next Actions (concrete, numbered)
- Conformation summary
- `<!-- cgg-evaluate -->` trigger block at the very bottom — `pending_cprs_expected` must match the exact number of CogPRs from Step 2

The user sees this plan in Claude Code's native plan UI with approve/edit/reject/clear options. When approved and context cleared, the plan persists and becomes the active state for the next session.

The session does NOT end until the human acts on the plan. The human may:
- **Approve + clear context** — plan persists, next session picks it up via `implement_plan`
- **Edit** — modify the handoff before approving
- **Continue working** — exit plan mode and keep going

The ripple-assessor runs HEADLESS on next session start (background, non-blocking via cgg-gate.sh hook). It writes proposals to `~/.claude/grapple-proposals/latest.md` — keeping its ~10k tokens OUT of the runtime context window. The completion notification is informational only ('proposals ready for /review when ready') — it does NOT demand immediate attention. Proposals are consumed when the user invokes `/review`, not before.

---

## Mode: Double-Time (emergency syncopate)

When the user invokes `/cadence double-time`, execute the emergency session boundary. Produces a valid handoff in minimal turns. No tick, no conformation, no assessor — just tic + plan.

### Phase 1: ENG/DIRECT — Operational Writes (Steps 1-2)

All operational mutation happens here. These are the writes that MUST complete before the handoff.

#### Step 1: Raise Autocompact Ceiling

If `CLAUDE_ENV_FILE` is available, temporarily push the autocompact boundary higher to prevent compaction mid-syncopate:

```
echo 'export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=95' >> "$CLAUDE_ENV_FILE"
```

This buys headroom. The next session's SessionStart hook will reset it to 80%.

#### Step 2: Emit Tic (lightweight)

**Counting rule (SUBSTRATE INVARIANT):** The canonical tic count is the physical number of `type=tic` entries across all `audit-logs/tics/*.jsonl` files, determined by JSON-parsing — never by grep, never by reading an embedded `tic_count_project` field from a previous entry. The global counter file (`~/.claude/cgg-tic-counter.json`) is a cached mirror of this physical truth, not an independent state machine.

1. Append tic record to `audit-logs/tics/YYYY-MM-DD.jsonl`:
   `{"type": "tic", "tic": "<ISO-8601 now>", "tic_zone": "<name from .ticzone>", "cadence_position": "syncopate", "scope": "project"}`
   Note: `tic_count_project` and `tic_count_global` are omitted — they are advisory and the canonical count is physical truth.
2. Reconcile counters from physical truth:
   ```bash
   PHYS=$(python3 -c "import json,glob; print(sum(1 for f in glob.glob('audit-logs/tics/*.jsonl') for l in open(f) if json.loads(l).get('type')=='tic'))")
   ```
3. Write global counter atomically (cached mirror of physical truth):
   ```bash
   TMP="$HOME/.claude/cgg-tic-counter.json.tmp.$$"
   printf '{"count": %d, "last_tic": "%s"}\n' "$PHYS" "$NOW" > "$TMP"
   mv "$TMP" "$HOME/.claude/cgg-tic-counter.json"
   ```
4. Report: `Tic #PHYS (physical) at YYYY-MM-DDTHH:MM:SSZ [syncopate]`

Note: `cadence_position` is `"syncopate"`, not `"downbeat"`. This distinguishes emergency exits from planned epoch boundaries.

### Phase 2: PLAN MODE — The Handoff (Steps 3-4)

#### Step 3: Enter Plan Mode

Use the `EnterPlanMode` tool to switch to Claude Code's native plan mode. This is mandatory and mechanical — call the tool, do not just declare the shift.

#### Step 4: Write the Handoff as the Plan

Generate a NEW native plan. The plan content IS the handoff — this is the ONE AND ONLY place the handoff gets written. Claude Code auto-saves the plan to `~/.claude/plans/` when approved, and references it in the next session.

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
| CPR extraction (Step 2 of downbeat) | Requires reading full context | Lessons stay inline, picked up next `/review` |
| Ripple assessor | Runs headless on next session start | cgg-gate.sh triggers it |

The double-time is a valid handoff — the next session gets Next Actions via the plan and can run a full downbeat when context is fresh.
