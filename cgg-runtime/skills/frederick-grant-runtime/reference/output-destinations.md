# Output Destinations

Frederick's compositions land as files. Long-form prose does not live in chat. The orchestrator who invokes Frederick uses the Write tool to land each artifact at a canonical path under `publications/` (or, for in-progress drafts, at a staging path), then commits the file narrowly per the federation's commit discipline.

This file declares the destination convention per artifact class, the thoroughness allocation per artifact class, and the editor's-marginalia placement convention.

## Why this is in the skill

Frederick's prose at scale (chronicle volumes, cadence essays, interviews, field-note collections) routinely exceeds 30KB per artifact. Emitting that into chat consumes context window the orchestrator needs for governance work, makes the artifact ephemeral, and fails the federation's audit-trail discipline. Files in `publications/` are versioned, citable, commit-tracked, and durable. Chat is none of those.

The "write-to-file" allocation is binding for any artifact above the brief threshold. Brief artifacts (anti-collapse audit on a draft, French filtration pass, copy-paste chapter starter) may emit inline; everything else writes to file.

## Destination convention

```
publications/<artifact-class>-<tic-or-tic-range>-frederick-grant.md
```

For chronicle volumes specifically:
```
publications/the-ubiquity-chronicles-vol-<roman>-frederick-grant.md
```

For interviews specifically:
```
publications/the-ubiquity-interviews-<descriptor>-fg.md
```

The tail `-frederick-grant.md` (or `-fg.md` for interviews matching the prior naming) signals authorship and prevents collision with non-Frederick publications (state-of-the-federation entries, federation insights reports, etc.).

## Per-class allocation table

| Artifact class | Destination pattern | Thoroughness target | Writes-to-file | Marginalia |
|---|---|---|---|---|
| Ubiquity Chronicles volume | `publications/the-ubiquity-chronicles-vol-<roman>-frederick-grant.md` | 50–150KB; multi-book; preface + books + chapters + epilogue/appendix | Required | Top: provenance flag. Bottom: receipt block, signed orchestrator-primary. |
| Parallel Lane Cadence essay | `publications/parallel-lane-cadence-tic<N>-frederick-grant.md` | 25–50KB; spine + field anchor + main composition (3 lanes) + Athenaeum resonance + Elara pass + unresolved branches + receipt closeout | Required | Top + bottom marginalia. |
| Field Notes (collection) | `publications/field-notes-tics-<A>-to-<B>-frederick-grant.md` | 15–40KB; dated entries; material anchors heavy; granular observations | Required | Top + bottom marginalia. |
| Field Note (single) | `publications/field-note-tic<N>-<descriptor>-frederick-grant.md` | 3–10KB; one site-specific observation | Required when standalone; inline if part of larger composition | Bottom marginalia only. |
| Ubiquity Interview | `publications/the-ubiquity-interviews-<descriptor>-fg.md` | 20–60KB; dialogic register; named interlocutor; threaded turns | Required | Top + bottom marginalia. |
| Audio Annotation | `publications/audio-annotation-<descriptor>-frederick-grant.md` | 5–20KB; marginalia register on a transcript or recording | Required when standalone | Bottom marginalia. |
| Tic 230 Probity passage | `publications/tic230-probity-<descriptor>-frederick-grant.md` | 8–20KB; focused passage on a runtime probity event | Required when standalone | Bottom marginalia. |
| Video Vision Brief | `publications/video-vision-brief-<descriptor>-frederick-grant.md` | 5–15KB; descriptive only, no retained images | Required when standalone | Bottom marginalia. |
| Logan / Wilderness Analysis | `publications/logan-wilderness-<descriptor>-frederick-grant.md` | 10–30KB; analytical register | Required | Bottom marginalia. |
| Duty Scaffold | `publications/duty-scaffold-<descriptor>-frederick-grant.md` | 8–25KB; civic-duty framing | Required | Bottom marginalia. |
| Anti-Collapse Audit | inline OR `publications/anti-collapse-audit-<target>-frederick-grant.md` | 1–5KB; pass on existing draft | Inline default; file when audit is itself the deliverable | None inline; bottom when filed |
| French Filtration | inline OR companion file | 1–5KB; stylistic transformation pass | Inline default | None inline |
| Elara Counterweight | inline (always — it is a sub-stage, not an artifact) | 0.5–3KB section within parent piece | Inline | N/A |
| Copy-Paste Chapter Starter | inline (it is a starter, by definition) | 0.5–2KB starter prompt block | Inline | N/A |
| Primary Invocation | depends on arising register — defer to whatever class the work resolves to | Per resolved class | Per resolved class | Per resolved class |

## Editor's marginalia convention

When marginalia is written into the file, it follows the convention established at tic 230 in the corrected Parallel Lane Cadence essay:

- **Visual register**: blockquote with italicized header `> *[Editor's marginalia, tic <N>. Outside Frederick's voice.]*`
- **Voice attribution**: signed at the close as `— *the orchestrator-primary, ent_homeskillet*` (or whichever voice is appropriate; never as Frederick)
- **Content scope**: provenance, skill metadata, receipt enumeration, runtime status, commit hashes, install-sync confirmations, hydration packet identifiers, intake declarations
- **Placement**:
  - **Top marginalia** (optional): a single brief italic-bracketed flag indicating that provenance lives at the close, so the reader does not assume the opening is unsigned. Two to three lines maximum.
  - **Bottom marginalia** (required for any write-to-file artifact): the full ephemera block, including provenance, receipts, scope of marginalia, and signoff.
- **What does NOT belong in marginalia**: anything Frederick himself can carry — his discipline, his method, his unresolved branches, his comparative apparatus. Those are the artifact, not the ephemera.

## Commit discipline

After Write lands the artifact:

1. Stage the file: `git add publications/<filename>`
2. Stage any audit-log churn from the hydration step (`audit-logs/sentinel/`, `audit-logs/signals/`, `audit-logs/services/cgg-sync-log.jsonl`, etc.)
3. Commit narrowly with a message naming the artifact class, tic range, and (if applicable) RTCH packet ID
4. Push to origin

The commit message follows the federation's `Telos` signoff convention. The commit message is itself outside Frederick's voice — it is the orchestrator's commit log, not part of the published artifact.

## Failure modes

- **Emitting long-form to chat**: consumes context, fails audit, makes the artifact ephemeral. Always Write to file for any artifact above the brief threshold.
- **Committing without audit-log churn**: leaves the working tree dirty. Always include the hydration-step audit-log churn in the commit alongside the artifact.
- **Marginalia inside Frederick's voice**: violates the diegesis discipline (see `profile/04-collapse-zones.md` § Insider Conflation). Marginalia is editor voice, signed accordingly.
- **Wrong destination pattern**: makes the artifact harder to discover. The naming convention is part of the federation's retrieval surface; honor it.

## Cross-references

- Diegesis discipline: `profile/04-collapse-zones.md` § Insider Conflation
- Voice constraints: `reference/runtime-authority-model.md` § Voice constraints
- Hydration protocol: `reference/hydration-protocol.md`
- Federation KI: *Versioning is mandatory* — published artifacts must commit narrowly to the canonical repo
