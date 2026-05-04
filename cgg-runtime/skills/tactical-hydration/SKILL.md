---
name: tactical-hydration
description: |
  Runtime tactical context hydration — staged discovery and bounded source-bearing hydration for agent intent. Answers "how does an agent know where to look before it already knows where to look?" via filesystem shape, structural signals, and typed candidate baskets. Working acronym: RTCH (runtime-tactical-context-hydration).

  CENTROID:
  intent → bounded, source-reenterable evidence packet via staged source-bearing discovery

  IS:
  - structured intake of agent/Architect intent (goal, seeds, profile, fanout, mutation risk)
  - zone orientation (cwd / repo root / zone root / rung chain / obvious truth files)
  - low-cost shape scout (directory map, headings, durable handles, JSON/YAML keys, refs)
  - typed candidate basket with origin/use taxonomy and pairing rule enforcement
  - tactical probe plan (multiple bounded probes, not one giant regex)
  - bounded chunk hydration with line-range provenance and next-re-entry commands
  - agent-ready evidence packet emission (selected_surfaces, unresolved_questions, caution_map)
  - optional handoff to /consolidate for full-surface dump packaging

  IS NOT:
    collapse_zones:
      - vector database (no embedding-space retrieval; federation prohibits at federation rung)
      - semantic oracle (RTCH does not "understand" content; it surfaces structural signals)
      - doctrine engine (RTCH produces evidence; downstream consumers judge truth)
      - terrain engine replacement (federation cartography handles multi-plane semantic projection; RTCH is tactical layer beneath)
      - /consolidate rewrite (discovery and packaging do not collapse)
      - lossy compressor (bounded chunks preserve source re-entry; never summarize away source)
      - confidence-inflated smart consolidator
    sibling_overlaps:
      - /consolidate (RTCH selects; /consolidate packages — distinct boundaries; compose, don't replace)
      - file-access-discipline (RTCH outputs targets; hydration USES file-access-discipline as execution primitive)
      - load-doctrine-chain (both serve subagent context; load-doctrine-chain owns CLAUDE.md chain only, RTCH owns wider source set)
      - cache-ops (pattern source for trust-tier shape; storage NOT shared; RTCH packets are separate evidence cache)
      - queue_state_compile (analogy only — both convert append-only source to compiled view; different transforms)

  WHEN:
  - when agent intent is vague and discovery is needed before reading or consolidation
  - when bare grep would over-fanout or under-discover a vague target
  - when an arena, harpoon, /review, or other lane needs source-bearing evidence before action
  - when bounded chunk hydration is appropriate (large governance files, doctrine chains, audit history)
  - when the candidate-basket discipline (origin/use tagging, pairing rule) is needed to prevent generic-term overconfidence
  - when source re-entry must be preserved (consumer may need to return to source for fuller context)

  NOT WHEN:
  - when target is fully known (single file, single line range) — read it directly via file-access-discipline
  - when the operation is mutation-only on a known target (use Edit/Write directly)
  - when /consolidate has already been invoked with explicit targets (RTCH would re-do discovery)
  - when the operation requires semantic similarity (RTCH does not do that; federation prohibits vector DB)
  - when the consumer needs a packaged dump only (skip RTCH; /consolidate alone is sufficient if targets are known)
  - when promoting doctrine (route through /review; RTCH evidence may inform but does not promote)

  RELATES TO:
  - /consolidate (compose: RTCH selects targets; /consolidate packages selected_surfaces into dump with provenance reference back to RTCH packet)
  - file-access-discipline (compose: RTCH Stage 6 hydration USES file-access-discipline chunked-read as execution primitive)
  - load-doctrine-chain (compose: RTCH may invoke for doctrine_chain target_profile zone orientation)
  - zone_root.py (compose: RTCH Stage 2 anchors on zone-root walk-up)
  - atomic-append (compose: optional RTCH packet persistence uses atomic-append write hygiene)
  - queue_state_compile (analogous: both implement "raw source → compiled view" pattern)
  - /review preflight (downstream: future integration consumes RTCH packets as bench-packet discovery surface)
  - arena spec authoring (downstream: future integration uses RTCH packets for context preparation)
  - harpoon orchestrator (downstream: future integration uses RTCH for anchor-spot discovery on external binders)

  ARGS:
    stance: dispatch
    off_envelope: ask
    # off_envelope rationale: RTCH requires a structured intake to operate (goal,
    # target_profile, fanout_level, mutation_risk, expected_output, enough_evidence).
    # Bare invocation without intake fields would force the lane to guess discovery
    # scope, defeating the discipline. Ask elicits the missing fields.
    core_dispatch_rays:
      - ""                            → interactive (elicit intake form)
      - "--goal <sentence>"           → with intake fields on CLI
      - "--intake <intake_json_path>" → from a saved/persisted intake
      - "--persist"                   → persist resulting packet to audit-logs/rtch/packets/
      - "--handoff-to-consolidate"    → after packet emission, hand selected_surfaces to /consolidate
    secondary_modulation_axes:
      - target_profile: doctrine_chain | audit_history | code_path | manifest_registry | vague_intent | mixed
      - fanout_level: conservative | normal | wide
      - mutation_risk: read_only | low_mutation | high_mutation
      - expected_output: hydration_packet | target_set_for_consolidate | single_chunk | claim_evidence

  IMPLEMENTATION_STATUS:
    binder: audit-logs/governance/runtime-tactical-context-hydration-binder.md (Phase 1 complete, tic 223)
    runner_script: NOT YET BUILT — Phase 2 deliverable (planned: cgg-runtime/scripts/rtch.py)
    current_mode: manual-discipline — agent walks the 8 stages using Read/Bash/Grep tools directly
    promotion_status: design lane, not doctrine; Phase 7 routes the doctrine question after Phase 6 validation

user-invocable: true
---

# /tactical-hydration — Runtime Tactical Context Hydration Lattice (RTCH)

You are the **Tactical Hydration Lane** — a staged discovery and bounded-hydration discipline that produces source-bearing evidence packets for agent intent. You sit BETWEEN bare-grep ("just go look") and /consolidate ("package these targets"). You select targets; /consolidate packages them.

> **Authoritative spec**: `audit-logs/governance/runtime-tactical-context-hydration-binder.md` (1050 lines).
> Read the binder before deviating from any procedure here. The binder owns design authority; this skill body is the runtime execution surface.

## Core Doctrine (Binder Spine)

Source discovery is staged. Candidate terms are not truth. Grep terms are not intelligence. Shape features are not proof. Hydration must preserve source re-entry. Bounded chunks beat blind full-file reads. Fanout must be declared. Every hydrated surface must say why it was selected.

## Implementation Mode

**Phase 1 (current)**: manual-discipline mode. The agent walks the 8 stages using Read, Bash (rg, find, wc, jq, git grep), and Grep tools directly. There is no `rtch.py` runner yet — that is Phase 2 deliverable.

**Phase 2+ (future)**: `cgg-runtime/scripts/rtch.py` will orchestrate Stages 2-7 with declared schema enforcement; this skill body will then become a thin CLI wrapper. The discipline below remains the same; only the execution mechanism shifts.

## When the Architect (or another agent) invokes you

1. **Elicit the intake form** if not provided. The intake is the lane's contract. Required fields:
   - `goal` (one sentence)
   - `target_profile` (doctrine_chain | audit_history | code_path | manifest_registry | vague_intent | mixed)
   - `fanout_level` (conservative | normal | wide)
   - `mutation_risk` (read_only | low_mutation | high_mutation)
   - `expected_output` (hydration_packet | target_set_for_consolidate | single_chunk | claim_evidence)
   - `enough_evidence_definition` (one sentence — when does the lane halt?)
   - Optional: `known_target`, `explicit_seeds`, `forbidden_assumptions`, `known_neighbor_surfaces`
   
   Without these fields, decline and ask. The intake is load-bearing — without `enough_evidence_definition` the lane has no halting condition and tends to over-fanout.

2. **Run the 8 stages in order**. Each stage produces typed output for the next.

## Stage 1 — Intake (already captured at invocation)

Confirm intake completeness. If `fanout_level: conservative` AND `mutation_risk: high_mutation`, surface the constraint stack to the user before proceeding.

## Stage 2 — Zone Orientation

Determine the working zone before searching:

```bash
pwd                              # current cwd
git rev-parse --show-toplevel    # repo root
# zone_root: walk up from cwd to find .ticzone (use zone_root.py if available)
python3 /Users/breydentaylor/canonical/canonical_developer/context-grapple-gun/cgg-runtime/scripts/zone_root.py
git status --short               # current state snapshot
```

Capture:
- `cwd`, `repo_root`, `zone_root`
- Rung chain: list of `.federation-root`, `.estate-root`, `.domain-root`, `.site-root` markers between zone-root and target dir; each rung's CLAUDE.md path if present
- Obvious truth files at zone-root: `CLAUDE.md`, `SYSTEM_MAP.md`, `MEMORY.md` (in user-global memory dir), `audit-logs/`, `sync-manifest.json`
- Obvious manifests/registries: `audit-logs/cprs/effective-state/`, `audit-logs/agent-mailboxes/inbox-registry.json`, `actor-registry.json`, `sub_telos.yaml`

For `target_profile: doctrine_chain`, optionally invoke load-doctrine-chain:

```bash
python3 /Users/breydentaylor/canonical/canonical_developer/context-grapple-gun/cgg-runtime/scripts/lib/load_doctrine_chain.py <target_file>
```

## Stage 3 — Shape Scout (Low-Cost Source-Shape Scans)

Run filesystem-shape scans BEFORE semantic hydration. No grep yet — structural signals only. Bound every scan; abort or warn on cost ceiling.

Required scans (skip those not applicable to the target_profile):

```bash
# Directory map
find <zone_or_target_dir> -maxdepth 3 -type d | head -50

# Candidate filenames + sizes
find <target_vicinity> -type f -name '*.md' -size -500k | head -50

# Headings (markdown only)
rg --no-heading -n '^#+\s' <obvious_truth_files>

# Frontmatter keys (small md files)
awk '/^---$/{p=!p; next} p' <md_file>

# Durable IDs in scope
rg -n 'cpr_[a-z_0-9]+|sig_[a-f0-9]+|tic-[0-9]+|OAVPLT-[0-9]+' <bounded_set>

# JSON/YAML keys (small json files)
jq 'keys' <small_json>

# Code symbols (code targets)
rg '^import |^from |^export |^def |^class |^function ' <code_dir>

# Audit/tic markers
rg -n '^## Session Lessons \(tic ' <memory_md>

# Source-of-truth phrase
rg -i 'authoritative|source of truth|canonical|single source' <bounded_set>

# Current/deprecated/superseded
rg 'deprecated|superseded|TERMINAL|status: pending|status: deferred' <bounded_set>
```

Output: `shape_inventory` — each scan tagged with input pattern, file count touched, hit count, rough wall time.

## Stage 4 — Candidate Basket

Build a typed basket. **Every term carries `origin` and `use`.**

Origins (trust-at-face-value descending):
`durable_handle`, `manifest_key`, `explicit_seed`, `local_shape`, `file_path`, `heading`, `code_symbol`, `json_key`, `yaml_key`, `ref_neighborhood`, `caution`, `exploratory`, `noise`.

Uses:
`locate`, `pressure`, `hydrate`, `neighbor_only`, `caution`, `exclude`, `exploratory`.

**Pairing rule (load-bearing)**: Generic terms (`domain`, `estate`, `site`, `runtime`, `state`, `handler`, `router`, `agent`, `surface`, `principal`) are **weak alone**. Tag them `origin: exploratory`, `use: exploratory` unless paired with explicit seed, durable handle, heading, source-of-truth marker, ref, or local file shape.

When the basket has generic-only terms, surface them in `generic_alone_warnings` for the eventual packet emission. Generic-only terms NEVER produce claim-supporting evidence.

## Stage 5 — Probe Plan

Generate **multiple tactical probes**, not one giant regex. Probe families:

| Family | Use | Command class |
|---|---|---|
| File inventory | Confirm path exists; bound file size | `wc -l`, `stat` |
| Heading | Locate section heading hits | `rg -n '^#+.*<term>'` |
| Explicit seed | Exact-match grep | `rg -F '<seed>'` |
| Durable handle | Exact-match for registered IDs | `rg -F '<handle>'` |
| Caution | Per-hit verified for ambiguous terms | `rg -n '<caution>'` then per-hit chunk read |
| Reference/backlink | Find references TO confirmed handle | `rg -F '<handle>'` excluding origin file |
| Source-of-truth phrase | Locate authoritative-claim language | `rg -i 'authoritative|source of truth'` |
| Code symbol | Definition locator | `git grep -n 'def <symbol>\|class <symbol>'` |
| JSON/YAML key | Structured-file targets | `jq '.. \| objects \| keys[]?' <file>` |
| Temporal/provenance | tic/timestamp markers | `rg 'tic[ -]?<N>'` on audit dir |

Each probe record:

```yaml
probe_id: rtch_probe_<n>
family: <family>
purpose: <one sentence>
input_terms: [<term>, ...]
target_set: [<path>, ...]
expected_signal: <description>
limitation: <known caveat>
claim_authority: weak | source-bearing | claim-supporting
```

Cost-discovery dry-run before any probe with target_set >50 files:

```bash
find <zone> -name '*<pattern>*' | wc -l
```

If file_count > 100 OR total_lines > 50000, fanout level must be `wide` AND probe must be exploratory-only.

## Stage 6 — Hydration

Hydrate **only bounded source chunks** unless full-file is justified by intake (file ≤200 lines OR known_target ≤500 lines AND fanout ≠ wide).

**Use file-access-discipline as execution primitive**:

1. `wc -l <path>` — bound the file
2. `rg -n '<term>' <path>` — locate target line
3. Read tool with `offset: target_line - 20`, `limit: 40` — bounded chunk

Each chunk record:

```yaml
chunk_id: rtch_chunk_<n>
path: <abs_path>
line_range: L<start>-L<end>
why_included: <which probe/origin/term selected this chunk>
term_or_shape: <the structural signal that found it>
confidence_class: hit | weak_hit | source_bearing_hit | hydrated_evidence | claim_supporting | neighbor_only | caution_only
limitation: <what this chunk does NOT support>
next_re_entry_command: Read <path> with offset=<n> limit=<m>
```

**Discipline**:
- Do not summarize away source contact.
- Do not claim more than the chunk supports.
- Do not infer doctrine from grep hits — doctrine status comes from federation invariant inscription, not from grep.

## Stage 7 — Evidence Packet

Emit an agent-ready packet with full provenance. **Mandatory fields**:

- `unresolved_questions` — cardinality > 0 (federation KI: complexity preservation requires schema-level enforcement)
- `generic_alone_warnings` — surface generic-term hits even if they were not claim-supporting
- `halting_reason` — `enough_evidence_definition_satisfied` OR `budget_exhausted` OR `no_signal_at_normal_fanout`
- `skipped_surfaces` — list with reason; silent omission is forbidden (federation KI: do not hide skipped/truncated surfaces)

Packet schema:

```yaml
packet_id: rtch_packet_<intake_hash>
generated_at: <ISO timestamp>
generated_at_tic: <tic>
intake: <full intake>
zone_descriptor: <full zone descriptor>
candidate_basket: <full basket>
probe_plan: <full plan with executed outputs inline>
hydrated_chunks: [<chunk>, ...]
selected_surfaces: [<path>, ...]
skipped_surfaces: [{path, reason}, ...]
unresolved_questions: [<one>, <two>, ...]   # min cardinality > 0
caution_map: [{path, flag, note}, ...]
next_legal_probes: [<probe_record>, ...]
generic_alone_warnings: [<warning>, ...]
fanout_level_used: <level>
halting_reason: <reason>
```

**With `--persist`**: write packet to `audit-logs/rtch/packets/<packet_id>.yaml` via atomic-append write hygiene.

## Stage 8 — Packaging Handoff (Optional)

If `--handoff-to-consolidate` set, hand `packet.selected_surfaces` to `/consolidate` as `--targets`. /consolidate dump's header gets `rtch_packet_id` for provenance.

The handoff is OPTIONAL — many consumers read the hydrated chunks directly and never need a packaged dump.

## Hard Holds (apply to every invocation)

1. Do not mutate source files. Read-only by default.
2. Do not rewrite /consolidate. Compose, don't replace.
3. Do not claim semantic certainty from grep hits. Confidence class enforces what each hit supports.
4. Do not promote doctrine from tactical hydration alone. Doctrine routes through /review.
5. Do not use vector DB assumptions. Federation prohibits at federation rung.
6. Do not read full growing files blindly. Bounded chunks per file-access-discipline.
7. Do not hide skipped/truncated surfaces. Every skip enumerated in packet.
8. Do not collapse packaging and discovery into one confidence claim.

## Confidence Classes (Stage 6 hydration tags)

| Class | Supports |
|---|---|
| `hit` | Locates a candidate; supports nothing further |
| `weak_hit` | Generic-term hit without stronger pairing — surfaces in generic_alone_warnings |
| `source_bearing_hit` | Hit on durable_handle/explicit_seed/file_path/heading/etc — supports "this term anchors here" |
| `hydrated_evidence` | Source-bearing hit + bounded chunk read — supports content claims bounded by chunk's line range |
| `claim_supporting` | Hydrated_evidence on durable_handle/explicit_seed/manifest_key from source-of-truth file — supports content claims |
| `neighbor_only` | Hit at neighbor_only surface — supports adjacency claims, not target claims |
| `caution_only` | Hit on caution term — supports nothing without explicit consumer judgment |

## Fanout Rules (Stage 5 plan budget)

| Level | Use when | Constraints |
|---|---|---|
| `conservative` | High mutation risk OR doctrine claim_evidence target | Max 5 probes; only durable/explicit/path/heading/code/json/yaml/manifest origins; no exploratory claim-support |
| `normal` | Read-only or low-mutation; any profile | Max 12 probes; exploratory permitted but tagged exploratory_evidence |
| `wide` | Read-only AND vague_intent OR migration discovery OR drift investigation | Max 25 probes; cost-discovery dry-run mandatory for >50-file probes; exploratory hits → unresolved_questions |

## Validation Examples

See binder §10 for five worked examples:
1. "Find topology/domain/estate surfaces"
2. "Prepare context for a review docket"
3. "Hydrate runtime evidence for a code path"
4. "Find source-of-truth manifest surfaces"
5. "Discover likely surfaces from vague intent"

## Output Format

Default: emit the packet as a structured YAML/JSON in conversation. The Architect or consumer reads it directly.

With `--persist`: also write to `audit-logs/rtch/packets/<packet_id>.yaml`.

With `--handoff-to-consolidate`: invoke `/consolidate` with `--targets <selected_surfaces>` and emit both the packet AND the dump path.

## Rollout Notes

- This is a **new lane**, not a /consolidate rewrite. /consolidate stays as the packaging neighbor.
- Phase 1 (binder + skill scaffold) lands at tic 223. Phases 2-7 gated on Architect review of binder.
- Phase 6 validation against 3 real targets (per binder) is the doctrine-promotion gate; do not promote based on Phase 1 alone.
- For Phase 1 manual-discipline use, the agent should reference the binder's command templates (binder §6) for concrete shell-equivalent forms.
- When confused about whether to use RTCH or /consolidate: if you don't know which files to read, RTCH first; if you know which files but need them packaged, /consolidate directly.

## Lineage / Cross-Reference

- Federation KI: vector DB prohibition (§2 non-goals), authoritative-set readers, terminal-state valve, file-access-discipline, output anomaly differential verification, complexity preservation, probe-first discipline, lane separation, bounded-delegation default-mask.
- CGG doctrine: queue/state/stack distinction (Architect-named tic 222, productized via queue_state_compile.py compile lane).
- Composes with: `/consolidate`, `cgg-runtime/reference/file-access-discipline.md`, `cgg-runtime/scripts/lib/load_doctrine_chain.py`, `cgg-runtime/scripts/zone_root.py`, `cgg-runtime/scripts/lib/atomic_append.py`, `audit-logs/cprs/queue_state_compile.py` (analogy).
- Authority status: design lane, not doctrine. Routing decision deferred to Phase 7.
