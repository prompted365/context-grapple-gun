# Ticignore Scoping -- Zones, Muffling & Monorepo Patterns

**Time: ~5 min**

CGG's signal routing is spatial. Signals have volume. Distance attenuates volume. The `.ticzone` file defines the space. The `.ticignore` file defines what is excluded from it.

---

## `.ticzone` -- The acoustic region anchor

A `.ticzone` file at a directory root declares an acoustic region. Everything within the zone shares a signal namespace, a muffling constant, and a set of active frequency bands.

```jsonc
{
  // Zone identifier. Used in tic records and acoustic routing.
  "name": "my-project",

  // IANA timezone string. Maps the zone to Earth's temporal grid.
  "tz": "America/Toronto",

  // Optional geographic coordinates. Enables future spatial coupling.
  "lat": 43.6532,
  "lon": -79.3832,

  // Paths belonging to this zone. Relative to .ticzone location. ~ supported.
  "include": ["."],

  // Which frequency bands are active in this zone.
  "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"],

  // Acoustic muffling constant for distance-based attenuation.
  "muffling_per_hop": 5
}
```

The format is JSONC -- `//` comments and trailing commas are accepted.

**Key fields:**

| Field | Purpose |
|-------|---------|
| `name` | Zone identifier. Appears in tic records and signal routing. |
| `tz` | Timezone. Maps the zone to a temporal grid for tic timestamps. |
| `include` | Array of paths in the zone. Usually just `["."]` for the whole project. |
| `bands` | Active frequency bands. Leave PRESTIGE off -- it is governance-blocked. |
| `muffling_per_hop` | How much volume is lost per directory hop. Default: 5. |

---

## The muffling formula

```
effective_volume = volume - (directory_hops(source, target) * muffling_per_hop)
```

**`directory_hops`** counts the number of directory segments between the signal's source path and the listener's path. A signal emitted from `src/auth/` and heard at `src/api/routes/` traverses 3 hops (up to `src/`, down to `api/`, down to `routes/`).

**`muffling_per_hop`** is the attenuation constant from `.ticzone`. Default is 5.

**Example:** A signal at volume 30 emitted from `src/auth/` with `muffling_per_hop = 5`:

| Listener at | Hops | Effective volume |
|-------------|------|-----------------|
| `src/auth/` | 0 | 30 |
| `src/` | 1 | 25 |
| `src/api/` | 2 | 20 |
| `src/api/routes/` | 3 | 15 |
| `tests/integration/api/` | 5 | 5 |
| `docs/architecture/decisions/` | 6 | 0 (inaudible) |

### PRIMITIVE never fully muffled

PRIMITIVE band signals have a minimum effective volume of 1, regardless of distance. A safety signal emitted at volume 5 from `src/auth/` is still audible at effective volume 1 even 100 directories away. This is by design -- emergencies always propagate.

All other bands can be fully muffled to effective volume 0.

### Cross-zone penalty

When a signal crosses from one zone into a nested zone (or vice versa), muffling is applied at **2x** the per-hop rate. Inter-zone communication is deliberately attenuated -- zones are acoustic boundaries.

---

## `.ticignore` -- Excluding paths from the zone

`.ticignore` uses the same syntax as `.gitignore`. Paths matching these patterns are excluded from the zone's acoustic space -- signals originating from ignored paths are not routed.

**Common exclusions:**

```gitignore
# Dependencies -- not your governance surface
node_modules/
vendor/
.venv/

# Build artifacts -- ephemeral, not auditable
dist/
build/
target/
__pycache__/
*.pyc

# Git internals
.git/

# Skill templates — contain example CogPR blocks, not real items
.claude/skills/

# Large binaries
*.wasm
*.so
*.dylib
```

**What NOT to ignore:**

- `MEMORY.md` files -- they hold active governance data (pending CPRs, operational memory). They are gitignored but NOT ticignored.
- `audit-logs/` -- this is your signal store. Never ignore it.
- `CLAUDE.md` files -- these are your governance surface.

---

## Flat zone vs nested zones

### Flat zone (most projects)

One `.ticzone` at the project root. Everything in the project shares the same acoustic space. Muffling still applies based on directory distance, but there is no zone boundary penalty.

```
my-project/
  .ticzone          <-- single zone: "my-project"
  .ticignore
  src/
  tests/
  docs/
```

This is the default and works for most repositories.

### Nested zones (large projects)

A `.ticzone` in a subdirectory creates a nested zone. The nearest `.ticzone` establishes the current jurisdictional position — there is no automatic parent/child field merge. The inner zone must define its own `tz`, `bands`, and other fields, or fall back to code defaults. Cross-zone signals pay the 2x muffling penalty.

```
my-monorepo/
  .ticzone          <-- parent zone: "my-monorepo"
  .ticignore
  packages/
    auth/
      .ticzone      <-- nested zone: "auth-service"
      src/
    api/
      .ticzone      <-- nested zone: "api-gateway"
      src/
    shared/
      src/           <-- no .ticzone, belongs to parent zone
```

Nested zones are useful when packages have genuinely independent governance -- different teams, different release cycles, different signal priorities. Signals within `auth/` route cheaply (single-zone muffling). Signals from `auth/` to `api/` pay the 2x cross-zone penalty.

---

## Monorepo patterns

### Pattern 1: One zone at root (recommended for most monorepos)

```
monorepo/
  .ticzone        <-- "monorepo", all packages share the zone
  .ticignore
  packages/
    frontend/
    backend/
    shared/
```

Pros: Simple. All signals visible across the whole repo. Muffling handles natural distance.

Cons: A PRIMITIVE signal deep in `packages/backend/auth/` is still audible at volume 1 in `packages/frontend/components/`. That might be noise for the frontend team.

### Pattern 2: One zone per package

```
monorepo/
  .ticzone        <-- "monorepo" (thin root zone)
  packages/
    frontend/
      .ticzone    <-- "frontend"
    backend/
      .ticzone    <-- "backend"
```

Pros: Clean acoustic isolation between packages. Backend signals stay in backend unless they are loud enough to cross the zone boundary at 2x muffling.

Cons: More configuration. Cross-package signals are heavily attenuated. Shared-concern signals (e.g., a database schema change affecting both frontend and backend) may need higher initial volume.

### Pattern 3: Hybrid (zone at root + selective nesting)

```
monorepo/
  .ticzone        <-- "monorepo"
  packages/
    frontend/     <-- no .ticzone, part of root zone
    backend/      <-- no .ticzone, part of root zone
    vendor/
      .ticzone    <-- "vendor" (isolated, read-only upstream)
```

Pros: Most packages share the acoustic space naturally. Only truly isolated subsystems (vendor code, forked dependencies) get their own zone.

Cons: Requires judgment about what deserves isolation.

---

## Choosing your `muffling_per_hop`

The default of 5 works for most projects. Adjust based on directory depth:

| Project shape | Suggested muffling | Reasoning |
|--------------|-------------------|-----------|
| Flat (few directories, < 3 levels deep) | 8-10 | Fewer hops, so each hop should attenuate more to create meaningful distance. |
| Deep (many levels, monorepo) | 3-5 | Many hops already create natural attenuation. Lower muffling prevents signals from going silent too fast. |
| Single package, simple structure | 5 (default) | The default handles most cases. |

You can always adjust `muffling_per_hop` later. It is a tuning knob, not a commitment.

---

## Quick reference

```bash
# Create a flat zone
echo '{
  "name": "my-project",
  "tz": "UTC",
  "include": ["."],
  "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"],
  "muffling_per_hop": 5
}' > .ticzone

# Create a ticignore
cat > .ticignore << 'EOF'
node_modules/
dist/
target/
__pycache__/
.git/
vendor/
.claude/skills/
EOF
```

That is all you need for zone setup. The acoustic model handles the rest.
