<p align="center">
  <img src="assets/cgg-banner.jpeg" alt="Context Grapple Gun by Prompted LLC & Ubiquity OS" width="100%" />
</p>

# Context Grapple Gun

Context Grapple Gun is a portable governance lifecycle for Claude Code and a developer-facing entry point into Prompted LLC's Ubiquity substrate.

Prompted LLC builds Ubiquity so AI systems can know when to act, when to ask, and how to turn human judgment into safer autonomy over time. CGG applies that thesis locally: it captures durable observations from real work, routes proposed learning through human review, promotes it through scoped gates, and hydrates approved guidance into later sessions without confusing rendered context with constitutional source.

CGG is complete without Ubiquity. When flat-file governance reaches its scale boundary, Ubiquity extends the same primitives into semantic recall, graph topology, conformation-aware retrieval, expression gating, and compiled enforcement.

Three primary commands. Auditable files. No hosted service.

## Start

```bash
npx context-grapple-gun install
cgg doctor
```

The installer ships and copies the versioned runtime from npm. It no longer clones moving `main`. The default runtime scope is user-level; the project's `.ticzone`, `.ticignore`, `audit-logs/`, `CLAUDE.md`, and `MEMORY.md` remain project-local.

Canonical command names are namespaced:

- `/context-grapple-gun:cadence`
- `/context-grapple-gun:review`
- `/context-grapple-gun:siren`

Claude Code may also permit `/cadence`, `/review`, and `/siren` when no other plugin owns those names.

## Read by intent

| You want to... | Start here |
|---|---|
| Install or migrate v5 | [INSTALL.md](INSTALL.md) |
| Use it now | [START-HERE.md](START-HERE.md) |
| Understand the pipeline | [DEV-README.md](DEV-README.md) |
| Evaluate the architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Decode the vocabulary | [docs/TERMINOLOGY.md](docs/TERMINOLOGY.md) |
| Audit release identity | [docs/RELEASE.md](docs/RELEASE.md) |
| Navigate commit history | [docs/COMMIT-HISTORY-CHEATSHEET.md](docs/COMMIT-HISTORY-CHEATSHEET.md) |
| Track the Academy refresh | [issue #13](https://github.com/prompted365/context-grapple-gun/issues/13) |

Homeskillet Academy predates the v5 runtime and distribution contract. It remains in the repository as source/history, but is intentionally excluded from the public plugin surface until issue #13 is complete. The legacy `/init-governance` skill is separately currentness-held under issue #14 while its pre-v5 direct-copy contract is reconciled or retired.

## The governance model

CGG separates three states:

1. **Born truth** — a durable observation captured near the work.
2. **Proposed learning** — a CogPR under evaluation and human review.
3. **In-force truth** — guidance explicitly promoted to a named scope.

A lower or later surface may expose an upstream defect. It may not silently rewrite the higher authority.

## Command ownership

| Command | Authority | What it does |
|---|---|---|
| `/context-grapple-gun:cadence` | Epoch boundary | Emits the canonical tic, seals the handoff, and leaves a resumable state. It does not independently promote lessons or mutate doctrine. |
| `/context-grapple-gun:review` | Human constitutional gate | Approves, rejects, modifies, merges, defers, or supersedes proposed learning and warrants. |
| `/context-grapple-gun:siren` | Signal operations | Surfaces recurring friction, signal state, warrants, and escalation pressure. |

## Why this compounds

The expensive part of persistent agent work is not only rediscovering facts. It is repeatedly reconstructing why a decision was made, which evidence supported it, what remained uncertain, and how far the resulting rule was allowed to travel.

CGG preserves those distinctions through:

- scoped governance zones;
- append-only tics, signals, queue rows, reviews, and receipts;
- a Site → Domain → Estate → Federation → Global abstraction ladder;
- source/install/loaded-runtime separation;
- human-gated promotion;
- bounded handoffs with rationale and resume paths.

## v5 distribution invariant

```text
canonical repository or npm payload
        ↓ versioned copy + mode-specific manifest
managed runtime target
        ↓ strict validation + plugin installation
loaded Claude Code inventory
```

These are distinct authorities. Install success is not inferred from a copied directory or a successful command exit.

CGG v5 therefore:

- makes `.claude-plugin/plugin.json` the single component authority;
- uses a strict, metadata-only marketplace;
- ships the runtime inside the npm package;
- implements materially distinct `full`, `skills`, and `convention` modes;
- verifies the loaded plugin inventory before writing `.cgg-install.json`;
- makes `cgg doctor` check package, plugin, zone, and loaded-runtime truth;
- makes uninstall receipt-bounded and preserves source checkouts and governance history;
- keeps PRESTIGE out of every new zone template.

## Runtime scope is not governance scope

| Surface | User install | Project install |
|---|---|---|
| Managed runtime | `~/.cgg/context-grapple-gun` | `$ZONE_ROOT/.claude/cgg` |
| Plugin enablement | user scope | project scope |
| `.ticzone` / `.ticignore` | `$ZONE_ROOT` | `$ZONE_ROOT` |
| `audit-logs/` | `$ZONE_ROOT` | `$ZONE_ROOT` |
| Project `CLAUDE.md` / `MEMORY.md` | `$ZONE_ROOT` | `$ZONE_ROOT` |

Installing runtime globally does not make project learning global. Broader scope still requires review.

## Public plugin boundary

The repository contains stable, experimental, internal, curriculum, and deprecated surfaces. Repository presence does not grant public admission. The v5 plugin exposes a curated stable set from `.claude-plugin/plugin.json`; the distribution validator rejects accidental admission of deprecated or currentness-held skills.

## What CGG is not

- not a vector database or semantic retrieval engine;
- not a hosted platform;
- not automatic rule promotion;
- not a generic context-window manager;
- not the full Ubiquity substrate.

CGG deliberately stays local and file-based. Full mode requires Claude Code, Python 3, and Bash. The npm installer itself requires Node 18 or newer.

## Core terms

- **CogPR** — behavior pull request: proposed durable learning awaiting review;
- **hydration boundary** — constitutional source remains separate from rendered working context;
- **abstraction ladder** — Site → Domain → Estate → Federation → Global;
- **tic** — ordered epoch event: timestamp plus monotonic project counter;
- **signal / warrant** — recurring condition and its governed escalation;
- **receipt** — evidence of what changed, under which authority, and against which version.

See [docs/TERMINOLOGY.md](docs/TERMINOLOGY.md).

## Evaluate it

1. Run `cgg install --dry-run` and inspect the resolved mutation plan.
2. Install and run `cgg doctor`.
3. Work through one real epoch and close with `/context-grapple-gun:cadence`.
4. Inspect `audit-logs/` and the handoff.
5. Run `/context-grapple-gun:review` when proposals are ready.

Look for whether the source, uncertainty, scope, and human authority survived each handoff—not merely whether the system produced more files.

## Safety

- Durable promotion remains human-gated.
- Existing zone configuration and history are preserved.
- Convention insertion/removal is marker-bounded.
- A managed runtime is removed only when its receipt explicitly authorizes recursive removal.
- Git source checkouts are never removed by `cgg uninstall`.
- Enterprise or seed-managed marketplace authority is reported rather than bypassed.

## License

MIT

## Maintainers

**[Prompted LLC](https://promptedllc.com)** — creators of the Ubiquity governance substrate.

Breyden Taylor, Founder & Architect — [LinkedIn](https://www.linkedin.com/in/breyden-taylor/) | breyden@prompted.community

Contributions welcome.
