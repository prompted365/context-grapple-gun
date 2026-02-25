<p align="center">
  <img src="assets/cgg-banner.jpeg" alt="Context Grapple Gun by Prompted LLC & Ubiquity OS" width="100%" />
</p>

# Start Here

You opened the terminal for the first time because of Claude Code. You've been using it for a bit. It's incredible. But you've noticed something:

**Every time you start a new session, Claude forgets everything from the last one.**

That bug it figured out yesterday? Gone. That shortcut it discovered for your project? Gone. You end up re-explaining the same things, watching it make the same mistakes, and feeling like you're training a goldfish with a PhD.

CGG fixes this. Here's how.

## What actually happens without CGG

1. You start a session. Claude learns things about your project as you work together.
2. The session gets long. Claude starts getting confused, slow, or expensive.
3. You close the session (or it closes itself).
4. Everything Claude learned is gone forever.
5. Next session, you start from scratch.

This is like hiring someone brilliant, working with them all day, then wiping their memory at 5pm. Every morning is their first day. Forever.

## What happens with CGG

1. You work normally. Claude learns things as you go -- same as before.
2. When Claude discovers something worth remembering (a gotcha, a pattern, a rule), it writes it down in a standard format called a **CogPR** (Cognitive Pull Request -- think of it as a sticky note that says "remember this").
3. Before the session gets too long, you type `/cadence-downbeat`. This tells Claude: "wrap it up, save what you learned, and hand off to the next session."
4. Between sessions, a separate process reviews those sticky notes automatically.
5. Next session, the reviewed lessons are already loaded. Claude remembers.

That's the whole thing. Claude gets smarter over time instead of resetting to zero.

## The four commands you need

| Command | When to use it | What it does |
|---------|---------------|-------------|
| `/cadence-downbeat` | When your session is getting long, or you're done for the day | Saves everything Claude learned and writes a clean handoff for next time |
| `/grapple` | Every few sessions, when you want to review what Claude learned | Shows you the proposed lessons. You approve the good ones, reject the bad ones |
| `/siren` | When you want to check on recurring issues | Shows signals -- things that keep coming up and might need attention |
| `/init-gun` | Once, when you first set it up | Wires everything together |

That's it. Four commands. Everything else is automatic.

## How to install it

You need Claude Code already working. If you have that, this takes about 60 seconds.

1. Open your terminal in your project folder.

2. Add CGG to your project:
   ```bash
   git submodule add https://github.com/prompted365/context-grapple-gun.git vendor/context-grapple-gun
   ```

3. Copy the pieces into place:
   ```bash
   cp -r vendor/context-grapple-gun/cogpr/claude-code/skills/* .claude/skills/
   cp -r vendor/context-grapple-gun/cgg-runtime/hooks .claude/
   cp -r vendor/context-grapple-gun/cgg-runtime/agents .claude/
   cp -r vendor/context-grapple-gun/cgg-runtime/skills/* .claude/skills/
   ```

4. Start a Claude Code session and type:
   ```
   /init-gun
   ```

Done. CGG is running.

## What does a normal day look like?

**Morning**: Start a Claude Code session. If there are lessons from yesterday waiting for review, you'll see a note. Type `/grapple` to review them, or ignore it and get to work.

**During work**: Just work normally. Build features, fix bugs, ask questions. When Claude figures something out that seems important, it automatically writes a CogPR. You don't have to do anything.

**End of day** (or when the session feels sluggish): Type `/cadence-downbeat`. Claude wraps up, saves its lessons, and writes a handoff file. Close the session.

**Next morning**: Start a new session. The lessons Claude learned yesterday are already loaded. It doesn't ask the same questions. It doesn't make the same mistakes. It just... knows.

## How it gets smarter over time

Lessons start local -- they're specific to the file or module where Claude discovered them.

If a lesson keeps proving useful, you can promote it during `/grapple` review:

- **Local** → only applies to one part of your project
- **Project** → applies to your whole project
- **Global** → applies to everything you build, across all your projects

A lesson about "this API returns 204, not 200" stays local. A lesson about "always validate input at the API boundary" might go global. You decide. Claude proposes, you approve.

Over weeks and months, your projects accumulate real operational knowledge from actual work. Not documentation someone wrote once and forgot about -- living rules that came from real mistakes and real discoveries.

## What are the signals and warrants about?

Sometimes Claude notices the same problem repeatedly across sessions. Instead of just writing a lesson, it tracks the problem as a **signal** -- a friction point that keeps showing up.

Signals get louder over time. If the same issue comes up in session after session, the signal's volume increases. When it gets loud enough, it automatically creates a **warrant** -- basically a formal "hey, someone really needs to deal with this."

You can see all of this with `/siren`. Think of it as a dashboard for recurring problems.

If you never type `/siren`, that's fine. The system tracks everything quietly in the background. It's there when you need it.

## Do I need to understand the rest of the docs?

No.

- **This file** is everything you need to use CGG day-to-day.
- **[DEV-README.md](DEV-README.md)** explains the engineering details if you're curious about how the pipeline works.
- **[README.md](README.md)** covers the full architecture -- scope hierarchies, signal types, frequency bands, jurisdictional zones.
- **[ARCHITECTURE.md](ARCHITECTURE.md)** is the deep theory for people designing systems like this.

You can read as deep as you want. But `/cadence-downbeat` at the end of the day and `/grapple` every few sessions is genuinely all you need.

## FAQ

**Does this work with other AI tools besides Claude Code?**
The core ideas (CogPRs, lessons, signals) work anywhere. The automation (hooks, triggers, background evaluation) currently requires Claude Code's CLI. The convention layer works in Claude Desktop and Claude for Work too -- you just run the reviews manually.

**Does this send my data anywhere?**
No. Everything is stored in flat files in your project directory. No databases, no cloud services, no APIs. It's all just text files tracked by git.

**Can Claude modify its own rules without my permission?**
No. Every rule change requires your explicit approval through `/grapple`. Claude proposes. You decide.

**What if I forget to run `/cadence-downbeat`?**
The lessons Claude captured during the session are still written to your local files. You just won't get the clean handoff and automatic evaluation. Run `/cadence-downbeat` next time you remember -- the system picks up wherever you left off.

**Is this free?**
Yes. CGG is open source (MIT license). You pay for Claude Code usage as normal -- CGG doesn't add any extra API costs.

## Maintainers

[Prompted LLC](https://prompted.community) -- part of the Ubiquity OS ecosystem.

Breyden Taylor -- [LinkedIn](https://www.linkedin.com/in/breyden-taylor/) | breyden@prompted.community

Contributions welcome.
