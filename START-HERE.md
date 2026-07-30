<p align="center">
  <img src="assets/cgg-banner.jpeg" alt="Context Grapple Gun by Prompted LLC & Ubiquity OS" width="100%" />
</p>

# Start Here

CGG keeps durable lessons, rationale, and unfinished work from disappearing at session boundaries without allowing the agent to promote its own conclusions into law.

## Install and verify

Run from the project you want CGG to govern:

```bash
npx context-grapple-gun install
cgg doctor
```

The default is a user-scope runtime at `~/.cgg/context-grapple-gun`. The project's `.ticzone`, `.ticignore`, `audit-logs/`, `CLAUDE.md`, and `MEMORY.md` remain in the project.

Use `cgg install --dry-run` to inspect the exact mutation plan first.

## The three commands

| Command | Use it when | What remains true |
|---|---|---|
| `/context-grapple-gun:cadence` | A real work epoch ends or context needs a clean rotation | One canonical tic and handoff are sealed. `/cadence` is the clock, not the judge. |
| `/context-grapple-gun:review` | Proposed lessons or warrants are ready for human judgment | The human decides what may persist and how far it may travel. |
| `/context-grapple-gun:siren` | You need signal and recurring-friction visibility | Signal state is surfaced without silently becoming doctrine. |

## A normal cycle

1. **Work normally.** Durable observations are captured near their source as born truth and may become CogPR candidates.
2. **Close with `/cadence`.** CGG emits the tic, writes the handoff, and leaves a resume path.
3. **Start the next session.** Full mode restores bounded continuity and exposes current signal/review state through the hook lifecycle.
4. **Run `/review`.** Approve, reject, modify, merge, defer, or supersede proposals. The agent cannot self-promote.
5. **Continue.** Approved guidance hydrates into later work with its scope and provenance intact.

## Choose an install mode

```bash
# Full: skills + agents + complete hook lifecycle
cgg install --mode full

# Skills: cadence/review/siren and compatibility wrappers; no hooks or agents
cgg install --mode skills

# Convention: marker-bounded protocol in CLAUDE.md only
cgg install --mode convention
```

## Choose runtime scope

```bash
# Default: reusable user runtime
cgg install --scope user

# Explicit project-local runtime
cgg install --scope project
```

Runtime scope is not governance scope. A user installation still reads and writes only through the active project zone unless a reviewed lesson is promoted.

## What `cgg doctor` proves

Doctor checks:

- the managed runtime target and install receipt;
- package, plugin, and marketplace version identity;
- strict single-manifest component authority;
- core skill paths and full-vs-skills mode boundaries;
- Claude Code plugin validation and loaded inventory;
- `.ticzone`, `.ticignore`, and `audit-logs/`;
- the runtime topology report.

A topology script returning successfully is not, by itself, proof that installation succeeded.

## Uninstall safely

```bash
cgg uninstall --dry-run
cgg uninstall
```

By default CGG removes the plugin registration and receipt-owned managed runtime. It preserves `.ticzone`, `.ticignore`, `audit-logs/`, `MEMORY.md`, and user-authored `CLAUDE.md` content.

Use `--remove-convention` only when you also want the marker-bounded CGG protocol block removed.

## Learn the vocabulary

See [docs/TERMINOLOGY.md](docs/TERMINOLOGY.md). The shortest mapping is:

- **CogPR** — proposed durable learning;
- **tic** — canonical ordered epoch event;
- **zone** — project jurisdiction boundary;
- **ladder** — authorized scope path;
- **receipt** — evidence that a transition actually occurred;
- **handoff** — bounded continuity into the next work epoch.

## Academy currentness

Homeskillet Academy predates the v5 distribution and runtime contract. It is intentionally excluded from the public plugin surface while [issue #13](https://github.com/prompted365/context-grapple-gun/issues/13) reconciles the curriculum.

The legacy `/init-governance` skill is also held outside the public manifest while [issue #14](https://github.com/prompted365/context-grapple-gun/issues/14) reconciles or retires its pre-v5 direct-copy contract.

## More depth

- [INSTALL.md](INSTALL.md) — installation and migration contract
- [DEV-README.md](DEV-README.md) — runtime mechanics
- [ARCHITECTURE.md](ARCHITECTURE.md) — system model and scale boundary
- [docs/RELEASE.md](docs/RELEASE.md) — version, validation, and npm release authority
