# Installing CGG in a Real Project — Historical Guide Held

> **DO NOT USE THIS ACADEMY GUIDE TO INSTALL CURRENT CGG.**
>
> The manual-copy procedure previously published here predates the v5 package, the current Claude Code plugin loading rules, exact mode inventories, receipt-bearing installation, and the machine-readable release gate. Following the old steps can create a partial or competing runtime while appearing successful.

## Current authority

Use these sources instead:

1. [release-status.json](../../../release-status.json) — determines whether the stated npm version is actually published;
2. [INSTALL.md](../../../INSTALL.md) — current npm-managed installation, modes, scopes, doctor, sync, and uninstall;
3. [START-HERE.md](../../../START-HERE.md) — current operating rhythm and command ownership;
4. [plugin-components.json](../../../cgg-runtime/config/plugin-components.json) — exact public component admission.

The current mode contract is:

| Mode | Skills | Agents | Hooks |
|---|---:|---:|---:|
| `full` | 17 | 11 | 8 |
| `skills` | 6 | 0 | 0 |
| `convention` | 0 | 0 | 0 |

The npm-managed installer is the admitted installation lane. The raw GitHub marketplace path is source evaluation only and must not be represented as inventory-equivalent to the full npm-managed install.

## Release gate

Run an npm installation command only when `release-status.json` says `published` for the version you intend to install. A `package.json` version, Git branch, tag, source checkout, or successful static manifest validation is not a registry receipt.

## Why the old guide was withdrawn

The historical guide instructed operators to copy selected skills, hooks, and agents manually. That model is no longer sufficient because it did not prove:

- one package-pinned runtime source;
- exact loaded skill, agent, and hook inventory;
- mode-specific payload contraction;
- source version and source-commit provenance as distinct receipt fields;
- non-destructive project-zone bootstrap;
- installed-versus-loaded runtime agreement;
- safe update and uninstall behavior.

The old content remains available through Git history for curriculum re-derivation. It is not current operating instruction.

## Academy status

The Academy refresh is tracked in [issue #17](https://github.com/prompted365/context-grapple-gun/issues/17). This guide should be rewritten only as part of that governed refresh and only after the curriculum exercises pass against a clean current installation.
