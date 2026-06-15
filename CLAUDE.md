# Context Grapple Gun — Domain CLAUDE.md

> Before performing any action, read the [federation CLAUDE.md](../../CLAUDE.md) to understand governance hierarchy. CGG is a developer-estate authoring domain governed by canonical federation doctrine; references flow downward only (federation → estate → domain → module).

> **Dehydrated at tic 314** (/review-314 freeze). This root is the compact index; full verbatim bodies live in [`cgg-ledger/ledger.md`](cgg-ledger/ledger.md), one tagged entry per invariant. Dehydration here is **principle-extraction, not information loss** — each bullet compresses toward the invariant's *centroid* (its core), not by line-count truncation; the invariant's first sentence is used as a *heuristic* handle for that centroid, never as a substitute for it. Origin is never lost: follow the pointer for the complete body, the walkable `promoted from` lineage, provenance, and refinements. The compression is honest only if a nested rung **rehydrates the invariant in the spirit it came from** (the fidelity proof). The full hydration/dehydration ladder — up-lane, down-lane, the gate, compression, and current-vs-target honesty — is presented in [`ARCHITECTURE.md` § "How the ladder actually moves"](ARCHITECTURE.md).

## External Schema Volatility

- **Epistemic Volatility Notice** — Claude Code hook format, plugin manifest schema, and install semantics are **externally versioned by Anthropic**.
  - *Ledger:* [`cgg-ledger/ledger.md#epistemic-volatility-notice`](cgg-ledger/ledger.md#epistemic-volatility-notice)
- **Volatile-Schema Validation Discipline (Probe-Before-Bind)** — The prevention complement to Epistemic Volatility Notice.
  - *Ledger:* [`cgg-ledger/ledger.md#volatile-schema-validation-discipline-probe-before-bind`](cgg-ledger/ledger.md#volatile-schema-validation-discipline-probe-before-bind)
- **Hook Format Requirement (Current)** — The hook format has changed multiple times.
  - *Ledger:* [`cgg-ledger/ledger.md#hook-format-requirement-current`](cgg-ledger/ledger.md#hook-format-requirement-current)
- **Plugin Hook Registration** — Plugins must register hooks in `hooks/hooks.json` at the plugin root — listing hooks in `plugin.json` components alone is insufficient.
  - *Ledger:* [`cgg-ledger/ledger.md#plugin-hook-registration`](cgg-ledger/ledger.md#plugin-hook-registration)
- **Agent Tool (formerly Task)** — The `Task` tool was renamed to `Agent` in Claude Code 2.1.63.
  - *Ledger:* [`cgg-ledger/ledger.md#agent-tool-formerly-task`](cgg-ledger/ledger.md#agent-tool-formerly-task)
- **Plugin Declaration Surface (CGG-Specific)** — CGG 4.0.0 demonstrated that component declarations placed in proprietary plugin.json fields (`components`, `install`, `claude_code`) did not register and were replaced in 4.0.1 by marketplace-based declaration.
  - *Ledger:* [`cgg-ledger/ledger.md#plugin-declaration-surface-cgg-specific`](cgg-ledger/ledger.md#plugin-declaration-surface-cgg-specific)
- **npm Distribution Wrapper** — CGG is distributed via npm as `context-grapple-gun`.
  - *Ledger:* [`cgg-ledger/ledger.md#npm-distribution-wrapper`](cgg-ledger/ledger.md#npm-distribution-wrapper)
- **Subagent Delegation — Schema Contracts** — When delegating hook creation or script writing to subagents, include the target script's JSON output schema in the prompt.
  - *Ledger:* [`cgg-ledger/ledger.md#subagent-delegation-schema-contracts`](cgg-ledger/ledger.md#subagent-delegation-schema-contracts)
- **showClearContextOnPlanAccept Must Be True** — CGG cadence depends on plan-mode context-clear as the session epoch boundary.
  - *Ledger:* [`cgg-ledger/ledger.md#showclearcontextonplanaccept-must-be-true`](cgg-ledger/ledger.md#showclearcontextonplanaccept-must-be-true)
- **Hook Path Resolution** — Hook scripts must discover zone root by walking up from the **edited file path**, not from `cwd`.
  - *Ledger:* [`cgg-ledger/ledger.md#hook-path-resolution`](cgg-ledger/ledger.md#hook-path-resolution)
- **Hook Binary Invocation (No Aliases)** — Hook scripts must call binaries directly, never shell aliases — aliases live in interactive shell config (.zshrc) and do not survive non-interactive invocation.
  - *Ledger:* [`cgg-ledger/ledger.md#hook-binary-invocation-no-aliases`](cgg-ledger/ledger.md#hook-binary-invocation-no-aliases)
- **Skill Body Is Sole Arg Parser** — Claude Code skill runtime does NOT enforce argument schemas declared in frontmatter `arguments:` field.
  - *Ledger:* [`cgg-ledger/ledger.md#skill-body-is-sole-arg-parser`](cgg-ledger/ledger.md#skill-body-is-sole-arg-parser)
- **Undeclared Args Classify by Projection** — When a skill is invoked with arguments not declared in the `arguments:` frontmatter field, those arguments appear in the skill body as part of the raw `arguments` string.
  - *Ledger:* [`cgg-ledger/ledger.md#undeclared-args-classify-by-projection`](cgg-ledger/ledger.md#undeclared-args-classify-by-projection)
- **Arguments Frontmatter Is Decorative** — The `arguments:` field in skill frontmatter is decorative for governance and documentation purposes.
  - *Ledger:* [`cgg-ledger/ledger.md#arguments-frontmatter-is-decorative`](cgg-ledger/ledger.md#arguments-frontmatter-is-decorative)
- **Extractor Surface Schema Contract** — Tools that extract governance artifacts (CogPRs, signals, bench packets) from canonical surfaces must declare their input schema contract — which files they read, what section markers they search for, what output stru…
  - *Ledger:* [`cgg-ledger/ledger.md#extractor-surface-schema-contract`](cgg-ledger/ledger.md#extractor-surface-schema-contract)

## Mandate And Cadence Ops

- **Mandate Consumption Discipline** — If a cadence mandate exists when a session closes, the session must invoke Mogul or explicitly defer.
  - *Ledger:* [`cgg-ledger/ledger.md#mandate-consumption-discipline`](cgg-ledger/ledger.md#mandate-consumption-discipline)
- **Mogul Mandate Execution Depth Scaling** — Mogul mandate execution depth must scale to estate state at mandate creation time.
  - *Ledger:* [`cgg-ledger/ledger.md#mogul-mandate-execution-depth-scaling`](cgg-ledger/ledger.md#mogul-mandate-execution-depth-scaling)
- **Mandate Lifecycle Defects** — Mandate lifecycle has four structural defects that refine the Mandate Consumption Discipline (CogPR-26) and Mandate Execution Depth Scaling (CogPR-47):
  - *Ledger:* [`cgg-ledger/ledger.md#mandate-lifecycle-defects`](cgg-ledger/ledger.md#mandate-lifecycle-defects)
- **Cadence Downbeat Enforcement** — Cadence downbeat must enforce a strict sequence: emit tic event, then write conformation, before the tic counter advances.
  - *Ledger:* [`cgg-ledger/ledger.md#cadence-downbeat-enforcement`](cgg-ledger/ledger.md#cadence-downbeat-enforcement)
- **Lighter-Cadence Rollout Post-Validation** — Once a constitutional pattern is validated at n=1 (pilot survives operator gate + first execution boundary), subsequent adopters should use lighter-cadence rollout (single-pass author + verify, no two-run gate geometr…
  - *Ledger:* [`cgg-ledger/ledger.md#lighter-cadence-rollout-post-validation`](cgg-ledger/ledger.md#lighter-cadence-rollout-post-validation)
- **Memory-Trim Lighter-Cadence Variant (Option B)** — MEMORY.md trims under the staged-execution pattern need not require the full 4-tic gate ceremony when the operator approves Option B (lighter-cadence single-pass per CogPR-160).
  - *Ledger:* [`cgg-ledger/ledger.md#memory-trim-lighter-cadence-variant-option-b`](cgg-ledger/ledger.md#memory-trim-lighter-cadence-variant-option-b)
- **Post-Cadence Clean-Close Ordering** — When a /cadence-emitted tic includes post-cadence operational cleanup that mutates governance state (signal triage with manifest sweeps, MEMORY.md candidate updates, queue-shaping commits), the closing /cadence should…
  - *Ledger:* [`cgg-ledger/ledger.md#post-cadence-clean-close-ordering`](cgg-ledger/ledger.md#post-cadence-clean-close-ordering)
- **Auto-Mandate Scope Expansion via Merge** — Session-start auto-mandate logic may merge+expand a manually-written mid-session mandate into a broader consolidated mandate when session_start fires (which can happen mid-session via UserPromptSubmit hook or explicit…
  - *Ledger:* [`cgg-ledger/ledger.md#auto-mandate-scope-expansion-via-merge`](cgg-ledger/ledger.md#auto-mandate-scope-expansion-via-merge)
- **Cadence-Ops Scheduler Doctrine-Runtime Parity** — cadence-ops.compute_due_cycles is the central tic-modulo cycle scheduler for Mogul mandates, but multiple doctrine surfaces name cycles that doctrine claims fire on cadence yet the runtime never schedules: (1) civil_s…
  - *Ledger:* [`cgg-ledger/ledger.md#cadence-ops-scheduler-doctrine-runtime-parity`](cgg-ledger/ledger.md#cadence-ops-scheduler-doctrine-runtime-parity)
- **Harmony Cadence Mod-Disagreement (Concrete Conductor-Score-Runtime Parity Instance)** — Concrete instance of Conductor-Score-Runtime Parity (federation KI) at the cadence-ops scheduler.
  - *Ledger:* [`cgg-ledger/ledger.md#harmony-cadence-mod-disagreement-concrete-conductor-score-runtime-parity-instance`](cgg-ledger/ledger.md#harmony-cadence-mod-disagreement-concrete-conductor-score-runtime-parity-instance)
- **Trigger-Router Starvation + Cadence-Ops Mandate-Write Bypass (Concrete Conductor-Score-Runtime Parity Instance) *(naming PROMOTED; runtime patch PROMOTE-SPEC, tic 299)*** — Federation KI *Trigger routing is mandatory — entity activation routes through inbox delivery; direct activation is exception-only.* The trigger-router is the manifest-validated, dedup-enforced, audit-logged dispatch…
  - *Ledger:* [`cgg-ledger/ledger.md#trigger-router-starvation-cadence-ops-mandate-write-bypass-concrete-conductor-score-runtime-parity-instance-naming-promoted-runtime-patch-promote-spec-tic-299`](cgg-ledger/ledger.md#trigger-router-starvation-cadence-ops-mandate-write-bypass-concrete-conductor-score-runtime-parity-instance-naming-promoted-runtime-patch-promote-spec-tic-299)
- **Even-Tic Review-Close Routing (/review Step 8.5 Discipline)** — /review Step 8.5 mandates writing a non-blocking review-close mandate so the next session verifies inscriptions landed.
  - *Ledger:* [`cgg-ledger/ledger.md#even-tic-review-close-routing-review-step-8-5-discipline`](cgg-ledger/ledger.md#even-tic-review-close-routing-review-step-8-5-discipline)
- **Cadence Skill Parser Path Drift Discipline** — When a runtime script emits JSON at top-level keys but the skill body documents a wrapper path (`result.tic.counter_after` rather than top-level `tic.counter_after`), a /cadence author who follows the spec literally p…
  - *Ledger:* [`cgg-ledger/ledger.md#cadence-skill-parser-path-drift-discipline`](cgg-ledger/ledger.md#cadence-skill-parser-path-drift-discipline)
- **Cadence-Ops Fail-Soft Observability Subprocess Pattern** — When a canonical-side observability or audit primitive should fire each /cadence without coupling its lifecycle to CGG's mutation pipeline, the integration pattern is a fail-soft subprocess step in cadence-ops.py — di…
  - *Ledger:* [`cgg-ledger/ledger.md#cadence-ops-fail-soft-observability-subprocess-pattern`](cgg-ledger/ledger.md#cadence-ops-fail-soft-observability-subprocess-pattern)
- **Cross-Cadence-Rails + Inbox-Marker-Dependency-Satisfaction Primitive** — When the next session needs a hot-and-ready swarm at SessionStart, the prior session's /cadence is the lowest-cost moment to manufacture the swarm's contextual rails — dispatch parallel /tactical-hydration lanes, term…
  - *Ledger:* [`cgg-ledger/ledger.md#cross-cadence-rails-inbox-marker-dependency-satisfaction-primitive`](cgg-ledger/ledger.md#cross-cadence-rails-inbox-marker-dependency-satisfaction-primitive)
- **review-close-check Verifier — Dehydration Blindspot** — review-close-check.py searches canonical/CLAUDE.md for promoted CogPR text and emits `promoted_text_missing` findings when not found.
  - *Ledger:* [`cgg-ledger/ledger.md#review-close-check-verifier-dehydration-blindspot`](cgg-ledger/ledger.md#review-close-check-verifier-dehydration-blindspot)

## Arena And Reasoning Geometry

- **Epistemic Triangulation Geometry** — Epistemic triangulation (coincidence/mechanism/counterfactual) is an effective geometry for hypothesis-testing arenas.
  - *Ledger:* [`cgg-ledger/ledger.md#epistemic-triangulation-geometry`](cgg-ledger/ledger.md#epistemic-triangulation-geometry)
- **Same-Model Convergence Discount** — Same-model agent convergence is weaker than cross-model convergence.
  - *Ledger:* [`cgg-ledger/ledger.md#same-model-convergence-discount`](cgg-ledger/ledger.md#same-model-convergence-discount)
- **Concession Cascade Detection** — Evidence-rebuttal concession cascade: when evidence advocate concedes all claims, check for role abandonment vs claim adjustment.
  - *Ledger:* [`cgg-ledger/ledger.md#concession-cascade-detection`](cgg-ledger/ledger.md#concession-cascade-detection)
- **Arena Velocity Guard** — When arena convergence happens faster than evidence accumulation, treat the consensus as a hypothesis set, not a decision set.
  - *Ledger:* [`cgg-ledger/ledger.md#arena-velocity-guard`](cgg-ledger/ledger.md#arena-velocity-guard)
- **Overlap-Frequency Tiering Primitive** — Overlap-frequency tiering is a reusable prioritization primitive for competitive and comparative analysis: features all competitors share = table stakes (necessary but not differentiating), some share = opportunity zo…
  - *Ledger:* [`cgg-ledger/ledger.md#overlap-frequency-tiering-primitive`](cgg-ledger/ledger.md#overlap-frequency-tiering-primitive)
- **CATALYZE Advocate Geometry** — Harpoon assessment arenas benefit from a CATALYZE advocate position that argues for higher-leverage constitutional alternatives, replacing binary PASS/NO with phased convergence.
  - *Ledger:* [`cgg-ledger/ledger.md#catalyze-advocate-geometry`](cgg-ledger/ledger.md#catalyze-advocate-geometry)
- **Cross-Rung Orientation (CRX) Arena Geometry** — CRX is the 6th arena geometry template, designed for cross-rung and cross-jurisdiction exploration.
  - *Ledger:* [`cgg-ledger/ledger.md#cross-rung-orientation-crx-arena-geometry`](cgg-ledger/ledger.md#cross-rung-orientation-crx-arena-geometry)
- **Recursive Meta-Enforcement** — Schema-level enforcement of governance requirements can be formally satisfied while substantively violated — a mandatory dissent field satisfied by writing "No dissent." is compliance theater.
  - *Ledger:* [`cgg-ledger/ledger.md#recursive-meta-enforcement`](cgg-ledger/ledger.md#recursive-meta-enforcement)
- **NIH Self-Examination in Adversarial Arenas** — In governed adversarial arenas, advocates arguing for build-alternative positions (CATALYZE, build-from-scratch, replace-with-custom) must include a mandatory NIH (Not Invented Here) self-examination: an honest numeri…
  - *Ledger:* [`cgg-ledger/ledger.md#nih-self-examination-in-adversarial-arenas`](cgg-ledger/ledger.md#nih-self-examination-in-adversarial-arenas)
- **Opposing-Values Geometry for Constitutional Questions** — Constitutional questions (expansion, restructuring, inscription, authority changes) should use opposing-values arena geometry where advocates hold genuinely different values (e.g., completeness vs coherence vs efficie…
  - *Ledger:* [`cgg-ledger/ledger.md#opposing-values-geometry-for-constitutional-questions`](cgg-ledger/ledger.md#opposing-values-geometry-for-constitutional-questions)
- **Post-Hoc Conformation (Anti-Pattern: In-Arena Invariant Scoring)** — Do not ask arena advocates to score their positions against invariants during their turns.
  - *Ledger:* [`cgg-ledger/ledger.md#post-hoc-conformation-anti-pattern-in-arena-invariant-scoring`](cgg-ledger/ledger.md#post-hoc-conformation-anti-pattern-in-arena-invariant-scoring)
- **VPL Standard Geometry (Tournament-Lattice)** — Tournament-lattice VPL (Value-Position Lattice) with bracket isolation and wildcard challenge is the standard geometry for federation governance shape questions.
  - *Ledger:* [`cgg-ledger/ledger.md#vpl-standard-geometry-tournament-lattice`](cgg-ledger/ledger.md#vpl-standard-geometry-tournament-lattice)
- **OA-VPL-T Arena Geometry** — OA-VPL-T (Office-Autonomous Value-Position Lattice with Temporal Modeling) is the 8th arena geometry template.
  - *Ledger:* [`cgg-ledger/ledger.md#oa-vpl-t-arena-geometry`](cgg-ledger/ledger.md#oa-vpl-t-arena-geometry)
- **Shared-Telos Arena: Stress Method-Optimization, Not Intent Divergence** — In a shared-Telos office arena, convergence-on-INTENT is expected and low-information; the adversarial yield is each office advocating the METHOD-of-execution that optimizes its OWN stewardship lens. *(tic 377)*
  - *Ledger:* [`cgg-ledger/ledger.md#shared-telos-arena-stress-method-not-intent`](cgg-ledger/ledger.md#shared-telos-arena-stress-method-not-intent)

## Signal And Queue Manifold

- **Cycle-Based Windows in Mixed-Frequency Event Streams** — When multiple event streams operate at different frequencies (e.g., governance tics at ~1 per hour, biome cycles at 50 per minute during simulation), windows for analysis must anchor to a common reference clock and ex…
  - *Ledger:* [`cgg-ledger/ledger.md#cycle-based-windows-in-mixed-frequency-event-streams`](cgg-ledger/ledger.md#cycle-based-windows-in-mixed-frequency-event-streams)
- **Signal ID Determinism** — Signal IDs must be deterministic and condition-stable — derived from the condition being signaled (entity, state, source), not from emission timestamp or session ID.
  - *Ledger:* [`cgg-ledger/ledger.md#signal-id-determinism`](cgg-ledger/ledger.md#signal-id-determinism)
- **Queue Metadata Schema Declaration** — Queue metadata schema is implicit.
  - *Ledger:* [`cgg-ledger/ledger.md#queue-metadata-schema-declaration`](cgg-ledger/ledger.md#queue-metadata-schema-declaration)
- **Encounter Quality Upstream of Signals** — The governance encounter surface (hook output at edit time) is constitutionally upstream of signal infrastructure.
  - *Ledger:* [`cgg-ledger/ledger.md#encounter-quality-upstream-of-signals`](cgg-ledger/ledger.md#encounter-quality-upstream-of-signals)
- **Authoritative Count Discipline** — Governance reporting tools must source counts from authoritative state (physical event files, active manifests), not from configuration or raw unfiltered logs.
  - *Ledger:* [`cgg-ledger/ledger.md#authoritative-count-discipline`](cgg-ledger/ledger.md#authoritative-count-discipline)
- **Dedup-at-Write Using Canonical Identity** — Duplicate detection must occur at the write boundary (physics layer) keyed on canonical record identity (signal_id, CPR id), not at scan time or by content hash.
  - *Ledger:* [`cgg-ledger/ledger.md#dedup-at-write-using-canonical-identity`](cgg-ledger/ledger.md#dedup-at-write-using-canonical-identity)
- **Queue Index Status Coverage Discipline** — When building indexed views of the queue (e.g., build_queue_index.py), the coverage must be explicit: which status values are indexed, which are aggregated, which are ignored.
  - *Ledger:* [`cgg-ledger/ledger.md#queue-index-status-coverage-discipline`](cgg-ledger/ledger.md#queue-index-status-coverage-discipline)
- **Emitter-Surface Declaration Contract** — Governance surfaces that can emit artifacts (MEMORY.md, arena reports, bench packets, session transcripts, decision briefs) must declare themselves as emitter surfaces in a registry.
  - *Ledger:* [`cgg-ledger/ledger.md#emitter-surface-declaration-contract`](cgg-ledger/ledger.md#emitter-surface-declaration-contract)
- **Terminal-State Valve Pattern** — JSONL queues that follow append-only with latest-entry-per-id-wins read semantics produce a class of bug where a stray later non-terminal row (typically status=extracted from a re-extraction pass) masks an already-set…
  - *Ledger:* [`cgg-ledger/ledger.md#terminal-state-valve-pattern`](cgg-ledger/ledger.md#terminal-state-valve-pattern)
- **Manifest-Prune Per-ID Terminal-State Sweep** — Debt B — manifest-prune.py sweeps must be per-id terminal-state-aware, not per-row.
  - *Ledger:* [`cgg-ledger/ledger.md#manifest-prune-per-id-terminal-state-sweep`](cgg-ledger/ledger.md#manifest-prune-per-id-terminal-state-sweep)
- **Debt A — Transient Patch-Landing Drift Auto-Resolution Owner** — Debt A — the transient patch-landing drift auto-resolution loop has no runtime owner (runtime lifecycle closure layer).
  - *Ledger:* [`cgg-ledger/ledger.md#debt-a-transient-patch-landing-drift-auto-resolution-owner`](cgg-ledger/ledger.md#debt-a-transient-patch-landing-drift-auto-resolution-owner)
- **Transient Patch-Landing Drift Signal Class** — When patches land in canonical source but have not yet been copied to the installed runtime tree, runtime-sync's pre-sync drift check correctly fires a TENSION/COGNITIVE detected_drift signal.
  - *Ledger:* [`cgg-ledger/ledger.md#transient-patch-landing-drift-signal-class`](cgg-ledger/ledger.md#transient-patch-landing-drift-signal-class)
- **Emitter Surface Declared Interface** — Any governance surface that emits <!-- --agnostic-candidate --> blocks must be reachable by cpr-extract.py.
  - *Ledger:* [`cgg-ledger/ledger.md#emitter-surface-declared-interface`](cgg-ledger/ledger.md#emitter-surface-declared-interface)
- **Sliding Window Event-Stream Filtering** — Sliding windows over governance event streams must filter by TIME (cycle / tic / timestamp) not by RECORD COUNT when the stream carries mixed-frequency event types.
  - *Ledger:* [`cgg-ledger/ledger.md#sliding-window-event-stream-filtering`](cgg-ledger/ledger.md#sliding-window-event-stream-filtering)
- **RTCH Harvest Reader — Terminal-Valve Discipline** — RTCH harvests over append-only ledgers (queue.jsonl, shape-ledger.jsonl, signal files) must read the terminal-valve projection, not aggregate raw emissions; otherwise stale pre-promotion state masquerades as live over…
  - *Ledger:* [`cgg-ledger/ledger.md#rtch-harvest-reader-terminal-valve-discipline`](cgg-ledger/ledger.md#rtch-harvest-reader-terminal-valve-discipline)
- **queue.jsonl Drift-Audit Primitive** — queue.jsonl needs a drift-audit primitive (analogous to memory-md-audit.py) that projects terminal-state and flags genuinely overdue pre-promotion rows, distinguishing them from falsely-overdue ones produced by reader…
  - *Ledger:* [`cgg-ledger/ledger.md#queue-jsonl-drift-audit-primitive`](cgg-ledger/ledger.md#queue-jsonl-drift-audit-primitive)
- **Self-Conditioning Discipline — Thin Terminal Residue Prevents Regression** — A self-conditioning declaration discipline needs a thin append-only terminal residue on an existing surface to avoid regressing into a rebuilt mutable state-store; the residue/state-store boundary = append-only+terminal+existing-surface (legitimate) vs mutable+polled+new-surface (category error). *(tic 377)*
  - *Ledger:* [`cgg-ledger/ledger.md#self-conditioning-discipline-needs-thin-terminal-residue`](cgg-ledger/ledger.md#self-conditioning-discipline-needs-thin-terminal-residue)

## Review And Promotion Discipline

- **Review Execution Delegation** — After `/review` docket is approved, dispatch execution to a `review-execute` subordinate agent — never execute promotions inline in the interactive path.
  - *Ledger:* [`cgg-ledger/ledger.md#review-execution-delegation`](cgg-ledger/ledger.md#review-execution-delegation)
- **Goal-Directive as Ratification Authority for Routine Review Passes** — When the Architect sets a /goal directive whose stop condition explicitly names processing-class outcomes (e.g., "all actionable review items are properly evaluated AND processed per governance requirements"), the goa…
  - *Ledger:* [`cgg-ledger/ledger.md#goal-directive-as-ratification-authority-for-routine-review-passes`](cgg-ledger/ledger.md#goal-directive-as-ratification-authority-for-routine-review-passes)
- **Promotion Scope Discipline** — Promotion decision is two decisions, not one: (1) is the content valid? (2) what class of doctrine does it belong to? Scope reconciliation must happen before promotion — batch promotion from census evidence is especia…
  - *Ledger:* [`cgg-ledger/ledger.md#promotion-scope-discipline`](cgg-ledger/ledger.md#promotion-scope-discipline)
- **Named-Is-Not-Landed Gate** — A complement surfaced in a prior mode but not yet materialized remains a valid complement.
  - *Ledger:* [`cgg-ledger/ledger.md#named-is-not-landed-gate`](cgg-ledger/ledger.md#named-is-not-landed-gate)
- **Reason-Coded Genuine-vs-Known Verifier Split** — A consistency verifier's boolean `consistent:false` is the wrong shape when N findings are pre-classifiable known false-positives: it must report `consistent:false(genuine=G, known=K)`, only `G>0` is a hazard, and each `known` finding must carry a REASON code (`dehydration_resolved | behavioral_text_unverifiable | stale_relocated_pointer`). A single shared resolver closes exactly ONE reason (`resolve_doctrine_surfaces` closed the dehydration reason: review-close-check went 10→4 at tic 335); the rest need distinct mechanisms (provenance-trace for behavioral/code targets, pointer-correction for relocated archives). A named-but-unlanded blindspot re-emits identical false-positives every cycle — the tic-301 verifier blindspot was named twice in doctrine yet unlanded for 34 tics until landed tic 335 — so the recurring set must be ENUMERATED + PRE-CLASSIFIED in the remediation tranche, and the agent must classify each finding with evidence rather than wave at the whole set with a known-blindspot label. Refines Named-Is-Not-Landed Gate; composes Conductor-Score-Runtime-Parity (doctrine names it, runtime didn't enforce) + the consumer-set obligation.
  - *Ledger:* [`cgg-ledger/ledger.md#reason-coded-genuine-vs-known-verifier-split`](cgg-ledger/ledger.md#reason-coded-genuine-vs-known-verifier-split)
- **Review-Execute Atomic Writeback Completeness** — review-execute must complete two idempotent writeback halves on auto-memory / inline promotion targets — flip the inline `status: pending` marker AND stamp a `<!-- promoted from cpr_… -->` breadcrumb — or it leaves recurring review-close-check false-positives (`promoted_text_missing`) the next session re-derives cold. Emit-side complement to the read-side genuine-vs-known verifier split; mechanized by `review-promote-writeback.py` (landed tic 338). Scoped to auto-memory targets only; ledger/compact-root provenance stays in the Step-2 body write.
  - *Ledger:* [`cgg-ledger/ledger.md#review-execute-atomic-writeback-completeness`](cgg-ledger/ledger.md#review-execute-atomic-writeback-completeness)
- **Two-Lane /review Execution Split** — Tic 188 /review docket arrived with 25 entries split across heterogeneous targets.
  - *Ledger:* [`cgg-ledger/ledger.md#two-lane-review-execution-split`](cgg-ledger/ledger.md#two-lane-review-execution-split)
- **CogPR Marker Syntax Discipline** — CogPR candidate inline inscriptions in MEMORY.md MUST use single-comment marker form `<!-- --agnostic-candidate` (no closing `-->` on the marker line; YAML body inside the comment; `-->` terminates the block).
  - *Ledger:* [`cgg-ledger/ledger.md#cogpr-marker-syntax-discipline`](cgg-ledger/ledger.md#cogpr-marker-syntax-discipline)
- **Review-Execute Large-File Truncation Hazard** — review-execute large-file truncation hazard with append-class instructions.
  - *Ledger:* [`cgg-ledger/ledger.md#review-execute-large-file-truncation-hazard`](cgg-ledger/ledger.md#review-execute-large-file-truncation-hazard)
- **Inline CogPR status:pending Field Required** — Inline CogPR inscriptions in MEMORY.md (and other extractor-watched surfaces) MUST carry an explicit `status: pending` field, placed immediately after `id:` in the YAML body.
  - *Ledger:* [`cgg-ledger/ledger.md#inline-cogpr-status-pending-field-required`](cgg-ledger/ledger.md#inline-cogpr-status-pending-field-required)
- **Inline CogPR Schema Completeness Required** — Inline CogPR inscriptions in MEMORY.md (and other extractor-watched surfaces) MUST carry three Tier 1 schema-completeness fields: `status: pending`, `lesson:`, and `source:`.
  - *Ledger:* [`cgg-ledger/ledger.md#inline-cogpr-schema-completeness-required`](cgg-ledger/ledger.md#inline-cogpr-schema-completeness-required)
- **Arsenal Instructions Carry Only the Up-Lane Ratchet — the Living-Corpus Down-Lane Is Un-Instructed** — The CGG arsenal was scaffolded as a living doctrine-lifecycle engine but every operational INSTRUCTION surface encodes only the up-lane (capture→enrich→/review→promote); the under-leverage lives in the instructions, not the engine. Refinement-instance of Conductor-Score-Runtime Parity; the down-lane WIRING stays DEFER (read-only-first). *(tic 378→379)*
  - *Ledger:* [`cgg-ledger/ledger.md#arsenal-instructions-carry-only-the-up-lane-ratchet`](cgg-ledger/ledger.md#arsenal-instructions-carry-only-the-up-lane-ratchet)
- **Fix-Then-Present — a Self-Presentation Doc Describing an Unwired Mechanic As Real IS the Misrepresentation** — Writing a presentation doc before fixing what is broken/misrepresenting produces a doc that lies; audit→decide-write-topology→fix+sync+verify-parity→mark current-vs-target honestly. Validated at two doctrine rungs (CGG arsenal + autonomous_kernel demotion/rollback over-claim). *(tic 377→379)*
  - *Ledger:* [`cgg-ledger/ledger.md#fix-then-present-self-presentation-honesty`](cgg-ledger/ledger.md#fix-then-present-self-presentation-honesty)
- **Build-and-Gate — Wired-but-Ratification-Gated Consumer for a Doctrine-Adjacent Model** — When you build a doctrine-adjacent model a live consumer would read (boot renderer/router/dispatch gate), don't choose defer-the-wiring vs ship-it-live: build+wire+test the consumer but gate its USE on an explicit `ratified` flag (default false) carried IN the model; /review flips it (ratification IS the flag-flip, no further code change). Build lands hot, effect is one human-gated bit. Needs DUAL proof: dormancy (0-at-false) + full-surface activation (exercise the whole consumer surface at true, not one happy-path — the reciprocal to-side gap that slipped the tic-429 from-side proof). *(tic 429→430)*
  - *Ledger:* [`cgg-ledger/ledger.md#build-and-gate-ratified-flag-gated-consumer`](cgg-ledger/ledger.md#build-and-gate-ratified-flag-gated-consumer)

## Subagent And Swarm Delegation

- **Lead Context as Binding Constraint** — Lead context accumulation — not advocate turn count — is the binding budget constraint in governed arenas.
  - *Ledger:* [`cgg-ledger/ledger.md#lead-context-as-binding-constraint`](cgg-ledger/ledger.md#lead-context-as-binding-constraint)
- **Coordination Overhead Accounting** — Coordination overhead (nudges, retries, phase-transition messages) is lead-side cost, not advocate-side cost.
  - *Ledger:* [`cgg-ledger/ledger.md#coordination-overhead-accounting`](cgg-ledger/ledger.md#coordination-overhead-accounting)
- **Spec-First Parallel Swarm** — Write complete spec surface BEFORE launching implementation agents.
  - *Ledger:* [`cgg-ledger/ledger.md#spec-first-parallel-swarm`](cgg-ledger/ledger.md#spec-first-parallel-swarm)
- **Constitutional-Office Swarm Differentiation** — Constitutional-office swarm agents with distinct jurisdictional lenses (Ladder Auditor/coherence, Civil Engineer/mechanics, CBUX Steward/encounter, Videographer/narrative) produce genuinely differentiated spec fragmen…
  - *Ledger:* [`cgg-ledger/ledger.md#constitutional-office-swarm-differentiation`](cgg-ledger/ledger.md#constitutional-office-swarm-differentiation)
- **Parallel Inscription Swarm Validated at n=3** — Spec-First Parallel Swarm (CogPR-140) + Lighter-Cadence Rollout Post-Validation validated at n=3 for inscription-class work.
  - *Ledger:* [`cgg-ledger/ledger.md#parallel-inscription-swarm-validated-at-n-3`](cgg-ledger/ledger.md#parallel-inscription-swarm-validated-at-n-3)
- **Mixed Subagent + Lead Swarm Geometry** — When a tranche set has mixed authorship — 1 subagent for large-surface authoring (where fresh-context constraint inversion is valuable for catching latent bugs) + N lead-direct for smaller or manual operations (where…
  - *Ledger:* [`cgg-ledger/ledger.md#mixed-subagent-lead-swarm-geometry`](cgg-ledger/ledger.md#mixed-subagent-lead-swarm-geometry)
- **Triplet Self-Spawn for Substrate Moments — Three-Posture Instance Reference** — Triplet self-spawn dispatches three same-skill instances on a single substrate signal, differentiated by POSTURE (not task), so the postures triangulate into a synthesis no single posture would produce — sub-class of…
  - *Ledger:* [`cgg-ledger/ledger.md#triplet-self-spawn-for-substrate-moments-three-posture-instance-reference`](cgg-ledger/ledger.md#triplet-self-spawn-for-substrate-moments-three-posture-instance-reference)

## Sync And Install Parity

- **Runtime Sync Parity Verification** — Source-repo correctness does not imply runtime correctness.
  - *Ledger:* [`cgg-ledger/ledger.md#runtime-sync-parity-verification`](cgg-ledger/ledger.md#runtime-sync-parity-verification)
- **Install Boundary as Governance Transition** — The forge→runtime install boundary (`canonical_developer/` → `~/.claude/`) is a first-class governance transition, not merely a file copy.
  - *Ledger:* [`cgg-ledger/ledger.md#install-boundary-as-governance-transition`](cgg-ledger/ledger.md#install-boundary-as-governance-transition)
- **Claimed Install-State Requires Auditable Sync-Log Proof** — **Claimed install-state is not real until post-commit sync proves byte parity across all targets and emits an auditable sync log.**
  - *Ledger:* [`cgg-ledger/ledger.md#claimed-install-state-requires-auditable-sync-log-proof`](cgg-ledger/ledger.md#claimed-install-state-requires-auditable-sync-log-proof)
- **Manual-Ceremony-as-Pipeline-Substitute Discipline** — When a manual ceremony substitutes for an autonomous workflow (e.g., 12-agent swarm replacing cpr-enrichment-scanner.py), the manual ceremony must complete the FULL output contract of the autonomous workflow it replac…
  - *Ledger:* [`cgg-ledger/ledger.md#manual-ceremony-as-pipeline-substitute-discipline`](cgg-ledger/ledger.md#manual-ceremony-as-pipeline-substitute-discipline)
- **Verifier Install Path via Sync Manifest** — Verifier gates that diff canonical source against runtime-installed artifacts must discover the install target via the same mechanism as the syncing tool (sync-manifest.json lookup), not hardcode a parallel path assum…
  - *Ledger:* [`cgg-ledger/ledger.md#verifier-install-path-via-sync-manifest`](cgg-ledger/ledger.md#verifier-install-path-via-sync-manifest)
- **Boot-Seam Duality (Primary SessionStart vs Citizens SubagentStart)** — The primary orchestrator boots via SessionStart (`session-restore.sh`, exec'd from an INSTALLED copy via a patch shim); spawned citizens boot via SubagentStart (`subagent-citizen-boot.py`, fires from SOURCE). A boot injection for "every citizen including the primary" is TWO wirings — wiring only SubagentStart silently omits the primary; verify sync-parity on the installed SessionStart hook specifically.
  - *Ledger:* [`cgg-ledger/ledger.md#boot-seam-duality-primary-sessionstart-citizens-subagentstart`](cgg-ledger/ledger.md#boot-seam-duality-primary-sessionstart-citizens-subagentstart)

## Verification And Proof Discipline

- **Multi-Stage Governance Pipeline Stages Must Be Coupled with Proof Artifacts** — Governance pipelines with N stages each capable of silent failure (queue write → commit → install propagation → audit) collapse into "trust the pipeline ran" unless each stage produces its own auditable proof artifact…
  - *Ledger:* [`cgg-ledger/ledger.md#multi-stage-governance-pipeline-stages-must-be-coupled-with-proof-artifacts`](cgg-ledger/ledger.md#multi-stage-governance-pipeline-stages-must-be-coupled-with-proof-artifacts)
- **Remote-vs-Local Verification Scope Split for Scheduled Agents** — When scheduling a remote agent (Anthropic cloud routine) to verify a system whose state is partly local-only — install state under `~/.claude/`, machine ctimes, hooks registered to the operator's settings.json — the v…
  - *Ledger:* [`cgg-ledger/ledger.md#remote-vs-local-verification-scope-split-for-scheduled-agents`](cgg-ledger/ledger.md#remote-vs-local-verification-scope-split-for-scheduled-agents)
- **Atomic-Commit Discipline (Multi-File Mutations)** — Atomic-commit (multi-file mutations bound into single commit unit with pre-commit validation) is required CGG-scope discipline.
  - *Ledger:* [`cgg-ledger/ledger.md#atomic-commit-discipline-multi-file-mutations`](cgg-ledger/ledger.md#atomic-commit-discipline-multi-file-mutations)
- **Gate Contracts (Not Vibes)** — A gate is a contract surface, not a vibe or preference.
  - *Ledger:* [`cgg-ledger/ledger.md#gate-contracts-not-vibes`](cgg-ledger/ledger.md#gate-contracts-not-vibes)
- **Shape Fingerprint Provenance** — Composite shape hash `sha256(content_hash + ctime + birthtime + inode)` creates a deterministic fingerprint robust to single-axis spoofing.
  - *Ledger:* [`cgg-ledger/ledger.md#shape-fingerprint-provenance`](cgg-ledger/ledger.md#shape-fingerprint-provenance)
- **Read-Side Verification Complement** — Append-only ledgers provide write-side integrity but without read-side chain verification a malicious or buggy reader can present out-of-order entries as canonical.
  - *Ledger:* [`cgg-ledger/ledger.md#read-side-verification-complement`](cgg-ledger/ledger.md#read-side-verification-complement)
- **Two-Run Spec-Gate Geometry** — Spec-first with operator review gate between Run 1 (spec authoring) and Run 2 (execution) materially separates spec production from execution risk.
  - *Ledger:* [`cgg-ledger/ledger.md#two-run-spec-gate-geometry`](cgg-ledger/ledger.md#two-run-spec-gate-geometry)
- **Boundary-Aware Body Extraction** — Spec validation gates that use hardcoded line offsets for body extraction (sed -n 'N,$p' with fixed N) break silently when the mutation being validated changes the boundary position.
  - *Ledger:* [`cgg-ledger/ledger.md#boundary-aware-body-extraction`](cgg-ledger/ledger.md#boundary-aware-body-extraction)
- **Budget-Exempt Closure Framing + Unit-Safe Truncation** — A closure/safety ritual guarding a budget-bounded payload (a receipt-request frame, a truncation marker) must be EXEMPT from that budget — render the bounded body first, append the guard after. And truncation of atomic typed units (badge-bearing rays) must cut at unit boundaries with an explicit `⟨SEALED⟩` marker, never mid-unit — a half-cut ray can read as a different, dangerous instruction. Byte-safe ≠ unit-safe.
  - *Ledger:* [`cgg-ledger/ledger.md#budget-exempt-closure-framing-and-unit-safe-truncation`](cgg-ledger/ledger.md#budget-exempt-closure-framing-and-unit-safe-truncation)
- **Atomic Dual-Surface Invariant Mechanization** — When a runtime script implements one half of an atomic dual-surface invariant but fails the other half mechanically, the patch is structural (add the missing collapse step) — not narrative (re-explain the discipline i…
  - *Ledger:* [`cgg-ledger/ledger.md#atomic-dual-surface-invariant-mechanization`](cgg-ledger/ledger.md#atomic-dual-surface-invariant-mechanization)
- **Cross-File Pointer Integrity Verification** — When a multi-file refactor produces a new authoring artifact whose body contains pointers (anchors, hyperlinks, refs) into a companion artifact, the pre-swap verification gate MUST include a pointer-integrity diff: co…
  - *Ledger:* [`cgg-ledger/ledger.md#cross-file-pointer-integrity-verification`](cgg-ledger/ledger.md#cross-file-pointer-integrity-verification)

## Memory And Inscription Hygiene

- **Session Learning Protocol** — When you discover something during a session that constitutes a durable lesson — a friction point resolved, a non-obvious behavior confirmed, a workflow correction — capture it as a CogPR (Cognitive Pull Request).
  - *Ledger:* [`cgg-ledger/ledger.md#session-learning-protocol`](cgg-ledger/ledger.md#session-learning-protocol)
- **Doctrine Surface Frontmatter Sweep Methodology** — Doctrine surfaces that accrete >30 specs without frontmatter render uniformly dense to readers (Mogul, ladder-auditor, agents) regardless of whether each spec is active, forward-looking, or dormant.
  - *Ledger:* [`cgg-ledger/ledger.md#doctrine-surface-frontmatter-sweep-methodology`](cgg-ledger/ledger.md#doctrine-surface-frontmatter-sweep-methodology)
- **MEMORY.md Inline Entry Location Lock (REVIEW_PINNED)** — MEMORY.md inline entries with `status: pending` are operationally treated as location-locked until /review processes them.
  - *Ledger:* [`cgg-ledger/ledger.md#memory-md-inline-entry-location-lock-review-pinned`](cgg-ledger/ledger.md#memory-md-inline-entry-location-lock-review-pinned)
- **User-Space Handoff Referrer Surface** — User-space handoff plans (`~/.claude/plans/*.md`) live OUTSIDE federation commit boundary, accumulate ~70+ files over many tics, and each cites MEMORY.md sections from its authoring era.
  - *Ledger:* [`cgg-ledger/ledger.md#user-space-handoff-referrer-surface`](cgg-ledger/ledger.md#user-space-handoff-referrer-surface)
- **Memory-Trim Staged Execution Pattern** — High-composite-load memory-surface trims (composite mutation count >5) execute across multiple tics, not single-tic.
  - *Ledger:* [`cgg-ledger/ledger.md#memory-trim-staged-execution-pattern`](cgg-ledger/ledger.md#memory-trim-staged-execution-pattern)
- **Memory-Trim Yield Source-Awareness** — Trim sweep yield against MEMORY.md after /review depends on the EXTRACTION SOURCE of the CPRs that /review terminalized, not just the count of verdicts applied.
  - *Ledger:* [`cgg-ledger/ledger.md#memory-trim-yield-source-awareness`](cgg-ledger/ledger.md#memory-trim-yield-source-awareness)
- **Bench Packet Prep Cycle Drop Reversal** — At tic 293 the bench_packet_prep cycle was dropped from the cadence-ops scheduler (CGG commit `280a8a5`).
  - *Ledger:* [`cgg-ledger/ledger.md#bench-packet-prep-cycle-drop-reversal`](cgg-ledger/ledger.md#bench-packet-prep-cycle-drop-reversal)
- **Binder Addendum Inscription Preservation** — Operator-reviewed governance documents should receive state updates via appended addendum sections with preserved original bodies, not in-place rewrites.
  - *Ledger:* [`cgg-ledger/ledger.md#binder-addendum-inscription-preservation`](cgg-ledger/ledger.md#binder-addendum-inscription-preservation)
- **Memory-MD-Audit Breach Class Distinction** — `memory-md-audit.py` breach detection must distinguish two structurally different breach classes — STRUCTURAL breaches and PENDING-STATE breaches — because their operational response and urgency are opposite.
  - *Ledger:* [`cgg-ledger/ledger.md#memory-md-audit-breach-class-distinction`](cgg-ledger/ledger.md#memory-md-audit-breach-class-distinction)

## Forensic And Drift Investigation

- **Detection Affordance Tracking** — Promoted invariants should carry `detection_affordance` metadata tracking whether a detection mechanism exists.
  - *Ledger:* [`cgg-ledger/ledger.md#detection-affordance-tracking`](cgg-ledger/ledger.md#detection-affordance-tracking)
- **Friction-to-Invariant Pipeline** — Implementation friction generates invariant candidates through a recurring pipeline: friction → debugging → root cause → candidate → naming → promotion.
  - *Ledger:* [`cgg-ledger/ledger.md#friction-to-invariant-pipeline`](cgg-ledger/ledger.md#friction-to-invariant-pipeline)
- **Contamination Lifecycle and Forensic Investigation Discipline** — Third-party software contamination follows a structural lifecycle: (1) silent environment mutation (shell profile injection, proxy redirection without ToS disclosure), (2) persistence mechanisms (auto-launch override…
  - *Ledger:* [`cgg-ledger/ledger.md#contamination-lifecycle-and-forensic-investigation-discipline`](cgg-ledger/ledger.md#contamination-lifecycle-and-forensic-investigation-discipline)
- **Accessibility API Structural Indistinguishability** — Cross-app activity tracking via accessibility API is structurally indistinguishable from legitimate dictation context — the app needs focused_app_bundle_id to deliver text.
  - *Ledger:* [`cgg-ledger/ledger.md#accessibility-api-structural-indistinguishability`](cgg-ledger/ledger.md#accessibility-api-structural-indistinguishability)
- **Competing Canons / Hardening Pass Obligation** — Report artifacts that span an iterative build accumulate competing canons when the approach changes mid-session but earlier sections aren't rewritten.
  - *Ledger:* [`cgg-ledger/ledger.md#competing-canons-hardening-pass-obligation`](cgg-ledger/ledger.md#competing-canons-hardening-pass-obligation)
- **Baseline Re-Anchoring After Intentional State Change** — Integrity sentinels that detect remediation-era changes must be rebaselined immediately after cleanup completes.
  - *Ledger:* [`cgg-ledger/ledger.md#baseline-re-anchoring-after-intentional-state-change`](cgg-ledger/ledger.md#baseline-re-anchoring-after-intentional-state-change)
- **Multi-Session Artifact Provenance** — Forensic reports spanning multiple investigation sessions must carry explicit per-finding timestamps, not a single document date.
  - *Ledger:* [`cgg-ledger/ledger.md#multi-session-artifact-provenance`](cgg-ledger/ledger.md#multi-session-artifact-provenance)
- **Drift Classification Taxonomy** — When auditing an adapter for API drift, classify each line as: accurate (matches current docs), likely stale (was accurate, drift detected), unverified from public docs (may work but not documented), or custom layer (…
  - *Ledger:* [`cgg-ledger/ledger.md#drift-classification-taxonomy`](cgg-ledger/ledger.md#drift-classification-taxonomy)
- **Context-Aware Severity Classification** — Pattern-matching severity ("if path contains X then critical") produces false escalation under remediation-era state changes.
  - *Ledger:* [`cgg-ledger/ledger.md#context-aware-severity-classification`](cgg-ledger/ledger.md#context-aware-severity-classification)
- **Sentinel-Integrity Triple Summary** — Three validations form a coherent integrity surface: (1) Shape Fingerprint Provenance — hash composition prevents single-axis spoofing, (2) Read-Side Verification Complement — ledger reading verifies chain integrity,…
  - *Ledger:* [`cgg-ledger/ledger.md#sentinel-integrity-triple-summary`](cgg-ledger/ledger.md#sentinel-integrity-triple-summary)
- **Extractor Anomaly Self-Reporting** — Extractors that produce zero output or anomalous counts (extreme divergence from expected range) must emit explicit diagnostic output to stderr or a dedicated anomaly log, not silence.
  - *Ledger:* [`cgg-ledger/ledger.md#extractor-anomaly-self-reporting`](cgg-ledger/ledger.md#extractor-anomaly-self-reporting)
- **Extractor Output Anomaly Flagging** — cpr-extract.py that finds N blocks but extracts 0 should surface the discrepancy.
  - *Ledger:* [`cgg-ledger/ledger.md#extractor-output-anomaly-flagging`](cgg-ledger/ledger.md#extractor-output-anomaly-flagging)
- **Generator-vs-Local-Repair Gap (Handoff Title Format)** — When a convention drift recurs across sessions (cross-tic n≥3 instances) and originates in a TEMPLATE that agents follow (skill body, spec, mandate format), the fix MUST land at the generator surface.
  - *Ledger:* [`cgg-ledger/ledger.md#generator-vs-local-repair-gap-handoff-title-format`](cgg-ledger/ledger.md#generator-vs-local-repair-gap-handoff-title-format)

## Pipeline And Integration

- **JSONL Atomic Writes (PRIMITIVE)** — All JSONL append-only files (`audit-logs/**/*.jsonl`) must use atomic append to prevent corruption from concurrent writers (hooks, session-start, Mogul cycles).
  - *Ledger:* [`cgg-ledger/ledger.md#jsonl-atomic-writes-primitive`](cgg-ledger/ledger.md#jsonl-atomic-writes-primitive)
- **Governance Label Accuracy** — 'Observer-first' is a governance label that systematically understates commitment.
  - *Ledger:* [`cgg-ledger/ledger.md#governance-label-accuracy`](cgg-ledger/ledger.md#governance-label-accuracy)
- **Copilot Script Classification (tier_2_adapt)** — External prompt systems that require human execution (e.g., "Open Chrome and navigate to...") are most accurately classified as `tier_2_adapt` — copilot scripts, not agent-executable envelopes.
  - *Ledger:* [`cgg-ledger/ledger.md#copilot-script-classification-tier-2-adapt`](cgg-ledger/ledger.md#copilot-script-classification-tier-2-adapt)
- **Bash-Python Quoting Collapse** — Inline Python in bash heredoc (`python3 -c "..."`) silently breaks when the Python code contains triple-quoted docstrings — bash C-style quoting (`$'...'`) mangles triple quotes into string terminators.
  - *Ledger:* [`cgg-ledger/ledger.md#bash-python-quoting-collapse`](cgg-ledger/ledger.md#bash-python-quoting-collapse)
- **Handoff Carry-Forward Probe Discipline** — Handoffs themselves are L3-class snapshots under the Volatility Handling Law.
  - *Ledger:* [`cgg-ledger/ledger.md#handoff-carry-forward-probe-discipline`](cgg-ledger/ledger.md#handoff-carry-forward-probe-discipline)
- **Recursive Self-Observation** — When a governance configuration surface is consumed by the mechanism it governs, the system exhibits recursive self-observation — the observer observing itself.
  - *Ledger:* [`cgg-ledger/ledger.md#recursive-self-observation`](cgg-ledger/ledger.md#recursive-self-observation)
- **Signal Resolution Writeback Atomicity (Dual-Surface)** — When signals are resolved in daily files (`audit-logs/signals/YYYY-MM-DD.jsonl`), the active-manifest may not receive a corresponding write — divergence between daily file truth and manifest curation.
  - *Ledger:* [`cgg-ledger/ledger.md#signal-resolution-writeback-atomicity-dual-surface`](cgg-ledger/ledger.md#signal-resolution-writeback-atomicity-dual-surface)
- **Precedence-Authority Envelopes (Cross-Clade Typed)** — Cross-clade typed envelopes that carry precedence-ordering authority as a first-class field.
  - *Ledger:* [`cgg-ledger/ledger.md#precedence-authority-envelopes-cross-clade-typed`](cgg-ledger/ledger.md#precedence-authority-envelopes-cross-clade-typed)
- **Cross-Estate Integration Assessment Triple Test** — Cross-estate integration assessments should use a triple-intersection test (federation invariants × estate's mandate × concrete operational evidence) to distinguish viable adoption from incidental compatibility.
  - *Ledger:* [`cgg-ledger/ledger.md#cross-estate-integration-assessment-triple-test`](cgg-ledger/ledger.md#cross-estate-integration-assessment-triple-test)
- **Composite Mutation Assessment at LEAD Level** — CogPR-117 (composite mutation scheduling) is systematically invisible to advocate-level reasoning in governed arenas.
  - *Ledger:* [`cgg-ledger/ledger.md#composite-mutation-assessment-at-lead-level`](cgg-ledger/ledger.md#composite-mutation-assessment-at-lead-level)
- **Wire-Cut Scoping by Capability Class** — Containment wire-cuts must be scoped to capability classes (ingress, all, panic), not binary on/off.
  - *Ledger:* [`cgg-ledger/ledger.md#wire-cut-scoping-by-capability-class`](cgg-ledger/ledger.md#wire-cut-scoping-by-capability-class)
- **Pattern Mining Context Procurement** — Pattern mining context procurement must precede mining — a briefing covering governance surfaces with NLP heuristics (bigram frequency, Gini coefficient, temporal clustering, entity co-occurrence) empowers mining agen…
  - *Ledger:* [`cgg-ledger/ledger.md#pattern-mining-context-procurement`](cgg-ledger/ledger.md#pattern-mining-context-procurement)
- **Inter-Engine Integration Emission** — When two engines share state through a registry file, the producing engine must emit records in the consuming engine's expected format.
  - *Ledger:* [`cgg-ledger/ledger.md#inter-engine-integration-emission`](cgg-ledger/ledger.md#inter-engine-integration-emission)
- **Single Routing Surface for Generation and Adjudication** — External media API routers (generation + adjudication) should share a single routing surface and budget.
  - *Ledger:* [`cgg-ledger/ledger.md#single-routing-surface-for-generation-and-adjudication`](cgg-ledger/ledger.md#single-routing-surface-for-generation-and-adjudication)
- **Overlay-at-Timestamp Assembly** — B-roll assembly must use overlay-at-timestamp (video replaces speaker footage at specific time windows), not insert-between-segments (video spliced into the timeline).
  - *Ledger:* [`cgg-ledger/ledger.md#overlay-at-timestamp-assembly`](cgg-ledger/ledger.md#overlay-at-timestamp-assembly)
- **Morph Transition Grammar** — Morph transitions are atomic compound operations: (1) keyframes must come from different visual worlds — two real frames produce camera interpolation, not transformation; (2) OUT morph chains from IN morph's actual la…
  - *Ledger:* [`cgg-ledger/ledger.md#morph-transition-grammar`](cgg-ledger/ledger.md#morph-transition-grammar)
- **Timeline Lock and Base Track Preparation** — Timeline lock (freezing the edited base track before generation) requires re-transcription of the edited base track BEFORE locking.
  - *Ledger:* [`cgg-ledger/ledger.md#timeline-lock-and-base-track-preparation`](cgg-ledger/ledger.md#timeline-lock-and-base-track-preparation)
- **Temporal Scope Discipline** — **Federation-scoped tic resolution for duration measurement** — governance functions measuring duration in federation tics must resolve from the canonical tic log (`audit-logs/tics/*.jsonl`, field: `domain_counter_aft…
  - *Ledger:* [`cgg-ledger/ledger.md#temporal-scope-discipline`](cgg-ledger/ledger.md#temporal-scope-discipline)
- **Governed Bridge Mechanics** — **Loneliness intervention as governed bridge mechanic** — isolated nodes in proximity-based networks experience self-reinforcing isolation: no neighbors means no interactions, no interactions means no trust accumulati…
  - *Ledger:* [`cgg-ledger/ledger.md#governed-bridge-mechanics`](cgg-ledger/ledger.md#governed-bridge-mechanics)
- **Inbox Triple-Source Sync** — Inbox archive operations must propagate across three sources of truth: (1) filesystem (WAIT/ACTIVE/DONE prefixes on files), (2) inbox-registry.json (canonical state enumeration), (3) hook-detection state (what the hoo…
  - *Ledger:* [`cgg-ledger/ledger.md#inbox-triple-source-sync`](cgg-ledger/ledger.md#inbox-triple-source-sync)
- **Open Question Classification (Probe-First Test)** — Open questions in specs classify by what resolves them: (a) operator-judgment (require human decision), (b) evidence-probe (resolvable by small filesystem or state inspection), (c) deferred (non-blocking, carry to lat…
  - *Ledger:* [`cgg-ledger/ledger.md#open-question-classification-probe-first-test`](cgg-ledger/ledger.md#open-question-classification-probe-first-test)
- **Spec as Tone Exemplar** — When a spec also functions as the tone exemplar for downstream deliverables that will imitate it, spec-level tone discipline matters more than discipline on comparable non-exemplar specs.
  - *Ledger:* [`cgg-ledger/ledger.md#spec-as-tone-exemplar`](cgg-ledger/ledger.md#spec-as-tone-exemplar)
- **Centroid-Ray Semantic Primitive** — A centroid is the weighted average position of a semantic cluster in a high-dimensional space (e.g., value position, computational cost, governance scope).
  - *Ledger:* [`cgg-ledger/ledger.md#centroid-ray-semantic-primitive`](cgg-ledger/ledger.md#centroid-ray-semantic-primitive)
- **Collapse Zone vs Sibling Overlap Distinction** — In multi-axis design spaces, a collapse zone is a region where multiple axes converge such that orthogonality breaks down (e.g., two previously independent variables become correlated).
  - *Ledger:* [`cgg-ledger/ledger.md#collapse-zone-vs-sibling-overlap-distinction`](cgg-ledger/ledger.md#collapse-zone-vs-sibling-overlap-distinction)
- **Negative Contour Via Is-Not Clause** — When defining a semantic boundary (what a concept is), explicit is-not clauses often sharpen meaning better than positive definition.
  - *Ledger:* [`cgg-ledger/ledger.md#negative-contour-via-is-not-clause`](cgg-ledger/ledger.md#negative-contour-via-is-not-clause)
- **Semantic Primitives Precede Mathematical Closure** — In specification design, establish semantic primitives (named concepts with boundaries) before deriving mathematical models.
  - *Ledger:* [`cgg-ledger/ledger.md#semantic-primitives-precede-mathematical-closure`](cgg-ledger/ledger.md#semantic-primitives-precede-mathematical-closure)
- **Cross-Centroid Ray Recurrence Mining** — When the same ray (same boundary condition, same edge case) appears in multiple semantic clusters (multiple domain problems, multiple specification contexts), it becomes a general principle worth mining and naming.
  - *Ledger:* [`cgg-ledger/ledger.md#cross-centroid-ray-recurrence-mining`](cgg-ledger/ledger.md#cross-centroid-ray-recurrence-mining)
- **Enrichment Pipeline Silent Starvation Surface** — When an enrichment tool is meant to run periodically (e.g., pattern mining, queue analysis) but no invocation schedule exists, the tool operates in a starvation state: dormant but not erroring.
  - *Ledger:* [`cgg-ledger/ledger.md#enrichment-pipeline-silent-starvation-surface`](cgg-ledger/ledger.md#enrichment-pipeline-silent-starvation-surface)
- **Consolidate Pre-Flight Discipline** — When `/consolidate` runs against an estate-spanning surface, two pre-flight disciplines apply before the consolidation produces an authoritative artifact.
  - *Ledger:* [`cgg-ledger/ledger.md#consolidate-pre-flight-discipline`](cgg-ledger/ledger.md#consolidate-pre-flight-discipline)
- **Conductor-Score-Runtime Parity (CGG Application)** — When CGG governance doctrine names a discipline that the runtime scripts do not enforce, the gap is a parity problem with four mechanism classes — field passthrough, terminal-state valves, schema key signatures, and r…
  - *Ledger:* [`cgg-ledger/ledger.md#conductor-score-runtime-parity-cgg-application`](cgg-ledger/ledger.md#conductor-score-runtime-parity-cgg-application)
- **Tracked External Scripts Pattern** — Some runtime-invokable scripts cannot be relocated to the standard install tree because they are path-locked to a non-runtime location (e.g., build_queue_index.py uses `Path(__file__).parent` to resolve queue.jsonl as…
  - *Ledger:* [`cgg-ledger/ledger.md#tracked-external-scripts-pattern`](cgg-ledger/ledger.md#tracked-external-scripts-pattern)
- **Extractor Schema Field Mapping** — cpr-extract.py requires source + lesson fields; rich authoring schemas (title/summary/abstraction_layers as emitted by cadence handoffs) are silently dropped.
  - *Ledger:* [`cgg-ledger/ledger.md#extractor-schema-field-mapping`](cgg-ledger/ledger.md#extractor-schema-field-mapping)
- **Patch Landing Five-Stage Discipline** — Substrate-modifying patches (extractor schema, queue read/write semantics, signal manifold rules) benefit from a 5-stage landing discipline: (1) spec — operator-authored or agent-validated contract with explicit tier…
  - *Ledger:* [`cgg-ledger/ledger.md#patch-landing-five-stage-discipline`](cgg-ledger/ledger.md#patch-landing-five-stage-discipline)
- **v2.1-lite Agent Routing-Disambiguation Frontmatter** — The v2.1 routing frontmatter format (CENTROID + IS + IS NOT [collapse_zones + sibling_overlaps] + WHEN + NOT WHEN + RELATES TO) was established at the skill rung as a routing-disambiguation primitive against silent mi…
  - *Ledger:* [`cgg-ledger/ledger.md#v2-1-lite-agent-routing-disambiguation-frontmatter`](cgg-ledger/ledger.md#v2-1-lite-agent-routing-disambiguation-frontmatter)
- **CGG Manifest Pointer Anti-Docrot Discipline** — For CGG runtime documentation, sync-manifest.json is the authoritative source for installed runtime surfaces.
  - *Ledger:* [`cgg-ledger/ledger.md#cgg-manifest-pointer-anti-docrot-discipline`](cgg-ledger/ledger.md#cgg-manifest-pointer-anti-docrot-discipline)
- **Manifest-Driven Inversion Harness Primitive *(PROMOTE-SPEC, tic 294)*** — Federation observability primitive distinct from per-script audit tools (memory-md-audit.py, queue-drift-audit.py, runtime-sync, contam-sentinel).
  - *Ledger:* [`cgg-ledger/ledger.md#manifest-driven-inversion-harness-primitive-promote-spec-tic-294`](cgg-ledger/ledger.md#manifest-driven-inversion-harness-primitive-promote-spec-tic-294)
- **Compile-Lane Consumer Integration Pattern** — Compile-lane consumer integration pattern.
  - *Ledger:* [`cgg-ledger/ledger.md#compile-lane-consumer-integration-pattern`](cgg-ledger/ledger.md#compile-lane-consumer-integration-pattern)
- **Orchestrator-on-Behalf-of-Subordinate Trace Pattern** — Orchestrator-on-behalf-of subordinate-trace pattern.
  - *Ledger:* [`cgg-ledger/ledger.md#orchestrator-on-behalf-of-subordinate-trace-pattern`](cgg-ledger/ledger.md#orchestrator-on-behalf-of-subordinate-trace-pattern)
- **Inline-Tracked CogPR DEFER Keeps status:pending (/review Step 7 Discipline)** — When a /review DEFER verdict lands on an INLINE-tracked CogPR (one that lives as a `status: pending` block in MEMORY.md and is NOT resident in queue.jsonl), do NOT change its inline status to enrichment_eligible/defer…
  - *Ledger:* [`cgg-ledger/ledger.md#inline-tracked-cogpr-defer-keeps-status-pending-review-step-7-discipline`](cgg-ledger/ledger.md#inline-tracked-cogpr-defer-keeps-status-pending-review-step-7-discipline)
- **Artifact-Count-≠-1 Fix-Family (Emit-Side Complement to Authoritative-Set Readers)** — Artifact-count-≠-1 is a single failure class spanning both N=0 (no report) and N=2 (duplicate report) cardinalities — not two separate per-incident bugs.
  - *Ledger:* [`cgg-ledger/ledger.md#artifact-count-1-fix-family-emit-side-complement-to-authoritative-set-readers`](cgg-ledger/ledger.md#artifact-count-1-fix-family-emit-side-complement-to-authoritative-set-readers)
- **R²-Roadrunner Runtime Context Sharpening Pattern** — R²-Roadrunner (Recursive-Refinement Roadrunner) names the runtime-context sharpening pattern where a coarse single-binder hydrate at session entry is iteratively narrowed by follow-on probes until the working scope is…
  - *Ledger:* [`cgg-ledger/ledger.md#r-roadrunner-runtime-context-sharpening-pattern`](cgg-ledger/ledger.md#r-roadrunner-runtime-context-sharpening-pattern)
- **Cockpit.intent Invocation Discipline (T2b)** — `cockpit.intent` (30th envelope class, `ak_control_room/envelopes.yaml`) emits via three governed surfaces per T2b spec (`audit-logs/governance/cockpit-intent-t2b-invocation-discipline-spec-tic264.md`); a fourth surfa…
  - *Ledger:* [`cgg-ledger/ledger.md#cockpit-intent-invocation-discipline-t2b`](cgg-ledger/ledger.md#cockpit-intent-invocation-discipline-t2b)
