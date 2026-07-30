# Installing Context Grapple Gun v5

CGG has one admitted installation path and one bounded source-evaluation path:

1. **npm-managed install** — deterministic, mode-selectable, exact-inventory-checked, and receipt-bearing.
2. **direct GitHub marketplace source** — useful for source inspection and schema evaluation; not equivalent to the npm-managed full install.

The distinction is deliberate. A Git checkout proves source availability. An npm-managed install proves a package, selected mode, loaded inventory, governance zone, and receipt agree.

## 1. Check the public release gate

Read [`release-status.json`](release-status.json).

```json
{
  "version": "5.0.0",
  "status": "release-candidate"
}
```

- `release-candidate` — source and CI candidate exist; registry publication is not asserted.
- `published` — the npm registry returned the stated version and the publication workflow recorded its exact source commit.

Do not infer npm availability from `package.json`, a branch, a tag, or a passing source build. Use the install command only when the status file says `published` for the requested version.

## 2. Prerequisites

For `full` and `skills` modes:

- Node.js 18 or newer
- Claude Code CLI with plugin support
- Python 3 for CGG runtime hooks and scripts

Convention-only mode requires only Node.js because it appends the governed protocol and does not register a plugin.

## 3. npm-managed installation

After the release gate says `published`:

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
inventory:   Skills(17) Agents(11) Hooks(8)
```

The installer:

1. validates arguments and package completeness;
2. refuses to overwrite a non-managed target;
3. copies the exact npm payload to the durable target;
4. contracts that payload to the selected mode;
5. materializes only the admitted full-mode agents into plugin-root `agents/`;
6. copies plugin-root `hooks/` only in full mode;
7. generates a mode-specific plugin manifest stamped with the npm version;
8. writes a `prepared` install receipt containing release version and source commit when available;
9. non-destructively bootstraps the project zone;
10. strictly validates the plugin;
11. adds or updates the `cgg` marketplace only when its source agrees;
12. installs or updates the plugin at the requested scope;
13. verifies the installed record has no load errors;
14. requires exact loaded component counts for the selected mode;
15. writes a `verified` receipt containing expected IDs and expected/loaded counts.

If any late step fails, the receipt remains `prepared`. Partial work does not become a success claim.

## 4. Install modes

```bash
npx context-grapple-gun@5 install --mode full
npx context-grapple-gun@5 install --mode skills
npx context-grapple-gun@5 install --mode convention
```

| Mode | Skills | Agents | Hooks | Zone bootstrap |
|---|---:|---:|---:|---:|
| `full` | 17 | 11 | 8 lifecycle events | Yes |
| `skills` | 6 | 0 | 0 | Yes |
| `convention` | 0 plugin skills | 0 | 0 | No; appends protocol only |

`skills` is a true no-agent, no-hook mode. A transition from `full` to `skills` removes the previously managed plugin-root `agents/` and `hooks/` surfaces before reinstalling and re-verifying the narrower inventory.

The admitted IDs are governed by [`cgg-runtime/config/plugin-components.json`](cgg-runtime/config/plugin-components.json).

The legacy Homeskillet Academy is excluded pending the current-runtime refresh tracked in [issue #17](https://github.com/prompted365/context-grapple-gun/issues/17).

## 5. Claude plugin scopes

```bash
npx context-grapple-gun@5 install --scope user
npx context-grapple-gun@5 install --scope project
npx context-grapple-gun@5 install --scope local
```

- `user` is the default.
- `project` is shared through project settings.
- `local` is repository-local and operator-private.

Plugin scope does not relocate the project governance zone. `.ticzone`, `.ticignore`, `audit-logs/`, `CLAUDE.md`, and `MEMORY.md` remain at the resolved zone root.

CI executes the packed npm artifact across all three scopes.

## 6. Target control

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

Marketplace rebinding is deliberately not automatic because removal can uninstall plugins or affect data in another scope.

## 7. Dry run

```bash
npx context-grapple-gun@5 install --dry-run
```

Dry-run mode resolves the target and zone, checks constitutional conflicts, and reports the selected mode's payload without writing or requiring Claude Code.

For `skills`, the plan explicitly states zero agents and zero hooks.

## 8. Project-zone bootstrap

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
- an unversioned legacy Session Learning Protocol conflicts with the v5 protocol;
- an existing target is not npm-managed.

The canonical protocol source is [`cgg-runtime/config/session-learning-protocol.md`](cgg-runtime/config/session-learning-protocol.md).

## 9. Exact identity and provenance

CGG keeps two identities distinct:

```text
release_version
= semantic compatibility and public distribution identity

source_commit
= exact source provenance and reconstruction identity
```

The publication workflow writes `release-manifest.json` into the packed artifact. The installer carries both fields into its receipt. A missing source commit is represented as `null`; it is never invented from a branch name or current working tree.

## 10. Direct GitHub source evaluation

The raw GitHub marketplace path is a **source-evaluation path**. It is **not equivalent to the npm-managed full install**.

```bash
claude plugin marketplace add prompted365/context-grapple-gun
claude plugin install context-grapple-gun@cgg --scope user
```

This path can be used to inspect source and exercise Claude's source-plugin parser. It does not receive:

- the npm publication receipt;
- mode-specific payload contraction;
- the npm install receipt;
- exact admitted-agent materialization;
- packed-artifact execution proof;
- the same doctor contract as an npm-managed target.

Do not represent raw Git installation as the public production, turnkey, or inventory-equivalent path. The exact source commit remains useful provenance, but provenance alone does not establish runtime conformance.

## 11. Doctor

```bash
npx context-grapple-gun@5 doctor
```

Doctor verifies:

- install receipt ownership, schema, and `verified` state;
- release version, package version, and generated manifest agreement;
- strict plugin validation;
- installed and enabled plugin record with no load errors;
- exact manifest skill count;
- exact materialized agent count;
- presence or absence of plugin-root hooks according to mode;
- exact loaded inventory:
  - `full`: Skills(17), Agents(11), Hooks(8)
  - `skills`: Skills(6), Agents(0), Hooks(0)
- receipt expected IDs and expected/loaded counts against the live inventory;
- required zone surfaces;
- valid `.ticzone` bands with `PRESTIGE` excluded;
- current Session Learning Protocol marker;
- topology diagnostic execution from the project zone.

The read-only topology view remains available separately:

```bash
npx context-grapple-gun@5 doctor --topology-only
```

Topology-only success does not imply package or plugin installation success.

## 12. Package reconciliation

The public v5 plugin loads from the durable package target; it does not raw-copy a second runtime into `~/.claude`.

```bash
npx context-grapple-gun@5 sync check
npx context-grapple-gun@5 sync diff
npx context-grapple-gun@5 sync sync
```

- `check` compares the running npm package with the durable target.
- `diff` lists missing, extra, or drifted owned files.
- `sync` routes repair through the governed installer using the prior mode and scope receipt.

Loaded runtime remains behavioral truth until reconciliation and verification complete.

## 13. Uninstall

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

## 14. Update

Use the intended published package version explicitly:

```bash
npx context-grapple-gun@5 install
```

The installer reads the previous receipt. A package version, mode, or scope change causes a controlled reinstall. An unchanged package/mode/scope uses the plugin update path and re-verifies exact inventory.

## 15. Release verification

The distribution contract workflow checks:

- shared package, lockfile, plugin, and release-status version;
- version advance when public runtime surfaces change;
- Node 18 and Node 24 tests;
- JavaScript syntax;
- npm payload inspection;
- current Claude Code strict plugin validation.

The clean installer workflow:

1. runs `npm pack --json`;
2. installs the resulting `.tgz` into an isolated prefix;
3. invokes the packaged `cgg` binary;
4. exercises full mode at user, project, and local scopes;
5. exercises same-version update;
6. contracts full to true skills-only mode and proves 6/0/0;
7. exercises convention mode;
8. runs doctor after each applicable transition;
9. uninstalls managed runtime while proving governance history survived.

The manual publication workflow requires an exact version and exact source commit, publishes with provenance, verifies the registry response, and then records the published status.
