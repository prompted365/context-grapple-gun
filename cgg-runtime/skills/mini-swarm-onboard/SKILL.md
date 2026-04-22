---
name: mini-swarm-onboard
description: |
  Quick CGG onboarding through governed triangulation — three agents debate which CGG mechanic matters most.

  CENTROID:
  quick governed-triangulation onboarding demonstration

  IS:
  - single-arena three-agent debate with narrator commentary
  - live CGG mechanic exposure compressed to ~10 minutes
  - dry-run surfacing of arena spec and task DAG before execution

  IS NOT:
    collapse_zones:
      - production arena (demo-scoped; never produces real governance pressure or CogPRs)
      - doctrine author (demonstrates existing mechanics; never modifies them)
      - extended course (single arena only — the multi-chapter course is /homeskillet-academy)
      - runtime reshape surface (narrates agent spawns; never restructures runtime)
    sibling_overlaps:
      - /homeskillet-academy (deeper multi-chapter course)
      - /stage (real arena orchestration — mini-swarm is a demo variant)

  WHEN:
  - on first-exposure demo within a ~10 minute window
  - when a visitor asks "what does governed triangulation look like"
  - when a fast CGG pitch without full academy scaffold is desired

  NOT WHEN:
  - as a production arena (use /stage)
  - for extended pedagogy across multiple mechanics (use /homeskillet-academy)
  - without CGG runtime surfaces installed (pre-flight will refuse)

  RELATES TO:
  - /homeskillet-academy (extended course — mini-swarm is the trailer; academy is the full screening)
  - /stage (real arena orchestration — mini-swarm is the demo; /stage carries the production weight)
  - /init-governance (install prereq — runtime must be bootstrapped before mini-swarm can run)

  ARGS:
    stance: dispatch
    off_envelope: proceed-with-note
    # off_envelope rationale: /mini-swarm-onboard's default is "full narrated run."
    # Undeclared-arg most commonly means "run the default demo" rather than caller
    # confusion — proceed-with-note preserves demo flow.
    core_dispatch_rays:
      - ""          → full run with narration gates
      - "--quick"   → compressed narration (single-line summaries)
      - "--dry-run" → print arena spec and task DAG, then exit
    secondary_modulation_axes:
      - pacing: guided | rapid
tools: Read, Grep, Glob, Agent, Bash
trigger: /mini-swarm-onboard
---

# /mini-swarm-onboard — Learn CGG by Watching Governance in Action

Three agents debate "Which CGG mechanic is most valuable?" while a narrator explains what is happening at each stage. The user learns governed triangulation by observation, not instruction.

## Invocation

- **`/mini-swarm-onboard`** — full run with narration gates
- **`/mini-swarm-onboard --quick`** — compressed narration (single-line summaries)
- **`/mini-swarm-onboard --dry-run`** — print the arena spec and exit

## Pre-flight Checks

Before executing, verify:

1. **CGG skills directory exists:** check for `cgg-runtime/skills/` relative to the zone root
2. **CGG agents directory exists:** check for `cgg-runtime/agents/` relative to the zone root
3. **Audit-logs directory exists:** check for `audit-logs/` at the zone root (create `audit-logs/arenas/pressure-reports/` if missing)
4. **Stage directory exists:** check for `stage/shows/` at the zone root (create if missing)
5. **Template exists:** verify `stage/templates/arenas/mini-swarm-onboard/` contains `spec.md`, `tasks.yaml`, `scoring.yaml`, `prompt.txt`

If any check fails, report what is missing and suggest running `/init-governance` or `/init-gun`.

## Execution Steps

### Step 1: Pre-flight

Run the pre-flight checks above. Report status to user:

```
Mini-Swarm Onboard — pre-flight
  CGG skills:    OK
  CGG agents:    OK
  audit-logs:    OK
  stage dir:     OK
  template:      OK
```

### Step 2: Dry-run gate

If `--dry-run` is set:
1. Read the arena spec from `stage/templates/arenas/mini-swarm-onboard/spec.md`
2. Read the task DAG from `stage/templates/arenas/mini-swarm-onboard/tasks.yaml`
3. Print both to the user
4. Exit

### Step 3: Generate show ID and directory

1. Generate show ID: `mini-swarm-onboard-YYYYMMDDTHHMMSS` (use current timestamp)
2. Create show directory: `stage/shows/<show-id>/`
3. Copy template files into the show directory for reference

### Step 4: Delegate to /stage

Invoke `/stage` with the mini-swarm-onboard template:

```
/stage --template mini-swarm-onboard --mode experimental --decision "Which CGG mechanic is most valuable: Signal Manifold, CogPR Pipeline, or Cadence System?"
```

The `/stage` skill handles:
- Show spec generation
- Team spawning with the 3 advocates + lead
- Phase enforcement with dependency gating
- Synthesis and pressure extraction

### Step 5: Narration gate execution

The LEAD (orchestrator) delivers narration gates between phases. Narration content:

**N1** (after context phase):
> You just watched three agents study their opponents before defending themselves. Rule 1 — Opponent-Context First — prevents strawmen. Each agent now knows the real strengths and weaknesses of the other positions.

**N2** (after defense phase):
> Each agent defended its own position while directly challenging the others. Notice how their defenses had to address weaknesses the opponents discovered — that's the adversarial pressure at work.

**N3** (after rebuttal phase):
> The rebuttal round is the 3x multiplier. Without it, agents present once and the lead guesses. With it, the strongest arguments survive challenge. Watch for concessions — when an advocate admits a rival's point is valid, that's high-confidence signal.

**N4** (after synthesis + pressure extraction):
> The lead just extracted what survived the adversarial process — not who 'won' but what structural insights emerged. The pressure report classifies findings by confidence tier. Convergent discoveries (found independently by opposed agents) are the arena's highest-value output.

**`--quick` mode narration:**
- N1: "Opponent-context phase complete — agents studied rivals before defending."
- N2: "Defense phase complete — each agent addressed discovered weaknesses."
- N3: "Rebuttal phase complete — strongest arguments survived challenge."
- N4: "Synthesis and pressure extraction complete — see report for governance outputs."

### Step 6: Post-arena summary

After the arena completes (including N4), print a summary:

```
/mini-swarm-onboard complete

Show:       <show-id>
Template:   mini-swarm-onboard (governed-triangulation + narration gates)
Mode:       experimental
Agents:     3 advocates + 1 lead/narrator
Phases:     9/9 complete (5 arena + 4 narration gates)

Artifacts produced:
  Synthesis:    stage/shows/<show-id>/synthesis.md
  Pressure:     audit-logs/arenas/pressure-reports/<show-id>.json
  Show spec:    stage/specs/<show-id>.yaml

Governance routing (experimental mode):
  Subject lessons:  kept locally (not routed to governance)
  Process lessons:  routed as CogPR candidates
  Meta lessons:     routed as CogPR candidates
  Signals:          blocked (experimental mode)

What you just saw:
  1. Three agents studied each other's positions (opponent-context first)
  2. Each defended its own position while challenging the others
  3. Each rebutted the attacks it received
  4. The lead synthesized what survived the adversarial process
  5. A pressure report classified findings by type and confidence

This is how CGG arenas produce governance inputs — through structured
opposition, not consensus. The strongest arguments survive challenge.

Next steps:
  /review   — evaluate any process/meta CogPRs generated by this arena
  /stage    — run your own arena on a real decision
  /siren    — check signal health
  /cadence  — manage session boundaries
```

## Ownership

This skill owns:
- `stage/shows/<show-id>/` (create, delegate to /stage)

This skill delegates to:
- `/stage` (arena execution, show spec, pressure report, governance routing)

This skill never modifies:
- CLAUDE.md
- MEMORY.md
- `.ticzone`

## Critical Invariants

1. **Arena mode is always experimental** — this is a demo, not a governance decision
2. **Narration gates are mandatory** — they are the teaching mechanism
3. **Subject findings stay local** — "which mechanic is most valuable" is not governance input
4. **Process/meta lessons may route** — how the arena works IS governance-relevant
5. **The LEAD narrates, never advocates** — narrator neutrality is a hard constraint
