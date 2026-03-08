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

The plugin manifest registers skills, hooks, and agents automatically.

Claude should ask two things:
1. install mode
2. install scope

Install mode decides how much automation you want.
Install scope decides where runtime surfaces live.

Default scope is user/global (`~/.claude/...`).
Project scope (`$ZONE_ROOT/.claude/...`) is opt-in only.

Project governance zone surfaces still live at the project root either way:
- `.ticzone`
- `.ticignore`
- `audit-logs/`
- project `CLAUDE.md` / `MEMORY.md`

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

## Install scopes explained

Install scope is separate from install mode.

| Scope | Runtime surfaces go to | Use when |
|------|-------------------------|----------|
| **User / Global** | `~/.claude/...` | Default. Best for federation, multi-project, and canonical validation workflows. |
| **Project** | `$ZONE_ROOT/.claude/...` | Use only when you explicitly want project-local embodiment. |
| **Enterprise** | Managed policy surface | Not a normal install target. Detect and respect managed policy constraints. |

### Important distinction

Scope only changes **runtime surface placement**.

These remain project-local:
- `.ticzone`
- `.ticignore`
- `audit-logs/`
- governance files in the project zone

So a user/global install still governs a project zone.
It does not move the zone into `~/.claude`.

Runtime scope and governance scope are different things.
Default runtime scope is user/global.
Default governance scope remains project-local unless promoted through the ladder.

---

## Bootstrap prompt (alternative)

If your Claude Code version doesn't support plugins yet, paste this into a session:

Copy this entire block and paste it into a Claude Code session in your project:

````
I want to install Context Grapple Gun (CGG) for this project's governance zone.

Important distinction:
- governance zone surfaces stay project-local
- runtime surfaces default to user/global (`~/.claude/...`)
- project runtime scope is opt-in only

CGG is a file-based governance lifecycle for persistent AI systems. It captures durable lessons discovered during work, carries them across session boundaries, and routes them through review so the project's operating rules can compound instead of resetting every session.

Here's what to do:

1. CHECK ENVIRONMENT: Look for the CGG submodule at `vendor/context-grapple-gun/`. If it doesn't exist, stop and tell me to add it first with:
   ```
   git submodule add https://github.com/prompted365/context-grapple-gun.git vendor/context-grapple-gun
   ```
   Then I can re-run this prompt.

2. ASK ME TWO QUESTIONS, in this order:

   First:
   "Which install mode do you want?"
   - **A) Full pipeline (recommended)** — hooks, ripple-assessor, skills, session restore, and automatic between-session evaluation.
   - **B) Skills only** — just `/cadence`, `/review`, and `/siren`, plus the local governance files they depend on.
   - **C) Convention only** — only the CogPR protocol added to `CLAUDE.md`.

   Second:
   "Which install scope do you want for runtime surfaces?"
   - **1) User / global (recommended)** — install runtime surfaces to `~/.claude/...`
   - **2) Project** — install runtime surfaces to `$ZONE_ROOT/.claude/...`
   - **3) Enterprise managed policy detected** — report constraints; do not treat this as a normal target

   If I do not explicitly choose project scope, default to user/global.

3. BASED ON MY ANSWER, do the following:

Resolve these variables first:

- `ZONE_ROOT` = project root / governance zone root
- `INSTALL_SCOPE` = `user` by default, or `project` only if explicitly chosen
- `INSTALL_ROOT` =
  - `~/.claude` if `INSTALL_SCOPE=user`
  - `$ZONE_ROOT/.claude` if `INSTALL_SCOPE=project`
- `SETTINGS_FILE` =
  - `~/.claude/settings.json` if `INSTALL_SCOPE=user`
  - `$ZONE_ROOT/.claude/settings.local.json` if `INSTALL_SCOPE=project`

Enterprise:
- if managed policy is detected, report it
- do not silently override or bypass it

---

### If A (Full pipeline):

Create runtime surface directories under `$INSTALL_ROOT` as needed.

**Copy primary skills:**
- `vendor/context-grapple-gun/cgg-runtime/skills/cadence/` -> `$INSTALL_ROOT/skills/cadence/`
- `vendor/context-grapple-gun/cgg-runtime/skills/review/` -> `$INSTALL_ROOT/skills/review/`
- `vendor/context-grapple-gun/cgg-runtime/skills/siren/` -> `$INSTALL_ROOT/skills/siren/`
- `vendor/context-grapple-gun/cgg-runtime/skills/init-governance/` -> `$INSTALL_ROOT/skills/init-governance/`
- `vendor/context-grapple-gun/cgg-runtime/skills/statusline/` -> `$INSTALL_ROOT/skills/statusline/`
- `vendor/context-grapple-gun/cgg-runtime/skills/homeskillet-academy/` -> `$INSTALL_ROOT/skills/homeskillet-academy/`

**Copy compatibility / alternate command wrappers:**
- `vendor/context-grapple-gun/cgg-runtime/skills/cadence-downbeat/` -> `$INSTALL_ROOT/skills/cadence-downbeat/`
- `vendor/context-grapple-gun/cgg-runtime/skills/cadence-syncopate/` -> `$INSTALL_ROOT/skills/cadence-syncopate/`
- `vendor/context-grapple-gun/cgg-runtime/skills/grapple/` -> `$INSTALL_ROOT/skills/grapple/`

Do not copy `init-gun` or `init-cogpr` unless explicitly requested for legacy compatibility.

**Copy hooks:**
- `vendor/context-grapple-gun/cgg-runtime/hooks/session-restore.sh` -> `$INSTALL_ROOT/hooks/session-restore.sh`
- `vendor/context-grapple-gun/cgg-runtime/hooks/session-restore-patch.sh` -> `$INSTALL_ROOT/hooks/session-restore-patch.sh`
- `vendor/context-grapple-gun/cgg-runtime/hooks/cgg-gate.sh` -> `$INSTALL_ROOT/hooks/cgg-gate.sh`
- `vendor/context-grapple-gun/cgg-runtime/hooks/posttool-microscan.sh` -> `$INSTALL_ROOT/hooks/posttool-microscan.sh`

Make copied hooks executable.

**Copy agents:**
- `vendor/context-grapple-gun/cgg-runtime/agents/ripple-assessor.md` -> `$INSTALL_ROOT/agents/ripple-assessor.md`
- `vendor/context-grapple-gun/cgg-runtime/agents/mogul.md` -> `$INSTALL_ROOT/agents/mogul.md`
- `vendor/context-grapple-gun/cgg-runtime/agents/ladder-auditor.md` -> `$INSTALL_ROOT/agents/ladder-auditor.md`
- `vendor/context-grapple-gun/cgg-runtime/agents/pattern-curator.md` -> `$INSTALL_ROOT/agents/pattern-curator.md`

**Create project-local governance zone surfaces at `ZONE_ROOT`:**
- `.ticzone` (if missing)
- `.ticignore` (if missing)
- `audit-logs/signals`
- `audit-logs/tics`
- `audit-logs/conformations`
- `audit-logs/cprs`
- `audit-logs/economy`
- `audit-logs/provenance`

These are always zone-local, regardless of install scope.

**Create global/shared runtime support path:**
- `mkdir -p ~/.claude/grapple-proposals`

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

**Patch the settings file at `$SETTINGS_FILE`.**

- If `INSTALL_SCOPE=user`, patch `~/.claude/settings.json`
- If `INSTALL_SCOPE=project`, patch `$ZONE_ROOT/.claude/settings.local.json`

Preserve existing hooks. Append new hook commands rather than overwriting matching events.
If enterprise-managed policy is detected, report any constraints before writing.

Example for user scope (merged into `~/.claude/settings.json`):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "$INSTALL_ROOT/hooks/session-restore-patch.sh"
      }
    ],
    "UserPromptSubmit": [
      {
        "type": "command",
        "command": "$INSTALL_ROOT/hooks/cgg-gate.sh"
      }
    ],
    "PostToolUse": [
      {
        "type": "command",
        "command": "$INSTALL_ROOT/hooks/posttool-microscan.sh"
      }
    ]
  }
}
```

**Add Session Learning Protocol to CLAUDE.md** — append the learning protocol block (shown below under "Convention block") to the project's CLAUDE.md. If no CLAUDE.md exists, create one with a project header and this block.

---

### If B (Skills only):

**Copy primary skills** to `$INSTALL_ROOT/skills/`:
- `vendor/context-grapple-gun/cgg-runtime/skills/cadence/` -> `$INSTALL_ROOT/skills/cadence/`
- `vendor/context-grapple-gun/cgg-runtime/skills/review/` -> `$INSTALL_ROOT/skills/review/`
- `vendor/context-grapple-gun/cgg-runtime/skills/siren/` -> `$INSTALL_ROOT/skills/siren/`

**Copy compatibility / alternate command wrappers:**
- `vendor/context-grapple-gun/cgg-runtime/skills/cadence-downbeat/` -> `$INSTALL_ROOT/skills/cadence-downbeat/`
- `vendor/context-grapple-gun/cgg-runtime/skills/cadence-syncopate/` -> `$INSTALL_ROOT/skills/cadence-syncopate/`
- `vendor/context-grapple-gun/cgg-runtime/skills/grapple/` -> `$INSTALL_ROOT/skills/grapple/`

Do not copy `init-gun` or `init-cogpr` unless explicitly requested for legacy compatibility.

**Create project-local governance zone surfaces at `ZONE_ROOT`:**
- `audit-logs/signals`
- `audit-logs/tics`
- `audit-logs/conformations`

**Create `.ticzone` and `.ticignore`** at project root (same as Full pipeline above — see those sections for templates).

**Add Session Learning Protocol to CLAUDE.md** (same convention block as Full pipeline).

Skip hooks, agents, and settings patching.

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

Install scope:
- user/global (~/.claude)
or
- project ($ZONE_ROOT/.claude)

Settings file:
- `~/.claude/settings.json`
or
- `$ZONE_ROOT/.claude/settings.local.json`

What was installed:
- Skills: /cadence, /review, /siren, /init-governance, /statusline, /homeskillet-academy
- Compatibility / alternate command wrappers: cadence-downbeat, cadence-syncopate, grapple
- Hooks:
  - SessionStart -> $INSTALL_ROOT/hooks/session-restore-patch.sh
  - UserPromptSubmit -> $INSTALL_ROOT/hooks/cgg-gate.sh
  - PostToolUse -> $INSTALL_ROOT/hooks/posttool-microscan.sh
- Agents: ripple-assessor, mogul, ladder-auditor, pattern-curator
- Proposals path: ~/.claude/grapple-proposals/latest.md

Zone-local governance surfaces remain at project root:
- `.ticzone`
- `.ticignore`
- `audit-logs/...`

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

Install scope:
- user/global (~/.claude)
or
- project ($ZONE_ROOT/.claude)

What was installed:
- Skills: /cadence, /review, /siren
- Compatibility / alternate command wrappers: cadence-downbeat, cadence-syncopate, grapple

Zone-local governance surfaces remain at project root:
- `.ticzone`
- `.ticignore`
- `audit-logs/...`

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

# 2. Choose install scope
# Default:
INSTALL_ROOT="$HOME/.claude"
SETTINGS_FILE="$HOME/.claude/settings.json"

# Optional project-local override:
# INSTALL_ROOT="$PWD/.claude"
# SETTINGS_FILE="$PWD/.claude/settings.local.json"

# 3. Copy active skills
mkdir -p "$INSTALL_ROOT"/skills/{cadence,review,siren,init-governance,statusline,homeskillet-academy,cadence-downbeat,cadence-syncopate,grapple}
for skill in cadence review siren init-governance statusline homeskillet-academy cadence-downbeat cadence-syncopate grapple; do
  cp vendor/context-grapple-gun/cgg-runtime/skills/$skill/SKILL.md "$INSTALL_ROOT/skills/$skill/"
done

# 4. Copy hooks
mkdir -p "$INSTALL_ROOT/hooks"
cp vendor/context-grapple-gun/cgg-runtime/hooks/session-restore.sh "$INSTALL_ROOT/hooks/"
cp vendor/context-grapple-gun/cgg-runtime/hooks/session-restore-patch.sh "$INSTALL_ROOT/hooks/"
cp vendor/context-grapple-gun/cgg-runtime/hooks/cgg-gate.sh "$INSTALL_ROOT/hooks/"
cp vendor/context-grapple-gun/cgg-runtime/hooks/posttool-microscan.sh "$INSTALL_ROOT/hooks/"
chmod +x "$INSTALL_ROOT"/hooks/*.sh

# 5. Copy agents
mkdir -p "$INSTALL_ROOT/agents"
cp vendor/context-grapple-gun/cgg-runtime/agents/ripple-assessor.md "$INSTALL_ROOT/agents/"
cp vendor/context-grapple-gun/cgg-runtime/agents/mogul.md "$INSTALL_ROOT/agents/"
cp vendor/context-grapple-gun/cgg-runtime/agents/ladder-auditor.md "$INSTALL_ROOT/agents/"
cp vendor/context-grapple-gun/cgg-runtime/agents/pattern-curator.md "$INSTALL_ROOT/agents/"

# 6. Create global/shared runtime support path
mkdir -p "$HOME/.claude/grapple-proposals"

# 7. Create project-local governance zone surfaces
mkdir -p audit-logs/{signals,tics,conformations,cprs,economy,provenance}

# 8. Create .ticzone and .ticignore at project root if missing
# Edit .ticzone: set "name" and "tz"
# Edit .ticignore: add project-specific exclusions

# 9. Merge hooks into $SETTINGS_FILE
# SessionStart   -> $INSTALL_ROOT/hooks/session-restore-patch.sh
# UserPromptSubmit -> $INSTALL_ROOT/hooks/cgg-gate.sh
# PostToolUse -> $INSTALL_ROOT/hooks/posttool-microscan.sh

# 10. Add the Session Learning Protocol block to project CLAUDE.md
#     (see convention-block.md)
#    (see "Convention block" above, or copy from convention-block.md)
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
