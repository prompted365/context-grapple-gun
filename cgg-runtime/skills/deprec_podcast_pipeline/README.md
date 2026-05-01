# deprec_podcast_pipeline

Deprecated at tic 206 by operator decision. The 10 podcast pipeline skills are preserved here as artifacts but are no longer registered as user-invocable skills.

## What's deprecated

All 10 skills that composed the podcast longform-to-shortform editorial intelligence pipeline:

- `podcast-conductor` — pipeline system manual
- `podcast-pipeline` — team orchestrator entry point
- `show-profile-manager` — show profile CRUD
- `audience-context-researcher` — runtime platform intel
- `transcript-scorer` — editorial scoring
- `edit-decision-list` — audio-first EDL with J/L cuts
- `broll-prompt-engineer` — scene-aware b-roll prompts
- `caption-semantic-layer` — two-tier caption architecture
- `post-copy-generator` — platform copy from show voice
- `pipeline-report` — HTML editorial report

## Why deprecation, not deletion

Per operator framing at tic 206 + the vendor marketplace doctrine (`cpr_vendor_marketplace_as_governed_relationship_doctrine_tic206`), the pipeline's substance survives in the form that matters: the infrastructure routers (`fal_router.py`, `overshoot_router.py`) are kept as **vendor trajectory lanes** at `cgg-runtime/scripts/media-router/`, retained for the upcoming vendor marketplace surface. The skill orchestration layer is preserved here as historical artifact and reference material, but unregistered from the live skill registry.

## How they were unregistered

Claude Code skill discovery scans `~/.claude/skills/*/SKILL.md` (one level deep). Wrapping the skills under `deprec_podcast_pipeline/` puts them at depth 2, making them invisible to the registry without deletion.

`sync-manifest.json` `exclude_patterns` extended with `deprec_*` so runtime-sync explicitly does not track or re-install the deprecated tree.

## What survives as live infrastructure

- `cgg-runtime/scripts/media-router/fal_router.py` — vendor trajectory lane (image/video generation egress, fal.ai)
- `cgg-runtime/scripts/media-router/overshoot_router.py` — vendor trajectory lane (visual adjudication via Overshoot)
- `cgg-runtime/scripts/media-router/fal_model_index.json` — model index for fal_router

These three remain installed and registered for runtime sync.

## How to revive

If a future surface (vendor marketplace UI, alternate creative pipeline) needs any of these orchestration patterns, copy the relevant skill back to `cgg-runtime/skills/<name>/` (depth 1) and re-run runtime-sync. The skills will re-register at next session start.

## Related artifacts (not deprecated)

- `~/.claude/projects/-Users-breydentaylor-canonical/memory/project_podcast-pipeline-build.md`
- `~/.claude/projects/-Users-breydentaylor-canonical/memory/project_pipeline-*.md` (assembly lessons, EDL grounding, retrieval architecture, morph b-roll validation, caption surface doctrine gap)
- `~/.claude/projects/-Users-breydentaylor-canonical/memory/project_overshoot-adaptor-assess.md`
- `~/.claude/projects/-Users-breydentaylor-canonical/memory/project_vendor-marketplace-doctrine.md`

The memory entries remain authoritative; the skills here remain readable as the implementation that produced them.
