# Commit History Cheat Sheet (c283b14 → e6beba1)

Scope: ordered summary of the mainline commits from **c283b14** (first-contact clarity) through **e6beba1** (cheat sheet publication). Each entry notes intent, what changed, what remained open, and how the next commit moved the state forward.

## c283b14 — Restructure README/START-HERE/INSTALL/DEV-README/ARCHITECTURE (2026-03-06)
- **Purpose:** Make first-contact onboarding coherent across entrypoints.
- **Changed:** Reflowed major docs for newcomer guidance and architecture digestion.
- **Gaps:** No runtime enforcement changes; lexical ceiling framing still evolving.
- **Next:** `ade23af` deepened lexical ceiling and pedagogy to close the narrative gap.

## ade23af — Fix lexical ceiling framing; add Academy pedagogy; update validation checklist (2026-03-06)
- **Purpose:** Clarify ceiling limits and pedagogy; harden validation cues.
- **Changed:** Added teaching sections, refined ceiling language, expanded checklist coverage.
- **Gaps:** Still doc-level; runtime guardrails unchanged.
- **Next:** `e4c4ab5` tightened ceiling mitigations and fusion guidance.

## e4c4ab5 — Clarify lexical ceiling mitigations and fusion path (2026-03-06)
- **Purpose:** Spell out mitigations CGG offers vs. when to fuse with substrate.
- **Changed:** Added mitigation list and fusion rationale across ARCHITECTURE/README.
- **Gaps:** Remained theoretical; separation-of-concerns framing still light.
- **Next:** `3b245de` added separation framing and checklist fixes.

## 3b245de — Separation-of-concerns framing; grep flag fixes (2026-03-06)
- **Purpose:** Distinguish governance vs. runtime lanes and fix validation grep usage.
- **Changed:** Added explicit separation language; corrected checklist regex flags.
- **Gaps:** Merge reconciliation pending; runtime still untouched.
- **Next:** `bc45d25` merged the clarity work to mainline.

## bc45d25 — Merge PR #6 (2026-03-05)
- **Purpose:** Consolidate first-contact clarity improvements.
- **Changed:** Brought prior doc revisions onto mainline.
- **Gaps:** No new content; follow-on tightening still required.
- **Next:** `d15f169` logged the next planning checkpoint.

## d15f169 — Initial plan (2026-03-06)
- **Purpose:** Planning stub for subsequent doc tightening.
- **Changed:** No feature/content changes.
- **Gaps:** Awaited concrete edits.
- **Next:** `82a17b4` delivered the doc tightening pass.

## 82a17b4 — Docs: tighten framing and consistency (2026-03-06)
- **Purpose:** Smooth language and align messaging across surfaces.
- **Changed:** Edited READMEs, INSTALL, Academy copy for consistency.
- **Gaps:** Purely editorial; install flow specifics still under refinement.
- **Next:** `ce43c78` merged the refinements.

## ce43c78 — Merge PR #7 (2026-03-05)
- **Purpose:** Land framing/consistency updates.
- **Changed:** Integrates 82a17b4 into mainline.
- **Gaps:** Install bootstrap language still being tuned.
- **Next:** `1a8f40d` planning for install-focused edits.

## 1a8f40d — Initial plan (2026-03-06)
- **Purpose:** Planning stub ahead of installation copy updates.
- **Changed:** None.
- **Gaps:** Install docs still needed polish.
- **Next:** `b89bf8e` refreshed bootstrap language.

## b89bf8e — Update INSTALL bootstrap and lifecycle framing (2026-03-06)
- **Purpose:** Clarify install steps and lifecycle expectations.
- **Changed:** Reworded install guidance to match governance lifecycle.
- **Gaps:** Minor formatting drift remained.
- **Next:** `bb98a42` fixed command prefix consistency.

## bb98a42 — Fix inconsistent command prefix formatting in INSTALL (2026-03-06)
- **Purpose:** Normalize command prefix presentation.
- **Changed:** Formatting-only corrections.
- **Gaps:** Cadence-syncopate positioning still ambiguous.
- **Next:** `120013b` marked cadence-syncopate as legacy.

## 120013b — Unify cadence-syncopate framing as legacy (2026-03-06)
- **Purpose:** Signal that cadence-syncopate is supported but not preferred.
- **Changed:** Adjusted messaging; no runtime behavior changes.
- **Gaps:** Needed merge to publish.
- **Next:** `26157dd` merged install updates.

## 26157dd — Merge PR #8 (2026-03-05)
- **Purpose:** Publish install-description updates.
- **Changed:** Integrated prior install edits.
- **Gaps:** Governance runtime still used TTL semantics.
- **Next:** `06c9ab5` rewrote signal decay constitutionally.

## 06c9ab5 — Constitutional: signals do not expire; acoustic decay replaces TTL (2026-03-05)
- **Purpose:** Align siren with constitutional principle of non-expiring signals.
- **Changed:** Removed TTLs, added decay semantics, warrant gating, dismissal rationale.
- **Gaps:** Hooks/scripts still referenced older assumptions.
- **Next:** `07c1753` hardened session restore and extraction to match.

## 07c1753 — Robust session-restore hook + bundled cpr-extract (2026-03-05)
- **Purpose:** Make session recovery and CogPR extraction resilient.
- **Changed:** Added queue deduping, enrichment scan trigger, tic-count anchoring, bundled cpr-extract.
- **Gaps:** Paths were still cwd-sensitive; zone anchoring missing.
- **Next:** `0571bc0` introduced zone-root anchoring.

## 0571bc0 — Portable governance runtime with zone-root anchoring (2026-03-06)
- **Purpose:** Eliminate stray-tic bugs and make runtime portable.
- **Changed:** Added zone_root resolver, zone-anchored hooks, bundled scanners, subsystem config.
- **Gaps:** tic counting still used deprecated field in extractor.
- **Next:** `c5de129` fixed physical tic counting.

## c5de129 — Fix get_tic_count physical count (2026-03-06)
- **Purpose:** Remove reliance on deprecated tic_count_project accumulator.
- **Changed:** Count tics by physical truth only.
- **Gaps:** Prompt surfaces still referenced TTL and path-first writes.
- **Next:** `ebb2d08` corrected prompt write rules and TTL references.

## ebb2d08 — Prompt correctness: MEMORY-first writes; remove TTL expiry (2026-03-06)
- **Purpose:** Align write rules with constitutional memory-first approach; drop TTL language.
- **Changed:** Updated cadence/review skills, convention docs, and install guidance.
- **Gaps:** Scope labels and bridge surface alignment still stale.
- **Next:** `dfae3b3` and `a345d22` corrected scope mappings.

## dfae3b3 — Scope ladder + bridge surface alignment (Phase 2C) (2026-03-06)
- **Purpose:** Sync skills with 5-rung ladder and bridge surface classification.
- **Changed:** Updated cadence/review/siren skills and ripple-assessor notes.
- **Gaps:** Script verdict labels still said PROJECT.
- **Next:** `a345d22` fixed SCRIPT_CODE labels.

## a345d22 — SCRIPT_CODE scope labels PROJECT → SITE (Phase 2D) (2026-03-06)
- **Purpose:** Ensure verdict labels match new ladder.
- **Changed:** Ripple assessor verdict strings corrected.
- **Gaps:** Documentation still showed 3-rung ladder and TTL references in places.
- **Next:** `f2fe64a` rewrote ladder docs and decay semantics.

## f2fe64a — 5-rung ladder + 4-surface model + bridge surface (Phase 2E) (2026-03-06)
- **Purpose:** Canonicalize ladder (Site→Global) and surface taxonomy.
- **Changed:** Updated README/START-HERE/DEV-README/TERMINOLOGY/ARCHITECTURE/Academy to 5 rungs; swapped TTL to decay semantics.
- **Gaps:** Mogul prompts still missing estate-ops baseline.
- **Next:** `ed5e0bf` added Mogul baseline prompt.

## ed5e0bf — Mogul estate-ops baseline prompt (Phase 3, gap #14) (2026-03-06)
- **Purpose:** Give Mogul a concrete estate-ops starting prompt.
- **Changed:** Added comprehensive mogul.md baseline.
- **Gaps:** Actor model and gate stabilization pending.
- **Next:** `864ff35` stabilized actor model and zone-config actors.

## 864ff35 — Phase 3 actor model stabilization (2026-03-06)
- **Purpose:** Formalize actor hierarchy and delegation boundaries.
- **Changed:** Added actor map (Homeskillet/Mogul/Swann), subordinate ripple-assessor, .ticzone-configurable actors, behavior-surface audit rules.
- **Gaps:** Gate enforcement and audit cycles not yet encoded.
- **Next:** `6c80fcd` implemented gate enforcement.

## 6c80fcd — Phase 4 gate enforcement + audit cycles (2026-03-06)
- **Purpose:** Enforce promotion gates and cadence audit scheduling.
- **Changed:** Ripple-assessor maturity gating, cadence due markers, review-close checks, audit cycle docs.
- **Gaps:** Deeper runtime intelligence and toolchain coverage still missing.
- **Next:** `2542a37` added Mogul runtime intelligence suite.

## 2542a37 — Phase 5 Mogul runtime intelligence (2026-03-06)
- **Purpose:** Add subordinate tools for curation, audit, manifestation tracking, drift detection, uninstall.
- **Changed:** New agents (pattern curator, ladder auditor), scripts (ladder audit, manifestation tracker, runtime sync, uninstall), microscan hook, init-governance skill.
- **Gaps:** Noise/discriminator heuristics rough; drift signals coarse.
- **Next:** `055a940` tightened heuristics and ownership rules.

## 055a940 — Phase 5 tightening (2026-03-06)
- **Purpose:** Reduce false positives and clarify ownership.
- **Changed:** Runtime-sync drift signals differentiated, ladder-audit narrowed, microscan hash check, pattern-curator rubric, init-governance contract sharpened.
- **Gaps:** Doc cleanup and removal of TTL remnants still pending.
- **Next:** `3e52224` performed Phase 6 cleanup.

## 3e52224 — Phase 6 cleanup (gaps 29–33) (2026-03-06)
- **Purpose:** Remove TTL vestiges, align docs, drop legacy skill copies.
- **Changed:** Cleaned IMPLEMENTATION-MAP, README tic example, removed legacy cogpr skills, added siren etymology, carried trip-hazard invariant and extraction pipeline notes.
- **Gaps:** Mandate contract and dimensional separation not yet encoded.
- **Next:** `1942f4a` added activation contract and separation model.

## 1942f4a — Phase 3E: Mogul activation contract + dimensional separation (2026-03-06)
- **Purpose:** Formalize mandate schema and dimension separation across office/actor/runtime/source/governance/trigger.
- **Changed:** Added JSON schema, mandate storage/flow, hook wiring (session start, cadence, review, gate), ownership invariant docs.
- **Gaps:** Mogul posture still executor-shaped; delegation ladder minimal.
- **Next:** `98c28d6` upgraded Mogul to suborchestrator with mandate lifecycle.

## 98c28d6 — Upgrade Mogul to governance suborchestrator + mandate lifecycle (2026-03-06)
- **Purpose:** Elevate Mogul from executor to suborchestrator with mandate lifecycle.
- **Changed:** Expanded mogul.md posture, orchestration ladder, mandate handling; added mandate-write script and schema updates; refreshed hooks/skills and architecture ownership invariant.
- **Gaps:** Ongoing validation and usage guidance (this cheat sheet) pending.
- **Next:** `58b1079` recorded the plan for documenting history.

## 58b1079 — Initial plan (2026-03-06)
- **Purpose:** Planning stub for the commit-history cheat sheet.
- **Changed:** None; sets intent for this documentation update.
- **Gaps:** Needed the actual cheat sheet.
- **Next:** `e6beba1` added the cheat sheet and surfaced it in README.

## e6beba1 — Add commit history cheat sheet and surface it in README (2026-03-06)
- **Purpose:** Publish the commit-history cheat sheet and make it discoverable.
- **Changed:** Added `docs/COMMIT-HISTORY-CHEATSHEET.md` covering c283b14→98c28d6 plus planning, linked from README’s “Audit recent changes.”
- **Gaps:** Future commits after this point should extend this sheet to keep the audit trail current.
- **Next:** Extend with subsequent commits as they land.
