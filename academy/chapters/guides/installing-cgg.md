# Installing CGG in a Real Project

**Time: ~10 min**

You explored the governance primitives across five chapters. Now install the real thing.

---

## Before you start

You need:
- An existing project with a git repository
- Python 3.10+ (for CGG scripts)
- Claude Code installed

You do NOT need to have completed the academy, but having done so means you understand what every piece does.

---

## Step 1: Add the CGG submodule

```bash
cd your-project/
git submodule add https://github.com/prompted365/context-grapple-gun.git vendor/context-grapple-gun
```

This puts CGG at `vendor/context-grapple-gun/`. All subsequent paths are relative to your project root.

---

## Step 2: Choose your install mode

| Mode | What you get | When to use |
|------|-------------|-------------|
| **A) Full pipeline** | Skills + hooks + agents. Lessons captured, evaluated, and promoted automatically between sessions. | You want the full experience. Recommended. |
| **B) Skills only** | Slash commands (`/cadence`, `/review`, `/siren`). No hooks. You run everything manually. | You want control over when things fire. |
| **C) Convention only** | CogPR and signal capture rules in CLAUDE.md. No files copied. You write CogPRs by hand. | Minimal footprint. Just the writing convention. |

---

## Step 3: Copy skills to `.claude/skills/`

**(Modes A and B)**

```bash
mkdir -p .claude/skills
cp -r vendor/context-grapple-gun/cgg-runtime/skills/cadence/ .claude/skills/cadence/
cp -r vendor/context-grapple-gun/cgg-runtime/skills/review/ .claude/skills/review/
cp -r vendor/context-grapple-gun/cgg-runtime/skills/siren/ .claude/skills/siren/
```

**Note:** Legacy redirect shims (`cadence-downbeat`, `cadence-syncopate`, `grapple`, `init-gun`, `init-cogpr`) exist in the CGG runtime for backward compatibility but are not needed for new installs.

---

## Step 4: Copy hooks to `.claude/hooks/`

**(Mode A only)**

```bash
mkdir -p .claude/hooks
cp vendor/context-grapple-gun/cgg-runtime/hooks/cgg-gate.sh .claude/hooks/cgg-gate.sh
cp vendor/context-grapple-gun/cgg-runtime/hooks/session-restore-patch.sh .claude/hooks/session-restore-patch.sh
chmod +x .claude/hooks/cgg-gate.sh .claude/hooks/session-restore-patch.sh
```

---

## Step 5: Copy agents to `.claude/agents/`

**(Mode A only)**

```bash
mkdir -p .claude/agents
cp vendor/context-grapple-gun/cgg-runtime/agents/ripple-assessor.md .claude/agents/ripple-assessor.md
```

---

## Step 6: Create audit directories

**(Modes A and B)**

```bash
mkdir -p audit-logs/signals
mkdir -p audit-logs/tics
mkdir -p audit-logs/conformations
mkdir -p ~/.claude/grapple-proposals
```

These directories hold signal stores (JSONL), tic records, conformation snapshots, and grapple review proposals.

---

## Step 7: Create `.ticzone`

Create a `.ticzone` file at your project root:

```jsonc
{
  "name": "your-project-name",
  "tz": "America/Toronto",
  "include": ["."],
  "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"],
  "muffling_per_hop": 5
}
```

Replace `your-project-name` with your actual project or repo name. Set `tz` to your IANA timezone. Leave PRESTIGE out of the bands list -- it is governance-blocked.

---

## Step 8: Create `.ticignore`

Create a `.ticignore` file at your project root. Start with your `.gitignore` patterns, then add CGG-specific exclusions:

```gitignore
# Dependencies
node_modules/
vendor/
.venv/

# Build artifacts
dist/
build/
target/
__pycache__/

# Git internals
.git/

# Skill templates (contain example CogPR blocks, not real items)
.claude/skills/
```

Note: MEMORY.md files are gitignored but NOT ticignored -- they hold active governance data.

---

## Step 9: Patch `settings.local.json` with hooks

**(Mode A only)**

Create or update `.claude/settings.local.json`. If the file already exists, merge these entries into the existing `hooks` object. Do not overwrite existing hooks:

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

- **SessionStart** fires `session-restore-patch.sh` -- discovers the latest handoff plan, extracts Next Actions, injects session context.
- **UserPromptSubmit** fires `cgg-gate.sh` on the first prompt — triggers the ripple-assessor agent in the background to evaluate pending CogPRs and signals.

---

## Step 10: Add Session Learning Protocol to CLAUDE.md

Append this block to your project's `CLAUDE.md`. If no `CLAUDE.md` exists, create one with a project header and this block:

```markdown
## Session Learning Protocol (CGG)

When you discover something during a session that constitutes a durable lesson -- a friction point resolved, a non-obvious behavior confirmed, a workflow correction -- capture it as a CogPR (Cognitive Pull Request).

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

Run `/cadence` when the session feels long -- around 100k tokens is a good heuristic. If context is degrading, `/cadence double-time` does a minimal exit.

### Posture (optional)

Declare your working mode at session start:

| | DIRECT (execute) | META (analyze) |
|---|---|---|
| **ENG** | Implement, fix, ship | Architect, plan, design |
| **OPS** | Run pipelines, hit APIs | Audit, review, explore |

When capturing a CogPR, include `posture: "ENG/META"` (or whichever mode applies). This helps `/review` weigh context -- a lesson from active implementation carries different weight than one from analysis.

Posture is advisory in CGG. Substrates that enforce posture constraints (META = read-only, etc.) use the same fields -- zero migration on upgrade.

### Signal format

For persistent conditions that need tracking, emit signals to `audit-logs/signals/YYYY-MM-DD.jsonl`. Use /siren for signal management if installed.
```

---

## Verification checklist

After completing the steps for your chosen mode, verify:

- [ ] **Skills respond** -- start a Claude Code session and try `/cadence`. You should see the cadence downbeat prompt. (Modes A, B)
- [ ] **`.ticzone` exists** -- `cat .ticzone` shows your zone definition with correct project name and timezone. (Modes A, B, C recommended)
- [ ] **`audit-logs/` directories exist** -- `ls audit-logs/` shows `signals/`, `tics/`, `conformations/`. (Modes A, B)
- [ ] **Hooks fire on session start** -- start a new session and check the output for session restore context injection. (Mode A)
- [ ] **CLAUDE.md has the convention block** -- search your `CLAUDE.md` for "Session Learning Protocol". (All modes)
- [ ] **`.ticignore` exists** -- `cat .ticignore` shows your exclusion patterns. (Modes A, B, C recommended)

---

## Four commands to know

After installation, CGG adds four primary slash commands:

```
/cadence             -- end of session. Saves lessons, writes handoff.
/cadence double-time -- emergency exit. Minimal handoff when context is low.
/review              -- every few sessions. Review proposed lessons.
/siren               -- check on recurring issues. Signal management.
```

Start working normally. When you are done with a session, type `/cadence`. That is the whole workflow.

---

## What happens next

The first time you use `/cadence`, CGG writes a handoff plan with any lessons discovered during the session. On the next session start (if you installed hooks), the session-restore hook discovers the plan, extracts your Next Actions, and injects them as context. The ripple-assessor evaluates any pending CogPRs in the background.

Every few sessions, run `/review` to review the proposals the assessor has queued up. You approve or reject each one. Approved lessons get promoted to the target CLAUDE.md scope. Rejected ones are discarded.

That is the full lifecycle: discover -> capture -> evaluate -> review -> promote.

---

## Reference

For full details on each component:

| Doc | What it covers |
|-----|----------------|
| [INSTALL.md](../../../INSTALL.md) | Complete installation reference with plugin install path |
| [START-HERE.md](../../../START-HERE.md) | Day-to-day usage guide |
| [DEV-README.md](../../../DEV-README.md) | Pipeline internals for contributors |
| [ARCHITECTURE.md](../../../ARCHITECTURE.md) | Signal manifold theory and governance layers |
