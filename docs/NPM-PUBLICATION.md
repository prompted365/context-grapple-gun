# npm publication authority

The public package is published only by the protected GitHub Actions workflow
at `.github/workflows/npm-release.yml`. The workflow is bound to one exact
source commit and uses npm Trusted Publishing (OIDC); it does not carry a
long-lived npm write token.

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

The workflow refuses a different branch, an open issue #16, an untrusted,
split, missing, or mismatched admission receipt, a non-candidate source, or a
shared-version mismatch. It packs and tests the artifact, publishes through
OIDC, and requires the registry to return all of:

- version `5.0.0`;
- the requested `latest` dist-tag;
- the exact integrity hash of the locally tested tarball;
- a successful registry-origin `cgg --version` execution.

Only after those checks pass does the workflow transition
`release-status.json` to `published` and commit the registry receipt. Once the
base status is `published`, CI forbids any runtime change at the same semantic
version. That closes the drift window: a candidate may be completed before
admission, but an admitted artifact is immutable.

If npm accepted the immutable artifact but `main` advanced before the source
receipt push, a rerun checks that the registry integrity exactly matches a
deterministic repack of the admitted source. It then skips the duplicate
publish, rebases the receipt over non-package changes, and retries the
fast-forward push. Any concurrent change to the packed surface is held for
governed repair rather than being mislabeled as the published artifact.
