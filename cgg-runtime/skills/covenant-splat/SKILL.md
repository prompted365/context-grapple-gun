---
name: covenant-splat
description: |
  Splat-conditioned covenant interpretation for the live board: rehydrate an ADMITTED
  current→target covenant against current reality, propose its decomposition as a bounded
  morphism, lower it to CovenantExpr/FragmentDAG, and validate the board projection —
  under the kernel contract (autonomous_kernel/covenant-splat-fqoq-runtime-spec.md).
  Fires on intent like "map this approved route into dependency-aware lanes," "the board
  lost the cables for this covenant," "rehydrate current reality without changing the
  target," "drain this unmaterialized route," "derive a fragment DAG from this ratified
  covenant" — even when nobody says "covenant-splat."

  CENTROID:
  admitted covenant → lawful current conformation slice → bounded morphism proposal → FragmentDAG contract

  IS:
  - the per-route drain procedure (§14 resolver — locate the admitted covenant, never re-litigate it, diagnose exactly one state)
  - CovenantSlice scaffold hydration from the compiler-visible field, fail-closed per source (scripts/hydrate-covenant-slice.py)
  - deterministic, csl-parity CovenantExpr → FragmentDAG lowering with occurrence-namespaced ids + choice ancestry (scripts/lower-covenant-expr.py)
  - board-projection validation with hash recomputation + honest unimplemented-assertion disclosure (scripts/validate-covenant-projection.py)
  - bounded agentic six-facet interpretation UNDER the morphism-proposer prohibitions (spec §9)

  IS NOT:
    collapse_zones:
      - covenant authority source (the kernel spec + admission receipts rule; this skill derives and proposes)
      - evidence-enrichment system (missing faces = unmaterialized decomposition, NOT evidence deficit)
      - route-metadata authoring lane (route-metadata.json is derived cache/override — never semantic authority)
      - re-adjudication surface (an admitted covenant is never re-litigated by tic/session/model/regeneration)
      - doctrine body (the kernel spec is the doctrine; edits route through /review)
      - terminalizer (canonical owns durable board truth; a proposal never lands itself)
      - the missing interpreter itself (see Current capability boundary — the scaffold and the lowerer are NOT the splat-conditioned agentic interpreter)
    sibling_overlaps:
      - harpoon-sequencer.py (it COMPILES the conformation slice from existing projections; this skill MATERIALIZES covenant projections INTO it — compiler vs materializer)
      - /tactical-hydration (generic intent→evidence discovery for unknown targets; this skill is covenant-specific hydration where the identity is already known — use RTCH when you don't yet know where to look)
      - /review (admission on the covenant OBJECT; this skill operates strictly downstream of admission — if the covenant itself needs judging, route there)
      - /consolidate (packages known surfaces into one dump; this skill interprets one route's covenant, it never bulk-packages)

  WHEN:
  - draining a covenant_decomposition_unmaterialized route (the unmaterialized cohort in the live slice)
  - a board route's covenant projection was lost, thinned, or never materialized and must be restored from admitted authority
  - decomposing an admitted covenant into CovenantExpr/FragmentDAG for the Rust boundary
  - reality changed (provider, write surface, runtime) and the route must re-splat WITHOUT the target moving
  - validating that the live board's covenant projections honor the kernel contract
  - constructing ordering (build ⊳ test ⊳ deploy) upstream of the crates (they execute topology, they do not infer it)

  NOT WHEN:
  - no admitted covenant exists and none is being located (that is covenant_absent — fresh judgment or /review if target/authority/scope would change)
  - the task is generic file discovery (use /tactical-hydration)
  - the covenant object itself needs admission (route to /review — coherence is not admission)
  - the ask is a board-wide compile or GO/NO-GO (run harpoon-sequencer.py --mode live; this skill is per-route)

  RELATES TO:
  - autonomous_kernel/covenant-splat-fqoq-runtime-spec.md (the ONLY doctrine body; this skill discloses it, never owns it)
  - audit-logs/governance/board-live-compiler-directive-tic621.md ADDENDUM 4 (label-retirement + demotion lineage)
  - canonical_developer/homeskillet-csl/ (the crates ARE the infra — this skill's lowerer mirrors their contract; the crates execute, this skill prepares)
  - canonical_developer/canonical-mount/ (the bounded-intelligence invocation rail — interim frontier interpreters and future local models dispatch through it, proposal-band, never as authority)

  ARGS:
    stance: dispatch
    off_envelope: ask
    core_dispatch_rays:
      - ""            → interactive (name the route/covenant, pick the lane)
      - "drain <id>"  → per-route §14 resolver walk (hydrate → locate covenant → diagnose exactly one)
      - "hydrate <id>"→ CovenantSlice scaffold for a backlog identity
      - "lower <file>"→ CovenantExpr JSON → FragmentDAG + waves (--pick g0=L resolves choices)
      - "validate"    → board-projection shape check (exit 0/1)
compatibility: >
  PROVISIONAL FIELD (AUTHORING_CONVENTION.md:308 — provisional-with-annotation pending
  convention review). Requires a canonical federation checkout containing
  autonomous_kernel/covenant-splat-fqoq-runtime-spec.md + the harpoon-office board
  surfaces, and Python 3. Outside the zone every script refuses with a typed
  COVENANT_SPLAT_ZONE_UNAVAILABLE and attempts no covenant judgment.
---

# covenant-splat — splat-conditioned covenant interpretation

**Read the kernel contract FIRST** (once per session): `autonomous_kernel/covenant-splat-fqoq-runtime-spec.md` — read instructions in `references/kernel-contract.md`. This skill is the operational progressive-disclosure surface; the spec is the doctrine body. Do not restate the spec from memory — follow the pointer.

## Current capability boundary

This skill currently provides: deterministic field-scaffold hydration · human/agent-guided six-facet interpretation · deterministic lowering of an already-proposed CovenantExpr (csl-parity ids + choice ancestry + resolution) · board-projection shape validation with recomputed hashes.

**The registered kernel runtime that performs the complete splat-conditioned agentic covenant interpretation is NOT yet built** (spec §16: the missing runtime join; §3: a future interpreter earns its own KERNEL_REGISTRATION.md). Never present the scaffold or the lowerer as that missing interpreter. Interim, a frontier agent holds the interpreter seat — dispatched proposal-band through canonical-mount, emitting the same SP5-shaped bid a local model would, so the eventual handoff is measurable.

## Procedure (the drain's first motion, per route)

1. **Hydrate** the current field: `python3 scripts/hydrate-covenant-slice.py <backlog-id>` → a CovenantSlice **scaffold** (typed-null facets, per-source status envelope). The scaffold is not a covenant.
2. **Locate the admitted covenant** (admission receipt, /review verdict, directive, ratified spec). If it exists — **do NOT re-litigate it.** Underdefined for decomposition → return `COVENANT_INSUFFICIENT` naming the missing faces. No covenant → `covenant_absent` — classify its `sub_shape` (`prose_pointer_absent` | `wrong_object_class`; kernel spec §14 sub-shape discipline, /review 634): the two carry OPPOSITE unheld paths (admission-routing vs retire/reclassify-before-admission).
3. **Run the six-facet splat** (KAT·APO·PAR·PLE·ENA·TEL, cross-bound one record) against NAVIGATION / io-map / router / repo+runtime state / receipts + OT scars. Record `narrowed_to · why_not_further · excluded · de_considered · suspended · live_under_conditions · renarrow_triggers` — the narrowing receipt is half the work.
4. **Propose morphisms** (anchors, write surfaces, fragment boundaries, ⊳/∥/⊕ relations, consumers, success predicates, rollback) — as a **bounded morphism-proposer** under the spec §9 prohibitions.
5. **Lower deterministically**: `python3 scripts/lower-covenant-expr.py <covenant-expr.json>` — occurrence-namespaced ids, choice ancestry, `--pick` resolution; sequential creates dependency edges, parallel none, choice stays branch metadata.
6. **Diagnose exactly one** §14 state (`references/route-diagnosis.md`) and persist the derived route contract as a `derivation`-typed entry WITH source pointers + hashes AND its slice disclosure (route-metadata.json = derived cache, never authoring surface).
7. **Validate the projection**: `python3 scripts/validate-covenant-projection.py` (exit 0/1; recomputes hashes; discloses unimplemented assertions honestly).

## Gotchas (the category errors this skill exists to prevent)

- A backlog row is not a covenant.
- A Claude Code plan is not a covenant.
- Route metadata is not the covenant source.
- An admitted covenant does not re-earn authority every tic.
- A changed reality invalidates a decomposition before it invalidates a target.
- Missing anchors/cables = decomposition or covenant-definition failure, not automatically evidence failure.
- canonical-mount/model output is a proposed morphism, never authority.
- The held-open center is never a target, fragment, or model output.
- A freshly generated slice is not per-route currency — a stale thing can be freshly rendered (conformation stays `unknown` until checked).
- A null axis is a demand for real work, never a default to paper over.

## References (load on demand — progressive disclosure)

- `references/kernel-contract.md` — how to read the kernel spec (the ONLY doctrine body)
- `references/route-diagnosis.md` — the §14 resolver order + diagnoses + five-status axes + axis fail-closed law
- `references/maps-and-ownership.md` — NAVIGATION/io-map/router roles vs the board's sequencing role
- `references/lowering-interface.md` — the homeskillet-csl lowering contract, exact id scheme, thin-covenant caveat

## Evals

- `evals/smoke-tests.json` — runnable contract checks (scripts + compiler)
- `evals/evals.json` — agent-facing behavioral cases (re-litigation refusal, covenant_absent honesty, authority-widening refusal, …)
- `evals/trigger-evals.json` — should-trigger / should-not-trigger routing set
