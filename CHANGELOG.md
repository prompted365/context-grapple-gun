# Changelog

## 5.0.0 — release candidate

Public registry status is governed by [`release-status.json`](release-status.json). This entry does not itself assert npm publication.

This release rebinds the public package and Claude Code plugin to the current CGG v5 runtime instead of preserving the older 4.0.1 distribution assumptions.

### Changed

- Made `.claude-plugin/plugin.json` the source-plugin skill authority.
- Reduced `.claude-plugin/marketplace.json` to marketplace identity and source metadata; removed the competing `strict: false` component map.
- Bound source plugin, npm package, lockfile, and release-status version to one guarded semantic release identity.
- Added exact source-commit provenance through publication-generated `release-manifest.json` and install receipts.
- Added an explicit public component-admission contract under `cgg-runtime/config/plugin-components.json`.
- Excluded the outdated Homeskillet Academy from the public plugin pending the governed refresh tracked in issue #17.
- Packaged the runtime in npm rather than cloning a moving `main` branch during installation.
- Implemented distinct `full`, `skills`, and `convention` modes.
- Made `skills` a true no-agent, no-hook mode: Skills(6), Agents(0), Hooks(0).
- Defined the full public inventory as Skills(17), Agents(11), Hooks(8).
- Corrected default plugin scope to `user` while preserving `project` and `local` options.
- Added non-destructive governance-zone bootstrap with `PRESTIGE` excluded from new active band lists.
- Added a canonical v5 Session Learning Protocol with source/install/loaded-runtime distinctions and current command ownership.
- Reframed `/init-governance` as project-zone bootstrap and repair rather than a second plugin distribution system.
- Added prepared/verified install receipts with exact expected IDs and expected/loaded inventory counts.
- Added safe uninstall while preserving governance history.
- Rebound `cgg sync` to package-target comparison and governed reinstall instead of raw-copying duplicate standalone runtime surfaces into `~/.claude`.
- Classified raw GitHub marketplace installation as a source-evaluation path, not an inventory-equivalent substitute for the npm-managed full install.
- Reconciled README, Start Here, installation, terminology, and public release-standing surfaces with the runtime contract.
- Added CI for Node 18 and Node 24, package payload inspection, current-Claude strict validation, and a public-runtime version-advance gate.
- Added a clean lifecycle gate that executes the packed `.tgz` across user, project, and local scopes, full-to-skills contraction, convention mode, doctor, update, and uninstall.
- Added a protected manual npm publication workflow with exact version and commit gating, provenance, registry verification, and published-status recording.

### Claude Code 2.1.220 compatibility

- Removed explicit manifest `hooks` because the standard root `hooks/hooks.json` is auto-loaded and a duplicate declaration prevents plugin load.
- Removed inert manifest `agents`; the npm installer materializes the exact admitted agent set at plugin-root `agents/` in full mode only.
- Updated plugin-list parsing to recognize qualified `id` records and surface load errors instead of masking them as “not installed.”
- Fixed fresh-zone doctor behavior when no conformation files exist yet.

### Held

- npm publication remains unasserted until `release-status.json` says `published` and names the verified registry version and source commit.
- Homeskillet Academy remains excluded until the v5 curriculum refresh is complete and verified.
- Third-party repository crawlers may continue to index deprecated source paths; public plugin admission is governed by `plugin-components.json`, not crawler inference.
