# Stage 02 — Context Hydration

## Role

Hydrate enough substrate to write honestly, **using the federation's runtime tactical context hydration mechanism**. Frederick does not write from memory. The orchestrator that invokes Frederick must produce a source-bearing evidence packet at this stage and pass the packet's `selected_surfaces` (with their hydrated chunks or full-file reads) to Stage 03 (Field Grounding) and Stage 05 (Composition).

## Entry condition

Stage 01 (Signal Intake) has named the signal and the hypothesis branches. The signal needs grounding before composition can proceed.

## Core question

Which context is load-bearing, and which context is costume?

## Mechanism — `/tactical-hydration` (RTCH)

This stage is bound to the federation's `/tactical-hydration` skill. The orchestrator invokes RTCH with an intake matching the standing template in `reference/hydration-protocol.md`, receives the evidence packet, applies the full-file-read shortcuts where they apply, and only then permits Stage 03 to begin.

### Steps

1. **Build intake.** Apply the standing intake template. Populate `goal`, `target_profile`, `fanout_level`, `mutation_risk` (always `read_only` for Frederick), `expected_output: hydration_packet`, `enough_evidence_definition`, `explicit_seeds`, `known_neighbor_surfaces`, and `forbidden_assumptions`.
2. **Invoke `/tactical-hydration`** with that intake.
3. **Receive packet.** The packet carries `selected_surfaces`, `unresolved_questions`, `caution_map`, `next_legal_probes`, `generic_alone_warnings`, `halting_reason`, and `fanout_level_used`.
4. **Apply full-file-read shortcuts** for each `selected_surface` matching a class in `reference/hydration-protocol.md` § "Always-full-read when in scope." For non-matching surfaces, perform RTCH's bounded-chunk hydration with explicit line ranges.
5. **Check halting reason.** If `halting_reason` is `enough_evidence_definition_satisfied`, proceed. If `budget_exhausted` or `no_signal_at_normal_fanout`, re-invoke RTCH with widened fanout or revised seeds. **Never** allow Stage 03 to begin under unsatisfied hydration.
6. **Carry forward to subsequent stages**:
   - `selected_surfaces` (now hydrated) → Stage 03 (Field Grounding) and Stage 05 (Composition)
   - `unresolved_questions` → Stage 07 (Receipt Closeout) — these become unresolved branches in Frederick's prose
   - `caution_map` → constrains all of Frederick's claims; binding for Stage 05 composition
   - `generic_alone_warnings` → Stage 06 (Elara Counterweight Pass) flags

## Artifacts consumed

- intake template fields
- federation archive (publications/, audit-logs/governance/, audit-logs/conformations/, ent_breyden/inbound/, ent_homeskillet/canonical/)
- profile files (loaded once per session, not per stage)

## Artifacts produced

- bounded-or-full source-bearing context packet
- hydrated `selected_surfaces` list (each entry with line range or full-file marker)
- Stage 07 carry-forward: unresolved_questions
- Stage 05 carry-forward: caution_map

## Closure test

Hydration is sufficient to proceed without pretending completion. Specifically:

- Every claim Frederick will make in the composition has a source-bearing surface in the packet.
- Every cautionary or contested element is in `caution_map` and will translate to an unresolved branch in the closeout.
- The `enough_evidence_definition` from the intake has been satisfied (the orchestrator confirms this explicitly before permitting Stage 03).

## Failure modes

- **Composing from memory.** If the orchestrator skips this stage, Frederick's prose will look fluent but be structurally unsupported. The artifact will read well and audit poorly.
- **Truncated reads disguised as full reads.** If a federation file is over 2000 lines and the orchestrator uses Read without `offset`/`limit`, the tail is silently dropped. Refer to `reference/hydration-protocol.md` for the full-read-eligible classes; everything outside that table requires bounded-chunk discipline.
- **Ignoring cautions.** RTCH's `caution_map` is binding. A caution that says "this signal is acknowledged but not resolved" forecloses Frederick's ability to claim closure. Cautions translate to open branches.
- **Insufficient seeds.** If the intake's `explicit_seeds` does not name the obvious sources (latest state-of-the-federation entry, relevant receipts, prior chronicle volume), RTCH will return a thinner packet than Frederick needs. The orchestrator must seed thoroughly.

## Cross-references

- `reference/hydration-protocol.md` — full intake template, full-read shortcut table, Stage 02 protocol
- `cgg-runtime/skills/tactical-hydration/SKILL.md` — RTCH skill body
- `audit-logs/governance/runtime-tactical-context-hydration-binder.md` — RTCH design binder
- Federation KI: *Authoritative-set readers must read the manifest, not aggregate raw emissions*
- Federation KI: *Bounded delegation surfaces default to masking bugs rather than surfacing them*
