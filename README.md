<p align="center">
  <img src="assets/cgg-banner.jpeg" alt="Context Grapple Gun by Prompted LLC & Ubiquity OS" width="100%" />
</p>

# Context Grapple Gun

**A file-based governance lifecycle for persistent AI systems.**

Three commands. Five structural mechanisms. One scale boundary.

---

**You only need four things to start:**
- Three commands: `/cadence`, `/review`, `/siren`
- Run `/cadence` to end every session cleanly; run `/review` every few sessions to approve lessons
- Scope ladder: Site → Domain → Estate → Federation → Global — you decide what promotes
- Install via [START-HERE.md](START-HERE.md); everything else is reference or depth

---

## Read this first (by intent)

| You want to... | Start here |
|----------------|------------|
| **Use it now** | [START-HERE.md](START-HERE.md) — the three commands, a normal day, install in 30 seconds |
| **Evaluate the architecture** | This file (keep reading) → [DEV-README.md](DEV-README.md) → [ARCHITECTURE.md](ARCHITECTURE.md) |
| **Learn through story** | [academy/README.md](academy/README.md) — five chapters, real simulations, one very persistent goat |
| **Install and extend** | [INSTALL.md](INSTALL.md) — plugin path, bootstrap fallback, install modes |

---

## 90-second mental model

**The problem:** AI agents discover truths during work — bug patterns, API quirks, coordination techniques that work. When the session ends, that knowledge vanishes. Next session: same agent, same repo, zero memory of what it learned.

**The CGG answer:** Lessons get captured as they happen, reviewed between sessions, and promoted to broader scopes with human approval at every gate. The project's operating rules grow from real work, not from someone writing documentation.

**Three commands run the lifecycle:**

| Command | What it does |
|---------|--------------|
| `/cadence` | End of session. Saves lessons, emits a tic (sequenced timestamp), writes a handoff for the next session. |
| `/review` | Review proposed lessons. Approve, reject, or modify before promotion. |
| `/siren` | Check on recurring friction. See what signals are building, what warrants have minted. |

**Five structural mechanisms make it work:**

| Mechanism | What it does |
|-----------|--------------|
| Abstraction ladder | Scope hierarchy: site → domain → estate → federation → global. Lessons climb it through review. |
| Epoch boundary | Context rotation discipline. End the session before cognitive degradation, carry knowledge forward. |
| Human gate | Every scope promotion requires explicit approval. The agent proposes; you decide. |
| Signal manifold | Runtime condition monitoring. Friction signals accrue volume, cross thresholds, mint warrants. |
| Tic / tic-zone | Canonical timestamping and jurisdictional scoping. Total ordering across agents and cadences. |

**One scale boundary:**

CGG is the governance lifecycle. It uses flat files, git-tracked, auditable by default. When flat files aren't enough — when you need semantic recall, graph topology, or conformation-aware retrieval — the substrate layer (Ubiquity) picks up where CGG leaves off. Same governance primitives, deeper infrastructure. CGG is complete without Ubiquity. Ubiquity composes on top when scale demands it.

---

## What CGG is not

- **Not a vector database.** No embeddings, no semantic search. Flat files and grep.
- **Not a magical memory layer.** Lessons require human review to promote. Nothing persists without approval.
- **Not a full substrate.** CGG handles governance lifecycle. Substrate capabilities (expression gating, graph topology, compiled constraints) require infrastructure CGG deliberately avoids.
- **Not a hosted platform.** Everything runs locally. No APIs, no services, no cloud dependencies.

---

## Core terms (with neutral aliases)

On first encounter, CGG terminology maps to familiar systems concepts:
- **CogPR** — behavior pull request: a proposed lesson flagged for review and promotion
- **tic** — sequenced timestamp: ISO-8601 + monotonic counter for total ordering
- **tic-zone** — jurisdiction boundary: `.ticzone`-defined acoustic region that scopes routing
- **siren → warrant** — recurring friction signal that mints an escalation when it crosses threshold
- **Abstraction ladder** — scope hierarchy: Site → Domain → Estate → Federation → Global; lessons climb through `/review`

Full glossary: [docs/TERMINOLOGY.md](docs/TERMINOLOGY.md).

---

## Skeptic's evaluation path

**~20 minutes to informed judgment.**

1. **Read:** This section + [START-HERE.md](START-HERE.md) (~5 min)
2. **Install:** Plugin path or bootstrap — 30 seconds
3. **Run:** Start a session, do some work, run `/cadence` at the end
4. **Inspect:** Look at `audit-logs/` — see the tic records, signal files, CogPR blocks
5. **Review:** Next session, run `/review` — see the docket, the verdicts, the scope assignments

What to look for: Does the captured lesson match what you learned? Did the handoff preserve context? Is the review gate actually human-controlled?

---

## The lexical ceiling (scope boundary)

**CGG is the portable lexical governance layer.** File-based lifecycle, human-gated promotion, auditable tic/signal trails, and jurisdictional scoping via zones.

**CGG expands lexical capabilities further than most approaches** by separating governance from storage/retrieval. But **text has a ceiling**: lesson corpora grow, nested projects add weight, and walls of text dilute force.

**Mitigations built in:** scoped zones (`.ticzone`, `.ticignore`), the abstraction ladder, signal decay, and human curation during `/review`. They extend the useful range; they don't remove the ceiling.

**Beyond the ceiling:** expression gating, conformation-aware retrieval, graph topology, economic pressure, and compiled constraints live outside this repo. CGG stays flat-file and auditable; when you need those capabilities, CGG's primitives become the audit trail under a substrate such as Ubiquity. The governance lifecycle stays the same.

---

## Two types of lessons

CGG captures rationale at two layers — both are valid governance artifacts:

**Subject-matter lessons** — truths about the system being built:
- Bug patterns, API quirks, architecture constraints
- System invariants, policy rules
- "This API returns 204 on success, not 200"

**Collaboration lessons** — truths about effective human-agent coordination:
- Prompting patterns that reduce drift
- Debugging rhythms, TDD work loops
- "When delegating multi-step tasks, include explicit abstraction-level scoping"

Both climb the abstraction ladder. Both pass through the same human gate. Constitutional governance must govern both the technical environment and the process that operates within it.

### A real collaboration example

A human operator used theory-of-mind reasoning to work more effectively with an agent called Homeskillet.

The operator observed:
- Homeskillet was strong at structural reasoning
- Weaker when instructions depended on implicit assumptions
- Vulnerable to conceptual drift when prompts were under-scoped

So the operator started prompting with a short theory-of-mind preface:
- What the agent is strong at
- Where the agent tends to drift
- Which assumptions must be explicit
- What abstraction level the task requires

That improved performance.

After several cadence cycles, the system itself surfaced the technique as a governance candidate:

> "When constructing subagent prompts, include a short theory-of-mind preface describing the agent's inferred strengths and limitations. This reduces conceptual drift and improves task alignment."

That lesson later appeared in how Homeskillet and related agents wrote and used subagent prompts -- including warnings about pitfalls according to inferred conceptual strengths and limits.

This is not a rule about the codebase. It is a rule about effective human-agent cognition in context. And it is just as valid a CogPR candidate as any API quirk or architecture constraint.

### Why CGG exists

Organizations running persistent AI systems hit a specific set of problems that better models don't solve:

- **Behavioral drift over time.** Agents gradually contradict their own constraints as context windows fill and rotate.
- **No rule evolution pathway.** When an agent discovers a better way to operate, the insight dies with the session. Manually updating system prompts doesn't scale.
- **Invisible blast radius.** When an agent's behavior changes, there's no audit trail showing what changed, when, why, or who approved it.
- **Cross-system incoherence.** Multiple agents in the same domain have no way to share validated lessons or coordinate on discovered constraints.
- **Jurisdictional ambiguity.** In regulated or multi-team environments, you can't define which agents can hear which signals, or which rules apply in which scope.

CGG addresses these through five structural mechanisms: the abstraction ladder (scoped rule tiers), the epoch boundary (context rotation discipline), the human constitutional gate (approval-gated promotion), the signal manifold (runtime condition monitoring), and the tic/tic-zone system (canonical ordering and jurisdictional scoping).

A constitutional governance loop wraps the entire system: experience generates proposals, proposals require human review, review produces promotion or rejection, and the operating constitution updates accordingly. Humans author law. Agents execute within it.

## Constitutional learning loops (Mermaid)

```mermaid
flowchart TB
    subgraph Fast["Fast loop — active session"]
        Work[Work session] --> Capture[Capture CogPR + signals]
        Capture --> Cadence[/`/cadence` end-of-session/]
    end

    Cadence --> Plan[Plan with trigger]
    Plan --> Assessor[Background ripple-assessor]
    Assessor --> Proposals[Proposals file]

    subgraph Gate["Human gate — constitutional review"]
        Proposals --> Review[/`/review` docket/]
        Review -->|approve| Promote[Promote scope (Site→...→Global)]
        Review -->|reject/modify| Iterate[Refine lesson or handler]
    end

    Promote --> Manifest[Manifest in CLAUDE.md + runtime hooks]
    Manifest --> SessionRestore[Next session restore]
    SessionRestore --> Work

    Manifest --> Signals[Runtime signals]
    Signals -->|threshold| Warrant[Warrant minted]
    Warrant --> Review
    Signals -.background pressure.- Cadence
```

## The abstraction ladder

Knowledge in CGG lives on a scope hierarchy. We call it the abstraction ladder because lessons climb it -- and sometimes descend it.

### Rungs

**Site** -- a lesson at the project root's `CLAUDE.md` or `MEMORY.md`. True across this codebase. The default working rung — most lessons live here. Example: "Our Redis connections use a shared pool -- never open individual connections in request handlers."

**Domain** -- cross-module within a site. Useful when a project has distinct subsystems (e.g., `crates/` vs `src/`). A lesson valid in the Rust crates but not the TypeScript layer lives at domain scope.

**Estate** -- cross-project governance. When multiple repos share an operator or team, estate scope covers the shared surface. Example: "All projects under this operator use the same tic-zone naming convention."

**Federation** -- cross-organization. When multiple estates coordinate (e.g., a vendor and a client sharing governance primitives). Rare; most users never need this rung.

**Global** -- a lesson promoted to `~/.claude/CLAUDE.md`. True across every project on the machine. This is a treaty, not a convenience. Example: "LiteLLM embedding calls require the provider prefix on the model name even when api_base is set."

Lessons are born locally — written to the nearest `MEMORY.md` from wherever the agent is working (born truth). The site rung is where they first become reusable rules. Most users only interact with site and global; the intermediate rungs exist for multi-project governance.

### Climbing: site to global

A lesson climbs when a CogPR is approved through `/review`. The ripple assessor checks scope correctness -- a Redis connection pattern specific to one site shouldn't become global law. Promotion requires evidence:

- At least 2 full pipeline cycles for global scope
- Cross-validation where relevant -- does the lesson hold in other projects?
- No schema churn that would invalidate it next week

The governance invariant: the system must be willing to refuse premature promotion even when the lesson is accurate. An accurate lesson with immature validation stays at site scope until it earns its way up. The first test of whether the system actually governs is whether it can say "not yet."

Two maturity gates formalize this: a temporal gate (`tic_gated`) that holds a proposal until it has survived a minimum number of conformations, and an epistemic gate (`enrichment_eligible`) that holds it until sibling cross-reference or inversion testing has been done. See [ARCHITECTURE.md](ARCHITECTURE.md#9-cpr-maturity-fields-concrete-spec) for the field spec.

### Descending: global to local

This is the less obvious direction, and it matters more than it appears.

A global lesson carries a core signal -- the primitive, the actual thing that's true. But how that truth expresses itself differs by site. When a global lesson lands in a new site context, it often needs a site-level specialization: same core signal, site-specific expression.

Example: a global lesson says "always validate embedding dimensions before similarity computation." At Site A, that's a NumPy shape check in Python. At Site B, it's a dimension guard before `iter().zip()` in Rust -- because Rust's zip silently truncates mismatched iterators and produces wrong results without an error. The primitive is identical. The expression is specialized.

This downstream flow keeps the ladder honest. Global lessons stay concrete because their site-level expressions test them against real codebases. If a global lesson can't produce a useful specialization at a new site, it probably shouldn't be global. The bottom keeps the top sharp.

```mermaid
%%{init: {'theme': 'dark', 'flowchart': {'padding': 24, 'rankSpacing': 60, 'nodeSpacing': 40}, 'themeVariables': {'primaryColor': '#4361ee', 'primaryTextColor': '#f8f9fa', 'primaryBorderColor': '#6c757d', 'lineColor': '#4895ef', 'secondaryColor': '#1a1a2e', 'tertiaryColor': '#16213e', 'edgeLabelBackground': '#1a1a2e', 'clusterBkg': '#16213e', 'clusterBorder': '#3d3d3d'}}}%%
flowchart TB
    subgraph GLOBAL["Global scope -- ~/.claude/CLAUDE.md"]
        direction LR
        G1(("Core signal<br/>the primitive"))
        G2["Treaty-level law<br/>applies everywhere"]
        G1 ------ G2
    end

    subgraph SITE_A["Site A"]
        direction TB
        PA1["Site CLAUDE.md<br/>validated for this codebase"]
        PA2["Local MEMORY.md<br/>born here, file-specific"]
        PA2 -. "CogPR approved<br/>via /review" .-> PA1
    end

    subgraph SITE_B["Site B"]
        direction TB
        PB1["Site CLAUDE.md<br/>validated for this codebase"]
        PB2["Local MEMORY.md<br/>born here, file-specific"]
        PB2 -. "CogPR approved<br/>via /review" .-> PB1
    end

    subgraph SITE_C["Site C -- new repo"]
        direction TB
        PC1["Site CLAUDE.md<br/>specialized expression"]
        PC2["Local discovery<br/>same primitive, new form"]
        PC2 -. "validates global<br/>lesson locally" .-> PC1
    end

    PA1 == "Promotion<br/>2+ cycles validated" ===> GLOBAL
    PB1 -. "Candidate<br/>pending validation" ..-> GLOBAL
    GLOBAL == "Specialization<br/>core signal descends" ===> PC1
    GLOBAL -. "Informs but<br/>does not dictate" ..-> PA1
    GLOBAL -. "Informs but<br/>does not dictate" ..-> PB1

    classDef global fill:#0f3460,stroke:#4cc9f0,color:#f8f9fa,stroke-width:2px
    classDef site fill:#1a1a2e,stroke:#4361ee,color:#f8f9fa
    classDef local fill:#2d2d2d,stroke:#6c757d,color:#e0e0e0
    classDef core fill:#533483,stroke:#4cc9f0,color:#f8f9fa,stroke-width:2px

    class G1 core
    class G2 global
    class PA1,PB1,PC1 site
    class PA2,PB2,PC2 local
```

### The unified flow: how knowledge survives context death

The system runs three loops at different speeds. The **fast loop** is your working session -- implement, debug, verify. The **medium loop** is site memory, where validated lessons accumulate across sessions. The **slow loop** is global memory, where universal invariants settle after enough cross-site validation. The 100k token cycle destroys the local context window, but because the CogPR buffer feeds site and global memory asynchronously, knowledge arcs over the destruction event and cascades into the next session.

```mermaid
graph TB
    classDef session fill:#2a4365,stroke:#2b6cb0,color:#e2e8f0,stroke-width:2px
    classDef project fill:#2c5282,stroke:#4299e1,color:#e2e8f0,stroke-width:2px
    classDef global fill:#1a365d,stroke:#63b3ed,color:#e2e8f0,stroke-width:3px
    classDef trigger fill:#7b341e,stroke:#ed8936,color:#fff,stroke-width:2px
    classDef human fill:#276749,stroke:#48bb78,color:#fff,stroke-width:2px

    %% Session Layer - Fast Loop
    S1["Session 1<br/>Design → Implement → Verify"]:::session
    S2["Session 2<br/>Design → Implement → Verify"]:::session
    S3["Session 3<br/>Design → Implement → Verify"]:::session

    %% Session Controls
    T1["Session getting long<br/>~100k tokens"]:::trigger
    T2["Session getting long<br/>~100k tokens"]:::trigger
    Cycle1["/cadence"]:::trigger
    Cycle2["/cadence"]:::trigger

    %% CogPR Buffer - Continuous
    CogPR1["CogPR Buffer<br/>(Friction Detection)"]:::session
    CogPR2["CogPR Buffer<br/>(Friction Detection)"]:::session

    %% Evaluation Layer
    Assess1["Ripple Assessor<br/>(Background Eval)"]:::project
    Assess2["Ripple Assessor<br/>(Background Eval)"]:::project

    %% Human Review
    Review["/review<br/>Human Review"]:::human

    %% Site Layer - Medium Loop
    ProjMem["Site Memory<br/>(Accumulated Primitives)"]:::project

    %% Global Layer - Slow Loop
    GlobalMem["Global Memory<br/>(Universal Invariants)"]:::global

    %% Bidirectional Knowledge Flow
    LocalObs["Raw Observations"]:::session

    %% Session 1 Flow
    S1 -->|Continuous| CogPR1
    S1 --> T1
    T1 -->|"natural stopping point"| Cycle1
    Cycle1 --> Assess1
    Assess1 --> Review

    %% Session 2 Flow
    Review -->|Approve & Merge| S2
    S2 -->|Continuous| CogPR2
    S2 --> T2
    T2 -->|"natural stopping point"| Cycle2
    Cycle2 --> Assess2
    Assess2 --> Review

    %% Session 3 Flow
    Review -->|Approve & Merge| S3

    %% Upward Abstraction
    CogPR1 -->|Extract Patterns| ProjMem
    CogPR2 -->|Extract Patterns| ProjMem
    ProjMem -->|Validate Universality| GlobalMem

    %% Downward Specialization
    GlobalMem -.->|Cascade Truths| ProjMem
    ProjMem -.->|Specialize Rules| S2
    ProjMem -.->|Specialize Rules| S3

    %% Continuous Feedback
    S1 -->|New Discoveries| LocalObs
    S2 -->|New Discoveries| LocalObs
    S3 -->|New Discoveries| LocalObs
    LocalObs -.->|Feed Upward| CogPR1
    LocalObs -.->|Feed Upward| CogPR2

    %% Async Signals
    CogPR1 -.->|Async| Assess1
    CogPR2 -.->|Async| Assess2
```

The `/review` human review isn't just a safety check -- it's the epoch boundary. It marks the moment where Session N's raw discoveries become Session N+1's upgraded starting state. The agent should have amnesia after the context flush. It doesn't, because the abstraction ladder carried the knowledge through.

### The 4/4 cadence

Four beats, steady time:

| Beat | Action | What happens |
|------|--------|-------------|
| 1 | **Work** | Implement, debug, ship. Lessons are a side effect of real work. |
| 2 | **Capture** | `/cadence` before context degrades -- 100k tokens is a good heuristic, not a hard boundary. Tic emitted, handoff written, CogPRs staged. |
| 3 | **Evaluate** | Between sessions, ripple assessor runs automatically. No human involvement. |
| 4 | **Review** | `/review` when the queue warrants it -- every 2-4 sessions, not every session. |

You might run beats 1 and 2 three times before doing beat 4. The review cadence is driven by proposal density, not a fixed schedule. The agent learns at project level on its own between beats 1 and 3. You shape what sticks and what climbs during beat 4.

If you're past the heuristic and the session feels sluggish, `/cadence double-time` produces a valid handoff with minimal ceremony -- tic + compact plan, no signal tick or conformation snapshot. Recovery: next session runs a full downbeat.

## Governance truth surfaces

**Tags are authoring. Queue is execution. Audit logs are history.**

Tags (`<!-- --agnostic-candidate -->` blocks in CLAUDE.md/MEMORY.md) are the human-readable capture format. The CogPR queue (`audit-logs/cprs/queue.jsonl`) is the machine-readable execution surface -- hooks extract tags into it, assessors advance entries through the lifecycle, `/review` applies verdicts from it. Audit logs (signals, tics, conformations, reviews) are append-only history. If a tag and a queue entry disagree, the queue wins. See [ARCHITECTURE.md §11](ARCHITECTURE.md) for the full data model.

## Signal architecture

Alongside the lesson lifecycle, CGG runs a parallel signal system for runtime conditions. These aren't lessons to promote -- they're states to monitor.

### Primitives

**Whisper** -- a micro-correction injected at runtime to prevent immediate failure. Low-latency, local, ephemeral.

**Siren** -- a continuous signal with volume that accrues over time. When the same friction point appears across sessions, the signal gets louder. Propagation follows an acoustic model: volume at source minus distance-based muffling. Signals below a target's hearing threshold exist in the manifold but don't interrupt.

**Warrant** -- minted automatically when a signal's volume crosses threshold, or when three signal types converge within 24 hours. BEACON + LESSON + TENSION in the same window is a "harmonic triad" -- auto-escalation without volume accrual. Warrants are obligations, not suggestions.

**CogPR** -- the lesson primitive. Discrete, reviewable, promotable. Covered above.

**Chorus** -- post-failure compression into durable institutional memory. Slow, synthesizing. "Don't repeat this class of failure."

### Frequency bands

| Band | Propagation | Use |
|------|-------------|-----|
| PRIMITIVE | Always audible, never fully muffled | Safety, data integrity, survival |
| COGNITIVE | Standard working level | Lessons, insights, process fixes |
| SOCIAL | High muffling, suppressed | Coordination between agents |
| PRESTIGE | Auto-muted, blocked by governance | Never optimized for |

PRESTIGE exists to be blocked. Any signal that would accrue reputation or status is filtered. The system optimizes for truth propagation, not clout.

### Quiet rail principle

Most of this runs silently. Signals accrue volume, assessors run between sessions, proposals queue up -- none of it interrupts the developer. You see the system only during `/review`. Everything else is auditable after the fact but invisible during work.

Less an alert system than a geological survey: instruments always recording, data read when you choose to.

### Tic (canonical clock primitive)

A tic is both a timestamp and a sequence number.

A timestamp tells you *when* something happened. A monotonic counter tells you *in what order*. Tics provide both -- an ISO-8601 timestamp paired with project and global sequence counters. Three audit capabilities follow:

- **Temporal**: "What did the system know at 2026-02-24T21:15:00?"
- **Sequential**: "What happened between tic 42 and tic 47, regardless of wall-clock time?"
- **Cross-cadence**: "Agent A's tic #3 occurred between Agent B's tic #41 and #42" -- even though they run on completely different rhythms.

Different systems emit tics at different cadences. A Claude Code agent downbeats at the 100k token mark. An Agent Zero superintendent downbeats at monologue boundaries. A cron job downbeats on a fixed schedule. None share a rhythm, but they all share the tic sequence. The tic counter is the total ordering that makes syncopated cadences commensurable.

Every `/cadence` emits a tic. Tics accumulate at two scopes:
- **Project tic counter**: derived by counting `"type": "tic"` entries in `audit-logs/tics/*.jsonl`
- **Global tic counter**: `~/.claude/cgg-tic-counter.json` -- simple `{"count": N, "last_tic": "ISO-8601"}`

Tic record format (appended to `audit-logs/tics/YYYY-MM-DD.jsonl`):
```json
{
  "type": "tic",
  "tic": "2026-02-24T21:15:00-05:00",
  "tic_zone": "operationTorque-estate",
  "cadence_position": "downbeat"
}
```

Tics are stored separately from signals (`audit-logs/tics/`, not `audit-logs/signals/`). The clock is not a signal -- tics are exempt from decay, muffling, volume accrual, and warrant triads.

### Tic-zone (acoustic region)

A tic-zone is a named acoustic region defined by a `.ticzone` file (JSONC -- `//` comments and trailing commas accepted) at the zone root. It defines the acoustic space for banded communications. All systems within a zone share the tic primitive regardless of cadence position.

```jsonc
{
  "name": "operationTorque-estate",
  "tz": "America/Toronto",
  "lat": 43.6532,
  "lon": -79.3832,
  "include": [".", "~/.claude"],
  "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL", "PRESTIGE"],
  "muffling_per_hop": 5
}
```

- `name`: Zone identifier used in tic records and acoustic routing.
- `tz`: IANA timezone. Maps the zone to Earth's temporal grid.
- `lat`/`lon`: Optional geographic coordinates for future spatial coupling.
- `include`: Paths belonging to this zone. Relative paths resolved from `.ticzone` location.
- `bands`: Active frequency bands in this zone.
- `muffling_per_hop`: Acoustic muffling constant for the zone's distance model.

#### `.ticignore` (exclusion filter)

A `.ticignore` file at the zone root excludes paths from the governance surface. Gitignore-style directory patterns. v1 supports directory exclusions only -- no glob wildcards, no file-level patterns. This is a documented constraint, not a missing feature.

Signals originating from ignored paths are not routed. CogPR scans skip ignored directories. The zone scan rule is: zone boundary first (`.ticzone` defines what's in), ignore second (`.ticignore` removes what's out).

MEMORY.md files are gitignored but NOT ticignored -- they hold active governance data (pending CogPRs, operational memory).

> **Zone scan rule** (shared across all scan points):
> 1. Resolve project root via nearest `.ticzone`
> 2. Governance surface = `**/CLAUDE.md` + `**/MEMORY.md` inside the zone + auto-memory
> 3. Exclude paths matching `.ticignore` (default: vendor/, node_modules/, .git/, .claude/skills/)
> 4. Skip `status: "example"` blocks (documentation templates)

Zone nesting: a `.ticzone` in a subdirectory creates a nested zone inheriting the parent's `tz` and `bands` unless overridden. Muffling crosses zone boundaries at 2x the per-hop rate.

### System conformation

At any tic boundary, the total state of a CGG-governed system forms a conformation: active signals, pending CogPRs, minted warrants, drift measurements, zone membership, and rules in force at each scope tier.

Between tic N and tic N+1, environmental pressure -- work, friction, discovery -- shifts the conformation. Most shifts are small: a local lesson captured, a signal volume incremented. Some are fold events: a warrant mints from a harmonic triad, or a promoted global rule reshapes how every downstream project operates.

The tic sequence makes this replayable. Reconstruct the system's exact conformation at any tic boundary, diff it against the previous one, trace what caused the transition. An engineer reads this as "what changed between sessions." A compliance officer reads it as "what rules were in force when this decision was made." The system reads it as "what shape am I in."

The sequence is the primary structure. Signals, warrants, and CogPRs are side chains. Bands are charge groups. Acoustic routing is the solvent. The conformation at any given tic is the folded shape of the system under accumulated pressure.

## Applicability

CGG is model-agnostic and host-agnostic. Claude Code is the current primary host, but the primitives -- flat-file signal stores, append-only JSONL, YAML/JSONC config, human-gated promotion -- port to any agent framework.

### Engineering teams

The CI/CD mental model is intentional. CogPRs are pull requests for agent behavior, not codebases. The ripple assessor is the CI runner. `/review` is code review. Engineers already know these workflows -- CGG maps directly onto them.

### Regulated industries

In fintech, healthcare, defense, and legal, AI behavioral changes require documented approval chains. CGG gives you an audit trail where every rule change is a CogPR with a reviewable diff, approval timestamp, and scope designation, and every epoch boundary emits a sequenced tic. Scoped memory tiers contain blast radius -- a lesson validated at one site cannot silently propagate to another without climbing the abstraction ladder through human gates. Tic-zones map jurisdictions: which agents operate in which acoustic regions, which bands are active, how signals attenuate across boundaries.

### Public sector

Government AI deployments face constraints around transparency, epoch management, and compartmentalization. All CGG state lives in flat, human-readable files -- no databases to subpoena, no APIs to query, `git log` as the audit tool. Tic counters and epoch boundaries map cleanly to fiscal years, legislative sessions, and administration changes, with rules version-controlled per epoch. Tic-zones enforce that signals from one agency's agents cannot propagate into another agency's acoustic space without explicit zone inclusion. The human approval requirement for rule promotion mirrors a basic principle: AI systems execute policy, they do not make it.

### Multi-agent coordination

When multiple agents operate in the same domain with different cadences, CGG provides the shared clock (tics), shared jurisdiction (zones), and shared governance (the abstraction ladder) that prevent drift into incoherence. Each agent keeps its own rhythm. The tic sequence keeps them synchronized without coupling them.

## Where CGG fits

CGG is a compact, portable governance lifecycle. Install it in 30 seconds, get value from session 1. Three commands. Zero dependencies.

CGG guarantees:
- File-based governance lifecycle (capture, evaluate, promote, audit)
- Human-gated rule promotion at every scope boundary
- Auditable signal/tic trails with total ordering
- Claude Code automation via hooks (when installed)
- Jurisdictional scoping via zones and exclusion filters

CGG does NOT provide (and deliberately avoids):
- Conformation-aware retrieval engines (load only what matches current system shape)
- Expression gating across timescales (silence irrelevant lessons based on context)
- Graph topology for relational memory (edges between concepts, not flat lists)
- Endogenous economics (cost models for governance operations)
- Compiled execution-boundary enforcement (constraints the agent cannot violate)

These are classes of capability that require infrastructure CGG deliberately avoids. When you hit the ceiling, you'll know -- the symptoms are described in [ARCHITECTURE.md](ARCHITECTURE.md#6-scaling-ceiling). No external repos required. The flat-file primitives become the audit trail beneath whatever substrate you adopt.

### When CGG stops being enough

You'll feel the ceiling when:
- Signals exceed a few hundred entries and dedup becomes slow
- Lessons span many files and grep stops finding the right thing
- You need "closest historical failure mode," not "keyword overlap"
- Rule stores grow monotonically and deeply nested projects accumulate heavy lesson loads

Deeper substrate layers that extend CGG: semantic recall (embeddings), graph topology (relational memory), expression gating (methylation/dormancy), and conformation-aware retrieval (shape matching). Same governance lifecycle underneath -- the flat-file primitives become the audit trail beneath the substrate.

See [ARCHITECTURE.md](ARCHITECTURE.md#6-scaling-ceiling) for the full design rationale and upgrade path.

### Measuring impact

Three numbers that tell you whether CGG is compounding or just accumulating:

1. **Repeat-mistake rate** -- declining = lessons are landing
2. **Time-to-resume** -- shrinking = handoffs are working
3. **Promotion ROI** -- promoted rules that prevent future incidents = compounding

## Packages

### `cogpr/` -- Cognitive Pull Request conventions

The convention layer. Markdown standards for flagging lessons and reviewing promotions. Works in Claude Code, Claude Desktop, and Claude for Work.

| Variant | Path | What it does |
|---------|------|-------------|
| Claude Code | `cogpr/claude-code/` | Skills with YAML frontmatter |
| Claude Desktop | `cogpr/claude-desktop/` | Project instructions snippet |
| Claude for Work | `cogpr/claude-work/` | Project instructions snippet |

### `cgg-runtime/` -- Trigger pipeline

Claude Code only. Automation connecting lesson capture to evaluation to review.

| Component | Purpose |
|-----------|---------|
| `hooks/cgg-gate.sh` | One-shot gate on first prompt |
| `hooks/session-restore-patch.sh` | Plan discovery and trigger extraction |
| `agents/ripple-assessor.md` | Fresh evaluator agent |
| `skills/` | `/cadence`, `/review`, `/siren` |

## Installation

### Claude Code -- full pipeline

Paste the bootstrap prompt into Claude Code. It asks one question (install mode), then sets everything up -- submodule, skills, hooks, agents, wiring. See [INSTALL.md](INSTALL.md) for the exact prompt.

### Claude Desktop / Claude for Work

Copy `cogpr/claude-desktop/project-instructions.md` into your project's custom instructions. Convention layer only -- CogPR flagging and manual review, no automated pipeline.

## Safety

All promotions require human approval through `/review`. Protected files like `~/.claude/CLAUDE.md` require extra confirmation. Trigger blocks are structured data with whitelisted keys, not executable instructions. Each handoff is processed at most once. Project scoping prevents cross-project bleed.

## License

MIT

## Maintainers

**[Prompted LLC](https://promptedllc.com)** -- creators of the Ubiquity governance substrate.

Breyden Taylor, Founder & Architect -- [LinkedIn](https://www.linkedin.com/in/breyden-taylor/) | breyden@prompted.community

Contributions welcome.
