# CGG Docs Reframe — Patch Plan

## A) Hierarchical Audience Reframing

Four-tier audience ladder, mapped to existing files:

| Tier | Audience | File | What they need | What they must not need |
|------|----------|------|----------------|------------------------|
| 0 | Day-to-day user | START-HERE.md | 3 commands, normal day, what to do when slow | Theory, mermaid graphs, schema |
| 1 | Installer / Operator | INSTALL.md | Install modes, what goes where, zone/ignore setup, cadence timing | Pipeline internals, signal physics |
| 2 | Developer / Integrator | DEV-README.md + cgg-runtime/skills/README.md | Pipeline mechanics, hook lifecycle, scan surfaces, zone jurisdiction, extension points | Molecular biology analogies, scaling ceiling philosophy |
| 3 | Architect / Systems thinker | README.md + ARCHITECTURE.md | Mental model, primitives, design rationale, "CGG stops here" boundary | Install steps, daily workflow |

Each file gets a 2-line "Who this is for" block at the top (after banner), pointing up and down the ladder. The existing callouts in README and DEV-README already hint at this — the patch makes them consistent and durable.

---

## B) Patch Plan Per File

### START-HERE.md
**Intent**: Zero-jargon onboarding. A user who just discovered Claude Code reads this and is productive in 5 minutes.

**Keep**:
- The goldfish-with-a-PhD framing (lines 7-13) — it's the hook
- The three-command table (lines 37-43) — core value prop
- The "normal day" walkthrough (lines 56-63)
- The FAQ (lines 100-127)
- The abstraction ladder simplified (lines 65-77)

**Changes**:
- [ ] Add "Who this is for" block after the banner (before line 5): "This is the user guide. Three commands, one install. If you want engineering details, see DEV-README. If you want the architecture, see README."
- [ ] Line 29/39: Reframe cadence timing. Current: "Before the session gets too long" / "When your session is getting long." Change to: "When you've been working a while — around 100k tokens is a good rule of thumb, or whenever you feel context getting stale." Add a sentence: "If you're really late and the session feels degraded, `/cadence double-time` does a quick exit instead of a full wrap-up."
- [ ] Line 61: Same reframe for "End of day" — add: "(or type `/cadence double-time` if you're in a rush)"
- [ ] Line 112: FAQ "What if I forget to run `/cadence`?" — add a sentence: "If context is very low and you need to exit fast, `/cadence double-time` saves the minimum viable handoff without the full ceremony."
- [ ] Lines 89-98: The reading depth section already does the tier pointing. Make it explicit: add "Tier 0: you're here" framing without using the word "tier" — just "This file → DEV-README → README → ARCHITECTURE, each one deeper."
- [ ] Line 119: "CGG is a compact expression of the Ubiquity concurrent development methodology" — reword to decouple: "CGG was extracted from a larger governance methodology. When flat files aren't enough, deeper substrate layers (semantic recall, graph topology, expression gating) pick up where CGG leaves off. But for most projects, CGG is all you need." Remove the Ubiquity name from this sentence — the methodology name appears in the maintainers section, which is fine.

**Remove/avoid**:
- Don't add `.ticzone`/`.ticignore` here — Tier 0 users don't need to know about zone config
- Don't add band tables or signal schema

---

### INSTALL.md
**Intent**: One-question install that works. Operator-level — what goes where and why.

**Keep**:
- The bootstrap prompt structure (lines 11-159) — this IS the install
- The three modes A/B/C
- The manual install path (lines 161-191)
- The reference doc table (lines 193-200)

**Changes**:
- [ ] Add "Who this is for" block after line 1 (top): "This is the installer. If you just want to use CGG, see START-HERE. If you want to understand the pipeline mechanics, see DEV-README."
- [ ] `.ticzone` and `.ticignore` creation is already added (our earlier edit) — verify it reads well in the install flow. The key thing: explain WHY these matter, not just what to put in them. Add 1 sentence each:
  - `.ticzone`: "This defines your project's governance boundary — where signals route and where scans stop."
  - `.ticignore`: "This prevents template files (like skill examples) from being counted as real governance items."
- [ ] Convention block (lines 109-144): Posture section already added. Verify the cadence timing language in the convention block matches the "100k heuristic, not hard rule" framing. Currently the convention block doesn't mention cadence timing — that's fine, it's about CogPR format. But add a one-liner under the band budget table: "Run `/cadence` when the session feels long — around 100k tokens is a good heuristic. If you're past that and context is degrading, `/cadence double-time` does a minimal exit."
- [ ] Add to the post-install output message (line 151-158): mention double-time as an option:
  ```
  /cadence             — end of session. Saves lessons, writes handoff.
  /cadence double-time — emergency exit. Minimal handoff when context is low.
  /review              — every few sessions. Review proposed lessons.
  /siren               — check on recurring issues.
  ```

**Remove/avoid**:
- Don't explain pipeline internals here — point to DEV-README
- Don't explain signal physics — point to README

---

### README.md
**Intent**: Full architecture reference for architects and systems thinkers. The "read this to understand the design."

**Keep**:
- The abstraction ladder with Mermaid (lines 32-110) — core mental model
- The unified flow with Mermaid (lines 112-208) — the knowledge lifecycle
- Signal architecture (lines 210-241) — primitives, bands, quiet rail
- Tic/tic-zone/conformation (lines 243-310) — the clock and jurisdiction system
- Applicability section (lines 311-351) — where CGG fits in real organizations
- Measuring impact (lines 353-360)

**Changes**:
- [ ] Lines 5-7: The existing audience callouts are good but not ladder-consistent. Rewrite to: "**Using CGG day-to-day?** Start with [START-HERE.md](START-HERE.md). **Installing or extending?** See [DEV-README.md](DEV-README.md). **Designing systems like this?** Read the [Architecture & Design Rationale](ARCHITECTURE.md)."
- [ ] Line 130 (Mermaid): `T1["100k Token<br/>Manually Trigger"]` — change label to `T1["Session getting long<br/>~100k tokens"]` to avoid implying 100k is a hard boundary
- [ ] Line 158 (Mermaid): `T1 -->|>= 100k| Cycle1` — change edge label to `T1 -->|"natural stopping point"| Cycle1`
- [ ] Line 205 (4/4 cadence table): "at or before 100k tokens" — change to "before context degrades — 100k tokens is a good heuristic, not a hard boundary"
- [ ] Add to the 4/4 cadence section (after line 208): "If you're past the heuristic and the session feels sluggish, `/cadence double-time` produces a valid handoff with minimal ceremony — tic + plan, no signal tick or conformation. Recovery: next session runs a full downbeat."
- [ ] Lines 274-299 (Tic-zone section): `.ticzone` is well-described. `.ticignore` gets one sentence at line 297. Expand to a proper subsection:

  ```markdown
  #### `.ticignore` (exclusion filter)

  A `.ticignore` file at the zone root excludes paths from the governance surface.
  Gitignore-style directory patterns. v1 supports directory exclusions only —
  no glob wildcards, no file-level patterns. This is a documented constraint,
  not a missing feature.

  Signals originating from ignored paths are not routed. CogPR scans skip
  ignored directories. The zone scan rule is: zone boundary first (`.ticzone`
  defines what's in), ignore second (`.ticignore` removes what's out).

  MEMORY.md files are gitignored but NOT ticignored — they hold active
  governance data (pending CogPRs, operational memory).
  ```

- [ ] Add a "Zone scan rule" callout box somewhere in the tic-zone section (near line 299):

  ```markdown
  > **Zone scan rule** (shared across all scan points):
  > 1. Resolve project root via nearest `.ticzone`
  > 2. Governance surface = `**/CLAUDE.md` + `**/MEMORY.md` inside the zone + auto-memory
  > 3. Exclude paths matching `.ticignore` (default: vendor/, node_modules/, .git/, .claude/skills/)
  > 4. Skip `status: "example"` blocks (documentation templates)
  ```

- [ ] Lines 331-351 ("Where CGG fits" + scaling ceiling): Rewrite the "CGG stops here" boundary using class-of-capability language. Replace lines 335-339 with:

  ```markdown
  CGG guarantees:
  - File-based governance lifecycle (capture, evaluate, promote, audit)
  - Human-gated rule promotion at every scope boundary
  - Auditable signal/tic trails with total ordering
  - Claude Code automation via hooks (when installed)
  - Jurisdictional scoping via zones and exclusion filters

  CGG does NOT provide (and deliberately avoids):
  - Conformation-aware retrieval engines (load only what matches current system shape)
  - Expression gating across timescales (silence irrelevant lessons based on context)
  - Graph topology for relational memory (edges between concepts, not flat lists)
  - Endogenous economics (cost models for governance operations)
  - Compiled execution-boundary enforcement (constraints the agent cannot violate)

  These are classes of capability that require infrastructure CGG deliberately avoids.
  When you hit the ceiling, you'll know — the symptoms are described in
  [ARCHITECTURE.md](ARCHITECTURE.md#6-scaling-ceiling). No external repos required.
  The flat-file primitives become the audit trail beneath whatever substrate you adopt.
  ```

- [ ] Remove the specific Ubiquity naming from the scaling ceiling prose (lines 337, 349). Keep it in the maintainers section (line 404) where it's attribution, not dependency.

**Remove/avoid**:
- Don't add install steps
- Don't add daily workflow (that's DEV-README / START-HERE)

---

### DEV-README.md
**Intent**: Practical developer guide. How the pipeline works, how to extend it, daily workflow.

**Keep**:
- The DevOps mapping table (lines 17-27) — killer framing
- The Mermaid session flow (lines 30-97) — shows the full pipeline
- The daily workflow section (lines 140-155)
- The commands table (lines 156-163)
- The deterministic assessor section (lines 164-171)
- Measuring impact (lines 184-192)

**Changes**:
- [ ] Lines 7-9: Audience callouts. Rewrite to be ladder-consistent: "**Just want the commands?** [START-HERE.md](START-HERE.md). **Full architecture and design rationale?** [README.md](README.md) and [ARCHITECTURE.md](ARCHITECTURE.md)."
- [ ] Lines 99-124 ("The 100k rule"): This section is the biggest cadence timing fix target.
  - Line 99 heading: change "The 100k rule" to "Session cadence and the 100k heuristic"
  - Line 101: "Around 100k tokens, Claude Code loses grip" — reframe to: "Context windows are finite. Around 100k tokens, early-session context starts getting stale — this is a heuristic, not a hard wall. Some sessions run longer, some shorter. The point is: end the epoch before the agent's reasoning degrades."
  - Line 103: "Hit `/cadence` at or before the 100k mark" — change to: "Run `/cadence` when the session feels ready to wrap — 100k tokens is a reasonable checkpoint, not a countdown timer."
  - Add after line 103 (new paragraph):
    ```
    If you've blown past the heuristic and context is visibly degrading (repetition,
    forgetting earlier decisions, slow responses), use `/cadence double-time`. It
    produces a valid handoff with minimal ceremony: tic + compact plan, no signal tick
    or conformation snapshot. The next session can run a full downbeat when context is
    fresh. Think of it as the emergency exit — same building, different door.
    ```
- [ ] Add a new subsection after the cadence timing section: "### Zone scanning and governance surface"
  ```markdown
  ### Zone scanning and governance surface

  CGG scans specific files, not everything. The zone scan rule:

  1. Project root = directory containing `.ticzone` (or CWD if no zone file)
  2. Governance files = `**/CLAUDE.md` and `**/MEMORY.md` inside the zone
  3. Auto-memory (`~/.claude/projects/*/memory/MEMORY.md`) is always included
  4. `.ticignore` exclusions are applied (default: vendor/, node_modules/, .git/, .claude/skills/)
  5. Blocks with `status: "example"` are skipped (documentation templates)

  This prevents phantom counts from template files, vendor docs, and archived skill
  definitions. If your `/review` docket shows unexpected pending CPRs, check whether
  `.ticignore` covers the source directory.
  ```
- [ ] Lines 126-133 (Packages section): Add a mention of `.ticzone`/`.ticignore` as part of what the runtime package expects: "The runtime assumes `.ticzone` and `.ticignore` at project root for scan boundary resolution. Install creates these if missing."
- [ ] Line 180: "That ceiling is where Ubiquity's deeper layers begin: embedding-based recall, graph topology, expression gating, conformation-aware retrieval. Those need infrastructure CGG deliberately avoids." — Reword to remove the name: "That ceiling is where deeper substrate layers begin — embedding-based recall, graph topology, expression gating, conformation-aware retrieval. Those need infrastructure CGG deliberately avoids." (Same meaning, no coupling.)

**Remove/avoid**:
- Don't add signal physics or conformation theory here
- Don't add install steps (point to INSTALL.md)

---

### ARCHITECTURE.md
**Intent**: Deep theory for system designers. The "why" behind every "what."

**Keep**:
- Five-tier knowledge taxonomy (lines 10-33)
- Performance physics (lines 34-49)
- Plan Mode hijacking (lines 50-59)
- Ripple assessor (lines 61-63)
- Tics/zones/conformation (lines 65-103)
- Scaling ceiling with Ubiquity layers table (lines 105-143)
- Measuring impact (lines 145-153)
- The promoted CogPR block (lines 155-172) — leave as-is, it's a living artifact

**Changes**:
- [ ] Add "Who this is for" block at the top (after line 1): "This is the deep theory. If you want to use CGG, see [START-HERE.md](START-HERE.md). If you want the practical developer guide, see [DEV-README.md](DEV-README.md). If you want the full reference, see [README.md](README.md)."
- [ ] Lines 34-49 (100k Token Cycle): Reframe.
  - Line 34 heading: keep "The 100k Token Cycle (Performance Physics)" — the heading is fine in an architecture doc
  - Line 41: "You do not 'power through' at 120k+ tokens. You end the epoch on purpose." — This is good and sharp. Add after it: "100k is a heuristic. The real boundary is cognitive degradation — when the agent starts contradicting itself, forgetting earlier context, or producing low-quality output. For most models, that starts around 100k. When you're past it and haven't called `/cadence`, use `/cadence double-time` for a minimal viable exit: tic + compact plan, skip signal tick and conformation."
- [ ] Lines 79-86 (Jurisdictional scoping): Add `.ticignore` treatment. After line 85 ("Structurally correct..."), add:
  ```markdown
  `.ticignore` complements the zone definition with exclusion filtering. Where `.ticzone`
  says "this is my jurisdiction," `.ticignore` says "except these paths." v1 supports
  directory-level exclusions only — intentionally simple. The zone scan rule resolves
  in order: zone boundary first (what's in), exclusion filter second (what's out).
  Governance surface = CLAUDE.md + MEMORY.md files inside the zone minus excluded paths.
  ```
- [ ] Lines 105-143 (Scaling Ceiling): This section names Ubiquity explicitly and appropriately for an architecture doc. Keep the name here — this is the one place where naming the methodology is architectural attribution, not dependency coupling. But add a sentence making the boundary explicit (after line 122):
  ```markdown
  CGG's docs do not depend on the substrate's docs. The categories above describe
  classes of capability, not specific implementations. Any system providing these
  capabilities composes with CGG's governance lifecycle.
  ```
- [ ] Add `.ticignore` v1 spec note in the jurisdiction section: "v1 of `.ticignore` supports directory-level exclusions only (trailing `/` patterns). Full gitignore glob semantics are not implemented. This is a documented constraint."

**Remove/avoid**:
- Don't simplify the language — this is the architect tier
- Don't add install instructions
- Don't add daily workflow

---

### cogpr/README.md
**Intent**: Convention layer reference. What CogPRs are, how to flag them, platform variants.

**Keep**:
- v3 changelog (lines 5-10)
- Variants table (lines 12-18)
- Platform-specific sections (lines 20-29)
- Standalone usage note (lines 31-36)
- Signal primitives table (lines 38-44)
- Band budget table (lines 46-53)

**Changes**:
- [ ] Add "Who this is for" block at top: "Convention reference for CogPR/Signal/Warrant block formats. For the automation pipeline, see [cgg-runtime/](../cgg-runtime/skills/README.md). For the full architecture, see [README.md](../README.md)."
- [ ] Add the three new optional birth context fields to the CogPR format description (mention them as optional, present when posture is in use):
  ```markdown
  ### Optional birth context fields (v3.1)
  - `posture`: Agent posture at discovery (e.g., "ENG/META", "OPS/DIRECT")
  - `cwd_context`: Working directory relative to project root
  - `birth_tic`: Nearest tic count at discovery time
  ```
- [ ] Add posture as an optional convention (short — 3 lines max). Point to INSTALL.md for the full posture table.

**Remove/avoid**:
- Don't add pipeline mechanics — that's cgg-runtime/
- Don't add zone/ignore concepts — cogpr is the convention layer only

---

### cgg-runtime/skills/README.md
**Intent**: Runtime pipeline reference. How the automation works.

**Keep**:
- v3 changelog (lines 5-12)
- Components table (lines 14-28)
- How it works pipeline (lines 35-43)
- Signal lifecycle (lines 45-53)
- Standalone guarantee (lines 55-61)
- Safety rules (lines 63-73)

**Changes**:
- [ ] Add "Who this is for" block at top: "Runtime pipeline reference. For the convention layer, see [cogpr/](../../cogpr/README.md). For daily usage, see [START-HERE.md](../../START-HERE.md)."
- [ ] Components table (lines 14-28): Already accurate post-rename. Verify all deprecated skills are listed with `[DEPRECATED]` tag.
- [ ] How it works pipeline (line 37): "Session ends -> PreCompact writes plan file" — this is slightly inaccurate. `/cadence` writes the plan file via EnterPlanMode. Reword: "Session ends -> `/cadence` writes handoff plan with `cgg-evaluate` trigger block"
- [ ] Add a note about zone scan rule affecting step 2 (SessionStart hook): "SessionStart hook scans for pending CogPRs using the zone scan rule: `**/CLAUDE.md` + `**/MEMORY.md` only, `.ticignore` exclusions applied. See DEV-README for the full rule."
- [ ] Add `/cadence double-time` to the "How it works" section as an alternative path: "For emergency exits, `/cadence double-time` writes a compact handoff (tic + plan, no signal tick or conformation) — the pipeline still fires on next session start."

**Remove/avoid**:
- Don't duplicate the zone scan rule in full — reference DEV-README
- Don't add architecture theory

---

## C) Refactor Sync Notes (for the implementation agent)

### Code-to-doc mapping

| Doc claim | Authoritative code file | What to verify |
|-----------|------------------------|----------------|
| Zone scan rule (CLAUDE.md + MEMORY.md only) | `cgg-runtime/hooks/session-restore-patch.sh` lines 62-84 | `--include=CLAUDE.md --include=MEMORY.md`, `.ticignore` reading loop, `status.*example` filter |
| Zone scan rule (review skill) | `cgg-runtime/skills/review/SKILL.md` Step 2 | Glob targets, exclusion list, example skip |
| Zone scan rule (siren conformation) | `cgg-runtime/skills/siren/SKILL.md` Step 4 | Glob targets, exclusion list, example skip |
| Birth context fields on CogPR | `cgg-runtime/skills/cadence/SKILL.md` Step 2 | `posture`, `cwd_context`, `birth_tic` as optional fields |
| Scope resolution rule | `cgg-runtime/skills/cadence/SKILL.md` Step 2 | Nearest CLAUDE.md walk-up, MEMORY.md fallback |
| `.ticzone` format | README.md lines 278-295 | JSONC fields match what code actually reads |
| `.ticignore` behavior | `session-restore-patch.sh` lines 66-79 | Directory-only exclusions, default fallback list |
| Install modes A/B/C | `INSTALL.md` bootstrap prompt | File copy matrix matches actual skill/hook/agent dirs |
| Proposals landing path | `cgg-runtime/hooks/cgg-gate.sh` | Output to `~/.claude/grapple-proposals/latest.md` |
| Deterministic assessor | `cgg-runtime/hooks/session-restore-patch.sh` lines 79-81 | `scripts/ripple-assessor.py` check + fallback |
| Cadence double-time | `cgg-runtime/skills/cadence/SKILL.md` Mode: Double-Time | Tic with `cadence_position: "syncopate"`, compact plan format |
| Deprecated skill redirects | `cgg-runtime/skills/{cadence-downbeat,cadence-syncopate,grapple}/SKILL.md` | Each contains only a redirect message |
| Signal store format | `cgg-runtime/skills/siren/SKILL.md` | JSONL at `audit-logs/signals/YYYY-MM-DD.jsonl`, latest-entry-per-ID-wins |
| Posture convention | `INSTALL.md` convention block | Posture table, advisory framing, CogPR field mention |

### Lockstep claims (must be updated together)

These doc statements mirror code behavior directly. If one changes, the other must:

1. **Scan surface**: "CLAUDE.md + MEMORY.md only" appears in: review/SKILL.md Step 2, siren/SKILL.md Step 4, session-restore-patch.sh, DEV-README zone scanning section, README zone scan rule callout. All five must match.
2. **Default exclusions**: "vendor/, node_modules/, .git/, .claude/skills/" appears in: session-restore-patch.sh default fallback, review/SKILL.md Step 2 default, siren/SKILL.md Step 4 default. All three must match.
3. **Example skip**: "`status: "example"` are not counted" appears in: session-restore-patch.sh grep filter, review/SKILL.md Step 2, siren/SKILL.md Step 4. All three must match.
4. **Proposals output path**: `~/.claude/grapple-proposals/latest.md` appears in: cgg-gate.sh, session-restore-patch.sh, review/SKILL.md Step 1, cgg-runtime/skills/README.md. All four must match.
5. **Cadence double-time semantics**: "tic + compact plan, no signal tick or conformation" appears in: cadence/SKILL.md double-time section, START-HERE FAQ, DEV-README cadence section, README 4/4 cadence, ARCHITECTURE.md performance physics. All must be consistent.
6. **Install file copy matrix**: INSTALL.md bootstrap prompt lists files → actual dirs in `cgg-runtime/skills/`, `cgg-runtime/hooks/`, `cgg-runtime/agents/`. If a skill is added/removed/renamed, both must update.

### Post-refactor checklist

After any code change to scan behavior, zone handling, or install flow:

- [ ] Run `grep -r "agnostic-candidate" . --include="*.md" | grep "pending" | wc -l` (raw) vs ticignore-filtered count — raw should be higher
- [ ] Verify install modes A/B/C bootstrap prompt matches actual directory contents (`ls cgg-runtime/skills/`, `ls cgg-runtime/hooks/`, `ls cgg-runtime/agents/`)
- [ ] Verify proposals land at `~/.claude/grapple-proposals/latest.md` (grep all files for this path)
- [ ] Verify `.ticignore` behavior: create a test file in an ignored dir with a pending CPR block, run the hook, confirm count excludes it
- [ ] Verify deprecated skills contain ONLY redirects (no duplicate logic)
- [ ] Verify cadence double-time description matches actual cadence/SKILL.md Mode: Double-Time section
- [ ] Verify `.ticzone` JSONC format documented in README matches what `siren conformation` actually reads
- [ ] Check that no doc file references an external repo by URL as a dependency or link target (Ubiquity naming in maintainers/attribution sections is fine)
- [ ] Run `bash -n` on both shell hooks after any edit
