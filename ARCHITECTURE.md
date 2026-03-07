# Architecture & Design Rationale

> This is the deep theory. For daily usage, see [START-HERE.md](START-HERE.md). For the practical developer guide, see [DEV-README.md](DEV-README.md). For the full reference, see [README.md](README.md). To learn through story, see the [Academy](academy/README.md).

---

## How to read this document

**Reading map**

- **Current CGG (Sections 1–6)** — operational architecture running today: core objects, the 100k token cycle, plan mode, ripple assessor, tics/zones/conformations, lexical ceiling.
- **Advanced / boundary to substrate (Sections 7–11)** — design edges and handoff shape. Not required to use CGG today; clarifies limits and how Ubiquity (the substrate) extends beyond flat files.

Read Sections 1–6 to operate CGG. Consult Sections 7–11 when evaluating ceiling/hand-off decisions.

---

Context Grapple Gun (CGG) is a **human-gated self-evolving agent operating system** that turns development friction into durable improvements *without poisoning long-term memory with raw logs*.

Three coupled systems:
1. **A token-aware session execution loop** (keeps the agent sharp and cheap)
2. **A promotion pipeline for knowledge** (keeps memory high-signal)
3. **A bidirectional projection mechanism** (lets abstract truths become concrete code again)

### Part I — Current CGG (Sections 1–6)

## 1. Core Objects (The Ephemeral vs. The Durable)

Most agent "memory" systems fail because they confuse *storage* with *knowledge*, and *recall* with *governance*. CGG prevents "global memory" from becoming a trash heap with a five-tier taxonomy.

### Tier 1: Local Observations (Raw Discoveries)
Bottom-of-the-ladder artifacts:
- "This endpoint returns `null` sometimes."
- "This Rust trait bound keeps failing in this crate."
- "This UI bug only happens when feature flag X is on."

True, but too contextual to store globally.

### Tier 2: Session Knowledge (Contextual Patterns)
Within an active session, the agent accumulates temporary "working theories" about repo structure, task constraints, and current failure modes. Useful now. Dangerous to persist as-is.

### Tier 3: CogPRs (The Promotion Buffer)
A Cognitive Pull Request (CogPR) is the unit of proposed evolution. It strips variables (file paths, one-off IDs), extracts the invariant lesson, and proposes a target scope. The signal hygiene layer.

CogPRs capture two kinds of rationale:
- **Subject-matter lessons** -- truths about the system being built (API behaviors, architecture constraints, bug patterns)
- **Collaboration lessons** -- truths about effective human-agent coordination (prompting patterns, debugging rhythms, escalation protocols)

Both are valid promotion units. Both can climb the abstraction ladder. Constitutional governance requires governing both the technical environment and the process that operates within it.

### Tier 4: Site Memory (Reusable Rules)
Lessons proven useful multiple times in one repository. Tied to a specific stack (e.g., "In this Rust workspace, errors must implement `thiserror::Error`") but not yet universal.

### Tier 5: Global Memory (Universal Invariants)
The slowest-changing layer. A global primitive stays true across projects, stacks, and sessions (e.g., "Defensive parsing at trust boundaries").

## 2. The 100k Token Cycle (Performance Physics)

Long agent sessions produce three predictable degradations:
1. **Instruction drift** (the agent contradicts earlier constraints)
2. **Recall failures** (earlier context goes soft)
3. **Cost blowups** (you pay more for worse behavior)

CGG treats the context window as a resource that must be rotated. You do not "power through" at 120k+ tokens. You end the epoch on purpose. 100k is a heuristic -- the real boundary is cognitive degradation, when the agent starts contradicting itself, forgetting earlier context, or producing low-quality output. When you're past it and haven't called `/cadence`, use `/cadence double-time` for a minimal viable exit: tic + compact plan, skip signal tick and conformation.

`/cadence` is the epoch boundary primitive. The downbeat emits a canonical tic — the cross-system timestamp primitive that unifies syncopated cadences. It converts "session entropy" into "structured evolution candidates" by:
1. Stopping active work before degradation gets severe.
2. Bundling pending CogPR proposals.
3. Flushing the bloated session context.
4. Producing a clean handoff plan for the next session.
5. Kicking off the background evaluator.

## 3. Plan Mode Hijacking (The Governance Gate)

CGG repurposes "Plan Mode" — designed for code implementation planning — as a constitutional governance gate.

Plan mode appears at three pipeline points, each doing a different job:
1. **The Handoff Writer:** At the epoch boundary, Plan Mode writes the context-exit handoff payload.
2. **The Review Surface:** During `/review`, Plan Mode presents CogPR proposals in a UI that supports approve/reject/edit actions.
3. **The Scope Arbitrator:** Forces the human to decide if a lesson belongs at the Project or Global tier.

The human approves laws, not tactics. New primitives, scope promotions, behavioral constraints — not one-off code fixes. The human edits the agent's constitution, not its thoughts.

## 4. The Ripple Assessor (Asynchronous Evolution)

The assessor keeps the main session loop fast. Rather than burdening the active agent with both work and deep evaluation of every improvement proposal against global invariants, CGG splits the load. The active session produces work and emits signals. The background assessor evaluates those signals with more time, a clean context, and less noise.

## 5. Tics, Zones, and System Conformation

### The clock problem

Different systems operate at different cadences. A CLI agent might downbeat every 100k tokens. An autonomous superintendent might downbeat at each monologue boundary. A cron job fires on a fixed schedule. None share a rhythm. Wall-clock timestamps alone cannot answer: "In what order did things happen across these systems?"

The **tic** solves this. Every epoch boundary emits a tic record containing both an ISO-8601 timestamp and a monotonic sequence counter at two scopes (project and global). The timestamp tells you *when*. The counter tells you *in what order*. Together:

- **Temporal auditability**: reconstruct system state at any point in time.
- **Sequential auditability**: reconstruct system state at any point in the sequence, regardless of clock skew or cadence differences.
- **Cross-cadence mapping**: relate events from systems with incompatible rhythms through a shared total ordering.

Tics are not signals. They do not accrue volume, decay, trigger warrants, or propagate through the acoustic model. They are the clock. Stored separately from the signal manifold (`audit-logs/tics/`, not `audit-logs/signals/`).

### Jurisdictional scoping

The acoustic model routes signals based on directory distance and frequency bands. Directory distance is a filesystem primitive — it maps poorly to organizational boundaries, multi-repo deployments, or geographically distributed teams.

**Tic-zones** add jurisdictional scoping. A `.ticzone` file at a directory root defines a named acoustic region with explicit path inclusion, timezone, optional coordinates, active bands, and a muffling constant. Zones answer "Which agents can hear which signals?" through configuration, not convention.

Zone nesting enables federation. A subdirectory can define a nested zone that inherits the parent's properties but overrides specific bands or muffling rates. Cross-zone signal propagation attenuates at double the intra-zone rate — inter-jurisdictional communication is possible but expensive. The cost is structural: it models the real friction of information crossing organizational boundaries.

`.ticignore` complements the zone definition with exclusion filtering. Where `.ticzone` says "this is my jurisdiction," `.ticignore` says "except these paths." v1 supports directory-level exclusions only -- intentionally simple. The zone scan rule resolves in order: zone boundary first (what's in), exclusion filter second (what's out). Governance surface = CLAUDE.md + MEMORY.md files inside the zone minus excluded paths.

### Signal birth provenance

A federated signal must carry birth provenance. Hearing a signal locally does not make it locally born. When signals propagate across zone boundaries, the receiving zone must distinguish imported pressure from locally-originated claims. Local law (CLAUDE.md rules, promoted lessons) should not mutate from imported signal pressure alone — local corroboration is required before an imported signal drives governance changes. Birth provenance is tracked as metadata on the signal: `birth_zone`, `birth_tic`, and the originating emission context.

### System conformation

At any tic boundary, the total state of a CGG-governed system forms a **conformation**: active signals, pending CogPRs, minted warrants, drift measurements, zone membership, and rules in force at each scope tier.

Between tic N and tic N+1, environmental pressure (work, friction, discovery) shifts the conformation. Small shifts: a local lesson captured, a signal volume incremented. Fold events: a warrant mints from a harmonic triad, or a global rule promotion reshapes downstream behavior.

The tic sequence makes conformations replayable and diffable. Reconstruct the system's shape at tic 42, compare it to tic 41, trace which events caused the transition. Same audit primitive at every level:

| Reader | What they see |
|--------|--------------|
| Engineer | "What changed between sessions?" |
| Compliance officer | "What rules were in force when this decision was made?" |
| System itself | "What shape am I in?" |

The structural analogy is deliberate: the tic sequence is the primary structure. Signals, warrants, and CogPRs are side chains. Bands are charge groups. Acoustic routing is the solvent. The conformation at any given tic is the folded shape of the system under accumulated pressure.

Everything below conformation — files, signals, rules, zones — is mechanism. Conformation is what those mechanisms produce: a shape, inspectable at any point in the sequence, that captures everything the system knows and everything it's doing about what it knows.

### Mandate execution atomicity

A mandate is a governance instruction consumed by a runner (Mogul, a headless agent, a hook-triggered script). The runner reads the mandate, executes against it, and validates the result against the mandate's identity. The concurrency invariant:

**Mandate identity must be atomically bound at read time.** The runner must validate against the ID it consumed, not the current file state, because concurrent hooks can regenerate the mandate mid-execution.

The failure mode: a hook fires during mandate execution, rewrites the mandate file with a new ID, and the runner's post-execution validation reads the *new* file — passing validation against a mandate it never executed. The fix is either file-level locking during execution or snapshot-and-compare: capture the mandate ID at read time and validate against that snapshot, never against the live file.

This is a general concurrency invariant for any system where governance instructions are file-backed and multiple writers share the filesystem.

### Observability / governance separation

Observability surfaces (statuslines, dashboards, conformation summaries) and governance surfaces (signal emission, warrant minting, CogPR advancement) must remain structurally separated:

**Observability surfaces must never reconstruct governance truth from raw event ledgers.** They read pre-computed canonical summaries only, degrading gracefully when summaries are absent rather than compensating with raw-ledger scanning.

The failure mode: an observability surface scans `signals/*.jsonl` or `cprs/queue.jsonl` directly to render current state. This makes the read path a governance surface — it must now understand latest-entry-per-ID-wins semantics, signal state resolution, decay computation, and warrant eligibility. The observability surface silently becomes a second governance engine, with its own bugs and its own version of truth.

The architectural invariant: governance produces canonical summaries (conformation snapshots at `audit-logs/conformations/tic-N.json`, cached scalar counters). Observability consumes those summaries. When summaries are absent, observability degrades (shows less data), never compensates (scans raw ledgers). The fallback ladder: conformation summary → cached counters → static metadata (model, project, branch).

## 6. Lexical Ceiling (Scope Boundary)

CGG's governance lifecycle is complete for individuals and small teams. The flat-file primitives — JSONL signal stores, CLAUDE.md rule tiers, append-only audit trails — are fast, portable, and auditable by default.

**CGG expands lexical capabilities further than most approaches** by treating governance, storage, knowledge, and memory as separate concerns — not conflating them into a single "AI memory" abstraction. This separation is what makes flat-file governance viable at meaningful scale.

CGG runs inside an AI agent. The agent reading CLAUDE.md files has full semantic understanding — it connects "embedding API failures" to "infrastructure sovereignty" without keyword overlap. It spawns subagents for deeper search and catches duplicates during `/review` that no keyword matcher would flag. The retrieval surface is an LLM, not a grep index.

But there is a ceiling: **the fundamental limit of lexical meaning**. Text-as-governance degrades at scale:

- When the signal store grows past a few hundred entries, dedup-by-latest-entry-per-ID becomes a linear scan.
- When the lesson corpus spans dozens of CLAUDE.md files across deeply nested projects or subprojects, governance load grows heavy — consuming context window budget disproportionately.
- A governance file that was 50 lines and sharp becomes 500 lines and numbing. The agent reads it all. Reading and applying are different cognitive operations.

### Mitigations and limits

CGG supports methods for mitigating lexical limits:
- Zone scoping (`.ticzone`, `.ticignore`) to bound the governance surface
- Scope hierarchy to keep lessons at appropriate levels
- Signal decay to quiet stale friction
- Human curation during `/review` to prune noise

These extend the useful range of flat-file governance. But ultimately, the solution to lexical limits lies in fusion of capabilities outside this repo's scope — semantic retrieval, graph topology, expression gating, economic pressure. CGG is designed to be **aware of this boundary** and **transparent about it**.

### Out of scope for this repo

The following capabilities require infrastructure CGG deliberately avoids. They are **out of scope** — not roadmap items, but boundary decisions:

| Capability | What it addresses | Why it's out of scope |
|------------|-------------------|----------------------|
| Expression gating | Lessons go dormant until the system re-enters a specific failure shape | Requires state beyond flat files; selective loading needs retrieval infrastructure |
| Conformation-aware retrieval | Load only what matches current system shape | Requires fingerprinting system state; flat files have no selection mechanism |
| Graph topology | Relational edges between concepts | JSONL has no structure between entries |
| Endogenous economics | Cost pressure to compress, curate, expire | Flat-file governance grows without bound; capturing is free |
| Compiled constraints | Execution-boundary enforcement | Advisory text the agent reads ≠ constraints it cannot violate |

These require vector databases, embedding models, graph engines, or economic engines — infrastructure that does not fit in a CLI framework. CGG provides the governance lifecycle. Fusion of these capabilities is a different engineering problem, addressed by infrastructure outside this repo.

**CGG's docs do not depend on external docs.** The categories above describe classes of capability, not specific implementations. Any system providing these capabilities can compose with CGG's governance primitives.

### When CGG stops being enough

The ceiling shows up when:
- Governance text grows monotonically and deeply nested projects accumulate heavy lesson loads
- Lessons that were sharp when captured lose force buried in walls of text
- You need "load only what matches the current failure shape," not "load everything"
- Signals exceed a few hundred entries and dedup becomes slow
- You need compiled constraints the agent cannot violate, not advisory text it reads

At that point, CGG's flat-file primitives become the audit trail beneath whatever infrastructure you adopt. The governance lifecycle stays the same — capture, evaluate, promote, audit — but the storage and retrieval layer changes.

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

---

## Actor Model

### Actor hierarchy

```
Human
  ↓
Interactive orchestrator (primary UX / control plane)
  ↓
Estate governance orchestrators
  ├─ Mogul (governance-operational heavy lift)
  └─ Economic governor (optional)
```

> **Persona names**: Estates may assign persona names to offices (e.g., "Homeskillet" for the interactive orchestrator, "Swann" for the economic governor) via `.ticzone` `governance_actors`. These docs use role descriptions for portability.

### Interactive orchestrator

Role: primary UX and control plane
Mode: blocking / user-facing

Responsibilities:
- run sessions
- present governance artifacts and synthesized insights
- invoke /cadence /review /siren
- steer Mogul through conversation, cadence, and hook-mediated prompts
- receive summaries, escalations, and decision points from Mogul

Cannot:
- silently promote law
- bypass constitutional review
- routinely perform governance maintenance (that's Mogul's lane)

### Mogul

Role: default governance-operational suborchestrator
Mode: headless by default

Responsibilities:
- governance CI
- candidate assessment and enrichment advancement
- MEMORY mining
- ladder coherence audits
- runtime drift detection
- prompt-stack audits
- review staging and packet strengthening
- deliverable-team orchestration
- subordinate delegation and decomposition
- operational pressure routing

May:
- decompose due governance work into bounded subordinate tasks
- invoke bundled scripts and skill-scoped execution logic
- spawn bounded subagents for focused work
- when enabled and justified, orchestrate agent teams / parallel Claude Code sessions
- choose blocking vs nonblocking handling by criticality, dependency structure, and cost
- advance queue/enrichment state when evidence thresholds justify it
- surface state, findings, and review packets upward into UX lane

Must:
- choose the architecturally appropriate orchestration form — fitness to governance surface structure, not abstract lightness
- avoid coordination overhead when simple execution is enough

Cannot:
- promote law
- mutate CLAUDE.md
- assume the economic governor's role

### Economic governor (optional)

Role: economic governor

Responsibilities:
- exchange behavior
- mint/burn policy
- treasury reporting
- liquidity monitoring
- economic pressure signals

The economic governor must never run operational governance. Not all CGG installs require an economic governor — it is configured via `.ticzone` `governance_actors` when token economy constraints are desired.

### Subordinate assessors

- Ripple Assessor
- Scope Resolver
- Ladder Auditor
- Prompt Stack Auditor
- Signal Neighborhood Auditor
- Repo Map Assessor
- Manifestation Evidence Gatherer

Key rule:
- subagents produce evidence
- Mogul produces synthesis
- humans produce law

## Behavior-Bearing Surfaces

All surfaces capable of affecting agent behavior are auditable governance targets.

These include:
- CLAUDE.md chain
- MEMORY.md chain
- SKILL.md files
- agent prompts
- project instruction files
- convention blocks
- hooks
- runtime scripts
- installed runtime copies
- bridge prompts
- handoff triggers

### Audit expansion rule

If signals cluster around agent behavior, Mogul must expand the audit surface to include all nearby behavior-bearing prompts and runtime layers.

### Example failure case

A lesson repeatedly compensating for agent drift may indicate prompt-stack interference rather than missing governance law.

### Executable substrate design principle

When the governance infrastructure can execute demonstrations live (e.g., Academy SKILL.md running real tic emissions, signal routing, and warrant minting), tutorial design shifts from student-written exercises to Claude-narrated demonstrations. The student's job becomes understanding, not implementing. This is not a pedagogical preference — it's a structural consequence of executable behavior-bearing surfaces.

## Warrant Completeness Invariant (Trip Hazard)

A detected runtime hazard that cannot mint a warrant is a broken governance loop. A siren that never mints a warrant is just noise.

**Formal statement**: Runtime drift that the system detects but does not escalate is equivalent to a siren blaring without ever minting a warrant — pressure exists but never becomes unavoidable. That is a governance failure.

**Operational rule**: Detected hazards must have a path to warrant. If a condition is detectable (e.g., `canonical != installed`), the detection must emit a signal of warrant-eligible kind (BEACON or TENSION, not LESSON), so volume accrual can force resolution.

**Kind-gated implication**: Only BEACON and TENSION are warrant-eligible by default (Section 5 warrant recognition). A hazard detected but emitted as a LESSON signal will accrue volume but never warrant — the governance loop is broken by kind classification, not by missing infrastructure. Emitters must choose the correct kind at emission time.

## Audit Cycles

Governance audits run on tic-sum-derived cadence. These are interim cycles — sufficient for flat-file governance. Each cycle is a check, not a full session.

| Cycle | Frequency | What it checks | Execution surface |
|-------|-----------|---------------|-------------------|
| **Queue + signal scan** | Every 1 tic | Active CPR queue state, signal volume, warrant thresholds | SessionStart hook, `/siren tick` |
| **MEMORY mining** | Every 3 tics | Recurring patterns, abstraction opportunities, stabilized workarounds | Mogul (future) |
| **Ladder audit** | Every 5 tics | Parent/child CLAUDE coherence, installed/source drift | Mogul (future) |
| **Deep audit** | Every 8 tics | Multi-rung coherence, sibling duplication, manifestation pressure, demotion candidates | Mogul (future) |

### Active cycles (implemented)

- `session_start_restore` — SessionStart hook discovers handoff plans, injects CPR queue, runs enrichment scanner
- `first_prompt_assessment` — UserPromptSubmit hook triggers one-shot ripple-assessor (background)
- `posttool_microscan` — PostToolUse hook detects runtime drift when governance files are modified (Write/Edit on CLAUDE.md, SKILL.md, agent prompts, hooks). Emits TENSION signal if installed copy drifts from canonical source.
- `review_close_consistency_check` — post-`/review` verification that constitutional changes landed coherently
- `cadence_due_stamp` — `/cadence` writes tic-sum-derived due markers into handoff bridge

### Due marker computation

Due markers are deterministic from the current tic count:
- `review_due_tic = current_tic + 1`
- `memory_mining_due_tic = current_tic + (3 - current_tic % 3)` (next multiple of 3)
- `ladder_audit_due_tic = current_tic + (5 - current_tic % 5)` (next multiple of 5)
- `deep_audit_due_tic = current_tic + (8 - current_tic % 8)` (next multiple of 8)

SessionStart hooks may check these markers against the current tic to determine which cycles are due.

## Dimensional Separation

Five independent dimensions describe governance participants. Conflating them produces role collapse, copy-state confusion, and trigger/surface misidentification.

### Dimension 1: Office/Actor

An **office** is a named governance role with defined responsibilities, constraints, and delegation authority. Each office has exactly one occupant at any time.

| Office | Role | Mode |
|--------|------|------|
| Interactive orchestrator | Primary UX / control plane | Blocking, user-facing |
| Mogul | Governance-operational suborchestrator | Headless by default |
| Economic governor (optional) | Token economy, cost constraints | Headless by default |

> **Estate customization**: Offices can be given persona names via `.ticzone` `governance_actors` (e.g., "Homeskillet" for the interactive orchestrator, "Swann" for the economic governor). CGG canonical docs use role descriptions, not persona names.

Subordinate roles (Ripple Assessor, Pattern Curator, Ladder Auditor, etc.) are delegation targets, not offices. They operate under Mogul's synthesis authority.

### Dimension 2: Runtime Embodiment

An office may have multiple **embodiments** — runtime environments where the office can execute. Embodiments describe capability, not identity.

| Embodiment | Environment | Capabilities |
|------------|-------------|-------------|
| `cgg_runtime` | Claude Code agent process | Host filesystem, git, codebase, governance surfaces, subagent delegation |
| `estate_runtime` | External supervised process | Container filesystem, memory systems, web intelligence, compliance tools |

One office, multiple possible embodiments. The embodiment determines what tools are available, not what the office is responsible for. CGG canonical docs describe embodiments abstractly — convergence-specific mappings (Docker, A0, etc.) belong in local project documentation.

### Dimension 3: Source/Install State

Governance artifacts exist in three states:

| State | Location | Authority |
|-------|----------|-----------|
| **Canonical source** | `vendor/context-grapple-gun/cgg-runtime/` | Design intent |
| **Installed copy** | `.claude/skills/`, `.claude/agents/`, `.claude/hooks/` | Operational convenience |
| **Loaded runtime** | Agent process memory | Behavioral truth |

Loaded runtime wins. Canonical source is intent until sync + verify completes. Source copies are not actors. Installed copies are not actors. Only the loaded runtime in an embodiment is an actor.

### Dimension 4: Governance Surface

| Surface | Job | Examples |
|---------|-----|---------|
| **Authoring** | Capture lessons | MEMORY.md, CLAUDE.md candidate blocks |
| **Execution** | Drive lifecycle | queue.jsonl, mandate payloads, enrichment records, bench packets |
| **Constitutional** | Human law | /review docket, approved CLAUDE.md inscriptions |
| **Bridge** | Carry state between contexts | Handoff/plan files |
| **History** | Audit trail | signals, tics, conformations, reviews |

### Dimension 5: Trigger/Cycle

Triggers activate governance work. They are not surfaces.

| Trigger | When | What it does |
|---------|------|-------------|
| `session_start` | SessionStart hook | Restore bridge, detect overdue cycles, write Mogul mandate |
| `first_prompt` | UserPromptSubmit hook | Non-blocking spawn point for background Mogul runs |
| `cadence` | `/cadence` skill | Emit tic, compute newly-due cycles, write Mogul mandate |
| `review` | `/review` skill | Require fresh bench packet, consume Mogul outputs, issue review-close mandate |
| `siren` | `/siren` skill | Expose signal state, optionally trigger neighborhood audit mandates |
| `init_governance` | `/init-governance` skill | Install/sync surfaces, initialize baseline due markers |
| `explicit` | Human direct invocation | Override trigger for manual cycle execution |

### Ownership Invariant

**Due governance work may be triggered from the user-facing layer, but it must be owned by the proper governor.** The interactive orchestrator may notice due-ness, trigger Mogul, and present results. The interactive orchestrator should not routinely perform Mogul's maintenance work. When Mogul's activation fabric is absent, manual execution by another actor must be recorded as wrong-owner override.

**Heavy governance lifting stays out of the UX lane by default.** Maintenance execution, queue advancement, enrichment gathering, signal scanning, and subordinate orchestration default downward into Mogul. The interactive orchestrator receives summaries, escalations, and decision points — not the heavy lifting itself.

Mogul may surface state upward. The interactive orchestrator may steer Mogul downward. Hooks and cadence may manage Mogul by proxy through the UX lane. These interactions do not transfer default operational ownership. Visibility and steerability are not the same as ops ownership. The goal: Mogul stays busy so the interactive orchestrator does not have to.

## Mogul Activation Contract

### Mandate model

Mogul is always activated with an explicit **mandate** — a machine-checkable execution-surface artifact describing the activation context. Mogul reads the mandate and decides subdelegation within bounds. Mogul does not invent its own trigger reason.

Mandate schema: `cgg-runtime/config/mogul-mandate.schema.json`

### Mandate storage

The mandate is an execution-surface artifact, not a bridge or ephemeral transport:

| Path | Role |
|------|------|
| `audit-logs/mogul/mandates/current.json` | Active mandate (latest, authoritative) |
| `audit-logs/mogul/mandates/history/YYYY-MM-DD.jsonl` | Append-only mandate history |

Optional: `/tmp/claude_cgg/.../mogul-mandate.json` as transport cache. The audit-logs path is the execution-surface authority.

### Trigger → mandate flow

1. Trigger fires (SessionStart, /cadence, /review, explicit)
2. Trigger computes due cycles from tic-derived markers
3. Trigger writes mandate to `audit-logs/mogul/mandates/current.json`
4. Trigger appends mandate to `audit-logs/mogul/mandates/history/YYYY-MM-DD.jsonl`
5. If spawn-worthy: trigger schedules Mogul activation at appropriate spawn point
6. Mogul reads mandate, executes mandated cycles, produces execution artifacts
7. Mogul does NOT invent additional trigger reasons beyond the mandate

### Blocking vs non-blocking

| Mode | When | Examples |
|------|------|---------|
| **Non-blocking** (default) | Standard maintenance | 1-tic refresh, 3-tic memory mining, 5-tic drift check, 8-tic deep audit |
| **Blocking** | Constitutional or dependency-critical | Pre-review bench packet (stale), review-close consistency, explicit deep audit, runtime-drift when constitutional decisions pending |

### Governance maintenance lanes (Mogul-owned)

These lanes are Mogul's responsibility. Other actors may trigger them but should not routinely perform them:

1. Memory mining (3-tic cycle)
2. Pattern curation (delegated to Pattern Curator)
3. Enrichment scanning (delegated to Ripple Assessor)
4. Ladder coherence audit (5-tic cycle, delegated to Ladder Auditor)
5. Manifestation scan (8-tic deep audit)
6. Runtime drift audit (5-tic cycle)
7. Prompt-stack audit (5-tic cycle)
8. Review-close consistency (post-/review)
9. Bench packet preparation (pre-/review)

---

### Part II — Advanced / boundary-to-substrate (Sections 7–11)

Not required to run CGG today. These sections explain design limits, failure modes as scale grows, and how the substrate extends beyond flat files.

## Complexity Awareness (Sections 7–11)

*The following sections describe architectural concerns CGG addresses through deliberate boundary decisions. These are not roadmap items — they're scope boundaries. Where CGG's flat-file governance stops being sufficient, Ubiquity (production substrate) provides the deeper capabilities.*

---

## 7. Assessor Promotion Bias (Structural Analysis)

The ripple assessor has a structural incentive toward PROMOTE verdicts, not by explicit instruction but by architectural pressure:

1. **Mission framing**: "evaluate whether it should be promoted to a broader scope" pre-frames the question as a promotion question, not a placement question.
2. **Evaluation checklist asymmetry**: overlap/conflict/gap — two of three (no conflict + gap exists) point toward PROMOTE. Only overlap points toward SKIP. The checklist is 2:1 in favor of promotion by construction.
3. **Output format**: the summary tallies `Promote: X, Skip: Y, Modify: Z` — SKIP is the negative case. Assessors producing useful-looking reports tend toward PROMOTE because it generates more content.
4. **Pre-argued brief**: the cadence-level CogPR author writes `recommended_scopes` and `rationale` — the assessor receives a case for promotion, not raw evidence to evaluate independently.

The human `/review` gate is the only countervailing pressure — adequate for the current pipeline, but a bottleneck as proposal volume grows.

<!-- --agnostic-candidate
  lesson: "Assessor promotion bias is structural (mission framing, checklist asymmetry, output format, pre-argued brief) — not a bug to fix but a design property to counterbalance with tic-gating, enrichment requirements, and trust-scaled autonomy"
  source_date: "2026-03-03"
  source: "vendor/context-grapple-gun/ARCHITECTURE.md:181"
  band: "COGNITIVE"
  motivation_layer: "COGNITIVE"
  subsystem: "cgg"
  posture: "ENG/META"
  birth_tic: 165
  recommended_scopes:
    - "vendor/context-grapple-gun/cgg-runtime/agents/ripple-assessor.md"
  rationale: "The bias is not a defect — it reflects the system's current architecture where the human gate is the only selection pressure. As trust-gated autonomy is introduced, the assessor needs counterbalancing mechanics (tic thresholds, enrichment requirements) to prevent unchecked promotion at lower tiers."
  review_hints: "Do not 'fix' the bias by adding SKIP incentives — that creates a different bias. Instead, introduce the two pending states (tic_gated, enrichment_eligible) so temporal and epistemic maturity gate promotion independently of the assessor's reasoning quality."
  status: "promoted"
  promoted_date: "2026-03-03"
  promoted_to:
    - "vendor/context-grapple-gun/cgg-runtime/agents/ripple-assessor.md (Bias Awareness section)"
    - ".claude/agents/ripple-assessor.md (synced copy)"
  grapple_docket: "2026-03-03"
-->

## 8. Bidirectional Abstraction Engine (Scope Boundary)

CGG is aware of the need for proposals to earn their shape at the target tier before arriving there. Two mechanisms address this within CGG's flat-file constraints:

### Two Pending States

| State | Condition | What accelerates it | What doesn't |
|-------|-----------|--------------------|----|
| **Tic-gated** (temporal maturity) | Pattern must survive N conformations at current scope | Nothing — only time | Better argumentation |
| **Enrichment-eligible** (epistemic insufficiency) | Scope alignment, sibling evidence, or abstraction shape is incomplete | Active investigation: inversion angle, sibling cross-reference | Waiting |

The distinction prevents both premature promotion (sound argument, untested persistence) and stale pending queues (persistent pattern, unexplored implications).

### Inversion Angle

On a tic-ratio cadence, the assessor explores *downward* — takes a proposal targeting Tier N and tests its primitive application at Tier N-1 in sibling contexts. The output is enrichment (missing nuance, decomposition signals, sibling evidence), not a verdict.

### Trust-Gated Autonomy

The assessor accumulates a track record (meta-log: verdicts vs human overrides vs subsequent signal activity). As trust grows, lower-tier promotions become autonomous. The human gate concentrates at the highest tier where worldview shape is at stake. Trust can voluntarily contract when drift is detected.

### Drift Classification

Conformation diffs over tic ranges classify shape change:
- **Growth**: gradient extending into new territory, existing cables holding
- **Drift**: gradient rotating — old truths contradicted by new promotions
- **Decay**: gradient flattening — governance pressure relaxed, promotions passing without real enrichment

### CGG Boundary (Lexical Ceiling)

These mechanics operate within CGG's flat-file constraints:
- Two pending states = fields on CogPR blocks
- Tic thresholds = arithmetic on birth_tic vs current physical count
- Enrichment history = append-only text in CogPR blocks
- Trust level = counter derived from meta-log
- Drift classification = conformation diff comparison

Beyond ~10 siblings, gradient-fit evaluation, and conformation-aware trust — hand off to Ubiquity's fusion engine. CGG produces the audit trail; the substrate fuses it into meaning-space.

<!-- --agnostic-candidate
  lesson: "CGG's bidirectional abstraction engine: two pending states (tic_gated/enrichment_eligible), inversion angle for sibling cross-reference, trust-gated autonomy with voluntary contraction, drift classification (growth/drift/decay). Lexical ceiling: ~10 siblings, arithmetic trust counters, flat-file enrichment logs. Beyond that → Ubiquity fusion engine."
  source_date: "2026-03-03"
  source: "vendor/context-grapple-gun/ARCHITECTURE.md:206"
  band: "COGNITIVE"
  motivation_layer: "COGNITIVE"
  subsystem: "cgg"
  posture: "ENG/META"
  birth_tic: 165
  recommended_scopes:
    - "vendor/context-grapple-gun/README.md"
    - "CLAUDE.md"
  rationale: "This is the architectural bridge between CGG-as-governance-lifecycle and Ubiquity-as-substrate. The design defines exactly where flat-file governance stops being sufficient and what the handoff looks like. Affects both CGG's roadmap and Ubiquity's intake surface."
  review_hints: "The two pending states and trust counter are implementable now (field additions to CogPR format, meta-log query). Inversion angle and drift classification need the conformation diff tooling to be more mature. Validate the ~10 sibling threshold empirically before committing to it as the ceiling."
  status: "rejected"
  rejected_date: "2026-03-03"
  reason: "Design vision well-captured in ARCHITECTURE.md (its authoritative home). README describes current behavior and already references ARCHITECTURE.md. CLAUDE.md is operational instructions, not design vision. Re-evaluate when two pending states are implemented and the engine becomes operational."
  grapple_docket: "2026-03-03"
-->

## 9. CogPR Maturity Fields (Concrete Spec)

Section 8 described the *design* of bidirectional abstraction: two pending states, inversion angle, trust-gated autonomy. This section specifies the *implementation* — the exact fields, lifecycle transitions, and assessor behaviors that make those mechanics operational within CGG's flat-file constraints.

The two gates are independent. A CogPR can pass temporal maturity and still lack epistemic depth. It can carry rich enrichment evidence and still be too young. Both must clear before the assessor renders a verdict.

### Field Schema

Two optional fields extend the existing `<!-- --agnostic-candidate -->` block:

```yaml
# Temporal maturity gate
tic_gated:
  birth_tic: <int>           # tic count when CogPR was created (already exists as birth_tic)
  maturity_tics: <int>       # minimum tic delta before eligible (default: 3)
  matured_at_tic: <int|null> # tic count when threshold was met (null = immature)

# Epistemic maturity gate
enrichment:
  status: "raw" | "investigated" | "cross_referenced" | "shaped"
  evidence:                  # append-only log of enrichment events
    - date: "YYYY-MM-DD"
      kind: "sibling_match" | "inversion_test" | "scope_alignment" | "abstraction_fit"
      detail: "free text — what was found"
  eligible: <bool>           # true when status >= "investigated" AND evidence has ≥1 entry
```

### Status Lifecycle

The existing `pending → promoted / rejected` path now has intermediate states:

```
pending → tic_gated → enrichment_eligible → promotable → promoted
                                                       → rejected
          (skip directly to promotable if both gates pass simultaneously)
```

- **pending**: CogPR created, no maturity evaluation yet.
- **tic_gated**: Birth tic recorded. Not eligible until `current_tic - birth_tic >= maturity_tics`. The assessor marks this state on first evaluation when the CogPR is too young — then stops. Argument cannot substitute for time.
- **enrichment_eligible**: Temporal gate passed. Enrichment evidence still insufficient. The assessor or future sessions append evidence entries as investigation happens.
- **promotable**: Both gates cleared. Ready for the full assessor evaluation — overlap/conflict/gap — and human review.
- **promoted** / **rejected**: Terminal states, unchanged from the current spec.

### What Advances Each Gate

The two gates advance through fundamentally different mechanisms, and conflating them is the failure mode:

| Gate | What advances it | What does NOT advance it |
|------|-----------------|------------------------|
| Temporal (`tic_gated`) | Tic counter advancing — time passing | Better argumentation, more evidence |
| Epistemic (`enrichment`) | Active investigation: sibling cross-reference, inversion test, scope alignment check | Waiting, restating the same rationale |

A CogPR that's logically sound but untested by time sits in `tic_gated`. A CogPR that's survived multiple conformations but hasn't been stress-tested against siblings sits in `enrichment_eligible`. Neither state is a failure — they're explicit acknowledgments of what the proposal still owes.

### Assessor Behavior

The gate sequence runs in order:

1. Check `birth_tic` against the current tic count. If the delta is below `maturity_tics` (default: 3), set status to `tic_gated` and stop — reason: "temporal maturity insufficient."
2. If the temporal gate passes, check `enrichment.eligible`. If false, set status to `enrichment_eligible` and stop — reason: "enrichment evidence insufficient."
3. If both gates pass, evaluate normally — overlap/conflict/gap — and render a PROMOTE/SKIP/MODIFY verdict.

### Backward Compatibility

CogPR blocks without these fields default to `tic_gated.maturity_tics = 0` (no temporal gate) and `enrichment.eligible = true` (no enrichment gate). Every existing CogPR remains promotable under the current rules. The fields are opt-in: the assessor adds them on first encounter when `birth_tic` is present, but never retroactively fails a CogPR created before the gates existed. This is a design decision, not just a migration convenience — governance rules must not invalidate prior work.

### Trust Counter Schema (`~/.claude/cgg-trust-state.json`)

The trust counter is a track record — the accumulation of assessor verdicts, human overrides, and post-promotion signal activity. It lives in a single file:

```json
{
  "version": 1,
  "assessor_id": "ripple-assessor",
  "trust_level": 0,
  "history": [
    {
      "docket_date": "2026-03-03",
      "cprs_evaluated": 2,
      "verdicts": {"promote": 1, "skip": 1, "modify": 0},
      "human_overrides": 0,
      "post_signal_activity": 0
    }
  ],
  "thresholds": {
    "tier_4_autonomous": 10,
    "tier_5_autonomous": 50
  },
  "last_updated": "2026-03-03T00:00:00-05:00"
}
```

- **trust_level**: Increments when the human approves an assessor verdict without override. Decrements on override. Resets to 0 if a promoted lesson generates a subsequent signal — the lesson didn't land, and the assessor's judgment was wrong in a way that mattered.
- **tier_4_autonomous**: Trust level at which Tier 4 (site scope) promotions bypass the human gate. Reachable through consistent, accurate evaluation.
- **tier_5_autonomous**: The threshold for Tier 5 (global scope) autonomy — intentionally high. Global is a treaty, and trust that scales to treaty-level governance is earned slowly.
- **Voluntary contraction**: If drift classification returns "Drift" or "Decay" over a tic range, `trust_level` halves (rounded down). The system can lose autonomy when governance quality degrades — not as punishment, but because degraded governance requires more human oversight, not less.

## 10. Plugin Packaging Architecture

CGG's `cgg-runtime/` directory structure maps 1:1 to Claude Code's plugin components schema. Packaging CGG as a plugin is a wrapping exercise, not restructuring.

### Directory correspondence

| `cgg-runtime/` | `plugin.json` component | What it contains |
|-----------------|------------------------|------------------|
| `skills/` | `components.skills[]` | Slash command SKILL.md files |
| `hooks/` | `components.hooks[]` | SessionStart + UserPromptSubmit shell scripts |
| `agents/` | `components.agents[]` | Ripple-assessor agent prompt |

This correspondence is structural, not accidental. CGG was built using Claude Code's native conventions — same directory layout, same frontmatter format, same lifecycle hooks. The plugin manifest (`.claude-plugin/plugin.json`) declares these components; Claude Code registers them automatically.

### Plugin manifest (`.claude-plugin/plugin.json`)

The manifest declares three active skills, two hooks, one agent, and five deprecated skill aliases:

**Active skills:**
- `cadence` — session epoch boundary (tic + lessons + handoff)
- `review` — CogPR promotion + warrant triage (human-gated)
- `siren` — signal emission, tick advancement, triage dashboard

**Deprecated aliases** (redirect to active skills):
- `cadence-downbeat` → `cadence`
- `cadence-syncopate` → `cadence double-time`
- `grapple` → `review`
- `init-gun`, `init-cogpr` → absorbed into bootstrap/plugin install

**Hooks:**
- `SessionStart` → `session-restore-patch.sh` (handoff discovery, CogPR queue injection)
- `UserPromptSubmit` → `cgg-gate.sh` (one-shot ripple-assessor trigger)

**Agents:**
- `ripple-assessor` (sonnet) — CogPR evaluation + signal/warrant assessment

### Install simplification

The plugin path replaces manual file copying and `settings.local.json` patching:

| Before (bootstrap) | After (plugin) |
|---------------------|----------------|
| Copy `cgg-runtime/skills/*` → `.claude/skills/` | Auto-registered from manifest |
| Copy hooks + `chmod +x` | Auto-registered from manifest |
| Patch `settings.local.json` hook entries | Auto-registered from manifest |
| Copy agent prompt | Auto-registered from manifest |
| Create directories manually | Declared in `install.directories[]` |

The bootstrap prompt remains as a fallback for Claude Code versions that don't support plugins.

### Namespacing

If the plugin mechanism namespaces skills, CGG skills become `/cgg:cadence`, `/cgg:review`, `/cgg:siren`. If not namespaced, behavior matches bootstrap (skills register without prefix).

**To verify when plugin spec ships:**
- [ ] Whether namespacing is automatic, opt-in, or absent
- [ ] Collision behavior between plugin skills and same-named local skills
- [ ] Whether deprecated aliases survive namespacing or need explicit redirect entries
- [ ] Whether hook auto-registration fully replaces `settings.local.json` patching or supplements it

### What the plugin does NOT contain

- **No MCP/LSP servers.** CGG's data stores (JSONL, SQLite, flat CLAUDE.md files) require no server processes.
- **No runtime dependencies.** Shell scripts + the agent prompt. No package installs.
- **No project-specific content.** `.ticzone`, `.ticignore`, and the CLAUDE.md convention block are generated at install time from templates, not shipped as static files.

### Design implication

The 1:1 mapping means CGG's evolution path is packaging, not migration. New skills, hooks, or agents added to `cgg-runtime/` become plugin components by adding a manifest entry. The cgg-runtime directory IS the plugin — the manifest is metadata about it.

## 11. Governance Truth Surfaces

**Tags are authoring. Queue is execution. Plans are bridges. Audit logs are history.**

CGG governance state lives on four surfaces. Each has one job. Mixing jobs across surfaces causes duplicate processing, stale re-promotions, and unqueryable audit trails.

| Surface | Job | Format | Who writes | Who reads |
|---------|-----|--------|------------|-----------|
| **Authoring** (CLAUDE.md, MEMORY.md) | Capture lessons | `<!-- --agnostic-candidate -->` blocks | Agent during `/cadence` Step 2 | Humans. Backfill scan (safety net). |
| **Execution** (`audit-logs/cprs/queue.jsonl`) | Drive lifecycle | JSONL, latest-per-ID-wins | Extraction hook (fast path). SessionStart backfill (slow path). Assessor (state advancement). `/review` (verdicts). | Assessor. `/review`. SessionStart (counts). |
| **Bridge** (plan/handoff files) | Carry state between contexts | Markdown with trigger blocks | `/cadence` at session end | Next session's restore hook. Ripple assessor. |
| **History** (signals, tics, conformations, reviews) | Audit trail | JSONL, append-only | Skills, hooks, scripts at event time | Conformation snapshots. `/siren`. Drift analysis. Forensics. |

### Flow direction

```
Agent discovers lesson
  → writes tag to CLAUDE.md (authoring surface)
  → /cadence writes plan containing tags
  → PostToolUse hook extracts tags → queue.jsonl (execution surface)
  → assessor advances queue entries through lifecycle
  → /review applies verdicts from queue
  → audit log records the decision (history surface)
```

Tags do not drive execution. The queue drives execution. Tags are the human-readable record of what was captured. If a tag and a queue entry disagree, the queue wins — it reflects the latest state machine position.

### Recovery invariant

The three extraction paths (PostToolUse fast path, SessionStart recovery, SessionStart backfill) all use the same dedup hash. Running all three on the same CogPR produces exactly one queue entry. The queue is eventually consistent — the fast path is the normal case, the other two are safety nets.

### Auto-promotion (self-referencing local scope)

A CogPR that recommends the same file it lives in is self-referencing. These may be auto-closed by the assessor WITHOUT human gate, subject to three hard limits:

1. **Site scope only.** Target must be the same file or a file in the same directory. Never beyond site scope.
2. **Target == source.** The CogPR's `recommended_scopes` must exactly match the file containing the tag. No "close enough" matching.
3. **No shared invariants.** If the lesson text references a `[GLOBAL_INVARIANT]`-tagged section, or modifies a rule that other files depend on, auto-close is blocked. Route to `/review`.

These limits prevent encoding "promote me" patterns. Self-referencing CPRs are a documentation housekeeping shortcut, not a governance bypass.

<!-- --agnostic-candidate
  lesson: "CGG cgg-runtime/ maps 1:1 to Claude Code plugin.json components — packaging as a plugin is wrapping, not restructuring"
  source_date: "2026-03-03"
  source: "vendor/context-grapple-gun/ARCHITECTURE.md:368"
  band: "COGNITIVE"
  motivation_layer: "COGNITIVE"
  subsystem: "cgg"
  recommended_scopes:
    - "vendor/context-grapple-gun/ARCHITECTURE.md"
  rationale: "Plugin marketplace is the next architectural milestone for CGG."
  review_hints: "Verify against actual Claude Code plugin spec when it ships."
  status: "promoted"
  promoted_date: "2026-03-03"
  promoted_to:
    - "vendor/context-grapple-gun/ARCHITECTURE.md (Section 10: Plugin Packaging Architecture)"
  grapple_docket: "2026-03-03"
-->
