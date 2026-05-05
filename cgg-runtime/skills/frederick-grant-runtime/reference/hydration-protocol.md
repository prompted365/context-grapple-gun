# Hydration Protocol

Frederick does not write from memory. Frederick writes from the federation's archive, which the orchestrator must hydrate before Frederick composes. This file binds Stage 02 (Context Hydration) to the federation's `/tactical-hydration` skill (RTCH) and declares the full-file-read shortcuts that bypass bounded-chunk discipline when the target is small enough to read whole.

## Why this is in the chain

Stage 02 of Frederick's workflow used to read "hydrate enough substrate to write honestly, not exhaustively." That sentence is true and underspecified. *Enough* is not a mechanism. The orchestrator that invokes Frederick must have a deterministic protocol for selecting and loading source material; otherwise Frederick composes from whatever the orchestrator happens to remember, which violates Frederick's own runtime-authority-model: *no claim in his prose may outrun the supplied materials.*

The mechanism is `/tactical-hydration`. RTCH is the federation-rung discipline for staged source discovery and bounded-chunk hydration with source-re-entry. It produces an evidence packet with `selected_surfaces`, `unresolved_questions`, `caution_map`, and `next_legal_probes`. Frederick consumes that packet at Stage 02 and proceeds.

## Standing intake template

Every Frederick invocation that requires source loading must pass an intake to `/tactical-hydration` of approximately this shape:

```yaml
goal: <one sentence — what Frederick is being asked to compose>
target_profile: doctrine_chain | audit_history | mixed
  # Frederick almost always uses "audit_history" or "mixed".
  # "audit_history" if reading state-of-the-federation entries, receipts, conformations.
  # "doctrine_chain" if reading CLAUDE.md surfaces and federation invariants.
  # "mixed" if both.
fanout_level: normal
  # Frederick rarely needs "wide" — he is reading a known archive, not discovering
  # an unknown one. Use "wide" only when the task is "find what the archive contains
  # about X without prior anchor."
mutation_risk: read_only
  # Frederick is read-only on the archive. Always read_only at the hydration step.
expected_output: hydration_packet
  # Frederick consumes the RTCH packet, then composes. He does not call /consolidate.
enough_evidence_definition: <one sentence — when does hydration halt?>
  # E.g., "all referenced state-of-the-federation entries from tic A through tic B
  # have been read end-to-end, and at least one receipt per major doctrinal claim
  # has been hydrated."
explicit_seeds:
  - <path 1>
  - <path 2>
  - ...
known_neighbor_surfaces:
  - publications/   # always — Frederick's primary surface
  - audit-logs/governance/   # always — receipts and design-lane material
  - audit-logs/conformations/   # often — tic boundary snapshots
  - audit-logs/agent-mailboxes/ent_breyden/inbound/  # for persona substrate
  - audit-logs/agent-mailboxes/ent_homeskillet/canonical/  # for prior persona context
forbidden_assumptions:
  - never claim something without hydrating its source
  - never quote from memory
  - never invent a tic, signal_id, or commit hash
```

## Full-file-read shortcuts

The federation has surfaces small enough to be read **end-to-end** rather than as bounded RTCH chunks. When Frederick's task touches one of these classes, the orchestrator should read the file in full at Stage 02 and treat the contents as fully hydrated, not as a probe-sample.

The shortcut is permitted because (a) the file is below the Read tool's default 2000-line ceiling, (b) the file is canonical (federation-authored, not vendor-volatile), and (c) Frederick's composition discipline gains more from full context on these files than from RTCH's per-chunk audit metadata.

### Always-full-read when in scope

| Source class | Path glob | Full-read trigger |
|---|---|---|
| State of the Federation | `publications/state-of-the-federation-tic-*.md` | Always when composition references the period |
| Ubiquity Chronicles | `publications/the-ubiquity-chronicles-*.md` | Always when composition continues the chronicle line |
| Ubiquity Interviews | `publications/the-ubiquity-interviews-fg.md` | Always when composing in interview register |
| What is Ubiquity primer | `publications/what-is-ubiquity.md` | Always when composition needs Ubiquity overview |
| Parallel Lane Cadence essays | `publications/parallel-lane-cadence-*-frederick-grant.md` | Always when composing a successor cadence essay |
| Receipt evidence | `audit-logs/governance/p[0-9]-*-receipt-tic*.md` | Always when composition references the patch |
| Architect-locked spec | `audit-logs/governance/p[0-9]-*-handoff-tic*.md` | Always when composition references the patch's authoring |
| Tic conformation snapshot | `audit-logs/conformations/tic-*.json` | Always when composition references that tic boundary |
| Persona substrate | `audit-logs/agent-mailboxes/ent_breyden/inbound/ubiquity-chronicles-tic175/frederick-grant-persona-substrate.md` | Always at first composition of a session |
| Deeper persona history | `audit-logs/agent-mailboxes/ent_homeskillet/canonical/deeperHistory&theEnigmaFrederickGrant.md` | When the task touches Frederick's identity continuity |

### Bounded-chunk per RTCH

| Source class | Why bounded |
|---|---|
| `audit-logs/signals/*.jsonl` | Append-only, can be very large |
| `audit-logs/cprs/queue.jsonl` | Append-only, regularly large |
| `audit-logs/tics/*.jsonl` | Tic event ledger, can grow large |
| Long doctrine surfaces (`canonical/CLAUDE.md`, `canonical_developer/context-grapple-gun/CLAUDE.md`) | Multi-thousand-line surfaces, RTCH-chunked |
| Anything > 2000 lines | RTCH-chunked by default |

## Stage 02 protocol

The orchestrator, at Stage 02, executes:

1. **Build the intake.** Apply the standing intake template. Choose `target_profile` from the task's nature. Name the explicit seeds (the paths the orchestrator already knows are required).
2. **Invoke `/tactical-hydration`** with that intake.
3. **Receive the evidence packet.** The packet carries `selected_surfaces`, `unresolved_questions`, `caution_map`, `next_legal_probes`, and `generic_alone_warnings`.
4. **Apply the full-file-read shortcuts.** For every selected_surface that matches a class in *Always-full-read when in scope* above, read the file in full with the Read tool. For every selected_surface that does not match, perform RTCH's bounded-chunk hydration with explicit line ranges.
5. **Carry forward**: `selected_surfaces` (now hydrated), `unresolved_questions` (pass to Frederick's Receipt Closeout), `caution_map` (constrain Frederick's claims).
6. **Block composition until hydration is sufficient** under the `enough_evidence_definition` from the intake. If RTCH halts with `halting_reason: budget_exhausted` or `no_signal_at_normal_fanout`, the orchestrator re-invokes RTCH with widened fanout or revised seeds. Never let Frederick compose under unsatisfied hydration.

## Failure modes

- **Composing from memory.** If the orchestrator skips Stage 02 and lets Frederick compose without RTCH, Frederick will produce admiring prose unsupported by source. The discipline fails silently. The artifact looks fluent but is structurally hollow.
- **Truncated reads.** If the orchestrator reads a long file with the Read tool's default 2000-line cap and treats it as fully hydrated, the missing lines become silent omissions. The full-read shortcut table above lists files known to be < 2000 lines; use Read with `offset`/`limit` for anything outside the table.
- **Forgetting cautions.** RTCH's `caution_map` is binding for Frederick's claim formation. If the caution says "this signal is acknowledged but not resolved," Frederick must not write "the federation closed it." Cautions translate directly to Frederick's open-branch enumeration.

## Cross-references

- `/tactical-hydration` skill body: `cgg-runtime/skills/tactical-hydration/SKILL.md`
- RTCH binder: `audit-logs/governance/runtime-tactical-context-hydration-binder.md`
- Federation KI: *Authoritative-set readers must read the manifest, not aggregate raw emissions* (read-side hydration discipline)
- Federation KI: *Bounded delegation surfaces default to masking bugs rather than surfacing them* — full-read shortcuts mitigate this for canonical federation files small enough to read whole
