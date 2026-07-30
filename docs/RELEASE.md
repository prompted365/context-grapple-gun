# CGG Release Authority

A CGG release is admitted only when one identity binds source, package, plugin metadata, installed bytes, and validation receipts.

## Version lock

Before release, the same semantic version must appear in:

- `package.json`;
- `package-lock.json`;
- `.claude-plugin/plugin.json`;
- `.claude-plugin/marketplace.json`.

Run:

```bash
npm run test:distribution
npm pack --dry-run
claude plugin validate . --strict
```

## Release sequence

1. Merge the release PR with green distribution and runtime checks.
2. Confirm `main` is the intended source SHA.
3. Create a GitHub release tagged `v<version>` from that SHA.
4. Let `.github/workflows/release-npm.yml` validate and publish with npm provenance.
5. Install the published version in a clean temporary HOME and project.
6. Run full, skills, and convention smoke tests.
7. Record package version, tarball integrity, release SHA, install receipt hashes, and loaded plugin inventory.

## Npm publishing prerequisite

The repository's npm workflow expects the `context-grapple-gun` npm package to trust this GitHub repository as an npm trusted publisher. The workflow uses GitHub OIDC and `npm publish --provenance`; it does not require a long-lived npm token when trusted publishing is configured.

If trusted publishing is not configured, the workflow must remain held. Do not substitute an unreceipted local publish and then describe the release as CI-produced.

## Clean-room smoke matrix

| Mode | Scope | Required result |
|---|---|---|
| full | user | core skills, curated agents, complete hooks, zone surfaces, loaded inventory |
| full | project | same component set at project scope |
| skills | user | core skills only; no hooks or agents |
| skills | project | core skills only at project scope |
| convention | n/a | one marker-bounded protocol block; no runtime target |

For each runtime mode, test install, doctor, reinstall/idempotency, and uninstall. Governance history must survive uninstall.

## Publication boundary

Merging code is not publishing npm. Creating a GitHub release is not proof npm published. An npm version appearing in the registry is not proof the plugin loaded. Each transition needs its own receipt.
