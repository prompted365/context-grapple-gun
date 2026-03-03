# CGG Implementation Map

Every documented behavior mapped to its authoritative code file. When a doc claim and code diverge, **code wins** — update the doc to match.

> Cross-reference companion to the doc ladder: [START-HERE](../START-HERE.md) (Tier 0), [INSTALL](../INSTALL.md) (Tier 1), [DEV-README](../DEV-README.md) + [skills/README](../cgg-runtime/skills/README.md) (Tier 2), [README](../README.md) + [ARCHITECTURE](../ARCHITECTURE.md) (Tier 3).

---

## 1. Pipeline Components

| Component | Code File | Purpose | Key Identifiers |
|-----------|-----------|---------|-----------------|
| SessionStart hook | `cgg-runtime/hooks/session-restore-patch.sh` | Plan discovery, trigger extraction, CPR counting, signal scanning, parallel session detection | `count_pending_cprs()` (line 64), `FIND_EXCLUDES` (line 77), inline Python signal dedup (line 133) |
| UserPromptSubmit gate | `cgg-runtime/hooks/cgg-gate.sh` | One-shot trigger — fires ripple-assessor then self-disarms | `TRIGGER_FILE` fast exit (line 20), deterministic assessor path (line 56), LLM fallback (line 69) |
| Ripple assessor | `cgg-runtime/agents/ripple-assessor.md` | Headless CPR evaluator + signal scanner | Frontmatter: `model: sonnet`, `tools: Read, Grep, Glob` (line 4-6). Output: `~/.claude/grapple-proposals/latest.md` (line 77) |
| Cadence (epoch boundary) | `cgg-runtime/skills/cadence/SKILL.md` | Tic emission, signal tick, conformation, lessons, handoff | Downbeat: Steps 0-4 (lines 26-99). Double-time: Steps 1-4 (lines 111-196) |
| Review (docket) | `cgg-runtime/skills/review/SKILL.md` | Human-gated CPR promotion + warrant triage | 8-step workflow (lines 13-165). Protected files (line 167). Safety rules (line 175) |
| Siren (signal ops) | `cgg-runtime/skills/siren/SKILL.md` | Signal emit/tick/update/history/conformation/diff | Sub-commands: status (line 21), tick (line 54), emit (line 114), update (line 168), history (line 193), conformation (line 215), conformation diff (line 292) |

### Deprecated Skills (redirect-only)

| Deprecated Skill | Redirects To | Code File |
|-----------------|-------------|-----------|
| `/cadence-downbeat` | `/cadence` (full downbeat) | `cgg-runtime/skills/cadence-downbeat/SKILL.md` |
| `/cadence-syncopate` | `/cadence double-time` | `cgg-runtime/skills/cadence-syncopate/SKILL.md` |
| `/grapple` | `/review` | `cgg-runtime/skills/grapple/SKILL.md` |
| `/init-gun` | Bootstrap install | `cgg-runtime/skills/init-gun/SKILL.md` |
| `/init-cogpr` | Bootstrap install | `cgg-runtime/skills/init-cogpr/SKILL.md` |

All deprecated skills contain only a redirect message — no duplicate logic. `init-gun` and `init-cogpr` have `disable-model-invocation: true`.

---

## 2. Zone Scan Rule

The zone scan rule defines which files are in the governance surface. It appears in **5 locations** that must stay synchronized:

| # | File | Where | What to search for |
|---|------|-------|--------------------|
| 1 | `hooks/session-restore-patch.sh` | Lines 76-104 | `find ... -name "CLAUDE.md" -o -name "MEMORY.md"`, `.ticignore` reading loop (line 79), default exclusions (line 90), auto-memory path (line 100) |
| 2 | `skills/review/SKILL.md` | Step 2, lines 30-40 | Glob targets, exclusion list, `status: "example"` skip |
| 3 | `skills/siren/SKILL.md` | Conformation step 4, lines 234-239 | Glob targets, exclusion list, `status: "example"` skip |
| 4 | `skills/README.md` | Line 48 | Zone scan rule summary + DEV-README reference |
| 5 | `../../DEV-README.md` | Zone scanning section | Full rule description (5 steps) |

**The rule:**
1. Project root = directory containing `.ticzone` (or CWD)
2. Governance files = `**/CLAUDE.md` + `**/MEMORY.md` inside the zone
3. Auto-memory (`~/.claude/projects/*/memory/MEMORY.md`) always included
4. `.ticignore` exclusions applied (default: `vendor/`, `node_modules/`, `.git/`, `.claude/skills/`)
5. Blocks with `status: "example"` are skipped

**Implementation detail:** `session-restore-patch.sh` uses `find` with `-not -path` exclusions built from `.ticignore` (line 77-91). It strips comments, whitespace, trailing slashes, and skips glob patterns (`*`, `?`) — only directory exclusions for governance scan (line 85).

---

## 3. Tic Emission

### Counting invariant (SUBSTRATE INVARIANT)

The canonical tic count is the **physical number** of `type=tic` entries across all `audit-logs/tics/*.jsonl` files, determined by JSON-parsing. Never by grep. Never by reading an embedded `tic_count_project` field.

| Location | Implementation |
|----------|---------------|
| `cadence/SKILL.md` line 32 | Counting rule stated + Python snippet (line 39) |
| `cadence/SKILL.md` line 123 | Same rule repeated for double-time mode |
| `siren/SKILL.md` line 219-230 | Physical count via inline Python for conformation |

### Downbeat vs syncopate

| Field | Downbeat | Double-time |
|-------|----------|-------------|
| `cadence_position` | `"downbeat"` | `"syncopate"` |
| Signal tick | Yes (Step 1) | Skipped |
| Conformation | Yes (Step 1.5) | Skipped |
| CPR extraction | Yes (Step 2) | Skipped |
| Handoff format | Full (cgg-evaluate block) | Compact (5 lines/section, no cgg-evaluate) |

### Global counter cache

Written atomically via tmp file + `mv` at `~/.claude/cgg-tic-counter.json`. Format: `{"count": N, "last_tic": "ISO-8601"}`. This is a **cached mirror**, not the source of truth.

### Tic store

Records appended to `audit-logs/tics/YYYY-MM-DD.jsonl`. Format:
```json
{"type": "tic", "tic": "ISO-8601", "tic_zone": "zone-name", "cadence_position": "downbeat|syncopate", "scope": "project"}
```

Advisory fields `tic_count_project` and `tic_count_global` are deliberately omitted from new records (cadence/SKILL.md line 36).

---

## 4. Signal Lifecycle

### Emission
- **Manual**: `/siren emit <kind> <band> <subsystem> <message>` — `siren/SKILL.md` line 114
- **Defaults**: volume=30, volume_rate=10, max_volume=100, ttl_hours=24 — `siren/SKILL.md` lines 135-154
- **PRESTIGE band blocked**: `siren/SKILL.md` line 123
- **ID format**: `sig_YYYY-MM-DDTHH:MMZ_<subsystem>_<4char_hash>` — `siren/SKILL.md` line 128

### Volume accrual
- Per tick: `volume = min(volume + volume_rate, max_volume)` — `siren/SKILL.md` line 61
- Only ticks `active` or `acknowledged` signals (NOT `working`/`resolved`/`expired`/`warranted`) — `siren/SKILL.md` line 59
- TTL expiry check on every tick — `siren/SKILL.md` line 64

### Effective volume (acoustic routing)
- `effective_volume = volume - (directory_hops(source, target) * 5)` — `siren/SKILL.md` line 50
- `review/SKILL.md` line 57 (identical formula)

### Warrant minting
- **Volume threshold**: `volume >= escalation.warrant_threshold` AND no existing warrant — `siren/SKILL.md` line 66
- **Harmonic triad**: PRIMITIVE/BEACON + COGNITIVE/LESSON + any/TENSION within 24h — `siren/SKILL.md` line 67, `review/SKILL.md` lines 61-68
- **Priority assignment**: PRIMITIVE=P1, COGNITIVE=P2, SOCIAL=P3 — `siren/SKILL.md` line 108
- Source signal updated to `status: "warranted"` on mint — `siren/SKILL.md` line 110

### Status transitions
- Valid statuses: `active`, `acknowledged`, `working`, `resolved`, `expired`, `warranted` — `siren/SKILL.md` line 174
- `working` sets `working_since` (optimistic lock) — `siren/SKILL.md` line 179
- `resolved` sets `resolved_at` + `resolution_note` — `siren/SKILL.md` line 180

### Conformation snapshots
- Written to `audit-logs/conformations/tic-<physical_count>.json` — `siren/SKILL.md` line 243
- Physical count from inline Python, NOT any embedded field — `siren/SKILL.md` line 244
- Includes: signals, warrants, pending CogPRs, zone config, rule fingerprints — `siren/SKILL.md` lines 246-277

---

## 5. CogPR Lifecycle

### Format
- Block: `<!-- --agnostic-candidate ... -->` — `cogpr/README.md` signal primitives table
- Required fields: `lesson`, `source_date`, `source`, `band`, `motivation_layer`, `subsystem`, `recommended_scopes`, `rationale`, `review_hints`, `status`
- Optional birth context: `posture`, `cwd_context`, `birth_tic` — `cadence/SKILL.md` lines 58-63

### Birth context
- Written at cadence Step 2 — `cadence/SKILL.md` lines 55-69
- Scope resolution: walk up directory tree to nearest CLAUDE.md, fallback to project root, MEMORY.md for operational memory

### Evaluation
- Ripple-assessor runs headless on next session start — `agents/ripple-assessor.md`
- Trigger path: `cadence` writes `cgg-evaluate` block → `session-restore-patch.sh` extracts to flag files → `cgg-gate.sh` fires assessor → proposals at `~/.claude/grapple-proposals/latest.md`
- Assessment: 30-line source context, plan context, target scope overlap/conflict/gap, memory bias — `agents/ripple-assessor.md` lines 34-41

### Review + promotion
- Human-gated via `/review` in Plan Mode — `review/SKILL.md` lines 70-120
- Verdicts: PROMOTE (update status + `promoted_to`, `promoted_date`), SKIP (`rejected` + `rejected_date`, `reason`), MODIFY (apply change then promote) — `review/SKILL.md` lines 124-158
- Meta-log: `~/.claude/grapple-meta-log.jsonl` — `review/SKILL.md` lines 161-164

### Status values
- `pending` → `promoted` | `rejected` (via `/review`)
- `example` — documentation templates, skipped by all scanners

---

## 6. Install & Config

### Bootstrap modes (INSTALL.md)
| Mode | What it does |
|------|-------------|
| A | Full automation — hooks + skills + agent |
| B | Skills only — no hooks (manual `/cadence` + `/review`) |
| C | Convention only — CogPR format blocks, no slash commands |

### File copy matrix
Source `cgg-runtime/` directories → target project locations:

| Source | Target | Contents |
|--------|--------|---------|
| `hooks/cgg-gate.sh` | `.claude/hooks/cgg-gate.sh` | UserPromptSubmit gate |
| `hooks/session-restore-patch.sh` | `.claude/hooks/session-restore-patch.sh` | SessionStart discovery |
| `agents/ripple-assessor.md` | `.claude/agents/ripple-assessor.md` | Assessor definition |
| `skills/cadence/` | `.claude/skills/cadence/` | Epoch boundary |
| `skills/review/` | `.claude/skills/review/` | Docket reviewer |
| `skills/siren/` | `.claude/skills/siren/` | Signal operations |

Deprecated skills are NOT copied during install.

### Zone/ignore creation
- `.ticzone` — JSONC zone definition at project root. Fields: `name`, `tz`, `lat`, `lon`, `include`, `bands`, `muffling_per_hop`
- `.ticignore` — gitignore-style exclusion patterns (directory-only in v1, no glob wildcards). Documented constraint.

### Convention block (INSTALL.md)
- Band budget table
- CogPR format with optional posture field
- Cadence timing heuristic ("~100k tokens" as checkpoint, not hard boundary)

---

## 7. Assessment Strategy

### Deterministic-first pattern
`cgg-gate.sh` line 56: checks for `$PROJECT_DIR/scripts/ripple-assessor.py`. If found, runs it directly (fast, deterministic, no LLM cost). Otherwise falls back to LLM agent spawn via `hookSpecificOutput` (line 69-77).

### LLM fallback
Instructs Claude to spawn `ripple-assessor` agent (Task tool, subagent_type) before starting user work. Non-blocking — runs in background.

### Proposals output
Always written to `~/.claude/grapple-proposals/latest.md`. Consumed and deleted by `/review` (review/SKILL.md line 165).

### One-shot idempotency
- Flag files (`pending-trigger.txt`, `pending-handoff-id.txt`) deleted immediately on fire — `cgg-gate.sh` line 42
- Handoff ID recorded to `~/.claude/cgg-processed-handoff-ids.txt` — `cgg-gate.sh` line 46
- Audit trail: `~/.claude/grapple-meta-log.jsonl` — `cgg-gate.sh` line 51

---

## 8. Data Stores

| Path | Format | Managing Component | Contents |
|------|--------|--------------------|----------|
| `audit-logs/signals/YYYY-MM-DD.jsonl` | Append-only JSONL | `/siren`, `/review` | Signals + warrants. Latest entry per ID wins. |
| `audit-logs/tics/YYYY-MM-DD.jsonl` | Append-only JSONL | `/cadence` | Tic records. Physical count = canonical truth. |
| `audit-logs/conformations/tic-N.json` | JSON snapshot | `/siren conformation` | System state at tic boundary. |
| `~/.claude/grapple-proposals/latest.md` | Markdown | `ripple-assessor` → `/review` | CPR verdicts + signal assessment. Deleted after consumption. |
| `~/.claude/grapple-meta-log.jsonl` | Append-only JSONL | `cgg-gate.sh`, `/review` | Trigger fires, promotion decisions, warrant verdicts. |
| `~/.claude/cgg-tic-counter.json` | JSON | `/cadence` | Cached mirror of physical tic count. `{"count": N, "last_tic": "ISO-8601"}` |
| `~/.claude/cgg-processed-handoff-ids.txt` | Plain text (one ID per line) | `cgg-gate.sh` | Idempotency ledger — prevents re-evaluation. |
| `.ticzone` | JSONC | Install, `/siren conformation` | Zone definition (name, tz, bands, muffling). |
| `.ticignore` | Gitignore-style patterns | `session-restore-patch.sh`, `/review`, `/siren conformation` | Exclusion filter for governance scan. |
| `${TMPDIR}/claude_cgg/$PROJECT_KEY/` | Temp files | `session-restore-patch.sh` → `cgg-gate.sh` | `pending-trigger.txt`, `pending-handoff-id.txt`. Ephemeral. |

---

## 9. Deprecated Skills

| Old Command | New Command | Migration |
|------------|-------------|-----------|
| `/cadence-downbeat` | `/cadence` | Automatic redirect — old skill announces rename and executes downbeat |
| `/cadence-syncopate` | `/cadence double-time` | Automatic redirect — old skill announces rename and executes double-time |
| `/grapple` | `/review` | Automatic redirect — old skill announces rename and executes review |
| `/init-gun` | Bootstrap install (INSTALL.md) | Describes bootstrap, offers to run it |
| `/init-cogpr` | Bootstrap install (INSTALL.md) | Describes bootstrap, exits |

Deprecated skills also exist at `cogpr/claude-code/skills/` (convention layer copies). These are identical redirects for projects that installed from the old cogpr-only package.

---

## 10. Doc Audience Ladder

| Tier | Audience | File(s) | What they need |
|------|----------|---------|----------------|
| 0 | Day-to-day user | [START-HERE.md](../START-HERE.md) | 3 commands, normal day, what to do when slow |
| 1 | Installer / Operator | [INSTALL.md](../INSTALL.md) | Install modes, file layout, zone/ignore setup |
| 2 | Developer / Integrator | [DEV-README.md](../DEV-README.md), [skills/README.md](../cgg-runtime/skills/README.md) | Pipeline mechanics, hook lifecycle, scan surfaces |
| 3 | Architect / Systems thinker | [README.md](../README.md), [ARCHITECTURE.md](../ARCHITECTURE.md) | Mental model, primitives, design rationale, scaling ceiling |
| Ref | Maintenance | This file, [LOCKSTEP-INVARIANTS.md](LOCKSTEP-INVARIANTS.md), [VALIDATION-CHECKLIST.md](VALIDATION-CHECKLIST.md) | Cross-references, sync points, QA runbook |

Each doc file has a "Who this is for" block pointing up and down the ladder.
