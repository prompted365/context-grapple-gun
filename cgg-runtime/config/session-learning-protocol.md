<!-- cgg-session-learning-protocol:v5 -->
## Session Learning Protocol (CGG)

CGG separates **born truth**, **in-force truth**, and **loaded runtime**.

- Capture a durable lesson as a CogPR in the relevant `MEMORY.md` or another declared born-truth surface.
- Do not write a lesson into `CLAUDE.md` merely because it was observed. `CLAUDE.md` is an in-force governance surface; promotion requires the human `/review` gate.
- `/cadence` owns the epoch boundary: it emits the canonical tic, seals the handoff, and leaves a resumable next state. It does not become the memory writer, signal emitter, CogPR extractor, assessor, or review authority.
- `/review` is the constitutional judgment surface. Agents may prepare evidence and recommend disposition; only the named human authority may approve a durable promotion.
- `/siren` owns signal inspection and recurring-friction operations. Signal visibility is not promotion authority.
- Canonical source, installed copy, and loaded runtime are distinct states. The loaded runtime governs current behavior; canonical source expresses intent until installation and verification complete.

### CogPR shape

Record the lesson inline, then add a bounded candidate block:

```markdown
<!-- --agnostic-candidate
  lesson: "one-line durable lesson"
  source_date: "YYYY-MM-DD"
  source: "file:line or receipt reference"
  band: "COGNITIVE"
  motivation_layer: "COGNITIVE"
  subsystem: "relevant_subsystem"
  recommended_scopes:
    - "path/to/broader/CLAUDE.md"
  rationale: "why the lesson should travel beyond its birth surface"
  review_hints: "what must be checked at /review"
  status: "pending"
-->
```

### Band boundary

| Band | Use |
|---|---|
| `PRIMITIVE` | Safety, survival, data-integrity, and irreversible-harm constraints |
| `COGNITIVE` | Learning, discovery, process improvement, and verified operating patterns |
| `SOCIAL` | Collaboration and coordination signals, used narrowly |
| `PRESTIGE` | Governance-blocked. Never emit or activate as a normal band. |

End a real session with `/cadence`. Use `/cadence double-time` only for a degraded-context emergency exit. Run `/review` when the docket is ready; do not silently promote from capture, cadence, assessment, or installation lanes.
<!-- /cgg-session-learning-protocol:v5 -->
