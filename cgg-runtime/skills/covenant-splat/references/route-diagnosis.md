# route-diagnosis — the §14 resolver card (operational condensation; the spec rules)

Doctrine body: `autonomous_kernel/covenant-splat-fqoq-runtime-spec.md` §14. One diagnosis per route, resolved IN ORDER:

1. Does an **admitted covenant** exist for this identity? → no: `covenant_absent`
   - `covenant_absent` carries a `sub_shape` (§14 sub-shape discipline, /review 634): `prose_pointer_absent` (no admission-capable receipt resolves at all — unheld path routes toward /review admission or per-member routing) | `wrong_object_class` (a real /review PROMOTE admitted a §5 object-1 while the route claims an object-2 build covenant — unheld path routes toward retire/reclassify BEFORE admission). Opposite unheld paths; a receipt may carry both when both hold.
2. Is its **Reality→Target** statement intact? → underdefined (target/constraints): `covenant_incomplete`
3. Conformation **rehydrated** against NAVIGATION / io-map / router / repo+runtime / receipts+scars? → stale: `covenant_conformation_stale`; conflicting surfaces: `covenant_contradicted`
4. Did the splat **preserve** exclusions, held-open hypotheses, authority, constraints, purpose, currentness?
5. **Decomposed** into anchors/cables/fragments/edges/choices/consumers/rollback? → no: `decomposition_missing`; partially: `decomposition_partial`. Faces existed but vanished in the legacy→live repair: `covenant_projection_lost` (restore the projection).
6. Decomposition **projected** into the live board?
7. **Runtime capable**? → no adapter: `execution_adapter_missing`; no runtime mapping: `runtime_mapping_missing`
8. All pass → `exec_ready`.

`evidence_insufficient`: RESERVED for a genuinely unsupported factual assertion **after applicable surfaces were actually searched** (record which). Absence-from-one-lens ≠ absence-in-reality. Token binding (spec §14): diagnosis token = `evidence_insufficient`; axis value = `genuinely_insufficient`; `true_evidence_gap` = carrier alias, mint no new uses.

## Five-status axes (every board node carries them — `covenant_projection` block)

- `covenant_status`: absent | incomplete | admitted | fulfilled | superseded | invalidated
- `projection_status`: complete | partial | lost | conflicting
- `conformation_status`: current | stale | contradicted | unknown
- `execution_status`: ready | blocked_by_dependency | blocked_by_runtime | blocked_by_physics | parked
- `evidence_status`: not_required_for_approved_mechanic | inherited_from_admission | supported_by_scars | requires_current_probe | genuinely_insufficient

**Axis fail-closed law (spec §14 — nulls apply to ALL five axes):** the compiler emits **null** for every axis it cannot adjudicate. `covenant_status`/`evidence_status` need drain receipts. `conformation_status` defaults **`unknown`** pre-drain — slice-generation freshness is an ENVELOPE fact, never per-route currency (*a stale thing can be freshly rendered*; the upgrade path is contagion conformation-proximity + the current-pointer staleness canary); `contradicted` is derivable now. `execution_status` asserts observed facts only (`blocked_by_dependency`/`blocked_by_physics`/`parked`); **`ready` needs the runtime-capable conjunct actually probed** — board-lens exec_ready does not discharge it. A null is never converted into an invented claim. **Readiness** = admitted covenant AND complete projection AND current conformation AND deps satisfied AND runtime available AND no explicit active gate — never "six prose strings exist."

## Judgment boundary at the drain

Fresh governance judgment ONLY where completing the definition would change **target / constraints / authority / scope**. Filling omitted execution mechanics inside an approved target is implementation work under the standing grant. Never re-litigate an admitted covenant.

## Drain-receipt evidence discipline (pin authoring + citation class — /review 734, paired rays; ledger: `constitution-ledger/ledger.md#drain-receipt-pin-scope-and-citation-class`)

**Pin scope.** `verified_input_hashes` pins UPSTREAM EVIDENCE at the narrowest stable scope. Three forbidden shapes (all lived t731): **whole-registry pins** on a shared mutable registry (route-metadata.json, backlog.jsonl) — the seat's own owed motions mutate those registries in the same close that consumes the receipts, so every seat motion is a self-inflicted staleness event; pin the route's OWN row/subtree hash instead. **Downstream-output pins** (board-state.json and other compiler root artifacts) — the compiler rewrites them each run; a receipt feeding the compile that pins the compile's output is a verification loop, not a verification. **Self-pins** (the receipt's own hash) — stale the instant any lawful correction lands; logically incapable of currency. A permanently-stale pin trains readers to ignore the staleness canary — the exact alarm the §14 discipline keeps loud.

**Citation class.** Before citing evidence, classify the surface: **append-accreting** (ledger anchors, dated jsonl lanes, commit history) — a pointer suffices; lineage is recoverable and `git log -S` proves HOW it changed. **Materialized / rewritten-in-place** (a backlog row's note, a registry entry, a mirror file) — QUOTE the load-bearing content INTO the receipt (the receipt becomes the append-accreting copy); even a current, correctly row-scoped pin on such a surface proves only THAT it changed, never what the change was (t634→t731: a quoted row body took a 481-commit walk to recover). Pin scope and forensic power are different axes — a narrow pin does not buy lineage. **Object-binding (third ray, /review 735).** Evidence for a gate/flag names the OBJECT — file path, tic, value — never the PATTERN: a route can host multiple instances of one pattern (wisdom-first carries TWO build-and-gate ratified bits born 117 tics apart, one TRUE and t591-live, one FALSE and t706-dormant), and pattern-cited evidence eventually reports one object's value under another's identity — surviving 111 tics there because the classification outcome was coincidentally identical.

**Shared-artifact ownership (M733-5 ruling, /review 734).** A bench/instrument artifact shared across routes has ONE owning route (the route it lives on — e.g. the union-veto bench is owned by `bk-16d-union-veto-quorum-scaling`); sibling routes hand up STAGED patches (staging/ artifacts, the INCREMENT-0 precedent) and never write the shared artifact directly; the canonical seat serializes application order.

**Scoped-admission face application (paired-gate atomic halves — /review 735; ledger: `constitution-ledger/ledger.md#scoped-admission-faces-and-paired-gate-are-atomic-halves`).** Every face application under a SCOPED admission (built-increment-only, measured-increment-only) ships with its paired gate entry — `blocked_by_admission` / `blocked_by_authority` — in the SAME seat motion, or with an explicit recorded basis for why no gate is owed. The readiness ladder reads FACES and GATE ENTRIES; it never reads admission text. So faces-alone under a scoped admission flips `exec_ready=True` while the route's entire remaining substance is exactly what the admission EXCLUDED (measured t732: three-scenario probe on the compiler's own `classify` — unmaterialized/False, faces-alone/True FALSE-GREEN, faces+paired-gate/blocked_by_authority honest; exec-ready 9 → 7 once the two latent siblings were fenced). Gate first or same write; if the gate is declined, decline the faces. Discriminator: this binds only where remaining substance sits OUTSIDE the admitted scope — a route whose admission covers genuinely open executable scope flips lawfully.
