# CGG Skills — Frontmatter Drift Audit & Duality-Lane Proposal

**Generated:** 2026-04-22
**Scope:** `cgg-runtime/skills/*/SKILL.md` — 30 skills
**Purpose:** assess the gap between the ~40-token frontmatter (the only thing the model sees until invocation) and the 500–11k-token body (the actual procedure). Propose a structured duality-lane description schema that pays a bounded cost to restore invocation accuracy.

---

## 1. Status Summary

Claude Code skills use **progressive disclosure**: the `description` field in frontmatter is the only surface the model sees until the Skill tool is invoked. That surface currently averages 35 tokens. The bodies average ~2,600 tokens — a **74× asymmetry** between what the model uses to *decide whether to invoke* and what it uses to *execute*.

This asymmetry is tolerable when the description fully captures the invocation criteria. It is dangerous when:

1. The body has evolved and the description has not.
2. The description tells the model what the skill **does** but not when **not** to invoke it.
3. Two sibling skills have near-identical descriptions and the model cannot disambiguate.

The current set has all three failure modes. The most damaging is #2 — the model silently **doesn't invoke** a skill because the description does not match the shape of the current task, even though the body contains exactly the right procedure. The operator never sees the miss; the session proceeds "skill-less" and accumulates drift.

**Top drift-risk skills (by git history):**

| Skill | Created | Last modified | Drift | Commits | Risk tier |
|---|---|---|---|---|---|
| cadence | 2026-03-02 | 2026-04-14 | **43d** | **19** | HIGH |
| review | 2026-02-18 | 2026-03-25 | **35d** | **16** | HIGH |
| stage | 2026-03-08 | 2026-04-05 | **28d** | 2 | MEDIUM |
| siren | 2026-02-18 | 2026-03-07 | 17d | 10 | MEDIUM |
| init-governance | 2026-03-06 | 2026-03-08 | 2d | **10** | MEDIUM |
| cadence-downbeat | 2026-02-24 | 2026-03-06 | 10d | 10 | LEGACY (redirect) |
| inbox | 2026-03-30 | 2026-04-10 | 11d | 2 | LOW |
| broll-prompt-engineer | 2026-04-11 | 2026-04-16 | 5d | 6 | LOW |
| podcast-pipeline | 2026-04-11 | 2026-04-16 | 5d | 6 | LOW |

1-commit skills (frontmatter + body born together, lowest drift risk): consolidate, governance-check, governance-mandate-cycle, mini-swarm-onboard, swarm, videographer.

---

## 2. Drift Matrix — Per-Skill Confusion Surface

For each skill: what the frontmatter promises vs what the body delivers, with the specific gaps that create invocation confusion. Drift flag = git-history evidence of body evolution without matching frontmatter revision.

| Skill | Drift flag | Confusion type | Specific gap |
|---|---|---|---|
| **cadence** | YES (43d / 19c) | Invocation-when / Not-when / Sibling | Body describes plan-mode hijack, Mogul mandate cascade, due markers, `Session Projection` as grapple-vs-sidecar duality — NONE in description. No anti-conditions ("don't run during chores", "don't run after small edits"). No relation to /review or /siren. |
| **review** | YES (35d / 16c) | Feature-undisclosed / Prereq-undisclosed | Body has Harmonic Triad Alerts, precomputed ripple-assessor proposal ingestion, governance query pre-check, review-execute subordinate dispatch, protected-files list. Description mentions none of these. Model may fail to check `~/.claude/grapple-proposals/latest.md` first. |
| **stage** | YES (28d / 2c) | Mode-undisclosed | Body has interactive/direct/spec/dry-run modes + arena registry + post-processing report pipeline. Description is one sentence of verbs. |
| **siren** | YES (17d / 10c) | Semantic-scope / Constitutional-principle | Description says "signal emission, tick advancement, triage dashboard". Body carries 5 constitutional principles (signals don't expire, tic is time authority, PRIMITIVE floor, warrant eligibility kind-gating). These principles shape correct usage but are invisible until invocation. |
| **init-governance** | YES (2d / 10c) | Low visible drift, high churn | 10 commits in 2 days — heavy initial iteration, frontmatter stabilized early. Probably current, but worth spot-check. |
| **mini-swarm-onboard** | NO but **schema mismatch** | Frontmatter-format | Uses a different frontmatter schema (`tools:`, `trigger:`, `arguments:` with nested `description:` keys) — not the standard `name` / `description` / `user-invocable` triplet. Naive YAML-like parsers can grab the wrong `description:` (validated: my first-pass scan grabbed the `--dry-run` arg's description, "Print the arena spec without executing"). Standard skill listing in the runtime gets it right, but this is an outlier format. |
| **consolidate** | NO (1c) | Over-long description (214 chars) | Already approaches the rich-duality structure informally; missing only explicit anti-conditions. |
| **inbox** | NO (11d / 2c) | Good baseline | Description correctly includes scope signal ("Any citizen or office can use this"). Missing: when NOT to use (single-item reads, no active mailbox). |
| **statusline** | NO (1d / 2c) | Body-duality present, frontmatter-duality absent | Body explicitly lists "It does NOT: …" — exactly the duality pattern we want, but only visible after invocation. Description says "read-only conformation radar" — close but incomplete. |
| **videographer** | NO (0d / 1c) | Subagent-delegation-unstated | Body has "Agent Delegation" section; description does not mention when to delegate vs run directly. |
| **swarm** | NO (0d / 1c) | Sibling-disambiguation absent | Body opens with "Unlike `/stage` (adversarial reasoning)…" — the distinction that prevents misrouting lives in the body, not the frontmatter. |
| **governance-check** | NO (0d / 1c) | Good | `/loop`-target usage hint present. |
| **governance-mandate-cycle** | NO (0d / 1c) | Good | Mentions spawning mechanism (Mogul background agent). |
| **audience-context-researcher** | NO (4d / 3c) | Good | Scope-narrow and clear. |
| **broll-prompt-engineer** | LOW (5d / 6c) | Role-only description | "writes prompts that serve meaning, not just illustration" — poetic, not invocation-criteria. |
| **caption-semantic-layer** | LOW (5d / 5c) | Architecture-name as description | "Two-tier caption architecture — key semantic + subtitle fill with no-double enforcement" — assumes reader knows what "no-double enforcement" means. |
| **complement** | NO (0d / 3c) | Esoteric language | "Closure inference and response-geometry disclosure" is accurate but dense. New sessions may skip past it. |
| **edit-decision-list** | LOW (4d / 5c) | Good | J/L-cut scope signal present. |
| **homeskillet-academy** | NO (3d / 4c) | Good | Audience ("narrative simulations, live demos") is clear. |
| **init-cogpr** | DEPRECATED | Deprecated marker present | Description begins `[DEPRECATED — use the bootstrap prompt in INSTALL.md]`. Safe. |
| **init-gun** | DEPRECATED | Deprecated marker present | Same pattern. Safe. |
| **cadence-downbeat** | LEGACY | Redirect marker present | Description begins `[LEGACY — prefer /cadence]`. Safe. |
| **cadence-syncopate** | LEGACY | Redirect marker present | Same. Safe. |
| **grapple** | LEGACY | Redirect marker present | `[LEGACY — prefer /review]`. Safe. |
| **pipeline-report** | LOW (4d / 4c) | Good | Role+output+deliverable-style clear. |
| **podcast-conductor** | LOW (4d / 5c) | Good | Explicitly says "Read this first" — strong self-orienting hint. |
| **podcast-pipeline** | LOW (5d / 6c) | Good | Scope clear. |
| **post-copy-generator** | LOW (3d / 2c) | Good | Platform + voice + rationale signaled. |
| **show-profile-manager** | LOW (4d / 4c) | Good | CRUD verbs + scope ("podcast pipeline") clear. |
| **transcript-scorer** | LOW (4d / 3c) | Good | Lens ("audience context") as disambiguator. |

**Summary counts:**
- HIGH-risk drift: 2 (cadence, review)
- MEDIUM-risk drift: 3 (stage, siren, init-governance)
- LEGACY/DEPRECATED (safe): 5 (cadence-downbeat, cadence-syncopate, grapple, init-cogpr, init-gun)
- Frontmatter-format outlier: 1 (mini-swarm-onboard)
- Low drift, good baseline: 19

---

## 3. Confusion Taxonomy

The matrix surfaces five distinct failure modes. Each demands a different fix in the description:

| # | Mode | Symptom | Fix |
|---|---|---|---|
| 1 | **Invocation-when gap** | Body knows exactly when to run; description is a verb list. Model under-invokes. | Add explicit "WHEN" clause tied to lifecycle / state / posture. |
| 2 | **Anti-invocation gap** | No "IS NOT" boundary. Model over-invokes or routes to wrong neighbor. | Add "IS NOT / NOT WHEN" clause naming the confusable neighbor. |
| 3 | **Feature-undisclosed** | Body has modes/flags/prerequisites the description omits. Model uses skill but misses critical mode (e.g., /review skipping the precomputed-proposals check). | Surface the mode set or prerequisite in description, even if one phrase. |
| 4 | **Sibling-disambiguation** | Two sibling skills compete for the same shape of work. Description does not name the neighbor. | Reference the neighbor by name in the description ("sibling to /X; use X when …"). |
| 5 | **Schema mismatch** | Frontmatter uses a non-standard key structure (nested descriptions, tools:, trigger:). Parsers and humans both get confused. | Normalize to the standard skill schema. Extension fields (tools, arguments) belong in body-level sections, not frontmatter, unless the runtime enforces them. |

Drift risk (git history) is an **amplifier** on all five — a skill with 19 body commits and 0 frontmatter revisions almost certainly has at least one of these modes present.

---

## 4. Duality-Lane Proposal — Structured Semantic Description

### Current shape (cadence example, 36 tokens)

```yaml
name: cadence
description: Session epoch boundary — emits canonical tic, captures lessons, writes handoff. Default is downbeat; use "double-time" for emergency syncopate.
user-invocable: true
```

### Proposed shape (cadence example, ~130 tokens)

```yaml
name: cadence
description: |
  Session epoch boundary. Emits canonical tic, captures lessons, writes a handoff as a plan-mode projection that persists across sessions via Claude Code's native plan UI.
  IS: the ONE place the handoff gets written; the clock of the Ubiquity governance system. Default mode is downbeat (full); `double-time` is emergency syncopate (<=5% context).
  IS NOT: inline governance mutation, Mogul spawn, or a /review worker — it is the clock, not the operator. Not a memory write, not a signal emitter, not a CogPR extractor.
  WHEN: once per tic, at session end or before context clear. Also on mid-session epoch boundaries when posture shifts materially (workspace change, scope pivot).
  NOT WHEN: during chores (chores are appetizers — real work happens alongside), after small single-step edits, or when the active plan already covers the current thread.
  RELATES TO: /review (governance judgment; runs on its own schedule after cadence), /siren (signal ops; cadence calls it implicitly via cadence-ops.py), Mogul mandate (cadence writes the mandate; Mogul consumes it next session).
user-invocable: true
```

### Structural invariants of the duality lane

Every proposed description fills the same five slots in the same order. This lets the model scan descriptions cheaply and compare across siblings:

| Slot | Label | Purpose |
|---|---|---|
| 1 | Lead sentence | Semantic anchor. What the skill *is* in system-level language. Same as today's descriptions, kept. |
| 2 | **IS:** | Sharpened definition, including mode set. What it positively commits to. |
| 3 | **IS NOT:** | Boundary. Names the confusable neighbors by role ("not a …") and the wrong-routing failure mode. |
| 4 | **WHEN:** | Invocation criteria tied to lifecycle state, posture, or observable conditions — not just intent. |
| 5 | **NOT WHEN:** | Anti-conditions. The operator's past corrections live here. |
| 6 | **RELATES TO:** | Sibling skills named explicitly. Prevents silent mis-routing. |

### Cost accounting

- Current avg description: ~35 tokens. Current total (30 skills): ~1,050 tokens always-loaded.
- Proposed avg description: ~120 tokens. Proposed total (30 skills): ~3,600 tokens always-loaded.
- **Delta: +2,550 tokens per session** of always-loaded frontmatter.

Trade-off: this is permanent cost against a cache-friendly surface (the skill frontmatter is stable across sessions, so it caches well). Against it, we gain protection against the silent-miss failure — a single session where the model flies skill-less on a 6,000-token skill body like cadence's is already ≥6,000 tokens of lost efficiency. The amortized break-even is roughly one prevented miss every 2-3 sessions.

### Compatibility

- YAML `description: |` blocks are valid skill frontmatter (literal block scalar). Claude Code's skill loader already handles multi-line descriptions.
- The `user-invocable: true` field stays at the same indent level — unchanged.
- No runtime change required. This is a pure frontmatter migration.

---

## 5. Concrete Before/After — Four High-Risk Skills

### cadence (see section 4 for full proposed form)

Critical additions: plan-mode hijack semantics, "once per tic at session end" cadence, anti-condition for chore contexts, explicit relationship to Mogul mandate.

### review (proposed)

```yaml
description: |
  Human-gated CogPR promotion + Warrant triage across CLAUDE.md scopes — the constitutional review gate.
  IS: the judgment surface where pending CogPRs advance to doctrine and Warrants receive triage. Consumes precomputed ripple-assessor proposals from ~/.claude/grapple-proposals/latest.md when available.
  IS NOT: a CogPR author (use `<!-- --agnostic-candidate -->` blocks), a signal manipulator (use /siren), or a promotion executor (dispatches to review-execute subordinate).
  WHEN: scheduled at cadence-computed `review_due_tic`; when enrichment_eligible CPRs accumulate; when Warrants surface in Harmonic Triad Alerts; when a governance-query pre-check shows actionable pipeline state.
  NOT WHEN: queue is empty or all entries are blocked on enrichment; during /cadence (cadence is the clock, /review is the judge).
  RELATES TO: /cadence (schedules the review); /siren (provides signal state for triage); review-execute (subordinate that applies approved verdicts).
```

### stage (proposed)

```yaml
description: |
  Governed reasoning arena launcher — orchestrates adversarial multi-agent deliberation to produce high-confidence governance inputs.
  IS: the spawning surface for governed-triangulation (3-agent), tournament-lattice (5-7 agent), and dyadic (2-agent) arenas. Supports interactive, --decision, --spec resume, --template override, --mode operational|experimental, and --dry-run modes.
  IS NOT: a deliverable-producing swarm (use /swarm), a signal emitter (arenas produce pressure reports which /siren may ingest), or a CogPR authoring tool (arenas may surface CogPR candidates as side effect).
  WHEN: deciding between 2+ structurally distinct positions; when a decision merits governance-grade evidence (signals, lessons, CogPRs); when adversarial reasoning is needed to break consensus drift.
  NOT WHEN: the decision is tactical (single-actor, local scope), when only one position exists (use direct reasoning), or when parallel deliverable work is needed (use /swarm).
  RELATES TO: /swarm (sibling; adversarial vs parallel-deliverable distinction); arena-report-agent (post-processor); /review (consumer of arena-produced CogPRs).
```

### siren (proposed)

```yaml
description: |
  Signal manifold operations — daily-ops dashboard for CGG v3 signals and warrants (companion to /review's board-meeting cadence).
  IS: emitter (signal creation), ticker (tic advancement with decay/accrual), router (band-gated dispatch), and triage dashboard. Honors constitutional principles: signals do not expire; tic is the time authority; PRIMITIVE band has a volume floor; warrant eligibility is kind-gated.
  IS NOT: a governance judgment surface (use /review), a cadence emitter (use /cadence), or a signal-resolution executor (resolution is a human decision, /siren records it).
  WHEN: new condition observed in the system; tic advancement due; signal state change warranted (acknowledge, dismiss, resolve); volume-30+ signal needs triage before other work.
  NOT WHEN: during /cadence (cadence-ops.py calls the conformation writer directly; inline /siren tick duplicates); when the pipe already routed through /review in the same tic.
  RELATES TO: /review (triage handoff); /cadence (implicitly calls signal state for conformations); Mogul (consumes signal scan via mandate cycle).
```

---

## 5a. Compatibility Note — Sections 4 and 5 (tic-164)

**Status as of tic-164:** Sections 4 and 5 above are the *proposal record* for the duality-lane description schema. They remain authoritative as historical reference and rationale.

**Authoritative shape going forward:** The canonical v2.1 schema, three-tier stratification, field definitions, worked `/cadence` example, authority path, failure modes, rollback procedure, and substrate deferral section now live in:

> `canonical_developer/context-grapple-gun/AUTHORING_CONVENTION.md`

`AUTHORING_CONVENTION.md` supersedes Sections 4 and 5 as the normative specification for skill frontmatter authoring. When authoring or auditing skill frontmatter, consult `AUTHORING_CONVENTION.md` as the single source of truth. Sections 4 and 5 here are preserved for lineage context only — do not use them to resolve schema questions.

**Pilot status:** `/cadence` is the first skill to adopt the v2.1 convention (PILOT APPLIED, tic-164, Run 2, Agent β). The `/cadence` `SKILL.md` frontmatter now carries the full v2.1 shape including `CENTROID`, `IS`, `IS NOT` (with `collapse_zones` and `sibling_overlaps`), `WHEN`, `NOT WHEN`, `RELATES TO`, and `ARGS` (with `core_dispatch_rays` and `secondary_modulation_axes`). The drift risk table in Section 1 for the `cadence` entry retains its historical HIGH classification; its drift status post-pilot is governed by the ladder auditor via `AUTHORING_CONVENTION.md` audit phases.

---

## 6. Recommended Next Actions

Ordered by leverage.

1. **Pilot the duality rewrite on cadence** — highest drift, highest body size, most load-bearing for session hygiene. One rewrite, test for one session, measure invocation accuracy.
2. **Rewrite review, stage, siren** — the MEDIUM-tier drifters with heavy bodies. These three plus cadence cover ~70% of the silent-miss risk surface.
3. **Normalize mini-swarm-onboard frontmatter** — convert from the `tools:`/`trigger:`/`arguments:` schema to the standard triplet; move argument descriptions into body. This is a parser-correctness fix, not a content fix.
4. **Add anti-conditions to the 19 low-drift good-baseline skills in a batch** — cheaper per-skill because their IS/WHEN clauses are already accurate; only the IS NOT / NOT WHEN / RELATES TO need authoring.
5. **Add a skill-frontmatter lint** — a pre-commit check that parses skill frontmatter, confirms the standard triplet, and flags descriptions under 80 chars or over 500. Cheap, catches regression.
6. **Constitutional question (routes to /review)** — is the duality-lane description schema a doctrine-promotion candidate, or does it stay as a CGG-runtime convention? It touches how skills disclose themselves, which affects routing, selection, and elimination — arguably a Rationale-as-Connective-Tissue matter. Worth asking at the next /review whether this deserves invariant status.

---

## 7. Open Questions

- **Description length ceiling.** Claude Code's skill listing UI in `/skills` may truncate at some length; the 120-token proposal is within safe bounds but should be validated against the rendered dialog.
- **YAML literal block vs folded block.** `|` preserves newlines (proposed), `>` folds them. `|` is chosen because the slot labels benefit from being on their own lines when the model reads them; folded form may be fine and cheaper to author.
- **Does the duality schema belong in the skill spec (cgg-runtime/skills/README.md) as a convention, or in CLAUDE.md as an invariant?** Leaning toward README convention for now; promote to invariant only if a drift-related incident validates the need.
