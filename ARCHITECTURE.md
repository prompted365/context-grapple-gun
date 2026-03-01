# Architecture & Design Rationale

Context Grapple Gun (CGG) is a **human-gated self-evolving agent operating system** that turns day-to-day development friction into durable improvements *without poisoning long-term memory with raw logs*.

It is best understood as three coupled systems:
1. **A token-aware session execution loop** (keeps the agent sharp and cheap)
2. **A promotion pipeline for knowledge** (keeps memory high-signal)
3. **A bidirectional projection mechanism** (lets abstract truths become concrete code again)

## 1. Core Objects (The Ephemeral vs. The Durable)

Most agent "memory" systems fail because they confuse *storage* with *knowledge*, and *recall* with *governance*. CGG prevents "global memory" from becoming a trash heap by enforcing a five-tier taxonomy.

### Tier 1: Local Observations (Raw Discoveries)
These are bottom-of-the-ladder artifacts:
- "This endpoint returns `null` sometimes."
- "This Rust trait bound keeps failing in this crate."
- "This UI bug only happens when feature flag X is on."

These are true, but too contextual to store globally.

### Tier 2: Session Knowledge (Contextual Patterns)
Within an active session, the agent accumulates temporary "working theories" about the repo structure, task constraints, and current failure modes. This is useful now, but dangerous to persist as-is.

### Tier 3: CogPRs (The Promotion Buffer)
A Cognitive Pull Request (CogPR) is the unit of proposed evolution. It strips variables (file paths, one-off IDs), extracts the invariant lesson, and proposes a target scope. This is the critical "signal hygiene" layer.

### Tier 4: Project Memory (Reusable Rules)
Lessons proven useful multiple times in one repository. They are tied to a specific stack (e.g., "In this Rust workspace, errors must implement `thiserror::Error`") but are not yet universal.

### Tier 5: Global Memory (Universal Invariants)
The slowest-changing layer. A global primitive stays true across projects, stacks, and sessions (e.g., "Defensive parsing at trust boundaries").

## 2. The 100k Token Cycle (Performance Physics)

Long agent sessions produce three predictable degradations:
1. **Instruction drift** (the agent starts contradicting earlier constraints)
2. **Recall failures** (earlier context becomes "soft")
3. **Cost blowups** (you pay more for worse behavior)

CGG treats the context window as a resource that must be rotated. You do not "power through" at 120k+ tokens. You end the epoch on purpose.

The `/cadence-downbeat` command is the epoch boundary primitive. The downbeat emits a canonical tic — the cross-system timestamp primitive that unifies syncopated cadences. It converts "session entropy" into "structured evolution candidates" by:
1. Stopping active work before degradation gets severe.
2. Bundling pending CogPR proposals.
3. Flushing the bloated session context.
4. Producing a clean handoff plan for the next session.
5. Kicking off the background evaluator.

## 3. Plan Mode Hijacking (The Governance Gate)

CGG relies on repurposing existing agent UI patterns for novel architectural uses. Specifically, it hijacks "Plan Mode" (typically used for code implementation planning) to serve as a constitutional governance gate.

Plan mode appears at three different points in the CGG pipeline, each doing a different job:
1. **The Handoff Writer:** At the epoch boundary, Plan Mode writes the context-exit handoff payload.
2. **The Review Surface:** When running `/grapple`, Plan Mode presents CogPR proposals to the human in a UI that supports approve/reject/edit actions.
3. **The Scope Arbitrator:** It forces the human to decide if a lesson belongs at the Project or Global tier.

What the human approves are laws, not tactics. You approve new primitives, scope promotions, and behavioral constraints. You do not approve one-off code fixes. This makes the human an editor of the agent's constitution, not a micromanager of its thoughts.

## 4. The Ripple Assessor (Asynchronous Evolution)

The assessor keeps the main session loop fast. Instead of asking the active agent to both do the work and deeply evaluate every improvement proposal against global invariants, CGG splits responsibilities. The active session produces work and emits signals. The background assessor evaluates those signals with more time, a clean context, and less noise.

## 5. Tics, Zones, and System Conformation

### The clock problem

Different systems operate at different cadences. A CLI agent might downbeat every 100k tokens. An autonomous superintendent might downbeat at each monologue boundary. A cron job fires on a fixed schedule. None of these share a rhythm, and wall-clock timestamps alone cannot answer the question: "In what order did things happen across these systems?"

The **tic** solves this. Every epoch boundary emits a tic record containing both an ISO-8601 timestamp and a monotonic sequence counter at two scopes (project and global). The timestamp tells you *when*. The counter tells you *in what order*. Together they provide:

- **Temporal auditability**: reconstruct the system's state at any point in time.
- **Sequential auditability**: reconstruct the system's state at any point in the sequence, regardless of clock skew or cadence differences.
- **Cross-cadence mapping**: relate events from systems with incompatible rhythms through a shared total ordering.

Tics are not signals. They do not accrue volume, expire via TTL, trigger warrants, or propagate through the acoustic model. They are the clock. They are stored separately from the signal manifold (`audit-logs/tics/`, not `audit-logs/signals/`).

### Jurisdictional scoping

The acoustic model (Section 2) routes signals based on directory distance and frequency bands. But directory distance is a filesystem primitive — it maps poorly to organizational boundaries, multi-repo deployments, or geographically distributed teams.

**Tic-zones** add jurisdictional scoping. A `.ticzone` file at a directory root defines a named acoustic region with explicit path inclusion, timezone, optional coordinates, active bands, and a muffling constant. Zones answer the question: "Which agents can hear which signals?" through configuration, not convention.

Zone nesting enables federation. A subdirectory can define a nested zone that inherits the parent's properties but overrides specific bands or muffling rates. Cross-zone signal propagation attenuates at double the intra-zone rate — inter-jurisdictional communication is possible but expensive, which is structurally correct for compartmentalized environments.

### System conformation

At any tic boundary, the total state of a CGG-governed system forms a **conformation**: the set of active signals, pending CogPRs, minted warrants, drift measurements, zone membership, and rules in force at each scope tier.

Between tic N and tic N+1, environmental pressure (work, friction, discovery) causes the conformation to shift. Small shifts: a local lesson captured, a signal volume incremented. Fold events: a warrant mints from a harmonic triad, or a global rule promotion reshapes downstream behavior.

The tic sequence makes conformations replayable and diffable. You can reconstruct the system's shape at tic 42, compare it to tic 41, and trace exactly which events caused the transition. This is the same audit primitive at every level of the stack:

| Reader | What they see |
|--------|--------------|
| Engineer | "What changed between sessions?" |
| Compliance officer | "What rules were in force when this decision was made?" |
| System itself | "What shape am I in?" |

The structural analogy is deliberate: the tic sequence is the primary structure. Signals, warrants, and CogPRs are the side chains. Bands are charge groups. Acoustic routing is the solvent environment. The conformation at any given tic is the folded shape of the system under the accumulated pressure of its entire history.

This is the terminal abstraction rung. Everything below it — files, signals, rules, zones — is mechanism. The conformation is what those mechanisms produce: a shape, inspectable at any point in the sequence, that captures everything the system knows and everything it's doing about what it knows.

## 6. Scaling Ceiling

CGG's governance lifecycle is complete for individuals and small teams. The flat-file primitives — JSONL signal stores, CLAUDE.md rule tiers, append-only audit trails — are fast, portable, and auditable by default.

But there is a ceiling. When the signal store grows past a few hundred entries, dedup-by-latest-entry-per-ID becomes a linear scan. When the lesson corpus spans dozens of CLAUDE.md files, finding the right lesson for the current context requires semantic understanding — grep matches keywords, not meaning. When epitaphs accumulate, the system needs to know which historical failure mode is closest to the current system shape, not just which one has the most string overlap.

This is where CGG stops and deeper substrate begins:
- Embedding-based semantic recall (vector similarity, not keyword matching)
- Graph topology for relational memory (edges between related concepts, not flat lists)
- Expression gating across timescales (methylation — some lessons are dormant until the system re-enters a specific failure shape)
- Conformation-aware retrieval (match the system's current shape to historical failure modes)

These require infrastructure — vector databases, embedding models, graph engines — that does not fit in a CLI framework. CGG gives you the governance lifecycle. The substrate that makes it scale at that level is a different engineering problem.

The honest boundary: **CGG is the governance lifecycle. Ubiquity is the substrate that makes governance meaningful at scale.**

### When CGG stops being enough

You'll feel the ceiling when:
- Signals exceed a few hundred entries and dedup becomes slow
- Lessons span many files and grep stops finding the right thing
- You need "closest historical failure mode," not "keyword overlap"
- Rule stores grow monotonically and every session loads stale context

### Ubiquity layers that extend CGG

| Layer | What it does | Why flat files can't |
|-------|-------------|---------------------|
| Semantic Recall | Embedding-based vector search across lessons | Grep matches keywords, not meaning |
| Graph Topology | Relational edges between concepts, not flat lists | JSONL has no structure between entries |
| Expression Gating | Methylation — lessons go dormant until the system re-enters a failure shape | Flat files are always fully loaded |
| Conformation-Aware Retrieval | Match "system shape now" to "system shape at time of failure" | No mechanism to fingerprint system state |

CGG is the governance lifecycle. Ubiquity layers compose on top — same signals, same tics, same human gates. The flat-file primitives become the audit trail beneath the substrate.

### Measuring CGG's impact

Three numbers that separate compounding governance from configuration drift:

1. **Repeat-mistake rate** — How often does the same wrong-approach pattern recur after a lesson is captured? Track by comparing CogPR failure codes against subsequent session friction. A declining rate means lessons are landing.

2. **Time-to-resume** — How long does a new session take to reach productive work after a handoff? Measure from session start to first meaningful tool call. Effective handoffs compress this. Poor handoffs produce "let me re-read everything" patterns.

3. **Promotion ROI** — How often does a promoted rule prevent a future incident? Track by correlating promoted CogPR failure codes with subsequent signal manifold activity. A promoted rule that never fires again has infinite ROI. One that keeps generating the same signal hasn't landed.

<!-- --agnostic-candidate
  lesson: "System conformation — the total state at any tic boundary (signals, CogPRs, warrants, drift, zone, rules) — is the terminal abstraction rung. The tic sequence is the primary structure that makes conformations replayable. Mechanisms produce shape; shape is what you audit."
  source_date: "2026-02-24"
  source: "vendor/context-grapple-gun/ARCHITECTURE.md:103"
  band: "COGNITIVE"
  motivation_layer: "COGNITIVE"
  subsystem: "cgg"
  recommended_scopes:
    - "CLAUDE.md"
  rationale: "The conformation concept completes the CGG abstraction stack. It connects the file-level primitives to the fold-level audit capability. Any system using tics needs to understand that the tic sequence enables conformation replay — this is the 'why' behind tic separation."
  review_hints: "Validate after conformation diffing is implemented. The concept is architecturally sound but tooling doesn't exist yet. Keep at project scope until replay tooling proves the concept."
  civilization_prior_refs: []
  status: "promoted"
  promoted_at: "2026-02-25"
  promoted_to:
    - "CLAUDE.md (Tic section — conformation terminal abstraction note)"
  grapple_docket: "2026-02-25"
-->
