<!-- CGG:SESSION-LEARNING-PROTOCOL:START -->
## Session Learning Protocol (CGG)

CGG separates three states that must not silently collapse:

- **born truth** — a durable observation captured near the work;
- **proposed learning** — a CogPR awaiting evaluation and human review;
- **in-force truth** — a rule that has been explicitly promoted to an authorized scope.

### Capture durable lessons

When work reveals a durable, non-obvious lesson, record it in the nearest relevant `MEMORY.md` as born truth. Do not write directly into `CLAUDE.md` unless the human has authorized a law change.

Place this structured candidate immediately after the lesson:

```yaml
<!-- --agnostic-candidate
  lesson: "one-line lesson summary"
  source_date: "YYYY-MM-DD"
  source: "file:line or artifact reference"
  band: "COGNITIVE"
  motivation_layer: "COGNITIVE"
  subsystem: "relevant_subsystem"
  recommended_scopes:
    - "path/to/broader/CLAUDE.md"
  rationale: "why this may travel beyond the local source"
  review_hints: "what must be checked before promotion"
  status: "pending"
-->
```

### Command ownership

- `/cadence` is the epoch boundary. It emits the canonical tic, seals the handoff, and leaves a resumable state. It does not independently promote learning or mutate doctrine.
- `/review` is the human constitutional gate. Proposed lessons and warrants do not become in-force truth without explicit review.
- `/siren` owns signal visibility and recurring-friction operations.

### Band budget

| Band | Use for |
|---|---|
| `PRIMITIVE` | Safety, data integrity, survival, and non-negotiable execution constraints |
| `COGNITIVE` | Learning, discovery, and process improvement (default) |
| `SOCIAL` | Collaboration and coordination signals, used deliberately |
| `PRESTIGE` | Governance-blocked. Never emit or promote from this band. |

### Scope and authority

Lessons may travel through Site → Domain → Estate → Federation → Global only through explicit review. Runtime scope controls where plugin code is installed. It does not move project governance history out of the project zone.

Rendered context, installed copies, and model inference are not constitutional source. Preserve provenance, uncertainty, scope, and the human authority that permitted each durable transition.
<!-- CGG:SESSION-LEARNING-PROTOCOL:END -->
