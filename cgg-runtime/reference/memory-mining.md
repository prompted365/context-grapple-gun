# MEMORY Mining Reference

## Surfaces to scan
- zone-root MEMORY.md
- auto-memory MEMORY.md (`~/.claude/projects/*/memory/MEMORY.md`)
- local CLAUDE.md chain
- signal store

## Patterns to detect
- Recurring workarounds (same fix applied 2+ times)
- Stabilized compensations (behavior correcting for known gap)
- Prompt workaround patterns ("do NOT..." instructions implying failure mode)
- Collaboration patterns (delegation styles, handoff structures)
- Signal-linked truths (MEMORY entries whose subsystem matches active signals)
- Runtime drift corrections (repeated sync/restart notes)

## Output format
Delegate to Pattern Curator for bounded mining, receive findings packet, synthesize into ops routing decisions.

## Ops routing packet
For each finding, classify destination and urgency:

| Destination | Use when |
|-------------|----------|
| deliverable_team | finding implies implementation work |
| ladder_auditor | finding implies structural governance issue |
| review_staging | finding is mature enough for /review |
| mogul_direct | finding requires Mogul-level synthesis |

| Urgency | Meaning |
|---------|---------|
| next_tic | act before next cadence |
| next_review | stage for upcoming /review |
| background | no urgency, track for pattern |
