---
name: covenant-splat
description: |
  Splat-conditioned covenant interpretation for the live board: rehydrate an ADMITTED
  current→target covenant against current reality, propose its decomposition as a bounded
  morphism, bind that proposal to the generic temporal-splat protocol, lower it to a
  receipted FragmentDAG, and validate the board projection — under the kernel contract
  (autonomous_kernel/covenant-splat-fqoq-runtime-spec.md).
  Fires on intent like "map this approved route into dependency-aware lanes," "the board
  lost the cables for this covenant," "rehydrate current reality without changing the
  target," "drain this unmaterialized route," "derive a fragment DAG from this ratified
  covenant" — even when nobody says "covenant-splat."

  CENTROID:
  admitted covenant → lawful current conformation slice → bounded morphism proposal → receipted temporal intake → FragmentDAG contract

  IS:
  - the per-route drain procedure (§14 resolver — locate the admitted covenant, never re-litigate it, diagnose exactly one state)
  - CovenantSlice scaffold hydration from the compiler-visible field, fail-closed per source (scripts/hydrate-covenant-slice.py)
  - the CGG-owned typed crossing from hydrated field + admitted covenant into SplatInterpretationRequestV1 / SplatProposalEnvelopeV1 (cgg-runtime/crates/cgg-temporal-adapter)
  - a deterministic Python parity oracle for CovenantExpr → FragmentDAG identities, choices, edges, and waves (scripts/lower-covenant-expr.py)
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
      - the registered interpreter itself (the deterministic temporal runtime is implemented; this skill and adapter do not become registered until the joined lane earns KERNEL_REGISTRATION.md)
    sibling_overlaps:
      - harpoon-sequencer.py (it COMPILES the conformation slice from existing projections; this skill MATERIALIZES covenant projections INTO it — compiler vs materializer)
      - /tactical-hydration (generic intent→evidence discovery for unknown targets; this skill is covenant-specific hydration where the identity is already known — use RTCH when you don't yet know where to look)
      - /review (admission on the covenant OBJECT; this skill operates strictly downstream of admission — if the covenant itself needs judging, route there)
      - /consolidate (packages known surfaces into one dump; this skill interprets one route's covenant, it never bulk-packages)

  WHEN:
  - draining a covenant_decomposition_unmaterialized route (the unmaterialized cohort in the live slice)
  - a board route's covenant projection was lost, thinned, or never materialized and must be restored from admitted authority
  - binding an admitted covenant and hydrated field into the generic temporal runtime request contract
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
  - prompted365/homeskillet-csl PR #4 (pure-Rust temporal mechanics, protocol validation, deterministic lowerer, existing-Harpoon adapter; canonical still terminalizes)
  - prompted365/canonical-mount (bounded-intelligence invocation rail; proposal-band, never authority)

  ARGS:
    stance: dispatch
    off_envelope: ask
    core_dispatch_rays:
      - ""              → interactive (name the route/covenant, pick the lane)
      - "drain <id>"    → per-route §14 resolver walk (hydrate → locate covenant → diagnose exactly one)
      - "hydrate <id>"  → CovenantSlice scaffold for a backlog identity
      - "bind <file>"   → hydrated slice + admission binding → SplatInterpretationRequestV1
      - "normalize <request> <mount-report>" → canonical-mount result → SplatProposalEnvelopeV1
      - "lower <file>"  → Python parity oracle: CovenantExpr JSON → FragmentDAG + waves
      - "validate"      → board-projection shape check (exit 0/1)
compatibility: >
  PROVISIONAL FIELD (AUTHORING_CONVENTION.md:308 — provisional-with-annotation pending
  convention review). Requires a canonical federation checkout containing
  autonomous_kernel/covenant-splat-fqoq-runtime-spec.md + the harpoon-office board
  surfaces, Python 3 for scaffold/parity scripts, and Rust for the typed interpreter
  cable. Outside the zone every script refuses with a typed
  COVENANT_SPLAT_ZONE_UNAVAILABLE and attempts no covenant judgment.
---

# covenant-splat — splat-conditioned covenant interpretation

**Read the kernel contract FIRST** (once per session): `autonomous_kernel/covenant-splat-fqoq-runtime-spec.md` — read instructions in `references/kernel-contract.md`. This skill is the operational progressive-disclosure surface; the spec is the doctrine body. Do not restate the spec from memory — follow the pointer.

## Current capability boundary

This skill provides deterministic field-scaffold hydration, human/agent-guided six-facet interpretation, a typed CGG-owned request/proposal cable, a Python lowering parity oracle, and board-projection shape validation.

**The deterministic pure-Rust temporal runtime is implemented in `prompted365/homeskillet-csl` PR #4.** It provides typed temporal coordinates and world separation, lawful path gating, multidimensional pressure transport, reversible runtime marks, canonical-federation intake, append-only journaling, deterministic execution lowering, and an exact adapter into the existing Harpoon DAG/rollback receipt machinery.

**The review-head crossing is implemented and green, but the registered lane is not live.** The exact chain now exercised is: hydrated `CovenantSlice` + admitted covenant → `SplatInterpretationRequestV1` → proposal-band canonical-mount invocation → CGG normalization into `SplatProposalEnvelopeV1` → homeskillet request/proposal/kernel/Harpoon seal. Component rollback, projection-isolation, and longitudinal-contamination tests are green on pinned review heads. The separate `canonical_federation` registration candidate remains staged and non-activating. Landing the dependency stack, regenerating current canonical board/surface inputs, running live dual-shadow observation windows, moving a selector, and canonical absorption remain governed gates.

The Python lowerer is now a parity oracle and migration fixture. It is not the operative temporal runtime, an authority source, or a terminalizer.

## Procedure (the drain's first motion, per route)

1. **Hydrate** the current field: `python3 scripts/hydrate-covenant-slice.py <backlog-id>` → a CovenantSlice **scaffold** (typed-null facets, per-source status envelope). The scaffold is not a covenant.
2. **Locate the admitted covenant** (admission receipt, /review verdict, directive, ratified spec). If it exists — **do NOT re-litigate it.** Underdefined for decomposition → return `COVENANT_INSUFFICIENT` naming the missing faces. No covenant → `covenant_absent` — classify its `sub_shape` (`prose_pointer_absent` | `wrong_object_class`; kernel spec §14 sub-shape discipline, /review 634): the two carry OPPOSITE unheld paths (admission-routing vs retire/reclassify-before-admission).
3. **Bind the request**: from `cgg-runtime/crates/cgg-temporal-adapter`, run `cargo run -- prepare-request <binding.json>`. This binds the scaffold to the covenant id/hash, admission receipt, exact tic + causal frontier, five axes, source hashes, authority ceiling, and center exclusion. The adapter refuses stale tics, missing admission, authority widening, malformed hashes, and non-actual ingress.
4. **Run the six-facet splat** (KAT·APO·PAR·PLE·ENA·TEL, cross-bound one record) against NAVIGATION / io-map / router / repo+runtime state / receipts + OT scars. Record `narrowed_to · why_not_further · excluded · de_considered · suspended · live_under_conditions · renarrow_triggers` — the narrowing receipt is half the work.
5. **Invoke bounded intelligence** through canonical-mount, proposal-band only. Its report text must be one `InterpretationResultV1`; the model cannot admit itself, lift currentness, widen authority, invent receipts, or terminalize.
6. **Normalize the proposal**: `cargo run -- normalize-proposal <request.json> <canonical-mount.json>` → `SplatProposalEnvelopeV1`, cryptographically bound to the exact request. The downstream temporal kernel imports the generic protocol and contains no CGG dependency.
7. **Check lowering parity**: `python3 scripts/lower-covenant-expr.py <covenant-expr.json>` remains the deterministic oracle for occurrence identities, full choice ancestry, edge sets, and waves. The operative Rust lane is `splat-harpoon-compat`; existing Harpoon owns fulfillment and rollback.
8. **Diagnose exactly one** §14 state (`references/route-diagnosis.md`) and persist the derived route contract as a `derivation`-typed entry WITH source pointers + hashes AND its slice disclosure (route-metadata.json = derived cache, never authoring surface).
9. **Validate the projection**: `python3 scripts/validate-covenant-projection.py` (exit 0/1; recomputes hashes; discloses unimplemented assertions honestly).

## Gotchas (the category errors this skill exists to prevent)

- A backlog row is not a covenant.
- A Claude Code plan is not a covenant.
- Route metadata is not the covenant source.
- An admitted covenant does not re-earn authority every tic.
- A changed reality invalidates a decomposition before it invalidates a target.
- Missing anchors/cables = decomposition or covenant-definition failure, not automatically evidence failure.
- canonical-mount/model output is a proposed morphism, never authority.
- The CGG adapter normalizes and binds; it does not fill missing facets, choose a winner, or improve an axis.
- The held-open center is never a target, fragment, route, mutable state, or model output.
- A freshly generated slice is not per-route currency — a stale thing can be freshly rendered (conformation stays `unknown` until checked).
- A null axis is a demand for real work, never a default to paper over.
- A shadow proposal is not an execution receipt, and a forecast is not an actual observation.

## References (load on demand — progressive disclosure)

- `references/kernel-contract.md` — how to read the kernel spec (the ONLY doctrine body)
- `references/route-diagnosis.md` — the §14 resolver order + diagnoses + five-status axes + axis fail-closed law
- `references/maps-and-ownership.md` — NAVIGATION/io-map/router roles vs the board's sequencing role
- `references/lowering-interface.md` — Python parity oracle, operative Rust lowerer, and existing-Harpoon fulfillment boundary
- `../../contracts/temporal-splat-interpreter-cable-v1.schema.json` — CGG-side binding input contract

## Evals

- `evals/smoke-tests.json` — runnable contract checks (scripts + compiler + Rust adapter)
- `evals/evals.json` — agent-facing behavioral cases (re-litigation refusal, covenant_absent honesty, authority-widening refusal, …)
- `evals/trigger-evals.json` — should-trigger / should-not-trigger routing set
