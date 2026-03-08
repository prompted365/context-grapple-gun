# Mini-Swarm Onboard Arena — Specification

**Pattern:** governed-triangulation + narration gates (Rule 0)
**Geometry:** Full pairwise triangle
**Strength:** 3x (opponent-context + defense + rebuttal)
**Tasks:** 15 (11 arena + 4 narration gates)
**Mode:** experimental (process/meta CogPRs route; subject findings stay local)
**Duration:** ~15-20 min (--quick compresses narration)

## Purpose

Onboard new CGG users by DEMONSTRATING governance in action. Three agents debate "Which CGG mechanic is most valuable?" — the user watches governed triangulation produce real governance artifacts, learning by observation rather than instruction.

## When to Use

- New user onboarding — first encounter with CGG governance
- Demonstrating the arena system to stakeholders
- Teaching governed reasoning patterns to teams
- Quick governance stress-test after installation

## When NOT to Use

- Real architecture decisions (use `governed-triangulation` in operational mode)
- Users already familiar with CGG mechanics
- Contexts where the ~15-minute runtime is prohibitive (unless `--quick`)

## Agents

| Agent | Position | Argument |
|-------|----------|----------|
| SIGNAL-ADVOCATE | Signal Manifold (/siren) | Persistent conditions, acoustic routing, nothing forgotten |
| PIPELINE-ADVOCATE | CogPR Pipeline | Born truth → earned doctrine, human-gated promotion |
| CADENCE-ADVOCATE | Cadence System | Forced boundaries, structured handoff, multi-session continuity |
| LEAD | Orchestrator + Narrator | Synthesizer and narration gate controller (does not advocate) |

## The 11 Rules

### Rule 0 — Narration Gates (extends base governed-triangulation)

Between each phase, the LEAD pauses to explain what just happened to the user. This turns the arena from a reasoning tool into a teaching tool. Four narration gates (N1-N4) are injected between phases.

Narration gates are dependency-gated like all other tasks — they block subsequent phases until complete.

**Narration content:**

**N1** (after context phase):
> "You just watched three agents study their opponents before defending themselves. Rule 1 — Opponent-Context First — prevents strawmen. Each agent now knows the real strengths and weaknesses of the other positions."

**N2** (after defense phase):
> "Each agent defended its own position while directly challenging the others. Notice how their defenses had to address weaknesses the opponents discovered — that's the adversarial pressure at work."

**N3** (after rebuttal phase):
> "The rebuttal round is the 3x multiplier. Without it, agents present once and the lead guesses. With it, the strongest arguments survive challenge. Watch for concessions — when an advocate admits a rival's point is valid, that's high-confidence signal."

**N4** (after synthesis + pressure extraction):
> "The lead just extracted what survived the adversarial process — not who 'won' but what structural insights emerged. The pressure report classifies findings by confidence tier. Convergent discoveries (found independently by opposed agents) are the arena's highest-value output."

**`--quick` mode:** When `--quick` is set, compress each narration gate to a single-line summary instead of the full narration text.

### Rule 1 — Opponent-Context First

Each advocate must begin by gathering strategic context on the OTHER two positions. No self-defense allowed in this stage.

Context reports must include:
- Real strengths (not strawmen)
- Real weaknesses (structural, not cosmetic)
- Structural dependencies (what does this position require to work?)
- Implementation risks (what could go wrong?)
- Architectural role (what does this position contribute to the whole?)

**Why this rule matters:** Without forced opponent study, advocates construct strawmen. The opponent-context-first pattern ensures each agent knows the real strengths and weaknesses of rival positions before defending its own.

### Rule 2 — Defense Round

After ALL context reports complete and N1 narration completes, each advocate defends its own position. Each defense must:
- Address weaknesses discovered by opponents in context phase
- Explain structural dependencies honestly
- Directly challenge the other two positions with specific evidence

**Key constraint:** Defense is blocked until ALL three context reports exist AND narration gate N1 has fired.

### Rule 3 — Rebuttal Round (the 3x Multiplier)

After ALL defenses complete and N2 narration completes, each advocate responds to the attacks against its position. This is what makes governed triangulation "3x strength" — without rebuttal, advocates present once and the lead guesses what would survive challenge.

Rebuttals must:
- Resolve contradictions raised during defense
- Counter structural attacks with evidence
- Identify flawed assumptions in rival critiques
- Concede points that are genuinely correct

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
context → N1 → defense → N2 → rebuttal → N3 → synthesis → pressure extraction → N4
```

No phase may start until ALL tasks in the previous phase (including narration gates) complete. This is enforced through task dependency chains, not honor system.

- Context tasks [1,2,3]: no blockers (run in parallel)
- Narration gate [N1]: blocked by [1,2,3]
- Defense tasks [4,5,6]: blocked by [N1]
- Narration gate [N2]: blocked by [4,5,6]
- Rebuttal tasks [7,8,9]: blocked by [N2]
- Narration gate [N3]: blocked by [7,8,9]
- Synthesis task [10]: blocked by [N3]
- Pressure extraction [11]: blocked by [10]
- Narration gate [N4]: blocked by [11]

See `tasks.yaml` for the full dependency template.

### Rule 6 — Lead Behavior (Signal Extraction + Narration)

The lead must NOT:
- Debate or advocate for any position
- Synthesize before ALL rounds complete
- Summarize early (this biases what advocates focus on in later rounds)
- Resolve ties prematurely

The lead MUST:
- Deliver narration gates between phases (Rule 0)
- Wait for all agents to finish all rounds
- Extract convergent discoveries (Rule 7)
- Identify surviving arguments
- Produce final synthesis (Rule 8)

### Rule 7 — Convergent Discovery Rule

> Independent discovery + opposed incentives + same conclusion = HIGH-CONFIDENCE signal.

When multiple agents with structurally opposed interests discover the same fact independently, that fact has passed an adversarial filter. These convergent discoveries are the arena's highest-value output.

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

**The arena is not complete until BOTH synthesis output AND pressure report are produced, AND narration gate N4 has fired.**

## Task Structure

```
[1] SIGNAL-ADVOCATE studies CogPR Pipeline + Cadence System ─┐
[2] PIPELINE-ADVOCATE studies Signal Manifold + Cadence System ─┼─ (parallel)
[3] CADENCE-ADVOCATE studies Signal Manifold + CogPR Pipeline ─┘
         │
         ▼
[N1] LEAD narrates Rule 1 to user (blocked by 1,2,3)
         │
         ▼
[4] SIGNAL-ADVOCATE defends Signal Manifold     ─┐
[5] PIPELINE-ADVOCATE defends CogPR Pipeline    ─┼─ (blocked by N1)
[6] CADENCE-ADVOCATE defends Cadence System     ─┘
         │
         ▼
[N2] LEAD narrates adversarial pressure (blocked by 4,5,6)
         │
         ▼
[7] SIGNAL-ADVOCATE rebuts       ─┐
[8] PIPELINE-ADVOCATE rebuts     ─┼─ (blocked by N2)
[9] CADENCE-ADVOCATE rebuts      ─┘
         │
         ▼
[N3] LEAD narrates convergent discovery rule (blocked by 7,8,9)
         │
         ▼
[10] LEAD synthesizes (blocked by N3)
         │
         ▼
[11] LEAD produces pressure report (blocked by 10)
         │
         ▼
[N4] LEAD walks user through pressure report (blocked by 11)
```

See `tasks.yaml` for the machine-readable template and `prompt.txt` for the ready-to-paste spawning prompt.

## Arena Mode

This arena runs in **experimental** mode. Subject-matter findings (which CGG mechanic is "most valuable") stay local — they are demonstration artifacts, not governance inputs. Process and meta lessons (about how the arena itself works) may route to governance via the CogPR pipeline.

```yaml
capture_policy:
  allow_subject_lessons: true
  route_subject_lessons_to_governance: false
  persist_subject_lessons_locally: true
  allow_process_lessons: true
  allow_meta_lessons: true
  allow_signals: false
  allow_warrants: false
  allow_governance_mutation: false
```

## Invariant

> study opponents → narrate → defend → narrate → rebut → narrate → synthesize → extract pressure → narrate

Never allow: defend → study → synthesize (skipping opponent-context produces strawmen).
Never allow: synthesize → rebut (lead synthesis before rebuttal forecloses the strongest arguments).
Never allow: end at synthesis without pressure extraction (arena decides but doesn't teach).
Never allow: skip narration gates (the teaching value is the entire point of this arena).
