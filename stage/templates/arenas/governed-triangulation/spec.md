# Governed Triangulation Arena (3-Agent)

**Pattern:** 3 partisan advocates + 1 lead synthesizer
**Geometry:** Full pairwise triangle (every edge traversed)
**Strength:** 3x (rebuttal + scoring + convergence extraction)

## When to use

- Architecture decisions
- Build ordering
- Root cause analysis
- Competing hypotheses (exactly 3)
- Policy debates

## When NOT to use

- Simple implementation (single-file, linear)
- More than 3 competing positions (use tournament-lattice)
- Tasks where the answer is already known

## Layers

| Layer | Function |
|-------|----------|
| 1. Triangulation | Surface geometry: each node studies the other two |
| 2. Dependency gating | Governance: no defense until context done, no synthesis until defenses done |
| 3. Adversarial incentives | Pressure: partisan advocates, not neutral analysts |
| 4. Lead synthesis | Signal extraction: convergent discoveries, surviving arguments |
| 5. Institutional memory | Capture: discoveries and process lessons persist |

## Invariant

> study opponents -> defend -> rebut -> synthesize

Never allow: defend -> study -> synthesize
