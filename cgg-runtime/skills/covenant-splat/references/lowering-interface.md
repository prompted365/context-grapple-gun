# lowering-interface — Python parity oracle, temporal lowerer, existing Harpoon

The lowering boundary now has three distinct implementations with three distinct jobs. Do not collapse them.

```text
scripts/lower-covenant-expr.py
    deterministic Python parity oracle + migration fixture

prompted365/homeskillet-csl / splat-harpoon-compat
    operative temporal-lane ExecutionExpr → receipted FragmentDAG lowerer

prompted365/homeskillet-csl / harpoon_bridge
    existing physical fulfillment, ready-driven execution,
    reverse-topological rollback drill, seven-faced StrikeReceipt
```

The temporal runtime also carries:

```text
splat-protocol
    SplatInterpretationRequestV1
    SplatProposalEnvelopeV1
    HarpoonExecutionEnvelopeV1
    SplatProjectionFrameV1
    SplatObservationRecordV1

splat-harpoon-adapter
    exact HarpoonExecutionEnvelopeV1 → existing harpoon_bridge::FragmentDag
    verifies ids, choice ancestry, dependencies, waves, and hashes before execution
```

The crates are the infrastructure. The Python lowerer remains valuable because it is an independent oracle. It is no longer the operative runtime.

## Lowering semantics (deterministic — pinned on all three boundaries)

- **Fragment ids are occurrence-namespaced**: `{id}#{occ}::obj-{i}` per objective, `{id}#{occ}::covenant` for an objective-less leaf; `occ` is the pre-order leaf counter. The same covenant may appear repeatedly without collision.
- **Sequential ⊳** creates every left-sink × every right-source dependency edge.
- **Parallel ∥** creates no cross-edges.
- **Choice ⊕** allocates group `g{n}` outer-first; every fragment carries its full `ChoiceTag{group, branch∈L|R}` ancestry. N-ary choice folds left: `A⊕B⊕C = Choice(Choice(A,B),C)`, so outer=`g0`, inner=`g1`.
- Choice resolution keeps a fragment only when it lies on the selected branch of every resolved group in its ancestry. Unresolved groups remain. An edge survives only when both endpoints survive.
- Waves derive through deterministic Kahn dependency grouping, sorted within each wave.
- A cycle, empty operator, unknown operator, duplicate fragment identity, dangling edge, wave mismatch, or hash mismatch is a refusal. It never becomes an empty-green plan.
- `scripts/propose-fragment-dag.py` is a deprecated forwarding alias. It lowers; it never proposes.

## Cross-boundary parity gate

For one expression and one choice-pick set, all of the following must agree:

```text
Python oracle output
Rust splat-harpoon-compat output
HarpoonExecutionEnvelopeV1
existing harpoon_bridge materialization
```

Agreement means exact equality of:

```text
occurrence identities
objective identities
choice-group allocation
full choice ancestry
resolved fragment set
dependency edge set
deterministic waves
fragment-set hash
edge-set hash
wave hash
```

The execution envelope is not permission to strike. It is the exact receipted topology crossing. The physical runner and rollback runner are supplied downstream.

## The thin-covenant caveat

The existing `CovenantBuilder` is structurally permissive: empty repositories, objectives, criteria, and constraints can type-check. A backlog id wrapped in that type is still not an admitted covenant. A thin covenant must never classify `exec_ready`.

The temporal boundary therefore requires the admitted covenant and current projection before lowering. Six-facet cross-binding, source tense, authority, standing, dispositions, center exclusion, conformation, admission receipt, and rollback remain upstream protocol facts; the execution DAG does not manufacture them.

## The default-parallel trap

A single existing Harpoon Covenant lowers its objectives as independent fragments unless an explicit expression supplies ordering. `build ⊳ test ⊳ deploy` must be constructed by the splat-conditioned interpretation step. Harpoon executes topology; it does not infer topology from prose.

## Rust boundary requirement

Covenant-backed fragments only:

```text
admitted covenant
+ current conformation
+ complete projection
+ source and receipt binding
+ explicit authority
+ center exclusion
+ exact ExecutionExpr
```

Never naked backlog rows. Never a model plan treated as admission. Never a stale slice promoted by recent rendering.

## Fulfillment

The existing Harpoon lane remains:

```text
materialize exact FragmentDag
→ execute ready-driven plan
→ early-terminate poisoned descendants
→ drill rollback reverse-topologically
→ compute absorption
→ emit seven-faced StrikeReceipt
```

`harpoon_bridge::prebuilt_fulfill` accepts an already-receipted exact DAG so the temporal adapter does not re-infer topology. Declared rollback is not drilled rollback. The receipt verifies this execution; it never re-approves the covenant. `canonical_federation` alone absorbs and terminalizes.
