---
name: covenant-splat
description: |
  Splat-conditioned covenant interpretation for the live board — convert an admitted
  current→target covenant (or board route) into executable anchors, cables, dependency
  edges, winch strategies and verification lanes, through the kernel contract
  (autonomous_kernel/covenant-splat-fqoq-runtime-spec.md). Progressive-disclosure
  operational surface: this skill POINTS at the kernel spec; it never owns the doctrine.

  CENTROID:
  admitted covenant → lawful current conformation slice → bounded morphism proposal → FragmentDAG contract

  IS:
  - CovenantSlice scaffold hydration from the compiler-visible current field (scripts/hydrate-covenant-slice.py)
  - deterministic CovenantExpr → FragmentDAG lowering + wave derivation (scripts/propose-fragment-dag.py)
  - board-projection validation against the kernel contract's acceptance assertions (scripts/validate-covenant-projection.py)
  - the per-route drain procedure card (references/route-diagnosis.md — the §14 resolver, one diagnosis per route)
  - bounded agentic six-facet interpretation UNDER the morphism-proposer prohibitions (§9)

  IS NOT:
    collapse_zones:
      - covenant authority source (the kernel spec + admission receipts rule; this skill derives and proposes)
      - evidence-enrichment system (missing faces = unmaterialized decomposition, NOT evidence deficit)
      - route-metadata authoring lane (route-metadata.json is derived cache/override — never semantic authority)
      - re-adjudication surface (an admitted covenant is never re-litigated by tic/session/model/regeneration)
      - doctrine body (the kernel spec is the doctrine; edits route through /review)
      - terminalizer (canonical owns durable board truth; a proposal never lands itself)
    sibling_overlaps:
      - harpoon-sequencer.py (compiles the conformation slice; this skill materializes covenant projections INTO it)
      - /tactical-hydration (generic discovery; this skill is covenant-specific hydration)
      - /review (admission on the covenant OBJECT; this skill operates downstream of admission)

  WHEN:
  - draining a covenant_decomposition_unmaterialized route (the 35-cohort) through the §14 resolver
  - decomposing an admitted covenant into CovenantExpr/FragmentDAG for the Rust boundary
  - validating that the live board's covenant projections honor the kernel contract
  - constructing ordering (build ⊳ test ⊳ deploy) upstream of the crates (they execute topology, they do not infer it)

  NOT WHEN:
  - no admitted covenant exists and none is being located (that is covenant_absent — route to the drain's fresh-judgment path, or /review if target/authority/scope would change)
  - the task is generic file discovery (use /tactical-hydration)
  - the covenant object itself needs admission (route to /review — coherence is not admission)

  RELATES TO:
  - autonomous_kernel/covenant-splat-fqoq-runtime-spec.md (the doctrine body this skill discloses)
  - audit-logs/governance/board-live-compiler-directive-tic621.md ADDENDUM 4 (label retirement lineage)
  - canonical_developer/homeskillet-csl/ (harpoon_bridge · covenant_composition · fragment_dag · fulfill — the crates ARE the infra)
  - canonical_developer/canonical-mount/ (the bounded-intelligence invocation rail)

  ARGS:
    stance: dispatch
    off_envelope: ask
    core_dispatch_rays:
      - ""            → interactive (name the route/covenant, pick the lane)
      - "drain <id>"  → per-route §14 resolver walk (hydrate → locate covenant → diagnose exactly one)
      - "hydrate <id>"→ CovenantSlice scaffold for a backlog identity
      - "lower <file>"→ CovenantExpr JSON → FragmentDAG + waves
      - "validate"    → board-projection contract check (exit 0/1)
---

# covenant-splat — splat-conditioned covenant interpretation

**Read the kernel contract FIRST** (once per session): `autonomous_kernel/covenant-splat-fqoq-runtime-spec.md` — activation instructions in `references/kernel-contract.md`. This skill is the operational progressive-disclosure surface; the spec is the doctrine body. Do not restate the spec from memory — follow the pointer.

## Procedure (the drain's first motion, per route)

1. **Hydrate** the current field: `python3 scripts/hydrate-covenant-slice.py <backlog-id>` → a CovenantSlice **scaffold** (compiler-visible reality + typed-null facets). The scaffold is not a covenant.
2. **Locate the admitted covenant** (admission receipt, /review verdict, directive, ratified spec). If it exists — **do NOT re-litigate it.** If underdefined for decomposition, return `COVENANT_INSUFFICIENT` naming the missing faces. No covenant → `covenant_absent`.
3. **Run the six-facet splat** (KAT·APO·PAR·PLE·ENA·TEL, cross-bound one record) against NAVIGATION / io-map / router / repo+runtime state / receipts + OT scars. Record `narrowed_to · why_not_further · excluded · de_considered · suspended · live_under_conditions · renarrow_triggers`.
4. **Propose morphisms** (anchors, write surfaces, fragment boundaries, ⊳/∥/⊕ relations, consumers, success predicates, rollback) — as a **bounded morphism-proposer** (prohibitions in the spec §9: never alter the target, widen authority, crown the centroid, route into the held-open center, remove a live hypothesis, invent metadata, treat a plan/title as a covenant, terminalize).
5. **Lower deterministically**: `python3 scripts/propose-fragment-dag.py <covenant-expr.json>` — sequential creates dependency edges, parallel none, choice stays branch metadata.
6. **Diagnose exactly one** §14 state (`references/route-diagnosis.md`) and persist the derived route contract WITH source pointers + hashes (route-metadata.json = derived cache, never authoring surface).
7. **Validate the projection**: `python3 scripts/validate-covenant-projection.py` (exit 0/1 against the live board-state.json).

## Gotchas (the category errors this skill exists to prevent)

- A backlog row is not a covenant.
- A Claude Code plan is not a covenant.
- Route metadata is not the covenant source.
- An admitted covenant does not re-earn authority every tic.
- A changed reality invalidates a decomposition before it invalidates a target.
- Missing anchors/cables = decomposition or covenant-definition failure, not automatically evidence failure.
- canonical-mount/model output is a proposed morphism, never authority.
- The held-open center is never a target, fragment, or model output.

## References (load on demand — progressive disclosure)

- `references/kernel-contract.md` — how to read the kernel spec (the ONLY doctrine body)
- `references/route-diagnosis.md` — the §14 resolver order + diagnoses + five-status axes
- `references/maps-and-ownership.md` — NAVIGATION/io-map/router roles vs the board's sequencing role
- `references/lowering-interface.md` — the homeskillet-csl lowering contract + thin-covenant caveat
