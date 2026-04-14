<p align="center">
  <img src="assets/cgg-banner.jpeg" alt="Context Grapple Gun by Prompted LLC & Ubiquity OS" width="100%" />
</p>

# Context Grapple Gun

**Persistent context and cognitive pull requests for Claude Code.**

*Context. Gates. Cognitive pull requests.*

CGG stops Claude Code from relearning the same lessons every session.
It captures hard-won discoveries from real work, routes them through human review, promotes them along an abstraction ladder, and hydrates them back into future sessions without confusing rendered context with constitutional source of truth.

Three commands. Auditable files. No service required.

---

**You only need four things to start:**
- Three commands: `/cadence`, `/review`, `/siren`
- Run `/cadence` to end every session cleanly; run `/review` every few sessions to approve lessons
- Scope ladder: Site > Domain > Estate > Federation > Global -- you decide what promotes
- Install: `npx context-grapple-gun install` -- or see [INSTALL.md](INSTALL.md) for details

---

## Read this first (by intent)

| You want to... | Start here |
|----------------|------------|
| **Install now** | `npx context-grapple-gun install` -- zero-thought entry, handles everything |
| **Use it now** | [START-HERE.md](START-HERE.md) -- the three commands, a normal day, what to expect |
| **Understand the pipeline** | [DEV-README.md](DEV-README.md) -- session flow, hook lifecycle, extraction pipeline |
| **Evaluate the architecture** | [ARCHITECTURE.md](ARCHITECTURE.md) -- signal manifold, acoustic model, governance layers |
| **Audit recent changes** | [docs/COMMIT-HISTORY-CHEATSHEET.md](docs/COMMIT-HISTORY-CHEATSHEET.md) |
| **Learn through story** | [academy/README.md](academy/README.md) -- five chapters, real simulations, one very persistent goat |
| **All install options** | [INSTALL.md](INSTALL.md) -- npm, plugin, bootstrap, manual, academy |

---

## 90-second mental model

**The problem:** AI agents discover truths during work -- bug patterns, API quirks, coordination techniques that work. When the session ends, that knowledge vanishes. Next session: same agent, same repo, zero memory of what it learned.

**The CGG answer:** Lessons get captured as they happen, reviewed between sessions, and promoted to broader scopes with human approval at every gate. The project's operating rules grow from real work, not from someone writing documentation.

**Three commands run the lifecycle:**

| Command | What it does |
|---------|--------------|
| `/cadence` | End of session. Saves lessons, emits a tic (sequenced timestamp), writes a handoff for the next session. |
| `/review` | Review proposed lessons. Approve, reject, or modify before promotion. |
| `/siren` | Check on recurring friction. See what signals are building, what warrants have minted. |

**Why this compounds instead of just accumulating:**

| Mechanism | What it does |
|-----------|--------------|
| Scoped gates | Every promotion requires explicit approval. The agent proposes; you decide what scope it reaches. |
| Abstraction ladder | Scope hierarchy: site > domain > estate > federation > global. Lessons climb through review, not drift. |
| Hydration boundary | Rendered working context is never confused with constitutional source of truth. Lessons hydrate back into sessions from their authoritative files. |
| Cognitive pull requests | Proposed lessons are captured as CogPRs — structured, reviewable units that strip contextual noise before promotion. |
| Signal manifold | Recurring friction accrues volume, crosses thresholds, mints warrants. You see what keeps coming up. |

**One scale boundary:**

CGG is the governance lifecycle. It uses flat files, git-tracked, auditable by default. When flat files aren't enough -- when you need semantic recall, graph topology, or conformation-aware retrieval -- the substrate layer (Ubiquity) picks up where CGG leaves off. Same governance primitives, deeper infrastructure. CGG is complete without Ubiquity. Ubiquity composes on top when scale demands it.

---

## What CGG is not

- **Not a vector database.** No embeddings, no semantic search. Flat files and grep.
- **Not a magical memory layer.** Lessons require human review to promote. Nothing persists without approval.
- **Not a full substrate.** CGG handles governance lifecycle. Substrate capabilities (expression gating, graph topology, compiled constraints) require infrastructure CGG deliberately avoids.
- **Not a hosted platform.** Everything runs locally. No APIs, no services, no cloud dependencies.

---

## Core terms (with neutral aliases)

On first encounter, CGG terminology maps to familiar systems concepts:
- **CogPR** -- behavior pull request: a proposed lesson flagged for review and promotion
- **Hydration boundary** -- source-of-truth separation: constitutional files (CLAUDE.md, MEMORY.md) are authoritative; rendered working context is downstream
- **Abstraction ladder** -- scope hierarchy: Site > Domain > Estate > Federation > Global; lessons climb through `/review`
- **Scoped gates** -- human approval at every scope transition; nothing promotes without explicit review
- **tic** -- sequenced timestamp: ISO-8601 + monotonic counter for total ordering
- **siren > warrant** -- recurring friction signal that mints an escalation when it crosses threshold

Full glossary: [docs/TERMINOLOGY.md](docs/TERMINOLOGY.md).

---

## Skeptic's evaluation path

**~20 minutes to informed judgment.**

1. **Read:** This section + [START-HERE.md](START-HERE.md) (~5 min)
2. **Install:** `npx context-grapple-gun install` -- 10 seconds
3. **Run:** Start a session, do some work, run `/cadence` at the end
4. **Inspect:** Look at `audit-logs/` -- see the tic records, signal files, CogPR blocks
5. **Review:** Next session, run `/review` -- see the docket, the verdicts, the scope assignments

What to look for: Does the captured lesson match what you learned? Did the handoff preserve context? Is the review gate actually human-controlled?

---

## Why CGG exists

Organizations running persistent AI systems hit a specific set of problems that better models don't solve:

- **Behavioral drift over time.** Agents gradually contradict their own constraints as context windows fill and rotate.
- **No rule evolution pathway.** When an agent discovers a better way to operate, the insight dies with the session. Manually updating system prompts doesn't scale.
- **Invisible blast radius.** When an agent's behavior changes, there's no audit trail showing what changed, when, why, or who approved it.
- **Cross-system incoherence.** Multiple agents in the same domain have no way to share validated lessons or coordinate on discovered constraints.
- **Jurisdictional ambiguity.** In regulated or multi-team environments, you can't define which agents can hear which signals, or which rules apply in which scope.

CGG addresses these through five structural mechanisms: the abstraction ladder (scoped rule tiers), the epoch boundary (context rotation discipline), the human constitutional gate (approval-gated promotion), the signal manifold (runtime condition monitoring), and the tic/tic-zone system (canonical ordering and jurisdictional scoping).

---

## Where CGG fits

CGG is a compact, portable governance lifecycle. `npx context-grapple-gun install` and get value from session 1. Three commands. Zero runtime dependencies.

CGG guarantees:
- File-based governance lifecycle (capture, evaluate, promote, audit)
- Human-gated rule promotion at every scope boundary
- Auditable signal/tic trails with total ordering
- Claude Code automation via hooks (when installed)
- Jurisdictional scoping via zones and exclusion filters

CGG does NOT provide (and deliberately avoids):
- Conformation-aware retrieval engines
- Expression gating across timescales
- Graph topology for relational memory
- Endogenous economics
- Compiled execution-boundary enforcement

These are classes of capability that require infrastructure CGG deliberately avoids. When you hit the ceiling, you'll know -- the symptoms are described in [ARCHITECTURE.md](ARCHITECTURE.md#6-scaling-ceiling).

---

## Measuring impact

Three numbers that tell you whether CGG is compounding or just accumulating:

1. **Repeat-mistake rate** -- declining = lessons are landing
2. **Time-to-resume** -- shrinking = handoffs are working
3. **Promotion ROI** -- promoted rules that prevent future incidents = compounding

---

## Safety

All promotions require human approval through `/review`. Protected files like `~/.claude/CLAUDE.md` require extra confirmation. Trigger blocks are structured data with whitelisted keys, not executable instructions. Each handoff is processed at most once.

Zone-local governance scoping prevents cross-project bleed. Global runtime installation does not make project governance global. Rules still route through the project's zone boundary and ladder.

---

## License

MIT

## Maintainers

**[Prompted LLC](https://promptedllc.com)** -- creators of the Ubiquity governance substrate.

Breyden Taylor, Founder & Architect -- [LinkedIn](https://www.linkedin.com/in/breyden-taylor/) | breyden@prompted.community

Contributions welcome.
