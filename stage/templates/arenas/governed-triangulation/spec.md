# Governed Triangulation Arena — Full Specification

**Pattern:** 3 partisan advocates + 1 lead synthesizer
**Geometry:** Full pairwise triangle (every edge traversed)
**Strength:** 3x (opponent-context + defense + rebuttal)
**Tasks:** 11 (3 context, 3 defense, 3 rebuttal, 1 synthesis, 1 pressure extraction)
**Validated:** rationalized-learning-regalia (2026-03-07, tic 213)

## When to Use

- Architecture decisions with exactly 3 competing positions
- Build ordering (what ships first?)
- Root cause analysis (3 competing hypotheses)
- Policy debates with structural consequences
- Any decision where adversarial pressure reveals hidden dependencies

## When NOT to Use

- Simple implementation (single-file, linear)
- More than 3 competing positions (use tournament-lattice)
- Tasks where the answer is already known
- Low-stakes decisions where the governance overhead exceeds the value

## The 10 Rules

### Rule 1 — Opponent-Context First

Each advocate must begin by gathering strategic context on the OTHER two positions. No self-defense allowed in this stage.

Context reports must include:
- Real strengths (not strawmen)
- Real weaknesses (structural, not cosmetic)
- Structural dependencies (what does this position require to work?)
- Implementation risks (what could go wrong?)
- Architectural role (what does this position contribute to the whole?)

**Why this rule matters:** Without forced opponent study, advocates construct strawmen. The rationalized-learning-regalia run proved that opponents discovered facts about rival positions that the advocates themselves hadn't articulated (e.g., all three independently found the `expression_factor: 0.615` placeholder).

### Rule 2 — Defense Round

After ALL context reports complete, each advocate defends its own position. Each defense must:
- Address weaknesses discovered by opponents in context phase
- Explain structural dependencies honestly
- Directly challenge the other two positions with specific evidence

**Key constraint:** Defense is blocked until ALL three context reports exist. This ensures every advocate has seen what opponents found about them before they defend.

### Rule 3 — Rebuttal Round (the 3x Multiplier)

After ALL defenses complete, each advocate responds to the attacks against its position. This is what makes governed triangulation "3x strength" — without rebuttal, advocates present once and the lead guesses what would survive challenge.

Rebuttals must:
- Resolve contradictions raised during defense
- Counter structural attacks with evidence
- Identify flawed assumptions in rival critiques
- Concede points that are genuinely correct

**Why rebuttal is non-optional:** The rationalized-learning-regalia run showed that MINING-ARCHITECT's rebuttal reframed Phase 5's dependency as softer than documented, changing the final build order from sequential to parallel. Without rebuttal, that correction would have been lost.

**Rebuttal under convergence:** When advocates converge during the defense phase, rebuttal may compress in length but is never skipped. Apparent agreement in defense may be weak advocacy, not genuine convergence — an advocate that does not rebut may be concealing an unvoiced challenge. The rebuttal round is where you find out which. Budget for convergence-compression, not rebuttal-elimination.

<!-- Added from marketplace-epistemic-triangulation arena (tic 9). All three advocates converged in defense; rebuttal round verified the convergence was genuine through concessions and scope refinements. -->

### Rule 4 — Scoring Rubric

Points (ascending value):
| Score | Category | Description |
|-------|----------|-------------|
| +1 | Factual insight | Verifiable claim about the system |
| +2 | Strategic relevance | Connects to the actual decision being made |
| +3 | Steelman of rival | Strongest possible version of opponent's argument |
| +4 | Structural weakness | Identifies a dependency or failure mode |
| +5 | Architectural reframe | Changes how the decision space is understood |

Penalties:
| Score | Category | Description |
|-------|----------|-------------|
| -2 | Shallow claim | Assertion without structural reasoning |
| -3 | Unsupported assertion | Claim with no evidence or logical basis |
| -5 | Hallucinated fact | Fabricated evidence (immediate disqualification of that argument) |

See `scoring.yaml` for machine-readable format.

### Rule 5 — Dependency Gating (Enforced)

```
context → defense → rebuttal → synthesis → pressure extraction
```

No phase may start until ALL tasks in the previous phase complete. This is enforced through task dependency chains, not honor system.

- Context tasks [1,2,3]: no blockers (run in parallel)
- Defense tasks [4,5,6]: blocked by [1,2,3]
- Rebuttal tasks [7,8,9]: blocked by [4,5,6]
- Synthesis task [10]: blocked by [7,8,9]
- Pressure extraction [11]: blocked by [10]

See `tasks.yaml` for the full dependency template.

### Rule 6 — Lead Behavior (Signal Extraction, Not Advocacy)

The lead must NOT:
- Debate or advocate for any position
- Synthesize before ALL rounds complete
- Summarize early (this biases what advocates focus on in later rounds)
- Resolve ties prematurely

The lead MUST:
- Wait for all agents to finish all rounds
- Extract convergent discoveries (Rule 7)
- Identify surviving arguments
- Produce final synthesis (Rule 8)

### Rule 7 — Convergent Discovery Rule

> Independent discovery + opposed incentives + same conclusion = HIGH-CONFIDENCE signal.

When multiple agents with structurally opposed interests discover the same fact independently, that fact has passed an adversarial filter. These convergent discoveries are the arena's highest-value output.

**Example:** In rationalized-learning-regalia, all three advocates independently found `expression_factor: 0.615` as a uniform placeholder — none were incentivized to find it, but all did. This became the highest-confidence finding.

### Rule 8 — Synthesis Output

The lead must produce:
1. **Corrected decision or architecture** — what the arena evidence supports
2. **Dependency graph** — structural ordering that survived challenge
3. **Implementation order** — if applicable, what ships in what sequence
4. **Key discoveries** — convergent findings, reframes, and concessions

The synthesis is NOT a vote count. It extracts surviving structure from the adversarial process.

### Rule 9 — Institutional Memory

After synthesis, record to persistent memory:
- **Structural discoveries** — facts about the system that were not known before the arena
- **Process lessons** — what worked and what didn't about the arena itself
- **Corrected decisions** — where the arena changed the pre-existing plan

This is what makes arenas compound. Without institutional memory, each arena starts from zero.

### Rule 10 — Pressure Extraction

After final synthesis, the lead must produce a **pressure report** as a separate artifact from the synthesis.

The pressure report must identify:
- **Convergent discoveries** — facts independently found by opposed agents
- **Unresolved contradictions** — tensions the synthesis could not dissolve
- **Repeated attack surfaces** — weaknesses targeted by multiple opponents
- **Hidden dependencies** — structural couplings exposed during the arena
- **False convergence risks** — consensus that formed on weak foundations
- **Candidate durable lessons** — reusable rules that emerged from the process

Each finding must be classified on two axes:

**Lesson type:** `subject | process | meta`
**Confidence tier:** `tentative | reinforced | convergent`

Confidence tiers:
- `tentative` — appeared once, not strongly stress-tested
- `reinforced` — survived rebuttal, repeated attack, or multiple supports
- `convergent` — independently discovered by opposed agents

Routing depends on arena mode (see Arena Routing section below).

**The arena is not complete until BOTH synthesis output AND pressure report are produced.**

See `scoring.yaml` for the pressure report output schema.

**Why this rule exists:** Without pressure extraction, the arena decides but doesn't teach. The governance system never learns what remained unresolved, what kept recurring, what contradiction survived, or what dependency appeared across rivals. Pressure extraction turns the arena from a reasoning tool into a governance-producing reasoning tool.

## 6-Layer Meta-Model

The governed triangulation primitive operates through six composable layers:

| Layer | Function | What it produces |
|-------|----------|-----------------|
| 1. Triangulation | Surface geometry | Each node studies the other two — full pairwise coverage |
| 2. Dependency gating | Governance | Enforced phase ordering prevents premature synthesis |
| 3. Adversarial incentives | Pressure | Partisan advocates, not neutral analysts — each WANTS to win |
| 4. Lead synthesis | Signal extraction | Convergent discoveries, surviving arguments, corrected decisions |
| 5. Pressure extraction | Governance bridge | Converts arena findings into signal/CogPR candidates for CGG |
| 6. Institutional memory | Capture | Discoveries and process lessons persist beyond the arena |

Layer 5 is the governance bridge — it connects the arena's reasoning output to CGG's governance lifecycle. Without it, arenas produce decisions but not governance inputs. With it, the arena feeds the abstraction ladder:

```
arena reasoning → pressure extraction → signal/CogPR candidates → review gate → promotion → CLAUDE.md
```

These layers are independent and composable. Layer 1 (geometry) works without layer 3 (adversarial incentives), but the combination is what produces the 3x strength multiplier. Layer 5 (pressure extraction) is what makes arenas compound across the governance lifecycle.

## Task Structure

```
[1] A studies B+C  ─┐
[2] B studies A+C  ─┼─ (parallel, no blockers)
[3] C studies A+B  ─┘
         │
         ▼
[4] A defends A    ─┐
[5] B defends B    ─┼─ (blocked by 1,2,3)
[6] C defends C    ─┘
         │
         ▼
[7] A rebuts       ─┐
[8] B rebuts       ─┼─ (blocked by 4,5,6)
[9] C rebuts       ─┘
         │
         ▼
[10] Lead synthesizes (blocked by 7,8,9)
         │
         ▼
[11] Lead: pressure extraction (blocked by 10)
```

See `tasks.yaml` for the machine-readable template and `prompt.txt` for the ready-to-paste spawning prompt.

## Invariant

> study opponents → defend → rebut → synthesize → extract pressure

Never allow: defend → study → synthesize (skipping opponent-context produces strawmen).
Never allow: synthesize → rebut (lead synthesis before rebuttal forecloses the strongest arguments).
Never allow: end at synthesis without pressure extraction (arena decides but doesn't teach).

## Reference Implementation

The first validated run was **rationalized-learning-regalia** (2026-03-07):
- 3 sonnet advocates + opus lead
- Question: "What is the correct build order for Phases 3, 4, and 5?"
- Result: Changed plan from sequential (3→4→5) to parallel (3→(4∥5))
- Key discovery: Phase 5's dependency on Phases 3+4 was softer than documented
- Convergent signal: `expression_factor: 0.615` placeholder found independently by all three advocates
- Full log: `audit-logs/teams/rationalized-learning-regalia.md`
- Show spec: `stage/specs/rationalized-learning-regalia.yaml`

## Arena Routing

Every arena run must declare a mode that controls how its outputs are routed.

### Modes

| Mode | Purpose | Learning | Governance routing |
|------|---------|----------|-------------------|
| `operational` | Real decisions — architecture, build order, root cause | All lesson types | Confidence-gated via `/review` |
| `experimental` | Reasoning experiments — demos, stress tests, teaching | All lesson types (kept locally) | Process/meta only — subject blocked from governance |

### Lesson Taxonomy

Arena findings are classified on two axes:

**Lesson type:**
- **Subject** — about the debated topic itself (e.g., "Phase 5's dependency is softer than documented")
- **Process** — about how the arena improved reasoning (e.g., "Rebuttal round changed the build order")
- **Meta** — about governance/routing/protocol design (e.g., "Opponent-context first prevents strawmen")

**Confidence tier:**
- **Tentative** — appeared once, not strongly stress-tested
- **Reinforced** — survived rebuttal, repeated attack, or multiple supports
- **Convergent** — independently discovered by opposed agents or brackets

### Drift-Safety Invariant

```
Experimental arenas may learn freely.
They just may not legislate from what they learn.
```

The key move: **block routing, not learning.** Experimental arenas keep all findings — subject, process, meta — in arena-local artifacts. Only governance routing is gated by mode.

### Routing Rules

#### Operational arenas

All lesson types route, but confidence gates the governance path:

| Confidence | Allowed action |
|-----------|---------------|
| `tentative` | May become notes or candidate artifacts. Must NOT directly become law. May open review packets. |
| `reinforced` | May become CogPR candidates. May become signal candidates if pressure is unresolved. |
| `convergent` | May become high-priority CogPR / BEACON / TENSION candidates. Still human-gated before governance mutation. |

#### Experimental arenas

All lesson types are preserved locally. Governance routing is blocked for subject matter:

| Lesson type | Learning | Governance routing |
|------------|----------|-------------------|
| `subject` | Retained in arena output + local sandbox/history | BLOCKED — must NOT route to governance surfaces, signals, or warrants |
| `process` | Retained | May become CogPR candidates |
| `meta` | Retained | May become CogPR candidates |

### Enforcement Rules (hard constraints)

```
if arena_mode == experimental:
  persist all findings locally              # learning stays high
  block candidate_signals                   # no BEACONs, no TENSIONs to manifold
  block candidate_cogprs where lesson_type == subject  # no subject legislation
  route candidate_cogprs where lesson_type in (process, meta)  # protocol learning OK
  block warrants
  block governance_mutation

if arena_mode == operational:
  persist all findings locally
  route candidate_signals by confidence_tier  # tentative=note, reinforced=candidate, convergent=high-priority
  route all candidate_cogprs by confidence_tier
  governance_mutation = human_gated           # /review required
```

### Capture Policy (declared in arena spec)

```yaml
# Operational default
capture_policy:
  allow_subject_lessons: true
  route_subject_lessons_to_governance: true
  persist_subject_lessons_locally: true
  allow_process_lessons: true
  allow_meta_lessons: true
  allow_signals: true
  allow_warrants: true
  allow_governance_mutation: false  # still human-gated via /review

# Experimental default
capture_policy:
  allow_subject_lessons: true
  route_subject_lessons_to_governance: false  # block routing, not learning
  persist_subject_lessons_locally: true       # keep everything
  allow_process_lessons: true
  allow_meta_lessons: true
  allow_signals: false
  allow_warrants: false
  allow_governance_mutation: false
```

### CGG Lifecycle Bridge

The arena's pressure extraction step maps directly to CGG's governance lifecycle:

```
arena pressure extraction
      ↓
classify by (lesson_type, confidence_tier)
      ↓
convergent discovery → BEACON candidate (operational only)
surviving contradiction → TENSION candidate (operational only)
reusable lesson → CogPR candidate (confidence-gated)
      ↓
/review gate
      ↓
promotion / rejection
      ↓
CLAUDE.md (institutional memory)
```

This closes the loop: the reasoning engine feeds the governance engine.

## Cognitive Budget Governance

Budget routing and execution envelope primitives, promoted from T3G arena operational findings.

### Budget Routing Function (L1-L2)

The routing function is tripartite: `format_gate → budget_gate → {LOW | MIDDLE | LIBERAL}`.

| Regime | Budget | Scope | Default? |
|--------|--------|-------|----------|
| LIBERAL | ~22 turns/advocate | Novel doctrine, no prior template, high reversal cost | No |
| MIDDLE | 18 turns/advocate | Standard governance questions, bounded scope | Yes (least-damaging failure mode) |
| LOW | 8 turns/task | Format-layer tasks below full governed triangulation | No |

MIDDLE is the correct default when task-class classifier signals are absent — its failure mode (modest waste) is less damaging than LOW's (protocol truncation) or LIBERAL's (context saturation).

<!-- promoted from CogPR-30 L1-L2 (tic 21→22, arena-sourced T3G). 5 convergent discoveries from 3 opposed advocates. Band: COGNITIVE. -->

### Execution Envelope Schema

The execution envelope carries budget metadata from the routing function to the spawning mechanism:

```yaml
execution_envelope:
  task_class: string        # classifier output
  budget_regime: LOW | MIDDLE | LIBERAL
  max_turns: integer        # per-advocate ceiling
  budget_scope: per_advocate | per_task
  override_allowed: boolean
  override_justification: string | null
  output_length_cap: integer | null
  lead_context_check: boolean  # must verify lead context ceiling before spawn
```

This extends Rule 5 (dependency gating) with budget gating — the envelope must be resolved before advocate spawning begins.

<!-- promoted from CogPR-31 (tic 21→22, arena-sourced T3G). All three advocates identified the envelope as hidden dependency. Band: COGNITIVE. -->

### Defense-Phase Convergence Timing

Governed triangulation arenas achieve structural convergence by defense phase when the question is bounded. Rebuttal serves as verification and numerical refinement under convergence, not primary discovery.

Evidence: 2/2 operational arenas (marketplace-epistemic-triangulation + turn-budget-governance-triangulation) converged by defense phase. This strengthens Rule 3's "rebuttal under convergence" clause — convergence-compression is the normal pattern for bounded questions, not the exception.

<!-- promoted from CogPR-33 (tic 21→22, arena-sourced T3G). Reinforced by 2/2 operational arenas. Band: COGNITIVE. -->

**Rebuttal as scope revision (distinct from defense convergence):** Defense-phase convergence produces position alignment — advocates discover shared structure. Rebuttal-phase revision produces scope narrowing and sequencing shifts — advocates adjust the boundary and ordering of their positions. These are distinct operations: convergence answers "do we agree on what?", revision answers "given agreement, how does our scope change?"

Evidence: In the tournament lattice run (5 agents, 2 brackets), all 5 advocates narrowed scope and shifted toward sequencing/portfolio framing in rebuttal, not defense. This holds across both triadic (3-agent) and dyadic (2-agent) brackets, confirming that rebuttal revision is structure-independent — it is a property of the three-phase process, not of bracket geometry.

<!-- promoted from T-CPR-2 (tic 40→42). Source: federation-strategic-direction-tournament pressure-report 2026-03-11. 3rd arena confirming rebuttal's structural role, extends CogPR-33. Confidence: 0.85 (reinforced). Band: COGNITIVE. -->
