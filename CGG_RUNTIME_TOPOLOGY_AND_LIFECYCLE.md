# CGG Runtime Topology and Lifecycle

CGG is a runtime — not a hook collection with helper scripts. This document maps the actual execution topology, mandate lifecycle, and workflow interactions as they exist today.

## 1. Purpose

CGG provides the governance execution substrate for the Canonical federation. It owns:

- Session lifecycle hooks (session-restore, prompt gate, post-tool, post-commit)
- Governance scripts (mandate writing, routing, assessment, mining, auditing)
- Skill specs (cadence, review, siren, init-governance, videographer, etc.)
- Agent specs (mogul, review-execute, pattern curators, ladder-auditor, etc.)
- Runner infrastructure (mogul-runner.sh for headless mandate consumption)

All of these are interdependent. Hooks call scripts. Scripts depend on libraries. Runners consume agent specs. Skills reference scripts. The install model must keep all layers current.

## 2. Active Topology

### 2.1 Canonical Source Tree (authoritative)

```
canonical_developer/context-grapple-gun/cgg-runtime/
├── hooks/          # 4 shell hooks (session-restore, cgg-gate, posttool-microscan, post-commit-sync)
├── scripts/        # 22 Python scripts + mogul-runner.sh + lib/
├── skills/         # Skill specs (*/SKILL.md)
└── agents/         # Agent specs (*.md)
```

This is the only surface where authoring occurs. All other locations are mirrors.

### 2.2 Installed Hooks (`~/.claude/hooks/`)

Direct copies of canonical hooks. Referenced by absolute path in `~/.claude/settings.json`. These are the entry points — Claude Code calls them on SessionStart, UserPromptSubmit, PostToolUse.

### 2.3 Installed Runtime Scripts (`~/.claude/cgg-runtime/scripts/`)

Mirror of canonical scripts. This is the **tier-3 fallback** in the `resolve_script()` chain and, in the current installation model, the **only tier that resolves** (see Section 3).

### 2.4 Installed Skills (`~/.claude/skills/`)

Mirror of canonical skill SKILL.md files. Claude Code reads these to populate the skill registry (slash commands).

### 2.5 Installed Agents (`~/.claude/agents/`)

Mirror of canonical agent spec .md files. Used by the Agent tool when spawning named subagents.

### 2.6 Plugin Cache (`~/.claude/plugins/cache/cgg/`) — ARCHIVED

Historical residue from the plugin-install era (v4.0.1, created 2026-03-08). CGG was unregistered from `installed_plugins.json` when the installation model shifted to direct hook wiring. The cache contains 17 scripts (5 fewer than current canonical) and a stale `mogul-runner.sh`.

**Status: non-authoritative, non-executing, scheduled for cleanup.**

## 3. Script Resolution Chain

Hooks use `resolve_script()` to find governance scripts at runtime:

```bash
resolve_script() {
  local name="$1"
  for candidate in \
    "$ZONE_ROOT/scripts/$name" \                       # Tier 1: project override
    "$CGG_SCRIPTS_DIR/$name" \                          # Tier 2: plugin-root-anchored
    "$HOME/.claude/cgg-runtime/scripts/$name"; do       # Tier 3: global fallback
    if [ -f "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}
```

### What currently resolves

| Tier | Path | Resolves? | Why |
|------|------|-----------|-----|
| 1 | `$ZONE_ROOT/scripts/` | No (for CGG scripts) | Contains `git-cycle.sh` (federation tooling, not CGG runtime) |
| 2 | `$CGG_PLUGIN_ROOT/cgg-runtime/scripts/` | **No** | `CLAUDE_PLUGIN_ROOT` is unset; fallback computes `~/cgg-runtime/scripts/` which doesn't exist |
| 3 | `$HOME/.claude/cgg-runtime/scripts/` | **Yes** | Active execution surface (synced from canonical) |

### Why `CLAUDE_PLUGIN_ROOT` is unset

CGG was unregistered from `installed_plugins.json`. Claude Code only sets `CLAUDE_PLUGIN_ROOT` for registered plugins. The hooks were migrated to direct `settings.json` references, which don't set plugin-root context. The tier-2 fallback computes `dirname(hook)/../..` = `$HOME`, producing a nonexistent path.

### Consequence

All script resolution goes through tier 3. If tier 3 is not synced with canonical, scripts silently fail to resolve and hooks fall through to inline fallback codepaths (which lack merge logic, routing, and proper lifecycle transitions).

## 4. Runtime Truth Table

| Location | Role | Status | Safe to execute from? |
|----------|------|--------|----------------------|
| Canonical source tree | **Authoritative** | Current | Yes (development) |
| `~/.claude/hooks/` | Active hooks | Must match canonical | Yes |
| `~/.claude/cgg-runtime/scripts/` | **Active runtime** | Must match canonical | Yes |
| `~/.claude/skills/` | Active skill registry | Must match canonical | Yes |
| `~/.claude/agents/` | Active agent registry | Must match canonical | Yes |
| `~/.claude/plugins/cache/cgg/` | **Stale residue** | Archived (v4.0.1) | **No** |

**Rule**: If canonical changes, the active runtime mirror must be updated before the next governance cycle. `runtime-sync.py` is the mechanism.

## 5. Mandate Lifecycle

```
         ┌─────────────────────────────────────┐
         │                                     │
    ┌────▼────┐    ┌─────────┐    ┌──────────┐ │
    │ pending │───▶│ running │───▶│ consumed │ │
    └────┬────┘    └────┬────┘    └──────────┘ │
         │              │                       │
         │              ▼                       │
         │         ┌────────┐                   │
         │         │ failed │                   │
         │         └────────┘                   │
         │                                      │
         ▼                                      │
    ┌────────────┐                              │
    │ superseded │◀─────────────────────────────┘
    └────────────┘  (new mandate merges/replaces)
```

### State definitions

| State | Meaning | Who transitions |
|-------|---------|-----------------|
| `pending` | Created, not yet executing | session-restore.sh, /cadence, /review |
| `running` | Mogul runner has started execution | mogul-runner.sh |
| `consumed` | All mandated cycles completed successfully | mogul-runner.sh **or** cgg-gate.sh (lightweight-only mandates) |
| `failed` | Execution encountered an error | mogul-runner.sh |
| `superseded` | A newer mandate replaced this one (ID recorded in `supersedes`) | mandate-write.py |

### Lightweight mandate consumer (RESOLVED)

**Status:** Resolved at commit `92e84a4` (Mar 13 2026); race-guard hardened at `354f8ab`; authoritative-source refined at `2f74ea1` (tic 208). The original defect was that a lightweight-only mandate stayed `pending` indefinitely because `cgg-gate.sh` had no consumer for it.

**Current behavior**: When a mandate contains only lightweight cycles (`queue_refresh`, `signal_scan`), `cgg-gate.sh` Branch A executes them inline with race-guard re-validation, then transitions the mandate to `consumed` with a `lightweight_results` audit field carrying the per-cycle outputs. When a mandate contains heavy cycles (with or without lightweight), the heavy branch spawns `mogul-runner.sh` which consumes the full mandate (heavy + lightweight) under one lifecycle.

**Implementation locations:**
- `cgg-runtime/hooks/cgg-gate.sh` lines ~177-298 (lightweight inline consumer + race guard + status transition)
- `cgg-runtime/scripts/mogul-runner.sh` lines ~488 (heavy-branch lightweight handling under same runner)
- `tests/test_lightweight_mandate_consumer.py` (regression-prevention fixture, tic 214)

**Authoritative-source discipline:** The `signal_scan` cycle reads from `audit-logs/signals/active-manifest.jsonl` (curated), not raw daily emissions, per Disagreement-as-Evidence (federation KI) and CogPR-184 (Signal Resolution Writeback Atomicity). The `queue_refresh` cycle counts unique IDs by latest-status using the canonical PENDING_STATUSES set per CogPR-205 (Authoritative-Set Readers Must Read the Manifest). Both consumers mirror the equivalent logic in `mogul-runner.sh` so heavy and lightweight paths produce comparable counts.

## 6. Execution Classes

### 6.1 Lightweight cycles

Deterministic, low-cost, no agent spawn required.

| Cycle | What it does |
|-------|-------------|
| `queue_refresh` | Re-scan CPR queue, update indices |
| `signal_scan` | Check signal volumes, accrue, check warrant thresholds |

**Handler**: `cgg-gate.sh` Branch A executes lightweight cycles inline when a mandate is lightweight-only (no heavy cycles present), then transitions the mandate to `consumed` with `lightweight_results` audit metadata. When heavy cycles are also present, `mogul-runner.sh` consumes the full mandate (heavy + lightweight) under one lifecycle. Race-guard re-validates mandate status before consumption to avoid contention with `mogul-runner.sh` if it picked up the mandate first. Resolved at commit `92e84a4`; see Section 5 "Lightweight mandate consumer (RESOLVED)".

### 6.2 Heavy cycles

Require Mogul agent spawn (headless `claude -p` via `mogul-runner.sh`).

| Cycle | What it does |
|-------|-------------|
| `memory_mining` | Scan MEMORY.md for CogPR extraction |
| `pattern_mining` | Run pattern curators (meta + direct) |
| `ladder_audit` | Audit CLAUDE.md governance chain coherence |
| `runtime_drift_check` | Compare canonical vs installed runtime |
| `deep_audit` | Full estate audit |
| `review_close_check` | Post-/review consistency verification |
| `bench_packet_prep` | Prepare bench packet for /review |

**Handler**: `mogul-runner.sh` → headless Claude → Mogul agent spec → optional team spawn.

### 6.3 Blocking review spawn

`/review` Step 5.5 can spawn a blocking Mogul instance for `bench_packet_prep`. This is the one place where Mogul runs inline (blocking the interactive orchestrator) rather than in background. Risk: collision with a `/loop`-backed Mogul if both are active.

### 6.4 /loop-owned work

`/loop` is a Claude Code built-in that periodically re-invokes a skill. It does not spawn Mogul directly. It can surface conditions that trigger mandates on the next session restore.

### 6.5 Team/subdelegation work

Mogul can create one team per session: `mandate-pattern-triangulation`. Team members (ladder-auditor, ripple-assessor, pattern-curator-meta, pattern-curator-direct) execute tasks with dependencies. All teammates inherit the same working directory and resolution chain as Mogul.

## 7. Workflow Map

### 7.1 /cadence (downbeat)

```
User invokes /cadence
  │
  ├─ Step 0: Plan reconciliation
  ├─ Step 0.5: Emit tic (cadence-ops.py emit_tic)
  │   └─ Appends to audit-logs/tics/YYYY-MM-DD.jsonl
  │   └─ Updates ~/.claude/cgg-tic-counter.json
  ├─ Step 1: Signal hygiene (/siren tick)
  ├─ Step 1.5: Snapshot conformation (cadence-ops.py write_conformation)
  │   └─ Writes audit-logs/conformations/tic-N.json
  ├─ Step 2: Extract CogPRs from MEMORY.md/CLAUDE.md
  ├─ Step 3: Enter plan mode
  └─ Step 4: Write handoff plan
      ├─ Compute due cycles for next tic
      ├─ Call mandate-write.py (merge-before-write)
      │   └─ Writes audit-logs/mogul/mandates/current.json
      │   └─ Appends audit-logs/mogul/mandates/history/YYYY-MM-DD.jsonl
      └─ Plan includes cgg-handoff + cgg-evaluate blocks
```

**Creates**: tic event, conformation, mandate, handoff plan.

### 7.2 /cadence double-time (syncopate)

```
User invokes /cadence double-time
  │
  ├─ Step 1: Raise autocompact ceiling (if available)
  ├─ Step 2: Emit tic (syncopate, counted)
  ├─ Step 3: Enter plan mode
  └─ Step 4: Write compact handoff (5 lines max per section)
```

**Skips**: conformation, CogPR extraction, mandate write, signal tick.
**Creates**: tic event, compact handoff plan.

### 7.3 Session start / restore

```
session-restore.sh fires (SessionStart hook)
  │
  ├─ Resolve latest plan from ~/.claude/plans/
  ├─ Extract handoff_id and cgg-evaluate block
  ├─ Write flag files ($TMPDIR) for cgg-gate.sh Branch B
  ├─ Count pending CogPRs (inline + queue.jsonl)
  ├─ Read physical tic count from audit-logs/tics/
  ├─ Compute due cycles (tic modulo)
  ├─ Call mandate-write.py (merge-before-write)
  │   └─ Merges with existing pending mandate OR supersedes consumed/failed
  ├─ Run cpr-extract.py (backfill counters)
  ├─ Run cpr-enrichment-scanner.py (background, non-blocking)
  ├─ Route trigger via trigger-router.py → mogul inbox
  └─ Output context: [CGG HANDOFF...] [MOGUL MANDATE...] [SIREN...] [TIC: #N]
```

**Redundant computation**: Due cycles are computed here AND in /cadence using the same modulo logic. `mandate-write.py` merge semantics absorb duplicates, but the computation is still redundant.

### 7.4 User prompt gate (cgg-gate.sh)

```
cgg-gate.sh fires (UserPromptSubmit hook)
  │
  ├─ Branch A: Mandate check (independent)
  │   ├─ Read current.json → parse status, cycles, classify heavy vs lightweight
  │   ├─ If pending + heavy: spawn mogul-runner.sh (background, owns full lifecycle)
  │   ├─ If pending + lightweight-only: race-guard re-check, execute inline,
  │   │                                 transition to consumed + lightweight_results
  │   ├─ If running: surface in-flight message
  │   └─ If failed: surface failure alert
  │
  └─ Branch B: Trigger-based assessment (independent, one-shot)
      ├─ Check $TMPDIR flag files from session-restore
      ├─ If present: delete flags (idempotency)
      ├─ Route ripple.assessment trigger via trigger-router.py
      ├─ Spawn ripple-assessor.py (background)
      └─ Output: [CGG TRIGGER FIRED] Proposals at ~/.claude/grapple-proposals/
```

### 7.5 /review

```
User invokes /review
  │
  ├─ Step 1: Check precomputed proposals (from ripple-assessor)
  ├─ Step 1.5: Governance query pre-check
  ├─ Steps 2-3: Scan pending CogPRs
  ├─ Step 4: Run signal tick logic (accrue, warrant check)
  ├─ Step 5: Detect harmonic triads
  ├─ Step 5.5: Bench packet freshness (may blocking-spawn Mogul)
  ├─ Step 6: Present docket in plan mode
  │   └─ User approves verdicts (PROMOTE/SKIP/MODIFY/MERGE/DEFER/SUPERSEDE)
  ├─ Step 7: Apply approved actions (dispatch to review-execute agent)
  ├─ Step 8: Consistency check
  ├─ Step 8.5: Write review_close_check mandate
  └─ Step 9: Log and cleanup
```

### 7.6 Mandate flow across workflow phases

```
/cadence ──creates──▶ mandate (pending, due cycles for next tic)
                              │
session-restore ──merges──▶ mandate (pending, merged cycles)
                              │
cgg-gate ──routes──▶ mogul-runner.sh (heavy + any lightweight) ──▶ consumed/failed
                  or ──▶ inline consume (lightweight-only) ──▶ consumed
                              │
/review ──creates──▶ mandate (pending, review_close_check)
                              │
next session-restore ──merges──▶ mandate (pending, merged)
```

### 7.7 Where mandates are created, surfaced, executed, consumed, or superseded

| Phase | Creates | Surfaces | Executes | Consumes | Supersedes |
|-------|---------|----------|----------|----------|------------|
| /cadence | Yes (merge-aware) | No | No | No | Via merge |
| session-restore | Yes (merge-aware) | Yes (context injection) | No | No | Via merge |
| cgg-gate | No | Yes (every prompt) | Yes (heavy via runner; lightweight inline) | Yes (lightweight-only mandates inline) | No |
| mogul-runner.sh | No | No | Yes | Yes (heavy + mixed mandates) | No |
| /review | Yes (review_close_check) | No | Yes (blocking bench-prep) | No | No |

## 8. Drift History

### Phase 1: Plugin-era install (pre-2026-03-08)

CGG installed as a Claude Code plugin. `CLAUDE_PLUGIN_ROOT` set by Claude Code. Script resolution tier 2 pointed at plugin cache. 17 scripts existed. System functioned with all tiers available.

### Phase 2: Direct-hook migration (~2026-03-08)

Hooks moved to `~/.claude/hooks/` with direct `settings.json` references. CGG unregistered from `installed_plugins.json`. Simpler, more controllable, no marketplace dependency. But `CLAUDE_PLUGIN_ROOT` stopped being set.

### Phase 3: Script surface expansion (2026-03-08 → 2026-03-13)

5 new scripts added to canonical post-migration:
- `cadence-ops.py` — cadence tic/conformation operations
- `enrichment-scanner.py` — CogPR enrichment pipeline
- `inbox-envelope.py` — agent inbox scanning
- `posture-analytics.py` — posture metric computation
- `trigger-router.py` — inbox-based trigger routing

Plus `mogul-runner.sh` evolved. Plugin cache did not receive any of these.

### Phase 4: /loop + Mogul teams (2026-03-09 → present)

`/loop` introduced persistent runtime polling. Mogul teams introduced multi-agent mandate execution. Both increased reliance on script resolution and runtime orchestration. Missing scripts stopped being minor install imperfections and became live architectural faults.

### Phase 5: Sync repair (2026-03-13)

Manual sync of all 22 scripts to `~/.claude/cgg-runtime/scripts/`. Hooks confirmed matching. Tier 3 resolution now functional. But sync is manual — no automated path prevents future drift.

## 9. Fix Classes

### 9.1 Install topology fix

**Problem**: `runtime-sync.py` tracks skills, agents, and hooks but not scripts.
**Fix**: Add `scripts` to `INSTALL_TARGETS` so `runtime-sync auto-sync` keeps `~/.claude/cgg-runtime/scripts/` current.
**Effect**: Prevents future drift. Makes manual sync unnecessary.

### 9.2 Lifecycle fix (RESOLVED)

**Status:** Resolved. Original problem: lightweight mandates (`queue_refresh`, `signal_scan`) had no consumer; they stayed `pending` forever, producing `[MOGUL MANDATE: lightweight]` on every prompt.
**Fix landed:** `cgg-gate.sh` Branch A executes lightweight cycles inline when no heavy cycles are present, then transitions the mandate to `consumed` with `lightweight_results` audit metadata. Race-guard re-validates status before consumption to avoid contention with `mogul-runner.sh`.
**Implementation history:** `92e84a4` (initial inline consumer + topology doc, Mar 13 2026), `354f8ab` (CogPR-57 race-guard hardening), `2f74ea1` (authoritative-source reading per CogPR-205, tic 208).
**Regression protection:** `tests/test_lightweight_mandate_consumer.py` (added tic 214) exercises the consumer end-to-end against synthetic mandates and asserts status transition + audit fields.
**Effect:** Mandate lifecycle is symmetrical — both heavy and lightweight paths have explicit state transitions; lightweight mandates do not leak as pending across sessions.

### 9.3 Hygiene fix

**Problem**: Stale plugin cache at `~/.claude/plugins/cache/cgg/` contains 17 scripts from v4.0.1 (5 behind canonical) and a drifted `mogul-runner.sh`. Not executing but could confuse future operators.
**Fix**: Delete the cache directory or mark it explicitly archived.
**Effect**: Removes ambiguous execution surface.

## 10. Source-of-Truth Doctrine

1. **Canonical repo is authoritative** — all authoring happens here
2. **`~/.claude/` runtime mirror is the execution surface** — hooks, scripts, skills, agents execute from here
3. **Plugin cache is dead** unless CGG is explicitly re-registered as a plugin
4. **`runtime-sync.py` is the sole sync mechanism** — manual copies are emergency patches, not process
5. **Post-commit-sync hook triggers runtime-sync** — canonical changes should auto-propagate on commit
6. **Loaded runtime wins** — runtime-sync reports drift, doesn't silently pretend canonical is active. If installed differs from canonical, the installed version is what runs.
