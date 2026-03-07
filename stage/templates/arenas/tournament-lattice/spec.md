# Tournament Lattice Arena (5-7 Agents)

**Pattern:** Bracketed local contests -> cross-bracket challenge -> final synthesis
**Geometry:** Layered contest graph (not full pairwise)
**Strength:** Scales governed triangulation without edge explosion

## When to use

- 5 to 7 competing positions
- Multiple architectural candidates
- Many competing hypotheses
- Several subsystems that interact
- Positions that cluster into natural groups

## When NOT to use

- 3 or fewer positions (use governed-triangulation)
- Simple implementation tasks
- Linear decisions with no competing alternatives

## Why not full pairwise at scale

At 3 agents, full pairwise is elegant.
At 5-7 agents, full pairwise produces:
- too many edges
- too much repetition
- too much drift
- too much token burn

## Shape

Instead of a complete graph, run a tournament:
1. Partition positions into brackets of 2-3
2. Run local governed triangulation within each bracket
3. Advance strongest surviving structures
4. Cross-bracket challenge
5. Optional wildcard audit
6. Final synthesis

## Bracket Configurations

| Agents | Bracket 1 | Bracket 2 | Wildcard |
|--------|-----------|-----------|----------|
| 5      | A, B, C   | D, E      | -        |
| 6      | A, B, C   | D, E, F   | -        |
| 7      | A, B, C   | D, E, F   | G        |

## Grouping Rule

Group brackets by **semantic adjacency**, not randomly.

If A/B/C are retrieval-side positions, put them together.
If D/E/F are governance-side positions, put them together.
Then cross-bracket compares retrieval synthesis vs governance synthesis.

## The Wildcard

The 7th agent is NOT another advocate. It is an adversarial auditor.

Its job:
- study both bracket outputs
- attack hidden assumptions
- expose false convergence
- identify untested dependencies

The wildcard is often more valuable than a seventh partisan.

## Scoring Extension

Local bracket scoring uses the standard rubric (+1 through +5, penalties).
Cross-bracket adds:
- +6 exposes hidden dependency
- +7 survives wildcard attack

This makes the final stage harder to fake.

## Invariant

> local pressure -> local survival -> cross-bracket pressure -> final survival -> memory
