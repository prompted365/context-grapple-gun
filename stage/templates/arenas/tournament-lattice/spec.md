# Tournament Lattice Arena — Full Specification

**Pattern:** Bracketed local contests → cross-bracket challenge → final synthesis
**Geometry:** Layered contest graph (not full pairwise)
**Strength:** Scales governed triangulation without edge explosion
**Agents:** 5-7 advocates + 1 lead + optional wildcard auditor
**Tasks:** 21 (5-agent) / 26 (7-agent with wildcard) — includes pressure extraction

## When to Use

- 5 to 7 competing positions
- Multiple architectural candidates that cluster into natural groups
- Many competing hypotheses (too many for a single triangle)
- Several subsystems that interact across domain boundaries
- Positions with natural semantic groupings (e.g., retrieval-side vs governance-side)

## When NOT to Use

- 3 or fewer positions (use governed-triangulation)
- Simple implementation tasks
- Linear decisions with no competing alternatives
- Positions that don't cluster into meaningful brackets

## Why Not Full Pairwise at Scale

At 3 agents, full pairwise (governed triangulation) is elegant — 3 edges, 9 context reports, clean geometry.

At 5-7 agents, full pairwise produces:
- **Too many edges:** 5 agents = 10 edges, 7 agents = 21 edges
- **Too much repetition:** Each agent studies 4-6 opponents instead of 2
- **Too much drift:** By round 3, agents lose track of the full argument space
- **Too much token burn:** O(n²) context gathering vs O(n) with brackets

The tournament lattice preserves adversarial pressure while keeping edges manageable.

## Shape

Instead of a complete graph, run a tournament:

1. **Partition** positions into brackets of 2-3
2. **Run local governed triangulation** within each bracket (context → defense → rebuttal)
3. **Extract local synthesis** — strongest surviving structure per bracket
4. **Cross-bracket challenge** — bracket outputs challenge each other
5. **Optional wildcard audit** — adversarial auditor attacks both bracket syntheses
6. **Final synthesis** — lead extracts surviving structure from the full tournament

## Bracket Configurations

| Agents | Bracket 1 | Bracket 2 | Wildcard | Total Tasks |
|--------|-----------|-----------|----------|-------------|
| 5      | A, B, C (triangulation) | D, E (dyadic) | — | 20 |
| 6      | A, B, C (triangulation) | D, E, F (triangulation) | — | 20 |
| 7      | A, B, C (triangulation) | D, E, F (triangulation) | G (auditor) | 25 |

### 6-Agent Configuration

Uses the same task template as 7-agent without the wildcard tasks. Both brackets run full triangulation (3 agents each).

### Bracket Asymmetry (3+2)

The 5-agent configuration uses asymmetric brackets: one triangulation (3 agents) and one dyadic (2 agents). The dyadic bracket produces lighter local adversarial pressure than the triangulation bracket, but cross-bracket challenge partially compensates — the dyadic bracket's synthesis faces the same structural scrutiny as the triangulation bracket's during the challenge phase.

This asymmetry is viable, not ideal. If all positions are equally contentious, prefer 6-agent (two full triangulations) when feasible. Use 3+2 when position count is fixed at 5 or when natural semantic grouping produces a clear 3/2 split.

<!-- promoted from T-CPR-1 (tic 40→42). Source: federation-strategic-direction-tournament pressure-report 2026-03-11. First tournament lattice run. Confidence: 0.80 (reinforced). Band: COGNITIVE. -->

## Grouping Rule

Group brackets by **semantic adjacency**, not randomly.

If positions A/B/C are retrieval-side approaches, put them together.
If positions D/E/F are governance-side approaches, put them together.
Then cross-bracket compares retrieval synthesis vs governance synthesis.

**Why this matters:** Semantic grouping ensures that local contests produce a coherent bracket synthesis. Random grouping produces mushy local results that don't compose well in cross-bracket challenge.

## The Wildcard (7th Agent)

The 7th agent is **NOT another advocate**. It is an adversarial auditor.

Its job:
- Study both bracket outputs (after local synthesis completes)
- Attack hidden assumptions that both brackets share
- Expose false convergence (both brackets agreeing for the wrong reasons)
- Identify untested dependencies between bracket-winning positions
- Challenge the structural coherence of the emerging synthesis

**The wildcard is often more valuable than a seventh partisan.** A seventh advocate adds another voice to one bracket. The wildcard attacks the entire tournament's conclusions.

### Wildcard Protocol

1. Wildcard is blocked until BOTH bracket syntheses complete
2. Wildcard studies both bracket outputs (task 21)
3. Wildcard attacks false convergence and hidden assumptions (task 22)
4. Both brackets must respond to wildcard challenges (tasks 23-24)
5. Final synthesis incorporates wildcard findings (task 25)

The wildcard may NOT:
- Advocate for any position
- Propose its own architecture
- Rank bracket outputs (that's the lead's job)

## Two-Stage Scoring

### Local Bracket Scoring (standard rubric)

| Score | Category |
|-------|----------|
| +1 | Factual insight |
| +2 | Strategic relevance |
| +3 | Steelman of rival argument |
| +4 | Structural weakness identified |
| +5 | Architectural reframe |

Penalties:
| Score | Category |
|-------|----------|
| -2 | Shallow claim |
| -3 | Unsupported assertion |
| -5 | Hallucinated fact |

### Cross-Bracket Scoring (extended rubric)

In addition to the local rubric, cross-bracket and wildcard phases add:

| Score | Category | Description |
|-------|----------|-------------|
| +6 | Hidden dependency exposed | Identifies a dependency between bracket-winning positions that neither bracket surfaced |
| +7 | Survives wildcard attack | Position withstands adversarial audit without structural damage |

Cross-bracket penalties:
| Score | Category |
|-------|----------|
| -4 | False convergence |
| -3 | Untested assumption |

This two-stage scoring makes the final synthesis harder to fake — positions must survive both local adversarial pressure AND cross-bracket challenge.

See `scoring.yaml` for machine-readable format.

## Cross-Bracket Challenge as Distinctive Mechanism

Cross-bracket challenge is the tournament lattice's distinctive epistemic value-add over governed triangulation. While local brackets run standard triangulation (context → defense → rebuttal), the cross-bracket phase is where hidden dependencies between bracket-winning positions emerge — dependencies that neither bracket surfaced during local synthesis.

Three categories of hidden dependency observed in the first tournament run:
1. **Common root dependencies** — bracket winners that appear independent but share an underlying prerequisite
2. **Multiplier relationships** — one bracket's infrastructure enabling the other bracket's value proposition
3. **Verification relationships** — one bracket's output serving as diversity/stress-test for the other

These dependencies are the tournament's primary epistemic output beyond what governed triangulation produces. The format's value proposition is: **local brackets produce refined positions; cross-bracket challenge reveals the relationships between them.**

<!-- promoted from T-CPR-3 (tic 40→42). Source: federation-strategic-direction-tournament pressure-report 2026-03-11. Convergent confidence — multiple independent agents identified cross-bracket as distinctive mechanism. Confidence: 0.90. Band: COGNITIVE. -->

## Rule 10 — Pressure Extraction

After final synthesis, the lead must produce a **pressure report** as a separate artifact. This rule is inherited from governed triangulation and applies identically at the tournament scale.

The pressure report must identify:
- **Convergent discoveries** — facts independently found by opposed agents (especially cross-bracket convergence, which is stronger than within-bracket convergence)
- **Unresolved contradictions** — tensions the synthesis could not dissolve
- **Repeated attack surfaces** — weaknesses targeted by multiple opponents across brackets
- **Hidden dependencies** — structural couplings exposed during cross-bracket challenge or wildcard audit
- **False convergence risks** — consensus that formed on weak foundations (the wildcard's primary detection target)
- **Candidate durable lessons** — reusable rules that emerged from the process

Routing follows the arena mode (see Arena Routing section below).

**The arena is not complete until BOTH synthesis output AND pressure report are produced.**

## Self-Referential Evidence Principle

Arena specs that include a self-referential evidence requirement — where advocates must examine their own run's metrics as evidence for their claims — produce measurably stronger concrete evidence than abstract argumentation alone.

In the first tournament run, the strongest concrete evidence came from self-referential examination:
- An advocate citing its own 40-file-read count as evidence of system complexity
- An advocate measuring coordination overhead across the 5-agent team as evidence about governance scaling

Self-referential evidence is not always applicable (the arena question must be about a property the arena itself exercises), but when it is, it should be explicitly required in the arena spec's prompt template.

<!-- promoted from T-CPR-4 (tic 40→42). Source: federation-strategic-direction-tournament pressure-report 2026-03-11. N=1 (first tournament with self-referential requirement). Confidence: 0.75 (reinforced). Band: COGNITIVE. -->

## 6-Layer Meta-Model

The tournament lattice inherits the governed triangulation meta-model and extends it:

| Layer | Function | What it produces |
|-------|----------|-----------------|
| 1. Triangulation | Surface geometry | Pairwise coverage within brackets |
| 2. Dependency gating | Governance | Enforced phase ordering at local AND cross-bracket scope |
| 3. Adversarial incentives | Pressure | Local partisans + cross-bracket structural challenge + wildcard audit |
| 4. Lead synthesis | Signal extraction | Two-pass: local bracket synthesis → final synthesis |
| 5. Pressure extraction | Governance bridge | Converts arena findings into signal/CogPR candidates for CGG |
| 6. Institutional memory | Capture | Discoveries from both bracket-local and cross-bracket phases persist |

The tournament lattice adds a **scaling dimension** that governed triangulation lacks: the bracket partition converts O(n²) edges to O(n) while preserving adversarial pressure through cross-bracket challenge. Layer 5 (pressure extraction) is what makes tournaments compound across the governance lifecycle.

## Task Templates

### 5-Agent (20 tasks)

```
Bracket 1 (triangulation):           Bracket 2 (dyadic):
[1] A studies B+C  ─┐                [4] D studies E  ─┐
[2] B studies A+C  ─┼─ (parallel)    [5] E studies D  ─┘ (parallel)
[3] C studies A+B  ─┘                        │
         │                                   │
         ▼                                   ▼
[6] A defends A   ─┐                [9]  D defends D  ─┐
[7] B defends B   ─┼─ (blocked 1-3) [10] E defends E  ─┘ (blocked 4-5)
[8] C defends C   ─┘                        │
         │                                   │
         ▼                                   ▼
[11] A rebuts     ─┐                [14] D rebuts     ─┐
[12] B rebuts     ─┼─ (blocked 6-8) [15] E rebuts     ─┘ (blocked 9-10)
[13] C rebuts     ─┘                        │
         │                                   │
         ▼                                   ▼
[16] Lead: Synthesize Bracket 1     [17] Lead: Synthesize Bracket 2
         (blocked 11-13)                     (blocked 14-15)
                   │                         │
                   ▼                         ▼
[18] Cross-bracket: B1 challenges B2  (blocked 16,17)
[19] Cross-bracket: B2 challenges B1  (blocked 16,17)
                   │
                   ▼
[20] Lead: Final synthesis  (blocked 18,19)
                   │
                   ▼
[21] Lead: Pressure extraction  (blocked 20)
```

### 7-Agent with Wildcard (26 tasks)

```
Bracket 1 (triangulation):           Bracket 2 (triangulation):
[1] A studies B+C  ─┐                [4] D studies E+F  ─┐
[2] B studies A+C  ─┼─ (parallel)    [5] E studies D+F  ─┼─ (parallel)
[3] C studies A+B  ─┘                [6] F studies D+E  ─┘
         │                                   │
         ▼                                   ▼
[7]  A defends A   ─┐                [10] D defends D  ─┐
[8]  B defends B   ─┼─ (blocked 1-3) [11] E defends E  ─┼─ (blocked 4-6)
[9]  C defends C   ─┘                [12] F defends F  ─┘
         │                                   │
         ▼                                   ▼
[13] A rebuts      ─┐                [16] D rebuts     ─┐
[14] B rebuts      ─┼─ (blocked 7-9) [17] E rebuts     ─┼─ (blocked 10-12)
[15] C rebuts      ─┘                [18] F rebuts     ─┘
         │                                   │
         ▼                                   ▼
[19] Lead: Synthesize Bracket 1     [20] Lead: Synthesize Bracket 2
         (blocked 13-15)                     (blocked 16-18)
                   │                         │
                   └──────────┬──────────────┘
                              ▼
               [21] WILDCARD-G: Study both syntheses (blocked 19,20)
                              │
                              ▼
               [22] WILDCARD-G: Attack false convergence (blocked 21)
                              │
                              ▼
               [23] Lead: B1 responds to wildcard (blocked 22)
               [24] Lead: B2 responds to wildcard (blocked 22)
                              │
                              ▼
               [25] Lead: Final synthesis (blocked 23,24)
                              │
                              ▼
               [26] Lead: Pressure extraction (blocked 25)
```

See `tasks.yaml` for machine-readable templates with full dependency chains.

## Dependency Rule

```
context → defense → rebuttal → local synthesis
  → [wildcard audit] → cross-bracket response → final synthesis
  → pressure extraction
```

No phase may start until its predecessors complete.
The lead must not synthesize early.
The wildcard must not advocate.
The arena must not end without pressure extraction.

## Local Synthesis Options

After each bracket completes, the lead has two options:

- **Option A (competitive):** Select the winning position from the bracket
- **Option B (structural):** Extract the strongest surviving structure from all bracket positions

For architecture work, Option B is usually better — the goal is to find the best structure, not to declare a winner.

## Invariant

> local pressure → local survival → cross-bracket pressure → final survival → pressure extraction → memory

This invariant ensures that positions must survive multiple rounds of increasingly broad challenge before entering the final synthesis, and that the arena's findings are classified for governance routing before being recorded.

## Arena Routing

Every arena run must declare a mode that controls how its outputs are routed. See `governed-triangulation/spec.md` for the full routing specification.

### Modes

| Mode | Purpose | Allowed outputs |
|------|---------|----------------|
| `operational` | Real decisions — architecture, build order, root cause | Subject lessons, process lessons, meta lessons, signals, CogPR candidates |
| `experimental` | Reasoning experiments — demos, stress tests, teaching | Process lessons, meta lessons only. No signals, no subject lessons, no governance mutation |

### Capture Policy (declared in arena spec)

```yaml
# Operational default
capture_policy:
  allow_subject_lessons: true
  allow_process_lessons: true
  allow_meta_lessons: true
  allow_signals: true
  allow_warrants: true
  allow_governance_mutation: false  # still human-gated via /review

# Experimental default
capture_policy:
  allow_subject_lessons: false
  allow_process_lessons: true
  allow_meta_lessons: true
  allow_signals: false
  allow_warrants: false
  allow_governance_mutation: false
```

### Drift-Safety Invariant

```
Experimental arenas may learn freely.
They just may not legislate from what they learn.
```

Block routing, not learning. Experimental arenas keep all findings locally. Only governance routing is gated by mode.

### Enforcement Rules (hard constraints)

```
if arena_mode == experimental:
  persist all findings locally              # learning stays high
  block candidate_signals                   # no BEACONs, no TENSIONs to manifold
  block candidate_cogprs where lesson_type == subject  # no subject legislation
  route candidate_cogprs where lesson_type in (process, meta)
  block warrants, governance_mutation

if arena_mode == operational:
  persist all findings locally
  route candidate_signals by confidence_tier
  route all candidate_cogprs by confidence_tier
  governance_mutation = human_gated           # /review required
```

### Confidence Tiers

Operational arenas gate governance routing by confidence:

| Tier | Meaning | Allowed action |
|------|---------|---------------|
| `tentative` | Appeared once, not stress-tested | Notes/candidates only. Not law. |
| `reinforced` | Survived rebuttal or repeated attack | CogPR/signal candidates |
| `convergent` | Independently discovered by opposed agents/brackets | High-priority candidates. Cross-bracket convergence > within-bracket. |

See `governed-triangulation/spec.md` for the full routing specification, lesson taxonomy, and capture policy reference.
