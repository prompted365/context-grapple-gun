---
name: cadence-syncopate
description: Emergency session turnaround — minimal tic + handoff in ≤5% context window. The off-beat escape hatch.
user-invocable: true
---

# /cadence-syncopate

Emergency session boundary for low-context situations. Produces a valid handoff in minimal turns. No tick, no conformation, no assessor — just tic + plan.

When the user invokes this command, execute the following steps. Every step is mandatory but minimal.

## Phase 1: ENG/DIRECT — Operational Writes (Steps 1–2)

All operational mutation happens here. These are the writes that MUST complete before the handoff.

### Step 1: Raise Autocompact Ceiling

If `CLAUDE_ENV_FILE` is available, temporarily push the autocompact boundary higher to prevent compaction mid-syncopate:

```
echo 'export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=95' >> "$CLAUDE_ENV_FILE"
```

This buys headroom. The next session's SessionStart hook will reset it to 80%.

### Step 2: Emit Tic (lightweight)

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

## Phase 2: PLAN MODE — The Handoff (Steps 3–4)

### Step 3: Enter Plan Mode

Use the `EnterPlanMode` tool to switch to Claude Code's native plan mode. This is mandatory and mechanical — call the tool, do not just declare the shift.

### Step 4: Write the Handoff as the Plan

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
- **Approve + clear context** → plan persists, next session picks it up via `implement_plan`
- **Edit** → modify the handoff before approving
- **Continue working** → exit plan mode and keep going

This is the constitutional gate — no context clear without human sign-off via the native plan UI.

## What Syncopate Skips (and why)

| Skipped | Why | Recovery path |
|---------|-----|---------------|
| Signal tick (`/siren tick`) | Too expensive at 5% | Next downbeat or manual `/siren tick` |
| Conformation snapshot | Depends on tick | Next downbeat |
| CPR extraction (Step 2 of downbeat) | Requires reading full context | Lessons stay inline, picked up next `/grapple` |
| Ripple assessor | Runs headless on next session start | cgg-gate.sh triggers it |

The syncopate is a valid handoff — the next session gets Next Actions via the plan and can run a full downbeat when context is fresh.
