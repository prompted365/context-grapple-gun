# Delegation Boundaries Reference

## Valid subordinate roles

- ripple assessor (runtime drift)
- scope resolver
- ladder auditor
- prompt-stack auditor
- signal neighborhood auditor
- repo-map assessor
- manifestation evidence gatherer
- deliverable workstream coordinators
- pattern curator (meta)
- pattern curator (direct)

## Single team topology (mandate cycle)

All mandate workers run in one team: `mandate-pattern-triangulation`. No nested teams. No standalone subagents while the team is active.

```
Team: mandate-pattern-triangulation
Lead: Mogul
Teammate 1: ladder-auditor
Teammate 2: ripple-assessor (runtime drift)
Teammate 3: pattern-curator-meta
Teammate 4: pattern-curator-direct
```

Platform guardrail: one team per session per lead.

## Task graph

T1-T4 run in parallel. T5-T8 depend on discovery completion. T9-T10 depend on elimination. T11-T12 are lead synthesis. See mogul.md Section B for full graph.

## Delegation mode

- Delegated outputs are evidence, not verdicts
- Mogul remains the synthesizing authority for the run
- Use the task graph dependency structure for sequencing
- For non-mandate work (deliverable teams, standalone assessments): use standard subagent dispatch

## Findings-broadcast cross-check

For adversarial pattern mining: cross-elimination verdicts (NOVEL/DUPLICATE/PARTIAL_OVERLAP) are the primary cross-check. Ladder and drift commentary on survivors is the secondary cross-check. Only candidates surviving both gates advance.

For ladder/drift findings: check for contradictions/reinforcements between findings and surviving pattern candidates during Mogul synthesis.

## Ripple Assessor boundary

- First-pass runtime drift audit (T2) + commentary on surviving candidates (T10)
- Preserve Mogul responsibility for synthesis
- Do not collapse Mogul into Ripple Assessor
- If a task implicates prompt-stack interference, actor-boundary conflict, multi-rung ladder coherence, or estate-wide ops routing, keep it at Mogul level

## Pattern Curator boundary

- Blind discovery → submission → elimination → await commentary
- Pattern curators are read-only — they never write to governance surfaces
- The blindness rule is a hard constraint: no own-category rationale before first-pass
- Mogul synthesizes findings; curators produce evidence only

## Ladder Auditor boundary

- First-pass coherence audit (T1) + commentary on surviving candidates (T9)
- Ladder Auditor is read-only — it never modifies governance surfaces
- If audit findings imply estate-wide restructuring or constitutional amendments, handle at Mogul level
