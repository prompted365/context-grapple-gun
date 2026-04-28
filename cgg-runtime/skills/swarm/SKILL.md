---
name: swarm
description: |
  Orchestrate governed parallel agent work. Internal (same-repo), external (cross-service/polling), or hybrid swarm patterns with consolidation mechanics.

  CENTROID:
  parallel deliverable orchestration with governed consolidation

  IS:
  - internal swarm (same-repo agents, shared context, artifact consolidation)
  - external swarm (cross-service, polling-based, async completion)
  - hybrid swarm (internal agents + external polling + inbox consolidation)
  - dependency-gated task DAG execution (blocked_by lists)

  IS NOT:
    collapse_zones:
      - adversarial reasoning (use /stage — arenas produce governance pressure; swarm produces deliverables)
      - single-agent wrapper (swarm implies ≥2 parallel agents with consolidation)
      - autonomous consolidator (lead holds consolidation authority; agents do not merge)
      - scope mutator (swarm coordinates work; does not promote, inscribe, or cross governance boundaries)
      - silent dispatch (every swarm writes a spec YAML before execution)
    sibling_overlaps:
      - /stage (governed reasoning orchestration)
      - /loop (polling primitive used inside external/hybrid swarm)
      - /review (constitutional judgment)

  WHEN:
  - when work can genuinely run in parallel (no strict sequencing across the whole)
  - when multiple file/module/service surfaces must be touched together
  - when cross-repo or external-service coordination requires async consolidation
  - on explicit operator invocation

  NOT WHEN:
  - for adversarial reasoning (use /stage)
  - for single-agent work (overhead exceeds benefit)
  - mid-arena (arena has its own phase execution; swarming inside an arena double-orchestrates)
  - when the workload is sequential by nature (each step depends on the prior result)

  RELATES TO:
  - /stage (orchestration — stage runs adversarial reasoning; swarm runs parallel deliverables)
  - /loop (polling — external/hybrid swarms use /loop for external-completion polling)
  - /review (constitutional judgment — swarm produces artifacts; review evaluates any surface claiming promotion)

  ARGS:
    stance: dispatch
    off_envelope: ask
    # off_envelope rationale: /swarm has three distinct patterns (internal/external/
    # hybrid) with very different execution mechanics. Undeclared-arg may indicate
    # caller confused between /swarm patterns or between /swarm and /stage —
    # ask prevents silent misroutes.
    core_dispatch_rays:
      - ""          → interactive (describe work, infer pattern)
      - "internal"  → same-repo parallel agents with shared task list
      - "external"  → cross-service with polling-based consolidation
      - "hybrid"    → internal agents + external polling + inbox consolidation
      - "--plan"    → generate swarm spec without executing
      - "--spec"    → resume from existing swarm spec
    secondary_modulation_axes:
      - consolidation_mode: artifact | return-value | inbox
      - dependency_style: dag | linear | free
      - polling_interval: <duration>
user-invocable: true
---

# /swarm — Governed Parallel Agent Orchestration

Orchestrate multi-agent work with structured consolidation. Unlike `/stage` (adversarial reasoning for governance input), `/swarm` coordinates parallel *deliverable* work with dependency gating and result merging.

## Invocation

- **`/swarm`** — interactive mode. Describe the work, infer pattern.
- **`/swarm internal "<task>"`** — same-repo parallel agents with shared task list.
- **`/swarm external "<task>"`** — cross-service agents with polling-based consolidation.
- **`/swarm hybrid "<task>"`** — mix of internal agents + external polling.
- **`/swarm --plan`** — generate swarm spec without executing (dry run).
- **`/swarm --spec <path>`** — resume from existing swarm spec.

## Pattern Selection

### Internal Swarm

All agents operate in the same repo and context. Lead orchestrator holds shared context, delegates work units, and consolidates results.

**When to use**: parallel code changes, multi-file refactors, research queries that can be parallelized, governance batch operations.

**Spawning**: `Agent()` tool with `run_in_background: true` for parallel execution.

**Consolidation**: Lead reads agent outputs (file artifacts or return values), validates completeness, merges results.

**Dependency gating**: Task DAG with `blocked_by` lists (same pattern as arena phases).

```
Lead spawns agents A, B, C (parallel, no blockers)
  -> A, B, C complete (file artifacts written)
  -> Lead reads artifacts, validates
  -> Lead spawns D (blocked_by: [A, B, C])
  -> D completes
  -> Lead consolidates final output
```

### External Swarm

Agents work across services, repos, or external systems. Results arrive asynchronously via polling or inbox.

**When to use**: CI/CD monitoring, cross-repo coordination, external API orchestration, long-running background processes.

**Spawning**: Mix of `Agent()` for initial dispatch + `/loop` for polling checkpoints.

**Consolidation**: Artifact-based. Each agent writes results to a known path. Consolidation agent polls for completion artifacts.

**Dependency gating**: File-existence checks + inbox state machine (arrived/completed).

```
Lead dispatches work to external surfaces (GH Actions, APIs, repos)
  -> /loop polls for completion artifacts at interval
  -> On completion detected: Lead reads artifacts
  -> Lead consolidates and reports
```

### Hybrid Swarm

Internal agents + external polling + inbox-based consolidation. The most flexible pattern.

**When to use**: work that requires both local computation and external coordination — e.g., generate code locally, deploy externally, validate via polling.

**Spawning**: Internal agents via `Agent()`, external monitoring via `/loop`, inbox for async results.

**Consolidation**: Internal results merge immediately; external results arrive via inbox transmissions and merge on scan.

```
Lead spawns internal agents A, B (parallel)
  -> A, B complete (immediate consolidation)
  -> Lead dispatches external work
  -> /loop polls external completion
  -> External results arrive in inbox
  -> Lead merges internal + external results
  -> Final consolidation
```

## Swarm Spec Format

Every swarm generates a spec YAML before execution:

```yaml
id: "<YYYY-MM-DD>_<slugified-task>"
title: "<task description>"
pattern: internal | external | hybrid
status: planned | active | consolidating | completed
created_at: "<ISO-8601>"
created_tic: <tic number>

lead:
  entity_id: "ent_homeskillet"
  context_budget: "<token estimate>"

agents:
  - id: "agent-a"
    role: "<what this agent does>"
    pattern: internal | external
    model: "sonnet | haiku | opus"
    isolation: "worktree | none"
    blocked_by: []
    owns_regions: []         # optional — region-level ownership for sub-file parallelism (e.g. ["lights/*", "cameras/*"]); empty implies file-level ownership per blocked_by
    output_path: "<where results go>"
    timeout_minutes: <number>

  - id: "agent-b"
    role: "<what this agent does>"
    pattern: internal
    blocked_by: ["agent-a"]
    output_path: "<where results go>"

consolidation:
  strategy: "merge_artifacts | inbox_collect | lead_synthesize"
  validation: "<how to verify completeness>"
  output_path: "<final consolidated output>"

polling:  # only for external/hybrid
  interval_minutes: <number>
  check_command: "<command to check completion>"
  timeout_minutes: <number>
  max_checks: <number>
```

## Execution Steps

### Step 1: Gather Context

**Interactive mode** (no pattern specified):
1. Ask: "What work needs to be parallelized?"
2. Ask: "Does all work happen in this repo, or does some involve external services?"
3. Infer pattern (internal/external/hybrid) from answers.
4. Confirm agent count and roles.

**Direct mode** (pattern + task specified):
1. Parse task description.
2. Infer agent breakdown from task complexity.
3. Confirm with user unless `--plan` mode.

### Step 2: Generate Swarm Spec

1. Create spec at `audit-logs/swarms/<id>/spec.yaml`.
2. Define agent roles, dependency DAG, consolidation strategy.
3. If `--plan` mode, stop here and display spec for review.

### Step 3: Spawn Agents

For each agent with no unmet blockers:
1. Spawn via `Agent()` with `run_in_background: true`.
2. Pass agent-specific prompt including: role, output_path, constraints.
3. If `isolation: "worktree"`, use worktree mode to avoid file conflicts.
4. Record agent spawn in `audit-logs/swarms/<id>/status.jsonl`.

### Step 4: Monitor & Gate

1. Wait for background agent completions (automatic notification).
2. On each completion:
   - Validate output exists at expected path
   - Check quality gate (if specified)
   - Update status.jsonl
   - Spawn any agents whose blockers are now satisfied
3. For external pattern: set up `/loop` polling at specified interval.

### Step 5: Consolidate

When all agents complete:
1. Execute consolidation strategy (merge artifacts, collect from inbox, or lead synthesis).
2. Write consolidated output to `consolidation.output_path`.
3. Update swarm spec status to `completed`.
4. Report summary to user.

## Consolidation Strategies

### merge_artifacts

Lead reads all agent output files and merges them. Best for parallel file operations where outputs don't overlap.

### inbox_collect

Results arrive as inbox transmissions. Lead scans inbox for all messages with matching `thread_id`, collects and synthesizes.

### lead_synthesize

Lead reads all agent outputs and produces a new synthesis document. Best when agent outputs need interpretation, not just concatenation.

## Cost Awareness

Agent teams are expensive. Each agent = separate Claude instance with full context.

| Pattern | Typical Cost | When Justified |
|---------|-------------|----------------|
| Internal (2-3 agents) | 2-3x single agent | Genuinely independent parallel work |
| Internal (4+ agents) | 4+x single agent | Only if parallelism saves significant wall-clock time |
| External | Low (polling is cheap) | Cross-service coordination |
| Hybrid | Variable | Mix of local + external work |

**Rule**: Don't swarm what a single agent can do sequentially in reasonable time. Swarm when parallelism provides real wall-clock savings or when work genuinely cannot be serialized.

## Governance Integration

### Audit Trail

All swarm activity is logged to `audit-logs/swarms/<id>/`:
- `spec.yaml` — swarm specification (immutable after creation)
- `status.jsonl` — agent spawn/completion events (append-only)
- Agent output artifacts (per-agent subdirectories)
- `consolidation/` — merged output

### Entity Integration

- Lead agent is the accountability owner for the swarm
- Each spawned agent gets entity lineage: `SPAWNED` edge from lead, `DELEGATED_BY` edge
- Ephemeral agents: inbox items forwarded to lead on exit (per agent-inbox-schema.md)

### Signal Emission

If a swarm exceeds timeout or agents fail:
- Emit TENSION signal with payload `{swarm_id, failed_agents, timeout_exceeded}`
- Lead decides: retry, skip, or escalate to operator

## Relationship to /stage

| Dimension | /stage | /swarm |
|-----------|--------|--------|
| **Purpose** | Adversarial reasoning (governance input) | Parallel deliverable work |
| **Agent roles** | Positional advocates + lead | Task-specialized workers + lead |
| **Output** | Governance artifacts (signals, CogPRs, pressure) | Deliverable artifacts (code, docs, configs) |
| **Consolidation** | Lead synthesizes adversarial positions | Lead merges parallel outputs |
| **Template source** | Arena templates (triangulation, lattice) | Swarm spec (internal/external/hybrid) |

Both use the same underlying mechanics (Agent tool, dependency DAG, phase gating) but serve different purposes. A swarm produces deliverables; a stage produces governance inputs.

## References

- `autonomous_kernel/agent-inbox-schema.md` — inbox state machine for async result collection
- `cgg-runtime/skills/stage/SKILL.md` — sibling skill (adversarial reasoning)
- `cgg-runtime/agents/mogul.md` — Mogul's subdelegation pattern (donor for delegation mechanics)
