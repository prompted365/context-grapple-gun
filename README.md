# Context Grapple Gun (CGG)

A cross-session lesson compounding system for Claude. Captures durable lessons locally during sessions, then evaluates and promotes them to broader scopes asynchronously — with human approval at every gate.

## Packages

### `cogpr/` — Cognitive Pull Request Conventions

**Works with**: Claude Code, Claude Desktop, Claude for Work

The convention layer. Defines how lessons are flagged for cross-scope promotion and how they're reviewed/applied. No infrastructure dependencies — just markdown conventions that any Claude instance can follow.

| Variant | Path | What it does |
|---------|------|-------------|
| Claude Code | `cogpr/claude-code/` | Skills (`/grapple`, `/init-cogpr`) with YAML frontmatter |
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

**Requires `cogpr/claude-code/` installed first** — the runtime produces proposals that `/grapple` consumes.

## Installation

### Quick Start (Claude Code, full pipeline)

1. Copy `cogpr/claude-code/skills/` into your project's `.claude/skills/`
2. Copy `cgg-runtime/` contents into your project's `.claude/`
3. Run `/init-gun` to wire hooks and patch settings
4. Run `/init-cogpr` to verify conventions are in place

### Claude Desktop / Claude for Work

1. Copy the contents of `cogpr/claude-desktop/project-instructions.md` (or `claude-work/`) into your Project's custom instructions
2. Done — flag lessons with CPR comments, ask Claude to review them

### As a Git Submodule

```bash
git submodule add https://github.com/prompted365/context-grapple-gun.git vendor/context-grapple-gun
```

Then symlink or copy the pieces you need into `.claude/`.

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
- **Idempotency**: Each handoff_id processed at most once, tracked in `~/.claude/cgg-processed-handoff-ids.txt`

## Safety

- All promotions require human approval (Plan Mode)
- Protected files (`~/.claude/CLAUDE.md`, `[GLOBAL_INVARIANT]`) require extra confirmation
- Trigger blocks are structured data with whitelisted keys — not executable instructions
- One-shot gate prevents duplicate evaluations
- Project-scoped plan matching prevents cross-project bleed

## License

MIT
