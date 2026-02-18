# CogPR — Cognitive Pull Request Conventions

Lesson flagging and cross-scope promotion conventions for Claude.

## Variants

| Platform | Path | Install method |
|----------|------|---------------|
| Claude Code | `claude-code/` | Copy skills to `.claude/skills/`, run `/init-cogpr` |
| Claude Desktop | `claude-desktop/` | Paste `project-instructions.md` into Project custom instructions |
| Claude for Work | `claude-work/` | Paste `project-instructions.md` into Project custom instructions |

## What's Included

### Claude Code
- `/grapple` skill — human-gated CPR merger/reviewer with Plan Mode approval
- `/init-cogpr` skill — installer that sets up conventions in a new project

### Claude Desktop / Claude for Work
- Project instructions snippet with capture rules, CPR flag format, and review workflow
- No slash commands — say "review my CPR flags" or "grapple" to trigger review

## Standalone Usage

CogPR works without the CGG runtime. Lessons are evaluated inline when you request review. The CGG runtime adds automated between-session evaluation via the trigger pipeline.
