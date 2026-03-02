# Installing CGG

> This is the installer. If you just want to use CGG, see [START-HERE](START-HERE.md). For pipeline mechanics, see [DEV-README](DEV-README.md).

One prompt. One question. Done.

CGG installs by pasting a single prompt into Claude Code. Claude reads the prompt, asks which mode you want, and sets everything up. No manual file copying. No separate init commands. The installer is a prompt, not a script.

## Bootstrap prompt

Copy this entire block and paste it into a Claude Code session in your project:

````
I want to install Context Grapple Gun (CGG) into this project. CGG is a session learning system — it helps you remember what you learn across sessions instead of starting from scratch every time.

Here's what to do:

1. CHECK ENVIRONMENT: Look for the CGG submodule at `vendor/context-grapple-gun/`. If it doesn't exist, stop and tell me to add it first with:
   ```
   git submodule add https://github.com/prompted365/context-grapple-gun.git vendor/context-grapple-gun
   ```
   Then I can re-run this prompt.

2. ASK ME ONE QUESTION: "How do you want to install CGG?" with these options:
   - **A) Full pipeline (recommended)** — hooks, agents, skills, session restore. Lessons are captured, evaluated, and promoted automatically between sessions.
   - **B) Skills only** — just the slash commands (/cadence, /review, /siren). No hooks. You run everything manually.
   - **C) Convention only** — just the CogPR and signal capture rules added to CLAUDE.md. No slash commands, no files copied. You write CogPRs by hand and review them yourself.

3. BASED ON MY ANSWER, do the following:

---

### If A (Full pipeline):

**Copy skills** (create `.claude/skills/` dirs as needed):
- `vendor/context-grapple-gun/cgg-runtime/skills/cadence/` -> `.claude/skills/cadence/`
- `vendor/context-grapple-gun/cgg-runtime/skills/review/` -> `.claude/skills/review/`
- `vendor/context-grapple-gun/cgg-runtime/skills/siren/` -> `.claude/skills/siren/`

Copy deprecated wrappers (so old command names still work):
- `vendor/context-grapple-gun/cgg-runtime/skills/cadence-downbeat/` -> `.claude/skills/cadence-downbeat/`
- `vendor/context-grapple-gun/cgg-runtime/skills/cadence-syncopate/` -> `.claude/skills/cadence-syncopate/`
- `vendor/context-grapple-gun/cgg-runtime/skills/grapple/` -> `.claude/skills/grapple/`

Copy deprecated init stubs (inform users they're absorbed into this bootstrap):
- `vendor/context-grapple-gun/cgg-runtime/skills/init-gun/` -> `.claude/skills/init-gun/`
- `vendor/context-grapple-gun/cgg-runtime/skills/init-cogpr/` -> `.claude/skills/init-cogpr/`

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

# Skill templates (contain example CPR blocks, not real items)
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

**Copy skills** (same as Full pipeline — all skill dirs listed above).

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

Optionally create `.ticzone` and `.ticignore` at project root (see Full pipeline section for templates). These improve CPR scanning accuracy but are not required for convention-only mode.

---

### Convention block to add to CLAUDE.md:

```markdown
## Session Learning Protocol (CGG)

When you discover something during a session that constitutes a durable lesson — a friction point resolved, a non-obvious behavior confirmed, a workflow correction — capture it as a CogPR (Cognitive Pull Request).

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

Run `/cadence` when the session feels long — around 100k tokens is a good heuristic. If context is degrading, `/cadence double-time` does a minimal exit.

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

4. AFTER INSTALLATION, print this:

```
CGG installed. Four commands:

/cadence             — end of session. Saves lessons, writes handoff.
/cadence double-time — emergency exit. Minimal handoff when context is low.
/review              — every few sessions. Review proposed lessons.
/siren               — check on recurring issues.

Start working. When you're done, type /cadence.
```
````

## Manual installation

If you prefer to set things up by hand instead of using the bootstrap prompt:

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
| [ARCHITECTURE.md](ARCHITECTURE.md) | Deep theory. Signal manifold, acoustic model, governance layers. |
