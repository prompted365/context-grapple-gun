# Installing CGG

> **Just want to use CGG?** See [START-HERE](START-HERE.md). **Pipeline mechanics?** See [DEV-README](DEV-README.md).

Two paths. Pick one.

---

## Path A: Install now (30 seconds)

You already know you want CGG. Get it running.

### Plugin install (recommended)

```bash
# Add the submodule
git submodule add https://github.com/prompted365/context-grapple-gun.git vendor/context-grapple-gun

# Install the plugin
claude plugin install vendor/context-grapple-gun
```

The plugin manifest registers skills, hooks, and agents automatically. Claude will ask which mode you want, then set up the remaining project governance files.

**When install finishes, you have:**
- `/cadence`, `/review`, `/siren`
- the selected level of automation for session boundaries and review flow
- `.ticzone` and `.ticignore` for governance scoping
- audit paths for signals, tics, and conformations

Start a session, do some work, run `/cadence` when you're done.

**Most users stop here.** The bootstrap prompt below is for environments without plugin support or for manual installs.

---

## Path B: Learn first (Academy)

You want to understand the governance model before installing. Good choice.

```
/homeskillet-academy
```

**Homeskillet Academy** is a ~90-minute interactive course. Claude teaches CGG primitives through stories:

| Chapter | Story | What it teaches |
|---------|-------|-----------------|
| 1 | The Taylor Family Calendar | Append-only truth stores |
| 2 | The Adjunct's Semester Project | Collaboration governance — promotable coordination patterns |
| 3 | Zookeeper Radio | Signals, bands, acoustic routing |
| 4 | Bridge Inspector | Human-gated review |
| 5 | Graduation | Full pipeline integration |

No CGG installation required for the Academy — you build the pieces from scratch. After completing it, come back here for the real install.

See [academy/README.md](academy/README.md) for details.

---

## Install modes explained

When installing, Claude asks which mode you want:

| Mode | What you get | Best for |
|------|--------------|----------|
| **Full pipeline** | Hooks + skills + background evaluation | Most users. Automatic capture, evaluation, and handoff. |
| **Skills only** | Just `/cadence`, `/review`, `/siren` | Manual control. You decide when to run things. |
| **Convention only** | Just the CogPR writing format | Minimal. No slash commands. You flag and review lessons by hand. |

If unsure, choose **Full pipeline**.

---

## Bootstrap prompt (alternative)

If your Claude Code version doesn't support plugins yet, paste this into a session:

Copy this entire block and paste it into a Claude Code session in your project:

````
I want to install Context Grapple Gun (CGG) into this project. CGG is a file-based governance lifecycle for persistent AI systems. It captures durable lessons discovered during work, carries them across session boundaries, and routes them through review so the project's operating rules can compound instead of resetting every session.

Here's what to do:

1. CHECK ENVIRONMENT: Look for the CGG submodule at `vendor/context-grapple-gun/`. If it doesn't exist, stop and tell me to add it first with:
   ```
   git submodule add https://github.com/prompted365/context-grapple-gun.git vendor/context-grapple-gun
   ```
   Then I can re-run this prompt.

2. ASK ME ONE QUESTION: "How do you want to install CGG?" with these options:
   - **A) Full pipeline (recommended)** — hooks, ripple-assessor, skills, session restore, and automatic between-session evaluation. Best when you want the full governance loop running.
   - **B) Skills only** — just `/cadence`, `/review`, and `/siren`, plus the local governance files they depend on. No hooks. You drive the lifecycle manually.
   - **C) Convention only** — only the CogPR protocol added to `CLAUDE.md`. No commands, no hooks, no copied runtime files. Manual capture and manual review.

3. BASED ON MY ANSWER, do the following:

---

### If A (Full pipeline):

**Copy primary skills** (create `.claude/skills/` dirs as needed):
- `vendor/context-grapple-gun/cgg-runtime/skills/cadence/` -> `.claude/skills/cadence/`
- `vendor/context-grapple-gun/cgg-runtime/skills/review/` -> `.claude/skills/review/`
- `vendor/context-grapple-gun/cgg-runtime/skills/siren/` -> `.claude/skills/siren/`

**Copy compatibility / alternate command wrappers** (these are valid command surfaces, not deprecated):
- `vendor/context-grapple-gun/cgg-runtime/skills/cadence-downbeat/` -> `.claude/skills/cadence-downbeat/`
- `vendor/context-grapple-gun/cgg-runtime/skills/cadence-syncopate/` -> `.claude/skills/cadence-syncopate/`
- `vendor/context-grapple-gun/cgg-runtime/skills/grapple/` -> `.claude/skills/grapple/`

Do not copy `init-gun` or `init-cogpr` unless I explicitly ask for legacy bootstrap compatibility. Those are absorbed into the install flow and should not be surfaced as first-contact commands.

**Copy hooks:**
- `vendor/context-grapple-gun/cgg-runtime/hooks/cgg-gate.sh` -> `.claude/hooks/cgg-gate.sh`
- `vendor/context-grapple-gun/cgg-runtime/hooks/session-restore-patch.sh` -> `.claude/hooks/session-restore-patch.sh`
- Make both executable: `chmod +x .claude/hooks/cgg-gate.sh .claude/hooks/session-restore-patch.sh`

**Copy agents:**
- `vendor/context-grapple-gun/cgg-runtime/agents/ripple-assessor.md` -> `.claude/agents/ripple-assessor.md`

**Create directories:**
- `mkdir -p ~/.claude/grapple-proposals`
- `mkdir -p audit-logs/signals`
- `mkdir -p audit-logs/tics`
- `mkdir -p audit-logs/conformations`

**Create `.ticzone`** at project root (if one doesn't exist):
```json
{
  "name": "<project-name>",
  "tz": "UTC",
  "include": ["."],
  "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"],
  "muffling_per_hop": 5
}
```
Replace `<project-name>` with the actual project/repo name. Leave PRESTIGE
out of the bands list — it's governance-blocked.

**Create `.ticignore`** at project root (if one doesn't exist).
Start with `.gitignore` patterns, then add CGG-specific exclusions:
```
# Inherit from .gitignore
node_modules/
dist/
target/
.git/

# Vendor/upstream (read-only, not your governance surface)
vendor/

# Skill templates (contain example CogPR blocks, not real items)
.claude/skills/
```

Note: MEMORY.md files are gitignored but NOT ticignored — they hold
active governance data (pending CPRs, operational memory).

**Patch `.claude/settings.local.json`** — read the existing file (or create it if missing), and add these hook entries to the `hooks` object. Preserve any existing hooks. If hooks with the same event already exist, append these as additional entries (hooks is an object keyed by event name, where each value is an array of hook configs):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": ".claude/hooks/session-restore-patch.sh"
      }
    ],
    "UserPromptSubmit": [
      {
        "type": "command",
        "command": ".claude/hooks/cgg-gate.sh"
      }
    ]
  }
}
```

**Add Session Learning Protocol to CLAUDE.md** — append the learning protocol block (shown below under "Convention block") to the project's CLAUDE.md. If no CLAUDE.md exists, create one with a project header and this block.

---

### If B (Skills only):

**Copy primary skills** (create `.claude/skills/` dirs as needed):
- `vendor/context-grapple-gun/cgg-runtime/skills/cadence/` -> `.claude/skills/cadence/`
- `vendor/context-grapple-gun/cgg-runtime/skills/review/` -> `.claude/skills/review/`
- `vendor/context-grapple-gun/cgg-runtime/skills/siren/` -> `.claude/skills/siren/`

**Copy compatibility / alternate command wrappers** (these are valid command surfaces, not deprecated):
- `vendor/context-grapple-gun/cgg-runtime/skills/cadence-downbeat/` -> `.claude/skills/cadence-downbeat/`
- `vendor/context-grapple-gun/cgg-runtime/skills/cadence-syncopate/` -> `.claude/skills/cadence-syncopate/`
- `vendor/context-grapple-gun/cgg-runtime/skills/grapple/` -> `.claude/skills/grapple/`

Do not copy `init-gun` or `init-cogpr` unless I explicitly ask for legacy bootstrap compatibility.

**Create directories:**
- `mkdir -p audit-logs/signals`
- `mkdir -p audit-logs/tics`
- `mkdir -p audit-logs/conformations`

**Create `.ticzone` and `.ticignore`** at project root (same as Full pipeline above — see those sections for templates).

**Add Session Learning Protocol to CLAUDE.md** (same convention block as Full pipeline).

Skip hooks, agents, and settings.local.json patching.

---

### If C (Convention only):

**Add Session Learning Protocol to CLAUDE.md** only. No files copied, no directories created.

Optionally create `.ticzone` and `.ticignore` at project root (see Full pipeline section for templates). These improve CogPR scanning accuracy but are not required for convention-only mode.

---

### Convention block to add to CLAUDE.md:

```markdown
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
```

---

4. AFTER INSTALLATION, print a mode-specific summary.

**If I chose A) Full pipeline**, print:

```
CGG installed — Full pipeline mode.

What was installed:
- Skills: /cadence, /review, /siren
- Compatibility / alternate command wrappers: cadence-downbeat, cadence-syncopate, grapple
- Hooks:
  - SessionStart -> .claude/hooks/session-restore-patch.sh
  - UserPromptSubmit -> .claude/hooks/cgg-gate.sh
- Agent: ripple-assessor
- Governance files: .ticzone, .ticignore
- Audit paths:
  - audit-logs/signals
  - audit-logs/tics
  - audit-logs/conformations
- Proposals path: ~/.claude/grapple-proposals/latest.md

What this means operationally:
1. You work normally.
2. You end a real session with /cadence.
3. CGG writes a handoff / plan, emits a tic, and stages lesson capture.
4. On the next session start, the SessionStart hook detects the handoff and restores relevant context.
5. On the first prompt of that session, the UserPromptSubmit gate fires once and launches the ripple-assessor in the background.
6. The assessor evaluates pending CogPRs and writes proposals to ~/.claude/grapple-proposals/latest.md.
7. You run /review to approve, reject, or edit what should persist.
8. You run /siren when you want signal visibility or recurring-friction triage.

What you may see in console:
- After /cadence: a handoff / plan confirmation
- On next session start: handoff discovery / restored context / possible active signal summary
- On first prompt of that session: a CGG trigger message indicating the assessor was spawned in the background
- Later: proposals available for /review

Primary commands:
/cadence             — normal session close. Writes tic, handoff, and lesson capture.
/cadence-syncopate   — compact / emergency exit command surface still supported.
/review              — constitutional review docket for proposed lessons.
/siren               — signal dashboard and recurring-friction triage.

Start working normally. End each real session with /cadence.
```

**If I chose B) Skills only**, print:

```
CGG installed — Skills only mode.

What was installed:
- Skills: /cadence, /review, /siren
- Compatibility / alternate command wrappers: cadence-downbeat, cadence-syncopate, grapple
- Governance files: .ticzone, .ticignore
- Audit paths:
  - audit-logs/signals
  - audit-logs/tics
  - audit-logs/conformations

What this means operationally:
- No hooks
- No automatic session restore
- No background assessor trigger
- You drive the lifecycle manually

Manual rhythm:
1. Work normally
2. End sessions with /cadence
3. Use cadence-syncopate if you need the compact / emergency exit surface
4. Run /review every few sessions
5. Run /siren when you want signal visibility

Primary commands:
/cadence             — normal session close. Writes tic, handoff, and lesson capture.
/cadence-syncopate   — compact / emergency exit command surface still supported.
/review              — review proposed lessons.
/siren               — signal dashboard and recurring-friction triage.

Start working normally. End each real session with /cadence.
```

**If I chose C) Convention only**, print:

```
CGG installed — Convention only mode.

What was installed:
- Session Learning Protocol block added to CLAUDE.md

What this means operationally:
- No skills
- No hooks
- No agent
- No automated pipeline
- CogPR capture and review remain manual

What to do next:
- Work normally
- When you discover a durable lesson, record it in CogPR form in the relevant governance surface
- Add automation later if you want command-driven cadence, review, and signal management
```

If anything requested was skipped, already present, failed, or could not be merged safely, say so explicitly in the final summary instead of pretending it was freshly installed.
````

## Manual installation

If you prefer to set things up by hand instead of using the plugin installer or bootstrap prompt:

```bash
# 1. Add the submodule (if not already present)
git submodule add https://github.com/prompted365/context-grapple-gun.git vendor/context-grapple-gun

# 2. Copy skills
cp -r vendor/context-grapple-gun/cgg-runtime/skills/* .claude/skills/

# 3. Copy hooks
mkdir -p .claude/hooks
cp vendor/context-grapple-gun/cgg-runtime/hooks/* .claude/hooks/
chmod +x .claude/hooks/*.sh

# 4. Copy agents
mkdir -p .claude/agents
cp vendor/context-grapple-gun/cgg-runtime/agents/* .claude/agents/

# 5. Create directories
mkdir -p ~/.claude/grapple-proposals
mkdir -p audit-logs/signals audit-logs/tics audit-logs/conformations

# 5.5. Create .ticzone and .ticignore at project root (if missing)
# Edit .ticzone: set "name" to your project name, adjust "tz" to your timezone
# Edit .ticignore: add project-specific exclusions beyond the defaults

# 6. Add hooks to .claude/settings.local.json (merge with existing content):
# SessionStart  -> .claude/hooks/session-restore-patch.sh
# UserPromptSubmit -> .claude/hooks/cgg-gate.sh

# 7. Add the Session Learning Protocol block to your project's CLAUDE.md
#    (see "Convention block" in the bootstrap prompt above)
```

## Reference docs

| Doc | What it covers |
|-----|----------------|
| [START-HERE.md](START-HERE.md) | Day-to-day usage. The three commands. What a normal day looks like. |
| [DEV-README.md](DEV-README.md) | Engineering details. How the pipeline works. Hook lifecycle. |
| [README.md](README.md) | Full reference. Scope hierarchies, signal types, applicability. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Deep theory. Signal manifold, acoustic model, governance layers. |
| [academy/README.md](academy/README.md) | Learn through story. Five chapters, real simulations, one goat. |
| [docs/TERMINOLOGY.md](docs/TERMINOLOGY.md) | Glossary with neutral aliases. What to learn when. |

---

## Backward compatibility

### Compatibility wrappers (still valid command surfaces)

These alternate command surfaces are installed by default and remain fully supported:

| Command | Equivalent to |
|---------|---------------|
| `/cadence-downbeat` | `/cadence` |
| `/cadence-syncopate` | `/cadence double-time` |
| `/grapple` | `/review` |

`cadence-syncopate` is a valid command surface for compact / emergency exits. It is not deprecated — use it when the alternate entrypoint makes sense for your workflow.

### Deprecated wrappers (absorbed into install flow)

These commands have been absorbed into the bootstrap install and are not installed by default:

| Old command | Status |
|-------------|--------|
| `/init-gun` | Absorbed into bootstrap install (this file) |
| `/init-cogpr` | Absorbed into bootstrap install (this file) |

Only install `init-gun` or `init-cogpr` if you explicitly need legacy bootstrap compatibility.
