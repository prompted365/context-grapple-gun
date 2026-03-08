# Governance Maintenance Ownership Reference

## Embodiment awareness

Mogul may operate in different runtime embodiments:

| Embodiment | Environment | Available capabilities |
|------------|-------------|----------------------|
| `cgg_runtime` | Claude Code agent process | Host filesystem, git, codebase, governance surfaces, subagent delegation |
| `estate_runtime` | External supervised process | Container filesystem, memory systems, web intelligence, compliance tools |

Embodiment determines tool availability, not responsibility. Governance duties are the same regardless of embodiment. When a mandated cycle requires capabilities unavailable in the current embodiment, note the gap in output — do not silently skip the cycle.

## Maintenance lanes

| Lane | Cycle | Delegated to |
|------|-------|-------------|
| Queue + signal scan | 1-tic | Direct or Ripple Assessor |
| Memory mining | 3-tic | Pattern Curator (bounded), Mogul synthesizes |
| Pattern curation | 3-tic | Pattern Curator |
| Enrichment scanning | Continuous | Ripple Assessor |
| Ladder coherence audit | 5-tic | Ladder Auditor |
| Runtime drift audit | 5-tic | Direct |
| Prompt-stack audit | 5-tic | Direct |
| Deep audit (multi-rung) | 8-tic | Ladder Auditor + Manifestation Evidence Gatherer |
| Bench packet preparation | Pre-/review | Direct |
| Review-close consistency | Post-/review | Direct |

When another actor performs Mogul's maintenance work (e.g., the interactive orchestrator doing memory mining because activation fabric was absent), this is a **wrong-owner override** — valid work, wrong governor.
