<p align="center">
  <img src="assets/cgg-banner.jpeg" alt="Context Grapple Gun by Prompted LLC & Ubiquity OS" width="100%" />
</p>

# Context Grapple Gun

Context Grapple Gun is a portable governance lifecycle for Claude Code and a developer-facing entry point into Prompted LLC's Ubiquity substrate.

CGG turns session-local human-agent learning into scoped, reviewable, receipted operating structure. It preserves the distinction between canonical source, installed plugin, loaded runtime, human judgment, and future hydration instead of calling all of them “memory.”

Three commands are the public operating surface:

| Command | Governing job |
|---|---|
| `/cadence` | Close the epoch, emit the canonical tic, seal the handoff, and leave a resumable next state. |
| `/review` | Let the named human authority approve, modify, defer, merge, supersede, or reject durable promotion. |
| `/siren` | Inspect the recurring-friction signal manifold without turning visibility into promotion authority. |

## Release status

[`release-status.json`](release-status.json) is the machine-readable public release gate.

- `release-candidate` means the source and CI candidate are available, but registry publication is not yet asserted.
- `published` means the npm registry receipt has been verified for the stated version and source commit.

Use the npm command only when that file says `published` for the requested version:

```bash
npx context-grapple-gun@5 install
```

Until then, do not infer registry availability from `package.json`, a branch name, a tag, or a successful source checkout.

## Public distribution invariant

```text
npm release + exact source receipt
  -> package-pinned marketplace source
  -> mode-specific plugin manifest
  -> installed plugin
  -> exact loaded component inventory
  -> project governance zone
  -> human-gated promotion
  -> future hydration
```

> No success claim until the release, plugin declaration, loaded inventory, and project zone agree.

The npm package contains the runtime it installs. It does not clone a moving branch. The source plugin, npm package, lockfile, and release status share one semantic release version. The publication workflow adds the exact source commit to `release-manifest.json`; install receipts carry both identities rather than collapsing semver and provenance into one field.

## Install modes

| Mode | Skills | Agents | Hooks | Zone bootstrap |
|---|---:|---:|---:|---:|
| `full` | 17 admitted skills | 11 admitted agents | 8 lifecycle events | Yes |
| `skills` | 6 core and compatibility skills | 0 | 0 | Yes |
| `convention` | 0 plugin skills | 0 | 0 | No; appends the governed protocol only |

The public component set is governed by [`cgg-runtime/config/plugin-components.json`](cgg-runtime/config/plugin-components.json). Deprecated surfaces and unrefreshed teaching artifacts do not enter the plugin merely because they exist in the repository.

The installer and `cgg doctor` require exact inventory equality. “At least one component loaded” is not admission.

## npm-managed installation

After `release-status.json` says `published`:

```bash
# Default: full mode, user scope
npx context-grapple-gun@5 install

# True skills-only mode: zero agents, zero hooks
npx context-grapple-gun@5 install --mode skills

# Convention only
npx context-grapple-gun@5 install --mode convention

# Inspect without writing
npx context-grapple-gun@5 install --dry-run
```

See [START-HERE.md](START-HERE.md) for the operating rhythm and [INSTALL.md](INSTALL.md) for scopes, target control, diagnostics, reconciliation, and uninstall.

## Direct Git source path

The raw GitHub marketplace path is a **source-evaluation path**, not an equivalent substitute for the npm-managed full install.

It does not receive the npm install receipt, mode-specific payload contraction, exact agent materialization, or packed-artifact proof. Use it to inspect and validate source. Do not represent it as the production or turnkey installation path unless a separate direct-Git lifecycle receipt proves equivalent inventory.

## Authority boundaries

- `/cadence` owns epoch close and handoff sealing. It is not the memory writer, signal emitter, assessor, extractor, or review authority.
- `/review` owns constitutional judgment. It uses an in-tic human ratification question set; it is not generic Plan Mode approval or interception.
- `/siren` owns signal operations. Signal volume does not grant sovereignty.
- The Claude plugin manager owns plugin registration and loaded component state.
- `/init-governance` owns project-zone bootstrap and repair after installation. It does not copy plugin components or rewrite Claude settings.
- Loaded runtime is behavioral truth. Canonical source remains intent until installation and verification complete.

## Flat-file boundary

CGG is complete as a local, auditable governance lifecycle. It deliberately avoids pretending that flat files are a semantic substrate.

When lexical lookup, file topology, and human review are no longer sufficient, Ubiquity extends the same primitives into semantic recall, graph topology, conformation-aware retrieval, expression gating, and compiled execution-boundary enforcement.

## Source map

| Need | Authority |
|---|---|
| Use CGG | [START-HERE.md](START-HERE.md) |
| Install and remove it | [INSTALL.md](INSTALL.md) |
| Check public release standing | [release-status.json](release-status.json) |
| Audit npm publication authority | [docs/NPM-PUBLICATION.md](docs/NPM-PUBLICATION.md) |
| Inspect admitted components | [cgg-runtime/config/plugin-components.json](cgg-runtime/config/plugin-components.json) |
| Understand the operating pipeline | [DEV-README.md](DEV-README.md) |
| Evaluate the theory and scale boundary | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Inspect runtime topology | [CGG_RUNTIME_TOPOLOGY_AND_LIFECYCLE.md](CGG_RUNTIME_TOPOLOGY_AND_LIFECYCLE.md) |
| Resolve current terms | [docs/TERMINOLOGY.md](docs/TERMINOLOGY.md) |
| See release deltas | [CHANGELOG.md](CHANGELOG.md) |

## Academy standing

The prior Homeskillet Academy is intentionally excluded from the public v5 plugin while it is re-derived against the current runtime. The refresh is tracked in [GitHub issue #17](https://github.com/prompted365/context-grapple-gun/issues/17). Until that gate closes, use the current guides and live runtime contracts rather than the legacy course as installation or architecture authority.

## Safety

- Durable promotion requires the human `/review` gate.
- Existing `.ticzone`, `.ticignore`, `CLAUDE.md`, `MEMORY.md`, and audit history are not overwritten by installation.
- `PRESTIGE` is governance-blocked and never appears in a newly created active band list.
- An existing constitutional conflict is held for human repair rather than silently rewritten.
- Uninstall preserves project governance history by default.
- Marketplace removal is explicit because it can affect more than one plugin scope.

## License

MIT

## Maintainers

**[Prompted LLC](https://promptedllc.com)** — creators of the Ubiquity governance substrate.

Breyden Taylor, Founder & Architect — [LinkedIn](https://www.linkedin.com/in/breyden-taylor/) | breyden@prompted.community
