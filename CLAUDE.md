# Context Grapple Gun — Domain CLAUDE.md

## Epistemic Volatility Notice

Claude Code hook format, plugin manifest schema, and install semantics are **externally versioned by Anthropic**. Treat as a volatile contract surface. Do not promote session-inferred schema understanding to doctrine without validating against current docs/schema.

All schema-specific sections below (Hook Format, Plugin Hooks, etc.) reflect the format as of the last validated check. They may become stale when Claude Code updates.

<!-- promoted from CogPR-15 (tic 9→11). Refines CogPR-1 and CogPR-4 by version-banding them. Source: tic-8 post-session analysis. -->

## Hook Format Requirement (Current)

The hook format has changed multiple times. The **current** format requires:

1. Each event contains an array of **matcher groups**
2. Each matcher group has an optional `matcher` (regex string) and a `hooks` array
3. `matcher` is a **regex string** matching tool names (e.g. `"Bash"`, `"Edit|Write"`)
4. For match-all: **omit `matcher` entirely**, or use `"*"`
5. `"matcher": {}` (object) is **invalid** in current versions

**Correct format (match-all — omit matcher):**
```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "path/to/hook.sh"
          }
        ]
      }
    ]
  }
}
```

**Correct format (filtered — regex string matcher):**
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "path/to/hook.sh"
          }
        ]
      }
    ]
  }
}
```

**Broken formats (do NOT use):**
- `{"type":"command","command":"..."}` directly in event array (pre-2.1.58 flat format)
- `{"matcher":{},"hooks":[...]}` with object matcher (pre-2.1.72 format)

Reference: [Hooks docs](https://code.claude.com/docs/en/hooks) | [Settings schema](https://json.schemastore.org/claude-code-settings.json)

Downstream surfaces (INSTALL.md, academy guide, init-governance SKILL.md) updated to current format at tic 2.

### Hook types available

- `"type": "command"` — runs a shell command, receives JSON on stdin
- `"type": "http"` — POSTs JSON to a URL endpoint (added 2.1.63)

### CGG-relevant hook events (2.1.69+)

- `InstructionsLoaded` — fires when CLAUDE.md or `.claude/rules/*.md` loaded into context
- `TeammateIdle` / `TaskCompleted` — support `{"continue": false}` to stop teammates
- Hook events now include `agent_id` and `agent_type` fields

### Other capabilities

- `${CLAUDE_SKILL_DIR}` — skills can reference their own directory (2.1.69)
- `/reload-plugins` — activate plugin changes without restart (2.1.69)
- Shared project configs across worktrees (2.1.63)

<!-- promoted from CogPR-1 (tic 1), updated tic 2 after second format break. Source: ~/.claude/projects/-Users-breydentaylor-canonical/memory/MEMORY.md -->

## Plugin Hook Registration

Plugins must register hooks in `hooks/hooks.json` at the plugin root — listing hooks in `plugin.json` components alone is insufficient. Use `${CLAUDE_PLUGIN_ROOT}` to reference scripts within the plugin directory.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/posttool-microscan.sh"
          }
        ]
      }
    ]
  }
}
```

Reference: [Plugin docs](https://code.claude.com/docs/en/plugins)

<!-- promoted from CogPR-4 (tic 3→5). Source: code.claude.com/docs/en/plugins. Validated by hooks/hooks.json creation. -->

## Agent Tool (formerly Task)

The `Task` tool was renamed to `Agent` in Claude Code 2.1.63. All CGG agent frontmatter must use `Agent`, not `Task`.

- **Frontmatter**: `tools: Read, Grep, Glob, Agent, Bash`
- **Spawn restriction**: `Agent(subagent-name)` restricts which subagents can be spawned
- The `Task` alias may still work but should not be relied upon

<!-- promoted from CogPR-5 (tic 3→5). Source: code.claude.com/docs/en/sub-agents. Applied to mogul.md at f26f21b. -->

## JSONL Atomic Writes (PRIMITIVE)

All JSONL append-only files (`audit-logs/**/*.jsonl`) must use atomic append to prevent corruption from concurrent writers (hooks, session-start, Mogul cycles).

**Required pattern**: write to temp file, then atomic rename/append — never direct `>>` append from concurrent processes.

- Scripts: use `scripts/lib/atomic-append.sh`
- Python: use `scripts/lib/atomic_append.py`
- All 10 JSONL-writing hooks/scripts have been patched to use these libraries

**Failure mode**: concurrent session-start hooks interleaving JSON lines, producing invalid JSONL. Observed at tic 1 and tic 4 on `mandates/history/*.jsonl`.

<!-- promoted from CogPR-8 (tic 4→5). Band: PRIMITIVE. Source: audit-logs/mogul/mandates/history/2026-03-08.jsonl corruption incident. -->

## Runtime Sync Parity Verification

Source-repo correctness does not imply runtime correctness. Hook-invoked scripts resolve from the **installed** location (`~/.claude/cgg-runtime/scripts/`), not from the canonical source repo. A fix committed to the source repo has no effect until the installed copy is synced and verified identical.

**Required sequence** after modifying any hook-invoked script:
1. Commit to source repo (`canonical_developer/context-grapple-gun/`)
2. Copy to installed location (`~/.claude/cgg-runtime/scripts/` or `~/.claude/hooks/`)
3. `diff` source and installed — must be identical
4. Verify hook resolution path reaches the correct file (check `resolve_script` candidates)

**Failure mode**: `inbox-envelope.py` was patched with signal dedup in the source repo but the installed copy at `~/.claude/` lacked the fix. Every SessionStart re-emitted 571 attention-debt signals because the executing script had no dedup guard. The source repo was correct; the runtime was not. Three sessions of cleanup failed to hold because the wrong script kept running.

**Registry is the inbox source of truth, not files**: `detect_stale()` reads from `inbox-registry.json`, not from WAIT files on disk. Deleting WAIT files without archiving registry entries leaves phantom state that hooks re-detect as stale.

<!-- promoted from CogPR-65 runtime-parity finding (tic 91). Band: COGNITIVE. Source: three-layer containment — trigger manifest + registry purge + script sync. Evidence: 571 phantom signals per session, 3 sessions of failed cleanup before root cause identified. -->

## Signal ID Determinism

Signal IDs must be deterministic and condition-stable — derived from the condition being signaled (entity, state, source), not from emission timestamp or session ID. A signal for the same condition across poll cycles must resolve to the same ID so that dedup infrastructure can suppress duplicates.

**Pattern**: Non-deterministic IDs (timestamp-suffix, session-suffix) cause the same condition to appear as N distinct signals per cycle, flooding the manifold. The dedup guard (inbox-envelope.py) is a runtime fix; this rule prevents the class of error at the emitter.

**Constraint**: Signal manifold integrity depends on ID stability — without it, the manifold's active count becomes meaningless noise. The 2305-duplicate incident at tic 91-94 demonstrated that a single non-deterministic emitter can overwhelm the entire signal surface.

**Evidence**: 1150 active WAIT signals from 8 condition-stable IDs each emitted 100+ times (2026-03-15.jsonl). 6 consecutive Mogul audit cycles confirmed. Tic-91 containment fixed symptoms; this rule prevents recurrence.

<!-- promoted from CogPR-66 (tic 94→100). Source: audit-logs/mogul/runs/tic-94-20260316T005800Z-run.json. Evidence: 2305-duplicate incident at tic 91-94, inbox-envelope.py dedup guard, 1150 active WAIT signals with 8 deterministic IDs. -->

## Review Execution Delegation

After `/review` docket is approved, dispatch execution to a `review-execute` subordinate agent — never execute promotions inline in the interactive path.

**Flow:**
1. Present the docket (judgment) → human approves
2. Spawn `review-execute` agent (background, `subagent_type: general-purpose`) with the full verdict table
3. Report completion in one line when notified

**Dispatch payload:** approved verdict table + file targets + review_tic number. The agent reads MEMORY.md for lesson text, writes promoted sections, updates `queue.jsonl` and MEMORY.md metadata. `queue.jsonl` update is the completion gate.

**Fallback:** If `review-execute.md` agent spec is unavailable, spawn a generic background agent with the same instructions.

<!-- promoted from CogPR-9 (tic 5→6). Source: session observation — review-execute.md agent spec at cgg-runtime/agents/review-execute.md. -->

## Plugin Declaration Surface (CGG-Specific)

CGG 4.0.0 demonstrated that component declarations placed in proprietary plugin.json fields (`components`, `install`, `claude_code`) did not register and were replaced in 4.0.1 by marketplace-based declaration. For this repo, the supported fix was `marketplace.json` + `strict: false` plus marketplace-based install flow.

This is a CGG-scope declaration-surface lesson, not federation law. The self-hosting marketplace pattern is the validated install mechanism for plugins with non-standard component paths.

<!-- promoted from CogPR-13 (tic 8→11, arena-refined). Supersedes CogPR-14. Source: npx context-grapple-gun install failure → fix at lib/installer.mjs + .claude-plugin/marketplace.json. -->

## npm Distribution Wrapper

CGG is distributed via npm as `context-grapple-gun`. The npm package is a zero-dep CLI wrapper — `npx context-grapple-gun install` clones the repo and registers the plugin via the self-hosting marketplace pattern. The runtime stays in the plugin; npm orchestrates install only.

- Published: 4.0.0 (initial), 4.0.1 (marketplace fix)
- npm auth requires granular access token with publish scope

<!-- promoted from CogPR-11 (tic 7→11). Source: session planning — user request for npm publishable package. -->

## Subagent Delegation — Schema Contracts

When delegating hook creation or script writing to subagents, include the target script's JSON output schema in the prompt. Subagents that parse another script's output without knowing the schema will write incorrect field paths.

**Failure mode**: Agent wrote `d.get('drifted',0)` but runtime-sync.py nests under `summary.drifted`.

<!-- promoted from CogPR-12 (tic 8→11). Source: canonical/.claude/hooks/federation-sync-check.sh:37. -->

## Mandate Consumption Discipline

If a cadence mandate exists when a session closes, the session must invoke Mogul or explicitly defer. Mandates generated by cadence hooks but not consumed create governance gap windows — cycles queue up but no scan occurs within the session that owns them.

Three consecutive unexecuted mandates at tics 13-15 demonstrated the structural pattern. The activation fabric now handles consumption, but the obligation to invoke or defer is doctrinal.

<!-- promoted from CogPR-26 (tic 16→19). Source: 3 consecutive unexecuted mandates at tics 13, 14, 15. Band: COGNITIVE. -->

## Mogul Mandate Execution Depth Scaling

Mogul mandate execution depth must scale to estate state at mandate creation time. The mandate metadata must include an estate state snapshot (`queue_pending`, `signals_active`, `hazards_open`, `tics_since_last_review`, `tics_since_last_conformation`) so that Mogul can match a run profile at execution time without re-reading the full estate.

Run profiles:
- **verification** (all-clear): compact receipt, no deep scan
- **active** (pending CPRs or recent arena output): targeted assessment of pending items
- **hazard** (open hazards or active signals): full drift check
- **post-review** (inscription verify only): confirm promoted lessons landed

Running identical full cycles regardless of estate state wastes cognitive resources and inflates run artifact noise. Estate-aware depth is a Mogul mandate behavior constraint only — not a general strategic pivot doctrine and not a claim about all federation bottlenecks.

<!-- promoted from CogPR-47 (tic 32→40). Source: PAT-T32-005 + PAT-T36-003 — 5-instance recurrence (tics 26, 32, 34, 36, 39) + tournament cross-bracket convergence (3 agents, 2 brackets). Operator scope note: estate-aware Mogul mandate depth only. Band: COGNITIVE. -->

## Mandate Lifecycle Defects

Mandate lifecycle has three structural defects that refine the Mandate Consumption Discipline (CogPR-26) and Mandate Execution Depth Scaling (CogPR-47):

1. **session-restore.sh overwrites without check** — always writes `current.json` without checking existing pending mandates. Lightweight mandates accumulate as durable obligations. **Mitigated**: tic-level idempotency guard added (checks `current.json` tic before emitting). **Fixed** (tic 108): reconcile-first cycle computation — reads previous mandate `tic_context` as primary schedule, modulo as fallback only.
2. **SessionStart recomputes instead of reconciling** — recomputes cadence from tic modulo instead of reconciling with previous mandate `tic_context`. Creates mandate duplication on session restore. **Mitigated**: `trigger-manifest.yaml` idempotency key changed from `mandate_{tic}_{session_id}` to `mandate_{tic}` with `first_wins` policy. **Fixed** (tic 108): collapsed into reconcile-first in session-restore.sh.
3. **No concurrency guard on inline Mogul spawn** — the review skill can inline-spawn Mogul without checking whether a loop-backed Mogul is already active. **Fixed** (tic 108): concurrency guard added to `/review` SKILL.md steps 5.5 and 8.5 — checks `current.json` status before writing mandates. Race guard added to cgg-gate.sh inline consumption.

**Idempotency key constraint**: The mandate idempotency key must NOT include `session_id` — per-session UUIDs defeat dedup because every session generates a unique ID, making every emission appear novel. The correct granularity is `mandate_{tic}` with `first_wins` policy. Evidence: tic-87 produced 269 inbox messages, 200+ report files, and 328 signal entries from a single-tic runaway caused by `{session_id}` in the key template.

<!-- promoted from CogPR-57 (tic 75→80), extended by CogPR-65 (tic 91). Source: external-audit-verified + mandate runaway containment. Refines CogPR-26 (mandate consumption) and CogPR-47 (mandate depth scaling). Band: COGNITIVE. -->

## Promotion Scope Discipline

Promotion decision is two decisions, not one: (1) is the content valid? (2) what class of doctrine does it belong to? Scope reconciliation must happen before promotion — batch promotion from census evidence is especially prone to scope collapse.

Doctrine class taxonomy:
- **CLAUDE.md** = active implementation doctrine (constraints that shape agent behavior)
- **Memory files** = born truth, structural design, architectural read (reference material, not law)
- **Risk map** = performance hazard doctrine (operational guardrails)

**Failure mode**: Foreground review without scope reconciliation against Mogul analysis caused 5 of 6 CogPRs routed to wrong target at tic 75.

<!-- promoted from CogPR-58 (tic 75→80). Source: operator-correction. Reinforced tier. Band: COGNITIVE. -->

## Cadence Downbeat Enforcement

Cadence downbeat must enforce a strict sequence: emit tic event, then write conformation, before the tic counter advances. The tic count hook must count only non-ignored tic events — counting all tic events including `count_mode: "ignored"` produces phantom ticks that desynchronize the tic counter from the conformation history.

12+ missing conformations across governance history trace to this root cause. The downbeat sequence is: (1) emit tic event with `count_mode: "counted"`, (2) write conformation snapshot, (3) advance counter. Any other ordering or omission breaks the tic-conformation invariant.

<!-- promoted from CogPR-43 (tic 27→32). Source: PAT-T31-002 pattern mining + HAZARD-T31-A runtime drift check. 5+ recurrences, 2 consecutive hazards. Band: COGNITIVE. -->

## Lead Context as Binding Constraint

Lead context accumulation — not advocate turn count — is the binding budget constraint in governed arenas. The lead receives ALL advocate outputs: N advocates × M turns each = N×M messages accumulating in lead context. Advocate budgets are local (bounded per-agent), but lead context is global (accumulates across all agents).

The routing function must check lead context ceiling across all regimes before spawning.

<!-- promoted from CogPR-32 (tic 21→22, arena-sourced T3G). All three advocates independently identified this as the binding constraint. Band: COGNITIVE. -->

## Coordination Overhead Accounting

Coordination overhead (nudges, retries, phase-transition messages) is lead-side cost, not advocate-side cost. Advocate budgets should price reasoning depth only. Conflating coordination with advocacy inflates budget estimates.

This accounting correction changed the LIBERAL regime derivation from 28 to ~22 turns/advocate — coordination overhead was incorrectly counted as advocate budget consumption.

<!-- promoted from CogPR-35 (tic 21→22, arena-sourced T3G). All three advocates independently confirmed this accounting principle. Band: COGNITIVE. -->

## Epistemic Triangulation Geometry

Epistemic triangulation (coincidence/mechanism/counterfactual) is an effective geometry for hypothesis-testing arenas. Each angle tests a different failure mode of the claim:
- **Coincidence** — could the evidence be explained by chance or confounding?
- **Mechanism** — is there a causal pathway connecting the claim to the evidence?
- **Counterfactual** — what would we expect to observe if the claim were false?

Use this geometry when the arena question is a testable hypothesis rather than a design choice.

<!-- promoted from arena-marketplace-0 (tic 9→25, arena-sourced marketplace-epistemic-triangulation). Process lesson — reinforced confidence tier. Band: COGNITIVE. -->

## Governance Label Accuracy

'Observer-first' is a governance label that systematically understates commitment. If the model includes synchronous pre-action checkpoints at critical boundaries (cost, publish, destroy), the model is 'governed-at-boundaries' and the label should match. Labels shape investment decisions — a mislabeled pattern will be under-resourced where it matters most.

<!-- promoted from CogPR-73 (tic 102→105). Source: arena:triad-fusion-authority-arena — Wildcard Record #5 (semantic downgrade), governance-examiner rebuttal, all agents converged on gates at cost/publish/destroy. Band: COGNITIVE. -->

## Same-Model Convergence Discount

Same-model agent convergence is weaker than cross-model convergence. Same-substrate agents satisfy incentive independence (opposed mandates) but not epistemic independence (shared priors). Downgrade same-model convergent findings to REINFORCED until validated by implementation evidence.

<!-- promoted from CogPR-76 (tic 102→105). Source: arena:triad-fusion-evidence-rebuttal — same-substrate shared priors observation. Tentative confidence; CGG scope first, federation promotion pending cross-model arena validation. Band: COGNITIVE. -->

## Concession Cascade Detection

Evidence-rebuttal concession cascade: when evidence advocate concedes all claims, check for role abandonment vs claim adjustment. Lead must verify empirical evidence perspective survives even when specific evidence base is thin. Concession cascade produces bilateral consensus, not triangulated convergence.

<!-- promoted from CogPR-77 (tic 102→105). Source: arena:triad-fusion-evidence-rebuttal — evidence advocate conceded all claims, bilateral consensus ≠ triangulated convergence. Band: COGNITIVE. -->

## Arena Velocity Guard

When arena convergence happens faster than evidence accumulation, treat the consensus as a hypothesis set, not a decision set. Each consensus point needs an explicit falsification condition. The wildcard strike-down question ('what would the smart-but-wrong version be?') applied to each point before ratification guards against elegant plans nobody can build.

<!-- promoted from CogPR-74 (tic 102→105). Source: arena:triad-fusion-authority-arena — 8 consensus points in 3 phases, Wildcard Records #3 and #8, strike-down question technique. Complements CogPR-33 (convergence timing). Band: COGNITIVE. -->

## showClearContextOnPlanAccept Must Be True

CGG cadence depends on plan-mode context-clear as the session epoch boundary. When false (the default as of Claude Code with 1M context), clear-context options are suppressed in the plan approval menu, replacing them with keep-context variants. This silently breaks the cadence handoff chain (plan approve + clear -> session-restore.sh -> trigger extraction -> assessor spawn). Set `showClearContextOnPlanAccept: true` in `~/.claude/settings.json` for any CGG-governed workspace.

<!-- promoted from CogPR-78 (tic 104→107). Source: binary-analysis-claude-code-2.1.81. Evidence: binary-verified — flag controls first option in plan approval menu, cadence handoff chain restored after setting true. Band: COGNITIVE. -->

## Session Learning Protocol

When you discover something during a session that constitutes a durable lesson — a friction point resolved, a non-obvious behavior confirmed, a workflow correction — capture it as a CogPR (Cognitive Pull Request).

### Write rule (born truth vs in-force truth)

Write lessons to MEMORY.md by default (born truth). Only write to CLAUDE.md when the lesson IS a law change (in-force truth). If no subsystem MEMORY.md exists, write to the project's auto-memory (`~/.claude/projects/*/memory/MEMORY.md`).

### CogPR format

Write the lesson inline, then add this flag immediately after:

<!-- --agnostic-candidate
  lesson: "one-line lesson summary"
  source_date: "YYYY-MM-DD"
  source: "file:line"
  band: "COGNITIVE"
  motivation_layer: "COGNITIVE"
  subsystem: "relevant_subsystem"
  recommended_scopes:
    - "path/to/broader/CLAUDE.md"
  rationale: "why this is broader than local"
  review_hints: "what to check when evaluating"
  status: "example"
-->

> Set `status: "pending"` on real CogPRs. The template uses `"example"` to avoid false positives in the inline CPR scanner.

### Birth discipline

Never delay birth of a pattern-shaped CogPR on the grounds of maturity. Capture first. Prove later. Promote only when earned.

- If the observation is pattern-shaped (recurring, structural, or contract-level), mint the CogPR immediately at birth tic.
- Maturity governs **promotion**, not **capture**. Losing the hypothesis is system failure; premature promotion is recoverable.
- For external platform contract surfaces (hook schema, plugin manifest, install semantics, marketplace protocol), capture hypotheses immediately — do not legislate from memory when contract validation is available.

### Band budget

| Band | Use for |
|------|---------|
| PRIMITIVE | Safety, data integrity, survival signals |
| COGNITIVE | Learning, discovery, process improvement (default) |
| SOCIAL | Collaboration signals (use sparingly) |
| PRESTIGE | Never. Governance-blocked. |

Run `/cadence` when the session feels long — around 100k tokens is a good heuristic. If context is degrading, `/cadence double-time` does a minimal exit. The `cadence-syncopate` command surface remains valid and supported.

### Experimental arena cadence isolation

Events inside experimental arenas may be recorded, but they do not advance physical cadence by default. Only operative-zone execution advances the physical tic counter.

When cadence is emitted from experimental closeout or other ignored contexts, emit a normal tic event (`type: "tic"`) with:

- `count_mode: "ignored"`
- `count_reason: "<explicit reason>"`
- `domain_counter_before == domain_counter_after`
- `global_counter_before == global_counter_after`

Do not fork the event type. The distinction is counting mode, not event existence. One event model, one scanner, one audit surface.

### Timestamp authority law

If timestamps are not canonical, they must never be used as authoritative ordering fields. Use tic, phase, dependency completion, or explicit operator-metadata labels instead. Canonical progression is determined by counted tic progression, not by wall-clock timestamps.

For arena reports and other non-canonical surfaces, prefer tic-based closure:
```json
{"source_tic": 9, "completion_tic": 9, "phase_closure": {"context": "complete", ...}}
```
not authoritative-looking wall-clock sequencing (`created_at`, `completed_at`).

### Posture (optional)

Declare your working mode at session start:

| | DIRECT (execute) | META (analyze) |
|---|---|---|
| **ENG** | Implement, fix, ship | Architect, plan, design |
| **OPS** | Run pipelines, hit APIs | Audit, review, explore |

When capturing a CogPR, include `posture: "ENG/META"` (or whichever
mode applies). This helps `/review` weigh context — a lesson from active
implementation carries different weight than one from analysis.

Posture is advisory in CGG. Substrates that enforce posture constraints
(META = read-only, etc.) use the same fields — zero migration on upgrade.

### Signal format

For persistent conditions that need tracking, emit signals to `audit-logs/signals/YYYY-MM-DD.jsonl`. Use /siren for signal management if installed.

### Topology

Run `cgg-doctor.sh` from your project root to see your governance topology.
