# Evidence Rebuttal Arena — Template Spec

## Purpose

A **continuation arena** that reopens settled or probationary verdicts from a parent arena when new material evidence surfaces after the parent run completes. This is not a re-run — it is a scoped reexamination of specific claims against specific evidence.

## When to Use

Use when ALL of the following hold:
1. A parent arena produced a governance memo with settled/probationary/rejected verdicts
2. New evidence has surfaced AFTER the parent run completed
3. The new evidence bears directly on one or more parent verdicts
4. The evidence was not available to the parent arena's advocates

Do NOT use when:
- The parent arena's verdicts are simply unpopular (that's appeal, not rebuttal)
- The "new evidence" is reinterpretation of existing evidence (that's revisionism)
- The question has fundamentally changed (start a new arena instead)

## Geometry

Governed triangulation (3 advocates) extended with wildcard audit phase.

### Roles

| Role | Mandate |
|------|---------|
| **EVIDENCE-ADVOCATE** | Argue that the new evidence materially changes parent verdicts |
| **ARCHITECTURE-DEFENDER** | Argue that the new evidence is orthogonal to the architectural/structural concerns the parent adjudicated |
| **GOVERNANCE-ARBITER** | Apply governance standards to adjudicate what constitutes valid authority evidence |
| **WILDCARD** | Detect validation bias, coverage theater, false authority from evidence presence |
| **LEAD** | Orchestrator/synthesizer. Does not advocate. |

### Phase Structure (12 tasks, 6 phases)

```
context [1-3, parallel] → defense [4-6, parallel] → rebuttal [7-9, parallel]
  → wildcard audit [10] → synthesis [11] → pressure extraction [12]
```

Same dependency gating as governed-triangulation, extended with wildcard phase.

## Required Spec Fields (beyond standard show spec)

```yaml
continuation_of: <parent arena id>

parent_arena:
  id: <parent arena id>
  governance_memo: <path to parent governance memo>
  pressure_report: <path to parent pressure report>
  verdict: <parent verdict>

new_evidence:
  <evidence_name>:
    location: <path or null>
    result: <summary>
    bears_on: <which parent claims this evidence affects>

claims_under_reexamination:
  from_probationary:
    - parent_claim: <claim text>
      new_evidence_relevance: <why this evidence changes things>
  from_rejected:
    - parent_claim: <claim text>
      rejection_reason: <original reason>
      new_evidence_relevance: <why this evidence rehabilitates the claim>
```

## Decision Artifact Schema

The lead produces a **verdict update**, not a full governance memo:

```yaml
verdicts_changed:
  - claim: "<parent claim>"
    old_verdict: "probationary|rejected"
    new_verdict: "settled|probationary|rejected"
    evidence: "<what changed>"
    wildcard_disposition: "<if applicable>"

verdicts_unchanged:
  - claim: "<parent claim>"
    verdict: "unchanged"
    reason: "<why evidence is orthogonal>"

new_constraints:
  - constraint: "<any new constraint surfaced by the evidence>"

updated_authority_map:
  surfaces_affected:
    - surface: "<name>"
      old_owner: "<from parent>"
      new_owner: "<if changed>"
      evidence: "<why>"
```

## Wildcard Targets (Evidence-Specific)

The wildcard must check for:
- **VALIDATION BIAS**: "tested = correct" is a category error
- **COVERAGE THEATER**: assertion count is not authority
- **FALSE AUTHORITY FROM EVIDENCE PRESENCE**: evidence proves internal consistency, not integration fitness
- **SURVIVORSHIP BIAS**: production usage without tests may be a different validation model
- **ASYMMETRIC COMPARISON**: comparing library unit tests to application lack of them may be category error
- **WEIGHT INFLATION**: does evidence asymmetry really change architectural verdicts?

## Scoring

Same rubric as governed-triangulation, plus:
- +6: Parent verdict change with evidence (specific claim upgraded/downgraded with cited evidence)
- -4: Parent verdict change without evidence (changing a verdict by argument alone in a rebuttal arena)

## Precedent

First instantiation: `triad-fusion-evidence-rebuttal` (tic 102), continuation of `triad-fusion-authority-arena`.
Evidence: telos-studio 8/8 test suites (148+ assertions) vs ArtCraft 0 test files.
