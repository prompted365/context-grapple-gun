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

## Overlap-Frequency Tiering Primitive

Overlap-frequency tiering is a reusable prioritization primitive for competitive and comparative analysis: features all competitors share = table stakes (necessary but not differentiating), some share = opportunity zone (competitive leverage), one has uniquely = differentiation (strategic advantage). Apply this tiering to any domain where multiple entities are compared across feature sets — SEO landscapes, capability surfaces, vendor assessments. The primitive appeared in 12/20 prompts during harpoon assessment with demonstrated live cross-domain instantiation.

<!-- promoted from CogPR-81 (tic 109→115). Source: arena:harpoon-alventra-seo-assessment — convergent (HARVEST+MINE advocates). Cross-domain applicability demonstrated in SEO, capability, and vendor assessment contexts. Band: COGNITIVE. -->

## CATALYZE Advocate Geometry

Harpoon assessment arenas benefit from a CATALYZE advocate position that argues for higher-leverage constitutional alternatives, replacing binary PASS/NO with phased convergence. The CATALYZE advocate's role: when a harpoon item fails direct adoption, identify what constitutional primitive it could become through transformation. This produces richer assessment output — items are not just accepted or rejected but classified along a spectrum from direct-adopt to constitutional-extract to reject.

<!-- promoted from CogPR-82 (tic 109→115). Source: arena:harpoon-alventra-seo-assessment — reinforced. Process improvement for arena geometry, validated in practice during harpoon assessment. Band: COGNITIVE. -->

## Copilot Script Classification (tier_2_adapt)

External prompt systems that require human execution (e.g., "Open Chrome and navigate to...") are most accurately classified as `tier_2_adapt` — copilot scripts, not agent-executable envelopes. The "Open Chrome" pattern is a reliable signal of copilot-script dependency. Assessment should separate pattern value (the reasoning structure may be reusable) from execution mechanism (human-in-the-loop vs agent-executable). This sharpens harpoon assessment by preventing misclassification of human-dependent prompts as directly ingestible automation.

<!-- promoted from CogPR-84 (tic 109→115). Source: arena:harpoon-alventra-seo-assessment — reinforced. Practical operational value for harpoon assessment classification. Band: COGNITIVE. -->

## Cross-Rung Orientation (CRX) Arena Geometry

CRX is the 6th arena geometry template, designed for cross-rung and cross-jurisdiction exploration. Structure: triad (domain-level reasoning with opposed advocates) + meta-pair (constitutional emissaries with expansion/constraint polarity) + ecotone synthesis (mechanical derivation from both polarity gates). The meta-pair catches what triads miss — specifically complementary-jurisdictions violations and suppressed emergence. First CRX run produced qualitatively different output from standard governed triangulation. Use CRX geometry when the arena question spans jurisdictional boundaries or rung levels.

Template location: `stage/templates/arenas/cross-rung-orientation/`

<!-- promoted from CogPR-88 (tic 109→115). Source: arena:occ-identity-primitives-crx — reinforced. First run validated qualitative difference from governed triangulation. Meta-pair caught complementary-jurisdictions violations the triad missed. Resolves BEACON_crx_geometry_validated. Band: COGNITIVE. -->

## Recursive Meta-Enforcement

Schema-level enforcement of governance requirements can be formally satisfied while substantively violated — a mandatory dissent field satisfied by writing "No dissent." is compliance theater. The response is recursive meta-enforcement: mechanisms watching mechanisms. When a governance schema requires a field (unresolved tensions, dissent, surprise assessment), the enforcement layer must also check whether the field's content is substantively meaningful, not just syntactically present. This applies to any schema-enforced governance requirement and extends concession cascade detection (CogPR-77) from arena-specific to system-wide.

<!-- promoted from CogPR-93 (tic 112→115). Source: arena:occ-epistemic-safeguards-crx — convergent. MECHANIST form-vs-substance analysis + LAWFUL iterative enforcement. Extends CogPR-77 (concession cascade). Resolves BEACON_occ_epistemic_governance_convergence. Band: COGNITIVE. -->

## NIH Self-Examination in Adversarial Arenas

In governed adversarial arenas, advocates arguing for build-alternative positions (CATALYZE, build-from-scratch, replace-with-custom) must include a mandatory NIH (Not Invented Here) self-examination: an honest numeric self-score (0-10) assessing how much of their advocacy is driven by NIH bias versus genuine gap analysis. Advocates who honestly assess their own failure modes produce genuine convergence; advocates who cannot produce bilateral stalemate. The NIH self-score is the mechanism that releases deadlocked positions into shared territory.

<!-- promoted from CogPR-108 (tic 118→119). Source: arena:harpoon-federation-mount-binder-v2-assessment — reinforced. CATALYZE's 5.5/10 NIH self-score released 3 of 5 gaps from exclusive to shared territory, making consensus partition possible. Band: COGNITIVE. -->

## Opposing-Values Geometry for Constitutional Questions

Constitutional questions (expansion, restructuring, inscription, authority changes) should use opposing-values arena geometry where advocates hold genuinely different values (e.g., completeness vs coherence vs efficiency), not same-direction geometry where advocates agree on value but differ on approach. Opposing-values geometry produces higher lock-pressure, surfaces absorption capacity concerns, and generates analytical tools (e.g., non-derivability test) that same-direction geometry cannot produce. Same-direction geometry produces low lock-pressure everywhere because advocates agree on valence — method disagreement does not generate the constitutional stress-testing that value disagreement does.

<!-- promoted from CogPR-112 (tic 118→119). Source: arena:harpoon-binder-v2-constitutional-impact — reinforced. Direct empirical comparison: Arena 1 (same-direction) produced low lock-pressure and no analytical tools; Arena 2 (opposing-values) produced the non-derivability test (CogPR-110) and structural reform mandates. Band: COGNITIVE. -->

## Post-Hoc Conformation (Anti-Pattern: In-Arena Invariant Scoring)

Do not ask arena advocates to score their positions against invariants during their turns. In-arena invariant scoring distorts advocate reasoning — advocates checklist-optimize against the scoring criteria instead of reasoning naturally from their value positions. The correct design is post-hoc conformation: advocates speak from values without scoring awareness, then an invariant field measurement is applied after advocacy completes. This separation is load-bearing — it preserves the authenticity of advocacy while still capturing invariant alignment data.

<!-- promoted from CogPR-114 (tic 118→119). Source: session:harpoon-binder-vpl-design-tic-118 — reinforced. Arena 1 experimental invariant weight scaffold demonstrated checklist-optimization distortion. VPL spec Phase 6 (post-hoc conformation) is the validated alternative. Band: COGNITIVE. -->

## VPL Standard Geometry (Tournament-Lattice)

Tournament-lattice VPL (Value-Position Lattice) with bracket isolation and wildcard challenge is the standard geometry for federation governance shape questions. The geometry combines three validated principles:

1. **Constitutional actors as advocates** — office holders (Mogul, Crisis Steward, CBUX, Civil Engineer, Ladder Auditor) have natural value centroids from jurisdictional mandates and natural evidence bases from operational data. Using them instead of generic labels produces advocates with authentic stakes.
2. **Value-position fusion** — constitutional actors naturally fuse value-driven and position-driven stances in a single lattice. Their jurisdictional mandates ARE value centroids; their operational data IS positional evidence. VPL achieves what separate arena types cannot.
3. **Wildcard chain coherence challenge** — the wildcard finds composite tensions invisible to bracket-isolated advocates. Every constitutional VPL arena must include a chain coherence wildcard.

Template: `stage/templates/arenas/value-lattice/spec.md`

<!-- promoted from CogPR-116 merged with CogPR-113 + CogPR-115 (tic 118→119). Source: arena:federation-governance-shape-vpl — convergent. Wildcard found 3 composite tensions invisible to 12 bracket documents. Constitutional actors produced office-specific evidence unavailable to generic labels. First VPL run validated the geometry. Band: COGNITIVE. -->

## Hook Path Resolution

Hook scripts must discover zone root by walking up from the **edited file path**, not from `cwd`. Hooks execute in an arbitrary working directory set by the harness (often `~` or other external paths), not by the project. Using `os.getcwd()` or `$CLAUDE_PROJECT_DIR` as the primary zone root anchor silently fails when cwd is outside the federation tree. The file path (`$CLAUDE_FILE`)is the only reliable anchor to discover zone root via directory traversal.

**Pattern:** Walk up from `$CLAUDE_FILE` looking for `.ticzone` or `audit-logs/`, not from `cwd`.

**Failure mode:** Hook returned silence from `~/`; full output from `canonical/` — same input JSON, different cwd. Zone root resolution from file path walked up correctly in all 4 tests. Existing post-commit-sync.sh had the same latent bug masked by git commit always running from repo dir.

<!-- promoted from CogPR-127 (tic 122→124). Source: session:sync-weigh-hook-tic-121. Zone root resolution validated walking up from file path in all test cases. -->

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

## Bash-Python Quoting Collapse

Inline Python in bash heredoc (`python3 -c "..."`) silently breaks when the Python code contains triple-quoted docstrings — bash C-style quoting (`$'...'`) mangles triple quotes into string terminators. The fix is to extract Python logic to a separate `.py` file and have the bash hook invoke it. This is a syntax-semantic collapse vector specific to hook authoring: bash and Python have incompatible quoting semantics that produce silent failures (no error, no output, exit 0 under `set -e`).

**Pattern**: When a hook needs non-trivial Python logic, write a `.py` file and call it from bash — never inline Python with heredoc or `-c` quoting.

<!-- promoted from CogPR-126 (tic 122→128). Source: session:sync-weigh-hook-tic-121. Evidence: bash -x trace showed $'Count' uncommitted' — triple-quote docstring mangled. Hook produced exit 0 with no output. Fixed by extracting to sync-weigh-check.py. Supports syntax-semantic collapse doctrine (canonical/CLAUDE.md). Band: COGNITIVE. -->

## OA-VPL-T Arena Geometry

OA-VPL-T (Office-Autonomous Value-Position Lattice with Temporal Modeling) is the 8th arena geometry template. Founding principle: **friction is evidence of hidden constitutional structure** — the revision trail from implementation friction is the excavation trail of the invariant stack. Key innovations: Phase 0a/0b (offices derive positions from mandate, not assigned labels), dependency-emergent brackets, and T0-T5 temporal tension modeling with Temporal Fraud as highest penalty.

Template: `stage/templates/arenas/office-autonomous-vpl/spec.md`

<!-- promoted from CogPR-128 (tic 122→128). Source: session:oavplt-design-tic-121. Evidence: convergence synthesis between c45 (federation-grounded) and oa54 (framework-level). Validated by 2 arena instances (sync-weigh + OT-integration). Refines arena template system, supports CogPR-112 (opposing-values geometry). Band: COGNITIVE. -->

## Install Boundary as Governance Transition

The forge→runtime install boundary (`canonical_developer/` → `~/.claude/`) is a first-class governance transition, not merely a file copy. Properties valid at the forge (syntax correctness, test passage, manifest consistency) are not automatically valid at the runtime. Derived constraints of this transition include: manifest atomicity, dual-read consistency, error transparency, and recursive self-observation. One structural anchor with derived rules is a tighter promotion footprint than independent inscriptions for each derived constraint.

This refines the Three-Form CGG Boundary (canonical/CLAUDE.md) with an operational principle: the install boundary is where governance properties must be re-verified, not assumed.

<!-- promoted from CogPR-130 (tic 122→128). Source: arena:sync-weigh-friction-oavplt — 5/7 office convergence. Ladder Auditor structural anchor framing validated. DIRECT-D enrichment: one structural anchor with derived rules is a tighter promotion footprint than seven independent inscriptions. Band: COGNITIVE. -->

## Detection Affordance Tracking

Promoted invariants should carry `detection_affordance` metadata tracking whether a detection mechanism exists. This is advisory at review time, not a blocking gate. Entries marked `"pending"` generate queue-refresh follow-up obligations. The metadata tracks the gap between inscription and enforcement — an invariant without a detection mechanism is a mandate without mechanism (F-2 pattern).

Format in promotion comments: `detection_affordance: active|pending|none`

<!-- promoted from CogPR-131 (tic 122→128). Source: arena:sync-weigh-friction-oavplt — 6/7 office convergence. Extends enforcement integrity (CogPR-100). Resolves the monitored-invariant concept: advisory question at review + metadata flag + follow-up obligation. Band: COGNITIVE. -->

## Friction-to-Invariant Pipeline

Implementation friction generates invariant candidates through a recurring pipeline: friction → debugging → root cause → candidate → naming → promotion. The pipeline itself is a governance primitive — friction density predicts candidate generation rate. The sync-weigh implementation produced 7 friction invariant candidates from one implementation, validating the pattern. The constitutional learning is the pipeline shape, not the individual candidates it produces.

<!-- promoted from CogPR-132 (tic 122→128). Source: arena:sync-weigh-friction-oavplt — Pattern Curator Meta primary, Bracket B convergence, 5/7 office agreement. Meta-process observation about how arenas discover invariants. Band: COGNITIVE. -->

## Recursive Self-Observation

When a governance configuration surface is consumed by the mechanism it governs, the system exhibits recursive self-observation — the observer observing itself. This is constitutionally distinct from linear enforcement (CogPR-100): enforcement integrity addresses distributed layers detecting distinct failure modes, while recursive self-observation addresses a single mechanism that is both enforcer and governed surface. Non-derivability from CogPR-100 confirmed — these are structurally different phenomena.

Live evidence: `sync-manifest.json` consumed by `sync-weigh-check.py` which checks manifest drift; `active-manifest.jsonl` created as fix for signal scan blind spot.

CGG scope — promote to federation if second subsystem instantiation emerges.

<!-- promoted from CogPR-133 (tic 122→128). Source: arena:sync-weigh-friction-oavplt — triple convergence (Pattern Curator Meta, cbUX, Videographer). Non-derivability vs CogPR-100 adjudicated: PASS. Resolves sig_2026-04-08_arena_fi7_nonderivability_open. Band: COGNITIVE. -->

## Encounter Quality Upstream of Signals

The governance encounter surface (hook output at edit time) is constitutionally upstream of signal infrastructure. If the encounter fails — silent hook, wrong path resolution, ambiguous output — the governance signal never fires. The manifold's health depends on encounter surface reliability. A silent exit-0 does not just frustrate the developer — it blinds the governance layer. Encounter quality is a load-bearing governance component, not a UX convenience.

<!-- promoted from CogPR-134 (tic 122→128). Source: arena:sync-weigh-friction-oavplt — reinforced across 3 arena offices (cbUX primary, Videographer + Pattern Curator Meta supporting). Crisis Steward's 2305-duplicate incident as causal evidence. Complements CogPR-130 (install boundary anchor). Band: COGNITIVE. -->

## Spec-First Parallel Swarm

Write complete spec surface BEFORE launching implementation agents. Agents read specs as their constitution — the spec is the agent's mandate, not a reference document. This eliminates the headless subagent curation problem (documented in global CLAUDE.md "Headless Subagent Delegation") by making the spec authoritative rather than relying on inline appendices. The temporal ordering is load-bearing: spec authoring must complete before agent spawning begins.

Validated at scale: 13 spec tranches → 12 implementation engines, 86/86 artifacts verified correct.

<!-- promoted from CogPR-135 (tic 125→128). Source: session:tic-125 megabuild. Evidence: largest implementation session in federation history — 13 tranches, 12 engines, 86/86 verified. Distinct from global "authoritative appendices" guidance — this is about temporal ordering of spec authoring vs agent spawning. Band: COGNITIVE. -->

## Composite Mutation Assessment at LEAD Level

CogPR-117 (composite mutation scheduling) is systematically invisible to advocate-level reasoning in governed arenas. Offices assess their own constitutional surface changes individually but never assess the composite. The wildcard chain coherence mechanism is the only reliable detection surface. Composite assessment must be enforced at LEAD/synthesis level as a mandatory Phase 6 deliverable, not left to advocate initiative.

<!-- promoted from CogPR-140 (tic 126→130). Source: arena:2026-04-09_ot-economic-integration-oavplt. Note: CD-5. Convergent: wildcard found, confirmed by conformation analysis (dead zone classification). Band: COGNITIVE. -->

## Wire-Cut Scoping by Capability Class

Containment wire-cuts must be scoped to capability classes (ingress, all, panic), not binary on/off. The Docks wire-cut spec demonstrates the pattern — three graduated scopes preserve maximum capability while containing the specific threat vector. Binary wire-cuts (everything or nothing) over-contain, causing collateral damage that discourages use of containment altogether.

<!-- promoted from CogPR-145 (tic 129→138). Source: pattern_miner:PAT-T129-DIRECT-A — reinforced. Docks wire-cut implementation validates graduated scoping. Crisis subsystem scope. Band: COGNITIVE. Confidence: 0.85. -->

## Authoritative Count Discipline

Governance reporting tools must source counts from authoritative state (physical event files, active manifests), not from configuration or raw unfiltered logs. bench-packet-prep.py silently reported tic=0 (from .ticzone config) and signals=290 (from raw logs) instead of tic=134 (from counted events) and signals=5 (from curated manifest). Extends CogPR-79 (spot-check output against source data) with a specific authoritative-source discipline.

<!-- promoted from CogPR-146 (tic 135→138). Source: session:tic-135. Evidence: bench-packet-prep.py sourced tic from config and signals from unfiltered logs, producing dramatically wrong counts. Extends CogPR-79. Band: COGNITIVE. Confidence: 0.92. -->

## Dedup-at-Write Using Canonical Identity

Duplicate detection must occur at the write boundary (physics layer) keyed on canonical record identity (signal_id, CPR id), not at scan time or by content hash. `dedup_signal_append()` in `atomic_append.py` demonstrates the pattern — one enforcement point, four emitters. This is distinct from atomic writes (CogPR-8, corruption prevention) and signal ID determinism (CogPR-66, ID stability) — this addresses where and how dedup enforcement happens: at the write boundary, using canonical identity as the key.

<!-- promoted from CogPR-147 (tic 135→138). Source: session:tic-135. Evidence: dedup_signal_append() in atomic_append.py — 4 emitters already using write-boundary dedup. Complements CogPR-8 (atomic writes) and CogPR-66 (signal ID determinism). Band: COGNITIVE. Confidence: 0.90. -->

## Pattern Mining Context Procurement

Pattern mining context procurement must precede mining — a briefing covering governance surfaces with NLP heuristics (bigram frequency, Gini coefficient, temporal clustering, entity co-occurrence) empowers mining agents with statistical shape without claiming to catch patterns. Three-tier posture (briefing+inline / interactive / full team) guards against cognitive drain while ensuring surface coverage. Validated: briefing-first approach empowered the pattern-curator to discover MEMORY.md truncation that a script couldn't.

<!-- promoted from CogPR-149 (tic 136→138). Source: session:tic-136. Evidence: pattern-mining-context.py + three-tier posture validated in practice. Shapes Mogul's agent-spawning behavior for pattern mining. Band: COGNITIVE. Confidence: 0.82. -->

## Hook Binary Invocation (No Aliases)

Hook scripts must call binaries directly, never shell aliases — aliases live in interactive shell config (.zshrc) and do not survive non-interactive invocation. Dedup by content hash prevents duplicate firing at event boundaries. Complements Hook Path Resolution (CogPR-127) which covers zone root discovery but not invocation resolution.

**Pattern**: Use full binary paths (`/usr/bin/python3`, `$(which tmux)`) in hook scripts, never aliases or functions from shell profiles.

<!-- promoted from CogPR-150 (tic 136→138). Source: session:tic-136. Evidence: alias resolution failure in hook invocation + content-hash dedup prevents duplicate firing. Complements CogPR-127 (Hook Path Resolution). Band: COGNITIVE. Confidence: 0.88. -->

## Inter-Engine Integration Emission

When two engines share state through a registry file, the producing engine must emit records in the consuming engine's expected format. Each engine may be individually correct while the integration surface is a blind spot. 14 cycles of invisible integration failure between biome-engine and trust-engine demonstrated the pattern — each engine passed its own tests, but the integration surface was never verified. Extends CogPR-79 (spot-check output against source) to cross-system integration verification.

<!-- promoted from CogPR-151 (tic 136→138). Source: session:tic-136. Evidence: 14 cycles of biome→trust invisible failure. Each engine individually correct; integration surface unverified. Extends CogPR-79 to inter-engine integration. Band: COGNITIVE. Confidence: 0.92. -->

- **Integration loop closure requires explicit invocation wiring** — each engine individually correct and sharing correct-format state is necessary but not sufficient for integration. The data-producing engine must explicitly invoke the data-consuming engine after state persistence. Invocation IS the integration, not data format. This extends CogPR-151 (format compliance) to call-path presence: engines may share perfectly formatted data yet produce silent zero-output because no engine calls the next one. The protection is an explicit orchestrator (e.g., trust-progression-cycle.py) that sequences produce → persist → consume as a single governed pipeline. (Validated: biome→trust→standing loop — 3 engines, correct formats, 18 cycles of interaction data, 0 trust computed. Root cause: no call path connected them. Orchestrator closed the loop immediately.)

<!-- promoted from CogPR-178 (tic 145→146). Source: session:visitor-phase1-dry-run. -->

## Named-Is-Not-Landed Gate

A complement surfaced in a prior mode but not yet materialized remains a valid complement. The structural relevance test must evaluate complement state (built vs named vs unnamed), not just recent-output presence. First calibration evidence from /complement invocation log — the gate correction shapes skill behavior by requiring materialization state assessment before declaring a complement irrelevant.

<!-- promoted from CogPR-152 (tic 136→138). Source: session:tic-136. Evidence: first /complement calibration. Gate correction: evaluate complement state, not just recent-output presence. Band: COGNITIVE. Confidence: 0.82. -->

## Contamination Lifecycle and Forensic Investigation Discipline

Third-party software contamination follows a structural lifecycle: (1) silent environment mutation (shell profile injection, proxy redirection without ToS disclosure), (2) persistence mechanisms (auto-launch override via internal config sync that resists user intervention, provider env.sh writes on every launch), (3) data residuals surviving removal (macOS drag-to-Trash removes only .app bundle; ~/Library data, launch agents, keychain entries, auto-updaters persist — observed: 9.4GB across 19 directories from 3 apps).

Detection requires three complementary systems: file-integrity drift (did watched files change — high confidence, after-the-fact), baseline deviation (new env vars, launch agents, proxy settings — high confidence, after-the-fact), live attribution (what process is touching files now — medium confidence, real-time only). 'Who changed this file' cannot be recovered after the fact without pre-existing auditing.

Investigation discipline: enforce app identity separation at the top of any multi-app investigation (per-app evidence buckets, shared-framework hypotheses explicitly labeled). Separate observed fact (entitlement exists, local server exists, bundled runtime exists) from inferred risk (possible interception surface, possible exfil path). Require proof threshold before strong verbs — use 'creates a surface for,' 'permits,' 'is capable of' until runtime evidence of activation exists. Entitlement proof first, runtime/process inventory second, network/socket verification third, source-level code inference last.

<!-- promoted from CogPR-170/171/172/173 merged (tic 141-143→143). Source: Genspark forensic investigation tic 141-143. Band: PRIMITIVE. detection_affordance: active (contam_sentinel.py). -->

## Accessibility API Structural Indistinguishability

Cross-app activity tracking via accessibility API is structurally indistinguishable from legitimate dictation context — the app needs focused_app_bundle_id to deliver text. The invasive choice is persisting and syncing that data, not collecting it. Detection requires inspecting the local database schema for sync tables and cross-app indexes, not monitoring runtime behavior.

<!-- promoted from CogPR-175 (tic 142→143). Source: Speakly genspark-flow.db analysis. Depends on: MERGE-A (three detection systems). Band: COGNITIVE. detection_affordance: pending. -->

## Competing Canons / Hardening Pass Obligation

Report artifacts that span an iterative build accumulate competing canons when the approach changes mid-session but earlier sections aren't rewritten. A report that describes abstract scalar-bar b-roll in sections 1-5 and morph-based narrative scenes in section 11 carries two incompatible descriptions of the same deliverable. The hardening pass (rewriting the top-level story to match the final winning approach while preserving the forensic record of how the pipeline got there) is a distinct authoring obligation, not a polish step.

<!-- promoted from CogPR-161 (tic 139→143). Source: session:podcast-pipeline-ep31. Band: COGNITIVE. detection_affordance: pending. -->

## Baseline Re-Anchoring After Intentional State Change

Integrity sentinels that detect remediation-era changes must be rebaselined immediately after cleanup completes. The baseline captures pre-remediation state — disappeared malware agents, shifted mdworker populations, etc. — creating false-positive noise that obscures real future drift. Rebaseline-after-remediation is the correct sequence: init → detect → remediate → rebaseline → monitor clean state. Without the rebaseline step, the sentinel's first clean-state check inherits all the remediation delta as 'drift', triggering high-volume signals (vol 50) that are entirely self-referential.

<!-- promoted from CogPR-176 (tic 143→143). Source: contam_sentinel.py vol 50 self-referential bootstrap signal. Band: COGNITIVE. detection_affordance: active (contam_sentinel.py rebaseline). -->

## Multi-Session Artifact Provenance

Forensic reports spanning multiple investigation sessions must carry explicit per-finding timestamps, not a single document date. The tic-142 deep analysis invalidated a key claim from the tic-141 initial report: 'App did NOT recontaminate on restart — injection was one-time onboarding action.' The correction (TokenProvider fires on every launch) was only possible because the second session tested what the first session assumed. Reports with a single date create a false impression of static, complete findings. The fix: each finding carries its own discovery timestamp and confidence level, and corrections to prior findings are marked explicitly as corrections with the original claim cited.

<!-- promoted from CogPR-177 (tic 143→143). Source: Genspark forensic binder — prior session's one-time claim corrected. Band: COGNITIVE. detection_affordance: pending. -->

## Drift Classification Taxonomy

When auditing an adapter for API drift, classify each line as: accurate (matches current docs), likely stale (was accurate, drift detected), unverified from public docs (may work but not documented), or custom layer (our orchestration, not an API claim). The classification taxonomy prevents conflating adapter-specific orchestration code with actual API contract violations. The TS overshoot adapter had 6 custom-layer files that were architecturally sound but would have been flagged as drift without this distinction.

<!-- promoted from CogPR-163 (tic 140→143). Source: session:overshoot-adapter-audit. Operationalizes Volatility Handling Law L3/L5. Band: COGNITIVE. detection_affordance: pending. -->

## Single Routing Surface for Generation and Adjudication

External media API routers (generation + adjudication) should share a single routing surface and budget. Generation asks 'make this' and adjudication asks 'is this good?' — both are media egress, both cost money, both need audit trails. Splitting them by provider rather than by function fragments the spend surface.

<!-- promoted from CogPR-162 (tic 140→143). Source: session:overshoot-adapter-audit. Extends cognitive budget routing. Band: COGNITIVE. detection_affordance: pending. -->

## Overlay-at-Timestamp Assembly

B-roll assembly must use overlay-at-timestamp (video replaces speaker footage at specific time windows), not insert-between-segments (video spliced into the timeline). Insert-based assembly adds duration to the video track without adding duration to the audio track, causing cumulative sync drift after every insertion. The audio spine is continuous and untouched; the visual layer swaps at precise windows.

<!-- promoted from CogPR-158 (tic 139→143). Source: session:podcast-pipeline-ep31. Band: COGNITIVE. detection_affordance: pending. -->

## Morph Transition Grammar

Morph transitions are atomic compound operations: (1) keyframes must come from different visual worlds — two real frames produce camera interpolation, not transformation; (2) OUT morph chains from IN morph's actual last frame (pose continuity); (3) editorial trims must not land inside morphing zones — cutting mid-morph produces visible breaks. EDL needs continuity_type per b-roll slot.

<!-- promoted from CogPR-155/167 merged (tic 139-141→143). Source: session:podcast-pipeline-ep31 + Ep31 reel analysis. Depends on: CogPR-158 (overlay method). Band: COGNITIVE. detection_affordance: pending. -->

## Temporal Scope Discipline

- **Federation-scoped tic resolution for duration measurement** — governance functions measuring duration in federation tics must resolve from the canonical tic log (`audit-logs/tics/*.jsonl`, field: `domain_counter_after`), not from domain-scoped counters in data files. Domain data files store domain-local cycle counters that do not map to federation time. The failure mode is silent zero-output: a duration function reads a biome-scoped `cycle` counter instead of the federation tic log's `domain_counter_after`, returning 0 for all entities despite 14+ tics elapsed. The rule: any function parameterized by federation tics must source its temporal data from the tic log. (Validated: standing-engine time-at-standing returned 0 for all visitors. Registry stored biome-scoped cycle counter; engine needed federation tic log's domain_counter_after. Silent zero-output for 14+ tics.)

<!-- promoted from CogPR-179 (tic 145→146). Source: session:visitor-phase1-dry-run. -->

- **Grace period temporal scope must match governance clock** — when governance functions define grace periods or deadlines, the temporal scope must bind to the governance clock (federation tics), not simulation clocks (biome cycles, generation counters). A full multi-cycle simulation (e.g., 50 biome cycles) may execute within a single federation tic. If grace were measured in simulation cycles, it would expire during a single simulation run, violating the governance intent: give the system time to observe and respond across governance review windows, not just simulate. The distinction between governance clock and simulation clock is fundamental to any system that runs multi-cycle simulations within governance-paced review windows. (Validated: demotion grace period of 5 federation tics correctly survives 50-cycle biome generations that execute within single tics.)

<!-- promoted from CogPR-181 (tic 146→146). Source: demotion lifecycle build. -->

## Governed Bridge Mechanics

- **Loneliness intervention as governed bridge mechanic** — isolated nodes in proximity-based networks experience self-reinforcing isolation: no neighbors means no interactions, no interactions means no trust accumulation, no trust means no promotion, no promotion means continued isolation. The intervention is a governed bridge: a weak edge, metadata-marked with `intervention_type`, that creates opportunity for trust accumulation without bypassing the trust system. The bridge does not grant trust — it creates the conditions under which trust can be earned. The constraint is "opportunity without bypass": the bridge must emit a governance signal, carry audit metadata, and use weak-edge weight so natural interactions can strengthen or replace it. (Validated: Flint isolated 20 cycles in sector 4 — no natural interaction partners. Loneliness bridge created weak cross-sector edge at cycle 20. Flint progressed guest→tourist→foreign_delegate by cycle 23, 3 cycles post-bridge. Bridge metadata and signal preserved full audit trail.)

<!-- promoted from CogPR-180 (tic 145→146). Source: session:visitor-phase1-dry-run. -->

## Gate Contracts (Not Vibes)

A gate is a contract surface, not a vibe or preference. Gate inputs must be explicitly declared (what goes in), outputs must be verifiable (what comes out), preconditions must be stateable (when it can run), and post-checks must be automatable (whether it succeeded). Spec-first execution with operator review gates works because the gate is a stated contract: inputs (spec text), outputs (binary proceed/halt decision), preconditions (spec authored and approved), post-checks (human review of applicability before unlock). Gates without declared contracts become vibe-based ("does this feel like a good implementation?"), producing endless renegotiation and operator cognitive overload. Pipeline phase dependencies must be structured gate contracts using this pattern.

<!-- promoted from cpr_gate_contracts_not_vibes_tic150 (tic 150→167). Source: tic-164-165-166 duality-lane authoring + Run 2 execution. Evidence: gate_b2 mechanism failure (tic 165) was diagnosable only because the gate had declared contract (preserve body byte-identical); absence of declared input made "was the gate input correct?" answerable. Band: COGNITIVE. -->

## Shape Fingerprint Provenance

Composite shape hash `sha256(content_hash + ctime + birthtime + inode)` creates a deterministic fingerprint robust to single-axis spoofing. File content alone can be mutated without changing hash (if the mutator knows the hash). File metadata alone can be spoofed (ctime touched, birthtime forged). Inode alone can change during file operations (copy, mv with recreation). The composite prevents an adversary from controlling all four axes simultaneously without triggering visible divergence. This forms one leg of a sentinel-integrity triple with Read-Side Verification Complement and Context-Aware Severity Classification.

<!-- promoted from cpr_shape_fingerprint_provenance_tic155 (tic 155→167). Source: pipeline integrity audit (tic 155). Sentinel-integrity triple cross-reference: Read-Side Verification Complement and Context-Aware Severity Classification (tic 155→167). Band: COGNITIVE. -->

## Read-Side Verification Complement

Append-only ledgers provide write-side integrity but without read-side chain verification a malicious or buggy reader can present out-of-order entries as canonical. Read-side verification closes the loop: chain-hash check (each line's hash includes prior line's hash), sequence number validation (entries appear in declared order), and monotonicity enforcement (no sequence number skips). This is the verification complement to JSONL Atomic Writes (CogPR-8), which addresses write-side integrity only. Read-side verification ensures the consumer sees the ledger as written, not a reshuffled or truncated version the reader chose to present.

<!-- promoted from cpr_read_side_verification_complement_tic155 (tic 155→167). Source: pipeline integrity audit (tic 155). Refines JSONL Atomic Writes (CogPR-8). Sentinel-integrity triple: pairs with Shape Fingerprint Provenance and Context-Aware Severity Classification. Band: COGNITIVE. -->

## Context-Aware Severity Classification

Pattern-matching severity ("if path contains X then critical") produces false escalation under remediation-era state changes. A file path containing "malware" is not inherently critical if the context is "archived forensic report" or "historical threat database." Context-aware classification requires knowing: what is this file for, who owns its lifecycle, what operational state is active now. A path appearing in active infection context is critical; the same path in post-remediation archival context is informational. This reduces noise while preserving signal. Validated against tic 159 runtime_drift_check: 71 findings, 0 critical (correctly downgraded from pattern-match false positives), 16 warning, 55 info. Sentinel-integrity triple: completes the integrity verification surface with Shape Fingerprint Provenance and Read-Side Verification Complement.

<!-- promoted from cpr_context_aware_severity_tic155 (tic 155→167). Source: tic-159 runtime_drift_check validation. Sentinel-integrity triple: Shape Fingerprint Provenance, Read-Side Verification Complement, Context-Aware Severity Classification. Band: COGNITIVE. -->

## Inbox Triple-Source Sync

Inbox archive operations must propagate across three sources of truth: (1) filesystem (WAIT/ACTIVE/DONE prefixes on files), (2) inbox-registry.json (canonical state enumeration), (3) hook-detection state (what the hooks know about). Failure to sync produces phantom state where one source disagrees with the others and hooks re-detect already-archived items as stale. The three sources can diverge silently: a file moved from WAIT to DONE (filesystem state correct), registry updated (registry state correct), but hook-detection still thinks it's WAIT because the hook fired before the registry update and cached its findings. Protection: any archive operation that modifies one source must atomically update all three. Validating archive completeness requires comparing across all three sources, not trusting any one surface.

<!-- promoted from cpr_inbox_triple_source_sync_tic160 (tic 160→167). Source: inbox operations audit (tic 160). Operationalizes atomic writes principle (CogPR-8) at the multi-surface level. Band: COGNITIVE. -->

## Two-Run Spec-Gate Geometry

Spec-first with operator review gate between Run 1 (spec authoring) and Run 2 (execution) materially separates spec production from execution risk. Cost: extra swarm cycle + operator review budget. Benefit: spec drift is caught at review time rather than at execution time, and the spec becomes a standalone artifact operators can reference, amend, or reject without collateral damage to execution agents. This geometry is operationally distinct from Spec-First Parallel Swarm (CogPR-140): the latter is one run with the spec as scaffold; this is two runs with the spec itself as a reviewable deliverable. Once a constitutional pattern is validated at n=1 (pilot survives operator gate + first execution boundary), subsequent adopters use lighter-cadence rollout (single-pass author + verify) until the convention shows transferability stress.

<!-- promoted from cpr_two_run_spec_gate_validated_tic165 (tic 164-165→167). Source: tic-164 spec swarm + tic-165 Run 2 execution. Validated geometry at 5-agent swarm scale. Band: COGNITIVE. -->

## Constitutional-Office Swarm Differentiation

Constitutional-office swarm agents with distinct jurisdictional lenses (Ladder Auditor/coherence, Civil Engineer/mechanics, CBUX Steward/encounter, Videographer/narrative) produce genuinely differentiated spec fragments — not just same-output-in-different-voice. Jurisdictional distance matters more than apparent topical relevance. When selecting offices for spec-writing swarms, a narrative lens on a schema question surfaces structural failures that pure governance lenses cannot see. Validated: Videographer's narrative-capture lens identified a structural tier-boundary visibility concern that all three governance-facing offices missed despite reading the same anchor inputs.

<!-- promoted from cpr_constitutional_lens_differentiation_tic165 (tic 165→167). Source: tic-164 spec swarm. Refines Spec-First Parallel Swarm (CogPR-140). Band: COGNITIVE. -->

## Open Question Classification (Probe-First Test)

Open questions in specs classify by what resolves them: (a) operator-judgment (require human decision), (b) evidence-probe (resolvable by small filesystem or state inspection), (c) deferred (non-blocking, carry to later tic). Type (b) should not present as operator-blocking. Protection: when drafting OQs during synthesis, apply a probe-first test — can this be answered in one bash command? If yes, classify as evidence-probe and resolve inline rather than routing to operator. This prevents false-blocking pressure at review gates.

<!-- promoted from cpr_oq_filesystem_probe_tic165 (tic 165→167). Source: tic-164 spec synthesis. Band: COGNITIVE. -->

## Spec as Tone Exemplar

When a spec also functions as the tone exemplar for downstream deliverables that will imitate it, spec-level tone discipline matters more than discipline on comparable non-exemplar specs. A spec that says "do not use metaphors in procedural sections" while itself using metaphors licenses downstream agents to do the same. Protection: apply the spec's own tone rules to the spec itself before operator review, not just to the deliverable. Cost: one surgical edit. Benefit: prevents drift of the norms the rollout is establishing.

<!-- promoted from cpr_spec_as_tone_exemplar_tic165 (tic 165→167). Source: tic-164 spec swarm. Validated in practice. Band: COGNITIVE. -->

## Boundary-Aware Body Extraction

Spec validation gates that use hardcoded line offsets for body extraction (sed -n 'N,$p' with fixed N) break silently when the mutation being validated changes the boundary position. Protection: use boundary-aware extraction anchored on structural delimiters (awk on '---' fences, closing tag markers, etc.) rather than line-number offsets. The fragility is not sed per se — it's the implicit assumption that the mutation preserves the line position of the boundary being measured across. Any spec gate that encodes "verify content below line N" inherits this assumption.

<!-- promoted from cpr_spec_gate_line_offset_fragility_tic165 (tic 165→167). Source: tic-165 Run 2 execution, spec.yaml gate_b2 mechanism failure. Band: COGNITIVE. -->

## Verifier Install Path via Sync Manifest

Verifier gates that diff canonical source against runtime-installed artifacts must discover the install target via the same mechanism as the syncing tool (sync-manifest.json lookup), not hardcode a parallel path assumption. Specs assuming an install path create a second source of truth that can drift from the actual sync mechanism without either side detecting the drift. Protection: any Gate-E-class parity check should resolve the install target from runtime-sync's manifest, inheriting the sync tool's canonical knowledge of where files land.

<!-- promoted from cpr_verifier_install_path_via_sync_manifest_tic165 (tic 165→167). Source: tic-165 Run 2 execution, spec.yaml gate_e mechanism. Extends CogPR-37 (Runtime Sync Parity Verification) and CogPR-40 (envelope pattern). Band: COGNITIVE. -->

## Lighter-Cadence Rollout Post-Validation

Once a constitutional pattern is validated at n=1 (pilot survives operator gate + first execution boundary), subsequent adopters should use lighter-cadence rollout (single-pass author + verify, no two-run gate geometry) until the convention shows transferability stress. The two-run gate exists to catch mechanism bugs at the spec↔execution seam during initial constitutional bootstrapping. Once the seam is exercised under load, the cost of repeating the geometry per-adopter is operator-attention drain that returns no marginal safety value. Verification gates remain mandatory; the adversarial swarm structure does not.

<!-- promoted from cpr_lighter_cadence_post_validation_tic166 (tic 166→167). Source: tic-166 Run 3 rollout (/review and /inbox adoption). Band: COGNITIVE. -->

## Sentinel-Integrity Triple Summary

Three validations form a coherent integrity surface: (1) Shape Fingerprint Provenance — hash composition prevents single-axis spoofing, (2) Read-Side Verification Complement — ledger reading verifies chain integrity, (3) Context-Aware Severity — classification prevents false escalation from stale paths. Applied together, they form a multi-layer detection surface. Each layer catches what the others miss: content tampering, reader manipulation, and context-blind pattern matching.
