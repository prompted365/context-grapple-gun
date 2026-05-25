# CGG Domain — Deprecated Docs Manifest

CGG sub-repo doc-currency cleanup lane. Pairs with federation manifest at
`audit-logs/deprecated-docs/_DEPREC_MANIFEST.md`.

## Convention

Per-repo deprec lanes. The CGG sub-repo manages its own deprec — federation
repo's deprec lane does NOT (and cannot) host CGG-domain files because of git
repo boundaries. Path inside this folder mirrors the original CGG-relative path.

Same three-filter discipline as federation manifest:

1. **NOT load-bearing** — not a CLAUDE.md, SKILL.md, agent .md, runtime-script-
   referenced, constitution-ledger, or effective-state surface.
2. **NOT current** — explicit `SUPERSEDED`/`DEPRECATED`/`LEGACY` marker OR
   genesis-era (Mar 8) untouched, orphaned-by-currency.
3. **Absorbed elsewhere OR snapshot-only refs** — content is single-tic
   historical OR only referenced from snapshot/consolidation artifacts (not
   live source surfaces).

## Tranche 5 — tic 292 (executed 2026-05-25)

CGG-domain genesis-era orphan reference docs + early authoring drift audits.
All have either zero incoming refs OR refs only from snapshot/historical
artifacts (tic 238/239 consolidation dumps, 2026-04-22 authoring-convention
swarm artifacts). No live CLAUDE.md/SKILL.md/agent reference to any of them.

| Moved | Original path | Marker / Class | Rationale |
|---|---|---|---|
| tic 292 | `docs/cgg-system-diagrams.md` | genesis-orphan (Mar 8) | Zero refs anywhere; ancient diagram doc |
| tic 292 | `docs/IMPLEMENTATION-MAP.md` | genesis-orphan, cohort | Intra-cohort refs preserved by same-dir move; CGG runtime implementation has moved on substantially |
| tic 292 | `docs/LOCKSTEP-INVARIANTS.md` | genesis-orphan, cohort | Same cohort; intra-refs intact |
| tic 292 | `docs/VALIDATION-CHECKLIST.md` | genesis-orphan, cohort | Same cohort; intra-refs intact |
| tic 292 | `docs/LOOP-INTEGRATION.md` | genesis-orphan | Only ref from tic 239 consolidation snapshot |
| tic 292 | `docs/HEADLESS-ENFORCEMENT.md` | genesis-orphan | Only ref from tic 239 consolidation snapshot |
| tic 292 | `docs/COMMIT-HISTORY-CHEATSHEET.md` | genesis-orphan | Only ref from tic 238 consolidation context dump |
| tic 292 | `docs/TERMINOLOGY.md` | genesis-orphan | Refs only from cbux audit + tic 238 consolidation; terminology has been absorbed into GLOSSARY.md (federation root) and CGG CLAUDE.md |
| tic 292 | `PLAN-hook-doc-update.md` | genesis-orphan | Only ref from tic 239 consolidation snapshot; plan was completed and absorbed long ago |
| tic 292 | `SKILLS_FRONTMATTER_DRIFT_AUDIT.md` | LEGACY (tic 209+) | Refs only from 2026-04-22 historical swarm artifacts; drift audit superseded by skill frontmatter standardization at tic 209+ |

## Carried forward (not moved this tranche)

- `cgg-runtime/reference/*.md` — multiple ancient reference docs (Mar 8). Need
  per-file audit; some may be linked from skill bodies. Carry to Tranche 6.
- `convention-block.md` — referenced live from `init-governance` SKILL.md;
  TRULY load-bearing despite genesis-era. Cannot deprec. May need refresh.
- LEGACY SKILL.md files (`cadence-downbeat`, `cadence-syncopate`, `grapple`,
  `init-gun`, `init-cogpr`): runtime-discovered by harness; deprec requires
  redirect shim. Carry to Tranche 4.
- LEGACY agent .md files (`pattern-curator{,-direct,-meta}`, `restoration-
  operator`, `review-execute`): dispatch-loaded by Agent tool; deprec
  requires actor-registry coordination. Carry to Tranche 3.
