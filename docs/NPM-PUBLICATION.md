# npm publication authority

The public package is published only by the protected GitHub Actions workflow
at `.github/workflows/npm-release.yml`. The workflow is bound to one exact
source commit and uses npm Trusted Publishing (OIDC); it does not carry a
long-lived npm write token. The workflow pins npm CLI `11.5.1`, the first
admitted OIDC-capable toolchain version for this release lane.
GitHub Actions Trusted Publishing generates npm provenance automatically; the
workflow verifies the resulting registry attestation instead of relying on a
local `--provenance` assertion.

The requested dist-tag is mutable registry state, not immutable package
identity. It is deliberately absent from the candidate `release-manifest.json`
that enters the tarball. The workflow records `registry_dist_tag` in the source
receipt only after the registry proves that the requested tag identifies the
exact packed bytes.

## npm Trusted Publisher settings

On the `context-grapple-gun` package settings page, enter these exact values:

| npm field | Exact value |
|---|---|
| Publisher | GitHub Actions |
| Organization or user | `prompted365` |
| Repository | `context-grapple-gun` |
| Workflow filename | `npm-release.yml` |
| Environment name | `npm-publish` |
| Allowed action | **Allow `npm publish`** |
| Disallowed action | Leave **Allow `npm stage publish`** unchecked |

The filename is entered without `.github/workflows/`. Every value is
case-sensitive. The repository field in `package.json` must continue to match
`https://github.com/prompted365/context-grapple-gun`.

After one OIDC publication succeeds, set package token access to disallow
traditional token-based publishing and revoke any obsolete npm automation
token. Trusted Publishing remains usable because it authenticates with a
short-lived workflow identity, not a registry token.

## Admission and dispatch

Publication remains held until GitHub issue #16 is closed with one trusted
owner, member, or collaborator comment containing all three exact receipt
lines as one contiguous tuple:

```text
publication-admission-commit: <full main commit sha>
publication-admission-version: 5.0.0
publication-admission-dist-tag: latest
```

Dispatch `Publish npm package` from `main` with:

```text
expected_version = 5.0.0
expected_commit  = <the same admitted full sha>
dist_tag         = latest
dry_run          = false
```

For `5.0.0`, publication is admitted directly to `latest`; this workflow does
not stage the release under `next` and later promote it. npm Trusted Publishing
OIDC authorizes `npm publish` but not `npm dist-tag` mutations. If the immutable
version already exists while the admitted tag points elsewhere, the workflow
fails with an explicit hold. An interactive npm authority must repair and
verify that registry mapping before receipt recovery can continue.

The workflow refuses a different branch, an open issue #16, an untrusted,
split, missing, or mismatched admission receipt, a non-candidate source, or a
shared-version mismatch. Before publishing, only an explicit registry `E404`
is treated as an absent version; network, authentication, and other registry
query failures stop the workflow. It packs and tests the artifact, publishes
through OIDC, and requires the registry to return all of:

- version `5.0.0`;
- the requested `latest` dist-tag;
- the exact integrity hash of the locally tested tarball;
- a registry-linked SLSA v1 provenance attestation for that exact version;
- successful cryptographic verification by `npm audit signatures` after a
  clean registry install;
- a successful registry-origin `cgg --version` execution.

Immediately before the irreversible `npm publish`, the workflow refetches
`main` and compares every top-level path represented by the actual pack receipt
against the admitted commit. Any packed-surface advance stops publication;
unrelated non-package advances remain eligible for receipt reconciliation.

Only after those checks pass does the workflow transition
`release-status.json` to `published`, bind the registry integrity and
attestation metadata into `release-manifest.json`, validate the two receipt
surfaces against each other, and commit them together. Once the base status is
`published`, CI forbids any runtime change at the same semantic version. That
closes the drift window: a candidate may be completed before admission, but an
admitted artifact is immutable.

If npm accepted the immutable artifact but `main` advanced before the source
receipt push, a rerun checks that the registry integrity exactly matches a
deterministic repack of the admitted source and that the admitted tag still
points to that exact version. It then skips the duplicate publish, rebases the
receipt over non-package changes, and retries the fast-forward push. Any
concurrent change to the packed surface or registry tag is held for governed
repair rather than being mislabeled as the published artifact.
