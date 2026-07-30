# Changelog

## 5.0.0 — distribution reconciliation

This release rebinds the public package and Claude Code plugin to the current CGG v5 runtime instead of preserving the older 4.0.1 distribution assumptions.

### Changed

- Made `.claude-plugin/plugin.json` the single complete source-plugin component authority.
- Reduced `.claude-plugin/marketplace.json` to marketplace identity and source metadata; removed the competing `strict: false` component map.
- Removed the stale source-plugin semantic version so direct Git installs use commit identity.
- Added an explicit public component-admission contract under `cgg-runtime/config/plugin-components.json`.
- Excluded the outdated Homeskillet Academy from the public plugin pending the governed refresh tracked in issue #17.
- Packaged the exact runtime in npm rather than cloning a moving `main` branch during installation.
- Implemented distinct `full`, `skills`, and `convention` modes.
- Corrected default plugin scope to `user` while preserving `project` and `local` options.
- Added non-destructive governance-zone bootstrap with `PRESTIGE` excluded from new active band lists.
- Added a canonical v5 Session Learning Protocol with source/install/loaded-runtime distinctions and current command ownership.
- Reframed `/init-governance` as project-zone bootstrap and repair rather than a second plugin distribution system.
- Added prepared/verified install receipts and loaded component inventory checks.
- Added safe uninstall while preserving governance history.
- Rebound `cgg sync` to package-target comparison and governed reinstall instead of raw-copying duplicate standalone runtime surfaces into `~/.claude`.
- Reconciled README, Start Here, installation, and terminology surfaces with the runtime and release contract.
- Added CI for Node tests, package payload inspection, and strict validation against the current Claude Code CLI.
- Added a protected, manually dispatched npm publication workflow with version gating, dry-run mode, strict plugin validation, and provenance.

### Held

- npm publication itself is not performed by this change.
- Repository merge remains a separate human decision.
- Homeskillet Academy remains excluded until the v5 curriculum refresh is complete and verified.
