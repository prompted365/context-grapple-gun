# Installing Context Grapple Gun v5

CGG has two supported distribution paths:

1. **npm package install** — deterministic, mode-selectable, receipt-bearing.
2. **direct GitHub marketplace install** — source plugin at a Git commit.

They converge on the same plugin component contract but carry different version authority.

## Prerequisites

For `full` and `skills` modes:

- Node.js 18 or newer
- Claude Code CLI with plugin support
- Python 3 for CGG runtime hooks and scripts

Convention-only mode requires only Node.js because it appends the governed protocol and does not register a plugin.

## npm install

```bash
npx context-grapple-gun@5 install
```

The npm package is the runtime source. The installer does not clone `main`.

### Default contract

```text
mode:        full
scope:       user
target:      vendor/context-grapple-gun
zone root:   nearest .ticzone, otherwise git root, otherwise cwd
```

The installer:

1. validates arguments and package completeness;
2. refuses to overwrite a non-managed target;
3. copies the exact npm payload to the durable target;
4. generates a mode-specific plugin manifest stamped with the npm version;
5. writes a `prepared` install receipt;
6. non-destructively bootstraps the project zone;
7. strictly validates the plugin;
8. adds or updates the `cgg` marketplace only when its source agrees;
9. installs or updates the plugin at the requested scope;
10. inspects Claude's installed record and component inventory;
11. writes a `verified` install receipt.

If any late step fails, the receipt remains `prepared`. The installer does not convert partial work into a success claim.

### Install modes

```bash
npx context-grapple-gun@5 install --mode full
npx context-grapple-gun@5 install --mode skills
npx context-grapple-gun@5 install --mode convention
```

| Mode | Skills | Agents | Hooks | Zone bootstrap |
|---|---:|---:|---:|---:|
| `full` | Core, compatibility, and admitted operational skills | Yes | Full lifecycle | Yes |
| `skills` | Core and compatibility skills | No | No | Yes |
| `convention` | No plugin skills | No | No | No; appends protocol only |

The admitted component list is `cgg-runtime/config/plugin-components.json`.

The legacy Homeskillet Academy is excluded pending the current-runtime refresh tracked in [issue #17](https://github.com/prompted365/context-grapple-gun/issues/17).

### Claude plugin scopes

```bash
npx context-grapple-gun@5 install --scope user
npx context-grapple-gun@5 install --scope project
npx context-grapple-gun@5 install --scope local
```

- `user` is the default.
- `project` is shared through project settings.
- `local` is repository-local and operator-private.

Plugin scope does not relocate the project governance zone. `.ticzone`, `.ticignore`, `audit-logs/`, `CLAUDE.md`, and `MEMORY.md` remain at the resolved zone root.

### Target control

```bash
npx context-grapple-gun@5 install --target ./vendor/context-grapple-gun
npx context-grapple-gun@5 install --target ~/.cgg/context-grapple-gun
```

The target is the durable plugin source. It contains the package-pinned runtime and `cgg-install-receipt.json`.

The installer replaces only a target with a valid npm-management receipt. It refuses:

- arbitrary non-empty directories;
- unreadable receipts;
- targets that contain the currently running package source;
- an existing `cgg` marketplace bound to another source.

Marketplace rebinding is deliberately not automatic because removing a marketplace may uninstall plugins or affect data in another scope.

### Dry run

```bash
npx context-grapple-gun@5 install --dry-run
```

Dry-run mode resolves the target and zone, checks constitutional conflicts, and reports intended work without writing or requiring Claude Code.

## Project zone bootstrap

For full and skills modes, installation creates missing surfaces only:

```text
.ticzone
.ticignore
audit-logs/tics/
audit-logs/signals/
audit-logs/cprs/
audit-logs/conformations/
audit-logs/economy/
audit-logs/provenance/
audit-logs/reviews/
```

A newly created `.ticzone` activates:

```json
["PRIMITIVE", "COGNITIVE", "SOCIAL"]
```

`PRESTIGE` is governance-blocked and is never activated by bootstrap.

Existing constitutional files are not rewritten. Installation stops for human repair when:

- an existing `.ticzone` activates `PRESTIGE`;
- an unversioned legacy Session Learning Protocol would conflict with the v5 protocol;
- an existing target is not npm-managed.

The canonical protocol source is `cgg-runtime/config/session-learning-protocol.md`.

## Direct GitHub installation

Direct source installation uses `.claude-plugin/plugin.json` as the complete component authority and the Git commit as version authority.

```bash
claude plugin marketplace add prompted365/context-grapple-gun
claude plugin install context-grapple-gun@cgg --scope user
```

Then bootstrap the project zone from a Claude Code session:

```text
/context-grapple-gun:init-governance
```

The source marketplace does not declare a second component map and does not pin a stale semantic version. A checkout or marketplace update to a new Git commit is a new source version.

Validate source before installing or after modifying plugin surfaces:

```bash
claude plugin validate . --strict
```

## Doctor

```bash
npx context-grapple-gun@5 doctor
```

Doctor verifies:

- install receipt ownership and `verified` state;
- receipt, target package, and generated manifest version agreement;
- strict plugin validation;
- installed and enabled plugin record;
- non-empty admitted skills and, in full mode, agents and hooks;
- required zone surfaces;
- valid `.ticzone` bands with `PRESTIGE` excluded;
- current Session Learning Protocol marker;
- topology diagnostic execution from the project zone.

The read-only topology view remains available separately:

```bash
npx context-grapple-gun@5 doctor --topology-only
```

Topology-only success does not imply package or plugin installation success.

## Package reconciliation

The public v5 plugin loads from the durable package target; it no longer raw-copies a second runtime into `~/.claude`. The compatibility `sync` command now compares the running npm package with that durable target and routes repair back through the governed installer:

```bash
npx context-grapple-gun@5 sync check   # version and byte-parity check
npx context-grapple-gun@5 sync diff    # list missing, extra, or drifted owned files
npx context-grapple-gun@5 sync sync    # verified reinstall using the prior mode/scope receipt
```

Internal and legacy standalone-copy tooling remains in source history for existing federation deployments, but the npm CLI does not silently create duplicate standalone skills, agents, or hooks. Loaded runtime remains behavioral truth until reconciliation and verification complete.

## Uninstall

```bash
npx context-grapple-gun@5 uninstall
```

Default uninstall:

- unregisters `context-grapple-gun@cgg` at the receipt's scope;
- removes only files named in the npm install receipt;
- preserves `.ticzone`, `.ticignore`, `audit-logs/`, `CLAUDE.md`, and `MEMORY.md`;
- retains the marketplace because another scope may depend on it.

Options:

```bash
# Keep the durable package target
npx context-grapple-gun@5 uninstall --keep-files

# Preserve Claude plugin data while unregistering
npx context-grapple-gun@5 uninstall --keep-data

# Explicitly remove marketplace cgg as well
npx context-grapple-gun@5 uninstall --remove-marketplace
```

Marketplace removal is explicit because Claude may uninstall marketplace plugins and remove related state.

## Update

Use the intended package version explicitly:

```bash
npx context-grapple-gun@5 install
```

The installer reads the previous receipt. A package version, mode, or scope change causes a controlled reinstall with plugin data preserved where supported. An unchanged package/mode/scope uses the plugin update path and then re-verifies the inventory.

For direct GitHub installs:

```bash
claude plugin marketplace update cgg
claude plugin update context-grapple-gun@cgg --scope user
```

## Release verification

The distribution contract workflow runs on changes to plugin manifests, runtime components, CLI code, package metadata, tests, and public installation docs.

It checks:

- Node tests;
- JavaScript syntax;
- npm payload receipt with `npm pack --dry-run`;
- installation of the current Claude Code CLI;
- strict plugin validation against that current CLI.

The source manifest and package-mode manifests are also tested against `cgg-runtime/config/plugin-components.json`.

## First run

After verified installation:

1. work normally;
2. end a real epoch with `/context-grapple-gun:cadence`;
3. start a fresh session and inspect the restored handoff;
4. run `/context-grapple-gun:review` when the docket is ready;
5. use `/context-grapple-gun:siren` for recurring-friction inspection.

Do not use the old Academy as current install authority until issue #17 closes.

## Maintainer release lane

The repository includes a manually dispatched `Publish npm package` workflow. Publication is never coupled to a merge automatically.

1. Merge an admitted distribution change.
2. Dispatch the workflow with the exact `package.json` version and `dry_run: true`.
3. Review Node tests, npm payload receipt, current Claude Code version, and strict plugin validation.
4. Ensure the protected `npm-publish` environment and `NPM_TOKEN` secret are configured.
5. Dispatch again with `dry_run: false` and the intended npm distribution tag.
6. Verify the published package through a clean `npx context-grapple-gun@<version> install --dry-run` and a clean-machine installation before declaring release complete.

The workflow requests GitHub OIDC permission and publishes with npm provenance. A successful GitHub job is publication evidence; it is not proof that a downstream installation loaded correctly, so the clean-install receipt remains required.
