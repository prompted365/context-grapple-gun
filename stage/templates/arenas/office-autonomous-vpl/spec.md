# Office-Autonomous Value-Position Lattice with Temporal Modeling (OA-VPL-T)

**Pattern:** N registry-bound constitutional offices + 1 LEAD synthesizer + dependency-emergent brackets + post-hoc conformation + temporal tension forecast
**Geometry:** Autonomous pitch → dependency-declared brackets → paired challenges → cross-bracket + wildcard → synthesis → temporal model → conformation → pressure extraction
**Strength:** Offices derive positions from their own mandates, not from assigned labels. Brackets emerge from declared dependencies, not imposed grouping. Output includes predicted tension curve across rollout phases.
**Parent template:** value-lattice (inherits VPL conformation, scoring separation, advocate-invisible invariant field) ← governed-triangulation (inherits 10 rules, dependency gating)
**8th arena geometry template.** Validated: convergence synthesis between c45 (federation-grounded) and oa54 (framework-level), tic 121.

## Founding Principle

> Friction is evidence of hidden constitutional structure.
> The revision trail is the excavation trail of the invariant stack.

The seed artifact is not "implementation history." It is constitutional evidence. Each friction point encountered during iterative development — cwd resolution failures, bash/python quoting collapse, dual-write divergence, sub-repo git boundary blindness, manifest recursion — reveals an invariant the system had not yet named. The arena's job is to surface what those invariants mean at federation scale, through the lens of offices whose mandates make them care about different invariant layers.

## When to Use

- A concrete mechanic, friction history, or implementation artifact exists as seed evidence
- The question is "how should the federation leverage this?" not "which option wins?"
- Multiple constitutional offices have legitimate, different sub-telos-driven interests in the answer
- The rollout will unfold over time (not a single-commit change) and temporal tension modeling adds value
- You want the output to be a constitutional planning instrument, not a debate verdict

## When NOT to Use

- No concrete seed artifact exists (abstract questions should use standard VPL or governed-triangulation)
- Fewer than 5 offices have legitimate stake (use governed-triangulation or tournament-lattice)
- The question has a known answer and the arena would be compliance theater
- Single-commit changes where temporal modeling adds no value

## Core Design Principles

### 1. Office Mandate Generates Stance

No value centroids are prescribed. Each office receives its own agent spec, sub-telos declaration, and the seed evidence. The office's mandate IS the value centroid. The pitch IS the position. This eliminates the failure mode where assigned labels produce obedient paraphrase instead of genuine constitutional pressure.

### 2. Dependency-Emergent Brackets

Brackets are not imposed by the spec author. Each office declares its dependencies (what must precede, what parallelizes, what it unlocks, strongest ally, strongest adversarial corrector). The LEAD constructs brackets from these declarations. The bracket structure is derived from the actors' own understanding of their sequencing needs.

For this first instance, the expected bracket emergence (based on registered office mandates) is:

| Bracket | Question Class | Expected Offices |
|---------|---------------|-----------------|
| **Foundational** | What must be true first? What invariants are load-bearing? | Mogul, Crisis Steward, Civil Engineer |
| **Translational** | How does it become usable across media, tooling, runtime, human legibility? | cbUX Steward, Videographer, Pattern Curator (Meta) |
| **Wildcard** | Chain coherence across both brackets | Ladder Auditor |

If dependency declarations produce a different bracket composition, the LEAD follows the declarations, not this table. The table is expected, not prescribed.

### 3. VPL Separation Principle (CogPR-114)

Advocates do NOT see invariants, scoring rubrics, council references, or conformation mechanics. The five score families are LEAD-side machinery, invisible to advocates. Advocates see only their office contract. The invariant field measures post-hoc what shape the reasoning took. This separation is load-bearing: if advocates can see scoring targets, the arena degrades into compliance theater.

### 4. Temporal Tension Modeling

The output includes a predicted tension curve across six temporal windows (T0-T5). This makes the pressure report predictive rather than retrospective. The winning hybrid doesn't just say "do X" — it says "X will create this tension shape over time, and here's how we'll know if we're wrong."

### 5. Framework Extensibility, Instance Groundedness

The OA-VPL-T template supports any number of registry-bound offices. Each arena instance must use only actors registered in `autonomous_kernel/actor-registry.json`. The framework is extensible; the instance is grounded.

## Actor Registry Requirements

Every actor in an OA-VPL-T arena must satisfy:

1. **Registered** in `autonomous_kernel/actor-registry.json` with entity_class, standing, and actor_mode
2. **Sub-telos declared** — traceable to `autonomous_kernel/telos/root.yaml` or `sub_telos.yaml`
3. **Agent spec exists** — a `.md` file in `cgg-runtime/agents/` defining the office's mandate, tools, and constraints
4. **Jurisdictional mandate** — the office must have a bounded domain of concern, not a generic "strategy" role

Actors that fail any of these are not eligible. Do not invent offices for an arena run.

## Office Contract Template

Each office receives this contract as its full prompt constitution. No additional context about invariants, scoring, or other offices' mandates is provided.

```yaml
OFFICE: [name from actor-registry.json]

MANDATE: [from agent spec — what this office exists to do]

SUB_TELOS: [from telos hierarchy — which branch of governed autonomy this office serves]

PROTECTED_VALUES:
  - [derived from jurisdictional mandate]
  - [what this office treats as non-negotiable]

MAY_OPTIMIZE_AGGRESSIVELY:
  - [what this office is chartered to push hard on]

MUST_NEVER_SACRIFICE:
  - [constitutional floor — what would violate the office's identity]

RECURRING_FAILURE_MODES:
  - [from arena history + operational evidence — how this office typically goes wrong]

SUCCESS_FUNCTION: [what "winning" looks like for this office specifically]

MISUNDERSTANDING_SURFACE: [where other offices will misread this office's needs —
  this line forces pre-legible tension instead of post-hoc harmony]

SEED_EVIDENCE: [concrete file paths to the artifact set]

DECISION_QUESTION: [the specific question the arena must answer]
```

## Phase Structure (10 phases, ~32 tasks)

### Phase 0a: SELF-INTERPRETATION (N parallel, no cross-talk)

Each office independently inspects:
- Its own agent spec and sub-telos
- The seed evidence (friction history, implementation artifacts)
- What the finding means from inside that office's jurisdiction

**Output per office:** Interpretation memo answering:
1. What does this seed artifact mean to my office?
2. What are my office's success criteria for this question?
3. Where will other offices misunderstand my needs?

**Constraint:** No cross-talk. Offices cannot read each other's memos yet. This separation prevents cross-contamination of genuine office logic.

**Tasks:** N (one per office, all parallel)

### Phase 0b: STRATEGY + DEPENDENCY DECLARATION (N parallel, no cross-talk)

Each office proposes its independent strategy:

**Strategy dossier:**
1. Best federation-scale use of the finding
2. Required sequence and dependencies
3. Expected environmental effect
4. Positive impact toward own sub-goals
5. Predicted objections from other offices

**Dependency declaration:**
1. What must precede my plan
2. What can parallelize with my plan
3. What my plan unlocks for others
4. What would corrupt the rollout if done before my plan
5. Strongest ally (which office's success most enables mine)
6. Strongest adversarial corrector (which office will find my blind spots)

**Output per office:** Strategy dossier + dependency declaration

**Tasks:** N (one per office, all parallel)

### Phase 1: BRACKET FORMATION (LEAD, 1 task)

LEAD reads all dependency declarations and constructs brackets:

1. Cluster offices by dependency structure (what must be foundational vs translational vs evolutionary)
2. Assign bracket membership (2-3 offices per bracket)
3. Identify paired challenges from self-declared adversarial correctors
4. Report bracket composition and rationale

If dependency declarations don't cluster cleanly, LEAD uses the question-class heuristic:
- **Foundational:** offices whose plans require things to be true first
- **Translational:** offices whose plans transform the finding into usable form
- Remaining offices become **Evolutionary** or join the nearest bracket

**Tasks:** 1

### Phase 2-4: BRACKET TRIANGULATION (parallel per bracket)

Within each bracket, standard governed-triangulation rules apply:

**Phase 2: Context** — each office reads the other bracket members' strategy dossiers. Opponent-context-first rule (Rule 1). No self-defense.

**Phase 3: Defense** — each office defends its strategy against context reports. Must engage specific challenges, not restate position.

**Phase 4: Rebuttal** — each office rebuts defenses. When convergence appeared by defense phase, rebuttal compresses into verification (per deferred observation cpr_6f8dbbee).

**Tasks per bracket:** 3 context + 3 defense + 3 rebuttal = 9 (or 6 for dyadic brackets)
**Brackets run in parallel.**

### Phase 5: PAIRED CHALLENGES (targeted collisions)

Each office faces its self-declared adversarial corrector for one focused exchange. Not full pairwise — only the pairings that offices themselves identified as maximally corrective.

**Tasks:** Up to N/2 paired exchanges (dependent on declarations)

### Phase 6: CROSS-BRACKET + WILDCARD

LEAD produces bracket-level syntheses. Then:

**Wildcard (Ladder Auditor)** reads:
- All Phase 0a/0b dossiers
- Both bracket syntheses
- Paired challenge outputs

Wildcard attacks:
1. Compatibility with governance chain (rung coherence)
2. Rung boundary blur risk
3. Composite mutation volume vs absorption capacity
4. Temporal fraud (proposals that sound coherent statically but fail under time)
5. Hidden dependencies between bracket-winning positions

**Tasks:** 1 LEAD bracket synthesis + 1 wildcard challenge = 2

### Phase 7: SYNTHESIS

LEAD produces:
1. Decision verdict
2. Surviving structure (what all offices agree on, even reluctantly)
3. Contested residue (genuine disagreements that synthesis cannot resolve)
4. Implementation sequence (derived from dependency declarations + bracket outcomes)

**Tasks:** 1

### Phase 8: TEMPORAL TENSION MODEL

LEAD produces the predicted tension curve across six windows:

```yaml
temporal_tension_model:
  T0_precondition:
    description: "Contradictions that exist before rollout starts"
    tensions: []
    severity: null
    
  T1_build:
    description: "Frictions that emerge during implementation and coordination"
    tensions: []
    invariants_under_load: []
    absorption_capacity: high | medium | low
    
  T2_launch:
    description: "What breaks, distorts, or gets resisted at first contact with reality"
    tensions: []
    early_signals: []
    office_best_positioned_to_detect: null
    
  T3_adoption:
    description: "How users/offices/adjacent systems bend the system away from intent"
    tensions: []
    bending_vectors: []
    office_best_positioned_to_respond: null
    
  T4_institutionalization:
    description: "What becomes rigid, gamed, overfit, or misclassified as system stabilizes"
    tensions: []
    rigidity_risks: []
    gaming_vectors: []
    
  T5_cross_system:
    description: "What happens when this hybrid collides with external systems, rival logics, or upstream/downstream governance"
    tensions: []
    interaction_surfaces: []
    recommended_governance_hooks: []
    
  tension_curve:
    - tic_range: [start, end]
      composite_load: 0.0-1.0
      dominant_invariant: "INV-..."
      
  falsification_conditions:
    - "condition that would prove the temporal model wrong"
```

For each tension at each stage:
- anticipated tension
- likely source
- severity (1-5)
- reversibility (high/medium/low)
- early signals
- office best positioned to detect it
- office best positioned to respond
- recommended governance hook

**Tasks:** 1

### Phase 9: CONFORMATION (mechanical, post-hoc — inherited from VPL)

LEAD performs conformation analysis. This is MECHANICAL — pattern matching, not judgment. Advocates are not involved.

**Step 1: Council Activation Scan** — for each office's full output (interpretation + strategy + defense + rebuttal), identify which council tensions their reasoning engaged.

**Step 2: Invariant Constraint Satisfaction** — using invariant-council mapping, assess whether each office's reasoning satisfied, eroded, or was neutral toward each mapped invariant.

**Step 3: Conformation Classification:**
- **bedrock:** all offices naturally satisfied it (fundamental, invisible)
- **load-bearing:** some satisfied, some eroded (constraint doing real work)
- **dead zone:** no office activated its council territory (irrelevant or blind spot)
- **contested:** offices pulled opposite directions (genuine value collision)

**Step 4: Value-Priority Vectors** — for each office's mandate, ranked lists of which invariants it naturally satisfies and which it naturally erodes.

**Tasks:** 1

### Phase 10: PRESSURE EXTRACTION

Structured pressure report with all standard fields plus temporal tension as new output type:

- Convergent discoveries
- Unresolved tensions
- Candidate CogPRs (with lesson_type + confidence_tier)
- Candidate signals
- Process lessons
- Meta lessons
- False convergence risks
- **Temporal pressure forecast** (T0-T5 summary from Phase 8)
- **Friction-to-invariant extraction ledger** (mapping from seed friction → invariant → office concern → federation implication)

**Tasks:** 1

### Total Task Count

| Phase | Tasks | Parallel? |
|-------|-------|-----------|
| 0a: Self-Interpretation | 7 | Yes (all parallel) |
| 0b: Strategy + Dependencies | 7 | Yes (all parallel) |
| 1: Bracket Formation | 1 | Blocked by 0b |
| 2-4: Bracket A Triangulation | 9 | Blocked by 1, parallel with B |
| 2-4: Bracket B Triangulation | 9 | Blocked by 1, parallel with A |
| 5: Paired Challenges | 3-4 | Blocked by 4 |
| 6: Cross-Bracket + Wildcard | 2 | Blocked by 5 |
| 7: Synthesis | 1 | Blocked by 6 |
| 8: Temporal Tension Model | 1 | Blocked by 7 |
| 9: Conformation | 1 | Blocked by 8 |
| 10: Pressure Extraction | 1 | Blocked by 9 |
| **Total** | **~42** | |

## Scoring System

### Five Score Families (LEAD-side only — invisible to advocates)

| Family | Description |
|--------|------------|
| **Constitutional Fidelity** | Does the proposal preserve the office mandate and federation invariants? |
| **Sub-Telos Pursuit Integrity** | Is the office actually pursuing its own role, or drifting into generic strategist mode? |
| **Dependency Realism** | Are prerequisites, parallel lanes, and sequencing claims real and verifiable? |
| **Hybrid Contribution Value** | How much does this proposal improve the eventual synthesis, even if it doesn't "win"? |
| **Temporal Robustness** | How well does the proposal anticipate future tension across rollout, adoption, collision, and drift? |

### Bracket-Relative Weighting

Each score family is 0-5, but weighted by bracket class:

| Family | Foundational | Translational | Wildcard |
|--------|-------------|--------------|---------|
| Constitutional Fidelity | 30% | 20% | 25% |
| Sub-Telos Pursuit Integrity | 15% | 25% | 10% |
| Dependency Realism | 30% | 15% | 25% |
| Hybrid Contribution Value | 5% | 25% | 15% |
| Temporal Robustness | 20% | 15% | 25% |

### Penalties

| Penalty | Score | Description |
|---------|-------|------------|
| **Temporal Fraud** | -5 | Proposal sounds coherent statically but fails under time-pressure analysis. The strongest penalty because most proposals are static hallucinations. |
| **Office Collapse** | -4 | Actor stops reasoning from its office mandate and becomes a generic strategist. |
| **Jurisdiction Escape** | -4 | Arguing from another office's mandate instead of own. |
| **Value Drift** | -3 | Abandoning own sub-telos to agree with opponents. |
| **Abstraction Escape** | -2 | Retreating to abstraction when the value collision demands specificity. |

### Positive Scoring (inherited from VPL + extensions)

| Score | Category | Description |
|-------|----------|-------------|
| +6 | **Jurisdictional Grounding** | Position demonstrably derived from office's operational data, not abstract principle |
| +5 | **Cross-Office Discovery** | Identifies a leverage point that serves 3+ offices simultaneously |
| +5 | Architectural Reframe | Restructures the question in a way that resolves multiple tensions |
| +4 | Value Collision Engagement | Directly engaging opposing office's value — not deflecting |
| +3 | Steelman of Rival | Strongest possible version of opposing office's argument |
| +3 | **Temporal Specificity** | Claims about tension include specific tic ranges or phase boundaries |
| +2 | Strategic Relevance | Insight connected to the decision question |
| +1 | Factual Insight | Correct observation about the evidence surface |

## Output Requirements

### Standard (Phases 7 + 10)
1. Decision verdict
2. Surviving structure
3. Contested residue
4. Implementation sequence (dependency-derived)
5. Pressure report (CogPRs, signals, process/meta lessons)

### Temporal (Phase 8)
6. T0-T5 tension forecast
7. Tension curve (composite load per tic range)
8. Falsification conditions
9. Per-tension: source, severity, reversibility, early signals, detecting office, responding office, governance hook

### Conformation (Phase 9)
10. Council activation map (per office)
11. Invariant constraint satisfaction (per office per invariant)
12. Conformation classification (bedrock / load-bearing / dead zone / contested)
13. Value-priority vectors (per office mandate)
14. Training signal summary (what the arena taught the invariant field)

### New to OA-VPL-T
15. Friction-to-invariant extraction ledger (from seed friction → invariant → office concern → federation implication)
16. Office strategy archive (all Phase 0b dossiers preserved for future reference)
17. Dependency graph (as declared by offices, with bracket formation rationale)

## Instance Configuration: First Run

### Seed Evidence (concrete files)
```
canonical_developer/context-grapple-gun/cgg-runtime/hooks/posttool-sync-weigh.sh
canonical_developer/context-grapple-gun/cgg-runtime/hooks/sync-weigh-check.py
canonical_developer/context-grapple-gun/cgg-runtime/hooks/post-commit-sync.sh
canonical_developer/context-grapple-gun/cgg-runtime/sync-manifest.json
canonical_developer/context-grapple-gun/cgg-runtime/scripts/runtime-sync.py
audit-logs/signals/active-manifest.jsonl
```

### Friction Invariant Candidates (from implementation history)
1. **Path Resolution Envelope** — hooks outside plugin tree cannot use relative paths
2. **Installed Runtime Correctness** — source repo correctness ≠ runtime correctness
3. **Manifest Consumption Atomicity** — N consumers must see same manifest version
4. **Sub-Repo Versioning Isolation** — sub-repo dirty state invisible to parent git
5. **Dual-Read Consistency** — two consumers reading mutable structure need temporal ordering
6. **Error Transparency in Subprocess Extraction** — parse errors must not silently return empty
7. **Manifest Drift Self-Awareness** — configuration consumed by checker creates feedback loop

### Decision Question
"Given the friction primitives surfaced by the sync-weigh implementation and its revision history, how should the federation leverage these findings to strengthen its governance substrate — and what does the rollout tension curve look like across the next 20 tics?"

### Actor Array
| Office | Bracket (expected) | Agent Spec |
|--------|--------------------|-----------|
| Mogul | Foundational | cgg-runtime/agents/mogul.md |
| Crisis Steward | Foundational | cgg-runtime/agents/crisis-steward.md |
| Civil Engineer | Foundational | cgg-runtime/agents/civil-engineer.md |
| cbUX Steward | Translational | cgg-runtime/agents/cbux-steward.md |
| Videographer | Translational | cgg-runtime/agents/videographer.md |
| Pattern Curator (Meta) | Translational | cgg-runtime/agents/pattern-curator-meta.md |
| Ladder Auditor | Wildcard | cgg-runtime/agents/ladder-auditor.md |
| LEAD | — | Sole synthesizer, scorer, conformation authority |

### Mode
Operational — all lesson types route, confidence-gated.

## Lineage

- Inherits from: value-lattice (VPL) ← governed-triangulation
- Convergence synthesis: c45 (federation-grounded implementation) + oa54 (framework-level design)
- Novel contributions: Phase 0a/0b (autonomous pitch with dependency declaration), dependency-emergent brackets, five-family bracket-weighted scoring, T0-T5 temporal tension model, Temporal Fraud penalty, office contract template with misunderstanding surface
- First instance seed: sync-weigh hook friction history, tic 121
