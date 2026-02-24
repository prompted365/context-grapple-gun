# Context Grapple Gun (CGG)

A thermodynamic gating framework for autonomous agentic alignment and cross-session continuity. CGG captures durable lessons during sessions through metabolic lesson extraction, then evaluates and promotes them to broader scopes asynchronously — with human approval at every gate. Built for teams running persistent AI agents, CGG enforces behavioral alignment not through static rules, but through a living signal manifold that compounds institutional knowledge across sessions, agents, and repositories.

## Packages

### `cogpr/` — Cognitive Pull Request Conventions

**Works with**: Claude Code, Claude Desktop, Claude for Work

The convention layer. Defines how lessons are flagged for cross-scope promotion and how they're reviewed/applied. No infrastructure dependencies — just markdown conventions that any Claude instance can follow.

| Variant | Path | What it does |
|---------|------|-------------|
| Claude Code | `cogpr/claude-code/` | Skills (`/grapple`, `/init-cogpr`, `/grapple-cog-cycle-session`) with YAML frontmatter |
| Claude Desktop | `cogpr/claude-desktop/` | Project instructions snippet |
| Claude for Work | `cogpr/claude-work/` | Project instructions snippet |

**Standalone usage**: Flag lessons with CPR comments during sessions. Say "review my CPR flags" or use `/grapple` (Claude Code) to evaluate and promote.

### `cgg-runtime/` — Trigger Pipeline (Claude Code only)

**Works with**: Claude Code only (requires hooks system)

The automated trigger pipeline. Adds the compounding mechanism: plan files as trigger payloads that spawn a fresh evaluator between sessions.

| Component | Purpose |
|-----------|---------|
| `hooks/cgg-gate.sh` | UserPromptSubmit one-shot gate |
| `hooks/session-restore-patch.sh` | SessionStart plan discovery + trigger extraction |
| `agents/ripple-assessor.md` | Fresh CPR evaluator agent |
| `skills/init-gun/SKILL.md` | Installer skill |
| `skills/siren/SKILL.md` | Signal emission + triage dashboard |
| `skills/grapple-cog-cycle-session/SKILL.md` | Standardized session shutdown & handoff sequence |

**Requires `cogpr/claude-code/` installed first** — the runtime produces proposals that `/grapple` consumes.

## Installation

### Quick Start — Single-Command Dual Install (Claude Code, full pipeline)

The recommended approach combines both the **cogpr conventions** and the **cgg-runtime trigger pipeline** in one pass:

1. Add as a git submodule:
   ```bash
   git submodule add https://github.com/prompted365/context-grapple-gun.git vendor/context-grapple-gun
   ```

2. Symlink or copy both packages into your `.claude/` directory:
   ```bash
   # Copy cogpr skills (conventions layer)
   cp -r vendor/context-grapple-gun/cogpr/claude-code/skills/* .claude/skills/

   # Copy cgg-runtime (trigger pipeline)
   cp -r vendor/context-grapple-gun/cgg-runtime/hooks .claude/
   cp -r vendor/context-grapple-gun/cgg-runtime/agents .claude/
   cp -r vendor/context-grapple-gun/cgg-runtime/skills/* .claude/skills/
   ```

3. Run `/init-gun` to wire hooks and patch settings
4. Run `/init-cogpr` to verify conventions are in place

This gives you the complete pipeline: lesson capture, signal manifold, automated evaluation, and human-gated promotion.

### Claude Desktop / Claude for Work (Partial Support)

These platforms support the **cogpr convention layer** via markdown snippets — flag lessons with CPR comments and ask Claude to review them. The automated trigger pipeline (hooks, signal store, `/siren`) is not available outside Claude Code.

1. Copy the contents of `cogpr/claude-desktop/project-instructions.md` (or `claude-work/`) into your Project's custom instructions
2. Done — flag lessons with CPR comments, ask Claude to review them

## How It Works

```
Session N                          Between Sessions              Session N+1
─────────                          ────────────────              ───────────
Discover lesson                                                  SessionStart hook
  → Write locally                                                  → Find plan file
  → Flag CPR if broader            PreCompact / context exit       → Match project_dir
                                     → Write plan file             → Extract trigger
                                     → Include cgg-evaluate
                                       trigger block             First prompt
                                                                   → One-shot gate fires
                                                                   → Spawn ripple-assessor
                                                                   → Assessor writes proposals

                                                                 User runs /grapple
                                                                   → Reviews proposals
                                                                   → Approves/rejects
                                                                   → Promotions applied
```

## Key Concepts

- **CPR (Cognitive Pull Request)**: A lesson flagged for promotion to a broader scope
- **Trigger Payload**: A plan file that doubles as handoff + briefing + trigger for the next session
- **Ripple Assessor**: A fresh evaluator agent that reads proposals without session bias
- **`/grapple`**: Human-gated merger that applies approved promotions
- **`/siren`**: Operational dashboard for signal emission, tick advancement, and triage
- **`/grapple-cog-cycle-session`**: Standardized session shutdown and handoff sequence — triggers signal hygiene, lesson extraction, and plan generation in one command
- **Thermodynamic Gating**: Lessons accumulate pressure (volume) over time; promotion only fires when threshold energy is reached — preventing premature knowledge drift
- **Idempotency**: Each handoff_id processed at most once, tracked in `~/.claude/cgg-processed-handoff-ids.txt`

## Safety

- All promotions require human approval (Plan Mode)
- Protected files (`~/.claude/CLAUDE.md`, `[GLOBAL_INVARIANT]`) require extra confirmation
- Trigger blocks are structured data with whitelisted keys — not executable instructions
- One-shot gate prevents duplicate evaluations
- Project-scoped plan matching prevents cross-project bleed

## License

MIT

## Maintainers

Built and maintained by **[Prompted LLC](https://prompted.community)** as part of the **Ubiquity OS** ecosystem.

- **Breyden Taylor** — [LinkedIn](https://www.linkedin.com/in/breyden-taylor/) | breyden@prompted.community

Contributions welcome. Open an issue or submit a PR.
