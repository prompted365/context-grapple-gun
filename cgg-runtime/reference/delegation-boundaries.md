# Delegation Boundaries Reference

## Valid subordinate roles

- ripple assessor
- scope resolver
- ladder auditor
- prompt-stack auditor
- signal neighborhood auditor
- repo-map assessor
- manifestation evidence gatherer
- deliverable workstream coordinators

## Delegation mode

- Choose the orchestration form that fits the governance surface structure (see mandate-protocol.md orchestration ladder)
- Use blocking execution for gate-critical, sequence-dependent work
- Use nonblocking execution for maintenance follow-through, background enrichment, scanning
- Load skills headlessly for sniper-clean tasks — often the most efficient path
- Resume bounded subagents when continuity across sessions matters
- Use agent teams only when the task structurally benefits from independent worker coordination
- Delegated outputs are evidence, not verdicts
- Mogul remains the synthesizing authority for the run

## Findings-broadcast cross-check

When running parallel subordinate agents (ripple assessor, pattern curator, ladder auditor), add a synthesis step after all return:

1. Collect all subordinate findings
2. For each pair of subordinates that ran in parallel, check for:
   - Contradictions (one finding negates another)
   - Reinforcements (independent evidence for the same pattern)
   - Blind spots (surface one agent examined that another's findings depend on but didn't read)
3. Produce a brief contradictions report if any found
4. Use contradictions as signal candidates — genuine disagreement between independent evidence-gatherers is high-value governance signal

## Ripple Assessor boundary

- Delegate only bounded assessment work
- Preserve Mogul responsibility for synthesis
- Do not collapse Mogul into Ripple Assessor
- If a task implicates runtime drift, prompt-stack interference, actor-boundary conflict, multi-rung ladder coherence, or estate-wide ops routing, keep it at Mogul level

## Pattern Curator boundary

- Delegate bounded mining tasks: scan specific authoring surfaces for pattern evidence
- Pattern Curator returns findings packets (candidate seeds, hazard findings, ops routing recommendations)
- Mogul synthesizes findings into governance actions
- If Pattern Curator returns findings that imply deliverable-team routing, estate-wide orchestration, or ladder coherence audit, handle them at Mogul level
- Pattern Curator is read-only — it never writes to governance surfaces

## Ladder Auditor boundary

- Delegate bounded coherence audit tasks: scan CLAUDE.md chain for structural issues
- Ladder Auditor returns audit packets with per-rule classifications (coherent, strained, overbroad, under_abstracted, demotion_pressure)
- Mogul synthesizes audit findings into review staging material or ops routing decisions
- If Ladder Auditor returns findings that imply estate-wide restructuring or constitutional amendments, handle them at Mogul level
- Ladder Auditor is read-only — it never modifies governance surfaces
