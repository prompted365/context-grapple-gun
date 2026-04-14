<p align="center">
  <img src="assets/cgg-banner.jpeg" alt="Context Grapple Gun by Prompted LLC & Ubiquity OS" width="100%" />
</p>

> **This is the user guide.** Three commands, 30-second install. For engineering details, see [DEV-README](DEV-README.md). For the full reference, see [README](README.md). To learn through story, see the [Academy](academy/README.md).

# Start Here

**CGG stops Claude Code from relearning the same lessons every session.** It captures hard-won discoveries from real work, routes them through human review, promotes them along an abstraction ladder, and hydrates them back into future sessions.

Three commands. Flat files. Human approval at every gate.

---

## The three commands

| Command | When | What it does |
|---------|------|--------------|
| `/cadence` | End of session, or when context feels long (~100k tokens) | Saves lessons, emits a timestamp, writes a handoff for the next session |
| `/review` | Every few sessions | Shows proposed lessons. You approve, reject, or modify before they stick. |
| `/siren` | When you want to check recurring issues | Shows friction signals — things that keep coming up and might need attention |

That's the daily interface. Everything else is automatic.

---

## What a normal day looks like

**Start a session.** If lessons from yesterday are waiting for review, you'll see a note. Run `/review` to handle them, or ignore it and get to work.

**Work normally.** Build features, fix bugs, ask questions. When Claude discovers something worth keeping — a gotcha, a pattern, a coordination technique that works — it flags it as a **CogPR** (behavior pull request).

**End the session.** When you're done or when things feel sluggish, run `/cadence`. Claude wraps up, saves lessons, and writes a handoff. Close the session.

**Next session.** Start fresh. Yesterday's lessons are already loaded. Claude doesn't ask the same questions. It doesn't make the same mistakes. It compounds.

---

## How it works (one paragraph)

Lessons get captured locally as you work. When you run `/cadence`, CGG bundles them with a handoff plan and a sequenced timestamp. Between sessions, a background evaluator checks the proposals. Next session, `/review` surfaces them in a docket. You approve the good ones to broader scope (site → global), reject the noise. Over weeks, the project accumulates real operational knowledge from real work — not documentation someone wrote once, but living rules from actual mistakes and discoveries.

---

## What you need to learn right now

**Day 1 essentials:**
- `/cadence` — run this when the session ends
- `/review` — run this every few sessions to approve or reject proposed lessons
- **CogPR** — what Claude flags as "remember this" (behavior pull request)
- **Site / Global** — where lessons live (narrow → broad scope). Intermediate rungs (domain, estate, federation) exist for multi-project governance.

**What can wait:**
- Signals, warrants, bands — the friction monitoring system. Works quietly in background.
- Tics, zones, conformations — canonical timestamps and jurisdictional scoping. Advanced.
- Ripple assessor — the background evaluator. You don't interact with it directly.

See [docs/TERMINOLOGY.md](docs/TERMINOLOGY.md) for the full glossary with neutral aliases.

---

## Quick glossary

| Term | What it means |
|------|---------------|
| **CogPR** | A proposed lesson flagged for review (like a pull request, but for behavior rules) |
| **Abstraction ladder** | Site → Domain → Estate → Federation → Global scope hierarchy. Lessons climb through `/review`. |
| **Epoch boundary** | The session rotation point. `/cadence` ends an epoch cleanly. |
| **Signal** | Recurring friction that accrues volume across sessions |
| **Warrant** | Auto-escalation when a signal crosses threshold — demands resolution |

---

## Install

```bash
npx context-grapple-gun install
```

Done. The CLI checks prerequisites, clones CGG, registers the plugin, and sets up your governance zone. After install, you have `/cadence`, `/review`, `/siren`, and the full governance pipeline.

**Verify it worked:** `cgg doctor`

See [INSTALL.md](INSTALL.md) for all options (plugin install, global CLI, bootstrap prompt, manual setup, install modes and scopes).

---

## What about scale?

**CGG is complete for individuals and small teams.** You don't need anything else.

CGG has a lexical ceiling — the point where flat-file governance stops being sufficient. When that happens (signals in the hundreds, lessons spanning dozens of files), CGG's primitives become the audit trail beneath whatever infrastructure you adopt. Same governance lifecycle, different storage layer.

Most projects never hit that ceiling.

---

## The scope ladder

Lessons are born locally in `MEMORY.md` (born truth). Promotion through `/review` moves them up:

| Scope | Where it lives | What it means |
|-------|----------------|---------------|
| **Site** | Project root `CLAUDE.md` | Applies across this codebase |
| **Domain** | Subsystem `CLAUDE.md` (e.g., `crates/CLAUDE.md`) | Applies to one module or subsystem |
| **Estate** | Cross-project governance surface | Applies across multiple repos under one operator |
| **Federation** | Cross-organization surface | Applies across multiple estates (rare) |
| **Global** | `~/.claude/CLAUDE.md` | Applies to everything you build, all projects |

Most users only interact with **site** and **global**. A lesson about "this API returns 204" stays at site scope. A lesson about "always validate embedding dimensions" might go global. You decide.

Site-level governance is fully bootstrapped via `/init-governance`. Domain/estate/federation are supported topology markers for multi-project governance — most users don't need them. Run `cgg-doctor.sh` to see your current topology.

---

## Two kinds of lessons

CGG captures both:

**Subject-matter lessons** — truths about the system:
- "This endpoint returns null sometimes"
- "Redis connections use a shared pool"

**Collaboration lessons** — truths about working effectively:
- "Include explicit abstraction-level scoping when delegating tasks"
- "Run tests after each small change, not in batches"

Both are valid. Both can climb the ladder. Both pass through the same human gate.

---

## Signals and warrants (optional depth)

Sometimes the same friction appears across multiple sessions. Instead of a lesson, CGG tracks it as a **signal** — a problem that keeps showing up.

Signals accrue **volume** over time. When volume crosses a threshold, CGG mints a **warrant** — a formal escalation that demands resolution.

Run `/siren` to see the dashboard. Or don't — it works quietly in background.

---

## FAQ

**Does this work outside Claude Code?**
The convention layer (CogPR format, manual review) works in Claude Desktop and Claude for Work. The automation (hooks, background evaluation) requires Claude Code.

**Does this send data anywhere?**
No. Everything is flat files in your project directory. No databases, no APIs, no cloud.

**Can Claude modify rules without approval?**
No. Every promotion requires `/review` approval. Claude proposes. You decide.

**What if I forget `/cadence`?**
Lessons are still in local files. You miss the handoff and automatic evaluation. Run `/cadence` next time — the system picks up.

**What about `/cadence double-time`?**
Emergency exit. Minimal handoff when context is degraded. Use when you're past the comfortable token range and need to get out fast.

---

## Reading path

| You want... | Read |
|-------------|------|
| Just use it | This file. You're done. |
| Understand the pipeline | [DEV-README.md](DEV-README.md) |
| Evaluate the architecture | [README.md](README.md) |
| Deep theory | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Learn through story | [academy/README.md](academy/README.md) |

---

## Maintainers

**[Prompted LLC](https://promptedllc.com)** — creators of the Ubiquity governance substrate.

Breyden Taylor, Founder & Architect — [LinkedIn](https://www.linkedin.com/in/breyden-taylor/) | breyden@prompted.community

Contributions welcome.
