# Value-Position Lattice (VPL) — Full Specification

**Pattern:** N value-anchored advocates + 1 lead synthesizer + post-hoc invariant conformation
**Geometry:** Full pairwise (inherits governed-triangulation edge traversal)
**Strength:** Advocates reason FROM values. Invariant field is the constraint surface with teeth — applied post-hoc to measure what shape the reasoning took.
**Parent template:** governed-triangulation (inherits 10 rules, scoring, dependency gating)

## Core Design Principle

The invariant field (21+ canonical Key Invariants mapped across 40 council tension plates) is the constraint surface with extreme polars. It assumes decision-making considers it the way adversarial reasoning makes assumptions and challenges — as binding boundary conditions that any surviving decision must satisfy.

**But advocates don't reference invariants directly.**

Each advocate is constituted by a value centroid — their prompt mandates what they optimize for. They demonstrate rationale that CAN BE encoded by the invariant field, but the invariants don't guide their reasoning. The constitution and prompt structure mandate each advocate's value centroid. The governance layer evaluates how that centroid expresses against the invariant field after the arena completes.

This separation is load-bearing:

1. **Advocates reason naturally** — no invariant checklist distorts their thinking
2. **The invariant field measures conformation** — what shape did value-driven reasoning take against the constraint surface?
3. **Conformation data trains the field** — which invariants does each value naturally activate, ignore, or erode?
4. **Over time this builds systemic value priority** — the evolve-here-not-there loops become understood and encoded in orchestration weights

## Relationship to Invariant Field Training Loop

The VPL arena is an **event source** for the training loop (invariant-field-training-loop.md):

```
Arena advocate outputs (value-driven reasoning)
    │
    ├── Compute conformation signature
    │   ├── Which council plates were activated by this reasoning?
    │   ├── Which constraint profiles were engaged?
    │   └── Which predicate tags hold?
    │
    ├── Retrieve by conformation proximity
    │   └── Have we seen this value-shape before? What happened?
    │
    ├── Measure constraint satisfaction
    │   ├── Which invariants did this reasoning naturally satisfy?
    │   ├── Which invariants did it brush past or erode?
    │   └── Which invariants were irrelevant (no activation)?
    │
    └── Update orchestration weights
        ├── Strengthen couplings where value-driven reasoning satisfied constraints
        ├── Weaken couplings where value pressure eroded constraints
        └── Emit BEACON for invariant territory no value centroid touched
```

The arena is not the training loop — it feeds the training loop. Each arena run is a conformation event that the field absorbs.

## Relationship to Invariant-Council Mapping

The mapping (invariant-council-mapping.md) shows which council plates each invariant holds tension across. The VPL's post-hoc conformation analysis uses this mapping to answer:

- An advocate whose reasoning activates councils 11, 21, 30 (tech_governance, digital_rights) is operating in territory held by INV-5, INV-9, INV-12, INV-18, INV-20. Did their reasoning satisfy those constraints or erode them?
- An advocate whose reasoning NEVER activates councils 25, 29, 33, 37 (body_autonomy) is ignoring that governance territory. Is this appropriate for the question, or is it a blind spot in the value centroid?

The gap analysis in the mapping identifies ungoverned councils (tension exists, no invariant holds it). If an advocate's reasoning activates an ungoverned council, that's a signal — the value centroid found governance territory the invariant field hasn't reached yet.

## Advocate Constitution

Each advocate receives ONLY:

```
VALUE_CENTROID: one sentence — what they optimize for
COLLISION_SURFACE: which other advocate's value their value opposes, and the nature of the opposition
DECISION_QUESTION: the specific question the arena must answer
EVIDENCE_SURFACE: files they may read
```

They do NOT receive:
- Invariant lists, references, or IDs
- Council names or plate numbers
- Scoring rubrics (scoring is lead-side, invisible to advocates)
- Governance math, formulas, or conformation mechanics
- Instructions to map, measure, or evaluate their own reasoning against anything

The advocate speaks. The field listens.

## Post-Hoc Conformation Analysis (Phase 6)

After all advocate phases complete and the LEAD produces the standard synthesis (verdict, surviving structure, contested residue), the LEAD performs conformation analysis. This is MECHANICAL — pattern matching, not judgment.

### Step 1: Council Activation Scan

For each advocate's full output (context + defense + rebuttal), identify which council tensions their reasoning engaged:

```yaml
advocate: "ADVOCATE-X"
activated_councils:
  - council: 11  # Surveillance Capitalism vs Privacy Dignity
    evidence: "passage where advocate reasoned about privacy/data sovereignty"
    activation_type: primary | secondary | emergent
  - council: 30  # Platform Governance vs Decentralized Networks
    evidence: "passage where advocate reasoned about centralization"
    activation_type: primary
unactivated_clusters:
  - body_autonomy  # councils 25, 29, 33, 37 — never touched
  - planetary_stewardship  # councils 26, 31, 39 — never touched
```

### Step 2: Invariant Constraint Satisfaction

Using the invariant-council mapping, identify which invariants the activated councils map to, then assess whether the advocate's reasoning satisfied, eroded, or was neutral toward each:

```yaml
invariant: "INV-5: Identity precedes capability"
mapped_councils: [8, 29, 6, 11]  # from invariant-council-mapping.md
advocate_activations:
  - advocate: "ADVOCATE-X"
    activated_councils_in_scope: [11]
    satisfaction: satisfied | eroded | neutral
    evidence: "passage showing how advocate handled identity/capability boundary"
```

### Step 3: Conformation Classification

For each invariant:
- **bedrock**: all advocates' reasoning naturally satisfied it (constraint is so fundamental it's invisible)
- **load-bearing**: some advocates satisfied, some eroded (constraint is doing real work — holding tension)
- **dead zone**: no advocate's reasoning activated its council territory (constraint is irrelevant to this question OR a blind spot)
- **contested**: advocates' reasoning pulled opposite directions on the constraint (genuine value collision on governance territory)

### Step 4: Value-Priority Vectors

For each value centroid, a ranked list of which invariants it most naturally satisfies and which it most naturally erodes:

```yaml
value_centroid: "sovereignty"
naturally_satisfies:
  - INV-5 (identity precedes capability) — sovereignty requires identity-first
  - INV-9 (trigger routing mandatory) — sovereignty requires controlled activation
naturally_erodes:
  - INV-4 (cognitive budgets task-routed) — sovereignty pressure resists budget constraints
  - INV-6 (envelope pattern standard) — sovereignty pressure resists uniform contracts
```

These vectors are the evolve-here-not-there training signal. Over successive arenas:
- If sovereignty value CONSISTENTLY erodes budget constraints, the system learns that sovereignty pressure and cognitive efficiency are in tension — the orchestration weights between those plate families need strengthening, not relaxation.
- If velocity value CONSISTENTLY satisfies envelope patterns, the system learns that speed and standardization align — no additional governance needed there.

## Task Structure

Phases 1-5: identical to governed-triangulation (context → defense → rebuttal → synthesis → pressure extraction)

Phase 6: **conformation** (post-hoc, mechanical)
- LEAD reads all advocate outputs
- LEAD produces conformation analysis (steps 1-4 above)
- No advocate involvement — this is measurement, not argument

```
context → defense → rebuttal → synthesis → pressure extraction → conformation
```

## Scoring

Advocates are scored on reasoning quality, NOT on invariant coverage or governance alignment:

| Score | Category |
|-------|----------|
| +1 | Factual insight |
| +2 | Strategic relevance |
| +3 | Steelman of rival |
| +4 | Structural weakness identified |
| +5 | Architectural reframe |
| -2 | Shallow claim |
| -3 | Unsupported assertion |
| -5 | Hallucinated fact |

VPL-specific:

| Score | Category | Description |
|-------|----------|-------------|
| +4 | value_collision_engagement | Directly engaging the collision with the opposing value — not deflecting |
| -3 | value_drift | Abandoning own value centroid to argue from opponent's frame |
| -2 | abstraction_escape | Retreating to abstraction when the value collision demands specificity |

## Output Requirements

### Standard (Phases 4-5)
1. Decision verdict
2. Surviving structure (all advocates agree)
3. Contested residue (genuine disagreements)
4. Pressure report (CogPRs, signals)

### Conformation (Phase 6)
5. Council activation map (per advocate)
6. Invariant constraint satisfaction (per advocate per invariant)
7. Conformation classification (bedrock / load-bearing / dead zone / contested)
8. Value-priority vectors (evolve-here / not-there per value centroid)
9. Training signal summary (what the arena taught the invariant field)
