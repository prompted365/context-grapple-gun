## Session Learning Protocol (CGG)

When you discover something during a session that constitutes a durable lesson — a friction point resolved, a non-obvious behavior confirmed, a workflow correction — capture it as a CogPR (Cognitive Pull Request).

### Write rule (born truth vs in-force truth)

Write lessons to MEMORY.md by default (born truth). Only write to CLAUDE.md when the lesson IS a law change (in-force truth). If no subsystem MEMORY.md exists, write to the project's auto-memory (`~/.claude/projects/*/memory/MEMORY.md`).

### CogPR format

Write the lesson inline, then add this flag immediately after:

<!-- --agnostic-candidate
  lesson: "one-line lesson summary"
  source_date: "YYYY-MM-DD"
  source: "file:line"
  band: "COGNITIVE"
  motivation_layer: "COGNITIVE"
  subsystem: "relevant_subsystem"
  recommended_scopes:
    - "path/to/broader/CLAUDE.md"
  rationale: "why this is broader than local"
  review_hints: "what to check when evaluating"
  status: "pending"
-->

### Band budget

| Band | Use for |
|------|---------|
| PRIMITIVE | Safety, data integrity, survival signals |
| COGNITIVE | Learning, discovery, process improvement (default) |
| SOCIAL | Collaboration signals (use sparingly) |
| PRESTIGE | Never. Governance-blocked. |

Run `/cadence` when the session feels long — around 100k tokens is a good heuristic. If context is degrading, `/cadence double-time` does a minimal exit. The `cadence-syncopate` command surface remains valid and supported.

### Posture (optional)

Declare your working mode at session start:

| | DIRECT (execute) | META (analyze) |
|---|---|---|
| **ENG** | Implement, fix, ship | Architect, plan, design |
| **OPS** | Run pipelines, hit APIs | Audit, review, explore |

When capturing a CogPR, include `posture: "ENG/META"` (or whichever
mode applies). This helps `/review` weigh context — a lesson from active
implementation carries different weight than one from analysis.

Posture is advisory in CGG. Substrates that enforce posture constraints
(META = read-only, etc.) use the same fields — zero migration on upgrade.

### Signal format

For persistent conditions that need tracking, emit signals to `audit-logs/signals/YYYY-MM-DD.jsonl`. Use /siren for signal management if installed.

### Topology

Run `cgg-doctor.sh` from your project root to see your governance topology.
