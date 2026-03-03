# CGG Lockstep Invariants

Doc statements that mirror code behavior directly. **If one changes, all others in the same group must update.** Check this file after any code change to scan behavior, zone handling, install flow, or skill renaming.

See [IMPLEMENTATION-MAP.md](IMPLEMENTATION-MAP.md) for full code cross-references.

---

## 1. Scan Surface — "CLAUDE.md + MEMORY.md only"

The governance scan targets exactly `**/CLAUDE.md` and `**/MEMORY.md` (plus auto-memory). Not all `.md` files.

| # | File | Location | What to search for |
|---|------|----------|--------------------|
| 1 | `cgg-runtime/hooks/session-restore-patch.sh` | Line 97 | `find ... -name "CLAUDE.md" -o -name "MEMORY.md"` |
| 2 | `cgg-runtime/skills/review/SKILL.md` | Step 2, lines 33-34 | `**/CLAUDE.md` and `**/MEMORY.md` glob targets |
| 3 | `cgg-runtime/skills/siren/SKILL.md` | Conformation step 4, lines 235-236 | `**/CLAUDE.md` and `**/MEMORY.md` glob targets |
| 4 | `cgg-runtime/skills/README.md` | Line 48 | Zone scan rule summary |
| 5 | `DEV-README.md` | Zone scanning section | Full rule: 5-step governance surface definition |

---

## 2. Default Exclusions — "vendor/, node_modules/, .git/, .claude/skills/"

When no `.ticignore` exists, these directories are excluded from governance scan.

| # | File | Location | What to search for |
|---|------|----------|--------------------|
| 1 | `cgg-runtime/hooks/session-restore-patch.sh` | Lines 89-90 | Default `FIND_EXCLUDES` fallback list |
| 2 | `cgg-runtime/skills/review/SKILL.md` | Step 2, lines 37-38 | "Default exclusions (if no .ticignore)" |
| 3 | `cgg-runtime/skills/siren/SKILL.md` | Conformation step 4, lines 237-238 | "default: vendor/, node_modules/, .git/, .claude/skills/" |

---

## 3. Example Skip — `status: "example"` blocks are not counted

Documentation template blocks with `status: "example"` are skipped by all scan paths.

| # | File | Location | What to search for |
|---|------|----------|--------------------|
| 1 | `cgg-runtime/hooks/session-restore-patch.sh` | Lines 66-71 | `count_pending_cprs()` awk — `example=1` flag, excluded from count |
| 2 | `cgg-runtime/skills/review/SKILL.md` | Step 2, lines 39-40 | "Skip blocks where `status: \"example\"`" |
| 3 | `cgg-runtime/skills/siren/SKILL.md` | Conformation step 4, line 239 | "Skip blocks with `status: \"example\"`" |

---

## 4. Proposals Output Path — `~/.claude/grapple-proposals/latest.md`

The single landing path for assessor output, consumed by `/review`.

| # | File | Location | What to search for |
|---|------|----------|--------------------|
| 1 | `cgg-runtime/hooks/cgg-gate.sh` | Line 61 | `--output "$HOME/.claude/grapple-proposals/latest.md"` |
| 2 | `cgg-runtime/agents/ripple-assessor.md` | Line 77 | "Write your proposals to `~/.claude/grapple-proposals/latest.md`" |
| 3 | `cgg-runtime/skills/review/SKILL.md` | Step 1, line 15 | "check if `~/.claude/grapple-proposals/latest.md` exists" |
| 4 | `cgg-runtime/skills/README.md` | Line 42, 66 | Proposals path in pipeline description and standalone guarantee |

---

## 5. Cadence Double-Time Semantics — "tic + compact plan, no signal tick or conformation"

What double-time skips must be described consistently everywhere it appears.

| # | File | Location | What to search for |
|---|------|----------|--------------------|
| 1 | `cgg-runtime/skills/cadence/SKILL.md` | Lines 187-196 | "What Double-Time Skips" table |
| 2 | `cgg-runtime/skills/README.md` | Line 46 | "compact handoff (tic + plan, no signal tick or conformation)" |
| 3 | `START-HERE.md` | FAQ section | Double-time as emergency exit description |
| 4 | `DEV-README.md` | Cadence section | Double-time: "tic + compact plan, no signal tick or conformation" |
| 5 | `ARCHITECTURE.md` | Performance physics section | Double-time: "minimal viable exit: tic + compact plan" |

---

## 6. Install File Copy Matrix — INSTALL.md paths vs actual `cgg-runtime/` contents

The bootstrap prompt lists files that get copied. These must match the actual directory structure.

| # | File | Location | What to verify |
|---|------|----------|--------------------|
| 1 | `INSTALL.md` | Bootstrap prompt (Mode A file list) | Listed skills, hooks, and agents |
| 2 | `cgg-runtime/` | Actual directory contents | `ls skills/`, `ls hooks/`, `ls agents/` |

**Current expected contents:**

```
cgg-runtime/
  hooks/
    cgg-gate.sh
    session-restore-patch.sh
  agents/
    ripple-assessor.md
  skills/
    README.md
    cadence/SKILL.md          (PRIMARY)
    review/SKILL.md           (PRIMARY)
    siren/SKILL.md            (PRIMARY)
    cadence-downbeat/SKILL.md (DEPRECATED redirect)
    cadence-syncopate/SKILL.md(DEPRECATED redirect)
    grapple/SKILL.md          (DEPRECATED redirect)
    init-gun/SKILL.md         (DEPRECATED redirect)
    init-cogpr/SKILL.md       (DEPRECATED redirect)
```

Only the 3 primary skills + 2 hooks + 1 agent are copied during install. Deprecated skills are NOT installed.
