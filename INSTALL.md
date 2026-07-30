# Installing Context Grapple Gun v5

CGG v5 has one distribution rule: **the version you name must identify the runtime bytes that Claude Code loads.**

The npm package therefore contains the plugin manifest, marketplace, hooks, runtime, skills, agents, scripts, and canonical convention block. `cgg install` copies that versioned payload into a managed target, generates the selected mode manifest, validates it, installs it, verifies the loaded inventory, and only then writes an install receipt.

Git is no longer required for npm installation.

## Fast path

Run from the project that should become the governance zone:

```bash
npx context-grapple-gun install
cgg doctor
```

Default behavior:

- mode: `full`;
- runtime scope: `user`;
- managed target: `~/.cgg/context-grapple-gun`;
- governance zone: nearest `.ticzone`, otherwise git root, otherwise current directory;
- project surfaces: `.ticzone`, `.ticignore`, `audit-logs/`, and the marker-bounded protocol in `CLAUDE.md`.

## Inspect before writing

```bash
cgg install --dry-run
```

Dry-run prints the resolved zone, managed target, mode, scope, surfaces, validation command, and plugin registration without mutation.

## Install modes

### Full

```bash
cgg install --mode full
```

Installs the curated v5 skills, curated agents, and the complete hook lifecycle declared by `hooks/hooks.json`:

- SessionStart;
- SubagentStart;
- PreCompact;
- PostCompact;
- Stop;
- SessionEnd;
- UserPromptSubmit;
- PostToolUse.

### Skills

```bash
cgg install --mode skills
```

Installs the cadence/review/siren command surface and compatibility wrappers. The generated plugin manifest contains no agents and no hooks. The lifecycle is manual.

### Convention

```bash
cgg install --mode convention
```

Adds only the marker-bounded Session Learning Protocol to the project `CLAUDE.md`. It does not install a plugin, runtime, hook, agent, or audit tree.

## Runtime scope

### User scope — default

```bash
cgg install --scope user
```

Managed runtime:

```text
~/.cgg/context-grapple-gun
```

Claude Code plugin enablement is user-scoped. The project zone remains project-local.

### Project scope

```bash
cgg install --scope project
```

Managed runtime:

```text
$ZONE_ROOT/.claude/cgg
```

Claude Code plugin enablement is project-scoped.

### Custom target

```bash
cgg install --target /absolute/or/relative/path
```

CGG refuses to overwrite a populated directory unless it contains a CGG install receipt or is an existing git checkout. A package-copy target is removable only when its receipt explicitly authorizes recursive removal. A git source checkout is classified separately and is never deleted by `cgg uninstall`.

## What the installer mutates

Full and skills modes may create, if absent:

```text
$ZONE_ROOT/.ticzone
$ZONE_ROOT/.ticignore
$ZONE_ROOT/audit-logs/{tics,signals,cprs,conformations,economy,provenance,reviews,governance}
$ZONE_ROOT/CLAUDE.md  # marker-bounded protocol append only
```

The default `.ticzone` admits:

```json
{
  "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"]
}
```

PRESTIGE is governance-blocked and is not activated by bootstrap.

Existing zone configuration, history, `MEMORY.md`, and user-authored `CLAUDE.md` content are never replaced.

## Plugin authority

The component map lives in one place:

```text
.claude-plugin/plugin.json
```

The marketplace is `strict: true` and carries only source, identity, version, and distribution metadata. It does not duplicate or override skills, agents, or hooks.

During install CGG:

1. writes the mode-specific plugin manifest into the managed target;
2. runs `claude plugin validate <target> --strict`;
3. refreshes the dedicated `cgg` marketplace registration;
4. installs `context-grapple-gun@cgg` at the selected scope;
5. verifies `claude plugin list --json` and `claude plugin details`;
6. writes `.cgg-install.json` with manifest hashes and target-removal authority.

A seed/enterprise-managed `cgg` marketplace cannot be replaced. CGG stops and reports that authority boundary instead of bypassing it.

## Diagnostics

```bash
cgg doctor
cgg doctor --json
```

Doctor validates package/plugin/marketplace version identity, manifest authority, component paths, loaded plugin state, zone surfaces, and topology.

Runtime drift commands remain available:

```bash
cgg sync check
cgg sync diff
cgg sync sync
```

## Uninstall

```bash
cgg uninstall --dry-run
cgg uninstall
```

Default uninstall:

- removes `context-grapple-gun@cgg` registration;
- removes the dedicated `cgg` marketplace;
- removes only a receipt-owned `package_copy` target with `removal_authorized: true`;
- preserves git source checkouts, governance history, and project source.

Options:

```bash
cgg uninstall --keep-runtime
cgg uninstall --remove-convention
cgg uninstall --scope project
```

`--remove-convention` removes only the content between CGG's start/end markers. It does not delete other `CLAUDE.md` content.

## Install from a GitHub checkout

For development, clone the repository and run the local CLI:

```bash
git clone https://github.com/prompted365/context-grapple-gun.git
cd context-grapple-gun
npm test
node bin/cgg.mjs install --project-dir /path/to/project
```

The repository manifest is the full-mode canonical source. A skills-only install is generated into a separate managed target so the source checkout is not rewritten. Source-checkout receipts explicitly deny recursive removal.

## Npm and release authority

The following versions must agree before packing or publishing:

- `package.json`;
- `package-lock.json`;
- `.claude-plugin/plugin.json`;
- `.claude-plugin/marketplace.json`.

`npm pack` runs the distribution validator through `prepack`. GitHub CI also validates paths, hook lifecycle coverage, documentation links, held-surface exclusion, mode boundaries, and Claude Code's current strict plugin validator.

See [docs/RELEASE.md](docs/RELEASE.md).

## Held legacy surfaces

Homeskillet Academy is not part of the v5 admitted plugin surface. Its refresh is tracked in [issue #13](https://github.com/prompted365/context-grapple-gun/issues/13).

The legacy `/init-governance` skill is also excluded while [issue #14](https://github.com/prompted365/context-grapple-gun/issues/14) reconciles or retires its pre-v5 direct-copy/settings-patch contract. `cgg install`, `cgg doctor`, and `cgg sync` are the v5 bootstrap and maintenance authorities.
