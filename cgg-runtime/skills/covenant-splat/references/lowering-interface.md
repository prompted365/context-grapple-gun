# lowering-interface — the homeskillet-csl CovenantExpr/FragmentDAG contract

Crates (canonical_developer/homeskillet-csl — vendored ≠ versioned, NEVER git-add near harpoonables): `harpoon_bridge` (CovenantBuilder, covenant algebra) · `covenant_composition` · `fragment_dag` · `fulfill`. **The crates ARE the infra — do not rebuild a parallel prose-overlay empire; drive them.**

## Lowering semantics (deterministic — mirrored exactly by `scripts/lower-covenant-expr.py`)

- **Fragment ids are occurrence-namespaced** (`covenant_composition.rs` ~:80): `{id}#{occ}::obj-{i}` per objective, `{id}#{occ}::covenant` for an objective-less leaf; `occ` = pre-order leaf counter — the SAME covenant may appear twice with no collision. **This id scheme is the acceptance-point-10 parity hazard**: any Rust↔Python executable-set hash equality must hash these identities.
- **Sequential ⊳** creates dependency edges: EVERY left-sink × EVERY right-source.
- **Parallel ∥** creates NO cross-edges.
- **Choice ⊕** allocates group `g{n}` OUTER-FIRST; every fragment carries its FULL choice ancestry as `ChoiceTag{group, branch∈L|R}` (`fragment_dag.rs:47`); n-ary choice is left-associative (`A⊕B⊕C = Choice(Choice(A,B),C)`: outer=g0, inner=g1). Resolution (`resolve_choices`): a fragment survives iff on the chosen branch of EVERY resolved group it carries; unresolved groups keep; an edge survives iff both endpoints survive.
- Waves derive by Kahn dependency-grouping, sorted within a wave; parallelism at dispatch is by DISJOINT WRITE SURFACE (items sharing a write surface serialize).
- `scripts/propose-fragment-dag.py` is a deprecated forwarding alias (it lowers, it never proposed — the morphism proposal is the interpreter's act).

## The thin-covenant caveat (root cause of the 35-cohort)

`CovenantBuilder` is structurally permissive: empty repositories/objectives/criteria/constraints are possible, so a backlog ID wrapped in the Covenant type type-checks while carrying no covenant meaning. **A thin covenant must never classify exec_ready** (kernel spec §17.1). The Rust `Covenant` type does not yet carry first-class: six-facet cross-binding, source-tense, authority/standing, de-considerations, held-open hypotheses, working centroid, center-exclusion declaration, conformation envelope, reopen/invalidation conditions, named eater, rollback covenant, admission receipt, covenant status.

## The default-parallel trap

A single Covenant lowers its objectives as INDEPENDENT (parallel) fragments unless an explicit CovenantExpr supplies ordering. `build ⊳ test ⊳ deploy` must be constructed UPSTREAM (by this skill's interpretation step) — the crates execute the topology; they do not infer it.

## Rust boundary requirement (the stomp_board_live generalization consumes)

Covenant-backed fragments ONLY — admitted covenant + complete current projection, **both classification axes preserved** (a readiness contradiction must never hide inside a container-effective headline; A3 is the scar), field-level provenance, fail-closed, raw derivation inputs exposed. Never naked backlog rows.

## Fulfillment (downstream, already built)

`fulfill_covenant`: decompose → resolve choices → execute → drill rollback reverse-topologically → compute absorption → seven-faced StrikeReceipt. **Declared rollback ≠ drilled rollback.** The receipt verifies execution; it never re-approves the covenant. canonical terminalizes; nothing else does.
