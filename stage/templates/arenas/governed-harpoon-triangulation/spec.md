# Governed Harpoon Triangulation — Full Specification

**Pattern:** 3 partisan advocates (HARVEST / MINE / CATALYZE) + 1 lead synthesizer
**Geometry:** Full pairwise triangle (every edge traversed)
**Strength:** 3x (opponent-context + defense + rebuttal)
**Tasks:** 11 (3 context, 3 defense, 3 rebuttal, 1 synthesis, 1 pressure extraction)
**Validated:** harpoon-alventra-seo-assessment (2026-03-27, tic 109)
**Parent template:** governed-triangulation (inherits all 10 rules, scoring, dependency gating)

## When to Use

- **Harpoon target assessment** — evaluating external repos, tools, prompt systems, or frameworks for ingestion or functionality mining
- Any decision where the question is "what do we do with this external asset?"
- When the decision space is: harvest whole / extract patterns / build what it reveals

## When NOT to Use

- Internal architecture decisions (use governed-triangulation)
- Comparing more than one target simultaneously (use tournament-lattice with bracket-per-target)
- Simple yes/no adoption decisions (the CATALYZE position is wasted if no constitutional patterns are plausible)

## What Makes This Different from Governed Triangulation

Standard governed-triangulation has generic positions A/B/C. This variant has **typed positions** with domain-specific scoring incentives:

| Position | Role | Incentive | Failure Mode |
|----------|------|-----------|-------------|
| **HARVEST** | Capability integration architect | Speed of deployment, operational value | Overestimates portability, underestimates tool coupling |
| **MINE** | Pattern extraction specialist | Reuse across verticals, geometry durability | Loses systemic/compound value by decomposing too early |
| **CATALYZE** | Constitutional opportunity detector | Cross-office leverage, federation primitives | NIH bias dressed as architecture; "build the primitive" = "never ship" |

### CATALYZE — The Key Innovation

CATALYZE replaces a simple "PASS/NO" advocate with productive opposition:

- Pro-progress (not anti-adoption)
- Argues the highest-leverage action is building constitutional primitives the target *reveals*, not ingesting the target itself
- **Must name specific offices, specific surfaces, specific outcomes** — vague "this could serve many verticals" claims are penalized
- Must honestly self-examine for NIH bias in the "where my position fails" section
- May propose phased convergence sequences that give all three positions partial wins

The result: arenas produce phased implementation paths instead of binary accept/reject verdicts.

## Scoring Extensions

Inherits all standard governed-triangulation scoring (factual_insight +1 through architectural_reframe +5, penalties -2 through -5).

**Additions for harpoon assessment:**

| Score | Category | Description |
|-------|----------|-------------|
| +6 | cross_office_discovery | Names 3+ specific federation/estate surfaces served, with evidence |
| -3 | vague_leverage_claim | Claims cross-office leverage without naming specific surfaces/outcomes |

See `scoring.yaml` for machine-readable format.

## Required Output Structure

Harpoon assessment synthesis MUST produce:

1. **Tier classification** — `tier_1_harvest` / `tier_2_adapt` / `tier_3_investigate` / `discard`
2. **Harpoon manifest** (if tier 1 or 2) — structured cut-list following federation harpoon pattern
3. **Constitutional patterns exposed** — patterns revealed regardless of tier, with surface enumeration
4. **Cross-office leverage map** — for each proposed action: federation surfaces, estate surfaces, leverage ratio
5. **Implementation phasing** — sequenced actions with dependencies, typically mapping to which advocate "wins" each phase

## Evidence Surface Requirements

Every harpoon arena spec must reference:
- The target's `source-material/` directory (what's being assessed)
- The target's `manifest.json` (envelope metadata)
- The target's `README.md` (mining hypothesis)
- Relevant federation doctrine (Volatility Handling Law, envelope patterns, etc.)

## Capture Policy

Default: operational mode (all lesson types route, confidence-gated via /review).

Harpoon assessment arenas are inherently operational — they produce real harvest decisions. Experimental mode is inappropriate for this geometry.

## Task Structure

Identical to governed-triangulation (11 tasks, 5 phases). See `tasks.yaml`.

## Reference Implementation

First validated run: **harpoon-alventra-seo-assessment** (2026-03-27, tic 109)
- 3 Opus advocates + Opus lead
- Target: 20-prompt local SEO system (Alventra Marketing)
- Result: tier_2_adapt with 5-phase convergent implementation path
- Key discovery: Client context envelope (convergent — all 3 advocates independently identified)
- CogPRs produced: 5 (CogPR-80 through CogPR-84, 2 convergent + 3 reinforced)
- CATALYZE reduced from 4 proposed gaps to 2 during the arena (honest self-correction)
- Full artifacts: `stage/shows/harpoon-assessment-alventra-seo/`
- Pressure report: `audit-logs/arenas/pressure-reports/2026-03-27_harpoon-alventra-seo-assessment.json`
