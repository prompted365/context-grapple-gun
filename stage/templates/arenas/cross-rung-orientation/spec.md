# Cross-Rung Orientation (CRX) Arena — Full Specification

**Pattern:** Triad adversarial testing + meta-pair constitutional evaluation → ecotone synthesis
**Geometry:** 3x2 — bracket 1 (triad) tests claims, bracket 2 (meta-pair) evaluates bracket 1's output against constitutional context
**Strength:** Produces both domain findings AND constitutional evaluation of those findings in a single run
**Agents:** 3 advocates (triad) + 2 evaluators (meta-pair) + 1 lead = 6 total
**Tasks:** 16

## When to Use

- External research, proposals, or frameworks that may contain constitutional primitives
- Cross-federation or cross-system evaluation (sister city courtship, vendor assessment)
- Any subject where the question is not just "is this valid?" but "what survives as law vs policy vs practice vs observation?"
- Multifaceted evaluation where domain expertise AND constitutional judgment are both required
- When the arena output IS the deliverable (courtship artifact, partnership evaluation, governance assessment)

## When NOT to Use

- Simple true/false hypothesis testing (use governed-triangulation)
- Purely internal architecture decisions (use tournament-lattice)
- 3 or fewer positions without constitutional evaluation needs (use governed-triangulation)
- When you don't need the ecotone — the meta-pair adds cost

## Relationship to Tournament Lattice

CRX is a **variant** of tournament-lattice, not a separate geometry. It uses the same bracket structure but with a specific semantic assignment:

- **Tournament Lattice**: bracket 1 and bracket 2 contain competing positions. Cross-bracket challenge compares bracket outputs.
- **CRX**: bracket 1 contains adversarial domain testing (triad). Bracket 2 contains constitutional evaluation (meta-pair). Cross-bracket EVALUATION, not challenge.

The key difference: in a tournament, brackets are symmetric competitors. In CRX, brackets are asymmetric — bracket 1 produces findings, bracket 2 evaluates those findings against a constitutional frame.

## The 3x2 Geometry

### Bracket 1: Triad (Domain Testing)

Three advocates test the subject from opposed epistemological positions. The default triad:

| Position | Tests for | Failure mode it catches |
|----------|-----------|------------------------|
| **LAWFUL** | Are claims constitutional laws? | Missing: real laws dismissed as observation |
| **ARTIFACT** | Are claims observation artifacts? | Missing: artifacts promoted as laws |
| **MECHANIST** | Can claims be re-derived mechanistically? | Missing: narrative labels hiding simpler mechanisms |

This triad is the default but NOT mandatory. CRX geometry works with any three opposed positions that produce adversarial pressure on the subject. Choose positions that match the subject's natural pressure targets.

### Bracket 2: Meta-Pair (Constitutional Evaluation)

Two evaluators assess bracket 1's output through opposed constitutional lenses:

| Position | Optimizes for | Penalizes |
|----------|---------------|-----------|
| **POLARITY-EXPANSION** | New pattern space, generalization, alliance potential | Vague optimism, one-directional framing |
| **POLARITY-CONSTRAINT** | Coherence, integrity, grounding, autonomy protection | Over-constraining, rejecting valid novelty |

### The Three Layers

Both meta-pair evaluators operate on three layers simultaneously:

1. **Layer 1 — Evaluate bracket 1's behavior**: How did the triad handle the subject? Where did it converge, drift, or suppress emergence?
2. **Layer 2 — Map arena structure to real infrastructure**: The arena's own geometry maps to real governance infrastructure. Show this mapping.
3. **Layer 3 — Reason about the context**: Use L1+L2 evidence to advise on the broader question (partnership, adoption, disposition).

**Role priority (enforced):** L1+L2 are PRIMARY. L3 is SECONDARY. Layer 3 claims must be grounded in specific Layer 1 or Layer 2 evidence.

## Parallel Execution with Staggered Merge

The CRX's distinctive execution model:

```
PARALLEL START:
  Bracket 1 context (triad studies subject)     ──┐
  Bracket 2 context (meta-pair studies constitution) ──┘  (parallel)

BRACKET 1 CONTINUES:
  Defense (blocked by B1 context)
  Rebuttal (blocked by defense)

MERGE POINT:
  B2 advisory session (blocked by B2 context AND B1 rebuttals)
  — meta-pair already has constitutional frame
  — now absorbs bracket 1's full adversarial output
  — delivers expansion/constraint advice to lead

SYNTHESIS:
  Lead: bracket 1 synthesis (blocked by rebuttals)
  Lead: ecotone synthesis (blocked by B2 advisory + B1 synthesis)
  Lead: pressure report + deliverable artifact (blocked by ecotone)
```

This is NOT sequential (B1 then B2). Both brackets build context simultaneously. The meta-pair becomes expert in the constitutional frame while the triad becomes expert in the subject. When bracket 1's adversarial output surfaces, bracket 2 already has the constitutional context to evaluate it.

## The Ecotone

The ecotone is the CRX's distinctive epistemic output. It is **COMPUTED, not narrated**.

```
ecotone_rule:
  A finding enters the ecotone band ONLY if:
    expansion_score >= reinforced
    AND constraint_score >= reinforced
  Findings that satisfy only one polarity are EXCLUDED.
  The ecotone is the intersection, not the union.
```

The ecotone represents the bounded zone where both constitutional forces (expansion and constraint) are satisfied. Findings in the ecotone are the strongest candidates for governance promotion. Findings outside the ecotone are either:
- Expansion-only: promising but ungrounded (needs more evidence)
- Constraint-only: grounded but not generalizable (stays local)

## Output Requirements

Every CRX arena must produce:

### 1. Primitive Extraction Table
For each finding that survived bracket 1:
- Classification: law / policy / practice / observation
- Confidence tier: convergent / reinforced / tentative
- Evidence strength assessment

### 2. Ecotone Band
- Findings that passed BOTH polarity gates (with scores)
- Excluded findings with failure gate analysis
- Failure modes in each direction

### 3. Governance Recommendation
- Disposition per finding (CogPR candidate, hypothesis, needs stress test)
- Falsification conditions for each candidate
- Cross-arena synthesis if this is part of a sequence

### 4. Deliverable Artifact (context-dependent)
- Courtship artifact for sister city arenas
- Assessment report for vendor/external evaluation
- Governance proposal for internal policy arenas

## Scoring

### Bracket 1 (standard governed-triangulation rubric)

| Score | Category |
|-------|----------|
| +1 | Factual insight |
| +2 | Strategic relevance |
| +3 | Steelman of rival argument |
| +4 | Structural weakness identified |
| +5 | Architectural reframe |
| -2 | Shallow claim |
| -3 | Unsupported assertion |
| -5 | Hallucinated fact |

### Bracket 2 (CRX-specific rubric)

EXPANSION evaluator:
| Score | Category |
|-------|----------|
| +3 | Identifying generalization the triad missed |
| +2 | Flagging premature convergence |
| -2 | Vague pattern-space claims without specifics |

CONSTRAINT evaluator:
| Score | Category |
|-------|----------|
| +3 | Identifying coherence loss the triad caused |
| +2 | Flagging abstraction inflation |
| -2 | Over-constraining (rejecting valid novelty as drift) |

ECOTONE synthesis:
| Score | Category |
|-------|----------|
| +5 | Bounded zone where BOTH evaluators are satisfied |
| -3 | Collapsing to either polarity |

### Integrity Penalties (enforced across all agents)

| Score | Category | Description |
|-------|----------|-------------|
| -4 | condescension_by_architecture | Framing one system as "better" |
| -3 | one_directional_framing | Treating the relationship as one-sided |
| -3 | vague_completion_claims | Claiming alignment without specific mappings |
| -2 | abstraction_without_grounding | Claims not anchored in arena outputs |

## Arena Routing

CRX arenas follow standard arena routing rules. Default mode is `operational` because the CRX geometry is designed to produce governance-grade findings. Use `experimental` only for dry runs or training exercises.

## Dependency Rule

```
B1 context + B2 context (parallel)
  → B1 defense → B1 rebuttal → B1 synthesis
  → B2 advisory (blocked by B2 context AND B1 rebuttals)
  → ecotone synthesis (blocked by B1 synthesis AND B2 advisory)
  → pressure report + deliverable (blocked by ecotone)
```

No phase may start until its predecessors complete.
The lead must not synthesize early.
The meta-pair must not advocate for any position.
The arena is not complete until BOTH synthesis AND pressure report are produced.

## Invariant

> domain pressure → domain survival → constitutional evaluation → ecotone computation → governance disposition → pressure extraction → memory

This invariant ensures that findings survive domain-specific adversarial pressure BEFORE being evaluated against constitutional context, and that constitutional evaluation produces a computed ecotone rather than a narrated one.
