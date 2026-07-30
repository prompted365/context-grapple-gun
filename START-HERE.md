<p align="center">
  <img src="assets/cgg-banner.jpeg" alt="Context Grapple Gun by Prompted LLC & Ubiquity OS" width="100%" />
</p>

# Start Here

CGG keeps Claude Code from paying the same reconstruction cost every session. It captures bounded lessons from real work, routes durable changes through human review, seals resumable handoffs, and keeps recurring friction visible without silently turning observations into law.

## The daily interface

| Command | Use it when | What it actually owns |
|---|---|---|
| `/cadence` | A real work epoch is complete or context is degrading | Canonical tic, epoch close, handoff seal, and resumable next state |
| `/review` | The proposal docket is ready | Human constitutional judgment over durable promotion |
| `/siren` | You need recurring-friction visibility | Signal inspection, triage, warrants, and signal operations |

Everything else is machinery behind those seams. The commands are intentionally narrow:

- `/cadence` does not become the memory writer, signal emitter, CogPR extractor, assessor, or review gate.
- `/review` does not outsource authority to an agent or generic plan approval.
- `/siren` does not turn visibility or volume into promotion authority.

## Install

```bash
npx context-grapple-gun@5 install
```

The installer now uses the package you invoked as the runtime source. It creates a durable plugin source under `vendor/context-grapple-gun`, generates the selected mode manifest, bootstraps the project governance zone, validates the plugin strictly, installs it at user scope by default, inspects the loaded component inventory, and writes a receipt.

A successful install means those checks passed. It is no longer a success message printed after cloning a moving branch.

Useful variants:

```bash
# Core skills only; no hooks or agents
npx context-grapple-gun@5 install --mode skills

# Project-local plugin registration
npx context-grapple-gun@5 install --scope project

# Repository-local registration
npx context-grapple-gun@5 install --scope local

# Append the governed learning convention only
npx context-grapple-gun@5 install --mode convention

# Inspect the plan without writing
npx context-grapple-gun@5 install --dry-run
```

Verify later:

```bash
npx context-grapple-gun@5 doctor
```

See [INSTALL.md](INSTALL.md) for direct GitHub installation, target control, reconciliation, and safe uninstall.

## A normal session

1. **Start.** SessionStart reads the zone, continuity surfaces, and current governance state. It may surface an active handoff or a review-ready condition. It does not silently approve anything.
2. **Work.** Durable discoveries may be captured as CogPR candidates on born-truth surfaces. Recurring friction may enter the signal manifold.
3. **Close.** Run `/cadence`. It closes the epoch, emits the canonical tic, seals the handoff, and leaves a clear resume path.
4. **Resume.** The next session hydrates from authoritative files and the sealed handoff. The loaded runtime remains behavioral truth for that session.
5. **Review.** When the docket is ready, run `/review`. You decide what promotes, what remains local, what needs evidence, and what is rejected.
6. **Inspect pressure.** Run `/siren` when repeated friction, signal thresholds, or warrants need attention.

## Where lessons live

CGG separates states that are often collapsed into “memory”:

| State | Meaning |
|---|---|
| Born truth | A bounded observation or lesson exists on its originating surface. |
| Proposal | A CogPR asks whether the lesson should travel. |
| In-force truth | A human-reviewed rule has been promoted into an authoritative governance surface. |
| Installed plugin | Claude Code has registered a declared component package. |
| Loaded runtime | The actual skills, agents, and hooks shaping current behavior. |
| Hydrated context | A working projection derived from authoritative sources for the present session. |

Hydrated context is useful. It is not constitutional source merely because it is visible.

## Scope ladder

| Scope | Typical authority surface | Meaning |
|---|---|---|
| Site | Project-root `CLAUDE.md` | Applies across the current codebase |
| Domain | Subsystem governance surface | Applies to one bounded subsystem |
| Estate | Cross-project authority | Applies across projects under one operator |
| Federation | Cross-estate authority | Applies across participating estates |
| Global | `~/.claude/CLAUDE.md` | Applies across the operator's work |

A lesson climbs only through a named review gate. Directory depth, repetition, or agent confidence does not grant scope.

## Install scope is not governance scope

Claude plugin scope determines where Claude registers the plugin:

- `user` — available across projects for the user; default
- `project` — shared through project settings
- `local` — repository-local and private to the operator

The governance zone remains project-local either way:

- `.ticzone`
- `.ticignore`
- `audit-logs/`
- project `CLAUDE.md` and `MEMORY.md`

## Two lesson classes

CGG can carry both:

- **Subject lessons:** truths about the system, such as an endpoint behavior or a build constraint.
- **Coordination lessons:** truths about how work succeeds, such as a required handoff field or a safer delegation boundary.

Neither class promotes merely because it was captured. Both require evidence appropriate to their consequence and the human gate appropriate to their scope.

## Signals and warrants

Signals track persistent conditions across time. They accrue evidence and pressure. A threshold may mint a warrant demanding attention.

A warrant is not a self-executing law change. It is an escalation artifact. Use `/siren` to inspect and resolve it through the appropriate lane.

## Current Academy status

The legacy Homeskillet Academy is not part of the public v5 plugin. Its teaching sequence predates the current runtime and is being re-derived under [issue #17](https://github.com/prompted365/context-grapple-gun/issues/17). Use this guide, [INSTALL.md](INSTALL.md), and the live runtime contracts until that work is admitted.

## FAQ

**Does CGG send project data to a hosted service?**  
No CGG service is required. The lifecycle is file-based and local. Claude Code itself is still the execution environment you chose.

**Can an agent promote rules without me?**  
No. Agents can detect, derive, compare, prepare, and recommend. Durable promotion remains human-gated.

**What happens if I forget `/cadence`?**  
Born-truth material may still exist, but you lose the clean epoch receipt and handoff. Run `/cadence` at the next legitimate boundary rather than inventing a completed prior state.

**What is `/cadence double-time`?**  
A bounded emergency exit when context is degraded. It preserves the minimum lawful handoff; it does not retroactively make an incomplete epoch rich.

**Does direct GitHub installation differ from npm?**  
Yes. Git installation uses the source manifest and Git commit as version authority. npm installation uses the exact npm package, creates a durable source target, generates a mode-specific versioned manifest, and writes an install receipt.

## Reading path

- Install and remove: [INSTALL.md](INSTALL.md)
- Product and source map: [README.md](README.md)
- Pipeline mechanics: [DEV-README.md](DEV-README.md)
- Deeper architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Runtime topology: [CGG_RUNTIME_TOPOLOGY_AND_LIFECYCLE.md](CGG_RUNTIME_TOPOLOGY_AND_LIFECYCLE.md)
- Terms: [docs/TERMINOLOGY.md](docs/TERMINOLOGY.md)
