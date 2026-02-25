<p align="center">
  <img src="assets/cgg-banner.jpeg" alt="Context Grapple Gun by Prompted LLC & Ubiquity OS" width="100%" />
</p>

# Context Grapple Gun (CGG) — Practical Developer Guide

**TL;DR: A CI/CD pipeline for your AI's memory and system prompts.**

If you use Claude Code (or any persistent AI agent), you know the pain of "context amnesia." The AI solves a complex bug in one session, but you have to manually update your `CLAUDE.md` to ensure it doesn't make the same mistake tomorrow.

**Context Grapple Gun (CGG)** automates this. It allows the AI to capture lessons locally, draft them as "Cognitive Pull Requests" (CogPRs), and asynchronously merge them into your global system prompts with your approval.

## The DevOps Analogy

If you understand standard software delivery, you already understand CGG:

* **CogPRs** = Pull Requests for your `CLAUDE.md`.
* **Ripple Assessor** = A CI/CD test runner that evaluates the AI's proposed rules against your existing prompts to prevent conflicts.
* **`/grapple`** = The Code Review / Merge step. You (the human) approve, reject, or modify the AI's proposed rules.
* **`/siren`** = Datadog / PagerDuty for your agent. It tracks recurring friction points across sessions and alerts you when a threshold is breached.

## Packages

### 1. `cogpr/` — The Convention Layer (Works Everywhere)
A set of markdown standards that teach Claude how to flag lessons as "Pull Requests." Works in Claude Code, Claude Desktop, and Claude for Work.

### 2. `cgg-runtime/` — The Automation Engine (Claude Code Only)
Automates the lifecycle using Claude Code's bash hooks.
* **On Session End:** Writes a handoff payload.
* **On Session Start:** A background agent evaluates pending PRs and flags.
* **During Session:** You type `/grapple` to review and merge the updates.

## Installation (Claude Code Native)

Install both the conventions and the automation engine in one pass:

1. Add as a git submodule:
   ```bash
   git submodule add https://github.com/prompted365/context-grapple-gun.git vendor/context-grapple-gun
   ```

2. Symlink or copy the packages into your `.claude/` directory:

   ```bash
   # Copy skills (commands)
   cp -r vendor/context-grapple-gun/cogpr/claude-code/skills/* .claude/skills/
   cp -r vendor/context-grapple-gun/cgg-runtime/skills/* .claude/skills/

   # Copy background agents and bash hooks
   cp -r vendor/context-grapple-gun/cgg-runtime/hooks .claude/
   cp -r vendor/context-grapple-gun/cgg-runtime/agents .claude/
   ```

3. Initialize the environment:

Run `/init-gun` and `/init-cogpr` inside Claude Code to wire the hooks.

_(Note: For Claude Desktop/Work, simply copy the contents of `cogpr/claude-desktop/project-instructions.md` into your Project's custom instructions.)_

## Daily Workflow

<p align="center">
  <img src="assets/cogpr-banner.jpeg" alt="CogPR — Cognitive Pull Requests by Prompted LLC & Ubiquity OS" width="100%" />
</p>

1. **Work Normally:** You and Claude Code debug an issue.

2. **Draft PR:** Claude realizes this is a durable lesson and drops a `<!-- --agnostic-candidate -->` (CogPR) flag in the local file.

3. **End Session:** Run `/grapple-cog-cycle-session` to gracefully shut down the session, generate a handoff file, and clean the context.

4. **Next Session:** The background hook triggers. A read-only agent evaluates the pending PR.

5. **Merge:** You type `/grapple`. A UI appears. You hit "Approve," and the lesson is injected into your global `CLAUDE.md`.

## Built-In Commands (Skills)

- `/grapple-cog-cycle-session` — Standardized session shutdown. Bundles current context and stages PRs for the next run.
- `/grapple` — The review dashboard. Approve or deny pending prompt updates.
- `/siren` — The monitoring dashboard. View active friction logs and background alerts.

## Safety & Constraints

- **No rogue modifications:** CGG _never_ modifies `CLAUDE.md` without explicit human approval via the `/grapple` command.
- **Idempotent hooks:** Background triggers fire exactly once per session handoff.
- **Project-scoped:** Rules learned in Project A do not bleed into Project B.

## Maintainers

Built and maintained by **[Prompted LLC](https://prompted.community/)** as part of the **Ubiquity OS** ecosystem.
- **Breyden Taylor** — [LinkedIn](https://www.linkedin.com/in/breyden-taylor/) | breyden@prompted.community

Contributions welcome. Open an issue or submit a PR.
