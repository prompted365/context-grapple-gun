# Context Grapple Gun — Constitution Ledger

> **Role:** Layer-1 verbatim preservation of the CGG domain's 155 governance invariants, dehydrated from `CLAUDE.md` at tic 314 under the /review-314 freeze (Architect verdict tic 313). The compact `CLAUDE.md` root carries a one-line summary + pointer per invariant; full verbatim bodies live here.
>
> **Schema:** each entry = `## Heading` + `<a id>` anchor + a `ledger-tags` comment (`authority_class` is a multi-axis TAG VALUE, not a file — per federation KI *Cluster taxonomy belongs in ledger data as multi-axis tags, not single-spine document structure*) + the body **verbatim** from the pre-dehydration `CLAUDE.md` snapshot.
>
> **Verification:** every body in this file is byte-identical to its source section (cgg-dehydrate.py format-aware self-check + dehydration-verifier.py set-diff/anchor checks, tic 314).

---

## Epistemic Volatility Notice
<a id="epistemic-volatility-notice"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Claude Code hook format, plugin manifest schema, and install semantics are **externally versioned by Anthropic**. Treat as a volatile contract surface. Do not promote session-inferred schema understanding to doctrine without validating against current docs/schema.

All schema-specific sections below (Hook Format, Plugin Hooks, etc.) reflect the format as of the last validated check. They may become stale when Claude Code updates.

<!-- promoted from CogPR-15 (tic 9→11). Refines CogPR-1 and CogPR-4 by version-banding them. Source: tic-8 post-session analysis. -->

---

## Volatile-Schema Validation Discipline (Probe-Before-Bind)
<a id="volatile-schema-validation-discipline-probe-before-bind"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

The prevention complement to Epistemic Volatility Notice. When adopting any externally-versioned Claude Code primitive (hook format, plugin manifest field, settings.json field, skill schema field, agent schema field) on a name-only basis — i.e., the primitive appears in a CHANGELOG, release notes, or feature announcement but its runtime shape is not confirmed against the published schema or a live probe — **DO NOT bind any apply path until the shape is runtime-confirmed**. Three valid schema states gate the adoption surface: **(A)** shape published in current schema → safe to inscribe apply path; **(B)** shape named in changelog but absent from current schema → probe live runtime OR defer, do NOT inscribe apply path; **(C)** shape never named publicly (only in changelog text) → defer until next release whose example demonstrates the shape. Any adoption proposal that references an externally-versioned primitive MUST surface the schema-confirmation state explicitly. Composes with federation `Receipt-Discipline-over-Excitement-Velocity` (probe-before-bind IS receipt-discipline at the adoption boundary), with `Cross-File Pointer Integrity Verification` (count references against definitions before binding), and with `Generator-vs-Local-Repair Gap` (template-side validation precedes apply-site inscription).

<!-- promoted from cpr_volatile_schema_validation_discipline_for_externally_versioned_primitives_tic270 (tic 270→272). Refines Epistemic Volatility Notice by naming the prevention mechanism. Source: tic 270 hard_deny .136 schema probe + plugins-reference dependencies field probe — both surfaced ambiguous CHANGELOG shapes that claude-code-guide validation correctly refused to bind. Architect explicit framing at tic 270 ("the 'autoMode.hard_deny named in changelog but absent from public schema' catch means the probe is behaving correctly: no mutation until the shape is runtime-confirmed. That should become a general rule for any name-only primitive from external changelogs.") Same-tic n=2 (hard_deny + plugin manifest); cross-tic n=4+ with Epistemic Volatility Notice exercise history (hook format multi-rev, plugin manifest .143 enforcement, install semantics across releases). Band: COGNITIVE. -->

---

## Hook Format Requirement (Current)
<a id="hook-format-requirement-current"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

The hook format has changed multiple times. The **current** format requires:

1. Each event contains an array of **matcher groups**
2. Each matcher group has an optional `matcher` (regex string) and a `hooks` array
3. `matcher` is a **regex string** matching tool names (e.g. `"Bash"`, `"Edit|Write"`)
4. For match-all: **omit `matcher` entirely**, or use `"*"`
5. `"matcher": {}` (object) is **invalid** in current versions

**Correct format (match-all — omit matcher):**
```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "path/to/hook.sh"
          }
        ]
      }
    ]
  }
}
```

**Correct format (filtered — regex string matcher):**
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "path/to/hook.sh"
          }
        ]
      }
    ]
  }
}
```

**Broken formats (do NOT use):**
- `{"type":"command","command":"..."}` directly in event array (pre-2.1.58 flat format)
- `{"matcher":{},"hooks":[...]}` with object matcher (pre-2.1.72 format)

Reference: [Hooks docs](https://code.claude.com/docs/en/hooks) | [Settings schema](https://json.schemastore.org/claude-code-settings.json)

Downstream surfaces (INSTALL.md, academy guide, init-governance SKILL.md) updated to current format at tic 2.

### Hook types available

- `"type": "command"` — runs a shell command, receives JSON on stdin
- `"type": "http"` — POSTs JSON to a URL endpoint (added 2.1.63)

### CGG-relevant hook events (2.1.69+)

- `InstructionsLoaded` — fires when CLAUDE.md or `.claude/rules/*.md` loaded into context
- `TeammateIdle` / `TaskCompleted` — support `{"continue": false}` to stop teammates
- Hook events now include `agent_id` and `agent_type` fields

### Other capabilities

- `${CLAUDE_SKILL_DIR}` — skills can reference their own directory (2.1.69)
- `/reload-plugins` — activate plugin changes without restart (2.1.69)
- Shared project configs across worktrees (2.1.63)

### Re-validated against 2.1.185 (tic 485 /review)

- Matcher-group array format (optional regex `matcher` + `hooks[]`) **unchanged** and confirmed honored — the running orchestrator booted through it. All registered events recognized by the 2.1.185 binary string table: SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PreCompact, **PostCompact**, SessionEnd, SubagentStart.
- Hook **types** now include `prompt` / `agent` / `mcp` beyond `command` / `http` — a hook can invoke a prompt, a subagent, or an MCP tool, not only a shell command.
- ~20+ events available (e.g. PostToolUseFailure, PermissionRequest/Denied, UserPromptExpansion, Stop/StopFailure, PostToolBatch, SubagentStop, Elicitation/ElicitationResult, Setup, CwdChanged, FileChanged, ConfigChange, WorktreeCreate/Remove, TaskCreated/Completed).
- The tool surface is now **lazy/deferred** — many tools load on demand via ToolSearch rather than being present upfront; capability-probing must check the deferred surface, not only the base tool set.
- `hookSpecificOutput.additionalContext` injection still holds (live-proven; not detailed in the published schema — runtime is ground truth). Probe-surface hierarchy: binary string-table + live-boot > published schema/docs > changelog — see [`#harness-agnostic-is-verified-against-runtime-ground-truth-not-lagging-published-schema`](#harness-agnostic-is-verified-against-runtime-ground-truth-not-lagging-published-schema). <!-- currency C1, tic 485 /review -->

<!-- promoted from CogPR-1 (tic 1), updated tic 2 after second format break. Source: ~/.claude/projects/-Users-breydentaylor-canonical/memory/MEMORY.md -->

---

## Plugin Hook Registration
<a id="plugin-hook-registration"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Plugins must register hooks in `hooks/hooks.json` at the plugin root — listing hooks in `plugin.json` components alone is insufficient. Use `${CLAUDE_PLUGIN_ROOT}` to reference scripts within the plugin directory.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/posttool-microscan.sh"
          }
        ]
      }
    ]
  }
}
```

Reference: [Plugin docs](https://code.claude.com/docs/en/plugins)

<!-- promoted from CogPR-4 (tic 3→5). Source: code.claude.com/docs/en/plugins. Validated by hooks/hooks.json creation. -->

---

## Agent Tool (formerly Task)
<a id="agent-tool-formerly-task"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

The `Task` tool was renamed to `Agent` in Claude Code 2.1.63. All CGG agent frontmatter must use `Agent`, not `Task`.

- **Frontmatter**: `tools: Read, Grep, Glob, Agent, Bash`
- **Spawn restriction**: `Agent(subagent-name)` restricts which subagents can be spawned
- The `Task` alias may still work but should not be relied upon
- **Re tic 485 (2.1.185):** the name `Task` is now **RE-USED** for task-management tools (`TaskCreate` / `TaskList` / `TaskGet` / `TaskUpdate` / `TaskStop` / `TaskOutput`) — a feature **distinct from** `Agent` (subagent spawn). The 2.1.63 Task→Agent rename still stands; the name-reuse is a separate later development. Agent frontmatter spawn capability = `Agent`. Without this note the "Task renamed to Agent" line reads as a contradiction against current docs (which describe `Agent` as the subagent tool and `Task*` as task-management). <!-- currency C2, tic 485 /review -->

<!-- promoted from CogPR-5 (tic 3→5). Source: code.claude.com/docs/en/sub-agents. Applied to mogul.md at f26f21b. -->

---

## JSONL Atomic Writes (PRIMITIVE)
<a id="jsonl-atomic-writes-primitive"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

All JSONL append-only files (`audit-logs/**/*.jsonl`) must use atomic append to prevent corruption from concurrent writers (hooks, session-start, Mogul cycles).

**Required pattern**: write to temp file, then atomic rename/append — never direct `>>` append from concurrent processes.

- Scripts: use `scripts/lib/atomic-append.sh`
- Python: use `scripts/lib/atomic_append.py`
- All 10 JSONL-writing hooks/scripts have been patched to use these libraries

**Failure mode**: concurrent session-start hooks interleaving JSON lines, producing invalid JSONL. Observed at tic 1 and tic 4 on `mandates/history/*.jsonl`.

<!-- promoted from CogPR-8 (tic 4→5). Band: PRIMITIVE. Source: audit-logs/mogul/mandates/history/2026-03-08.jsonl corruption incident. -->

---

## Runtime Sync Parity Verification
<a id="runtime-sync-parity-verification"></a>
<!-- ledger-tags: authority_class=sync_and_install_parity | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Source-repo correctness does not imply runtime correctness. Hook-invoked scripts resolve from the **installed** location (`~/.claude/cgg-runtime/scripts/`), not from the canonical source repo. A fix committed to the source repo has no effect until the installed copy is synced and verified identical.

**Required sequence** after modifying any hook-invoked script:
1. Commit to source repo (`canonical_developer/context-grapple-gun/`)
2. Copy to installed location (`~/.claude/cgg-runtime/scripts/` or `~/.claude/hooks/`)
3. `diff` source and installed — must be identical
4. Verify hook resolution path reaches the correct file (check `resolve_script` candidates)

**Failure mode**: `inbox-envelope.py` was patched with signal dedup in the source repo but the installed copy at `~/.claude/` lacked the fix. Every SessionStart re-emitted 571 attention-debt signals because the executing script had no dedup guard. The source repo was correct; the runtime was not. Three sessions of cleanup failed to hold because the wrong script kept running.

**Registry is the inbox source of truth, not files**: `detect_stale()` reads from `inbox-registry.json`, not from WAIT files on disk. Deleting WAIT files without archiving registry entries leaves phantom state that hooks re-detect as stale.

<!-- promoted from CogPR-65 runtime-parity finding (tic 91). Band: COGNITIVE. Source: three-layer containment — trigger manifest + registry purge + script sync. Evidence: 571 phantom signals per session, 3 sessions of failed cleanup before root cause identified. -->

- **Runtime-Invokable Scripts Must Register in Sync Manifest** — any script installed to `~/.claude/` that is invoked by hooks or other runtime machinery must appear in `sync-manifest.json` with the canonical source path. Scripts absent from the manifest are orphaned at install time — they exist at runtime but sync-parity checks cannot track them, creating a silent divergence surface. If a hook calls a script not listed in the manifest, sync-verify will not re-verify that script's byte-identity post-update.

<!-- promoted from cpr_biome_trust_scripts_absent_from_sync_manifest_tic170 (tic 171→172). Source: session:visitor-phase1-sync-audit. -->

- **Installed-Only Orphan Files** — files present in the installed location (`~/.claude/`) but absent from both the canonical source repo and `sync-manifest.json` are structural orphans. They persist across sync cycles without re-verification or removal. Detection requires explicit diff: canonical repo + manifest contents vs. installed filesystem. A single untracked installed file can silently persist through multiple purge cycles if no removal mechanism is triggered.

<!-- promoted from CogPR-185 (tic 172→172). Source: session:sync-verify-tic172. -->

---

## Self-Locating Artifact Test Isolation
<a id="self-locating-artifact-test-isolation"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | born_tic=365 | promoted_tic=366 -->

A self-locating runtime artifact — one that resolves its operating root by walking up from its own file location (`Path(__file__)` → marker search, e.g. a hook's `resolve_zone_root` walking for `.ticzone`) — **cannot be acceptance-tested in-tree**. An acceptance test that invokes the artifact at its source path resolves the **real** zone (because the source lives inside that zone), not the test's temp zone — so cwd/env-fallback cases never exercise and the test silently mutates production state (audit logs, seen-files, real subprocess side effects). Isolation requires copying the artifact **out of tree** into a temp dir whose only `.ticzone` ancestor is the temp fixture, so the resolver's marker-walk terminates at the fixture. The in-tree run is not a milder version of the test — it exercises a different zone.

**Why distinct (non-derivability):** This is the **test-time inverse** of *Runtime Sync Parity Verification* ("Source-repo correctness does not imply runtime correctness") — that invariant governs *which copy runs* (installed vs source); this governs *which zone the artifact mutates during its own test*. It is a sibling, not a child, of the *Presence/Observation Fallacy Guard* watcher-scope clause — that governs *judgment* scope ("declare which zone you judge before judging"); this governs *mutation* scope ("a self-locating mutator's `__file__` decides which surface it writes"). Self-location is the same property that makes the artifact robust in production (fires correctly from source OR installed copy) AND un-isolatable in-tree: one mechanism, build-view vs test-view.

**Evidence:** Building the cadence plan-hook hardening (tic 365), the first acceptance test fired `cadence-plan-submit.py` at its canonical source path; `resolve_zone_root` walked `HOOK_DIR` parents, found canonical's `.ticzone` first, and every temp-zone fire resolved real-canonical — appending 7 polluting events to the real `cadence-plan-submit.jsonl` and running tdelta/git-cycle/rebru. Re-test with the hook copied to `/tmp/zone/hooks/` (temp `.ticzone` the only ancestor) resolved the temp zone and passed all 9 checks, including the cwd-fallback and fail-closed cases the in-tree run structurally could not reach.

<!-- promoted from cpr_self_locating_artifact_test_isolation_tic365 (born tic 365, /review 366). Band: COGNITIVE. Source: cadence plan-hook hardening build. Verdict: PROMOTE (Architect-gated). Non-derivability resolved: distinct test-isolation discipline — test-time inverse of install-parity; mutation-scope sibling of watcher-scope. -->

**Production-cwd-clobber refinement (tic 505 — the runtime-run complement).** The test-isolation footgun above has a *production* twin: a self-locating GENERATOR whose scan root **defaults to cwd** (`io_map.py build`, `--root` defaulting to the current directory) does not merely leak fixtures under test — run from the **wrong cwd in production** it SILENTLY CLOBBERS its full output to a syntactically-valid but semantically-EMPTY artifact (tic 504: io-map.json 8769 edges → 0 edges, "1 scripts · 0 edges"), passing every "did it run?" / exit-code check; only a CONTENT-cardinality check catches it. The corrector who re-runs such a generator INHERITS THE VERIFICATION OBLIGATION (*the-corrector-inherits-the-verification-obligation*): diff-stat / row-count / edge-count the regenerated artifact against the prior known-good BEFORE trusting it — a regen that DELETES most of the file is the tell. Fix: pass the explicit root (`--root <federation-root>`); durable guard: spot-check output cardinality, never the exit code (*report-generators-must-spot-check-output-against-source-data*). **Lock line:** *a self-locating generator run from the wrong root produces a valid-but-empty clobber, not an error — measure the artifact's cardinality, never the run's exit code.*

<!-- REFINED tic 505 (production-cwd-clobber complement) from cpr_self_locating_generator_run_from_wrong_cwd_silently_clobbers_corrector_inherits_verification_tic504 (PROMOTE-as-refinement, /review 505, Architect-gated). Derivable composition of self-locating-artifact-test-isolation (test-time) + the-corrector-inherits-the-verification-obligation + report-generators-must-spot-check — recorded as a refinement edge (NOT a net-new parent; SKIP≠DISCARD) so it loads where self-locating generators run in production. Net-new sliver: the PRODUCTION-run cwd-clobber manifestation (valid-but-semantically-empty, exit-0). LIVE-CONFORMED this very pass — /review 505 passed --project-dir explicitly to cpr-enrichment-scanner + bench-packet-prep BECAUSE of this lesson. Evidence: tic 504 harpoon arc — io_map.py build from audit-logs/governance clobbered io-map.json (git diff 67322 deletions); caught via git diff --stat, restored, re-ran --root /Users/breydentaylor/canonical → 1115 scripts / 8922 edges. Band: PRIMITIVE. signer ent_homeskillet-c48 (claude-opus-4-8). -->

---

## Cycle-Based Windows in Mixed-Frequency Event Streams
<a id="cycle-based-windows-in-mixed-frequency-event-streams"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When multiple event streams operate at different frequencies (e.g., governance tics at ~1 per hour, biome cycles at 50 per minute during simulation), windows for analysis must anchor to a common reference clock and explicitly specify frequency-relative boundaries. A "last 10 cycles" query is ambiguous: last 10 tics, last 10 biome cycles, or last 10 of the slowest-clock? Use explicit window syntax: `window_type: "tic", window_size: 10, anchor_tic: 172` for federation-scoped windows. For domain-local simulation queries, declare the window against the simulation clock with explicit cycle counter boundaries. Silent frequency-mismatch produces off-by-one results in cycle-based aggregations.

<!-- promoted from cpr_1c573c6a1002deba (tic 171→172). Source: session:event-stream-analysis-tic170. Band: COGNITIVE. -->

---

## Signal ID Determinism
<a id="signal-id-determinism"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Signal IDs must be deterministic and condition-stable — derived from the condition being signaled (entity, state, source), not from emission timestamp or session ID. A signal for the same condition across poll cycles must resolve to the same ID so that dedup infrastructure can suppress duplicates.

**Pattern**: Non-deterministic IDs (timestamp-suffix, session-suffix) cause the same condition to appear as N distinct signals per cycle, flooding the manifold. The dedup guard (inbox-envelope.py) is a runtime fix; this rule prevents the class of error at the emitter.

**Constraint**: Signal manifold integrity depends on ID stability — without it, the manifold's active count becomes meaningless noise. The 2305-duplicate incident at tic 91-94 demonstrated that a single non-deterministic emitter can overwhelm the entire signal surface.

**Evidence**: 1150 active WAIT signals from 8 condition-stable IDs each emitted 100+ times (2026-03-15.jsonl). 6 consecutive Mogul audit cycles confirmed. Tic-91 containment fixed symptoms; this rule prevents recurrence.

<!-- promoted from CogPR-66 (tic 94→100). Source: audit-logs/mogul/runs/tic-94-20260316T005800Z-run.json. Evidence: 2305-duplicate incident at tic 91-94, inbox-envelope.py dedup guard, 1150 active WAIT signals with 8 deterministic IDs. -->

---

## Review Execution Delegation
<a id="review-execution-delegation"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

After `/review` docket is approved, dispatch execution to a `review-execute` subordinate agent — never execute promotions inline in the interactive path.

**Flow:**
1. Present the docket (judgment) → human approves
2. Spawn `review-execute` agent (background, `subagent_type: general-purpose`) with the full verdict table
3. Report completion in one line when notified

**Dispatch payload:** approved verdict table + file targets + review_tic number. The agent reads MEMORY.md for lesson text, writes promoted sections, updates `queue.jsonl` and MEMORY.md metadata. `queue.jsonl` update is the completion gate.

**Fallback:** If `review-execute.md` agent spec is unavailable, spawn a generic background agent with the same instructions.

<!-- promoted from CogPR-9 (tic 5→6). Source: session observation — review-execute.md agent spec at cgg-runtime/agents/review-execute.md. -->

---

## Plugin Declaration Surface (CGG-Specific)
<a id="plugin-declaration-surface-cgg-specific"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

CGG 4.0.0 demonstrated that component declarations placed in proprietary plugin.json fields (`components`, `install`, `claude_code`) did not register and were replaced in 4.0.1 by marketplace-based declaration. For this repo, the supported fix was `marketplace.json` + `strict: false` plus marketplace-based install flow.

This is a CGG-scope declaration-surface lesson, not federation law. The self-hosting marketplace pattern is the validated install mechanism for plugins with non-standard component paths.

<!-- promoted from CogPR-13 (tic 8→11, arena-refined). Supersedes CogPR-14. Source: npx context-grapple-gun install failure → fix at lib/installer.mjs + .claude-plugin/marketplace.json. -->

---

## npm Distribution Wrapper
<a id="npm-distribution-wrapper"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

CGG is distributed via npm as `context-grapple-gun`. The npm package is a zero-dep CLI wrapper — `npx context-grapple-gun install` clones the repo and registers the plugin via the self-hosting marketplace pattern. The runtime stays in the plugin; npm orchestrates install only.

- Published: 4.0.0 (initial), 4.0.1 (marketplace fix)
- npm auth requires granular access token with publish scope

<!-- promoted from CogPR-11 (tic 7→11). Source: session planning — user request for npm publishable package. -->

---

## Subagent Delegation — Schema Contracts
<a id="subagent-delegation-schema-contracts"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When delegating hook creation or script writing to subagents, include the target script's JSON output schema in the prompt. Subagents that parse another script's output without knowing the schema will write incorrect field paths.

**Failure mode**: Agent wrote `d.get('drifted',0)` but runtime-sync.py nests under `summary.drifted`.

<!-- promoted from CogPR-12 (tic 8→11). Source: canonical/.claude/hooks/federation-sync-check.sh:37. -->

- **Headless subagent model capacity must exceed largest file the spec touches** — When a headless subagent definition specifies operations on growing files (CLAUDE.md, MEMORY.md, queue.jsonl), the agent's chosen model must have context capacity sufficient for the largest file the spec claims to manipulate. If model and file size diverge silently — model context shrinks relative to file growth, OR file grows beyond model context — the spec fails not by erroring but by truncate-fallback: the agent reads what it can fit, then performs a degraded operation that LOOKS like the spec but drops content past its read window. Two-layer protection required: **Layer 1 (model capacity)** — choose a model whose context capacity exceeds the largest file the spec touches, with margin for file growth across many tics. **Layer 2 (chunked-read methodology)** — never read entire growing files just to find an insert point. Use chunked-read-around-target-insert: wc-then-grep-then-narrow-window-then-edit. This decouples model capacity from file size and is the higher-leverage protection because it works regardless of model choice. Both layers must be enforced for any agent that operates on doctrine-class files. (Validated: tic 207 review-execute used model haiku spec'd to read-modify-write entire queue.jsonl (435+ lines, ~50KB+); haiku could not fit; truncated reads; fell back to appending — matched lucky alignment with downstream latest-by-id reads, so system worked, but mismatch was invisible. Fix: model haiku→sonnet + chunked-read mandate inscribed.)

<!-- promoted from cpr_headless_model_file_size_capability_mismatch_tic207 (tic 207→209). Source: tic 207 review-execute queue.jsonl mutation drift. Band: COGNITIVE. -->

---

## Goal-Directive as Ratification Authority for Routine Review Passes
<a id="goal-directive-as-ratification-authority-for-routine-review-passes"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When the Architect sets a /goal directive whose stop condition explicitly names processing-class outcomes (e.g., "all actionable review items are properly evaluated AND processed per governance requirements"), the goal directive itself functions as Architect ratification authority for the enclosed routine verdicts. Holding at an individual ratification gate (e.g., "Ratify this docket?") for routine PROMOTE / PROMOTE-SPEC / ACK-MAINTAIN verdicts within scope violates the goal-condition contract; the gate has already been set by /goal at higher abstraction.

Extends two existing feedback discipline notes — *Own Routine Commits/Messages/CogPR Submissions* (the Architect does not gate routine push/commit/CogPR-submission decisions) and *Don't Gate-Hold; Tranche Stomp* (the Architect is collaborator, not external reviewer; execute tranches; trim where investigated-clear) — from author-side authoring decisions to /review-execution verdict batches.

**Operational form**: when /goal stop condition is set, lobby for inscription via review_hints, present verdict recommendations with rationale, then EXECUTE the recommended docket directly. Only escalate individual ratification calls for items that lie OUTSIDE the goal's scope (e.g., protected-file inscriptions per workflow Safety Rules — those still require explicit Architect gate even under goal directive).

**Composes with**: *Receipt-Discipline-over-Excitement-Velocity* (a /goal directive's gate is a different *kind* of gate than the docket-level ratification gate — Receipt-Discipline still applies to the goal-scoping decision, but executes once the goal is set); *Verdict-Shape KI* (PROMOTE-SPEC defers implementation per workflow — this discipline does not collapse PROMOTE-SPEC into PROMOTE; it preserves verdict-shape discipline within goal-directive execution); *Protected-File Safety Rule* (~/.claude/CLAUDE.md, GLOBAL_INVARIANT-tagged files require their own explicit ratification regardless of /goal directive).

**Falsification**: if the Architect overrides this discipline by explicit retract-of-authority during a /goal-driven /review pass, the discipline contracts; the goal directive's gate-collapse claim was over-extended. Validated tic 272 via stop-hook firing as operational signal at ratification-gate-hold, which corrected the held state to execution.

<!-- promoted from cpr_goal_directive_as_ratification_authority_for_routine_review_passes_tic272 (tic 272→273). Source: /review tic 272 execution under Architect /goal directive; stop-hook fired when ratification gate was held. Band: COGNITIVE. Posture: ENG/DIRECT. -->

---

## Mandate Consumption Discipline
<a id="mandate-consumption-discipline"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

If a cadence mandate exists when a session closes, the session must invoke Mogul or explicitly defer. Mandates generated by cadence hooks but not consumed create governance gap windows — cycles queue up but no scan occurs within the session that owns them.

Three consecutive unexecuted mandates at tics 13-15 demonstrated the structural pattern. The activation fabric now handles consumption, but the obligation to invoke or defer is doctrinal.

<!-- promoted from CogPR-26 (tic 16→19). Source: 3 consecutive unexecuted mandates at tics 13, 14, 15. Band: COGNITIVE. -->

---

## Mogul Mandate Execution Depth Scaling
<a id="mogul-mandate-execution-depth-scaling"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Mogul mandate execution depth must scale to estate state at mandate creation time. The mandate metadata must include an estate state snapshot (`queue_pending`, `signals_active`, `hazards_open`, `tics_since_last_review`, `tics_since_last_conformation`) so that Mogul can match a run profile at execution time without re-reading the full estate.

Run profiles:
- **verification** (all-clear): compact receipt, no deep scan
- **active** (pending CPRs or recent arena output): targeted assessment of pending items
- **hazard** (open hazards or active signals): full drift check
- **post-review** (inscription verify only): confirm promoted lessons landed

Running identical full cycles regardless of estate state wastes cognitive resources and inflates run artifact noise. Estate-aware depth is a Mogul mandate behavior constraint only — not a general strategic pivot doctrine and not a claim about all federation bottlenecks.

<!-- promoted from CogPR-47 (tic 32→40). Source: PAT-T32-005 + PAT-T36-003 — 5-instance recurrence (tics 26, 32, 34, 36, 39) + tournament cross-bracket convergence (3 agents, 2 brackets). Operator scope note: estate-aware Mogul mandate depth only. Band: COGNITIVE. -->

---

## Mandate Lifecycle Defects
<a id="mandate-lifecycle-defects"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Mandate lifecycle has four structural defects that refine the Mandate Consumption Discipline (CogPR-26) and Mandate Execution Depth Scaling (CogPR-47):

1. **session-restore.sh overwrites without check** — always writes `current.json` without checking existing pending mandates. Lightweight mandates accumulate as durable obligations. **Mitigated**: tic-level idempotency guard added (checks `current.json` tic before emitting). **Fixed** (tic 108): reconcile-first cycle computation — reads previous mandate `tic_context` as primary schedule, modulo as fallback only.
2. **SessionStart recomputes instead of reconciling** — recomputes cadence from tic modulo instead of reconciling with previous mandate `tic_context`. Creates mandate duplication on session restore. **Mitigated**: `trigger-manifest.yaml` idempotency key changed from `mandate_{tic}_{session_id}` to `mandate_{tic}` with `first_wins` policy. **Fixed** (tic 108): collapsed into reconcile-first in session-restore.sh.
3. **No concurrency guard on inline Mogul spawn** — the review skill can inline-spawn Mogul without checking whether a loop-backed Mogul is already active. **Fixed** (tic 108): concurrency guard added to `/review` SKILL.md steps 5.5 and 8.5 — checks `current.json` status before writing mandates. Race guard added to cgg-gate.sh inline consumption.
4. **Cross-mandate write race on current.json during runner mid-cycle** — when mogul-runner is mid-execution on a mandate AND /cadence emits a new mandate to `current.json` before the runner's artifact verification step runs, the verifier reads `$MANDATE_FILE` with the new mandate's mtime as its temporal reference, causing `find -newer $MANDATE_FILE` to false-negative legitimately-produced cycle artifacts written before the new mandate's mtime. The runner writes `status: failed` to `current.json`, overwriting the new mandate's pending status with the prior mandate's verifier failure. **Fix candidates (any composition)**: (1) runner snapshots `current.json` at run start, verifier uses snapshot mtime; (2) cadence checks runner status before writing `current.json`; (3) verifier uses mandate's `created_at` ISO timestamp instead of file mtime; (4) lock file around mandate state transitions. **Implementation tranches LANDED at tic 280** (composition of fix candidates 1+2): mogul-runner.sh snapshot-pinning at all 3 verifier clauses with trap-cleanup (CGG `1729e29`); cadence-ops.py `wait_for_runner_quiescence()` helper with 30s timeout / 2s interval / WARN-and-proceed-on-timeout (CGG `fb3158d`). **Production-validation receipt**: first /cadence emission after fix (tic 280→281) reports `runner_wait{waited_s=0.0, runner_was_running=false, runner_final_status=consumed, timed_out=false}` — structural-correctness receipt closed. Natural-contention falsification (/cadence DURING mid-runner; not an already-consumed case) remains pending until the next genuine mid-runner /cadence boundary fires.

**Idempotency key constraint**: The mandate idempotency key must NOT include `session_id` — per-session UUIDs defeat dedup because every session generates a unique ID, making every emission appear novel. The correct granularity is `mandate_{tic}` with `first_wins` policy. Evidence: tic-87 produced 269 inbox messages, 200+ report files, and 328 signal entries from a single-tic runaway caused by `{session_id}` in the key template. **Additional defect (tic 179)**: Session-start auto-mandate logic may merge+expand a manually-written mid-session mandate when session_start fires (e.g., via UserPromptSubmit hook). The merge is non-lossy (cycles absorbed, mandate_id recorded in `merged_from`) but the absorbing mandate runs ALL its cycles. Operator scope expansion: a narrow mid-session mandate may seed a next-session-start-expanded mandate.

<!-- promoted from CogPR-57 (tic 75→80), extended by CogPR-65 (tic 91). Source: external-audit-verified + mandate runaway containment. Refines CogPR-26 (mandate consumption) and CogPR-47 (mandate depth scaling). Band: COGNITIVE. Merged with cpr_ee28b41183d01e30 (tic 179). Extended by cpr_mandate_cross_mandate_write_race_4th_defect_class_tic279 (/review tic 279). Source: tic 279 SessionStart runner-mid-cycle verifier mtime race; mandate history JSONL running_to_failed trace. Implementation tranches: mogul-runner.sh snapshot-pinning + cadence-ops.py runner-status check (next gate). Refined-spec at tic 282 by cpr_cogpr3_race_fix_falsification_validated_in_production_tic280 (production-validation receipt at tic 280→281 /cadence emission: runner_wait clean; structural-correctness closed; natural-contention falsification still pending). Cross-tic n=3: tic 251 N=0 sub-case → tic 279 incident + recovery + CogPR → tic 280 fix landed + first production verification. -->

---

## Promotion Scope Discipline
<a id="promotion-scope-discipline"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Promotion decision is two decisions, not one: (1) is the content valid? (2) what class of doctrine does it belong to? Scope reconciliation must happen before promotion — batch promotion from census evidence is especially prone to scope collapse.

Doctrine class taxonomy:
- **CLAUDE.md** = active implementation doctrine (constraints that shape agent behavior)
- **Memory files** = born truth, structural design, architectural read (reference material, not law)
- **Risk map** = performance hazard doctrine (operational guardrails)

**Failure mode**: Foreground review without scope reconciliation against Mogul analysis caused 5 of 6 CogPRs routed to wrong target at tic 75.

<!-- promoted from CogPR-58 (tic 75→80). Source: operator-correction. Reinforced tier. Band: COGNITIVE. -->

---

## Cadence Downbeat Enforcement
<a id="cadence-downbeat-enforcement"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Cadence downbeat must enforce a strict sequence: emit tic event, then write conformation, before the tic counter advances. The tic count hook must count only non-ignored tic events — counting all tic events including `count_mode: "ignored"` produces phantom ticks that desynchronize the tic counter from the conformation history.

12+ missing conformations across governance history trace to this root cause. The downbeat sequence is: (1) emit tic event with `count_mode: "counted"`, (2) write conformation snapshot, (3) advance counter. Any other ordering or omission breaks the tic-conformation invariant.

<!-- promoted from CogPR-43 (tic 27→32). Source: PAT-T31-002 pattern mining + HAZARD-T31-A runtime drift check. 5+ recurrences, 2 consecutive hazards. Band: COGNITIVE. -->

---

## Lead Context as Binding Constraint
<a id="lead-context-as-binding-constraint"></a>
<!-- ledger-tags: authority_class=subagent_and_swarm_delegation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Lead context accumulation — not advocate turn count — is the binding budget constraint in governed arenas. The lead receives ALL advocate outputs: N advocates × M turns each = N×M messages accumulating in lead context. Advocate budgets are local (bounded per-agent), but lead context is global (accumulates across all agents).

The routing function must check lead context ceiling across all regimes before spawning.

<!-- promoted from CogPR-32 (tic 21→22, arena-sourced T3G). All three advocates independently identified this as the binding constraint. Band: COGNITIVE. -->

---

## Coordination Overhead Accounting
<a id="coordination-overhead-accounting"></a>
<!-- ledger-tags: authority_class=subagent_and_swarm_delegation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Coordination overhead (nudges, retries, phase-transition messages) is lead-side cost, not advocate-side cost. Advocate budgets should price reasoning depth only. Conflating coordination with advocacy inflates budget estimates.

This accounting correction changed the LIBERAL regime derivation from 28 to ~22 turns/advocate — coordination overhead was incorrectly counted as advocate budget consumption.

<!-- promoted from CogPR-35 (tic 21→22, arena-sourced T3G). All three advocates independently confirmed this accounting principle. Band: COGNITIVE. -->

---

## Epistemic Triangulation Geometry
<a id="epistemic-triangulation-geometry"></a>
<!-- ledger-tags: authority_class=arena_and_reasoning_geometry | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Epistemic triangulation (coincidence/mechanism/counterfactual) is an effective geometry for hypothesis-testing arenas. Each angle tests a different failure mode of the claim:
- **Coincidence** — could the evidence be explained by chance or confounding?
- **Mechanism** — is there a causal pathway connecting the claim to the evidence?
- **Counterfactual** — what would we expect to observe if the claim were false?

Use this geometry when the arena question is a testable hypothesis rather than a design choice.

<!-- promoted from arena-marketplace-0 (tic 9→25, arena-sourced marketplace-epistemic-triangulation). Process lesson — reinforced confidence tier. Band: COGNITIVE. -->

---

## Governance Label Accuracy
<a id="governance-label-accuracy"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

'Observer-first' is a governance label that systematically understates commitment. If the model includes synchronous pre-action checkpoints at critical boundaries (cost, publish, destroy), the model is 'governed-at-boundaries' and the label should match. Labels shape investment decisions — a mislabeled pattern will be under-resourced where it matters most.

<!-- promoted from CogPR-73 (tic 102→105). Source: arena:triad-fusion-authority-arena — Wildcard Record #5 (semantic downgrade), governance-examiner rebuttal, all agents converged on gates at cost/publish/destroy. Band: COGNITIVE. -->

---

## Same-Model Convergence Discount
<a id="same-model-convergence-discount"></a>
<!-- ledger-tags: authority_class=arena_and_reasoning_geometry | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Same-model agent convergence is weaker than cross-model convergence. Same-substrate agents satisfy incentive independence (opposed mandates) but not epistemic independence (shared priors). Downgrade same-model convergent findings to REINFORCED until validated by implementation evidence.

<!-- promoted from CogPR-76 (tic 102→105). Source: arena:triad-fusion-evidence-rebuttal — same-substrate shared priors observation. Tentative confidence; CGG scope first, federation promotion pending cross-model arena validation. Band: COGNITIVE. -->

<!-- REFINEMENT EDGE (tic 500, /review 500): the cross-model validation this entry awaited is DELIVERED. A blind cross-model strike (strikers C=claude-sonnet-4-6 + D=claude-haiku-4-5 joining the same-model Opus pair A/B) over the 19-KI rehydration corpus reproduced the load-bearing ① flip under ALL FOUR strikers — symptom_01 lands a LIFECYCLE_PERSISTENCE centroid, harpoon off-field (cosine −0.4428) (audit-logs/governance/harpoon-office/shape-rehydration-proof/tic500-crossmodel-strike-receipt.json: candidate_crossmodel_PASS). NET-NEW measurement discipline beyond the parent discount: (a) cross-model agreement is a CENTROID-FAMILY-altitude property, not a specific-item one — the four strikers landed ① on THREE different KIs but the SAME family, so asserting agreement at the specific-item altitude falsely reads PARTIAL where the family-altitude truth is full agreement (measure the claim at the altitude it lives at); (b) per-striker DIVERGENCE becomes the anisotropic Σ of the consensus splat (tight where 4/4 agree, wide where they split), NOT noise to discount; (c) the same-model-convergence-discount is RETIRED AT FAMILY ALTITUDE for this corpus — the flip survives genuinely different model lineages (the discount still applies at the specific-item altitude, where C/D genuinely diverged). HARD BOUNDARY (Architect, /review 500): this is evidence/refinement classification, NOT runtime authorization — no boot-seam injection, no cadence wiring; the shape_field_rehydration primitive stays runtime_authority:none, gated on F2 (corpus-learned taxonomy) + C9 (rung-applicability filter). ACCEPT-AS-REFINEMENT under the shape-field candidate + redundant-scout-medley lens; clusters with cpr_wide_berth_office_holder_dispatch... (office-holder divergence). From cpr_crossmodel_strike_agreement_measured_at_centroid_family_altitude_tic500 (Architect override of the reviewer's DEFER, verdict-batch 5h7c2b/8ufvsf); refinement edge only, no standalone KI. signer ent_homeskillet-c48 (claude-opus-4-8). -->

---

## Concession Cascade Detection
<a id="concession-cascade-detection"></a>
<!-- ledger-tags: authority_class=arena_and_reasoning_geometry | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Evidence-rebuttal concession cascade: when evidence advocate concedes all claims, check for role abandonment vs claim adjustment. Lead must verify empirical evidence perspective survives even when specific evidence base is thin. Concession cascade produces bilateral consensus, not triangulated convergence.

<!-- promoted from CogPR-77 (tic 102→105). Source: arena:triad-fusion-evidence-rebuttal — evidence advocate conceded all claims, bilateral consensus ≠ triangulated convergence. Band: COGNITIVE. -->

---

## Arena Velocity Guard
<a id="arena-velocity-guard"></a>
<!-- ledger-tags: authority_class=arena_and_reasoning_geometry | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When arena convergence happens faster than evidence accumulation, treat the consensus as a hypothesis set, not a decision set. Each consensus point needs an explicit falsification condition. The wildcard strike-down question ('what would the smart-but-wrong version be?') applied to each point before ratification guards against elegant plans nobody can build.

<!-- promoted from CogPR-74 (tic 102→105). Source: arena:triad-fusion-authority-arena — 8 consensus points in 3 phases, Wildcard Records #3 and #8, strike-down question technique. Complements CogPR-33 (convergence timing). Band: COGNITIVE. -->

---

## showClearContextOnPlanAccept Must Be True
<a id="showclearcontextonplanaccept-must-be-true"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

CGG cadence depends on plan-mode context-clear as the session epoch boundary. When false (the default as of Claude Code with 1M context), clear-context options are suppressed in the plan approval menu, replacing them with keep-context variants. This silently breaks the cadence handoff chain (plan approve + clear -> session-restore.sh -> trigger extraction -> assessor spawn). Set `showClearContextOnPlanAccept: true` in `~/.claude/settings.json` for any CGG-governed workspace.

<!-- promoted from CogPR-78 (tic 104→107). Source: binary-analysis-claude-code-2.1.81. Evidence: binary-verified — flag controls first option in plan approval menu, cadence handoff chain restored after setting true. Band: COGNITIVE. -->

---

## Overlap-Frequency Tiering Primitive
<a id="overlap-frequency-tiering-primitive"></a>
<!-- ledger-tags: authority_class=arena_and_reasoning_geometry | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Overlap-frequency tiering is a reusable prioritization primitive for competitive and comparative analysis: features all competitors share = table stakes (necessary but not differentiating), some share = opportunity zone (competitive leverage), one has uniquely = differentiation (strategic advantage). Apply this tiering to any domain where multiple entities are compared across feature sets — SEO landscapes, capability surfaces, vendor assessments. The primitive appeared in 12/20 prompts during harpoon assessment with demonstrated live cross-domain instantiation.

<!-- promoted from CogPR-81 (tic 109→115). Source: arena:harpoon-alventra-seo-assessment — convergent (HARVEST+MINE advocates). Cross-domain applicability demonstrated in SEO, capability, and vendor assessment contexts. Band: COGNITIVE. -->

---

## CATALYZE Advocate Geometry
<a id="catalyze-advocate-geometry"></a>
<!-- ledger-tags: authority_class=arena_and_reasoning_geometry | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Harpoon assessment arenas benefit from a CATALYZE advocate position that argues for higher-leverage constitutional alternatives, replacing binary PASS/NO with phased convergence. The CATALYZE advocate's role: when a harpoon item fails direct adoption, identify what constitutional primitive it could become through transformation. This produces richer assessment output — items are not just accepted or rejected but classified along a spectrum from direct-adopt to constitutional-extract to reject.

<!-- promoted from CogPR-82 (tic 109→115). Source: arena:harpoon-alventra-seo-assessment — reinforced. Process improvement for arena geometry, validated in practice during harpoon assessment. Band: COGNITIVE. -->

---

## Copilot Script Classification (tier_2_adapt)
<a id="copilot-script-classification-tier-2-adapt"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

External prompt systems that require human execution (e.g., "Open Chrome and navigate to...") are most accurately classified as `tier_2_adapt` — copilot scripts, not agent-executable envelopes. The "Open Chrome" pattern is a reliable signal of copilot-script dependency. Assessment should separate pattern value (the reasoning structure may be reusable) from execution mechanism (human-in-the-loop vs agent-executable). This sharpens harpoon assessment by preventing misclassification of human-dependent prompts as directly ingestible automation.

<!-- promoted from CogPR-84 (tic 109→115). Source: arena:harpoon-alventra-seo-assessment — reinforced. Practical operational value for harpoon assessment classification. Band: COGNITIVE. -->

---

## Cross-Rung Orientation (CRX) Arena Geometry
<a id="cross-rung-orientation-crx-arena-geometry"></a>
<!-- ledger-tags: authority_class=arena_and_reasoning_geometry | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

CRX is the 6th arena geometry template, designed for cross-rung and cross-jurisdiction exploration. Structure: triad (domain-level reasoning with opposed advocates) + meta-pair (constitutional emissaries with expansion/constraint polarity) + ecotone synthesis (mechanical derivation from both polarity gates). The meta-pair catches what triads miss — specifically complementary-jurisdictions violations and suppressed emergence. First CRX run produced qualitatively different output from standard governed triangulation. Use CRX geometry when the arena question spans jurisdictional boundaries or rung levels.

Template location: `stage/templates/arenas/cross-rung-orientation/`

<!-- promoted from CogPR-88 (tic 109→115). Source: arena:occ-identity-primitives-crx — reinforced. First run validated qualitative difference from governed triangulation. Meta-pair caught complementary-jurisdictions violations the triad missed. Resolves BEACON_crx_geometry_validated. Band: COGNITIVE. -->

---

## Recursive Meta-Enforcement
<a id="recursive-meta-enforcement"></a>
<!-- ledger-tags: authority_class=arena_and_reasoning_geometry | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Schema-level enforcement of governance requirements can be formally satisfied while substantively violated — a mandatory dissent field satisfied by writing "No dissent." is compliance theater. The response is recursive meta-enforcement: mechanisms watching mechanisms. When a governance schema requires a field (unresolved tensions, dissent, surprise assessment), the enforcement layer must also check whether the field's content is substantively meaningful, not just syntactically present. This applies to any schema-enforced governance requirement and extends concession cascade detection (CogPR-77) from arena-specific to system-wide.

<!-- promoted from CogPR-93 (tic 112→115). Source: arena:occ-epistemic-safeguards-crx — convergent. MECHANIST form-vs-substance analysis + LAWFUL iterative enforcement. Extends CogPR-77 (concession cascade). Resolves BEACON_occ_epistemic_governance_convergence. Band: COGNITIVE. -->

---

## NIH Self-Examination in Adversarial Arenas
<a id="nih-self-examination-in-adversarial-arenas"></a>
<!-- ledger-tags: authority_class=arena_and_reasoning_geometry | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

In governed adversarial arenas, advocates arguing for build-alternative positions (CATALYZE, build-from-scratch, replace-with-custom) must include a mandatory NIH (Not Invented Here) self-examination: an honest numeric self-score (0-10) assessing how much of their advocacy is driven by NIH bias versus genuine gap analysis. Advocates who honestly assess their own failure modes produce genuine convergence; advocates who cannot produce bilateral stalemate. The NIH self-score is the mechanism that releases deadlocked positions into shared territory.

<!-- promoted from CogPR-108 (tic 118→119). Source: arena:harpoon-federation-mount-binder-v2-assessment — reinforced. CATALYZE's 5.5/10 NIH self-score released 3 of 5 gaps from exclusive to shared territory, making consensus partition possible. Band: COGNITIVE. -->

---

## Opposing-Values Geometry for Constitutional Questions
<a id="opposing-values-geometry-for-constitutional-questions"></a>
<!-- ledger-tags: authority_class=arena_and_reasoning_geometry | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Constitutional questions (expansion, restructuring, inscription, authority changes) should use opposing-values arena geometry where advocates hold genuinely different values (e.g., completeness vs coherence vs efficiency), not same-direction geometry where advocates agree on value but differ on approach. Opposing-values geometry produces higher lock-pressure, surfaces absorption capacity concerns, and generates analytical tools (e.g., non-derivability test) that same-direction geometry cannot produce. Same-direction geometry produces low lock-pressure everywhere because advocates agree on valence — method disagreement does not generate the constitutional stress-testing that value disagreement does.

<!-- promoted from CogPR-112 (tic 118→119). Source: arena:harpoon-binder-v2-constitutional-impact — reinforced. Direct empirical comparison: Arena 1 (same-direction) produced low lock-pressure and no analytical tools; Arena 2 (opposing-values) produced the non-derivability test (CogPR-110) and structural reform mandates. Band: COGNITIVE. -->

---

## Post-Hoc Conformation (Anti-Pattern: In-Arena Invariant Scoring)
<a id="post-hoc-conformation-anti-pattern-in-arena-invariant-scoring"></a>
<!-- ledger-tags: authority_class=arena_and_reasoning_geometry | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Do not ask arena advocates to score their positions against invariants during their turns. In-arena invariant scoring distorts advocate reasoning — advocates checklist-optimize against the scoring criteria instead of reasoning naturally from their value positions. The correct design is post-hoc conformation: advocates speak from values without scoring awareness, then an invariant field measurement is applied after advocacy completes. This separation is load-bearing — it preserves the authenticity of advocacy while still capturing invariant alignment data.

<!-- promoted from CogPR-114 (tic 118→119). Source: session:harpoon-binder-vpl-design-tic-118 — reinforced. Arena 1 experimental invariant weight scaffold demonstrated checklist-optimization distortion. VPL spec Phase 6 (post-hoc conformation) is the validated alternative. Band: COGNITIVE. -->

---

## VPL Standard Geometry (Tournament-Lattice)
<a id="vpl-standard-geometry-tournament-lattice"></a>
<!-- ledger-tags: authority_class=arena_and_reasoning_geometry | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Tournament-lattice VPL (Value-Position Lattice) with bracket isolation and wildcard challenge is the standard geometry for federation governance shape questions. The geometry combines three validated principles:

1. **Constitutional actors as advocates** — office holders (Mogul, Crisis Steward, CBUX, Civil Engineer, Ladder Auditor) have natural value centroids from jurisdictional mandates and natural evidence bases from operational data. Using them instead of generic labels produces advocates with authentic stakes.
2. **Value-position fusion** — constitutional actors naturally fuse value-driven and position-driven stances in a single lattice. Their jurisdictional mandates ARE value centroids; their operational data IS positional evidence. VPL achieves what separate arena types cannot.
3. **Wildcard chain coherence challenge** — the wildcard finds composite tensions invisible to bracket-isolated advocates. Every constitutional VPL arena must include a chain coherence wildcard.

Template: `stage/templates/arenas/value-lattice/spec.md`

<!-- promoted from CogPR-116 merged with CogPR-113 + CogPR-115 (tic 118→119). Source: arena:federation-governance-shape-vpl — convergent. Wildcard found 3 composite tensions invisible to 12 bracket documents. Constitutional actors produced office-specific evidence unavailable to generic labels. First VPL run validated the geometry. Band: COGNITIVE. -->

---

## Hook Path Resolution
<a id="hook-path-resolution"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Hook scripts must discover zone root by walking up from the **edited file path**, not from `cwd`. Hooks execute in an arbitrary working directory set by the harness (often `~` or other external paths), not by the project. Using `os.getcwd()` or `$CLAUDE_PROJECT_DIR` as the primary zone root anchor silently fails when cwd is outside the federation tree. The file path (`$CLAUDE_FILE`)is the only reliable anchor to discover zone root via directory traversal.

**Pattern:** Walk up from `$CLAUDE_FILE` looking for `.ticzone` or `audit-logs/`, not from `cwd`.

**Failure mode:** Hook returned silence from `~/`; full output from `canonical/` — same input JSON, different cwd. Zone root resolution from file path walked up correctly in all 4 tests. Existing post-commit-sync.sh had the same latent bug masked by git commit always running from repo dir.

<!-- promoted from CogPR-127 (tic 122→124). Source: session:sync-weigh-hook-tic-121. Zone root resolution validated walking up from file path in all test cases. -->

---

## Session Learning Protocol
<a id="session-learning-protocol"></a>
<!-- ledger-tags: authority_class=memory_and_inscription_hygiene | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When you discover something during a session that constitutes a durable lesson — a friction point resolved, a non-obvious behavior confirmed, a workflow correction — capture it as a CogPR (Cognitive Pull Request).

### Write rule (born truth vs in-force truth)

Write lessons to MEMORY.md by default (born truth). Only write to CLAUDE.md when the lesson IS a law change (in-force truth). If no subsystem MEMORY.md exists, write to the project's auto-memory (`~/.claude/projects/*/memory/MEMORY.md`).

### CogPR format

Write the lesson inline, then add this flag immediately after:

<!-- --agnostic-candidate
  lesson: "one-line lesson summary"
  source_date: "YYYY-MM-DD"
  source: "file:line"
  band: "COGNITIVE"
  motivation_layer: "COGNITIVE"
  subsystem: "relevant_subsystem"
  recommended_scopes:
    - "path/to/broader/CLAUDE.md"
  rationale: "why this is broader than local"
  review_hints: "what to check when evaluating"
  status: "example"
-->

> Set `status: "pending"` on real CogPRs. The template uses `"example"` to avoid false positives in the inline CPR scanner.

### Birth discipline

Never delay birth of a pattern-shaped CogPR on the grounds of maturity. Capture first. Prove later. Promote only when earned.

- If the observation is pattern-shaped (recurring, structural, or contract-level), mint the CogPR immediately at birth tic.
- Maturity governs **promotion**, not **capture**. Losing the hypothesis is system failure; premature promotion is recoverable.
- For external platform contract surfaces (hook schema, plugin manifest, install semantics, marketplace protocol), capture hypotheses immediately — do not legislate from memory when contract validation is available.

### Band budget

| Band | Use for |
|------|---------|
| PRIMITIVE | Safety, data integrity, survival signals |
| COGNITIVE | Learning, discovery, process improvement (default) |
| SOCIAL | Collaboration signals (use sparingly) |
| PRESTIGE | Never. Governance-blocked. |

Run `/cadence` when the session feels long — around 100k tokens is a good heuristic. If context is degrading, `/cadence double-time` does a minimal exit. The `cadence-syncopate` command surface remains valid and supported.

### Experimental arena cadence isolation

Events inside experimental arenas may be recorded, but they do not advance physical cadence by default. Only operative-zone execution advances the physical tic counter.

When cadence is emitted from experimental closeout or other ignored contexts, emit a normal tic event (`type: "tic"`) with:

- `count_mode: "ignored"`
- `count_reason: "<explicit reason>"`
- `domain_counter_before == domain_counter_after`
- `global_counter_before == global_counter_after`

Do not fork the event type. The distinction is counting mode, not event existence. One event model, one scanner, one audit surface.

### Timestamp authority law

If timestamps are not canonical, they must never be used as authoritative ordering fields. Use tic, phase, dependency completion, or explicit operator-metadata labels instead. Canonical progression is determined by counted tic progression, not by wall-clock timestamps.

---

## Doctrine Surface Frontmatter Sweep Methodology
<a id="doctrine-surface-frontmatter-sweep-methodology"></a>
<!-- ledger-tags: authority_class=memory_and_inscription_hygiene | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Doctrine surfaces that accrete >30 specs without frontmatter render uniformly dense to readers (Mogul, ladder-auditor, agents) regardless of whether each spec is active, forward-looking, or dormant. Federation KI overlap (which spec implements which Key Invariant) is unlabeled, creating Authority Vacuum at the doctrine layer. A one-shot mechanical sweep adding `status: active|forward|dormant` + `last_validated_tic: N` + `implements: <federation KI>` frontmatter scales to 70+ files in one Python pass with rule-based heuristic + manual override map. Validated tic 214: 73 AK specs patched (61 active / 9 forward / 3 JSON sidecars); 33 cross-linked to federation KIs. The pattern is reusable for any doctrine surface that has crossed the dense-without-discrimination threshold.

<!-- promoted from CogPR-cpr_doctrine_surface_frontmatter_sweep_methodology_tic214 (tic 214→216). Source: ~.claude/projects/-Users-breydentaylor-canonical/memory/MEMORY.md. -->

For arena reports and other non-canonical surfaces, prefer tic-based closure:
```json
{"source_tic": 9, "completion_tic": 9, "phase_closure": {"context": "complete", ...}}
```
not authoritative-looking wall-clock sequencing (`created_at`, `completed_at`).

### Posture (optional)

Declare your working mode at session start:

| | DIRECT (execute) | META (analyze) |
|---|---|---|
| **ENG** | Implement, fix, ship | Architect, plan, design |
| **OPS** | Run pipelines, hit APIs | Audit, review, explore |

When capturing a CogPR, include `posture: "ENG/META"` (or whichever
mode applies). This helps `/review` weigh context — a lesson from active
implementation carries different weight than one from analysis.

Posture is advisory in CGG. Substrates that enforce posture constraints
(META = read-only, etc.) use the same fields — zero migration on upgrade.

### Signal format

For persistent conditions that need tracking, emit signals to `audit-logs/signals/YYYY-MM-DD.jsonl`. Use /siren for signal management if installed.

### Topology

Run `cgg-doctor.sh` from your project root to see your governance topology.

---

## Bash-Python Quoting Collapse
<a id="bash-python-quoting-collapse"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Inline Python in bash heredoc (`python3 -c "..."`) silently breaks when the Python code contains triple-quoted docstrings — bash C-style quoting (`$'...'`) mangles triple quotes into string terminators. The fix is to extract Python logic to a separate `.py` file and have the bash hook invoke it. This is a syntax-semantic collapse vector specific to hook authoring: bash and Python have incompatible quoting semantics that produce silent failures (no error, no output, exit 0 under `set -e`).

**Pattern**: When a hook needs non-trivial Python logic, write a `.py` file and call it from bash — never inline Python with heredoc or `-c` quoting.

<!-- promoted from CogPR-126 (tic 122→128). Source: session:sync-weigh-hook-tic-121. Evidence: bash -x trace showed $'Count' uncommitted' — triple-quote docstring mangled. Hook produced exit 0 with no output. Fixed by extracting to sync-weigh-check.py. Supports syntax-semantic collapse doctrine (canonical/CLAUDE.md). Band: COGNITIVE. -->

---

## OA-VPL-T Arena Geometry
<a id="oa-vpl-t-arena-geometry"></a>
<!-- ledger-tags: authority_class=arena_and_reasoning_geometry | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

OA-VPL-T (Office-Autonomous Value-Position Lattice with Temporal Modeling) is the 8th arena geometry template. Founding principle: **friction is evidence of hidden constitutional structure** — the revision trail from implementation friction is the excavation trail of the invariant stack. Key innovations: Phase 0a/0b (offices derive positions from mandate, not assigned labels), dependency-emergent brackets, and T0-T5 temporal tension modeling with Temporal Fraud as highest penalty.

Template: `stage/templates/arenas/office-autonomous-vpl/spec.md`

<!-- promoted from CogPR-128 (tic 122→128). Source: session:oavplt-design-tic-121. Evidence: convergence synthesis between c45 (federation-grounded) and oa54 (framework-level). Validated by 2 arena instances (sync-weigh + OT-integration). Refines arena template system, supports CogPR-112 (opposing-values geometry). Band: COGNITIVE. -->

---

## Install Boundary as Governance Transition
<a id="install-boundary-as-governance-transition"></a>
<!-- ledger-tags: authority_class=sync_and_install_parity | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

The forge→runtime install boundary (`canonical_developer/` → `~/.claude/`) is a first-class governance transition, not merely a file copy. Properties valid at the forge (syntax correctness, test passage, manifest consistency) are not automatically valid at the runtime. Derived constraints of this transition include: manifest atomicity, dual-read consistency, error transparency, and recursive self-observation. One structural anchor with derived rules is a tighter promotion footprint than independent inscriptions for each derived constraint.

This refines the Three-Form CGG Boundary (canonical/CLAUDE.md) with an operational principle: the install boundary is where governance properties must be re-verified, not assumed.

<!-- promoted from CogPR-130 (tic 122→128). Source: arena:sync-weigh-friction-oavplt — 5/7 office convergence. Ladder Auditor structural anchor framing validated. DIRECT-D enrichment: one structural anchor with derived rules is a tighter promotion footprint than seven independent inscriptions. Band: COGNITIVE. -->

---

## Claimed Install-State Requires Auditable Sync-Log Proof
<a id="claimed-install-state-requires-auditable-sync-log-proof"></a>
<!-- ledger-tags: authority_class=sync_and_install_parity | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

**Claimed install-state is not real until post-commit sync proves byte parity across all targets and emits an auditable sync log.**

Refines Install Boundary as Governance Transition: the install boundary is a **proof-required** transition, not merely a re-verification site. State assertions ("synced," "current," "matches canonical") have no constitutional weight without a sync-log entry tying the claim to a specific commit and surface set. "No drift detected" output alone is insufficient — silent abort can produce that observation while leaving install untouched.

Required proof artifacts for any claim that install-state matches canonical:
1. Commit SHA the sync ran against
2. Hook fired (traceable in stdout, sync log, or install-target ctime updates)
3. auto-sync completed the full pipeline (compare → copy → log-write → drift-signal-resolution)
4. Byte equality verifiable across all enumerated install targets
5. Sync log entry at `audit-logs/services/cgg-sync-log.jsonl` carrying timestamp + commit + synced surface list

The queue write path, commit discipline, and install propagation path are coupled, not assumed — each stage must produce its own proof artifact.

<!-- promoted from CogPR-209 (tic 209→211). Source: tic-209 /review Pass 1 closeout — operator-named upgrade. Band: COGNITIVE. -->

<!-- REFINEMENT EDGE (tic 406→/review 407, Architect-gated Option 3): install-parity is proven ONLY by byte-diff (sha match) at the install target the SYNCING TOOL ITSELF maps (runtime-sync discover --json), never at a hardcoded parallel path assumption, and never by trusting the verifier's HEADLINE synced/drifted/new counts. Proven twice in one tic at the boot-read-gate install: (1) runtime-sync reported "Synced: 196 | Drifted: 0 | New: 0" while the new hook was ABSENT from install — the check used an ASSUMED path (~/.claude/cgg-runtime/hooks/) instead of the tool's OWN discovered target (~/.claude/hooks/; hooks and scripts install to DIFFERENT roots); (2) git commit --amend did NOT trigger post-commit auto-sync at all, leaving the installed copy divergent while a re-run check would have counted it synced. NET-NEW teeth beyond this parent + Verifier-Install-Path-via-Sync-Manifest: (a) headline counts are not proof — a missing file can be counted "synced"; (b) --amend is a sync-trigger blind spot; (c) hooks and scripts have DIFFERENT install roots, so one assumed path is wrong for half of them. Composes Disagreement-as-evidence (the verifier's count disagreed with the filesystem — the disagreement was the signal) + byte-identity-verification-beats-count-size-metadata-parity (federation). This tic's gate-precedence patch + sync was itself verified this way (sha a4a6aaf… byte-identical at the discovered ~/.claude/cgg-runtime/scripts/boot-receipt.py). From cpr_verify_against_the_tools_discovered_path_headline_counts_lie_tic406 (audit-logs/governance/borns-tic406-boot-seam-verification.md); PROMOTE as refinement edge on Claimed-Install-State + Verifier-Install-Path, no standalone KI. signer ent_homeskillet-c48. -->

---

## Multi-Stage Governance Pipeline Stages Must Be Coupled with Proof Artifacts
<a id="multi-stage-governance-pipeline-stages-must-be-coupled-with-proof-artifacts"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Governance pipelines with N stages each capable of silent failure (queue write → commit → install propagation → audit) collapse into "trust the pipeline ran" unless each stage produces its own auditable proof artifact AND the absence of any stage's proof artifact is itself a detectable signal — not a pipeline that "looks fine."

The /review pipeline at tic 209 had three silent-failure stages: (a) queue write via Edit-tool-anchoring could insert before existing trailing lines and lose to latest-entry-per-id; (b) commit-after-execute was assumed but not codified, so the post-commit-sync hook had nothing to fire on; (c) auto-sync ran but its drift-signal-resolution side routine crashed on an undefined name, silently aborting before propagation completed. Each stage individually appeared to "work" — the pipeline as a whole did not propagate truth.

The fix coupled all three: atomic-append.sh as the queue-write proof artifact, Step 8.6 commit-after-execute as the commit-discipline proof artifact, and runtime-sync.py NameError patch + sync-log entry as the install-propagation proof artifact. Each stage now produces a verifiable trace; absence of any trace is the signal.

The pattern generalizes beyond /review. Any governance pipeline that mutates multiple state surfaces in sequence is vulnerable to the same failure class: one stage's silent abort being invisible to the others. The discipline is to identify each stage, name its proof artifact, and require its presence in the pipeline's success condition. This is the constitutional implementation of "Claimed install-state is not real until post-commit sync proves byte parity across all targets and emits an auditable sync log" — generalized from the specific install-state instance to any multi-stage pipeline.

<!-- promoted from cpr_governance_pipeline_stages_coupled_with_proof_artifacts_tic209 (tic 209→211). -->

---

## Remote-vs-Local Verification Scope Split for Scheduled Agents
<a id="remote-vs-local-verification-scope-split-for-scheduled-agents"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When scheduling a remote agent (Anthropic cloud routine) to verify a system whose state is partly local-only — install state under `~/.claude/`, machine ctimes, hooks registered to the operator's settings.json — the verification must be explicitly split into remote-checkable and local-required halves. The remote agent CANNOT see local install state; it can only see what's committed to the repo it checks out. Pretending otherwise produces verification reports that confirm what the remote agent CAN see while the actual question (did the local hook fire?) is invisible to it.

The split discipline:
1. Enumerate the proof requirements (operator-stated or derived).
2. Classify each requirement as remote-checkable, local-required, or hybrid.
3. Remote agent verifies its half autonomously and writes a structured docket to a known repo path (e.g., audit-logs/governance/<verification-name>.md).
4. Docket explicitly enumerates what the operator must verify locally, with exact commands and expected outputs.
5. Verdict classification must include "ZERO ACTIVITY TO TEST AGAINST" as a distinct outcome — not collapsed into success or failure. Zero activity is not proof; it requires a manual exercise plan to forcibly trigger the verification path.

The pattern is not specific to post-commit-sync. It applies to any scheduled remote agent verifying: local hook firing (PostToolUse, SessionStart, etc.), local install state (~/.claude/skills/, ~/.claude/agents/), operator-machine-bound resources (file ctimes, process state, MCP connections), or cross-repo coupling (federation root + nested CGG repo).

Without the explicit split, scheduled agents either (a) report misleading success on the half they can see, or (b) get stuck waiting for state they can never observe. The split makes both halves first-class.

<!-- promoted from cpr_remote_vs_local_verification_scope_split_tic209 (tic 209→211). Refines Cross-Agent Artifact Authority Deferral (canonical KI) by extending the boundary discipline to scheduled remote agents. -->

---

## Manual-Ceremony-as-Pipeline-Substitute Discipline
<a id="manual-ceremony-as-pipeline-substitute-discipline"></a>
<!-- ledger-tags: authority_class=sync_and_install_parity | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When a manual ceremony substitutes for an autonomous workflow (e.g., 12-agent swarm replacing cpr-enrichment-scanner.py), the manual ceremony must complete the FULL output contract of the autonomous workflow it replaced — not merely the visible artifacts.

The autonomous version of cpr-enrichment-scanner does two things atomically: (1) produce lens-A.json + lens-B.json + consolidated.json artifacts on disk, (2) append `enrichment_eligible` status writeback rows to queue.jsonl. Both steps are part of the producer→consumer contract. The manual swarm did (1) and skipped (2), so 63 enriched CPRs were invisible to bench-packet-prep and /review for an entire tic cycle.

This is structurally distinct from drift (system bug) — it is manual-process-bypassed-pipeline-contract. Same write-failure shape, different cause, different remediation class. The fix shape: mechanical atomic-append of the missing status rows with explicit provenance metadata (`enriched_by`, `enrichment_artifact`, `writeback_reason`) to preserve lineage integrity per federation invariant.

The discipline: when designing manual ceremonies that substitute for autonomous workflows, audit the autonomous workflow's complete output contract (artifacts produced AND state mutations performed AND signals emitted) and ensure the manual ceremony produces ALL of them, not just the visible artifacts. Skipped state mutations create silent invisibility — the work exists but the manifold doesn't see it.

Refines Conductor-Score-Runtime Parity (federation KI): the parity problem has a manual-ceremony variant. When doctrine names a discipline AND the runtime enforces it AND the manual substitute bypasses it, the parity violation is human-side, not system-side. Same diagnostic frame, different remediation locus.

<!-- promoted from cpr_manual_ceremony_must_complete_autonomous_workflow_output_contract_tic210 (tic 210→211). -->

---

## Handoff Carry-Forward Probe Discipline
<a id="handoff-carry-forward-probe-discipline"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Handoffs themselves are L3-class snapshots under the Volatility Handling Law. When a handoff carries an obligation of the form "wait until <future event> to assess <state>", that obligation encodes an unprobed hypothesis about current substrate state. The substrate may already contain decisive evidence that the handoff didn't have when it was authored — typically because the authoring context preceded the substrate event.

Concrete instance (tic 209 → tic 211): The tic 209/210 handoff carried routing decision tic-209-seq-2 with `outcome: null` and an explicit carry-forward instruction to "backfill at next session ≥ 2026-05-04 with verification agent's report status." The decision had scheduled a remote routine to verify the post-commit-sync hook fire. At the time the handoff was written, no local evidence had been collected.

When the operator asked at tic 210 "trigger bench-packet-prep and backfill the routing decision or tell me why not", a 30-second substrate probe (`tail audit-logs/services/cgg-sync-log.jsonl`) revealed two CONFIRMED-class sync events on a specific commit — both showing `drifted → synced`, with `commit_message` captured in the first event. The hook had ALREADY fired successfully, three days before the scheduled remote-routine verification. Backfilling outcome with `verdict_class: CONFIRMED` was honest, cheap, and amendable.

The operator's question forced a substrate check the handoff hadn't done. Without it, the routing decision would have carried `outcome: null` for three more days while the answer sat in plain text in the sync log.

The discipline: any handoff carry-forward item of the shape "wait until <future event> to verify <state>" should be treated as a candidate for substrate probe at the start of the next session, not passively re-deferred. The probe is cheap (one tail or one grep), the reward is freeing the obligation from the calendar to the present, and the cost of being wrong (probing finds no evidence yet) is zero.

Generalizes Verify-Before-Remediate External Friction (federation KI) from external surfaces (insights reports, partner complaints) to internal surfaces (handoff carry-forwards, scheduled obligations, deferred goals). Same family — verify against source before narrating, before remediating, before re-deferring. Same family as Probe-First Discipline (federation KI) applied to inherited handoff narrative rather than session narrative.

Mechanism: at /cadence handoff-consumption time (or at any moment when a carry-forward item surfaces), apply the test: "Could the substrate already contain the evidence this item is waiting for?" If yes, probe before re-deferring. If no, leave the item carried.

Refinement (tic 371 — sibling-finding-is-unverified-claim): the L3-snapshot status reaches past the handoff envelope to a *born CogPR's own surfaced-but-uninscribed sibling finding*. A captured CogPR frequently names an adjacent finding ("this also implies X about subsystem Y") that is not itself inscribed. That sibling carries the same unprobed-hypothesis status as a handoff carry-forward — a claim, not inherited truth — and must be probed from source before any fix is built on it. Tic 370 instance: the tic-368 producer-without-reconciler born surfaced a sibling — "cpr-enrichment-scanner re-appends unchanged rows every boot → queue BLOAT (producer-without-dedup-at-write class)." Reading the scanner from source partially FALSIFIED it: the writeback is update-in-place (replace-by-id, not append → the queue does not grow), the evidence path already dedups (`if not new_evidence: continue`), and the only real residual is write-churn on the zero-evidence path — a much lower-severity, differently-shaped issue (fixed tic 371 via a reason-stable skip). Building "dedup-at-write for the scanner" on the born's premise would have fixed a misdiagnosed problem. Composes Presence/Observation Fallacy Guard (federation KI): a claim's presence inside an inscribed candidate is not proof of its truth. The Architect's "prep, hold spec" directive is the structural room that lets the falsification land before the build.

<!-- promoted from cpr_born_sibling_finding_is_unverified_claim_tic370 (tic 370→371). Source: session_lessons_tic_370.md — born during the tic-370 enrichment-scanner prep, which source-falsified the tic-368 born's "queue bloat" sibling (bloat→churn, append→in-place, all-tiers→zero-evidence-path-only). Refinement edge (LIKELY DERIVABLE per its own non_derivability), not a new parent. Band: COGNITIVE. -->

<!-- promoted from cpr_handoff_carry_forward_items_must_probe_substrate_before_redeferring_tic211 (tic 211→211). -->

<!-- promoted from cpr_claimed_install_state_requires_sync_log_proof_tic209 (tic 209→209). Source: operator-named invariant during /review tic 209 hook coverage audit. Validated tic 209: post-commit-sync hook fired on /review commits but resolve_drift_signals_on_sync crashed on undefined find_audit_logs (CGG commit a948a71 patched it) — install was not updated despite "no drift detected" output. Manual byte-equality check exposed the silent abort. Constitutional lesson: trust the proof artifact, not the printed claim. Band: COGNITIVE. -->

---

## Detection Affordance Tracking
<a id="detection-affordance-tracking"></a>
<!-- ledger-tags: authority_class=forensic_and_drift_investigation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Promoted invariants should carry `detection_affordance` metadata tracking whether a detection mechanism exists. This is advisory at review time, not a blocking gate. Entries marked `"pending"` generate queue-refresh follow-up obligations. The metadata tracks the gap between inscription and enforcement — an invariant without a detection mechanism is a mandate without mechanism (F-2 pattern).

Format in promotion comments: `detection_affordance: active|pending|none`

<!-- promoted from CogPR-131 (tic 122→128). Source: arena:sync-weigh-friction-oavplt — 6/7 office convergence. Extends enforcement integrity (CogPR-100). Resolves the monitored-invariant concept: advisory question at review + metadata flag + follow-up obligation. Band: COGNITIVE. -->

---

## Friction-to-Invariant Pipeline
<a id="friction-to-invariant-pipeline"></a>
<!-- ledger-tags: authority_class=forensic_and_drift_investigation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Implementation friction generates invariant candidates through a recurring pipeline: friction → debugging → root cause → candidate → naming → promotion. The pipeline itself is a governance primitive — friction density predicts candidate generation rate. The sync-weigh implementation produced 7 friction invariant candidates from one implementation, validating the pattern. The constitutional learning is the pipeline shape, not the individual candidates it produces.

<!-- promoted from CogPR-132 (tic 122→128). Source: arena:sync-weigh-friction-oavplt — Pattern Curator Meta primary, Bracket B convergence, 5/7 office agreement. Meta-process observation about how arenas discover invariants. Band: COGNITIVE. -->

---

## Recursive Self-Observation
<a id="recursive-self-observation"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When a governance configuration surface is consumed by the mechanism it governs, the system exhibits recursive self-observation — the observer observing itself. This is constitutionally distinct from linear enforcement (CogPR-100): enforcement integrity addresses distributed layers detecting distinct failure modes, while recursive self-observation addresses a single mechanism that is both enforcer and governed surface. Non-derivability from CogPR-100 confirmed — these are structurally different phenomena.

Live evidence: `sync-manifest.json` consumed by `sync-weigh-check.py` which checks manifest drift; `active-manifest.jsonl` created as fix for signal scan blind spot.

CGG scope — promote to federation if second subsystem instantiation emerges.

<!-- promoted from cpr_recursive_self_observation_tic179 (tic ?? → 179). Source: arena:2026-04-26_memory-trim-oavplt. Band: COGNITIVE. -->

---

## Atomic-Commit Discipline (Multi-File Mutations)
<a id="atomic-commit-discipline-multi-file-mutations"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Atomic-commit (multi-file mutations bound into single commit unit with pre-commit validation) is required CGG-scope discipline. Pattern recurs: sync manifest dual-writes, registry-content-source triples, memory-trim MOVE = destination + forward pointer + referrer patches in same commit. CGG-scope distinct from CogPR-8 (intra-file atomic JSONL writes) — this is inter-file atomicity.

<!-- promoted from cpr_atomic_commit_discipline_scope_tic179 (tic 179 → 179). Source: arena:2026-04-26_memory-trim-oavplt. Band: COGNITIVE. -->

---

## MEMORY.md Inline Entry Location Lock (REVIEW_PINNED)
<a id="memory-md-inline-entry-location-lock-review-pinned"></a>
<!-- ledger-tags: authority_class=memory_and_inscription_hygiene | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

MEMORY.md inline entries with `status: pending` are operationally treated as location-locked until /review processes them. Functions as second pin axis (REVIEW_PINNED, Disposition 0b orthogonal to constitutional-pin Disposition 0). Memory-trim cycles must respect this lock.

<!-- promoted from cpr_review_pinned_location_lock_tic179 (tic 179 → 179). Source: arena:2026-04-26_memory-trim-oavplt. Band: COGNITIVE. -->

---

## User-Space Handoff Referrer Surface
<a id="user-space-handoff-referrer-surface"></a>
<!-- ledger-tags: authority_class=memory_and_inscription_hygiene | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

User-space handoff plans (`~/.claude/plans/*.md`) live OUTSIDE federation commit boundary, accumulate ~70+ files over many tics, and each cites MEMORY.md sections from its authoring era. Memory-trim reference audits AND ladder-audit cycles must include this referrer axis or they silently sever the handoff chain.

<!-- promoted from cpr_user_space_handoff_referrer_surface_tic179 (tic 179 → 179). Source: arena:2026-04-26_memory-trim-oavplt. Band: COGNITIVE. -->

---

## Memory-Trim Staged Execution Pattern
<a id="memory-trim-staged-execution-pattern"></a>
<!-- ledger-tags: authority_class=memory_and_inscription_hygiene | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

High-composite-load memory-surface trims (composite mutation count >5) execute across multiple tics, not single-tic. Pattern: 4-tic staged window — Stage 0 (Probe + Inscribe), Stage 1 (Audit + Pin List), Stage 2 (Trim execution), Stage 3 (Re-stamp + Verification). Schedule decompression preserves operator absorption capacity AND prevents composite cascade failure.

<!-- promoted from cpr_memory_trim_staged_execution_pattern_tic179 (tic 179 → 179). Source: arena:2026-04-26_memory-trim-oavplt. Band: COGNITIVE. -->

---

## Signal Resolution Writeback Atomicity (Dual-Surface)
<a id="signal-resolution-writeback-atomicity-dual-surface"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When signals are resolved in daily files (`audit-logs/signals/YYYY-MM-DD.jsonl`), the active-manifest may not receive a corresponding write — divergence between daily file truth and manifest curation. Resolution writeback must be atomic across both surfaces, or a sweep-style reconciliation must run on cadence. **Mechanism (tic 182):** `cgg-runtime/scripts/manifest-prune.py` provides atomic, idempotent, archive-preserving sweep — moves resolved entries from active-manifest to `audit-logs/signals/resolved-archive.jsonl`. Wired into `mogul-runner.sh` as pre-spawn invocation. Validated tic 182: 20 stale-resolved entries swept to 3 active, matching session-start banner exactly. The doctrine is now mechanism-implemented, not merely named.

<!-- promoted from cpr_cmd_auto_sync_writeback_gap_tic171 (tic 171 → 179). Source: arena:2026-04-26_memory-trim-oavplt. Band: COGNITIVE. Refined with cpr_active_manifest_resolution_sweep_tic182 (tic 182→183) — named-doctrine to mechanism-implemented. -->

---

## Precedence-Authority Envelopes (Cross-Clade Typed)
<a id="precedence-authority-envelopes-cross-clade-typed"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Cross-clade typed envelopes that carry precedence-ordering authority as a first-class field. Surviving primitive from OT solo arena (tic 170). Refines existing envelope-pattern invariant — when envelopes cross jurisdictional boundaries, precedence-authority must be explicit, not implied by sequence.

<!-- promoted from cpr_precedence_authority_envelopes_ot_tic170 (tic 170 → 179). Source: arena:2026-04-26_memory-trim-oavplt. Band: COGNITIVE. -->

---

## Queue Metadata Schema Declaration
<a id="queue-metadata-schema-declaration"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Queue metadata schema is implicit. Producer (review-skill, review-execute, mandate-runner, cpr-extract-hook) and consumer (build-queue-index, bench-packet-prep, /governance-check) conventions drift silently. Schema-declaration discipline must be explicit across producers/consumers. Complement to Emitter-Surface Declaration Contract (CogPR-160) and Extractor Surface Schema Contract (CogPR-149).

<!-- promoted from cpr_4cc73a735df78a1b (tic 179 → 179). Source: arena:2026-04-26_memory-trim-oavplt. Band: COGNITIVE. -->

---

## Cross-Estate Integration Assessment Triple Test
<a id="cross-estate-integration-assessment-triple-test"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Cross-estate integration assessments should use a triple-intersection test (federation invariants × estate's mandate × concrete operational evidence) to distinguish viable adoption from incidental compatibility. Two-axis tests miss "looks compatible but evidence base is wrong" failures.

<!-- promoted from cpr_fbfabe0b5eb9e0d2 (tic 179 → 179). Source: arena:2026-04-26_memory-trim-oavplt. Band: COGNITIVE. -->

<!-- promoted from CogPR-133 (tic 122→128). Source: arena:sync-weigh-friction-oavplt — triple convergence (Pattern Curator Meta, cbUX, Videographer). Non-derivability vs CogPR-100 adjudicated: PASS. Resolves sig_2026-04-08_arena_fi7_nonderivability_open. Band: COGNITIVE. -->

---

## Encounter Quality Upstream of Signals
<a id="encounter-quality-upstream-of-signals"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

The governance encounter surface (hook output at edit time) is constitutionally upstream of signal infrastructure. If the encounter fails — silent hook, wrong path resolution, ambiguous output — the governance signal never fires. The manifold's health depends on encounter surface reliability. A silent exit-0 does not just frustrate the developer — it blinds the governance layer. Encounter quality is a load-bearing governance component, not a UX convenience.

<!-- promoted from CogPR-134 (tic 122→128). Source: arena:sync-weigh-friction-oavplt — reinforced across 3 arena offices (cbUX primary, Videographer + Pattern Curator Meta supporting). Crisis Steward's 2305-duplicate incident as causal evidence. Complements CogPR-130 (install boundary anchor). Band: COGNITIVE. -->

---

## Spec-First Parallel Swarm
<a id="spec-first-parallel-swarm"></a>
<!-- ledger-tags: authority_class=subagent_and_swarm_delegation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Write complete spec surface BEFORE launching implementation agents. Agents read specs as their constitution — the spec is the agent's mandate, not a reference document. This eliminates the headless subagent curation problem (documented in global CLAUDE.md "Headless Subagent Delegation") by making the spec authoritative rather than relying on inline appendices. The temporal ordering is load-bearing: spec authoring must complete before agent spawning begins.

Validated at scale: 13 spec tranches → 12 implementation engines, 86/86 artifacts verified correct.

<!-- promoted from CogPR-135 (tic 125→128). Source: session:tic-125 megabuild. Evidence: largest implementation session in federation history — 13 tranches, 12 engines, 86/86 verified. Distinct from global "authoritative appendices" guidance — this is about temporal ordering of spec authoring vs agent spawning. Band: COGNITIVE. -->

---

## Composite Mutation Assessment at LEAD Level
<a id="composite-mutation-assessment-at-lead-level"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

CogPR-117 (composite mutation scheduling) is systematically invisible to advocate-level reasoning in governed arenas. Offices assess their own constitutional surface changes individually but never assess the composite. The wildcard chain coherence mechanism is the only reliable detection surface. Composite assessment must be enforced at LEAD/synthesis level as a mandatory Phase 6 deliverable, not left to advocate initiative.

<!-- promoted from CogPR-140 (tic 126→130). Source: arena:2026-04-09_ot-economic-integration-oavplt. Note: CD-5. Convergent: wildcard found, confirmed by conformation analysis (dead zone classification). Band: COGNITIVE. -->

---

## Wire-Cut Scoping by Capability Class
<a id="wire-cut-scoping-by-capability-class"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Containment wire-cuts must be scoped to capability classes (ingress, all, panic), not binary on/off. The Docks wire-cut spec demonstrates the pattern — three graduated scopes preserve maximum capability while containing the specific threat vector. Binary wire-cuts (everything or nothing) over-contain, causing collateral damage that discourages use of containment altogether.

<!-- promoted from CogPR-145 (tic 129→138). Source: pattern_miner:PAT-T129-DIRECT-A — reinforced. Docks wire-cut implementation validates graduated scoping. Crisis subsystem scope. Band: COGNITIVE. Confidence: 0.85. -->

---

## Authoritative Count Discipline
<a id="authoritative-count-discipline"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Governance reporting tools must source counts from authoritative state (physical event files, active manifests), not from configuration or raw unfiltered logs. bench-packet-prep.py silently reported tic=0 (from .ticzone config) and signals=290 (from raw logs) instead of tic=134 (from counted events) and signals=5 (from curated manifest). Extends CogPR-79 (spot-check output against source data) with a specific authoritative-source discipline.

<!-- promoted from CogPR-146 (tic 135→138). Source: session:tic-135. Evidence: bench-packet-prep.py sourced tic from config and signals from unfiltered logs, producing dramatically wrong counts. Extends CogPR-79. Band: COGNITIVE. Confidence: 0.92. -->

---

## Dedup-at-Write Using Canonical Identity
<a id="dedup-at-write-using-canonical-identity"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Duplicate detection must occur at the write boundary (physics layer) keyed on canonical record identity (signal_id, CPR id), not at scan time or by content hash. `dedup_signal_append()` in `atomic_append.py` demonstrates the pattern — one enforcement point, four emitters. This is distinct from atomic writes (CogPR-8, corruption prevention) and signal ID determinism (CogPR-66, ID stability) — this addresses where and how dedup enforcement happens: at the write boundary, using canonical identity as the key.

<!-- promoted from CogPR-147 (tic 135→138). Source: session:tic-135. Evidence: dedup_signal_append() in atomic_append.py — 4 emitters already using write-boundary dedup. Complements CogPR-8 (atomic writes) and CogPR-66 (signal ID determinism). Band: COGNITIVE. Confidence: 0.90. -->

**Producer-without-reconciler starvation (refinement).** A scheduled queue PRODUCER (e.g. `pattern_mining`, emitted every cadence by `compute_due_cycles`) WITHOUT its scheduled RECONCILER (`cpr_step`, absent from `compute_due_cycles` since ~tic 90) silently re-floods the queue with `extracted` re-extractions of already-promoted lessons, appended AFTER terminal rows (a Terminal-State-Valve violation). The flood is invisible to every routine surface: `governance_query.queue.status` returns 0 for the extracted tier, `bench_packet_prep` was dropped from the scheduler at tic 293 (manual-only), and the enrichment scanner only scans the enrichment tiers — so ~17 duplicates accreted ~280 tics touched by nothing. The robust fix is dedup-at-write IN THE PRODUCER — skip any envelope whose content-deterministic canonical id already exists in the queue's latest-entry projection (any status) — NOT merely re-scheduling the downstream reconciler, which leaves the producer free to re-flood between runs. Maps Dedup-at-Write + Terminal-State-Valve onto the producer boundary. (Lane-placement of the reconciler itself is a federation refinement under *Lane-separation* — judgment-bearing reconcilers go async-decoupled, see `constitution-ledger/ledger.md#lane-separation-foreground-judgment-background-execution`.)

<!-- promoted from cpr_producer_without_reconciler_queue_starvation_tic368 (session_lessons_tic_368.md, /review 370 PROMOTE-as-refinement, Architect-gated). Routed as refinement NOT new parent per the candidate's own non-derivability assessment: composition of Dedup-at-Write-Using-Canonical-Identity + Cadence-Ops-Scheduler-Doctrine-Runtime-Parity + Enrichment-Pipeline-Silent-Starvation. Runtime fix LANDED tic 369 (CGG 40e3f02; proven 7/7 incl. idempotency). Band: PRIMITIVE. -->

---

## Pattern Mining Context Procurement
<a id="pattern-mining-context-procurement"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Pattern mining context procurement must precede mining — a briefing covering governance surfaces with NLP heuristics (bigram frequency, Gini coefficient, temporal clustering, entity co-occurrence) empowers mining agents with statistical shape without claiming to catch patterns. Three-tier posture (briefing+inline / interactive / full team) guards against cognitive drain while ensuring surface coverage. Validated: briefing-first approach empowered the pattern-curator to discover MEMORY.md truncation that a script couldn't.

<!-- promoted from CogPR-149 (tic 136→138). Source: session:tic-136. Evidence: pattern-mining-context.py + three-tier posture validated in practice. Shapes Mogul's agent-spawning behavior for pattern mining. Band: COGNITIVE. Confidence: 0.82. -->

---

## Hook Binary Invocation (No Aliases)
<a id="hook-binary-invocation-no-aliases"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Hook scripts must call binaries directly, never shell aliases — aliases live in interactive shell config (.zshrc) and do not survive non-interactive invocation. Dedup by content hash prevents duplicate firing at event boundaries. Complements Hook Path Resolution (CogPR-127) which covers zone root discovery but not invocation resolution.

**Pattern**: Use full binary paths (`/usr/bin/python3`, `$(which tmux)`) in hook scripts, never aliases or functions from shell profiles.

<!-- promoted from CogPR-150 (tic 136→138). Source: session:tic-136. Evidence: alias resolution failure in hook invocation + content-hash dedup prevents duplicate firing. Complements CogPR-127 (Hook Path Resolution). Band: COGNITIVE. Confidence: 0.88. -->

---

## Inter-Engine Integration Emission
<a id="inter-engine-integration-emission"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When two engines share state through a registry file, the producing engine must emit records in the consuming engine's expected format. Each engine may be individually correct while the integration surface is a blind spot. 14 cycles of invisible integration failure between biome-engine and trust-engine demonstrated the pattern — each engine passed its own tests, but the integration surface was never verified. Extends CogPR-79 (spot-check output against source) to cross-system integration verification.

<!-- promoted from CogPR-151 (tic 136→138). Source: session:tic-136. Evidence: 14 cycles of biome→trust invisible failure. Each engine individually correct; integration surface unverified. Extends CogPR-79 to inter-engine integration. Band: COGNITIVE. Confidence: 0.92. -->

- **Integration loop closure requires explicit invocation wiring** — each engine individually correct and sharing correct-format state is necessary but not sufficient for integration. The data-producing engine must explicitly invoke the data-consuming engine after state persistence. Invocation IS the integration, not data format. This extends CogPR-151 (format compliance) to call-path presence: engines may share perfectly formatted data yet produce silent zero-output because no engine calls the next one. The protection is an explicit orchestrator (e.g., trust-progression-cycle.py) that sequences produce → persist → consume as a single governed pipeline. (Validated: biome→trust→standing loop — 3 engines, correct formats, 18 cycles of interaction data, 0 trust computed. Root cause: no call path connected them. Orchestrator closed the loop immediately.)

<!-- promoted from CogPR-178 (tic 145→146). Source: session:visitor-phase1-dry-run. -->

- **Backfill After Emission-Gap Closure** — when an emission gap closes (previously missing signal generator becomes active), backfill the signal queue with synthesized entries for the gap period, keyed on the prior inferred state. Backfill entries must carry `synthesized: true` and reference the gap resolution tic. Without backfill, the gap period appears quiescent when it was actually blind, creating false confidence in the completeness of the historical signal surface.

<!-- promoted from cpr_66abdac2db1ffd6c (tic 171→172). Source: session:visitor-phase1-gap-closure. -->

---

## Named-Is-Not-Landed Gate
<a id="named-is-not-landed-gate"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

A complement surfaced in a prior mode but not yet materialized remains a valid complement. The structural relevance test must evaluate complement state (built vs named vs unnamed), not just recent-output presence. First calibration evidence from /complement invocation log — the gate correction shapes skill behavior by requiring materialization state assessment before declaring a complement irrelevant.

<!-- promoted from CogPR-152 (tic 136→138). Source: session:tic-136. Evidence: first /complement calibration. Gate correction: evaluate complement state, not just recent-output presence. Band: COGNITIVE. Confidence: 0.82. -->

---

## Live-Wiring Is a Build, Not a Config Flip
<a id="live-wiring-is-a-build-not-a-config-flip"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | born_tic=371 | promoted_tic=373 -->

Live-wiring a render-proven tool into a hook EVENT is a BUILD, not a config flip. A CLI that renders correctly to stdout/JSON is "named/proven" but NOT "landed" as a hook: the hook's INPUT contract (a stdin envelope) and its model-visible OUTPUT channel are externally-versioned (Anthropic) and must be probed before binding. Tic 371: task_touch.py was render-proven (8/8) but wiring it raw into PreToolUse would have been SILENTLY INVISIBLE — plain stdout at exit 0 is DISCARDED; only `hookSpecificOutput.additionalContext` reaches the model, and only exit 2 blocks. The probe (claude-code-guide) caught it; the fix was a stdin-JSON adapter (`task-touch-pretool.py`), not a settings.json line. Render-proven is not wired. Refines Named-Is-Not-Landed Gate (extends "named ≠ landed" to the hook-wiring surface specifically); composes Volatile-Schema Validation Discipline (probe-before-bind on an externally-versioned hook I/O schema).

<!-- promoted from cpr_live_wiring_is_a_build_not_a_config_flip_tic371 (tic 371→373, /review 373 PROMOTE as refinement edge). Source: session_lessons_tic_371.md; claude-code-guide confirmed PreToolUse exit-0 stdout is discarded, additionalContext is the model-visible channel, exit-2 is the only block. Adapter: cgg-runtime/hooks/task-touch-pretool.py; activation receipt audit-logs/governance/task-touch-live-wiring-activation-receipt-tic371.md. Validated by 3 live in-session fires (ESCALATE/OFFICE/SUBSTRATE). Non-derivability: author flagged LIKELY DERIVABLE (composes Volatile-Schema Validation + Named-Is-Not-Landed); promoted as a refinement edge — the net contribution is the concrete operational trap (hook stdout discarded; additionalContext is the sole model-visible channel; exit-2 is the sole block), not a new parent. Band: COGNITIVE. Confidence_tier: reinforced (n=3 live fires). -->

---

## Contamination Lifecycle and Forensic Investigation Discipline
<a id="contamination-lifecycle-and-forensic-investigation-discipline"></a>
<!-- ledger-tags: authority_class=forensic_and_drift_investigation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Third-party software contamination follows a structural lifecycle: (1) silent environment mutation (shell profile injection, proxy redirection without ToS disclosure), (2) persistence mechanisms (auto-launch override via internal config sync that resists user intervention, provider env.sh writes on every launch), (3) data residuals surviving removal (macOS drag-to-Trash removes only .app bundle; ~/Library data, launch agents, keychain entries, auto-updaters persist — observed: 9.4GB across 19 directories from 3 apps).

Detection requires three complementary systems: file-integrity drift (did watched files change — high confidence, after-the-fact), baseline deviation (new env vars, launch agents, proxy settings — high confidence, after-the-fact), live attribution (what process is touching files now — medium confidence, real-time only). 'Who changed this file' cannot be recovered after the fact without pre-existing auditing.

Investigation discipline: enforce app identity separation at the top of any multi-app investigation (per-app evidence buckets, shared-framework hypotheses explicitly labeled). Separate observed fact (entitlement exists, local server exists, bundled runtime exists) from inferred risk (possible interception surface, possible exfil path). Require proof threshold before strong verbs — use 'creates a surface for,' 'permits,' 'is capable of' until runtime evidence of activation exists. Entitlement proof first, runtime/process inventory second, network/socket verification third, source-level code inference last.

<!-- promoted from CogPR-170/171/172/173 merged (tic 141-143→143). Source: Genspark forensic investigation tic 141-143. Band: PRIMITIVE. detection_affordance: active (contam_sentinel.py). -->

---

## Accessibility API Structural Indistinguishability
<a id="accessibility-api-structural-indistinguishability"></a>
<!-- ledger-tags: authority_class=forensic_and_drift_investigation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Cross-app activity tracking via accessibility API is structurally indistinguishable from legitimate dictation context — the app needs focused_app_bundle_id to deliver text. The invasive choice is persisting and syncing that data, not collecting it. Detection requires inspecting the local database schema for sync tables and cross-app indexes, not monitoring runtime behavior.

<!-- promoted from CogPR-175 (tic 142→143). Source: Speakly genspark-flow.db analysis. Depends on: MERGE-A (three detection systems). Band: COGNITIVE. detection_affordance: pending. -->

---

## Competing Canons / Hardening Pass Obligation
<a id="competing-canons-hardening-pass-obligation"></a>
<!-- ledger-tags: authority_class=forensic_and_drift_investigation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Report artifacts that span an iterative build accumulate competing canons when the approach changes mid-session but earlier sections aren't rewritten. A report that describes abstract scalar-bar b-roll in sections 1-5 and morph-based narrative scenes in section 11 carries two incompatible descriptions of the same deliverable. The hardening pass (rewriting the top-level story to match the final winning approach while preserving the forensic record of how the pipeline got there) is a distinct authoring obligation, not a polish step.

<!-- promoted from CogPR-161 (tic 139→143). Source: session:podcast-pipeline-ep31. Band: COGNITIVE. detection_affordance: pending. -->

---

## Baseline Re-Anchoring After Intentional State Change
<a id="baseline-re-anchoring-after-intentional-state-change"></a>
<!-- ledger-tags: authority_class=forensic_and_drift_investigation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Integrity sentinels that detect remediation-era changes must be rebaselined immediately after cleanup completes. The baseline captures pre-remediation state — disappeared malware agents, shifted mdworker populations, etc. — creating false-positive noise that obscures real future drift. Rebaseline-after-remediation is the correct sequence: init → detect → remediate → rebaseline → monitor clean state. Without the rebaseline step, the sentinel's first clean-state check inherits all the remediation delta as 'drift', triggering high-volume signals (vol 50) that are entirely self-referential.

<!-- promoted from CogPR-176 (tic 143→143). Source: contam_sentinel.py vol 50 self-referential bootstrap signal. Band: COGNITIVE. detection_affordance: active (contam_sentinel.py rebaseline). -->

---

## Multi-Session Artifact Provenance
<a id="multi-session-artifact-provenance"></a>
<!-- ledger-tags: authority_class=forensic_and_drift_investigation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Forensic reports spanning multiple investigation sessions must carry explicit per-finding timestamps, not a single document date. The tic-142 deep analysis invalidated a key claim from the tic-141 initial report: 'App did NOT recontaminate on restart — injection was one-time onboarding action.' The correction (TokenProvider fires on every launch) was only possible because the second session tested what the first session assumed. Reports with a single date create a false impression of static, complete findings. The fix: each finding carries its own discovery timestamp and confidence level, and corrections to prior findings are marked explicitly as corrections with the original claim cited.

<!-- promoted from CogPR-177 (tic 143→143). Source: Genspark forensic binder — prior session's one-time claim corrected. Band: COGNITIVE. detection_affordance: pending. -->

---

## Drift Classification Taxonomy
<a id="drift-classification-taxonomy"></a>
<!-- ledger-tags: authority_class=forensic_and_drift_investigation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When auditing an adapter for API drift, classify each line as: accurate (matches current docs), likely stale (was accurate, drift detected), unverified from public docs (may work but not documented), or custom layer (our orchestration, not an API claim). The classification taxonomy prevents conflating adapter-specific orchestration code with actual API contract violations. The TS overshoot adapter had 6 custom-layer files that were architecturally sound but would have been flagged as drift without this distinction.

<!-- promoted from CogPR-163 (tic 140→143). Source: session:overshoot-adapter-audit. Operationalizes Volatility Handling Law L3/L5. Band: COGNITIVE. detection_affordance: pending. -->

---

## Single Routing Surface for Generation and Adjudication
<a id="single-routing-surface-for-generation-and-adjudication"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

External media API routers (generation + adjudication) should share a single routing surface and budget. Generation asks 'make this' and adjudication asks 'is this good?' — both are media egress, both cost money, both need audit trails. Splitting them by provider rather than by function fragments the spend surface.

<!-- promoted from CogPR-162 (tic 140→143). Source: session:overshoot-adapter-audit. Extends cognitive budget routing. Band: COGNITIVE. detection_affordance: pending. -->

---

## Overlay-at-Timestamp Assembly
<a id="overlay-at-timestamp-assembly"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

B-roll assembly must use overlay-at-timestamp (video replaces speaker footage at specific time windows), not insert-between-segments (video spliced into the timeline). Insert-based assembly adds duration to the video track without adding duration to the audio track, causing cumulative sync drift after every insertion. The audio spine is continuous and untouched; the visual layer swaps at precise windows.

**Audio spine duration derivation**: When extracting audio for the composite track, use reel durations (the final edited sequence duration), not source durations (the unedited source material). Audio extracted at source durations (13.5s) while video uses reel durations (10s) from the same EDL produces progressive drift after every cut point. Correct sequence: extract audio_in to audio_out for exactly (reel_out - reel_in) seconds duration.

<!-- promoted from CogPR-158 (tic 139→143). Source: session:podcast-pipeline-ep31. Band: COGNITIVE. detection_affordance: pending. -->

<!-- promoted from CogPR-186 (tic 149→188). Source: MEMORY.md inline candidate. Audio spine duration must use reel durations, not source durations. Evidence: tic 149 assembly produced 13.5s audio clip from 10s reel — progressive drift after each cut point. Fix: extract audio at source_in for exactly (reel_out - reel_in) seconds. Band: COGNITIVE. Confidence_tier: tentative. -->

---

## Morph Transition Grammar
<a id="morph-transition-grammar"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Morph transitions are atomic compound operations: (1) keyframes must come from different visual worlds — two real frames produce camera interpolation, not transformation; (2) OUT morph chains from IN morph's actual last frame (pose continuity); (3) editorial trims must not land inside morphing zones — cutting mid-morph produces visible breaks. EDL needs continuity_type per b-roll slot.

<!-- promoted from CogPR-155/167 merged (tic 139-141→143). Source: session:podcast-pipeline-ep31 + Ep31 reel analysis. Depends on: CogPR-158 (overlay method). Band: COGNITIVE. detection_affordance: pending. -->

---

## Timeline Lock and Base Track Preparation
<a id="timeline-lock-and-base-track-preparation"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Timeline lock (freezing the edited base track before generation) requires re-transcription of the edited base track BEFORE locking. If the edit trims key phrases from the base track, the b-roll markers and captions remain locked to their original (now-phantom) timestamps. Correct sequence: (1) build base track → (2) edit for content coherence → (3) re-transcribe edited track at 0.001s granularity → (4) verify all markers match edited content → (5) lock timeline → (6) THEN generate b-roll/morph content. Skipping step 3 produces silent content loss: key phrases ('energetic hygiene', 'you think it's yours') vanish from the reel while markers reference them.

<!-- promoted from CogPR-188 (tic 149→188). Source: MEMORY.md inline candidate. Timeline lock + base track preparation discipline. Evidence: tic 149 edit trimmed key phrases from base track; captions + b-roll markers referenced phantom content. Root cause: re-transcription skipped between edit and lock. Correct sequence: edit → re-transcribe → verify → lock → generate. Band: COGNITIVE. Confidence_tier: tentative. -->

---

## Temporal Scope Discipline
<a id="temporal-scope-discipline"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

- **Federation-scoped tic resolution for duration measurement** — governance functions measuring duration in federation tics must resolve from the canonical tic log (`audit-logs/tics/*.jsonl`, field: `domain_counter_after`), not from domain-scoped counters in data files. Domain data files store domain-local cycle counters that do not map to federation time. The failure mode is silent zero-output: a duration function reads a biome-scoped `cycle` counter instead of the federation tic log's `domain_counter_after`, returning 0 for all entities despite 14+ tics elapsed. The rule: any function parameterized by federation tics must source its temporal data from the tic log. (Validated: standing-engine time-at-standing returned 0 for all visitors. Registry stored biome-scoped cycle counter; engine needed federation tic log's domain_counter_after. Silent zero-output for 14+ tics.)

<!-- promoted from CogPR-179 (tic 145→146). Source: session:visitor-phase1-dry-run. -->

- **Grace period temporal scope must match governance clock** — when governance functions define grace periods or deadlines, the temporal scope must bind to the governance clock (federation tics), not simulation clocks (biome cycles, generation counters). A full multi-cycle simulation (e.g., 50 biome cycles) may execute within a single federation tic. If grace were measured in simulation cycles, it would expire during a single simulation run, violating the governance intent: give the system time to observe and respond across governance review windows, not just simulate. The distinction between governance clock and simulation clock is fundamental to any system that runs multi-cycle simulations within governance-paced review windows. (Validated: demotion grace period of 5 federation tics correctly survives 50-cycle biome generations that execute within single tics.)

<!-- promoted from CogPR-181 (tic 146→146). Source: demotion lifecycle build. -->

---

## Governed Bridge Mechanics
<a id="governed-bridge-mechanics"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

- **Loneliness intervention as governed bridge mechanic** — isolated nodes in proximity-based networks experience self-reinforcing isolation: no neighbors means no interactions, no interactions means no trust accumulation, no trust means no promotion, no promotion means continued isolation. The intervention is a governed bridge: a weak edge, metadata-marked with `intervention_type`, that creates opportunity for trust accumulation without bypassing the trust system. The bridge does not grant trust — it creates the conditions under which trust can be earned. The constraint is "opportunity without bypass": the bridge must emit a governance signal, carry audit metadata, and use weak-edge weight so natural interactions can strengthen or replace it. (Validated: Flint isolated 20 cycles in sector 4 — no natural interaction partners. Loneliness bridge created weak cross-sector edge at cycle 20. Flint progressed guest→tourist→foreign_delegate by cycle 23, 3 cycles post-bridge. Bridge metadata and signal preserved full audit trail.)

<!-- promoted from CogPR-180 (tic 145→146). Source: session:visitor-phase1-dry-run. -->

---

## Gate Contracts (Not Vibes)
<a id="gate-contracts-not-vibes"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

A gate is a contract surface, not a vibe or preference. Gate inputs must be explicitly declared (what goes in), outputs must be verifiable (what comes out), preconditions must be stateable (when it can run), and post-checks must be automatable (whether it succeeded). Spec-first execution with operator review gates works because the gate is a stated contract: inputs (spec text), outputs (binary proceed/halt decision), preconditions (spec authored and approved), post-checks (human review of applicability before unlock). Gates without declared contracts become vibe-based ("does this feel like a good implementation?"), producing endless renegotiation and operator cognitive overload. Pipeline phase dependencies must be structured gate contracts using this pattern.

<!-- promoted from cpr_gate_contracts_not_vibes_tic150 (tic 150→167). Source: tic-164-165-166 duality-lane authoring + Run 2 execution. Evidence: gate_b2 mechanism failure (tic 165) was diagnosable only because the gate had declared contract (preserve body byte-identical); absence of declared input made "was the gate input correct?" answerable. Band: COGNITIVE. -->

---

## Clean Primary Proof Outranks the Audited Escape-Hatch in Gate Precedence
<a id="clean-proof-outranks-escape-hatch-in-gate-precedence"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=409 | first_appearance_tic=407 -->

A governance gate that admits BOTH a clean primary proof (a valid receipt) AND an audited escape-hatch (an override) must evaluate the clean proof FIRST; the escape-hatch is a gap-filler for when clean proof genuinely cannot exist (a clipped packet, an unavailable injection), never a substitute that pre-empts a genuine proof. If the override is checked first, two failures follow: (1) it MASKS genuine compliance — the gate reports `via=override` when the clean-proof path was in fact satisfied, so an auditor cannot distinguish "satisfied cleanly" from "escaped"; (2) a stale or broad override silently keeps authorizing past its intended scope, defeating the gate's freshness guarantee (enforce a FRESH proof each cycle). The fix is a precedence inversion: clean-proof-first, override-as-fallback-only — an override evaluated-first is not merely redundant but actively erodes the gate's evidentiary value (can't tell compliant from escaped) and its freshness guarantee. Composes the sovereign-gate engine/adapter split (tic 406) + engine-content-separation; refines the boot-read-gate narrow+fail-closed posture.

<!-- promoted from cpr_clean_proof_outranks_escape_hatch_in_gate_precedence_tic407 (tic 407→409, /review 409). Source: audit-logs/governance/borns-tic407-gate-precedence-and-classifier.md. Evidence: proven tic 407 — boot-receipt.py gate_decision allowed a governed mutation via=override (matching the prior session's cadence-boundary override) even though an honestly-emitted full/gapless boot-read receipt existed for the same (entity,tic); swapping the two blocks (receipt-pass before override-match) resolved it via=boot_read_receipt; proven across 6 cases (receipt→via=boot_read_receipt; no-receipt→BLOCK; bootstrap override still works where no clean proof exists; path-scoped override does not broaden; emit ungated; clean receipt outranks override even on path mismatch). Composes sovereign-gate engine/adapter split + engine-content-separation; refines boot-read-gate narrow+fail-closed posture. Band: STRUCTURAL. Confidence_tier: reinforced. -->

---

## A Mutation Gate's Command Classifier Gates the WRITE SIGNAL, Not the Mere Path MENTION
<a id="mutation-gate-classifier-gates-write-signal-not-path-mention"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=409 | first_appearance_tic=407 -->

A mutation gate that classifies free-form COMMANDS (Bash) — as opposed to typed file-path tool calls (Edit/Write) — must gate the WRITE SIGNAL, not the mere MENTION of a governed surface path. A command that names a governed path can be a read (cat/grep/head/tail/less/wc/diff/jq/awk), a versioning op (git add/commit/push/status/diff/log/show), or an actual write (a `>`/`>>` redirect, tee, sed -i, dd of=, or a known write-script). Only the last class mutates: reading INSPECTS state, and versioning RECORDS already-mutated state (the mutation was gated at its Edit/Write source — versioning it is not a second mutation). A classifier that fires on path-MENTION over-blocks every read, every commit, and the cadence-tail git-versioning — taxing the exact operations a governed system runs constantly, which then pressures operators toward broad audited overrides (the override that masks the precedence problem in the sibling entry above). The fix: enumerate the WRITE signals (redirect/tee/in-place-edit/dd-of + known write-scripts + typed state-movement like `backlog.py --state`) and gate ONLY those; let reads and versioning that merely name a governed path pass. Honest-scope limitation (declared, not hidden): an arbitrary-code write — a python heredoc opening a governed path in 'a'/'w' mode — is NOT detectable by a command-substring classifier; the Bash classifier gates the enumerable write signals only, and the typed Edit/Write path remains the strongly-gated primary mutation surface. Composes the sovereign-gate narrow+fail-closed posture + Syntax-Semantic-Collapse (a command's tokens carry execution semantics, but mention ≠ execution).

<!-- promoted from cpr_mutation_gate_classifier_gates_the_write_signal_not_the_path_mention_tic407 (tic 407→409, /review 409). Source: audit-logs/governance/borns-tic407-gate-precedence-and-classifier.md. Evidence: proven tic 407 — narrowed the boot-read-gate Bash classifier (CGG 41af34a) from "any command mentioning a governed path" to "an actual write to a governed surface"; self-test 23/23 + live end-to-end through the installed hook (read ledger→allow; git add+commit→allow; >>queue.jsonl→gated/BLOCK exit 2 for a no-receipt entity; Edit ledger→gated). Composes sovereign-gate narrow+fail-closed + Syntax-Semantic-Collapse (canonical KI). Carries an honest arbitrary-code-write-gap clause. Band: STRUCTURAL. Confidence_tier: reinforced. -->

**Refinement — a gate's operative PARAMETER resolves from authoritative state, not the command's data payload (tic 518 born → /review 519 PROMOTE-as-refinement, Architect-gated):** The tic-resolution sibling of the same over-matching footgun. The boot-read mutation gate parses a tic-like token (`_tic<N>`) out of the COMMAND STRING (a cpr_id / file path) and demands a boot receipt for that EMBEDDED historical tic — even when a valid receipt exists for the real session tic. The operative tic IS the SESSION tic (authoritative state: cgg-tic-counter); a tic embedded in an argument is DATA, not the clock. Just as the parent gates the WRITE SIGNAL not the path MENTION, a gate must resolve its operative PARAMETER from authoritative session/runtime state, never by scraping it from the command's free-form payload. Do NOT satisfy the misfire with a false historical-tic receipt — that pollutes the boot-receipt / drift-audit lane with a non-session tic; the correct workaround is a tic-free / session-tic-bearing path (e.g. invoke a script BY PATH so its `_tic<N>`-bearing ids live in file content, not the command string), and the real fix is physics-layer (resolve operative tic from session state). This is a perception-layer guard that fires only after the damage (#footgun-guard-at-perception-layer-warns-after-the-footgun-already-fired); recurrence is guaranteed at every /review writeback that names a tic-bearing CogPR/born id. (Validated tic 518: tripped by `review-promote-writeback --cpr-id cpr_..._tic401`; physics-layer fix backlogged as `bk-boot-read-gate-operative-tic-from-session-state`. The path-by-invocation workaround was re-exercised at /review 519's own queue writeback.)

<!-- promoted from cpr_boot_read_gate_resolves_tic_from_command_content_not_session_state_tic518 (tic 518→519, /review 519). Source: audit-logs/governance/borns-tic518-boot-read-gate-tic-from-command-content.md. Refines mutation-gate-classifier-gates-write-signal-not-path-mention (parameter-from-authoritative-state, the tic-resolution sibling); composes footgun-guard-at-perception-layer + Syntax-Semantic-Collapse. Build-side fix backlogged. Band: COGNITIVE. Confidence: 0.8. Architect-gated. -->

**Refinement (build-side closure) — the content-derived re-key keys on the WRITE TARGET, and a narrow PATTERN over a wide SCOPE still over-matches (tic 520 born → /review 520 PROMOTE-as-refinement, Architect-gated):** The physics-layer fix the tic-518 refinement backlogged (`bk-boot-read-gate-operative-tic-from-session-state`) LANDED at tic 520 (CGG `18b595d`), and building it sharpened the lesson twice. (1) PARAMETER-RESOLUTION EXTENSION: the parent gates the WRITE SIGNAL not the path MENTION at *classification* time; this extends the same discipline to *parameter resolution* — a gate's bounded content-derived override (here the legitimate tic-504 born work-tic re-key, needed because /cadence Step 0.5 advances current_tic past the Step-2 born write) must key on the actual WRITE TARGET — `file_path` for Edit/Write/NotebookEdit, or the redirect/tee/sed-i/dd DESTINATION for Bash — never on a tic appearing elsewhere in the command (an argument, a `--plan-file` read ref, a `git add` versioning mention). (2) SCAN-SCOPE SUB-LESSON: the pre-520 code ran a *narrow* regex (`borns-tic(\d+)-`) over the *whole* command string (`fp or cmd`), so narrowness of the PATTERN did not save it — a narrow pattern over a wide SCOPE still over-matches. The default parameter source is authoritative SESSION STATE; the content-derived re-key is a bounded exception scoped to the write target, with teeth preserved (a born for an un-receipted work-tic still blocks). Reproduced live during its own fix: the un-synced installed gate blocked the fixing session's own diagnostic Bash because the command literally contained `borns-tic401-`. (Validated tic 520: `_born_work_tic(fp or cmd)` → `_born_write_target_tic(tool, fp, cmd)`; 39 self-checks + 4 e2e — footgun cmd ALLOWs at session tic, born@session ALLOWs, born@un-receipted BLOCKs, source-edit ungated; synced byte-identical.)

<!-- promoted from cpr_content_derived_parameter_rekey_keys_on_write_target_not_command_content_tic520 (tic 520 → /review 520 PROMOTE-as-refinement, Architect-gated batch [AskUserQuestion approval]). Source: audit-logs/governance/borns-tic520-boot-read-gate-rekey-keys-on-write-target-not-command-content.md. Build-side closure of the tic-518 parameter-from-authoritative-state refinement (bk-boot-read-gate-operative-tic-from-session-state DONE, CGG 18b595d); adds the write-target discriminator + the narrow-pattern-over-wide-scope sub-lesson. Composes footgun-guard-at-perception-layer (this IS the physics-layer fix that guard pointed at). Band: COGNITIVE. Confidence: 0.85. signer ent_homeskillet-c48. -->

---

## Precondition-Gate Perimeter Completeness — Cover Every Review-Input Surface or Declare the Exemption
<a id="precondition-gate-perimeter-completeness"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=500 -->

A precondition gate (boot-read-gate class) that classifies what it guards by a fixed allowlist of governed-STATE surfaces leaves review-INPUT surfaces un-guarded — borns, candidate-spec proof-verdicts, counsel/review receipts, route manifests, bench packets all become `/review` input under no read-attestation while the state mutation for the *same arc* blocks. **The defect is not narrowness — it is SILENT ASYMMETRY:** the same arc can author the review input the human gate consumes without the attestation the gate demands for the state write. **The law is the disjunction:** a precondition gate must EITHER (A) cover every surface that becomes counsel/review input, OR (B) explicitly declare why a given surface is exempt — and the asymmetry must be a NAMED design choice, never a silent allowlist gap. The implementation arm (extend the allowlist vs declare the exemption — e.g. "a born is a reversible birth that `/review` re-reads fresh, so the load-bearing attestation is at review-TIME not write-TIME") is DOWNSTREAM of the law and separately gated; the primitive is the disjunction, not either arm. **Mechanical acceptance-check clause** (what "covered" means for an iteratively-re-run observer surface — merged from the observer-coherence sibling): an observer's output is not admissible as review input until internally coherent — (1) supersede chain marked (latest→final, run snapshots immutable per-timestamp; no stale-run ambiguity); (2) NO run-glob in governed receipts (cite `run_id` + status, never `*-tic-N`); (3) control-plane lifecycle-before-token routing (own a file by its lifecycle role, not by what it mentions; never overload one enum across distinct roles); (4) downstream counts intact. **Hold the tension:** do NOT collapse to "gate everything" — that re-introduces the tic-407 over-block; the narrow posture is correct, the gap is the undeclared asymmetry. This is the **SYMMETRIC COMPLEMENT** of *the mutation-gate classifier* (tic 407 fixed OVER-block on the Bash-read side — "gate the write signal, not the path mention"; this names UNDER-block-or-undeclared on the Edit/Write review-input side). Refines the boot-read invariant + the sovereign-gate narrow+fail-closed posture + the federation physics-layer-enforcement principle (enforcement at the execution boundary must cover the *whole* boundary, or declare its negative space) + Presence/Observation *watcher-scope-must-be-declared*; the acceptance checks compose *Authoritative-set readers must read the manifest*. **Terminology-as-governance-surface sub-ray** (carried from the merged observer-coherence born, may split at a future /review): a load-bearing artifact whose NAME or metaphor can be misread carries governance risk even when its SUBSTANCE is correct; the fix is a rename recommendation routed through the gate, not a silent rename. Lock line: *Silent asymmetry is the defect, not narrowness — cover every review-input surface, or declare the exemption.*

**Work-tic re-key refinement (tic 504 — the dynamic-keying third arm).** The disjunction above (cover OR declare exemption) is a *static perimeter* law; a third failure axis is *dynamic* — when the gate keys its attestation on a MOVING reference (`current_tic` from the live mandate) and a process advances that reference BEFORE the write it guards, the gate fires a spirit-false-positive on its own best-case write. Concretely: `/cadence` Step 0.5 emits the next tic, THEN Step 2 writes the session's born (`borns-tic<N>-…`); the gate read `current_tic` = the just-emitted NEXT tic (whose boot receipt cannot exist yet — that boot is the next session) and blocked the born, forcing a routine audited OVERRIDE every cadence — which **erodes the override's signal** (a routine exception is no exception). The fix is NOT a blanket born-exemption — the arm-B *example* above ("a born is a reversible birth, attest at review-TIME") would over-exempt perception-debt-laden *mid-session* born writes, re-opening the hole. It is a NARROWER third arm: **key the attestation to the artifact's OWN work-tic.** The born encodes its work-tic in its filename (`borns-tic<N>-`), and the CLOSING session DID receipt tic N at boot; the gate checks tic N's receipt, not `current_tic` — a legitimate session-close capture passes, a born for an un-receipted tic still BLOCKS (teeth held), non-born writes keep `current_tic` (unchanged). Wired tic 504 (`boot-read-gate.py` `_born_work_tic`; dual-proven: close-capture allow + un-receipted-tic block + non-born unchanged + self-test). **Lock line addendum:** *a gate keying on a moving reference must anchor attestation to the guarded artifact's own work-tic, never the advanced reference — and must never make its own highest-context, lowest-debt write the routine exception.*

<!-- promoted from cpr_precondition_gate_covers_all_review_input_surfaces_or_declares_exemption_tic500 (PROMOTE) + cpr_iterative_observer_must_be_internally_coherent_before_becoming_review_input_tic500 (MERGED-in as the mechanical acceptance-check clause; original marked absorbed). Source: audit-logs/governance/borns-tic500-boot-read-gate-perimeter-covers-review-input-or-declares-exemption.md + borns-tic500-observer-coherence-before-counsel-input.md. /review 500: Architect counter-strike OVERRODE the reviewer's DEFER — the A/B implementation arm is not a blocker; the law is the disjunction (verdict-batch ids 5h7c2b/gbx3iv/8ufvsf). Evidence: tic 500 — boot-read-gate.py blocked `backlog.py add --state` (governed-state, via the --state matcher) but let the STRIKE-3 spec-verdict Edit + the counsel-verification-receipt Edit + two born Writes land un-gated (review-input surfaces match none of _DOCTRINE_PATH_MARKERS); grounded by reading ~/.claude/hooks/boot-read-gate.py. Implementation arm tracked at bk-boot-read-gate-review-input-perimeter (hook change is itself /review-gated — changing an enforcement perimeter is governance). Band: PRIMITIVE. Confidence_tier: reinforced (2 sources merged). signer ent_homeskillet-c48 (claude-opus-4-8). -->

<!-- REFINED tic 504 (work-tic re-key third arm) from cpr_review_input_perimeter_must_grace_the_cadence_close_born_write_tic502 (PROMOTE-as-refinement). /review 504: Architect-directed early pass; verdict reached by six-ray strike (NOT crouched on a menu) — the apophatic ray proved the lesson is NOT fully derivable from the parent: the parent's arm-B example (blanket born-exemption, attest-at-review-TIME) would OVER-exempt mid-session born writes; the net-new content is the DYNAMIC-keying axis + the work-tic-rekey resolution (a third arm beyond cover/blanket-exempt) + the don't-routinize-your-own-best-write corollary. Conformation n>=3 (self-reported tic 502; overrides 0dc5db25 @ tic 503, 11c403b6 @ tic 504-keyed). Fix wired+tested BEFORE inscription (fix-then-present): boot-read-gate.py _born_work_tic — close-capture allow + un-receipted-tic block (teeth) + non-born unchanged + 3 self-test checks green; synced byte-identical. Source: queue cpr_review_input_perimeter_must_grace_the_cadence_close_born_write_tic502 (extracted->promoted). Band: PRIMITIVE. signer ent_homeskillet-c48 (claude-opus-4-8). -->

**Cover-arm three-move refinement (tic 505 — how to faithfully EXTEND the cover arm).** When EXTENDING the gate's coverage (arm A) to a NEW class of surfaces, the faithful + over-block-safe implementation is THREE moves, not one: **(a) cover-by-path** the members the path/name matcher already catches; **(b) cover-by-content** the members the path matcher MISSES but a content/signal check catches (the silent-asymmetry hole hides here — a path-only extension leaves content-only members un-gated while *looking* complete); **(c) declared exemption** for the residue (arm B), named, never a silent gap. Implementing the cover arm as path-only is the recurring under-block: it reads as "coverage extended" while a whole content-identified member class stays ungated. **Lock line:** *extending the cover arm is path-coverage AND content-coverage AND a declared-exemption residue — path-only coverage is silent under-block wearing the look of completeness.*

<!-- REFINED tic 505 (cover-arm three-move) from cpr_precondition_perimeter_extend_by_path_plus_content_plus_declared_exemption_tic502 (PROMOTE-as-refinement, /review 505, Architect-gated). Refinement edge (NOT net-new parent; SKIP≠DISCARD): decomposes arm A ("cover every surface") into path-coverage + content-coverage + declared-exemption, naming the path-only under-block hole. Sibling to the tic-504 work-tic dynamic third arm (above). Source: queue cpr_precondition_perimeter_extend_by_path_plus_content_plus_declared_exemption_tic502 (extracted->promoted). Band: COGNITIVE. signer ent_homeskillet-c48 (claude-opus-4-8). -->

**SKIP-with-home note — a "recorded" boot receipt is not a "cleared" mutation gate; the ladder-only path does not flip `full_boot_injection_read` (tic 532 born → /review 537 SKIP-with-home).** Emitting `boot-receipt.py` with `--ladder-explainback` returns `status=recorded, missing_fields=[], "boot loop closed"` — every visible success signal — yet the first governance mutation still BLOCKS on `boot-read-gate.py` because the ladder path records the drift-audit sentence WITHOUT flipping `full_boot_injection_read`; only the `--full-boot-read` path (with `--boot-read-mode full --chunking surface_typed`) clears the gate. A clean-looking receipt with `missing_fields=[]` is NOT a gate-cleared signal. This is the Presence/Observation *observed-success-does-not-prove-content-validity* guard on the receipt surface itself. Homed here, not promoted (derivable-PARTIAL from the boot-read invariant + Presence/Observation).

<!-- SKIP-with-home /review 537 (durable home, NOT promoted-to-doctrine): cpr_boot_receipt_recorded_is_not_mutation_gate_cleared_emit_full_boot_read_at_boot_tic532 (queue.jsonl, extracted->rejected). Reason: derivable (PARTIAL, author-stated) from boot-read invariant + Presence/Observation Fallacy Guard; single-cycle. Home loads at the boot-receipt locus. Source: audit-logs/governance/borns-tic532-boot-receipt-full-read-flag.md. Re-evaluate -> PROMOTE on a 2nd occurrence of the two-path receipt footgun. Band: COGNITIVE. -->

---

## Shape Fingerprint Provenance
<a id="shape-fingerprint-provenance"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Composite shape hash `sha256(content_hash + ctime + birthtime + inode)` creates a deterministic fingerprint robust to single-axis spoofing. File content alone can be mutated without changing hash (if the mutator knows the hash). File metadata alone can be spoofed (ctime touched, birthtime forged). Inode alone can change during file operations (copy, mv with recreation). The composite prevents an adversary from controlling all four axes simultaneously without triggering visible divergence. This forms one leg of a sentinel-integrity triple with Read-Side Verification Complement and Context-Aware Severity Classification.

<!-- promoted from cpr_shape_fingerprint_provenance_tic155 (tic 155→167). Source: pipeline integrity audit (tic 155). Sentinel-integrity triple cross-reference: Read-Side Verification Complement and Context-Aware Severity Classification (tic 155→167). Band: COGNITIVE. -->

---

## Read-Side Verification Complement
<a id="read-side-verification-complement"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Append-only ledgers provide write-side integrity but without read-side chain verification a malicious or buggy reader can present out-of-order entries as canonical. Read-side verification closes the loop: chain-hash check (each line's hash includes prior line's hash), sequence number validation (entries appear in declared order), and monotonicity enforcement (no sequence number skips). This is the verification complement to JSONL Atomic Writes (CogPR-8), which addresses write-side integrity only. Read-side verification ensures the consumer sees the ledger as written, not a reshuffled or truncated version the reader chose to present.

<!-- promoted from cpr_read_side_verification_complement_tic155 (tic 155→167). Source: pipeline integrity audit (tic 155). Refines JSONL Atomic Writes (CogPR-8). Sentinel-integrity triple: pairs with Shape Fingerprint Provenance and Context-Aware Severity Classification. Band: COGNITIVE. -->

---

## Context-Aware Severity Classification
<a id="context-aware-severity-classification"></a>
<!-- ledger-tags: authority_class=forensic_and_drift_investigation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Pattern-matching severity ("if path contains X then critical") produces false escalation under remediation-era state changes. A file path containing "malware" is not inherently critical if the context is "archived forensic report" or "historical threat database." Context-aware classification requires knowing: what is this file for, who owns its lifecycle, what operational state is active now. A path appearing in active infection context is critical; the same path in post-remediation archival context is informational. This reduces noise while preserving signal. Validated against tic 159 runtime_drift_check: 71 findings, 0 critical (correctly downgraded from pattern-match false positives), 16 warning, 55 info. Sentinel-integrity triple: completes the integrity verification surface with Shape Fingerprint Provenance and Read-Side Verification Complement.

<!-- promoted from cpr_context_aware_severity_tic155 (tic 155→167). Source: tic-159 runtime_drift_check validation. Sentinel-integrity triple: Shape Fingerprint Provenance, Read-Side Verification Complement, Context-Aware Severity Classification. Band: COGNITIVE. -->

---

## Inbox Triple-Source Sync
<a id="inbox-triple-source-sync"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Inbox archive operations must propagate across three sources of truth: (1) filesystem (WAIT/ACTIVE/DONE prefixes on files), (2) inbox-registry.json (canonical state enumeration), (3) hook-detection state (what the hooks know about). Failure to sync produces phantom state where one source disagrees with the others and hooks re-detect already-archived items as stale. The three sources can diverge silently: a file moved from WAIT to DONE (filesystem state correct), registry updated (registry state correct), but hook-detection still thinks it's WAIT because the hook fired before the registry update and cached its findings. Protection: any archive operation that modifies one source must atomically update all three. Validating archive completeness requires comparing across all three sources, not trusting any one surface.

<!-- promoted from cpr_inbox_triple_source_sync_tic160 (tic 160→167). Source: inbox operations audit (tic 160). Operationalizes atomic writes principle (CogPR-8) at the multi-surface level. Band: COGNITIVE. -->

---

## Two-Run Spec-Gate Geometry
<a id="two-run-spec-gate-geometry"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Spec-first with operator review gate between Run 1 (spec authoring) and Run 2 (execution) materially separates spec production from execution risk. Cost: extra swarm cycle + operator review budget. Benefit: spec drift is caught at review time rather than at execution time, and the spec becomes a standalone artifact operators can reference, amend, or reject without collateral damage to execution agents. This geometry is operationally distinct from Spec-First Parallel Swarm (CogPR-140): the latter is one run with the spec as scaffold; this is two runs with the spec itself as a reviewable deliverable. Once a constitutional pattern is validated at n=1 (pilot survives operator gate + first execution boundary), subsequent adopters use lighter-cadence rollout (single-pass author + verify) until the convention shows transferability stress.

<!-- promoted from cpr_two_run_spec_gate_validated_tic165 (tic 164-165→167). Source: tic-164 spec swarm + tic-165 Run 2 execution. Validated geometry at 5-agent swarm scale. Band: COGNITIVE. -->

---

## Constitutional-Office Swarm Differentiation
<a id="constitutional-office-swarm-differentiation"></a>
<!-- ledger-tags: authority_class=subagent_and_swarm_delegation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Constitutional-office swarm agents with distinct jurisdictional lenses (Ladder Auditor/coherence, Civil Engineer/mechanics, CBUX Steward/encounter, Videographer/narrative) produce genuinely differentiated spec fragments — not just same-output-in-different-voice. Jurisdictional distance matters more than apparent topical relevance. When selecting offices for spec-writing swarms, a narrative lens on a schema question surfaces structural failures that pure governance lenses cannot see. Validated: Videographer's narrative-capture lens identified a structural tier-boundary visibility concern that all three governance-facing offices missed despite reading the same anchor inputs.

<!-- promoted from cpr_constitutional_lens_differentiation_tic165 (tic 165→167). Source: tic-164 spec swarm. Refines Spec-First Parallel Swarm (CogPR-140). Band: COGNITIVE. -->

---

## Open Question Classification (Probe-First Test)
<a id="open-question-classification-probe-first-test"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Open questions in specs classify by what resolves them: (a) operator-judgment (require human decision), (b) evidence-probe (resolvable by small filesystem or state inspection), (c) deferred (non-blocking, carry to later tic). Type (b) should not present as operator-blocking. Protection: when drafting OQs during synthesis, apply a probe-first test — can this be answered in one bash command? If yes, classify as evidence-probe and resolve inline rather than routing to operator. This prevents false-blocking pressure at review gates.

<!-- promoted from cpr_oq_filesystem_probe_tic165 (tic 165→167). Source: tic-164 spec synthesis. Band: COGNITIVE. -->

---

## Spec as Tone Exemplar
<a id="spec-as-tone-exemplar"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When a spec also functions as the tone exemplar for downstream deliverables that will imitate it, spec-level tone discipline matters more than discipline on comparable non-exemplar specs. A spec that says "do not use metaphors in procedural sections" while itself using metaphors licenses downstream agents to do the same. Protection: apply the spec's own tone rules to the spec itself before operator review, not just to the deliverable. Cost: one surgical edit. Benefit: prevents drift of the norms the rollout is establishing.

<!-- promoted from cpr_spec_as_tone_exemplar_tic165 (tic 165→167). Source: tic-164 spec swarm. Validated in practice. Band: COGNITIVE. -->

---

## Boundary-Aware Body Extraction
<a id="boundary-aware-body-extraction"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Spec validation gates that use hardcoded line offsets for body extraction (sed -n 'N,$p' with fixed N) break silently when the mutation being validated changes the boundary position. Protection: use boundary-aware extraction anchored on structural delimiters (awk on '---' fences, closing tag markers, etc.) rather than line-number offsets. The fragility is not sed per se — it's the implicit assumption that the mutation preserves the line position of the boundary being measured across. Any spec gate that encodes "verify content below line N" inherits this assumption.

<!-- promoted from cpr_spec_gate_line_offset_fragility_tic165 (tic 165→167). Source: tic-165 Run 2 execution, spec.yaml gate_b2 mechanism failure. Band: COGNITIVE. -->

---

## Verifier Install Path via Sync Manifest
<a id="verifier-install-path-via-sync-manifest"></a>
<!-- ledger-tags: authority_class=sync_and_install_parity | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Verifier gates that diff canonical source against runtime-installed artifacts must discover the install target via the same mechanism as the syncing tool (sync-manifest.json lookup), not hardcode a parallel path assumption. Specs assuming an install path create a second source of truth that can drift from the actual sync mechanism without either side detecting the drift. Protection: any Gate-E-class parity check should resolve the install target from runtime-sync's manifest, inheriting the sync tool's canonical knowledge of where files land.

<!-- promoted from cpr_verifier_install_path_via_sync_manifest_tic165 (tic 165→167). Source: tic-165 Run 2 execution, spec.yaml gate_e mechanism. Extends CogPR-37 (Runtime Sync Parity Verification) and CogPR-40 (envelope pattern). Band: COGNITIVE. -->

---

## Lighter-Cadence Rollout Post-Validation
<a id="lighter-cadence-rollout-post-validation"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Once a constitutional pattern is validated at n=1 (pilot survives operator gate + first execution boundary), subsequent adopters should use lighter-cadence rollout (single-pass author + verify, no two-run gate geometry) until the convention shows transferability stress. The two-run gate exists to catch mechanism bugs at the spec↔execution seam during initial constitutional bootstrapping. Once the seam is exercised under load, the cost of repeating the geometry per-adopter is operator-attention drain that returns no marginal safety value. Verification gates remain mandatory; the adversarial swarm structure does not. This scales to multi-skill batch conversions without quality loss: tic 167-168 completed 6 skill conversions in 3 batches in ~40 minutes with zero verification gate failures across all 6 adopters, confirming that batch geometry (3 skills per commit) produces identical verification surface with dramatically lower operator-attention cost per adopter. Convention-accrual throughput scaled from ~2 adopters/tic (pilot) to 6 adopters/tic (batch), confirming that once the spec↔execution seam is exercised under load, per-adopter two-run cost returns no marginal safety value.

<!-- promoted from cpr_lighter_cadence_post_validation_tic166 (tic 166→167). Source: tic-166 Run 3 rollout (/review and /inbox adoption). Band: COGNITIVE. -->
<!-- absorbed from cpr_batch_conversion_lighter_cadence_scales_tic168 (tic 168→211). Source: tic-168-run4-5-6-batch. Strengthens lighter-cadence doctrine with multi-skill batch-throughput evidence (6 skills, 3 batches, ~40 min, 0 failures). Band: COGNITIVE. -->

---

## Sentinel-Integrity Triple Summary
<a id="sentinel-integrity-triple-summary"></a>
<!-- ledger-tags: authority_class=forensic_and_drift_investigation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Three validations form a coherent integrity surface: (1) Shape Fingerprint Provenance — hash composition prevents single-axis spoofing, (2) Read-Side Verification Complement — ledger reading verifies chain integrity, (3) Context-Aware Severity — classification prevents false escalation from stale paths. Applied together, they form a multi-layer detection surface. Each layer catches what the others miss: content tampering, reader manipulation, and context-blind pattern matching.

---

## Centroid-Ray Semantic Primitive
<a id="centroid-ray-semantic-primitive"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

A centroid is the weighted average position of a semantic cluster in a high-dimensional space (e.g., value position, computational cost, governance scope). A ray is a direction vector from the centroid toward an edge case or boundary condition. Centroid-ray analysis decomposes complex multi-dimensional design questions into (1) where is the gravitational center of this design space? and (2) what are the critical rays we must defend against? This primitive is reusable across arena design, capability assessment, and specification synthesis. First validated in VPL arena geometry (value-position lattice) with 8 constitutional actors; generalized to agenda conflict analysis and scope boundary definitions.

<!-- promoted from cpr_ec5e0bb4676a6867 (tic 171→172). Source: session:vpl-centroid-ray-formalization. Band: COGNITIVE. -->

---

## Collapse Zone vs Sibling Overlap Distinction
<a id="collapse-zone-vs-sibling-overlap-distinction"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

In multi-axis design spaces, a collapse zone is a region where multiple axes converge such that orthogonality breaks down (e.g., two previously independent variables become correlated). Sibling overlap is a region where two design entities share a boundary but maintain distinct identities. The distinction matters: collapse zones are failure modes that demand refactoring; sibling overlaps are natural boundaries that may be acceptable design interfaces. Failure to distinguish produces either over-design (treating normal overlap as catastrophic) or blindness to genuine collapse hazards.

<!-- promoted from cpr_e067f0e9efb86951 (tic 171→172). Source: session:vpl-centroid-ray-formalization. Band: COGNITIVE. -->

---

## Negative Contour Via Is-Not Clause
<a id="negative-contour-via-is-not-clause"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When defining a semantic boundary (what a concept is), explicit is-not clauses often sharpen meaning better than positive definition. A data structure is NOT a service (no stateful lifecycle), is NOT a schema (no validation), is NOT a contract (no guarantee) — these negations together create a boundary that positive definitions might miss. Particularly useful when a concept is frequently confused with neighbors. Applies to spec writing, CLAUDE.md boundaries, and architecture documentation.

<!-- promoted from cpr_2d42a4621f4cc4b1 (tic 171→172). Source: session:vpl-centroid-ray-formalization. Band: COGNITIVE. -->

---

## Semantic Primitives Precede Mathematical Closure
<a id="semantic-primitives-precede-mathematical-closure"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

In specification design, establish semantic primitives (named concepts with boundaries) before deriving mathematical models. Attempting to derive formulas without semantic agreement produces math that is technically correct but semantically incoherent — the formula is closed but it measures the wrong thing. Order: (1) name the thing, (2) define what it is and what it is NOT, (3) identify the dimensions, (4) then derive mathematical models. Validated in VPL bracket design where semantic confusion about "value" appeared twice before term definitions were formally inscribed.

<!-- promoted from cpr_9271cbb793058ebd (tic 171→172). Source: session:vpl-centroid-ray-formalization. Band: COGNITIVE. -->

---

## Cross-Centroid Ray Recurrence Mining
<a id="cross-centroid-ray-recurrence-mining"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When the same ray (same boundary condition, same edge case) appears in multiple semantic clusters (multiple domain problems, multiple specification contexts), it becomes a general principle worth mining and naming. Recurrence is the signal that a ray is structural, not accidental. Three cross-domain instances of the same ray justifies extracting it as a reusable primitive. Applied to pattern mining and CogPR extraction: rays that recur across 3+ problem domains are federation-level doctrine candidates.

<!-- promoted from cpr_705787965bf1712e (tic 171→172). Source: session:vpl-centroid-ray-formalization. Band: COGNITIVE. -->

---

## Skill Body Is Sole Arg Parser
<a id="skill-body-is-sole-arg-parser"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Claude Code skill runtime does NOT enforce argument schemas declared in frontmatter `arguments:` field. The frontmatter field is documentation and CI hint, not a parser. The skill body itself is the sole argument parser — the skill code receives raw `arguments` string and must parse it according to whatever grammar the skill implements. Do not assume the runtime pre-validates or pre-parses arguments against the schema. This is a design principle, not a limitation — it lets skills implement context-aware parsing strategies that a fixed schema validator cannot support.

<!-- promoted from cpr_5b4fc68a54f05b2d (tic 171→172). Source: session:skill-invocation-audit-tic170. Band: COGNITIVE. -->

---

## Undeclared Args Classify by Projection
<a id="undeclared-args-classify-by-projection"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When a skill is invoked with arguments not declared in the `arguments:` frontmatter field, those arguments appear in the skill body as part of the raw `arguments` string. The skill must classify them by projection: (1) intentional extra args that the caller knows about (call site competence signal), (2) accidental extra args from caller confusion (possible bug), (3) reserved args for future use (forward compatibility). Projection is a skill-level decision, not a runtime validation. Undeclared args are not errors unless the skill chooses to treat them as such.

<!-- promoted from cpr_7e2a40d83256d618 (tic 171→172). Source: session:skill-invocation-audit-tic170. Band: COGNITIVE. -->

---

## Arguments Frontmatter Is Decorative
<a id="arguments-frontmatter-is-decorative"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

The `arguments:` field in skill frontmatter is decorative for governance and documentation purposes. It is NOT enforced by the runtime and does NOT restrict what callers can pass. Skills should document their expected arguments in frontmatter for clarity, but the skill body must handle the actual runtime `arguments` string with full parser responsibility. Callers are not restricted to documented arguments — undeclared args pass through silently. This design allows skills to be forward-compatible with future argument additions without runtime parser changes.

<!-- promoted from cpr_6e68f18c7ca09069 (tic 171→172). Source: session:skill-invocation-audit-tic170. Band: COGNITIVE. -->

---

## Extractor Surface Schema Contract
<a id="extractor-surface-schema-contract"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Tools that extract governance artifacts (CogPRs, signals, bench packets) from canonical surfaces must declare their input schema contract — which files they read, what section markers they search for, what output structure they produce. Without declared contracts, extractors silently miss new surfaces or emit incomplete results when sources change. The contract is a typed specification that extractors can validate against at load time, preventing silent starvation. Extend CogPR-140 (Spec-First Parallel Swarm) to include surface contracts as part of spec commitment.

**Refinement — YAML block-scalar fold-failure (tic 484 → /review 492, `cpr_cpr_extract_does_not_fold_yaml_block_scalars_silent_born_content_loss_tic484`).** A named sub-class of the silent starvation this contract guards: `cpr-extract.py`'s born-field parser did not FOLD YAML block scalars — a field authored as `lesson: >` (folded) or `lesson: |` (literal) followed by an indented body was extracted as the bare indicator char (`>` / `|`), silently DISCARDING the entire body. The extractor declared `source` + `lesson` as its required schema (see *Extractor Schema Field Mapping*), but its reader did not implement YAML block-scalar value-grammar, so a schema-valid born passed the presence check while losing all content — presence ≠ fulfillment at the parser layer. Fix landed tic 485 (`bk-cpr-extract-block-scalar-fold`). The discipline this sharpens: an extractor's declared input contract must specify not just WHICH fields it reads but the FULL value-grammar it parses (block scalars, multi-line, quoting) — declaring a field whose value-form it cannot actually read is the contract's own failure mode.

<!-- promoted from cpr_5cf38169077f731d (tic 171→172). Source: session:enrichment-pipeline-audit-tic171. Band: COGNITIVE. -->
<!-- refinement promoted from cpr_cpr_extract_does_not_fold_yaml_block_scalars_silent_born_content_loss_tic484 (tic 484 → /review 492). Source: bk-cpr-extract-block-scalar-fold (fix landed tic 485, commit). Refines Extractor Surface Schema Contract + Extractor Schema Field Mapping — adds the YAML-block-scalar fold-failure as a named sub-class (presence≠fulfillment at the parser layer). Band: COGNITIVE. Architect-approved AskUserQuestion tic 492, signer ent_homeskillet-c48. -->

---

## Extractor Anomaly Self-Reporting
<a id="extractor-anomaly-self-reporting"></a>
<!-- ledger-tags: authority_class=forensic_and_drift_investigation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Extractors that produce zero output or anomalous counts (extreme divergence from expected range) must emit explicit diagnostic output to stderr or a dedicated anomaly log, not silence. Silent zero-output is worse than failure — it looks like success. Implement anomaly self-reporting as a fallback pathway: if output count is 0 or N times the expected range, switch to diagnostic mode and dump what was searched, what was matched, and what boundary conditions failed.

<!-- promoted from cpr_1cb129067984ef9d (tic 171→172). Source: session:enrichment-pipeline-audit-tic171. Band: COGNITIVE. -->

---

## Queue Index Status Coverage Discipline
<a id="queue-index-status-coverage-discipline"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When building indexed views of the queue (e.g., build_queue_index.py), the coverage must be explicit: which status values are indexed, which are aggregated, which are ignored. Each query against the index must declare what status categories it includes. A query "how many promotions were approved this tic?" is answering a different question than "how many promotion candidates existed?" — the first counts promoted entries, the second counts promoted + deferred + pending. Index metadata must enumerate what the index covers so downstream consumers can verify they are using the correct view.

<!-- promoted from cpr_915fd5c4bdfc47b0 (tic 171→172). Source: session:enrichment-pipeline-audit-tic171. Band: COGNITIVE. -->

**Refinement (tic 523, /review-gated) — incomplete coverage RESURRECTS terminal items, via TWO blindness vectors, in the state-COMPILER too (not just the index).** `queue_state_compile.py` is a second coverage surface under this discipline, and its taxonomy was frozen at tic 222 while the queue lexicon grew. A status-derivation reader that cannot SEE a terminal disposition falls through to the latest ACTIVE row underneath and resurrects a settled item into `live_now` — silently inflating the live count for EVERY compiler-fed reader (bench-packet, statusline, governance_query, ripple-assessor). At tic 523 this read 81 live_now vs 38 genuine — 43 resurrected. TWO independent vectors, one quiver (*a terminal disposition is structurally invisible → latest active row wins*): (1) **taxonomy gap** — `TERMINAL_STATUSES` omitted `promoted_spec`/`implemented`/`resolved`/`withdrawn_inline_tracked`/`production_validated_*` (30 items); the status wasn't even a recognized state row. (2) **metadata over-exclusion** — `compute_id_state` partitioned `state_rows` on `is_metadata_row`, so a `promoted`/`absorbed` terminal row carrying a `triage_*` annotation (the tic-467 promoted-spec triage pass) was swept out as "metadata" (13 items); a status-bearing row is a state assertion regardless of annotations, so the partition must use `is_pure_metadata` (metadata-flagged AND status-less). FIX (tic 523): widen `TERMINAL_STATUSES` (+ `pending`→ACTIVE) and partition on `is_pure_metadata`; verified live_now 81→38, 0 newly-live, the 2 live Mogul audits + 36 deferred survive, 43 formerly-resurrected items now bucket `terminal_*`. META-RAY (the diagnostic discipline this earns): a **live/active count must be struck across its FULL status distribution, not a single status slice** — reading only the `deferred` slice concluded "compiler defaults deferred to live" and MISSED 43 resurrected terminals; the full-distribution strike is what revealed the shape (composes *rehydration is shape-derived, not grep* — the single-pole read is the degenerate child). Composes *Authoritative Count Discipline* + *Terminal-State Valve Pattern* + *Conductor-Score-Runtime Parity* (writers added terminal statuses; the reader taxonomy didn't catch up). NOT a new parent KI — a refinement-edge on this entry; widening was a /review doctrine decision per this discipline (tic-523 Architect gate), not a silent expansion.

---

## Emitter-Surface Declaration Contract
<a id="emitter-surface-declaration-contract"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Governance surfaces that can emit artifacts (MEMORY.md, arena reports, bench packets, session transcripts, decision briefs) must declare themselves as emitter surfaces in a registry. Without a registry, artifact extractors have no way to discover new emission surfaces — they remain hardcoded to legacy surfaces. The registry entry specifies: surface location, emission frequency, output format, artifact type, status field presence. This enables the extractor to validate and adapt when new emission surfaces come online.

<!-- promoted from cpr_564ecfbdb1ab6b39 (tic 171→172). Source: session:enrichment-pipeline-audit-tic171. Band: COGNITIVE. -->

---

## Enrichment Pipeline Silent Starvation Surface
<a id="enrichment-pipeline-silent-starvation-surface"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When an enrichment tool is meant to run periodically (e.g., pattern mining, queue analysis) but no invocation schedule exists, the tool operates in a starvation state: dormant but not erroring. Silent starvation produces zero output without signaling that nothing ran. Prevention requires: (1) explicit schedule declaration (when should this run?), (2) invocation audit trail (did it run last time it was supposed to?), (3) staleness detection (has output aged beyond expected cadence?). Without these three, enrichment tools fail silently and queue analysis degrades across tics without anyone noticing.

<!-- promoted from cpr_c1b5aaf9f9bb8742 (tic 171→172). Source: session:enrichment-pipeline-audit-tic171. Band: COGNITIVE. -->

---

## Baseline Classification Decoupled From Enrichment Firing Lane
<a id="baseline-classification-decoupled-from-enrichment-firing-lane"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | promoted_tic=428 | refines=enrichment-pipeline-silent-starvation-surface -->

A CogPR's classification baseline (class / tier / type — `lesson_class`, `target_surface`, `proof_type`) must be DECOUPLED from the full-enrichment firing lane: a strong candidate must be presentable and evaluable at the `extracted` stage via a thoughtful, NON-DUPLICATED baseline-metadata pass, and full enrichment + maturity-extension must be DEFERRED, OPTIONAL case-betterment tools (pieces that strengthen the case if it is not strong as-is), NOT mandatory firing-gates that block evaluation. PATTERN — at tic 427 the bench-packet intake reported `enrichment_covered: 0` on two strong, explicit, fully-authored borns purely because `cpr-enrichment-scanner.py` ran its deterministic-lite baseline classifier ONLY over HOLDING_STATUSES (`enrichment_needed` / `enrichment_eligible`); the borns sat at `extracted` (where cpr-extract writes Tier-1 candidates), so the class/tier/type baseline never generated until they were artificially advanced `extracted→enrichment_needed` — coupling the cheap classification to the expensive evidence-gather. CONSTRAINT — composes the *Enrichment Pipeline Silent Starvation Surface* (the lane it refines) + the deterministic-lite baseline classifier (tic 409, "the lane cannot starve") + *Conductor-Score-Runtime Parity* (doctrine says the baseline runs for every holding CPR, but `extracted` is a real pre-holding state the runtime skipped): the FIX is a split — the baseline classification pass runs for `extracted` AND holding (no evidence gathers, no queue mutation, no status change at `extracted`), while the heavy evidence-gather pass stays holding-only. EXPLANATION — the discriminator is "evaluate cheap, enrich on demand": classification is a cheap, deterministic, idempotent read that should be available the moment a candidate exists; enrichment is the expensive, deferred step spent ONLY when the baseline case is not strong enough to decide. Tying the cheap pass to the expensive pass's firing condition starves evaluation and forces wasteful advancement. EVIDENCE — BUILT tic 427: `BASELINE_STATUSES = {extracted} | HOLDING_STATUSES` + `get_extracted_baseline_cprs()` + an extracted-stage baseline-only pass in `scan_and_enrich` (`derive_baseline_classification` + `write_deterministic_lite_consolidated`, fail-soft, idempotent, never clobbers heavy Tier-1); unit-tested; synced (byte parity). DOGFOOD-CONFIRMED at /review 428: this very born landed at `extracted` and received its baseline (`lesson_class=engineering`) with no forced advancement, and bench-packet-prep reported 100% enrichment coverage on it. Net-new ray over the parent surface: the CLASSIFICATION baseline is decoupled from the ENRICHMENT firing condition, so a strong CogPR is evaluable pre-enrichment.

<!-- promoted from cpr_cogpr_baseline_metadata_decoupled_from_full_enrichment_tic427 (borns-tic427-baseline-decoupling.md, /review 428 PROMOTE-as-refinement, Architect-gated). Refines Enrichment-Pipeline-Silent-Starvation-Surface; composes the tic-409 deterministic-lite baseline + Conductor-Score-Runtime Parity (CGG Application). NOT a new compact-root KI (self-stated). Confidence tier: tentative (n=1, build landed tic 427, dogfood-confirmed tic 428). Band: COGNITIVE. -->

---

## Consolidate Pre-Flight Discipline
<a id="consolidate-pre-flight-discipline"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When `/consolidate` runs against an estate-spanning surface, two pre-flight disciplines apply before the consolidation produces an authoritative artifact. (1) **Pre-consolidation drift reconciliation** — when a surface contains internal drift between authoritative sources (e.g., spine.md says "X" while extended schema says "X′"), the drift must be reconciled against current state BEFORE consolidation flattens the surface; consolidating with unresolved drift inscribes contradictory claims into a single artifact. (2) **Scope walks repository tiers explicitly** — initial `/consolidate` invocations often scope to a single tier (e.g., one repo's docs) when the actual coherence boundary spans federation root + estate + domain + module; scope must walk repository tiers explicitly and the scope walk must be declared as a checklist before consolidation begins. The two disciplines compose: walk the tiers, reconcile the drift, then consolidate. Without pre-flight, consolidate produces lossy compression that looks authoritative.

<!-- promoted from cpr_pre_consolidation_drift_reconciliation_tic182 + cpr_consolidation_scope_walks_repository_tiers_tic182 (tic 182→183, MERGE_PROMOTE). Source: tic 182 cadence — Sovereign Starter source-level reconciliation; initial /consolidate scope walked one tier (canonical/) before architect correction expanded to canonical+canonical_developer+canonical_user. Tier=tentative→reinforced (2 instances on same surface). Companion to Volatility Handling Law L0-L5. Band: COGNITIVE. -->

---

## Conductor-Score-Runtime Parity (CGG Application)
<a id="conductor-score-runtime-parity-cgg-application"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When CGG governance doctrine names a discipline that the runtime scripts do not enforce, the gap is a parity problem with four mechanism classes — field passthrough, terminal-state valves, schema key signatures, and runtime ownership for behavior-bearing artifacts. The federation invariant captures the diagnostic frame; the CGG application is that every governance script under cgg-runtime/scripts/ must be auditable against these four axes. Field passthrough applies wherever producer→consumer pipelines exist (cpr-extract → bench-packet-prep → ripple-assessor → review-execute). Terminal-state valves apply at any JSONL queue read. Schema key signatures apply when extractors widen what counts as input. Runtime ownership applies to every executable in the cgg-runtime/scripts/ tree, including path-locked scripts that cannot be sync-installed. A patch landing in any one class without parity in the others produces silent governance drift even when surface scripts run successfully.

<!-- promoted from cpr_conductor_score_runtime_parity_tic185 (tic 185→188). Source: architect verbatim ("This is not a heartbeat problem. This is a conductor-score-runtime parity problem.") at tic 185 patch session. Validated by 4 patches: ripple-assessor 13-field passthrough, cpr-extract terminal-id valve + id preservation + anomaly report, bench-packet-prep terminal-state preference + dossier enrichment fields, build_queue_index runtime ownership declaration. 112/112 byte-identical canonical↔installed post-sync. Federation-side promotion at canonical/CLAUDE.md (parent invariant). Band: COGNITIVE. Confidence: 0.95. -->

---

## Headless Delegate Structured Emission Contract
<a id="headless-delegate-structured-emission-contract"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | born_tic=372 | promoted_tic=373 -->

When a headless delegate (`claude -p`) executes work and a downstream verifier requires a specific structured key per executed unit (e.g. `results.<cycle>` per Mogul mandate cycle), the delegate's prompt MUST explicitly force that key for EVERY executed unit — INCLUDING the trivial/empty-output case. Instruction asymmetry is the trap: if one unit's instruction pins "results.X MUST include {...}" (signal_scan) while a sibling says only "report ..." in prose (cache_refresh), the delegate folds the trivial case into prose and omits the structured key — and the strict verifier correctly FAILS work that actually ran. The empty-output case is the specific omission trigger: nothing structured to say is the easiest thing to drop. This is a Conductor-Score-Runtime-Parity instance — the score (verifier) demanded a key the conductor (prompt) never forced the runtime (delegate) to emit. The fix is structural at the PROMPT EMISSION CONTRACT (force the key per-unit, with the trivial case named explicitly), never by weakening the verifier. Refines Conductor-Score-Runtime Parity (CGG Application); composes Bounded Delegation Surfaces Default to Masking Bugs (the delegate's "done" elides a structural gap) and Gate Contracts (Not Vibes).

<!-- promoted from cpr_headless_delegate_structured_emission_contract_tic372 (tic 372→373, /review 373 PROMOTE as refinement edge). Source: mogul-runner.sh mandate tic-372 failure ("cache_refresh: not in structured report results"); transcript proved cache_refresh executed (sig_cache.refresh_complete emitted) but results carried 6/7 keys. Fix CGG 170c7cd (line 364 every-executed-cycle clause + cache_refresh MUST-include clause, synced 190/190). Non-derivability: distinct from Report-Generators-Must-Spot-Check (which is about TRUSTING a loader's output) — this governs the delegate's EMISSION CONTRACT, with the empty/trivial output case as the named omission trigger; refinement to Conductor-Score-Runtime-Parity, not a new parent. Band: COGNITIVE. Confidence_tier: reinforced (fix landed + synced). -->

---

## Terminal-State Valve Pattern
<a id="terminal-state-valve-pattern"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

JSONL queues that follow append-only with latest-entry-per-id-wins read semantics produce a class of bug where a stray later non-terminal row (typically status=extracted from a re-extraction pass) masks an already-settled terminal disposition (promoted/absorbed/superseded/rejected/deferred/dismissed/resolved/skipped). The fix pattern is symmetric: at the WRITE boundary (extractor) track the set of ids whose latest status is terminal and skip re-extraction for them; at the READ boundary (loader) prefer the latest TERMINAL entry per id, falling back to latest-overall only when no terminal exists. Apply both — write-side prevents the row from being created, read-side handles rows that already exist. Asymmetric application creates conformation drift: bench-packet sees the terminal correctly but a peer reader (e.g., ripple-assessor's grapple-proposals) could surface the stale extracted row, producing two different views of the same id. The tic 187 bench-packet-prep produced a 13-vs-39 asymmetry against raw queue_refresh — that 26-row delta is the valve doing its job at scale, not a bug. Refines Dedup-at-Write Using Canonical Identity (CogPR-117) by adding the read-side complement.

**Refinement (tic 337 — the verification boundary + danger-asymmetry):** the valve has a THIRD boundary beyond write (extractor) and read (loader): the VERIFICATION boundary, where an agent asserts the *presence or absence* of a row. A `break`-on-first-match scan for CURRENT state stops on a superseded earlier entry and reports a false ABSENCE — the inverse of the false-PRESENCE that *Authoritative-set readers must read the manifest* (federation KI) and *Manifest-Prune Per-ID Terminal-State Sweep* guard. Same root cause (no terminal-per-id reduction), opposite surface error — and the false-NEGATIVE is the more dangerous of the two: it manufactures a *phantom discrepancy* that invites a redundant or destructive "fix." (Live tic 336: a first-match scan reported a consumer-set tranche writeback MISSING while the terminal entry at line 1506 HAD it — nearly re-writing a writeback that already existed.) Discipline: any presence/absence assertion over an append-only / last-wins log must dedup to terminal-per-id FIRST; `break`-on-first-match is safe only when scanning for ANY occurrence, never for current state.

<!-- refined by cpr_append_only_log_presence_verification_must_dedup_to_terminal_first_tic336 (tic 337 /review). n=1 lived near-miss; promoted as a REFINEMENT not a standalone KI — the core rule (dedup-to-terminal before trusting state) is derivable from the valve; the novel contribution is the verification-boundary direction + the danger-asymmetry (false-negative > false-positive). CGG-rung. Band: COGNITIVE. -->
<!-- promoted from cpr_terminal_state_valve_pattern_tic185 (tic 185→188). Source: architect Patch 2/3 specification at tic 185, write+read symmetric implementation across cpr-extract.py + bench-packet-prep.py + ripple-assessor.load_queue mirror at tic 186. First practical exercise at tic 187 bench-packet-prep produced quantitatively larger evidence (16-row valve suppression) than the n=2 fixture parity suggested. Absorbs cpr_cf93e962cf35ee0d (bench packet generator dedup gap) — that CPR named the diagnostic; this one names the structural solution. Band: COGNITIVE. Confidence: 0.93. -->

---

## Manifest-Prune Per-ID Terminal-State Sweep
<a id="manifest-prune-per-id-terminal-state-sweep"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Debt B — manifest-prune.py sweeps must be per-id terminal-state-aware, not per-row. The current pattern (per-row sweep) treats each row in isolation; a row marked resolved that is later superseded by a non-terminal entry under the same id leaves the active-manifest divergent from the latest-entry-per-id projection. The fix: sweep by id, applying terminal-state valve semantics — the id is removed from active-manifest only when its latest entry across all daily files is terminal. Composes with Terminal-State Valve Pattern (this is the read-side projection complement: terminal-state valve filters extracted/non-terminal rows; per-id sweep filters at the manifest level using the same semantics), federation KI Authoritative-set readers must read the manifest (the manifest is the curated truth; a per-row sweep produces stale manifests that violate the authoritative-set claim), federation KI Disagreement-as-Evidence (the per-row vs per-id reading IS the disagreement; today's tic-235 manifest 0/0 vs bench-packet-prep 8/0 is direct exercise). Pair-evaluate with Debt A (transient drift auto-resolution owner) but DO NOT MERGE — Debt A is auto-resolution authority assignment, Debt B is sweep mechanics; different layers per Architect tic 228 closeout.

<!-- promoted from cpr_manifest_prune_terminal_state_per_id_tic228 (tic 228→235). Source: ~/.claude/projects/-Users-breydentaylor-canonical/memory/MEMORY.md tic 228 session lessons. Architect tic 228 closeout: "Debt B = materialized state / manifest projection correctness." Live evidence at tic 235 review: manifest 0/0 vs bench-packet-prep 8/0 is the per-row vs per-id disagreement in operation. Band: COGNITIVE. Confidence_tier: tentative. -->

---

## Debt A — Transient Patch-Landing Drift Auto-Resolution Owner
<a id="debt-a-transient-patch-landing-drift-auto-resolution-owner"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Debt A — the transient patch-landing drift auto-resolution loop has no runtime owner (runtime lifecycle closure layer). The Transient Patch-Landing Drift Signal Class names the closure path doctrinally; the manifest-prune per-id sweep (Debt B) corrects the manifest read-side projection; but the loop that observes a transient `detected_drift` signal and writes its self-resolved closure (`status=resolved`, `resolution_diagnosis="transient_patch_landing_drift_resolved_post_sync"`, `resolved_tic`, `resolution_note`) currently has no declared runtime owner. Without an owner, transient drift signals carry forward across sessions even when the closing sync action has already occurred in the same operational flow, inflating active-signal counts and misrepresenting manifold state. Pair-evaluate with Debt B (cpr_manifest_prune_terminal_state_per_id_tic228) but DO NOT MERGE — Debt A is auto-resolution authority assignment, Debt B is sweep mechanics; different layers per Architect tic 228 closeout. Composes with Conductor-Score-Runtime Parity (federation KI — doctrine names the closure class, runtime must enforce a state that carries it), Signal Resolution Writeback Atomicity (the writeback must be atomic across signal record + manifest), and Transient Patch-Landing Drift Signal Class (names the class; this names the missing runtime owner for closing it). The resolution: assign explicit ownership for the auto-resolution loop — either a dedicated runtime hook (post-sync verification observes prior-tic detected_drift signals against the just-synced surface and writes resolved transitions) or extend an existing owner (runtime-sync.py post-verification step, sentinel hook closure pass) — and inscribe the assignment so the loop is no longer authority-vacant.

<!-- promoted from cpr_transient_drift_auto_resolution_owner_tic228 (tic 228→236). Source: ~/.claude/projects/-Users-breydentaylor-canonical/memory/MEMORY.md tic 228 session lessons line 2390. Architect tic 228 closeout: "Debt A = runtime lifecycle closure." Pair-promoted with Debt B at /review tic 235 Pass 1; this complement closes the runtime-owner gap that Debt B's mechanism alone cannot. Band: COGNITIVE. Confidence_tier: tentative. -->

---

## Tracked External Scripts Pattern
<a id="tracked-external-scripts-pattern"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Some runtime-invokable scripts cannot be relocated to the standard install tree because they are path-locked to a non-runtime location (e.g., build_queue_index.py uses `Path(__file__).parent` to resolve queue.jsonl as a sibling in audit-logs/cprs/). Forcing relocation breaks the path lock; leaving them invisible to sync-manifest creates an unowned-runtime gap. The pattern is to extend sync-manifest with a `tracked_external_scripts` section that declares ownership without forcing relocation. Each entry names path, owner, category, invokers, write target, `install_target` (null if intentionally project-local), `install_reason`, and any `schema_coverage_limit` deferred to /review. Refines the existing "Runtime-Invokable Scripts Must Register in Sync Manifest" invariant (which assumed sync was always to ~/.claude/) by accommodating intentionally-project-local runtime. The `schema_coverage_limit` field is the audit trail naming where a script's coverage diverges from the federation's full taxonomy without silently widening it — widening is a /review question per CogPR-159.

<!-- promoted from cpr_tracked_external_scripts_pattern_tic185 (tic 185→188). Source: build_queue_index.py declaration at tic 185 — install_target=null + install_reason="path-locked to audit-logs/cprs/ for sibling queue.jsonl resolution" + schema_coverage_limit naming the {promoted, skipped, superseded} subset of the federation's terminal set. Refines Runtime-Invokable Scripts Must Register in Sync Manifest. Band: COGNITIVE. Confidence: 0.85. -->

---

## Transient Patch-Landing Drift Signal Class
<a id="transient-patch-landing-drift-signal-class"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When patches land in canonical source but have not yet been copied to the installed runtime tree, runtime-sync's pre-sync drift check correctly fires a TENSION/COGNITIVE detected_drift signal. The signal self-resolves the moment runtime-sync sync runs and post-sync verification confirms byte-identical parity. This is a recurring same-cycle class — not yet a longitudinal recurrence claim — that the manifold can recognize and resolve under a distinct closure path from persistent runtime drift. Class signature: a TENSION/COGNITIVE detected_drift signal emitted by runtime-sync's pre-sync check, where the underlying drift is closed by the sync action that follows in the same operational flow. Resolution metadata schema: `status=resolved`, `resolution_diagnosis="transient_patch_landing_drift_resolved_post_sync"`, `resolved_tic`, plus a free-text `resolution_note` carrying the diagnostic + probe evidence (diff -rq + runtime-sync verification), manifest entry mirrored, manifest-prune sweep to resolved-archive. Doctrine names the class so /siren can suggest the resolution; automation of the closure path is deferred until cross-tic recurrence appears (per the temporal-scope-precision invariant). Sentinel discipline is to emit (drift detection is real-time evidence); the manifold should not carry these as carryforward signals across sessions when the sync that closes them is part of the same operational flow.

<!-- promoted from cpr_transient_patch_landing_drift_signal_class_tic186 (tic 186→188). Source: same-cycle n=3 in tic 186 (sig_detected_drift_4287ec7eb993 carryforward, sig_detected_drift_8a209e055ed3 newly fired, sig_2026-04-23_detected_drift_8dc4140d332c long-standing — all closed under identical diagnostic class). Conservative wording per operator correction: name the class, defer automation; cross-tic recurrence required before automated resolution path. Promoted alongside cpr_temporal_scope_evidence_precision_tic187 (tic 187→188, federation invariant) so the temporal-scope discipline is in place when this inscription lands. Band: COGNITIVE. Confidence: 0.87. -->

---

## Memory-Trim Lighter-Cadence Variant (Option B)
<a id="memory-trim-lighter-cadence-variant-option-b"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

MEMORY.md trims under the staged-execution pattern need not require the full 4-tic gate ceremony when the operator approves Option B (lighter-cadence single-pass per CogPR-160). The geometry: skip the swarm-authored Stage 1 deliverables; have a single agent author pin list + disposition table + operator gate in one pass; preserve REVIEW_PINNED entries (status: pending or deferred per Inline Entry Location Lock); accept the conservative reduction the lock-respecting trim produces. The original trim plan's headline target assumed /review would clear most pending entries before Stage 2; under Option B that assumption is not enforced — the trim lands where REVIEW_PINNED constraint allows, then waits for the next /review to unblock another sweep. The sequence (trim → /review → trim) is iterative, not single-shot. Generalizes lighter-cadence rollout (CogPR-160) from convention-conversion adopters to MEMORY.md trim ceremonies.

<!-- promoted from cpr_07199ad8276b1221 (tic 183→188). Source: tic 183 Option B trim — 1207 → 961 lines (-246, ~20%) with 80/80 refs verified, 12/12 spot-checked REVIEW_PINNED entries preserved, 0 broken local refs. n=1 in-anger validation. Companion to cpr_32d815d6fe39536e (trim yield extraction-source awareness, also promoted tic 188). Band: COGNITIVE. Confidence: 0.78. -->

---

## Memory-Trim Yield Source-Awareness
<a id="memory-trim-yield-source-awareness"></a>
<!-- ledger-tags: authority_class=memory_and_inscription_hygiene | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Trim sweep yield against MEMORY.md after /review depends on the EXTRACTION SOURCE of the CPRs that /review terminalized, not just the count of verdicts applied. Tic 183 /review terminalized 12 CPRs but only 2 MEMORY.md inline blocks unlocked for trim because most processed CPRs were extracted from cadence handoffs (~/.claude/plans/), inbox envelopes, or arena reports — not from MEMORY.md inline candidates. The cadence is iterative and source-aware: trim sweep yield ≈ count(MEMORY-sourced CPRs terminalized this /review × ~9 lines/block). Plan trim cadence by checking the source field on pending CPRs before estimating sweep yield. To unlock MEMORY.md inline blocks specifically, /review needs a bench packet biased toward MEMORY.md-sourced extractions. Refines Memory-Trim Staged Execution Pattern with extraction-source-awareness as a yield-estimation discipline.

<!-- promoted from cpr_32d815d6fe39536e (tic 183→188). Source: tic 183 /review trim sweep — projected yield assumed /review would process the 47 REVIEW_PINNED inline blocks; actual yield was 2 because those CPRs weren't in the bench packet's recommended order. Companion to cpr_07199ad8276b1221 (lighter-cadence trim variant) — both born tic 183, refine the trim doctrine together. Band: COGNITIVE. Confidence: 0.78. -->

---

## Post-Cadence Clean-Close Ordering
<a id="post-cadence-clean-close-ordering"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When a /cadence-emitted tic includes post-cadence operational cleanup that mutates governance state (signal triage with manifest sweeps, MEMORY.md candidate updates, queue-shaping commits), the closing /cadence should make post-cleanup state visible to the next session's /review. Originally this ordering was satisfied by an explicit bench-packet-prep run in the pre-/cadence window; that mechanism was dropped at tic 293 (see *Bench Packet Prep Cycle Drop Reversal* below) because it satisfied parity in name only — the bench packet was a JSON projection of queue state that /review already reads directly from `audit-logs/cprs/queue.jsonl` + `audit-logs/signals/active-manifest.jsonl`. The clean-close ordering now reduces to: (1) prior /cadence emits boundary tic + mandate, (2) post-cadence cleanup mutates manifold/queue, (3) closing /cadence emits next boundary tic; /review opens directly against authoritative queue + manifest state at the next session. The diagnostic discipline survives the mechanism: if a future cycle is added as the doctrinal mechanization of this ordering, it must demonstrate semantic substance (not just JSON projection of state already canonically available) before scheduler admission.

<!-- promoted from cpr_post_cadence_clean_close_ordering_tic187 (tic 187→188). Amended at /review tic 294 by cpr_bench_packet_prep_cycle_drop_doctrine_reversal_tic273_post_cadence_clean_close_ordering_tic293 — bench-packet-prep cycle dropped from cadence-ops scheduler at tic 293 (CGG commit 280a8a5) because ~20-tic runtime exercise produced enrichment_coverage=0/N every cycle (presence/observation fallacy class). Original tic 187→188 validation evidence (13 vs 39 pending asymmetry from valve-pattern) remains the diagnostic case for the Terminal-State Valve Pattern but is no longer the cadence-ordering case. Source: ~/.claude/plans/shimmering-tumbling-dawn.md (tic 293→294 handoff). Band: COGNITIVE. Confidence: 0.90. -->

---

## Bench Packet Prep Cycle Drop Reversal
<a id="bench-packet-prep-cycle-drop-reversal"></a>
<!-- ledger-tags: authority_class=memory_and_inscription_hygiene | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

At tic 293 the bench_packet_prep cycle was dropped from the cadence-ops scheduler (CGG commit `280a8a5`). The cycle had been scheduled at `tic % 2 == 0` from tic 273 onward as the runtime mechanization of *Post-Cadence Clean-Close Ordering* and the CGG-rung application of *Conductor-Score-Runtime Parity*. Across tics 273-292 the Mogul cycle ran ~10 times producing `enrichment_coverage=0/N` every cycle. The doctrinal promise was "pre-strengthen weak packets before /review consumption"; the runtime delivered "JSON projection of queue state that /review already reads directly from `queue.jsonl` + `active-manifest.jsonl`." The runtime bore the doctrinal label while delivering no doctrinal substance — a concrete instance of federation KI *Presence/Observation Fallacy Guard* (tic 293).

**Runtime drop scope (5 files, retained substrate):** `cgg-runtime/scripts/cadence-ops.py` (cycles.append removed), `cgg-runtime/scripts/mogul-runner.sh` (prompt + verification + schema cleaned), `cgg-runtime/skills/review/SKILL.md` (Step 5.5 blocking gate removed; 5.6 renumbered to 5.5), `cgg-runtime/agents/mogul.md` (capability list cleaned), `cgg-runtime/sync-manifest.json` (invoker list updated). Retained on disk: `bench-packet-prep.py` script (manually invocable via `mandate.cycle_request.run_now`), `mogul-mandate.schema.json` enum entry (manual mandates still permit it), `audit-logs/mogul/bench-packets/latest.json` (last artifact archive), test fixtures (regression coverage).

**Doctrine reversal scope:** the bench_packet_prep instance is reversed; the diagnostic frame (parity-in-name-only) remains promoted in *Conductor-Score-Runtime Parity (CGG Application)* and *Cadence-Ops Scheduler Doctrine-Runtime Parity*. The fix-family framing extends: if a future candidate names a cadence whose runtime would only summarize (not semantically fulfill state already canonically available), the same drop pattern applies. Reversibility is intentional per federation KI *Rollback velocity must exceed attachment velocity* — re-adding `cycles.append("bench_packet_prep")` in cadence-ops.py + restoring /review Step 5.5 restores the cycle.

<!-- promoted from cpr_bench_packet_prep_cycle_drop_doctrine_reversal_tic273_post_cadence_clean_close_ordering_tic293 (tic 293→294, /review Pass 1). Two-part promotion: (a) ratify the runtime drop landed at CGG commit 280a8a5 (Architect-authorized at tic 293 "lets rock and roll" + Full Drop scope selection); (b) amend tic 188 Post-Cadence Clean-Close Ordering + tic 226 Cadence-Ops Scheduler Doctrine-Runtime Parity inscriptions to reflect the reversal. Co-promoted with federation KI *Presence/Observation Fallacy Guard* (the failure class the drop responds to) and CGG-rung *Manifest-Driven Inversion Harness Primitive* (PROMOTE-SPEC, manifest at audit-logs/governance/falsifier/manifest.yaml v0.2 captures the failure class as schema invariant). Source: ~/.claude/plans/shimmering-tumbling-dawn.md (tic 293→294 handoff). Band: COGNITIVE. Confidence: 0.90. -->

---

## Extractor Schema Field Mapping
<a id="extractor-schema-field-mapping"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

cpr-extract.py requires source + lesson fields; rich authoring schemas (title/summary/abstraction_layers as emitted by cadence handoffs) are silently dropped. The extractor should accept alternate field mappings natively (title or summary → lesson, path → source) rather than forcing authoring-time normalization. The tic 163 harvest succeeded only because source/lesson were synthesized via inline Python, not via the extractor's own schema flexibility. Without widening, every cadence handoff that uses the rich format re-incurs the harvest cost.

<!-- promoted from cpr_extractor_schema_widening_tic164 (tic 164→211). Source: tic-164-cadence. Fourth-layer silent-miss in tic 163 extraction pipeline. Band: COGNITIVE. -->

---

## Extractor Output Anomaly Flagging
<a id="extractor-output-anomaly-flagging"></a>
<!-- ledger-tags: authority_class=forensic_and_drift_investigation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

cpr-extract.py that finds N blocks but extracts 0 should surface the discrepancy. Currently prints '0' to stdout and exits 0 — matches the Output Anomaly Invariant violation pattern (CogPR-80). Required behavior: emit 'scanned N blocks, extracted M, dropped (N-M) due to missing required fields: [fields]' to stderr when M < N. This converts silent-miss to loud-miss and satisfies the differential verification invariant at the extraction boundary.

<!-- promoted from cpr_extractor_output_anomaly_flagging_tic164 (tic 164→211). Source: tic-164-cadence. Tic 163 extractor returned 0 for a plan file containing 21 authored candidates. Silent exit-0 meant the miss was only detected because the operator specifically checked queue growth against handoff expectation. Extractors are governance instruments — their silent-misses are governance debt. Band: COGNITIVE. -->

---

## Emitter Surface Declared Interface
<a id="emitter-surface-declared-interface"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Any governance surface that emits <!-- --agnostic-candidate --> blocks must be reachable by cpr-extract.py. Plan files (~/.claude/plans/) were the first discovered scope miss (tic 163); the fix added a single --plan-file arg. But the broader pattern is that there's no declared emitter-surface interface — surfaces that could emit (inbox envelope markdown, arena report summaries, bench packets, session transcripts) have no contract with the extractor. The scope should be declarative (emitter surfaces register with the extractor) rather than extractor-hardcoded.

<!-- promoted from cpr_emitter_surface_declared_interface_tic164 (tic 164→211). Source: tic-164-cadence. Meta-pattern from the tic 163 silent-miss analysis. Each silent-miss layer (scope/status/schema) is an instance of missing declared interface contract between authoring surfaces and consumer layers. Extending volatility-handling law: internal capability surfaces also need declared contracts — not just external ones. Band: COGNITIVE. -->

---

## Sliding Window Event-Stream Filtering
<a id="sliding-window-event-stream-filtering"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Sliding windows over governance event streams must filter by TIME (cycle / tic / timestamp) not by RECORD COUNT when the stream carries mixed-frequency event types. When a high-frequency event type (resource_flow: 1 record per cycle per edge) shares a stream with lower-frequency event types (bond_formation: 1 record per bond creation), a count-based window (last N records) silently excludes the lower-frequency types even when they are within the semantically-intended time window. The failure mode is invisible: the window still returns 20 records, but they are all from the dominant event class. In this session: standing-engine's diversity_window_cycles=20 was interpreted as 'last 20 records' rather than 'records within last 20 cycles' — resource_flow crowded out bond interactions, diversity entropy was mechanically capped at 0.28-0.67 for visitors whose bond lineage was already present in the data. Fix: filter by `rec.cycle >= (current_cycle - window_cycles + 1)`. Generalizable pattern — any governance stream with mixed event frequencies has this risk. Complements the existing 'CONFIG key names must match implementation semantics' discipline.

<!-- promoted from cpr_cycle_based_windows_in_mixed_frequency_contexts_tic170 (tic 170→211). Source: tic-170 standing-engine.py _get_entity_interactions + _compute_interaction_history_score fixes. Band: COGNITIVE. -->

---

## Binder Addendum Inscription Preservation
<a id="binder-addendum-inscription-preservation"></a>
<!-- ledger-tags: authority_class=memory_and_inscription_hygiene | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Operator-reviewed governance documents should receive state updates via appended addendum sections with preserved original bodies, not in-place rewrites. The pattern: when a dated artifact (e.g., telos-immersive-rfc-binder-tic115.md) needs current-state refresh, append a clearly-marked 'TIC N STATE ADDENDUM' section that (1) references the original body unchanged, (2) updates each original Open Question / decision with current status, (3) enumerates new decisions since the original compilation, (4) cross-references authoritative state documents produced since. This protects the review provenance of the original while making state current. In-place rewrite blurs the review boundary — future readers cannot distinguish operator-reviewed content from subsequent edits. The addendum preserves the audit trail and makes time-of-decision legible. Also validates: handoff documents are bridge surfaces (transient), RFC binders are archive surfaces (permanent), and the difference matters structurally.

<!-- promoted from cpr_binder_addendum_inscription_preservation_tic169 (tic 169→211). Source: tic-169 telos-immersive-rfc-binder-tic115 state update. Band: COGNITIVE. -->

---

## Parallel Inscription Swarm Validated at n=3
<a id="parallel-inscription-swarm-validated-at-n-3"></a>
<!-- ledger-tags: authority_class=subagent_and_swarm_delegation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Spec-First Parallel Swarm (CogPR-140) + Lighter-Cadence Rollout Post-Validation validated at n=3 for inscription-class work. Splitting by target file (one agent per surface) produces collision-free parallel inscription. Each agent received a narrow scope (file path + specific CPR IDs + lookup procedure via grep for specific IDs) rather than bulk reading the queue. Total session wall-time for 36 inscriptions: ~5 minutes of parallel agent execution vs estimated 30+ minutes sequential. Evidence for file-partitioned parallelism as the low-coordination-overhead pattern for bulk inscription. Key discipline: agent prompt must explicitly say 'do NOT read entire queue.jsonl, use grep for specific IDs' — one prior agent bailed citing token budget because it tried to read the full queue.

<!-- promoted from cpr_parallel_inscription_swarm_n3_validated_tic172 (tic 172→211). Source: tic-172 /review Pass 2 — 3 parallel review-execute agents inscribed 36 sections across 5 file targets (canonical/CLAUDE.md, CGG CLAUDE.md, AUTHORING_CONVENTION.md, cadence/SKILL.md, stage/SKILL.md) with zero collision; all sections findable via grep post-execution. Band: COGNITIVE. -->

---

## Auto-Mandate Scope Expansion via Merge
<a id="auto-mandate-scope-expansion-via-merge"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Session-start auto-mandate logic may merge+expand a manually-written mid-session mandate into a broader consolidated mandate when session_start fires (which can happen mid-session via UserPromptSubmit hook or explicit re-invocation). The merge is non-lossy (my cycles absorbed into run_now, my mandate_id recorded in merged_from) but the absorbing mandate runs ALL its cycles including the narrow one I intended plus 5 others. Consequence at tic 172: my 1-cycle review_close_check became a 6-cycle mandate whose review_close_check fired the artifact gate failure. The merge-before-write discipline (CogPR-57) prevented mandate loss but didn't prevent scope expansion. Not a bug — correct behavior under the mandate lifecycle invariant. Worth naming: when operator writes a narrow mid-session mandate, they may be writing the seed of a next-session-start-expanded mandate. Not blocking, but counts as scope awareness.

<!-- promoted from cpr_auto_mandate_merges_with_operator_mandate_tic172 (tic 172→211). Source: tic-172 /review Step 8.5 — wrote review_close_check mandate at 04:44:52; session_restore.sh session_start trigger fired at 04:46:26 (likely from UserPromptSubmit hook mid-session) and wrote a new 6-cycle mandate that merged_from my narrow review-close mandate. Band: COGNITIVE. -->

---

## Patch Landing Five-Stage Discipline
<a id="patch-landing-five-stage-discipline"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Substrate-modifying patches (extractor schema, queue read/write semantics, signal manifold rules) benefit from a 5-stage landing discipline: (1) spec — operator-authored or agent-validated contract with explicit tier rules and hard constraints; (2) implementation — write the code against the spec, no inferred behavior; (3) fixtures — write fixture tests that cover each spec rule (positive + negative + edge), run them, require all green; (4) dry-run — exercise against real substrate (not synthetic data) without writing, report what WOULD happen per tier/category; (5) runtime-sync check — verify canonical→install parity (TENSION/COGNITIVE drift expected pre-sync, byte-identical post-sync). Only then commit, and only with cross-repo boundary respect (CGG patch separately from canonical audit artifacts). The 5 stages compose: spec is the contract, fixtures are the conscience, dry-run is the probe, runtime-sync is the parity check, commit boundary is the federation discipline. Skipping any one stage produces a class of failure: no-spec → silent semantic widening; no-fixtures → mechanism bugs at edge cases; no-dry-run → unexpected scale behavior; no-runtime-sync → install drift carryforward; no-commit-boundary → cross-repo entanglement. Validated at tic 188 Patch E.

<!-- promoted from cpr_patch_landing_discipline_5stage_tic188 (tic 188→211). Source: Patch E execution flow at tic 188: spec → implementation → fixtures (19/19) → dry-run → runtime-sync check → commit boundary discipline. Band: COGNITIVE. -->

---

## Two-Lane /review Execution Split
<a id="two-lane-review-execution-split"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Tic 188 /review docket arrived with 25 entries split across heterogeneous targets. Initial dispatch table treated all PROMOTEs uniformly through review-execute. Operator caught the structural hazard: targets like cadence/SKILL.md, biome-engine.py header, cadence-ops.py header are not the same execution class as appending to CLAUDE.md. The operator forced a corrective split: Lane A = doctrine/docs targets (review-execute eligible, mechanical promotion to CLAUDE.md / GIT_RULES.md), Lane B = code/spec/header targets (separate OPS/DIRECT inline patches with read-edit-write of existing files). Final tally: 10 Lane A doctrine inscriptions + 3 Lane B header/spec patches + 3 SKIP + 9 DEFER = 25. Lane A dispatched as review-execute agent with verdict table only; Lane B handled inline by orchestrator with spec→edit→smoke-check→runtime-sync sequence. Commit boundaries kept separate: ak-control-room (87ce943, Lane A), CGG (8d9e21e Lane A + 7c6641c Lane B), canonical (4ac640f Lane A + 9bb980d Lane B + 1072034 path cleanup + 5c5aa97 review-close mandate + 1814b10 CONSISTENT evidence). Runtime-sync verified 112/112 byte-identical post-Lane-B. review-close-check verdict: CONSISTENT (0 findings) after the verifier-path cleanup commit.

<!-- promoted from cpr_two_lane_review_execution_tic188 (tic 188→211). Source: tic-188 /review execution with mixed doctrine + code/spec targets. Operator-forced split into Lane A (review-execute eligible) + Lane B (OPS/DIRECT patches). Band: COGNITIVE. -->

---

## v2.1-lite Agent Routing-Disambiguation Frontmatter
<a id="v2-1-lite-agent-routing-disambiguation-frontmatter"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

The v2.1 routing frontmatter format (CENTROID + IS + IS NOT [collapse_zones + sibling_overlaps] + WHEN + NOT WHEN + RELATES TO) was established at the skill rung as a routing-disambiguation primitive against silent misrouting in overlapping clusters. The format generalizes to the agent-spec rung at the description-block level: the structured prose lives in the `description: |` literal block, and the agent body (system prompt, execution protocol, hard constraints) is preserved as authored. The "lite" qualifier names the lighter-cadence rollout — no per-agent body rewrites; only the frontmatter description is restructured. The discipline is not "rich descriptions" but **structural routing surface**: every CENTROID is one-line jurisdictional; every IS NOT carries explicit collapse_zones (what the agent must not drift into) and sibling_overlaps (nearby agents); every WHEN/NOT WHEN exposes the phase model or invocation criteria. Validated at tic 221 across all 18 CGG agents in 4 lanes (Mogul team, Crisis Office, Expression/encounter, mechanical applier). Specific disambiguations made visible at routing time that were silent before: civil-engineer (routine under Mogul) vs restoration-operator (post-crisis under Crisis Steward) — same surfaces, different lifecycle phase, hard distinction in both agents' collapse_zones; pattern-curator marked [LEGACY/FALLBACK] with explicit collapse_zone "first-line pattern miner" routing standard cycles to the adversarial direct/meta pair; videographer agent vs `/videographer` skill — same name, different namespaces, sibling_overlap names the namespace distinction; review-execute model floor (sonnet, NOT haiku) inscribed in NOT WHEN with the tic 207 lineage. The format is reusable for any agent corpus where Agent-tool dispatch sees overlapping clusters. AUTHORING_CONVENTION.md may be cross-referenced; this inscription does not amend it. Lineage: skill-rung cross-tic precedent at tics 167-168 (batch conversions established the format); tic 221 validates the agent-rung lift. Temporal-scope discipline per `cpr_temporal_scope_evidence_precision_tic187`.

<!-- promoted from cpr_v21_lite_agent_routing_disambiguation_tic222 (tic 222 /review PROMOTE). Source: tic 221 CGG agent fleet uplift, 18 agents in 4 lanes. Band: COGNITIVE. -->

---

## CGG Manifest Pointer Anti-Docrot Discipline
<a id="cgg-manifest-pointer-anti-docrot-discipline"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

For CGG runtime documentation, sync-manifest.json is the authoritative source for installed runtime surfaces. INSTALL.md, topology documents, and runtime-facing docs should point to the manifest rather than maintain static hook/agent/script lists. Orientation counts are allowed only when labeled non-authoritative.

The pattern: when SSOT is established via configuration manifest, downstream documentation that mirrors the manifest's enumerations becomes the drift surface. The mirror IS the drift surface — every addition to the manifest creates an obligation to update N downstream docs, and any forgotten downstream produces stale-list rot. The constraint: replace mirrors with manifest-pointer paragraphs ("Authoritative discovery: <manifest-path> → <key>. Sync each matching file from <canonical> to <installed>. Current count: N (orientation only — read manifest for canonical list)."). The explanation: this makes the manifest's SSOT claim structurally enforced — humans reading docs are pointed back at the manifest, code reading the manifest gets correct discovery, sync runs from the manifest. New surface additions land at the manifest only, with no downstream-doc update obligation. Validated at tic 221: INSTALL.md (4-hook + 4-agent stale lists replaced with manifest-pointer paragraphs after Architect audit found "INSTALL.md hardcodes 4 hooks; reality is 11") and CGG_RUNTIME_TOPOLOGY_AND_LIFECYCLE.md Section 2.7 (Sync-Manifest Authority Reconciliation, explicitly documenting SSOT-vs-actual-consumer behavior). This is the CGG operational application of the federation-rung documentation-side refinement of "Authoritative-set readers must read the manifest" doctrine.

<!-- promoted from cpr_manifest_pointer_anti_docrot_tic222 (tic 222 /review PROMOTE — CGG application; federation refinement also landed at canonical/CLAUDE.md). Source: tic 221 documentation audit. Band: COGNITIVE. Standalone pattern-family maturity claim deferred pending cross-domain/cross-tic recurrence. -->

---

## CogPR Marker Syntax Discipline
<a id="cogpr-marker-syntax-discipline"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

CogPR candidate inline inscriptions in MEMORY.md MUST use single-comment marker form `<!-- --agnostic-candidate` (no closing `-->` on the marker line; YAML body inside the comment; `-->` terminates the block). Closed-form marker `<!-- --agnostic-candidate -->` (with closing arrow on opener) silently fails extraction — cpr-extract scans for blocks delimited by single open/single close, and a closed-on-opener marker creates an empty comment with the YAML body OUTSIDE any HTML comment boundary. Edit tool succeeds (the bytes write fine; markdown renders fine), so the authoring writer gets no signal. cpr-extract emits zero-block scans (visible in the anomaly counters as written_to_queue=0 for affected blocks but not as a parser error). Validated tic 223→224 cadence: 6 federation/CGG-rung CogPR candidates (3 from Phase 7 routing decision + 3 from three-layer terrain ship proposal) inscribed with the broken closed-form marker passed authoring without error but extracted zero blocks; only re-running with single-replace (closed-form → open-form) caused them to extract correctly (written_to_queue: 6 in subsequent run). Mitigation candidate: cpr-extract should warn-on-detect when MEMORY.md contains the closed-form marker pattern, since this pattern is guaranteed to be an authoring error (no legitimate use case exists for closed-on-opener `<!-- --agnostic-candidate -->`). The authoring discipline is the lesson; the extractor warning is the mechanism that catches the discipline failure. Refines: federation KI 'Bounded delegation surfaces default to masking bugs rather than surfacing them' — this is the same shape at the parser-input boundary: a parser that silently skips malformed input instead of warning surfaces the issue at the consumer, after the inscription window has closed. Refines: CogPR-77 (Schema Failure Self-Reporting) which mandates extractors warn on zero-output anomalies — currently fires at the aggregate level (blocks_extracted < blocks_found) but does not fire per-block on this specific authoring error class.

<!-- promoted from cpr_cogpr_marker_syntax_silent_extraction_failure_tic224 (tic 224→226). Source: ~/.claude/projects/-Users-breydentaylor-canonical/memory/MEMORY.md:tic-224-cadence-fix. Band: COGNITIVE. -->

---

## Cadence-Ops Scheduler Doctrine-Runtime Parity
<a id="cadence-ops-scheduler-doctrine-runtime-parity"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

cadence-ops.compute_due_cycles is the central tic-modulo cycle scheduler for Mogul mandates, but multiple doctrine surfaces name cycles that doctrine claims fire on cadence yet the runtime never schedules: (1) civil_status_check — civil-engineer.md:166 declares 'Mogul includes civil_status_check in next mandate if last report > 10 tics' but compute_due_cycles has no civil entry at any modulo (audit at audit-logs/governance/cgg-civil-cycle-detection-audit-tic224.md confirmed gap; tic 220 manual restart did not inscribe a runtime mechanism); (2) bench_packet_prep — RESOLVED VIA DOCTRINE REVERSAL AT TIC 293: cycle dropped from compute_due_cycles (CGG commit 280a8a5) after ~20-tic exercise produced enrichment_coverage=0/N every cycle; doctrine reversal at /review tic 294 reduced *Post-Cadence Clean-Close Ordering* to direct queue/manifest reads (see *Bench Packet Prep Cycle Drop Reversal* above). Both gaps survived because manual compensation worked and there was no failure surface to force the runtime fix — and the bench_packet_prep resolution chose the second mitigation path (amend doctrine to drop the cadence claim) rather than the first (extend compute_due_cycles to schedule). Same shape as Conductor-Score-Runtime Parity (federation KI) applied specifically to the cadence-ops scheduler: doctrine names a cadence, runtime mechanism (compute_due_cycles) doesn't enforce it. The recurrence is structural — any future doctrine surface naming a cadence will repeat the gap unless the inscription discipline includes 'verify compute_due_cycles enforces this AND verify the runtime delivers semantic substance, not just JSON projection of state already canonically available' as a doctrine-promotion gate. The bench_packet_prep resolution is the concrete pattern: when the proposed mechanism only summarizes state already readable from authoritative sources, doctrine reversal is the correct outcome, not scheduler admission. Same-tic n=2 (descriptive evidence within tic 224 audit boundary). Cross-tic n=1 (tic 293 reversal closes case (2); case (1) civil_status_check remains open).

<!-- promoted from cpr_cadence_ops_scheduler_doctrine_gap_recurrence_tic225 (tic 225→226). Source: ~/.claude/projects/-Users-breydentaylor-canonical/memory/MEMORY.md:tic-225-cadence. Band: COGNITIVE. -->

---

## Manifest-Driven Inversion Harness Primitive *(PROMOTE-SPEC, tic 294)*
<a id="manifest-driven-inversion-harness-primitive-promote-spec-tic-294"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Federation observability primitive distinct from per-script audit tools (memory-md-audit.py, queue-drift-audit.py, runtime-sync, contam-sentinel). The existing audit tools are domain-specific, uncoordinated, and each holds its own checks; the inversion harness inverts the stance: one DECLARATIVE manifest names every governance mechanism's expected fire-shape (status_class + invocation_policy + fire_schedule + expected_artifact + content_fingerprint + audit_blind_spots + audits + doctrine_source), and a single runner composes existing observation surfaces against the manifest to classify runtime_state (`healthy` / `broken` / `broken_content` / `fire_pending` / `fire_recent_quiescent` / `dormant` / `unwired` / `dropped`). Mathematically equivalent to existing audit scripts; framed as continuous adversarial probe — Popper-style "try to falsify the conjecture that the federation is healthy" rather than pytest-style "try to confirm behavior is correct." Same code; different stance; the stance changes which failures surface.

**Staged rollout contract (T1-T4):**

- **T1 — manifest** (LANDED tic 293, canonical commits bf68efd6 v0.1 + bfaddd77 v0.2). Schema at `audit-logs/governance/falsifier/manifest.yaml`. 13 mechanisms declared with the named invariant *Presence/Observation Fallacy Guard* (federation KI tic 293) + 6 anti-fallacy guards + 5 meta_audit_blind_spots + 2-axis status encoding (status_class × invocation_policy).
- **T2 — runner** (gates on /review tic 294 PROMOTE-SPEC ratification — THIS PROMOTION). Implementation surface: `cgg-runtime/scripts/falsifier-run.py`. Contract: reads manifest + observed state; emits classification report to `audit-logs/governance/falsifier/reports/`. Does NOT emit signals (T4 separates emission); does NOT mutate governance state. Spec is the manifest itself (the schema declares all interpretive obligations).
- **T3 — cadence-ops integration** as fail-soft subprocess (gates on T2 surfacing real findings, not dormant noise). Pattern follows memory-md-audit's tic 269 fail-soft integration — runs inside compute_due_cycles bundle, returns observability without blocking on errors.
- **T4 — emission promotion** to siren (gates on T3 demonstrating BROKEN-class findings stabilize against false positives). The siren emission gate is its own /review-class decision per *Verdict-Shape Discriminates Execution Gate* — T4 is NOT pre-authorized by this PROMOTE-SPEC.

**Why this composes:** federation KIs *Spec-runtime alignment by accident is structural drift* (the manifest is the structural enforcement layer that prevents accidental alignment), *Authoritative-Set Readers Must Read the Manifest* (the falsifier IS a manifest reader by construction), *Conductor-Score-Runtime Parity* (the content_fingerprint field catches "runs the cycle bearing the doctrinal label but not delivering the doctrinal substance" — the exact failure class that the bench_packet_prep drop responds to), *Recursive Self-Observation* (mitigated by manifest-driven scope: no recursion into the falsifier itself unless explicitly declared as a mechanism in the manifest), and *Presence/Observation Fallacy Guard* (the falsifier is the runtime implementation of the invariant — every observation is interpreted against the manifest's declared envelope).

**Federation evidence justifying coordinated observability:** cross-tic recurrence of silent-failure cases includes bench_packet_prep (tics 273-292, resolved at 293), harmony cadence mod-disagreement (tics 215/219/223, resolved at tic 226), signal resolution writeback atomicity (Debt A, owner-vacant), phantom tic emission (tics 266 + 291, surveillance), doc-as-doctrine genesis-era reference trap (tic 292). Existing observability is scattered; the inversion harness is composition of existing surfaces under a single declarative manifest, not new mechanism.

**PROMOTE-SPEC scope:** this promotion authorizes the primitive name + the T1→T4 staged contract. T2 implementation tranche follows in a subsequent /review gate per the *Verdict-Shape Discriminates Execution Gate* federation KI. If T2 runner authoring surfaces additional schema inadequacies the v0.2 manifest didn't anticipate, the schema iterates before the runner accepts a new manifest version — schema-as-spec; runner-as-conscience.

<!-- promoted from cpr_manifest_driven_inversion_harness_primitive_tic293 (tic 293→294, /review Pass 1) as PROMOTE-SPEC. T1 manifest landed at canonical bf68efd6 + bfaddd77 (tic 293); T2 runner authoring follows in subsequent /review gate per Verdict-Shape KI. Co-promoted with federation KI *Presence/Observation Fallacy Guard* (the runtime-implementing mechanism) and CGG-rung *Bench Packet Prep Cycle Drop Doctrine Reversal* (the failure case the manifest captures as schema invariant). Source: ~/.claude/plans/shimmering-tumbling-dawn.md (tic 293→294 handoff). Band: COGNITIVE. Confidence: 0.85. -->

**T5 — layer-coverage extension (PROMOTE-SPEC, tic 324).** The two complementary harnesses leave a structural coverage SEAM: the FALSIFIER (observe → classify) covers 13 mechanisms that are ALL `layer:mogul_cycle`; the multi-tic SMOKE (`cgg-runtime/tests/smoke_multitic_runners.py`, tic 322) covers scheduler reachability + runner invocability + the launch/hook/injection/dispatch WIRING — but **NEITHER harness OBSERVES THE HEALTH of the hook/injection/dispatch layer**. The smoke asserts those surfaces are wired (present + registered), which per the *Presence/Observation Fallacy Guard* is NOT proof they FIRE; the falsifier does not track them at all (every manifest mechanism is `layer:mogul_cycle`). A silently-broken event-driven surface (posttool-microscan stops firing, citizen-boot injection regresses, trigger-router drops a dispatch) would be caught by neither until a downstream symptom surfaces. **Authorized extension (implementation deferred per Verdict-Shape):** extend the falsifier manifest with hook/injection/dispatch mechanisms (`layer:hook | layer:injection | layer:dispatch`) carrying event-triggered `fire_schedule` + `expected_artifact` + `content_fingerprint`, and extend the smoke's PHASE-5 parity guard to require those mechanisms once added. Do NOT deprecate either harness — complementary lenses (exercise vs observe), not redundant. <!-- promoted from cpr_observe_harness_excludes_hook_injection_dispatch_layer_tic322 (tic 322→324, /review unified docket) as PROMOTE-SPEC — manifest + smoke PHASE-5 extension is implementation, gated to a separate session. Coverage-completeness refinement of the Manifest-Driven Inversion Harness Primitive. Source: tic 322 cityworks two-harness loop-closure pass (smoke CGG 13a1655). Band: COGNITIVE. -->

---

## Compile-Lane Consumer Integration Pattern
<a id="compile-lane-consumer-integration-pattern"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Compile-lane consumer integration pattern. When a state-derivation tool (compiler) materializes append-only event logs into materialized state outputs, downstream consumers must treat the compiler as the canonical state source AND explicitly label any fallback to raw event-log reading as DEGRADED mode (with subtype label naming the specific failure). Naming the failure mode is the discipline; silent fallback to raw-row reading is the failure mode the discipline closes. Validated at tic 223 by lifting compile-lane from ONE_SHOT_ONLY → PARTIAL → PRODUCTIZED: queue_state_compile.py emits 5 outputs (effective_state.json, effective_state.md, strike_stack_candidates.json, anomaly_report.md, maturity_index.json); bench-packet-prep.py invokes the compiler at the start of its run and consumes the outputs as state source, with explicit DEGRADED_NO_COMPILER / DEGRADED_INVOCATION_FAILED / DEGRADED_COMPILE_FAILED / DEGRADED_OUTPUT_LOAD_FAILED stderr labels and a compile_lane_status field carrying the result into the bench packet. The structural separation of compile (state derivation) from consume (state usage) makes the substrate's coordination cost auditable — readers can see which view they're getting and why. Composes with: federation KI 'Authoritative-set readers must read the manifest' (compile is the curated-set producer; consumer reads the manifest); CGG-rung 'Terminal-State Valve Pattern' (compile applies the valve); CGG-rung 'Two-Lane /review Execution Split' (lane separation between lane-doctrine and lane-tooling).

<!-- promoted from cpr_compile_lane_consumer_integration_pattern_tic223 (tic 223→226). Source: ~/.claude/projects/-Users-breydentaylor-canonical/memory/MEMORY.md:tic-223-session-lessons. Band: COGNITIVE. -->

---

## Orchestrator-on-Behalf-of-Subordinate Trace Pattern
<a id="orchestrator-on-behalf-of-subordinate-trace-pattern"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Orchestrator-on-behalf-of subordinate-trace pattern. When a Mogul-team subordinate's hard constraint forbids direct mailbox write (e.g., ripple-assessor's 'sole write target: ~/.claude/grapple-proposals/latest.md'), the orchestrator can deposit a delivery_receipt envelope to the subordinate's mailbox via the existing mailbox writer (inbox-envelope.py), preserving the subordinate's identity in the envelope body and creating a discoverable audit trace before merging into Mogul/orchestrator synthesis. Validated at tic 222 B.3 pilot: receipt envelope WAIT_normal_ripple.assessment.receipt_t222_c421d89c.json landed in ent_ripple_assessor/inbound/ with subordinate-self-write-authority=false, writer-on-behalf-of=ent_homeskillet, primary-proposal-path pointer to ~/.claude/grapple-proposals/latest.md, and full cycle metadata. The trace is discoverable by anyone scanning the mailbox without reading the orchestrator's full report. Composes with: federation KI 'Lane Separation: foreground judgment, background execution' (orchestrator is the foreground writer for governance traces); CGG-rung Bifurcated Bridge Authority (sharp/atmospheric output paths). Federation routing: the question 'should subordinate output authority be expanded to include receipt-mirror surface, OR is orchestrator-on-behalf-of the durable discipline?' is itself routed to /review tic 223+ as a design question — NOT promoted at this candidate. This candidate names the pattern that worked AT THE PILOT; the doctrine question is downstream.

<!-- promoted from cpr_orchestrator_on_behalf_of_subordinate_trace_tic223 (tic 223→226). Source: ~/.claude/projects/-Users-breydentaylor-canonical/memory/MEMORY.md:tic-223-session-lessons. Band: COGNITIVE. -->

---

## Review-Execute Large-File Truncation Hazard
<a id="review-execute-large-file-truncation-hazard"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

review-execute large-file truncation hazard with append-class instructions. When review-execute receives append-class instructions for files larger than its model-context window (~1100+ lines for sonnet-class CLAUDE.md), the agent may truncate the file when writing — effectively deleting content while attempting to append. Validated at tic 222: review-execute first pass for D.2 + D.3 CGG inscriptions caused canonical_developer/context-grapple-gun/CLAUDE.md to drop from 1096 lines to 150 lines (975 deletions, 29 insertions). Recovery: git checkout of working-tree file restored to 1096; orchestrator re-authored both inscriptions as proper Edit-with-anchor appends; final 1110 lines (+14 net append). The hazard is invisible to review-execute itself (its receipt reports 'inserted at end of file' which would be true if it had read the full file before writing — but it did not). Mitigation: orchestrator must verify file line counts BEFORE and AFTER review-execute large-file appends, treating any negative delta as truncation. Refines: federation KI 'Bounded delegation surfaces default to masking bugs rather than surfacing them' (this is one specific mechanism); CGG-rung 'Review Execution Delegation' (model floor sonnet — the truncation happened in this very review-execute despite sonnet-class). Hard mitigation candidate: review-execute should be augmented with an explicit pre-write line count assertion + post-write delta check, raising visibly on truncation rather than silently writing the truncated state. Operational fact, not yet doctrine.

<!-- promoted from cpr_review_execute_large_file_truncation_hazard_tic223 (tic 223→226). Source: ~/.claude/projects/-Users-breydentaylor-canonical/memory/MEMORY.md:tic-223-session-lessons. Band: COGNITIVE. -->

---

## Harmony Cadence Mod-Disagreement (Concrete Conductor-Score-Runtime Parity Instance)
<a id="harmony-cadence-mod-disagreement-concrete-conductor-score-runtime-parity-instance"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Concrete instance of Conductor-Score-Runtime Parity (federation KI) at the cadence-ops scheduler. cadence-ops.compute_due_cycles named harmony_invoke at tic % 4 == 0 (paired with pattern_mining); audit-logs/harmony/invocations.jsonl recorded harmony fires at tics 215, 219, 223 — all tic % 4 == 3, off by one full cycle from the declared schedule. Score and runtime disagreed for at least 3 cross-tic instances before discovery. Discovery vector: ambient render age (◐ aging t-3 at tic 226) made the staleness visible only because the radar's harmony tail decoder was invoked. Without the decode pass, the disagreement would have continued indefinitely. Pairs with the federation-rung Spec-runtime alignment by accident invariant (alignment between two forces never explicitly coordinated) — here the misalignment was visible only because a third surface (radar tail decoder) sampled both. Mitigation: cadence-ops harmony_invoke moves from `tic % 4 == 0` paired with pattern_mining to per-tic firing (matches the Slice as Bounded World Preservation cascade requirement that harmony be a per-tic Layer-1 contributor). The runtime fix lands at the cadence-ops layer; this CGG-rung CogPR captures the discovery and the diagnostic discipline (decode ambient state when available; do not assume cadence parity). Cross-tic n=3 (tics 215/219/223 confirmed disagreement instances).

<!-- promoted from cpr_harmony_cadence_mod_disagreement_tic226 (tic 226→237, /review Pass 2 governance sprint). Concrete instance of federation KI Conductor-Score-Runtime Parity at cadence-ops boundary. Pairs with already-promoted "Cadence-Ops Scheduler Doctrine-Runtime Parity" (this file) and "Spec-runtime alignment by accident is structural drift, not victory" (federation root). Source: ~/.claude/projects/-Users-breydentaylor-canonical/memory/MEMORY.md:tic-226-session-lessons. Band: COGNITIVE. -->

---

## Trigger-Router Starvation + Cadence-Ops Mandate-Write Bypass (Concrete Conductor-Score-Runtime Parity Instance) *(naming PROMOTED; runtime patch PROMOTE-SPEC, tic 299)*
<a id="trigger-router-starvation-cadence-ops-mandate-write-bypass-concrete-conductor-score-runtime-parity-instance-naming-promoted-runtime-patch-promote-spec-tic-299"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Federation KI *Trigger routing is mandatory — entity activation routes through inbox delivery; direct activation is exception-only.* The trigger-router is the manifest-validated, dedup-enforced, audit-logged dispatch primitive that enforces this. As of the tic-273 deep probe the router had been dormant ~85 tics (last fire tic 187). Probe verdict: **STARVED, not dead** — alive, wired, byte-identical canonical↔installed, manifest-active, would dispatch correctly if invoked.

**Acute live bypass**: `cadence-ops.py write_cadence_mandate` writes the next-tic Mogul mandate via direct `mandate-write.py` calls, completely bypassing the trigger-router. Every /cadence-emitted mandate is therefore an undeclared doctrinal exception with no `exception_class` in the manifest — 85+ silent exceptions since tic 188. This is the canonical concrete instance of *Conductor-Score-Runtime Parity* at the cadence-ops layer: doctrine says "trigger routing mandatory"; the runtime path circumvents the only mechanism that enforces it.

**Three additional should-fire-but-don't gaps**: (1) `arena.pressure` / `arena.harpoon_assessment` — arenas fired repeatedly (tics 220-270+) but arena-pressure-ingest.py never calls the router; (2) `swarm.task_dispatch` — substantial /swarm activity (tics 256-272+) without per-task envelope routing; (3) `estate_inbound_packet` — schema + ent_estate_router inbound dir exist, but no estate-side caller invokes the router. Plus 14+ manifest trigger classes that have NEVER fired across 573 logged events — the manifest mixes forward-spec / dormant / active-but-unwired states without discrimination, overstating the router's starvation.

**Two-part remediation**:
- **(A) Runtime patch (CGG-rung, PROMOTE-SPEC)** — cadence-ops `write_cadence_mandate` calls the trigger-router subprocess after constructing the mandate body. One subprocess invocation closes the most acute live violation. Implementation defers to a subsequent /review gate per *Verdict-Shape Discriminates Execution Gate*. When the patch lands, the router log should carry a `synthesized: true` boundary marker noting the 85-tic gap (CGG KI *Backfill After Emission-Gap Closure*).
- **(B) Manifest class-narrowing (CGG-rung operational doctrine)** — per-class decision on the 14+ never-fired classes: forward-spec (`status: forward`), dormant (relocate to deferred manifest), or active-but-unwired (find the should-fire emitter and wire it).

**Falsification**: if the cadence-ops patch lands and the router still doesn't fire on per-cadence mandate writes, the bypass class is broader than the single caller — audit ALL `mandate-write.py` call-sites.

Composes with: federation KIs *Trigger routing is mandatory* (this names a concrete same-class violation), *Conductor-Score-Runtime Parity* (the canonical example — router enforces, writer bypasses), *Spec-runtime alignment by accident is structural drift* (the bypass survives because manifest-validation has been single-class for 85+ tics), *Bounded delegation surfaces default to masking bugs* (the mandate-write boundary masked the bypass); CGG-rung *Mandate Lifecycle Defects* (the tic-108 idempotency fixes inadvertently created the direct-emission bypass path). Probe n=1 (tic 273); the bypass itself is cross-tic n≥85.

**Lock line**: *Doctrine says route; cadence-ops writes direct. Name the bypass, then close it.*

<!-- promoted from cpr_trigger_router_starved_cadence_ops_bypass_conductor_score_runtime_parity_instance_tic273 (tic 273→299, /review brought forward to tic 299). Naming PROMOTED CGG-rung; runtime patch (A) is PROMOTE-SPEC per Verdict-Shape KI — implementation defers to a subsequent gate. Sibling to "Harmony Cadence Mod-Disagreement" (same Conductor-Score-Runtime Parity class at cadence-ops). Probe n=1 / bypass n≥85. Band: COGNITIVE. -->

---

## Even-Tic Review-Close Routing (/review Step 8.5 Discipline)
<a id="even-tic-review-close-routing-review-step-8-5-discipline"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

/review Step 8.5 mandates writing a non-blocking review-close mandate so the next session verifies inscriptions landed. But the cadence-ops off-by-one schedule deterministically includes `review_close_check` in every EVEN tic's mandate. When the next cadence tic is even, writing a separate review-close mandate to current.json is redundant, risks double `review_close_check` execution (benign per the Artifact-Count-≠-1 Fix-Family but noisy), and overwrites a consumed mandate mid-session.

Discipline: before writing a Step 8.5 review-close mandate, check whether the next cadence tic is even. If EVEN (review_close_check deterministically due), ROUTE the review-close obligation to that cadence cycle — log the intent to grapple-meta-log rather than writing a separate mandate. If ODD (no deterministic review_close_check), write the mandate per Step 8.5. This extends the concurrency-guard's SPIRIT (avoid mandate collisions) to the consumed-mandate + deterministic-even-tic case the literal guard does not cover.

Composes with: federation KIs *Conductor-Score-Runtime Parity* and *Composite mutation scheduling requires explicit assessment*; CGG-rung *Cadence-Ops Scheduler Doctrine-Runtime Parity* and *Mandate Lifecycle Defects* (concurrency guard); the cadence-ops off-by-one fix-family (cross-tic n=5, tics 297-301). Implementation of the Step 8.5 even-tic-routing branch in the installed /review SKILL.md is a follow-on per *Verdict-Shape Discriminates Execution Gate*.

<!-- promoted from cpr_review_close_routes_to_deterministic_even_tic_review_close_check_not_separate_mandate_tic299 (tic 299→301, /review tic 301). Doctrine PROMOTED CGG-rung; SKILL.md Step 8.5 branch edit is the follow-on implementation. Self-exemplified at tic 301 (odd tic → Step 8.5 wrote the review-close mandate). Band: COGNITIVE. -->

### Refinement: a LIVE `pending` mandate is MERGE-only — "no overlap" is not a license to supersede

The concurrency guard's `pending` branch (Step 8.5) historically read "if no cycle overlap, supersede with the review-close mandate." That literal rule is WRONG for a LIVE, not-yet-consumed cadence mandate — the one SessionStart will hand Mogul. Superseding it drops its unconsumed cycles (harmony_invoke / signal_scan / queue_refresh / …) — precisely the cycles the handoff requires. The correct move on any live `pending` mandate is always the non-destructive one: **MERGE `review_close_check` into the existing `run_now` (dedup if present), never supersede.** Supersede is reserved for the terminal-state branch (consumed / failed / missing). "No cycle overlap" describes the cycle set; it does not authorize destroying a live mandate. This is `self-operation-signal-discipline` (federation, promoted tic 373) applied to a routing surface the session depends on: when you modify a surface you also rely on for execution, favor the non-destructive operation. Composes the *Even-Tic Review-Close Routing* discipline (above): even-tic routing decides WHETHER to write a separate mandate; this decides HOW to combine when a live one exists — merge, not supersede. The SKILL.md Step 8.5 `pending`-branch wording was corrected at /review 375.

<!-- promoted from cpr_merge_not_supersede_live_cadence_mandate_at_review_close_tic373 (session_lessons_tic_373.md, inline; /review 375 PROMOTE-as-refinement, Architect-ratified). Refines the Even-Tic Review-Close Routing entry + Mandate Lifecycle Defects (concurrency guard); SKILL.md Step 8.5 pending-branch edit landed same pass (not deferred — a skill-body wording fix, terminal-admissible). Non-derivability: the existing pending-branch did NOT mandate merge for the no-overlap case (it said supersede), so this is a genuine wording fix, not already-covered. Composes federation KI self-operation-signal-discipline. Band: COGNITIVE. -->

**SKIP-with-home note — a lifecycle reconciler defaults to ENUMERATE-TERMINAL-else-MERGE (tic 534 born → /review 537 SKIP-with-home, enrichment-eligible).** Generalizing the mandate-specific rule above: when ANY lifecycle reconciler decides MERGE-vs-SUPERSEDE before overwriting an existing record, ENUMERATE the explicitly-TERMINAL states and treat EVERYTHING ELSE as live → MERGE/preserve. The inverse (enumerate the known-LIVE states, else fresh-write) silently DROPS an unrecognized live status when the status vocabulary grows. Discriminator is STATUS/liveness, never a category label; pin the terminal set as a named constant + a parity test. Operationalizes *State-agreement-is-not-truth-unless-lifecycle-reachable* at the write boundary. Held at SKIP on the temporal gate only (single tic-534 instance in `mandate-write.py`) — **re-evaluate → PROMOTE on a 2nd lifecycle-reconciler instance.**

<!-- SKIP-with-home /review 537 (durable home, NOT promoted-to-doctrine; enrichment-eligible on 2nd conformation): cpr_lifecycle_merge_defaults_to_enumerate_terminal_else_merge_tic534 (queue.jsonl, extracted->rejected). Reason: not-fully-derivable (the enumerate-terminal-else-merge INVERSION + named-constant/parity-test arm are net-new shape) BUT temporal maturity single-cycle; born author self-assessed SKIP-with-home. Generalizes the "LIVE pending mandate is MERGE-only" entry above. Source: audit-logs/governance/borns-tic534-splat-blast-radius-and-terminal-else-merge.md. Band: PRIMITIVE. -->

---

## Inline-Tracked CogPR DEFER Keeps status:pending (/review Step 7 Discipline)
<a id="inline-tracked-cogpr-defer-keeps-status-pending-review-step-7-discipline"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When a /review DEFER verdict lands on an INLINE-tracked CogPR (one that lives as a `status: pending` block in MEMORY.md and is NOT resident in queue.jsonl), do NOT change its inline status to enrichment_eligible/deferred (the skill's literal Step 7 DEFER handling) AND do NOT write a terminal/non-pending entry to queue.jsonl. The cpr-extract inline tracker counts blocks by literal `status: pending` (CGG KI *Inline CogPR status:pending Field Required*); changing the inline status drops the block from the banner's inline-pending count with no guaranteed re-surfacing, while a terminal queue.jsonl entry makes governance_query report it terminal — producing a dual-counter disagreement (banner says gone, queue says terminal, lesson meant to re-surface).

Correct DEFER discipline for inline-tracked CogPRs: KEEP `status: pending` and add advisory annotation fields (`last_reviewed_tic`, `defer_until_tic`, `defer_reason`). The block stays in the inline-pending set, re-surfaces at the defer_until_tic gate, and queue.jsonl stays silent on it — banner and governance_query remain in agreement. Write queue.jsonl terminal entries only for genuinely terminal PROMOTE/SKIP verdicts, not for tic-gated DEFERs of inline CogPRs.

Distinguish from queue-resident CogPRs: when a DEFER'd CogPR is already extracted into queue.jsonl, the skill's enrichment_eligible flow IS correct (append the enrichment_eligible entry; latest-entry-per-id wins). The inline-vs-queue-resident branch is the discrimination Step 7 currently omits.

Composes with: CGG KI *Inline CogPR status:pending Field Required*; federation KI *Disagreement-as-evidence* (this PREVENTS a spurious dual-counter disagreement). Implementation of the Step 7 branch in the installed /review SKILL.md is a follow-on per *Verdict-Shape Discriminates Execution Gate*.

<!-- promoted from cpr_inline_tracked_cogpr_defer_keeps_status_pending_avoids_dual_counter_disagreement_tic299 (tic 299→301, /review tic 301). Doctrine PROMOTED CGG-rung; SKILL.md Step 7 branch edit is the follow-on implementation. Self-exemplified at tic 301 (CogPR-2 DEFER used the queue-resident enrichment_eligible flow). Band: COGNITIVE. -->

---

## Artifact-Count-≠-1 Fix-Family (Emit-Side Complement to Authoritative-Set Readers)
<a id="artifact-count-1-fix-family-emit-side-complement-to-authoritative-set-readers"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Artifact-count-≠-1 is a single failure class spanning both N=0 (no report) and N=2 (duplicate report) cardinalities — not two separate per-incident bugs. The failure surfaces in at least two operational lanes: (1) signal manifold dual-emission (manifest-prune debt from Debt B / cpr_manifest_prune_terminal_state_per_id_tic228 — same signal entry appearing twice within an emission window), and (2) Mogul runner review_close_check artifact verification (tic-250 N=2 reports / sig_review_close_check_double_emission_tic250, tic-251 N=0 reports / mandate failure). Three cross-tic instances confirm structural recurrence rather than per-incident drift. The class is the emit-side complement to two existing federation KIs: *Authoritative-set readers must read the manifest, not aggregate raw emissions* (read-side dedup discipline) and *Terminal-State Valve Pattern* (read-side filter producing state from queue). This CGG-rung doctrine names what the read-side KIs assume but don't enforce: the emit side must produce one canonical row per (id, terminal_state) tuple, with dedup-on-emission rather than dedup-on-read absorbing the inflation. Fix-family framing routes a single remediation through three candidate seams: (a) runtime-side dedup-on-emission gate at the manifest-prune / review_close_check boundary, (b) downstream verification accepts N≥1 with terminal-state-valve absorption (treats N=2 as benign drift caught by reader-side dedup), or (c) upstream emission idempotency contract — emitters guarantee at-most-once per (id, terminal_state). The class also under-specifies its current signal name: `sig_review_close_check_double_emission_tic250` only names the N=2 sub-case; rename candidate `sig_review_close_check_artifact_count_violation` covers both N=0 and N=2 under one identity. Lock line: *Artifact-count-≠-1 is one class. Fix the emit side.*

<!-- promoted from cpr_review_close_check_artifact_count_violation_fix_family_tic253 (tic 253→256, /review Pass 1 Object 7 routing). Cross-tic n=3 evidence: Debt B (cpr_manifest_prune_terminal_state_per_id_tic228 signal-manifold dual-emission) + tic-250 N=2 Mogul mandate + tic-251 N=0 Mogul mandate. Composes with federation KIs Authoritative-set readers + Terminal-State Valve Pattern (this fix-family is the emit-side complement). Surfaced for /review by tic-255 cadence handoff as ITEM 0 (review_close_check inhibition cycle 4 escalation beyond ≥3-cycle threshold) routed to ITEM 1 (Object 7 durable remediation). Band: COGNITIVE. Source: /review tic 253 Object 7 SURFACE-FIX-FAMILY verdict + tic 254 META design + tic 255 cadence inhibition surfacing. -->

---

## Mixed Subagent + Lead Swarm Geometry
<a id="mixed-subagent-lead-swarm-geometry"></a>
<!-- ledger-tags: authority_class=subagent_and_swarm_delegation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When a tranche set has mixed authorship — 1 subagent for large-surface authoring (where fresh-context constraint inversion is valuable for catching latent bugs) + N lead-direct for smaller or manual operations (where session-context familiarity is load-bearing) — parallel throughput is preserved without overspawning subagents. The geometry's load-bearing claim is that subagent dispatch and lead-direct execution are not mutually exclusive within one swarm boundary; mixed authorship is the throughput-vs-overhead optimum when each tranche carries different cognitive-budget characteristics.

**Constraint**: composes with Spec-First Parallel Swarm (parent; spec authoring must complete before swarm dispatch), Region-Level File Ownership in Parallel Swarms (ak-control-room domain KI; sub-file granularity for collision avoidance), Evidence Scaffold Precedes Reasoning (federation KI; typed checkpoint commitment before downstream agents spawn), `feedback_no-haiku-default` (subagent model floor is sonnet, never haiku, per Review-Execute Large-File Truncation Hazard).

**Explanation**: pure subagent dispatch overspawns when small or lead-context-dependent tranches don't benefit from fresh-context constraint inversion (the subagent loses session-arc context that the lead carries cheaply). Pure lead-direct dispatch saturates the lead's context window when one tranche has large authoring surface. Mixed geometry resolves both failure modes: large-surface tranche goes to a subagent (cheap fresh-context); small or session-context-dependent tranches stay lead-direct (preserved continuity). The geometry is not a parallelism shortcut — it is a per-tranche cognitive-budget routing primitive.

**Evidence**: cross-tic n=3. (1) Tic 256 T2 swarm: T2a subagent (~80+ lines new file authoring) + T2b/T2c/T2d lead-direct (smaller ops) — zero file collisions. (2) Tic 257 T3 swarm: T3a/T3b/T3c subagents (parallel adapter+state+endpoint authoring) + T3d lead-direct (block authoring) — zero collisions. Both within same-physical-session arc under Architect-Authorized Cadence Compression. (3) Tic 259 T6 swarm at independent-session boundary: T6a lead-direct (~12-line cadence-ops patch) + T6b subagent dispatch (~127-line POST handler) — zero collisions, tsc clean, runtime-sync byte-parity verified. The third instance closes the cross-tic exercise eligibility gap (independent-session boundary, not same-arc within one tic) that pure same-arc evidence could not satisfy under Temporal-Scope Precision discipline.

**Ray-preservation note (harmony tic 259, `repair-before-lock`)**: harmony's caution at /review tic 259 flagged this inscription as lock-class and suggested deferring one more cycle for additional independent-session evidence. Architect approved Option A (full slate); the ray is preserved by recording the caution here rather than flattening it. Future cross-tic exercises should continue to be observed; if the geometry under-performs at a 4th instance, this inscription is the load-bearing reference for a /review re-evaluation.

**Lock line**: *Subagent for size, lead for context; mixed within budget.*

<!-- promoted from cpr_mixed_subagent_lead_swarm_geometry_tic257 (/review tic 259 Option A — full slate). Cross-tic n=3 evidence: tic 256 T2 + tic 257 T3 same-arc + tic 259 T6 independent-session. Composes with CogPR-140 Spec-First Parallel Swarm, ak-control-room domain KI Region-Level File Ownership, federation KI Evidence Scaffold Precedes Reasoning, MEMORY feedback_no-haiku-default. Harmony tic 259 `repair-before-lock` caution preserved in ray-preservation note (not flattened). Band: COGNITIVE. Source: cadence handoff tic 257 + cross-tic exercise tic 259 T6 swarm. -->

---

## R²-Roadrunner Runtime Context Sharpening Pattern
<a id="r-roadrunner-runtime-context-sharpening-pattern"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

R²-Roadrunner (Recursive-Refinement Roadrunner) names the runtime-context sharpening pattern where a coarse single-binder hydrate at session entry is iteratively narrowed by follow-on probes until the working scope is bounded enough for direct mutation. The name registers the dual recursion: the binder resolves recursively (R²: read full, then read narrower window, then read line range), and the operator runs recursively (Roadrunner: each probe sharpens the next, never blocks). The pattern is the canonical mechanism for bounded source-bearing context expansion when a session inherits a coarse handoff and needs to produce a precise mutation.

**Constraint**: composes with `/tactical-hydration` (RTCH; the broader staged-discovery surface that produces the binder basket), Spec-First Parallel Swarm (CogPR-140; the binder is the spec's source for downstream agent scope), `Look-First — Read Active Plan File Before Plan-Write` (federation KI; the recursive sharpening starts at the plan file), Bounded delegation surfaces default to masking bugs (federation KI; R² is the read-side discipline that the bounded subagent cannot perform from cold context). The pattern does NOT replace RTCH or Look-First — it operationalizes them at the single-binder boundary.

**Explanation**: a session inherits a handoff that names many binders (Plan, Queue, Mandate, Disposition, Receipt, etc.) but cannot operate on all of them at once. Without R², the session either reads everything (context overflow) or guesses which binder to read first (premature scope commitment). With R²: pick the binder pointing at the hottest unresolved pressure (typically `@OpenRay.0`), read full via the single-binder hydrate method (e.g., `read_full` for a small file, `jsonl_tail` for an append-only stream), then narrow recursively — `rg_window` for keyword location, `read_lines` for line-range extraction, `jsonl_grep` for status filtering. The recursion terminates when the working scope is small enough that the mutation can be authored without further reads.

**Evidence**: T5c (tic 258) implemented all 9 hydrate methods including `read_full` (single-binder, R²'s entry point) at CGG `d2935c2`. T5c smoke-tested against live n=2 cadence-block (`@Mandate.0 read_full`, `@Tic.0 jsonl_tail`, `@Posture.0 rg_window`) — three Roadrunner sharpening probes against three distinct binders. Tic 259 T6 implementation arc exercised the pattern operationally: T6a's lead-direct path used R² over the cadence-ops.py file (no subagent overhead because the binder was narrow); T6b's subagent path needed broader context (vite-governance-api.ts at 2626 lines) and dispatched with the spec section as a curated narrow binder rather than blanket file read. The R² discipline shaped the dispatch geometry choice itself.

**Ray-preservation note (harmony tic 259, `repair-before-lock`)**: harmony's caution flagged this inscription alongside Mixed Swarm Geometry. The unblock condition (T5c Bite 4 implementation) is mechanically satisfied at CGG `d2935c2`; the rationale was authored at tic 256 and the gate cleared at tic 258. The harmony caution here reads as a general "preserve the rays" stance on simultaneous lock inscriptions, not a specific objection to R²-Roadrunner's evidence base. Architect approved Option A (full slate); the ray is preserved by recording the caution rather than flattening it.

**Lock line**: *Roadrunner the binder until the scope is bounded; recursion terminates at the mutation boundary.*

<!-- promoted from cpr_r2_roadrunner_runtime_context_sharpening_pattern_tic256 (/review tic 259 Option A — full slate). Unblocked from /review tic 257 ITEM 1 (UNBLOCKED-PENDING-BITE-4-IMPLEMENTATION) by T5c Bite 4 landing at CGG d2935c2 (tic 258). Composes with /tactical-hydration (RTCH parent), CogPR-140 Spec-First Parallel Swarm, federation KI Look-First, federation KI Bounded delegation surfaces. Harmony tic 259 `repair-before-lock` caution preserved in ray-preservation note (not flattened). Band: COGNITIVE. Source: cadence handoff tic 256 + T5c implementation tic 258 + T6 swarm exercise tic 259. -->

---

## Generator-vs-Local-Repair Gap (Handoff Title Format)
<a id="generator-vs-local-repair-gap-handoff-title-format"></a>
<!-- ledger-tags: authority_class=forensic_and_drift_investigation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When a convention drift recurs across sessions (cross-tic n≥3 instances) and originates in a TEMPLATE that agents follow (skill body, spec, mandate format), the fix MUST land at the generator surface. Patching the local emission (one handoff) leaves the next emission free to reproduce the drift because the next author reads prior templates as precedent. Templates carry forward; local repairs do not.

**Pattern**: handoff title format must distinguish work_tic (the tic the session actually worked under = `counter_before`) from entry_tic (the tic emitted by /cadence for the next session = `counter_after`). Use: `tic{work_tic}-close-for-tic{entry_tic}-entry`. Forbidden anti-pattern: titles like `tic{emitted_tic}-close` alone — these conflate emission-tic with work-tic and propagate off-kilter framing into the next session's framing inheritance.

**Constraint**: composes with federation KI *Conductor-Score-Runtime Parity* (the cadence skill is the score; handoff agents are the runtime; off-kilter titles are the parity gap), federation KI *Spec-runtime alignment by accident is structural drift* (titles-tolerated-anyway is the lucky alignment pattern), federation KI *First-Use Surfacing Protocol* (work_tic / entry_tic are candidate_reserved vocabulary; first compliant title is the surfacing boundary). Operationalizes cadence/SKILL.md Step 4 (Write the Handoff as the Plan).

**Explanation**: downstream consumers (next session's framing, /review docket attribution, audit-log narration, conformation references) all inherit the title's tic number as the canonical work-tic. Mis-labeling silently shifts the federation's perception of when work happened by one tic, compounding across review cycles. The generator-surface fix is structural; comment-level reminders at the emission point are insufficient because the next author reads prior emissions as templates.

**Evidence**: cross-tic n≥3 — three distinct handoff titles exhibiting the conflation pattern across tics 261-263. Architect-locked verification test inscribed (next /cadence's handoff title format is the falsification gate). Validated cross-tic n=1 at tic 267 cadence emission (title `tic266-close-for-tic267-entry` produced clean +1 emission with no phantom — falsification test PASSES).

**Lock line**: *Templates carry forward; local repairs do not. Fix the generator.*

<!-- promoted from cpr_tic_framing_convention_off_kilter_work_tic_vs_emission_tic_tic262 (/review tic 267). Cross-tic n≥3 drift evidence (tics 261-263) + cross-tic n=1 falsification-test pass (tic 267). Composes with federation KIs Conductor-Score-Runtime Parity, Spec-runtime-alignment-by-accident, First-Use Surfacing Protocol. Band: COGNITIVE. Source: cadence handoff tic 263 + validation tic 267. -->

---

## Inline CogPR status:pending Field Required
<a id="inline-cogpr-status-pending-field-required"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Inline CogPR inscriptions in MEMORY.md (and other extractor-watched surfaces) MUST carry an explicit `status: pending` field, placed immediately after `id:` in the YAML body. cpr-extract.py treats absence-of-status as "skip with skipped_no_status counter increment" — the block is recognized, parsed, and discarded. The skip is silent at the per-block level: writers cannot detect the failure without explicit queue.jsonl grep after extraction.

**Pattern**: every inline CogPR block must declare `status: pending` adjacent to its `id:` field. The discipline complements but is distinct from *CogPR Marker Syntax Discipline* (which catches closed-form `<!-- --agnostic-candidate -->` openers) — both are silent-skip inscription-discipline failures that the Edit tool cannot catch and the extractor silently absorbs.

**Constraint**: composes with *CogPR Marker Syntax Discipline* (same family — silent-skip inscription class), *CogPR-77 Extractor Anomaly Self-Reporting* (aggregate-level anomaly logging that should be extended to per-block skip-id logging at runtime patch layer), federation KI *Bounded delegation surfaces default to masking bugs* (the parser is the bounded delegate that silently masks authoring errors instead of warning). Promotion target is cadence/SKILL.md Step 2 authoring template plus per-block skip-id logging at the extractor.

**Explanation**: cpr-extract.py treats `status` absence as "block not ready for queue" (intentional state machine — only `status: pending` blocks should flow to queue.jsonl). But many existing inscribed blocks lack the field explicitly, so writers inheriting them as templates inherit the omission. The aggregate counter increments but no per-id surfacing fires, so the authoring session passes through with apparent success. Authoring-side discipline (always include `status: pending`) compounds with extractor-side discipline (per-block skip-id logging) to close the silent-skip gap.

**Evidence**: same-tic n=2 within tic 263 arc (both candidates inscribed without status, both silently skipped, both fixed by status:pending insertion). Cross-tic family at n=4 (Inscription-discipline silent-skip family: CogPR Marker Syntax + status:pending + parser-path-drift authoring + parser-path-drift validation). Validation receipt: cpr-extract second-run counters `blocks_extracted=8` (up from 6), `written_to_queue=2` (up from 0), `skipped_no_status=10` (down from 12, matching the +2 status-fixed blocks).

**Lock line**: *Every inline CogPR carries `status: pending` adjacent to `id:`. Silent skip is failure, not absence.*

<!-- promoted from cpr_inline_cogpr_status_pending_field_required_silent_skip_tic263 (/review tic 267). Same-tic n=2 + Inscription-discipline family cross-tic n=4. Composes with CogPR Marker Syntax Discipline, CogPR-77 Extractor Anomaly Self-Reporting, federation KI Bounded delegation surfaces. Band: COGNITIVE. Source: cadence handoff tic 263. -->

---

## Cadence Skill Parser Path Drift Discipline
<a id="cadence-skill-parser-path-drift-discipline"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When a runtime script emits JSON at top-level keys but the skill body documents a wrapper path (`result.tic.counter_after` rather than top-level `tic.counter_after`), a /cadence author who follows the spec literally produces empty parsed values and may misinterpret success as failure — leading to re-invocation and phantom counted tics on top of legitimate emissions.

**Pattern**: skill body documentation of mechanical-script output schemas must match the actual emission shape byte-for-byte. When a divergence is detected, the fix is structural at the skill body (the generator/template surface), not at each emission site. Patches landed under *Governance Tool Urgency Triage* qualify for immediate runtime authority — code-wrong, doctrine-intact.

**Constraint**: composes with federation KI *Governance Tool Urgency Triage* ("Is the code wrong, or is the doctrine incomplete?" — code-wrong fixes land under existing doctrine authority; learning routes through /review), federation KI *Spec-runtime alignment by accident is structural drift, not victory* (the parser-tolerated-anyway pattern is the lucky alignment that hides the drift until phantom tic emission surfaces it), and *Generator-vs-Local-Repair Gap* (sibling discipline at handoff-title surface).

**Explanation**: cadence-ops.py emits `{tic: {...}, conformation: {...}, mandate: {...}}` at top level. A SKILL.md snippet documenting `result.tic.counter_after` causes the author's parser to read `data.get('result', {}).get('tic', {})` — an empty dict — and misinterpret the cadence emission as failed. Re-invocation produces a phantom counted tic on top of the legitimate one. Append-only tic invariant forbids rollback; the phantom is permanent provenance noise. Fix at the SKILL.md generator surface; downstream emissions inherit the corrected schema automatically.

**Evidence**: cross-tic n=1 at tic 264 incident (phantom tic 266 produced by parser-path-drift after legitimate tic 265 emission). Fix landed at CGG `e2f5d18` under Urgency Triage (tic 266). Cross-tic n=1 validation at tic 267 cadence emission (clean +1, no phantom). Part of Inscription-discipline silent-skip family at cross-tic n=4.

**Lock line**: *Spec documents what runtime emits, byte-for-byte. Drift means generator-side fix.*

<!-- promoted from cpr_cadence_skill_md_step_0_5_parser_path_drift_tic264 (/review tic 267). Cross-tic n=1 incident (tic 264) + cross-tic n=1 fix validation (tic 267). ABSORB-class child: cpr_parser_path_drift_fix_validated_cross_tic_n1_tic267 (the validation evidence). Composes with federation KIs Governance Tool Urgency Triage, Spec-runtime-alignment-by-accident, sibling Generator-vs-Local-Repair Gap. Band: COGNITIVE. Source: cadence handoff tic 264 + fix CGG e2f5d18 + validation tic 267. -->

---

## Atomic Dual-Surface Invariant Mechanization
<a id="atomic-dual-surface-invariant-mechanization"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When a runtime script implements one half of an atomic dual-surface invariant but fails the other half mechanically, the patch is structural (add the missing collapse step) — not narrative (re-explain the discipline in comments). Doctrine names the invariant; runtime must mechanize it. Where the runtime is missing the discipline, fix the runtime; don't inscribe more doctrine around the gap.

**Pattern**: any time a write-side discipline (append-resolution, append-then-collapse) couples to a read-side mechanism (prune/projection), the read-side must honor the write-side's intended semantics. Latest-entry-per-id is the universal collapse primitive for append-only emission surfaces in this federation; mechanisms that read those surfaces without applying it produce orphan-row drift.

**Constraint**: refines existing CGG KI *Signal Resolution Writeback Atomicity (Dual-Surface)* by completing the read-side mechanization. Composes with federation KI *Authoritative-Set Readers Must Read the Manifest* (same authoritative-set discipline applied at the prune mechanism layer), federation KI *Three-Layer Terrain Architecture* (Layer 1 daily files remain append-only invariant; Layer 2 manifest is the curated projection where collapse + partition apply), and federation KI *Governance Tool Urgency Triage* (code-wrong, doctrine-intact — patch under existing authority).

**Explanation**: manifest-prune.py historically partitioned per-row by structural_status without latest-entry-per-signal_id collapse. Two failure modes resulted: (1) append-a-resolved-row writeback left orphan active rows behind — the resolved row archived but the original active row remained in keep, so the signal continued to surface as active on next Mogul signal_scan; (2) physical duplicate rows for same signal_id retained per-row, inflating physical manifest size. The patch adds a first-pass latest-by-key collapse before the projection+partition pass. The pattern generalizes beyond signals: queue.jsonl, conformation files, mandate history — wherever append-only emission carries a "latest wins" semantic, readers must apply collapse.

**Evidence**: same-tic n=2 within tic 263 arc (atomic dual-surface fix-up for sig_review_close_check_double_emission + manifest-prune collapse patch, both under Governance Tool Urgency Triage). Validated at tic 262: manifest 6 rows → 4 rows, 4 unique signal_ids, 4 active under Mogul filter. Patches: CGG `7540cc3` + canonical `12b6760` runtime apply.

**Lock line**: *Where doctrine names a discipline and runtime mechanizes only half, patch the mechanism — not the comments.*

<!-- promoted from cpr_manifest_prune_latest_entry_per_id_collapse_before_partition_tic263 (/review tic 267). Same-tic n=2 + cross-tic exercise eligible at any future append-only emission surface where reader/writer disciplines couple. Refines CGG KI Signal Resolution Writeback Atomicity. Composes with federation KIs Authoritative-Set Readers Must Read the Manifest, Three-Layer Terrain Architecture, Governance Tool Urgency Triage. Band: COGNITIVE. Source: cadence handoff tic 263 + patches CGG 7540cc3 / canonical 12b6760. -->

---

## Cross-File Pointer Integrity Verification
<a id="cross-file-pointer-integrity-verification"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When a multi-file refactor produces a new authoring artifact whose body contains pointers (anchors, hyperlinks, refs) into a companion artifact, the pre-swap verification gate MUST include a pointer-integrity diff: count pointer references from artifact A against anchor definitions in artifact B and assert all references resolve. Bounded delegation surfaces silently build broken-pointer infrastructure when the spec implies the pointers work but doesn't enforce verification.

**Pattern**: any refactor producing compact + ledger, index + content, summary + detail, or pointer-A → anchor-B structure must include pointer-integrity verification at the pre-mutation gate. Adding pointer syntax without verification creates silent broken-link infrastructure that compounds across consumers (next session's framing, /review docket attribution, downstream readers). Differential count (refs in A vs defs in B) is the load-bearing primitive — not a sample of "looks right."

**Constraint**: refines federation KI *Bounded delegation surfaces default to masking bugs by default* (that invariant NAMES the failure class — broken delegation surfaces produce false-completion reports; this KI NAMES the prevention discipline — pointer-integrity diff at the swap boundary). Composes with federation KI *Constitutional refactor must run under /review freeze on same-surface promotions* (the freeze provides the temporal window for verification; pointer-integrity is the structural check inside that window).

**Explanation**: subagent-authored compact + ledger refactors produce divergent half-built artifacts when the subagent treats the two as independent outputs rather than coupled surfaces. The compact root contains pointer syntax; the ledger contains anchor syntax. Both surfaces can pass per-artifact validation (markdown lints, structure checks, body completeness) and still produce 100% broken pointers if no consumer ever counts references against definitions. The check is mechanical: `count(ref-pattern in A) == count(matching-anchor-pattern in B)` and `every ref in A has matching anchor in B`. Sub-second runtime; catches the failure class that bounded delegation makes invisible.

**Evidence**: same-tic n=1 at tic 267 Pass-4-C swap boundary — subagent-authored compact-root-pass4.md contained 38 *Ledger:* pointers each referencing ledger.md#anchor-slug; subagent's ledger.md had 83 anchors but NONE matched the 38 compact-root anchors (the ledger held only DEMOTED entries, not compact-root entries). 38/38 broken pointers caught pre-swap by differential count. Lead-direct fix extended ledger with "Compact-Root Source Bodies" section preserving verbatim full text + provenance for all 38 entries, restoring Layer 1 invariant compliance. Post-fix: 0/38 broken pointers; 5/5 sampled anchors verified resolving after swap. Cross-tic exercise eligible at any future multi-file refactor with pointer/anchor structure.

**Lock line**: *Count references against definitions before swap. Bounded delegation does not catch pointer drift.*

<!-- promoted from cpr_cross_file_pointer_integrity_verification_before_atomic_swap_tic267 (/review tic 269 → 270). Same-tic n=1 (Pass-4-C swap boundary); cross-tic exercise eligible at next multi-file refactor with pointer/anchor structure. Refines federation KI Bounded delegation surfaces default to masking bugs. Composes with Constitutional refactor must run under /review freeze. Band: COGNITIVE. Source: tic 267 close handoff + Pass-4-C verification incident. -->

---

## Cadence-Ops Fail-Soft Observability Subprocess Pattern
<a id="cadence-ops-fail-soft-observability-subprocess-pattern"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When a canonical-side observability or audit primitive should fire each /cadence without coupling its lifecycle to CGG's mutation pipeline, the integration pattern is a fail-soft subprocess step in cadence-ops.py — discovered relative to zone_root, invoked via `subprocess.run` with `capture_output` + `timeout`, result embedded in cadence output JSON, errors absorbed into the result dict rather than blocking cadence emission.

**Pattern**: every canonical-side per-tic audit/observability primitive integrates via the same shape — (1) discover script path relative to zone_root, (2) subprocess.run with capture_output=True + timeout, (3) embed result + ran/exit_code/healthy/summary into cadence output dict, (4) any exception absorbed into the result dict with `ran: false` + `error: <message>`. The cadence pipeline never raises on the integration; absence or failure of the primitive degrades observability, never blocks the tic.

**Constraint**: complements existing CGG KI *Cycle-Based Windows in Mixed-Frequency Event Streams* (the cadence is the cycle; this is how external observers ride the cycle). Composes with federation KI *Bounded delegation surfaces default to masking bugs by default* (the fail-soft must capture errors in the result dict — silent absorption with no surfacing is the failure mode this pattern actively avoids). Generalizes the cockpit-intent-emit soft-fail import pattern from tic 267 T2b: cockpit-intent is a CGG-side library imported via sys.path (import class); memory-md-audit is a canonical-side standalone script invoked via subprocess (subprocess class). Both share fail-soft semantics across the integration-class axis.

**Explanation**: per-tic observability primitives that block /cadence on their own failure mode create cross-surface fragility — a broken audit script halts governance, which is the opposite of the audit's purpose. The fail-soft subprocess pattern decouples observability lifecycle from cadence lifecycle while preserving per-tic firing cadence. The result dict carries enough state (ran, exit_code, healthy, summary) for downstream consumers (ReBru blocks, bench-packets, /review) to distinguish "audit ran healthy" from "audit ran with breach" from "audit unavailable." Errors are not swallowed — they are made structured.

**Evidence**: same-tic n=1 first-fire at tic 269 cadence — memory-md-audit step returned HEALTHY embedded in cadence output (status=0, healthy=true, summary="[HEALTHY] MEMORY.md: 205 lines / 31,570 bytes"). Cross-tic n=2 with cockpit-intent-emit import pattern (tic 267 T2b): subprocess class + import class form the two-axis integration boundary for cadence-ops. Pattern is reusable for any canonical-side audit/observability primitive that should run per-tic but whose absence must not break /cadence.

**Lock line**: *Per-tic external integrations into cadence-ops degrade observability on failure, never the tic. Errors are structured into the result dict — never swallowed.*

**Instance — Path C `claude_agents_snapshot` (tic 273):** the cadence-ops `claude_agents_snapshot` step is a third instance of this pattern, alongside memory-md-audit (subprocess class) and cockpit-intent-emit (import class). Three clean fires at tics 271/272/273 with dynamic value variation (counts 1/2/1, each matching observed agent state) confirm live sensor reading rather than static configuration; the statusline `agents N (kinds)` FULL-mode segment is the consumer that surfaces the snapshot at glance speed (Architect perception substrate). Cross-tic n=3. Inscribed as an instance reference, not standalone doctrine — the live-sensor instantiation is the novel piece; the integration shape is the parent pattern (derivable from fail-soft subprocess + Authoritative Count Discipline + statusline architecture). Falsification: if the step produces zero counts when agents are demonstrably active (false-negative) or non-zero counts with no active agents (false-positive), the reading is not live and the instance is invalid.

<!-- promoted from cpr_path_c_claude_agents_snapshot_cadence_ops_step_promotes_eligible_tic273 (tic 273→299, /review brought forward to tic 299). Inscribed as INSTANCE reference under the parent Fail-Soft Observability Subprocess Pattern per the candidate's own non-derivability self-assessment (borderline-derivable → instance, not standalone KI). Cross-tic n=3 (counts 1/2/1, tics 271/272/273). Band: COGNITIVE. -->

---

## Inline CogPR Schema Completeness Required
<a id="inline-cogpr-schema-completeness-required"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Inline CogPR inscriptions in MEMORY.md (and other extractor-watched surfaces) MUST carry three Tier 1 schema-completeness fields: `status: pending`, `lesson:`, and `source:`. Absence of any Tier 1 field triggers `skip_schema_incomplete` at cpr-extract (the block is recognized, parsed, and discarded silently). The skip is invisible at the per-block level — writers cannot detect failure without explicit queue.jsonl grep after extraction.

**Pattern**: every inline CogPR block must declare all three Tier 1 fields adjacent to `id:`. The `status: pending` field alone is insufficient (cpr_inline_cogpr_status_pending_field_required_silent_skip_tic263); the `lesson:` field is the second Tier 1 field (cpr_inline_cogpr_lesson_field_required_sibling_to_status_pending_tic275); the `source:` field is the third. Tier 2 fields (`title`, `evidence`) and Tier 3 fields (`lesson` alone for minimal blocks) are additional — Tier 1 is the completeness floor.

**Constraint**: unifies and supersedes the per-field discipline entries:
- *Inline CogPR status:pending Field Required* (tic 263, promoted tic 267) — Tier 1 field 1
- *lesson:* field sibling (tic 275) — Tier 1 field 2
- Both are now instances of this unified parent: **any missing Tier 1 field = schema incomplete = silent skip**

Composes with *CogPR Marker Syntax Discipline* (same silent-skip inscription-discipline family), *CogPR-77 Extractor Anomaly Self-Reporting* (aggregate anomaly logging; per-block skip-id logging is the runtime patch layer), federation KI *Bounded delegation surfaces default to masking bugs* (the parser is the bounded delegate that silently masks authoring errors).

**Evidence**: tic 263 (n=2 within-arc: status:pending omission × 2) + tic 275 (lesson: omission surfaced via enrichment-swarm schema-completeness audit). Cross-tic inscription-discipline family n=4+ (CogPR Marker Syntax + status:pending + lesson: + parser-path-drift authoring + parser-path-drift validation).

**Lock line**: *Every inline CogPR carries `status: pending`, `lesson:`, and `source:` adjacent to `id:`. Any missing Tier 1 field = silent skip.*

<!-- promoted from cpr_inline_cogpr_lesson_field_required_sibling_to_status_pending_tic275 (tic 275→278) unified with cpr_inline_cogpr_status_pending_field_required_silent_skip_tic263 (tic 263→267). Unified parent inscribed at /review tic 278. Evidence: tic 263 status:pending n=2 + tic 275 lesson: field surface. Band: COGNITIVE. /review tic 278 verdict: PROMOTE CGG-rung unified parent. -->

---

## Memory-MD-Audit Breach Class Distinction
<a id="memory-md-audit-breach-class-distinction"></a>
<!-- ledger-tags: authority_class=memory_and_inscription_hygiene | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

`memory-md-audit.py` breach detection must distinguish two structurally different breach classes — STRUCTURAL breaches and PENDING-STATE breaches — because their operational response and urgency are opposite.

**Pattern**:
- **STRUCTURAL breaches** (`orphan_files`, `dead_refs`): demand immediate fix. An orphan file (no index pointer) or a dead reference (pointer to non-existent file) is always wrong regardless of review window state. These are defects.
- **PENDING-STATE breaches** (`inline_extraction_candidates` for sections pinned by `REVIEW_PINNED` locks on `status: pending` CogPRs): are expected pressure during active /review windows. They unlock automatically post-terminalization (when the CogPR is promoted, absorbed, or rejected). Treating them as urgency-level defects drives unnecessary trim cycles during the exact period when inline CogPRs are being reviewed.

**Constraint**: composes with federation KI *Governance is instrumental, not terminal* (false urgency signals waste governance cycles on expected pressure, not real drift). Composes with *Inline CogPR Schema Completeness Required* (above — REVIEW_PINNED pressure is the expected companion to in-flight schema-complete CogPRs). Note: runtime patch needed — add `breach_class` field to `audit-logs/governance/memory-md-audit.py` per-finding output to enable downstream consumers (ReBru blocks, bench-packets) to filter by class. The runtime patch is a follow-up implementation tranche; this inscription anchors the doctrine.

**Evidence**: REVIEW_PINNED inline_extraction_candidates were producing false /cadence urgency for ~10 tics (tic 266-276) because audit output did not distinguish expected pending-window pressure from structural defects. Doctrine: cross-tic n=1 first-fire (tic 276 audit-sweep during /review window).

**Lock line**: *Structural breach = fix now. Pending-state breach = expected; wait for terminalization.*

<!-- promoted from cpr_memory_md_audit_breach_class_distinction_pending_vs_structural_tic276 (tic 276→278). Source: tic 276 audit-sweep during /review window. Band: COGNITIVE. /review tic 278 verdict: PROMOTE CGG-rung. Runtime patch (breach_class field in memory-md-audit.py) is follow-up tranche. -->

---

## Triplet Self-Spawn for Substrate Moments — Three-Posture Instance Reference
<a id="triplet-self-spawn-for-substrate-moments-three-posture-instance-reference"></a>
<!-- ledger-tags: authority_class=subagent_and_swarm_delegation | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

Triplet self-spawn dispatches three same-skill instances on a single substrate signal, differentiated by POSTURE (not task), so the postures triangulate into a synthesis no single posture would produce — sub-class of Mixed Subagent + Lead Swarm Geometry.

**Instance reference**: at tic 274, a single substrate-moment signal (State-of-the-Federation autobiography arc) warranted three parallel postures: ENG/META (architectural framing), OPS/META (operational-status audit), ENG/DIRECT (implementation path). The three-way triangulation produced compound output that neither a single-posture agent nor a sequential three-step approach would have yielded in equivalent wall-clock time.

**Constraint**: sub-geometry under *Mixed Subagent + Lead Swarm Geometry* (parent). Posture is the differentiating axis — not model, not task decomposition, not domain. Three postures are sufficient for substrate-moment triangulation; more than three postures typically indicates task decomposition rather than posture triangulation.

**Promotion note**: cross-tic n=1 (tic 274 first-fire). PROMOTE-SPEC instance reference; named sub-geometry when cross-tic n=2 surfaces a second instance in a different domain. Holds for next /review.

<!-- promoted-spec from cpr_triplet_self_spawn_for_substrate_moments_three_postures_tic274 (tic 274→278). Source: tic 274 State-of-the-Federation autobiography arc. Cross-tic n=1; instance reference under Mixed Subagent + Lead Swarm Geometry. Band: COGNITIVE. /review tic 278 verdict: PROMOTE-SPEC instance reference. -->

---

## Cross-Cadence-Rails + Inbox-Marker-Dependency-Satisfaction Primitive
<a id="cross-cadence-rails-inbox-marker-dependency-satisfaction-primitive"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

When the next session needs a hot-and-ready swarm at SessionStart, the prior session's /cadence is the lowest-cost moment to manufacture the swarm's contextual rails — dispatch parallel /tactical-hydration lanes, terminate each with /consolidate, and write the harvested packets to a stable rails directory referenced by an inbox-marker-dependency-satisfaction DAG that the next session's hook-derived dispatcher reads. The pattern decouples discovery (this tic, parallelizable, lead-supervised) from execution (next tic, hook-kicked-off, dependency-DAG-ordered) across the cadence boundary.

**Two primitives this inscription names:**

1. **Cross-Cadence-Rails** — manufacturing swarm context in the prior session's /cadence rather than cold-starting in the next. Rails directories under `audit-logs/swarms/` carry RTCH packets, slice baskets, and dependency declarations authored while context is hot. Next-session dispatch reads the rails; it does NOT re-derive context.

2. **Inbox-Marker-Dependency-Satisfaction** — a DAG node structure in the inbox marker (e.g., `audit-logs/agent-mailboxes/ent_homeskillet/inbound/swarm-tic278/`) declaring `dependencies: [rail-T1, rail-T2, rail-T3]` where each dependency is a `status: complete` signal written by the rail's /consolidate step. The next session's hook-derived dispatcher reads the DAG and fires only when all declared dependencies are satisfied. This converts sequential guesswork into dependency-ordered parallel execution.

**Recommended scopes (follow-up implementation tranches):**
- `cgg-runtime/skills/swarm/SKILL.md` — doctrine the cross-cadence-rails authoring step
- `cgg-runtime/skills/cadence/SKILL.md` — doctrine the prior-session rail-manufacturing step
- Skill-body changes are follow-up tranches; this inscription carries the doctrine.

**Evidence**: cross-tic n=2 validated this session arc (tic 277 authoring → tic 278 execution); tic 278 swarm consumed rails manufactured at tic 277 /cadence. The dependency-satisfaction DAG is the missing formal primitive that converts ad-hoc rail-reading into governed dependency-ordered dispatch.

**At-scale refinement (tic 280)**: cross-tic n=3 first-fire at substantive parallel load — n=6 rails authored at tic 279 close (~190K total RTCH content across rail-T1 through rail-T6) consumed at tic 280 SessionStart by n=7 W1 subagents dispatched in a single tool-call block. Scaling observations: (i) wall-time savings of ~9-15 hr sequential compressed to ~60-90 min wall-time; (ii) zero file-collision events across 7 parallel subagents committing to 3 repos atomically; (iii) DO-NOT-PUSH boundary held cleanly with lead retaining push authority; (iv) inbox-marker-dependency-satisfaction surface honored both as completion signal AND as dispatch-time observable. Composed cleanly with CogPR-3 race fix-family (same session arc — both primitives co-validated). Federation-lift gate (cross-domain instance) opens when an external estate or sibling federation adopts the primitive.

<!-- promoted-spec from cpr_parallel_rtch_consolidate_rails_for_next_swarm_with_inbox_marker_dependency_signaling_tic277 (tic 277→278). Source: tic 277 /cadence rail authoring → tic 278 swarm execution. Cross-tic n=2. Band: COGNITIVE. /review tic 278 verdict: PROMOTE-SPEC CGG-rung under /swarm doctrine extension. Skill-body changes (swarm/SKILL.md + cadence/SKILL.md) are follow-up tranches. Refined-spec at tic 282 by cpr_cross_cadence_rails_primitive_first_fire_at_scale_tic280 (cross-tic n=3 at-scale validation: n=6 rails + n=7 subagents; wall-time savings ~9-15 hr → ~60-90 min; zero file-collision). Composed with CogPR-3 race fix-family in same session arc. -->

<!-- promoted from cpr_fail_soft_observability_step_in_cadence_ops_tic268 (/review tic 269 → 270). Same-tic n=1 first-fire HEALTHY at tic 269; cross-tic n=2 with cockpit-intent-emit import pattern. Complements CGG KI Cycle-Based Windows in Mixed-Frequency Event Streams. Composes with federation KI Bounded delegation surfaces default to masking bugs. Band: COGNITIVE. Source: tic 268 close handoff + cadence-ops step 5 integration (CGG f18468d). -->

---

## RTCH Harvest Reader — Terminal-Valve Discipline
<a id="rtch-harvest-reader-terminal-valve-discipline"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

RTCH harvests over append-only ledgers (queue.jsonl, shape-ledger.jsonl, signal files) must read the terminal-valve projection, not aggregate raw emissions; otherwise stale pre-promotion state masquerades as live overdue work.

**Pattern**: Authoritative-set read discipline at the harvest boundary — before counting, ranking, or surfacing any entry from an append-only log, project the terminal state (latest entry per id, valve-filtered to terminal status). Never accumulate raw line counts or status distributions directly from the raw file. The terminal-valve projection is the canonical view; raw emissions are implementation detail.

**Constraint**: Refines federation KI *Authoritative-Set Readers Must Read the Manifest, Not Aggregate Raw Emissions* (same authoritative-set discipline applied specifically at the RTCH harvest boundary). Composes with CGG KI *Terminal-State Valve Pattern* (reader-side application of the write-side valve doctrine). The violation surface is tactical-hydration scripts that grep or count lines without first projecting terminal state — these produce falsely-overdue work backlogs.

**Evidence**: tic 278 wave1 RTCH harvest (water-cycle-CogPR-backfill task) read pre-promotion duplicates for a CogPR at lines 427/540/669 of queue.jsonl without consulting terminal-valve; the CogPR had already been promoted at line 859 (tic 246). Rail T4 harvest surfaced the CogPR as overdue — a falsification caught by Architect correction. Cross-tic n=2 (tic 246 promotion + tic 278 false-overdue detection).

**Lock line**: *RTCH reads terminal-valve projection; raw emissions are write-side artifact only.*

<!-- promoted from cpr_rtch_harvest_reader_pattern_terminal_valve_violation_tic278 (tic 278→279). Source: tic 278 wave1 water-cycle-CogPR-backfill task — Architect-corrected falsification. Rail T4 RTCH harvest read pre-promotion duplicates without terminal-valve. Cross-tic n=2. Band: COGNITIVE. /review tic 279 verdict: PROMOTE CGG-rung. -->

---

## queue.jsonl Drift-Audit Primitive
<a id="queue-jsonl-drift-audit-primitive"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

queue.jsonl needs a drift-audit primitive (analogous to memory-md-audit.py) that projects terminal-state and flags genuinely overdue pre-promotion rows, distinguishing them from falsely-overdue ones produced by reader misreads.

**Pattern**: A standalone script (`cgg-runtime/scripts/queue-drift-audit.py`, analogous to `audit-logs/governance/memory-md-audit.py`) that: (1) reads queue.jsonl and projects terminal state per id via latest-entry-per-id semantics; (2) classifies each id as terminal (promoted/deferred/skipped/absorbed) or active (pending/extracted); (3) for active ids, computes age in tics and flags genuinely overdue entries; (4) for terminal ids, reports any raw-emission duplicates that could mislead RTCH harvest readers; (5) emits structured output (breach_class, id, age_tics, duplicate_count) consumable by bench-packet-prep and ReBru blocks.

**Constraint**: Composes with federation KI *Authoritative-Set Readers Must Read the Manifest, Not Aggregate Raw Emissions* (the audit primitive IS the manifest-projection mechanism for queue.jsonl). Composes with *RTCH Harvest Reader — Terminal-Valve Discipline* (above — the audit primitive surfaces the raw-emission duplicates that cause harvest misreads). Composes with memory-md-audit.py precedent (same structural pattern: project state → classify breaches → emit structured findings). Without this primitive, genuine overdue work is indistinguishable from falsely-overdue entries at harvest time.

**Implementation tranche owed**: `cgg-runtime/scripts/queue-drift-audit.py` (~45 min, next gate). Doctrine inscribes now; script implementation defers per Verdict-Shape KI (PROMOTE-SPEC authorizes-but-defers).

**Evidence**: tic 278 wave1 RTCH harvest demonstrated the falsification class — CogPR already promoted at line 859 was surfaced as overdue because raw duplicates at lines 427/540/669 were read without terminal-valve projection. The absence of a drift-audit primitive means the gap is invisible until a harvest misread produces an Architect-corrected falsification. Cross-tic n=1 first-fire (tic 278).

**Lock line**: *queue.jsonl drift-audit primitive is the queue-health observability primitive; its absence makes genuine vs. falsely-overdue indistinguishable.*

<!-- promoted-spec from cpr_queue_jsonl_drift_audit_primitive_tic278 (tic 278→279). Source: tic 278 wave1 RTCH harvest falsification; same surface as RTCH Harvest Reader inscription above. Cross-tic n=1 first-fire. Band: COGNITIVE. /review tic 279 verdict: PROMOTE-SPEC CGG-rung. Implementation tranche: cgg-runtime/scripts/queue-drift-audit.py (~45 min, next gate). -->

---

## review-close-check Verifier — Dehydration Blindspot
<a id="review-close-check-verifier-dehydration-blindspot"></a>
<!-- ledger-tags: authority_class=mandate_and_cadence_ops | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

review-close-check.py searches canonical/CLAUDE.md for promoted CogPR text and emits `promoted_text_missing` findings when not found. Pass-4-A constitutional dehydration moved promoted CogPR body text from canonical/CLAUDE.md (compact root) to `audit-logs/governance/constitution-ledger/ledger.md` (multi-axis tagged ledger). After dehydration, the verifier reports false-positive `promoted_text_missing` for legacy CogPRs whose text now lives in ledger.md (tic 279 review_close_check: 81 such findings + 29 orphaned_promotion findings; sample CogPRs 27/36/39/40/45 confirmed pre-Pass-4 promotions whose body is in ledger.md). The verifier needs extension to ALSO search ledger.md before emitting promoted_text_missing.

**Pattern**: When a constitutional surface undergoes dehydration (body text relocated from compact root to ledger), all downstream verifiers that search the old surface must be extended to also search the new surface. This is the read-side complement to the write-side dehydration — the score moved; the runtime must follow.

**Constraint**: Concrete instance of federation KI *Phased Dehydration as Multi-Tic Temporal Trajectory* (Pass-4-A is a moving-target multi-tic process; this names the downstream tool that didn't get the memo). Concrete instance of federation KI *Conductor-Score-Runtime Parity* (score moved during Pass-4-A; verifier runtime didn't follow — mechanism class 4: runtime ownership for behavior-bearing artifacts). Distinct from *Artifact-Count-≠-1 Fix-Family* (that names N=0/N=2 cardinality failures at emit-side; this names a DIFFERENT failure class — verifier searches stale target after substrate dehydration). Complements, not duplicates.

**Implementation tranche owed**: extend `cgg-runtime/scripts/review-close-check.py` search path to include `audit-logs/governance/constitution-ledger/ledger.md`; treat ledger-anchor matches as valid for `promoted_text` (~30 min, next gate). Doctrine inscribes now; implementation defers per Verdict-Shape KI.

**Evidence**: tic 279 review_close_check Mogul mandate cycle — 111 total findings (110 errors / 1 warning); 81 `promoted_text_missing` against canonical/CLAUDE.md targets for pre-Pass-4 CogPR IDs whose body text was relocated to ledger.md per Pass-4-A dehydration plan. Report at audit-logs/mogul/cycle-reports/review-close-checks/tic-279-20260523T032314-check.json. Cross-tic n=1 first-fire (tic 279).

**Lock line**: *Dehydration is a two-step migration: relocate body text AND update all verifiers that search the old location.*

<!-- promoted-spec from cpr_review_close_check_verifier_dehydration_blindspot_tic279 (tic 279→279). Source: tic 279 Mogul mandate review_close_check cycle — 81 false-positive promoted_text_missing findings post-Pass-4-A dehydration. Band: COGNITIVE. /review tic 279 verdict: PROMOTE-SPEC CGG-rung. Implementation tranche: review-close-check.py ledger.md search extension (~30 min, next gate). -->

---

## Cockpit.intent Invocation Discipline (T2b)
<a id="cockpit-intent-invocation-discipline-t2b"></a>
<!-- ledger-tags: authority_class=pipeline_and_integration | rung=domain | domain=context-grapple-gun | dehydrated_tic=314 -->

`cockpit.intent` (30th envelope class, `ak_control_room/envelopes.yaml`) emits via three governed surfaces per T2b spec (`audit-logs/governance/cockpit-intent-t2b-invocation-discipline-spec-tic264.md`); a fourth surface (I-C per-skill instrumentation) is deferred to T2c.

**I-A — Posture-Toggle Hook** (`cgg-runtime/hooks/cockpit-intent-posture-toggle.py`). UserPromptSubmit hook scans the prompt for `[Posture → X/Y]` toggles or `POSTURE:` banner lines and emits an envelope; `intent_class` derives from the new posture (`*/META → observe`, `*/DIRECT → free`). Registered in `hooks/hooks.json` (plugin) and in user-scope `~/.claude/settings.json` (post-install). Fail-soft: hook never blocks UserPromptSubmit.

**I-B — Cadence-Emit Step** (`cgg-runtime/scripts/cadence-ops.py` main step 4). After tic + conformation + mandate, cadence-ops invokes the Python emitter with `intent_class: observe` — every counted /cadence produces a declared-state envelope alongside the conformation snapshot. Documented in `cgg-runtime/skills/cadence/SKILL.md` Step 0.5 output table. Fail-soft pattern follows the *Cadence-Ops Fail-Soft Observability Subprocess Pattern* (import class variant): errors land in `result["cockpit_intent"]` but never block cadence output.

**I-D — Manual REST Escape Hatch.** The T2a POST endpoint at `/api/governance/cockpit/intent` (vite-governance-api.ts) remains accessible without code changes for diagnostic probes, calibration evidence collection, and replay of missed emissions. Two invocation paths are documented in the T2b spec Appendix A:

- **curl** against the vite dev server (`http://localhost:8080/api/governance/cockpit/intent`); requires `npm run dev` under `canonical_developer/ak-control-room/`.
- **Python** (CLI-only / headless context) via `cgg-runtime/scripts/lib/cockpit_intent_emit.py` `emit_intent()` — writes byte-shape-parity rows to the same `audit-logs/cockpit/intents/YYYY-MM-DD.jsonl` the POST endpoint writes to. Use this path when the vite server is unavailable.

Validation rules are identical across all four paths (I-A / I-B / I-D-curl / I-D-python) per `envelopes.yaml#cockpit.intent.when_included`. The Python emitter applies per-tic dedup keyed on `(source_object_ref, source_path, intent_class, posture, mode)`; the vite POST endpoint does NOT currently apply dedup — manual probes that need dedup should route through the Python helper.

**Pattern**: I-A and I-B are operational emission paths; I-D is the diagnostic / replay escape hatch. Naming the escape hatch explicitly in doctrine prevents future tightening from inadvertently breaking diagnostic affordances (composes with federation KI *Identity precedes capability* — the operator probe path is a first-class invocation surface, not an exception).

<!-- promoted-spec from cpr_cockpit_intent_t2b_invocation_discipline_spec_tic264 (PROMOTE-SPEC at /review tic 267 docket #5). Implementation tranches I-A + I-B landed at CGG commits 5a77d29 + a2b71b4 (tic 267). W3-B3 (tic 282) residue takedown: hooks.json plugin registration for I-A, cadence/SKILL.md Step 0.5 documentation of I-B output key, this CGG CLAUDE.md section documenting I-D escape hatch. I-C deferred to T2c per spec. Band: COGNITIVE. Domain rung: CGG. -->

---

### Hydration-tooling vs runtime-tooling sync-lane distinction

<a id="hydration-tooling-vs-runtime-tooling-sync-lane-distinction"></a>

**Ledger tags:**
- `invariant_id`: `cpr_hydration_runtime_sync_lane_distinction_tic316`
- `terrain_class`: `sync_and_install_parity`
- `lanes`: ["sync_and_install_parity"]
- `era`: `cpr_era_tic_200_plus`
- `target_rung`: `domain`
- `compact_root_status`: `ledger_only`
- `first_appearance_tic`: `219`
- `promoted_tic`: `316`
- `confidence_tier`: `reinforced`

**Body:**

- **Hydration-tooling and runtime-tooling occupy distinct sync lanes** — a domain directory may legitimately carry NO sync-manifest entry. Runtime tooling (skills, agents, hooks, scripts that install to `~/.claude/`) is sync-manifest-tracked and must maintain canonical↔installed byte parity. Hydration tooling (estate-seed packaging, scope contracts, drift-audit scaffolds that are consumed in-place at the authoring rung and never install to a runtime tree) is NOT sync-tracked, and its absence from the sync manifest is correct, not drift. A verifier that treats every domain dir as runtime-tracked produces false drift findings. The distinction: does the artifact have a runtime install target? If no, it is hydration-lane and sync-manifest-exempt by design.

<!-- promoted from cpr_ce04128acd44699f (freeze-lifted tranche, /review tic 316). Source: EstateSeed tic 219 — a domain dir with no sync-manifest entry read as drift until the hydration/runtime lane split was named. Band: COGNITIVE. -->

---

### Status-axes separation (one status field collapses orthogonal lifecycle axes)

<a id="status-axes-separation"></a>

**Ledger tags:**
- `invariant_id`: `cpr_status_axes_separation_tic316`
- `terrain_class`: `queue_and_state`
- `lanes`: ["queue_and_state", "identity_and_capability"]
- `era`: `cpr_era_tic_200_plus`
- `target_rung`: `domain`
- `compact_root_status`: `ledger_only`
- `first_appearance_tic`: `219`
- `promoted_tic`: `316`
- `confidence_tier`: `reinforced`
- `relations`: composes_with `identity-precedes-capability` (capabilities derived not stored)

**Body:**

- **A single overloaded `status` field collapses orthogonal lifecycle axes and produces wrong-class verdicts at boundaries** — when one `status` enum is asked to carry spec-validity AND exercise-state AND install-parity AND activation-state AND review-pending simultaneously, a reader at any boundary mis-classifies because the axes are independent. The cure is to separate the axes (status_class × invocation_policy, or explicit per-axis fields) so each boundary reads the axis it actually gates on. This is the state-surface analogue of "Identity precedes capability" (capabilities derived from standing+roles+jurisdiction+lifecycle, never stored as one fixed scalar): governance-entity status is likewise multi-axis and must not be stored as one collapsed value.

<!-- promoted from cpr_190620613fa08a3f (freeze-lifted tranche, /review tic 316). Source: tic 219→220 cbux/civil entity misclassification — overloaded status field caused wrong activity-class verdicts at dispatch boundaries. Band: COGNITIVE. -->

---

### First-cycle independent-audit-value test for long-dormant governance entities

<a id="first-cycle-independent-audit-value-test"></a>

**Ledger tags:**
- `invariant_id`: `cpr_first_cycle_audit_value_test_tic316`
- `terrain_class`: `estate_relations`
- `lanes`: ["estate_relations", "review_and_promotion"]
- `era`: `cpr_era_tic_200_plus`
- `target_rung`: `domain`
- `compact_root_status`: `ledger_only`
- `first_appearance_tic`: `~220`
- `promoted_tic`: `316`
- `confidence_tier`: `tentative`
- `relations`: composes_with `governance-is-instrumental-not-terminal`

**Body:**

- **RESTART-vs-ABSORB for a long-dormant/bypassed governance entity is decided by a first-cycle independent-audit-value test** — when a governance entity has been dormant or routed-around for many tics, the question "revive it or absorb its function elsewhere" is answered empirically: run exactly ONE cycle and ask whether that cycle surfaced anything the other (live) surfaces missed. If cycle-1 finds independent value → RESTART (the entity has a distinct lens). If cycle-1 only re-derives what live surfaces already produce → ABSORB (the lens is redundant). This keeps dormant-entity decisions evidence-based rather than sentiment-based, and instantiates "governance is instrumental, not terminal" — an entity earns its existence by library-exercise value, not by having once been chartered.

<!-- promoted from cpr_e2598252b1deba47 (freeze-lifted tranche, /review tic 316). Band: COGNITIVE. -->

---

### Mirror-inscription is the cheap reversible bridge for extraction-lane coverage gaps

<a id="mirror-inscription-cheap-reversible-bridge"></a>

**Ledger tags:**
- `invariant_id`: `cpr_mirror_inscription_reversible_bridge_tic316`
- `terrain_class`: `signal_and_queue_manifold`
- `lanes`: ["signal_and_queue_manifold", "review_and_promotion"]
- `era`: `cpr_era_tic_200_plus`
- `target_rung`: `domain`
- `compact_root_status`: `ledger_only`
- `first_appearance_tic`: `241`
- `promoted_tic`: `316`
- `confidence_tier`: `reinforced`
- `relations`: refines `emitter-surface-declared-interface`

**Body:**

- **When a CogPR is inscribed in a surface the extractor does not scan, mirror-inscribe it (same id) to a known extraction surface rather than widening hook coverage** — the cheap, reversible fix for an extraction-lane coverage gap is a same-id mirror entry on an already-scanned surface, not expanding `cpr-extract.py`'s scan set (which broadens the hook's surface area and risk). The mirror is reversible (delete it; nothing else changed) and self-cleaning (terminal-state-valve dedups by id). Widening coverage is the heavier, less-reversible move reserved for when mirroring recurs enough to justify it. Refines the Emitter-Surface-Declared-Interface contract: the bridge respects the declared interface instead of mutating it.

<!-- promoted from cpr_mirror_inscription_cheap_reversible_bridge_tic241 (freeze-lifted tranche, /review tic 316). Band: COGNITIVE. -->

---

### Pipeline silence must be auditable (zero-evidence runs must self-report why)

<a id="pipeline-silence-must-be-auditable"></a>

**Ledger tags:**
- `invariant_id`: `cpr_pipeline_silence_must_be_auditable_tic316`
- `terrain_class`: `forensic_and_drift`
- `lanes`: ["forensic_and_drift", "verification_and_proof"]
- `era`: `cpr_era_tic_100_149`
- `target_rung`: `domain`
- `compact_root_status`: `ledger_only`
- `first_appearance_tic`: `166`
- `promoted_tic`: `316`
- `confidence_tier`: `reinforced`
- `relations`: composes_with `extractor-anomaly-self-reporting`, `output-anomalies-...-differential-verification`

**Body:**

- **A pipeline that produces no output must record WHY, so "scanned, found nothing" is distinguishable from "never scanned"** — an enrichment/mining/scan pipeline that silently produces zero output is indistinguishable from one that never ran. The protection: on a zero-evidence run, write an auditable record (`enrichment_scanned_at`, `scan_count`, `no_evidence_reason`) naming what was missing (e.g. empty source_date, missing subsystems, source-as-path penalty). This converts silent starvation into a legible signal. (Validated live: the tic-202 deferred CogPRs are the exact zero-evidence victims, now carrying `no_evidence_reason`. The remaining structural fix-vectors — source_date default at cpr-extract.py:539, subsystems.json data file — are tracked as CGG-runtime hardening, separate from this principle.)

<!-- promoted from cpr_enrichment_pipeline_silent_starvation_tic166 (freeze-lifted tranche, /review tic 316; reduced to the auditability principle). Source: tic 166 enrichment investigation; fix #1 confirmed landed (scanner writes no_evidence_reason). Band: COGNITIVE. -->

---

### Advertised containment scope is not wired containment scope

<a id="advertised-containment-scope-is-not-wired-containment-scope"></a>

**Ledger tags:**
- `invariant_id`: `cpr_advertised_containment_scope_is_not_wired_containment_scope_tic317`
- `terrain_class`: `pipeline_and_integration`
- `lanes`: ["pipeline_and_integration", "verification_and_proof", "forensic_and_drift"]
- `era`: `cpr_era_tic_300_349`
- `target_rung`: `domain`
- `compact_root_status`: `ledger_only`
- `first_appearance_tic`: `317`
- `promoted_tic`: `321`
- `confidence_tier`: `tentative`
- `relations`: refines `wire-cut-scoping-by-capability-class` (parent says scopes must EXIST; this says each must be WIRED + tested); composes_with federation KI `presence-observation-fallacy-guard` (presence-of-script-does-not-prove-runtime-execution)

**Body:**

- **A containment kill-switch that advertises a menu of capability scopes does NOT guarantee each scope is actually wired into the emitter it claims to gate** — at tic 317 the `.wire-cut-signals` scope was DEAD: `wire_check_signals()` existed in `wire-cutter.sh` and the scope was documented, but the Python signal emitter (`inbox-envelope.py emit_attention_debt_signals`) never called it, so arming `.wire-cut-signals` alone would NOT have stopped the attention-debt emitter — only hook-level cuts (`.wire-cut-all/-hooks/-session/-gate`, which kill the triggering hook) worked. The prior 200+ attention-debt signal loop was contained by a hook-level cut, masking that the granular surgical cut was non-functional. Discipline: a containment scope must be VERIFIED to fire at the emitter boundary (an **arm-and-observe-zero** test — arm each scope in a sandbox, assert the emitter returns empty), not assumed present because it appears in the switch menu. Presence of a scope in the menu ≠ wired enforcement at the emitter. This is the Presence/Observation Fallacy Guard applied to the containment layer, and the prevention-side complement to Wire-Cut Scoping by Capability Class (which says scopes must EXIST; this says each must be WIRED + tested). Detection affordance: a periodic kill-switch self-test mechanizes it.

<!-- promoted from cpr_advertised_containment_scope_is_not_wired_containment_scope_tic317 (tic 317→321, /review unified docket). Source: tic 317 containment-wirecutter forensic. n=1 cross-tic, anchored to inscribed KI family (Wire-Cut Scoping + Presence/Observation Fallacy Guard). Band: COGNITIVE. -->

---

### Born-truth reconstruction is a read job keyed by birth-tic, not a grep

<a id="born-truth-reconstruction-is-a-read-job-keyed-by-birth-tic"></a>

**Ledger tags:**
- `invariant_id`: `cpr_born_truth_reconstruction_is_a_read_job_keyed_by_birth_tic_not_grep_tic319`
- `terrain_class`: `verification_and_proof`
- `lanes`: ["verification_and_proof", "signal_and_queue_manifold", "memory_and_inscription"]
- `era`: `cpr_era_tic_300_349`
- `target_rung`: `domain`
- `compact_root_status`: `ledger_only`
- `first_appearance_tic`: `319`
- `promoted_tic`: `321`
- `confidence_tier`: `reinforced`
- `relations`: composes_with `rtch-harvest-reader-terminal-valve-discipline`; refines the "distrust the cheap proxy" family; folds in the **reconstruction-is-parity-not-hindsight** enrichment

**Body:**

- **Missing governance signal is NOT keyword-regex-greppable, because the tension was resolved in SUBSTANCE under different words than its slug** — un-mapped council resolutions, the rationale-arc behind a route/outcome, the "lived friction" behind a contract-only invariant: a surveillance/privacy resolution can live inside a "data ownership" discussion with neither slug present. Reaching for grep and concluding "found nothing → can't certify" is the cop-out, and it twice produced false numbers in one session: (1) a claimed "41/102 production-available route ceiling" that was actually a LOWER-BOUND on a truncated cold slice (the route was truncated OUT, not absent — the parity audit proved it recoverable from the full trace); (2) a "0/40 councils exercised" that was a grep artifact, not a finding. The signal exists in the system's OWN lineage. **Reconstruction is a READ job, keyed by the BIRTH-TIC every CogPR/invariant carries in its ledger provenance** ("promoted from CogPR-N, tic 21→22, arena-sourced"): open the convo-log / arena AT that tic and semantically locate the arc (tension → opposition → move → resolution). That is production-available born-truth, NOT hindsight — **reconstruction is parity, not hindsight**: hindsight injects the gold LABEL; resolving the trace's own visible evidence is legitimate, and a cold-slice grep floor is a LOWER-BOUND, not a ceiling. Corollary: the constitutional corpus is MULTI-SCOPE (federation constitution-ledger + CGG cgg-ledger + ak-control-room) — readiness counts must span all scopes, not just one federation slice.

<!-- promoted from cpr_born_truth_reconstruction_is_a_read_job_keyed_by_birth_tic_not_grep_tic319 (tic 319→321, /review unified docket; MODIFY — folded the reconstruction-is-parity-not-hindsight enrichment into the body, upgrading tier tentative→reinforced). Source: tic 319 edge-corpus reconstruction; n=2 this session (41-not-a-ceiling + 0/40-grep-artifact) + cross-instance corroboration (parallel-instance council-scan grep traps). Band: COGNITIVE. -->

---

### Boot-injection lane: a tic-gated broadcast pointer feeding both boot seams

<a id="boot-injection-lane-tic-gated-broadcast-pointer"></a>

**Ledger tags:**
- `invariant_id`: `cpr_boot_injection_lane_tic_gated_broadcast_pointer_tic320`
- `terrain_class`: `mandate_and_cadence_ops`
- `lanes`: ["mandate_and_cadence_ops", "pipeline_and_integration"]
- `era`: `cpr_era_tic_300_349`
- `target_rung`: `domain`
- `compact_root_status`: `ledger_only`
- `first_appearance_tic`: `320`
- `promoted_tic`: `321`
- `confidence_tier`: `tentative`
- `relations`: complements the citizen-boot REMINDERS lane (`autonomous_kernel/citizen-boot-reminders-spec.md §3` — same seams, different payload class); inherits loop-safety from `signal-id-determinism` + `dedup-at-write-using-canonical-identity` (mints no signals at all)

**Body:**

- **A tic-gated boot-injection lane delivers a broadcast pointer into BOTH boot seams for a bounded tic window with an auto re-eval reminder at a target tic** — registry `audit-logs/boot-injections/active.jsonl` + renderer `cgg-runtime/scripts/boot-injection.py` feed both `session-restore.sh` (SessionStart/orchestrator) AND `subagent-citizen-boot.py` (SubagentStart/every recognized citizen, EVEN WHEN the inbox is empty). It is the ambient-injection complement to the citizen-boot reminders lane: the reminders lane carries per-actor scheduled obligations; this lane carries a broadcast pointer with a tic window and an audience router (all / orchestrator / citizens / ent_*). **Loop-safe BY CONSTRUCTION** — read-only render over the registry, mints no signals, writes no governance state, dedup-on-unchanged at the calling hook — so the §5 200+ signal-runaway class cannot recur through it. A broadcast-pointer-with-tic-window is distinct enough from a per-actor scheduled obligation to warrant its own naming. Install-path gotcha: callers MUST pass `--zone-root` because the installed copy under `~/.claude` resolves zone by `__file__` walk and cannot find canonical's `.ticzone`; the renderer also falls back to cwd + `CLAUDE_PROJECT_DIR`.

<!-- promoted from cpr_boot_injection_lane_tic_gated_broadcast_pointer_tic320 (tic 320→321, /review unified docket). Source: tic 320 autonomous-kernel-activation build; live-validated (citizen→glossary pointer, dedup silent, general-purpose→none; firing in the tic-321 SessionStart). CGG af2b4d6 + canonical 51bb4ecc. Band: COGNITIVE. -->

**Coverage-topology refinement (ABSORBED tic 324):** PUSH-nav / boot-injection is **actor-scoped, not board-scoped** — it reaches every recognized citizen at boot regardless of which board they land on. This is what makes the ambient injection layer board-of-boards-COMPLETE precisely BECAUSE the PULL-nav layer (compact-root → ledger-anchor pointers) is **non-uniform**: PULL-nav only exists on DEHYDRATED boards (measured tic 321: 2 of 10 marked rungs — federation + CGG, both ~100% resolve; the other 8 hold doctrine inline with zero pointers). An agent landing on an inline board vs a dehydrated board sees structurally different surfaces, and the uniform injection is what broadcasts the map (GLOSSARY § Doctrine Surface Navigation) that explains the split. **Injection compensates for non-uniform dehydration.** WALK-nav (`load_doctrine_chain` rung-walk) spans all 10 boards, returning None gracefully for a marked rung with no CLAUDE.md. Total tic-321 measure: 341 pointers (194 KI + 147 MEMORY index), ~100% live. <!-- absorbed from cpr_injection_coverage_is_actor_scoped_pull_nav_is_board_scoped_tic321 (tic 321→324, /review unified docket). ABSORB into boot-injection-lane KI as the coverage-rationale that explains why the lane structurally exists. Source: tic 321 board-of-boards navigation-coverage audit. Band: COGNITIVE. -->

**Living-capture-plus-indefinite-injection refinement (PROMOTED tic 381, /review 381):** the lane has a SECOND payload class beyond the tic-windowed broadcast pointer — an **indefinite** injection (`inject_until_tic 9999`, `reminder_at_tic null`) pointing at a **living capture doc** for a load-bearing, multi-turn Architect exploration that is NOT yet doctrine. The correct vehicle for such an exploration is the pair: (1) ONE living capture doc in `audit-logs/governance/` marked `status: exploration` (NOT forward-spec, NOT doctrine), folded turn-by-turn as the model thickens, re-committed at settling points ("don't lose the exact contour" > "don't churn commits"); (2) an indefinite boot-injection with audience-routing pointing future boots at it with a "KEEP LOGGING" directive. This is neither premature CogPR promotion (which corrupts a live exploration into false-doctrine) nor loss to context decay — the candidate nugget is flagged INSIDE the doc for /review, not inscribed. Composes `Binder-Addendum-Inscription-Preservation` (preserve the body, append turn-by-turn) + `Receipt-discipline-over-excitement-velocity` (the capture surfaces compression; the human gates promotion). **IS-NOT:** NOT a mandate to boot-inject every exploration — only Architect-directed, load-bearing, multi-turn ones; AND the freshness discipline (`non-ledger-tracking-artifacts...` + the zombie-holds class-conflation refinement) applies — an indefinite `inject_until` is itself a tracking-artifact freshness obligation that must be re-evaluated when the exploration settles into doctrine or retires. Validated tic 380→381: the `era-design-self-evident-carry-tic380` injection fired in the tic-381 SessionStart, and the capture doc was logged into again (§3.12) the same session it pointed a new instance at. <!-- promoted from cpr_live_architect_exploration_belongs_in_living_capture_plus_indefinite_boot_injection_tic380 (tic 380→381, /review 381 unified docket). Source: tic 380 Era-Design exploration; era-design-self-evident-carry-tic380 boot-injection. Band: COGNITIVE. Confidence_tier: reinforced. -->

---

### Boot-seam duality — the primary boots via SessionStart, spawned citizens via SubagentStart

<a id="boot-seam-duality-primary-sessionstart-citizens-subagentstart"></a>

**Ledger tags:**
- `invariant_id`: `cpr_boot_seam_duality_primary_sessionstart_vs_citizens_subagentstart_tic332`
- `terrain_class`: `sync_and_install_parity`
- `lanes`: ["sync_and_install_parity", "mandate_and_cadence_ops", "pipeline_and_integration"]
- `era`: `cpr_era_tic_300_349`
- `target_rung`: `domain`
- `compact_root_status`: `compact`
- `first_appearance_tic`: `332`
- `promoted_tic`: `333`
- `confidence_tier`: `reinforced`
- `relations`: composes `trigger-routing-is-mandatory` (federation) + `runtime-sync-parity-verification`; complements `boot-injection-lane-tic-gated-broadcast-pointer` (same two seams, different payload class)

**Body:**

- **The primary orchestrator and spawned citizens boot through DIFFERENT seams; a boot injection meant for "every citizen including the primary" must wire BOTH seams, not one.** `subagent-citizen-boot.py` is a **SubagentStart** hook — it fires ONLY for spawned citizens, NEVER for the primary orchestrator (`ent_homeskillet`), who boots via **SessionStart** (`session-restore.sh`). A boot-injection that must reach "every citizen including the primary" is therefore TWO wirings: SessionStart (primary; PREPEND the payload ahead of the handoff) + SubagentStart (spawned citizens). Wiring only SubagentStart silently omits the most important recipient — the primary. The two install surfaces also differ in a way that bears directly on Runtime-Sync-Parity: SubagentStart is registered in project `.claude/settings.json` and fires **from SOURCE**; SessionStart fires via a `~/.claude/hooks/session-restore-patch.sh` shim that **execs an INSTALLED copy** of the hook — so sync-parity must be verified on the *installed* SessionStart hook specifically, not assumed from source correctness. Architect-surfaced at the tic-332 implementation gate ("subagentstart not going to fire on homeskillet, right? so it needs to be injected into the thread prepending the handoff").

<!-- promoted from cpr_boot_seam_duality_primary_sessionstart_vs_citizens_subagentstart_tic332 (tic 332→333, /review 333 unified docket). Source: tic-332 both-seam worldview wiring + Architect seam-split correction at the impl gate; live-validated tic 333 — the FIRST NATIVE BOOT, where the compiled worldview reached the primary via SessionStart exactly as the invariant predicts. Band: COGNITIVE. -->

---

### Local-settings activation ≠ tracked-distribution registration — a third distribution-boundary axis

<a id="local-settings-activation-not-tracked-distribution-registration"></a>

**Ledger tags:**
- `invariant_id`: `cpr_seam_local_activation_vs_tracked_distribution_tic351`
- `terrain_class`: `sync_and_install_parity`
- `lanes`: ["sync_and_install_parity", "pipeline_and_integration"]
- `era`: `cpr_era_tic_350_plus`
- `target_rung`: `domain`
- `compact_root_status`: `ledger_only`
- `first_appearance_tic`: `351`
- `promoted_tic`: `361`
- `confidence_tier`: `reinforced`
- `relations`: complements `boot-seam-duality-primary-sessionstart-citizens-subagentstart` (same distribution-boundary family — Boot-Seam Duality governs seam SELECTION across the two boot seams; THIS governs surface REGISTRATION, local vs tracked); refines federation `presence-observation-fallacy-guard` with a new typed variant `config-presence-in-a-local-surface-does-not-prove-portable-wiring`; distinct from `runtime-sync-parity-verification` (byte parity of an already-distributed surface, not registration portability)

**Body:**

- **A delivery seam proven LIVE LOCALLY is not proven PORTABLE.** Config-presence in an operator-local / gitignored settings surface (`.claude/settings.json`) is *local-truth*: it activates the seam on THIS machine but is absent from the tracked distribution surface, so a fresh clone / different operator / plugin-install gets the seam **silently omitted**. Before investing canonical payload onto a delivery seam, verify the seam is registered on a TRACKED distribution surface, not merely active locally — *"do not write canonical payload onto a local-only seam."* The fix is **additive** (register on the tracked surface) and must NOT remove the local activation when the tracked surface is not loaded in the current environment (e.g. plugin not enabled), else you trade a proven-local seam for an unproven-here tracked one — the same anti-pattern inverted. Local settings = environment activation; tracked plugin manifest = canonical distribution; both can legitimately coexist (double-fire, if both ever active, is covered by the consumer's dedup-on-unchanged). This sits in the distribution-boundary family next to Boot-Seam Duality (which seam) as a distinct third axis (which surface registers it).

**Evidence.** Born tic 351 — SubagentStart reachability slice. The `subagent-citizen-boot.py` SubagentStart hook was registered ONLY in gitignored `.claude/settings.json` (CGG plugin not loaded in this env — the local entry the only active path); the TRACKED plugin `hooks/hooks.json` registered SessionStart citizen-boot but NEVER SubagentStart — so every plugin-install got primary-boot but no per-citizen boot. Fix CGG `bc7cbb3` (added SubagentStart to tracked `hooks/hooks.json` parallel to SessionStart, `${CLAUDE_PLUGIN_ROOT}` convention, no matcher; script filters by actor-registry). Verified: JSON valid; registered citizen → worldview+CITIZEN-BOOT inject; general-purpose → silent; seen-state net-zero; local `.claude/settings.json` KEPT (this env's activation). Empirical pre-existing fires corroborated reach (receipts tic 341/344 from crisis_steward / cbux_steward / civil_engineer).

<!-- promoted from cpr_seam_local_activation_vs_tracked_distribution_tic351 (tic 351→361, /review 361 unified docket; Architect MERGE-PROMOTE directive — neighbor-linked into the Boot-Seam Duality / distribution-boundary family rather than floating as an unrelated KI; ledger mechanics favor a standalone tagged entry with explicit `relations` over folding into the tic-332 invariant body). Fix landed CGG bc7cbb3. Band: COGNITIVE. -->

---

### Budget-exempt closure framing + unit-safe truncation

<a id="budget-exempt-closure-framing-and-unit-safe-truncation"></a>

**Ledger tags:**
- `invariant_id`: `cpr_budget_exempt_closure_framing_and_unit_safe_truncation_tic332`
- `terrain_class`: `verification_and_proof_discipline`
- `lanes`: ["verification_and_proof_discipline", "pipeline_and_integration"]
- `era`: `cpr_era_tic_300_349`
- `target_rung`: `domain`
- `compact_root_status`: `compact`
- `first_appearance_tic`: `332`
- `promoted_tic`: `333`
- `confidence_tier`: `reinforced`
- `relations`: refines `boundary-aware-body-extraction` (extends boundary-discipline from fixed line-offsets to typed atomic units carrying execution semantics); generalizes beyond the worldview compiler to any budgeted render of typed/atomic units carrying a closure obligation

**Body:**

- **A loop-closing/safety ritual guarding a budget-bounded payload must be EXEMPT from that budget; truncation of atomic typed units must cut at unit boundaries, never mid-unit.** Two coupled sub-lessons from wiring the worldview receipt into the boot injection: **(1) BUDGET-EXEMPT CLOSURE FRAMING** — a ritual that closes or guards a payload (a boot-receipt request frame, a truncation marker) must be structurally exempt from the `--max-chars` budget that bounds the payload, else it gets truncated away exactly when the payload is largest (when closure matters most). Render the bounded body first; append the guard *after*. **(2) UNIT-SAFE TRUNCATION** — when the payload is composed of atomic typed units (badge-bearing pertinence rays: `⟨YOURS·act⟩…`), truncation must cut at unit boundaries, never mid-unit. A half-cut `⟨YOURS·act⟩` ray can read as a DIFFERENT, dangerous instruction. Truncate at the last complete line that fits, then append an explicit `⟨SEALED⟩` "body truncated; do not infer omitted rays" marker (itself budget-exempt per sub-lesson 1). **Byte-safe ≠ unit-safe.**

- **Refinement (tic 514 → /review 515) — the exemption set must include the load-bearing pertinence rays, not only the closure ritual; FIRST-IN-ORDER is not SURVIVAL.** In a budget-bounded render that truncates a prioritized list, an "invariant-first ORDERING" guarantee is silently defeated by render-order TRUNCATION: a must-survive unit (the boot-read invariant; the APOPHATIC `standing.boundary`) can be sealed away when head + reserve exhaust the budget BEFORE the first ray renders. The fix is not re-ordering but BUDGET-EXEMPTION of the load-bearing units (the same status closure/identity/ladder prose already enjoy): force the must-survive units in, bound only the remainder, keep the rest honestly RENDER-BOUND-marked (FIELD ≠ SEALED). Especially load-bearing when the sealed unit IS the gate that instructs the reader to expand the seal — at the 2200 citizen seam (tic 514) the boot-read invariant ("do not act from a clipped preview") was itself clipped: the gate against acting-on-a-clipped-preview, clipped. This extends sub-lesson (1) from "the closure ritual is exempt" to "every must-survive unit is exempt, regardless of render position."

<!-- refinement edge from cpr_budget_truncation_order_is_not_survival_must_survive_units_need_exemption_tic514 (tic 514 → /review 515, REFINE-into-budget-exempt, Architect-gated batch apply). Extends the exemption set from the closure ritual to all load-bearing pertinence rays; first-in-ORDER is not SURVIVAL. Proven LIVE: tic-514 citizen-boot GAP-1 (boot-read invariant clipped at the 2200 seam), fixed budget-exempt + regression-guarded. Derivable-from-parent (this entry); recorded as a refinement so it loads where budgeted typed-unit renders fire. Band: COGNITIVE. signer ent_homeskillet-c48. -->

<!-- promoted from cpr_budget_exempt_closure_framing_and_unit_safe_truncation_tic332 (tic 332→333, /review 333 unified docket). Source: tic-332 office-worldview.py receipt-frame + line-safe-truncation hardening (Architect flags); live-validated tic 333 — first-native-boot conformance-diff confirmed the frame appeared past the cap and truncation cut on a complete ray + SEALED marker. Band: COGNITIVE. -->

---

## Reason-Coded Genuine-vs-Known Verifier Split
<a id="reason-coded-genuine-vs-known-verifier-split"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=336 | first_appearance_tic=334 -->

A consistency verifier's boolean `consistent:false` is the wrong shape when N of its findings are pre-classifiable known false-positives. The shape doctrine, in three coupled parts:

**(1) Split genuine from known, and only `genuine` is a hazard.** The check must report `consistent:false(genuine=G, known=K)`; `K>0` alone is expected noise, only `G>0` is a real inconsistency. A boolean collapses the two and forces every cycle to re-triage the known set cold.

**(2) Each `known` finding carries a REASON code, because the known-set is multi-reason.** Empirically surfaced by landing the consumer-set fix at tic 335 (review-close-check went 10→4): the resolved 6 were the `dehydration_resolved` reason; the surviving 4 are a structurally distinct sibling sub-class whose `promoted_to` target is a source file (`.py`/`SKILL.md`), a domain-relative path, or a relocated-archive path — carrying NO text-matchable trace (no lesson, no provenance comment, `cpr_id` not a literal in the target). A content-matching verifier cannot verify those by ANY amount of surface-resolution; the inscription is a code BEHAVIOR or a moved file, not text. The reason codes: `dehydration_resolved | behavioral_text_unverifiable | stale_relocated_pointer`. Each cycle reads WHY a finding is known and which mechanism (if any) would close it.

**(3) One shared resolver closes exactly ONE reason — the rest need their own mechanisms.** `resolve_doctrine_surfaces` (the tic-335 consumer-set helper) closed only the `dehydration_resolved` reason. The behavioral/code targets need a provenance-trace axis; the relocated archives need a relocation-aware pointer correction. A single resolver is necessary but not sufficient; do not expect it to neutralize the residual.

**The named-is-not-landed driver.** A named-but-unlanded consumer blindspot re-emits identical false-positives every cycle, and a by-failure cadence re-waves them as "known blindspot" without confirming each is actually an instance — the silent-degrade cadence operating on the AGENT, not just the code. Live proof: finding #2 in the residual IS `cpr_review_close_check_verifier_blind_to_spec_surface_promotion_targets_tic301` itself — the verifier blindspot named twice in doctrine (`cgg-ledger#review-close-check-verifier-dehydration-blindspot` + the tic-301 CogPR, status promoted) yet whose runtime patch did not land for 34 tics, until landed at tic 335. Remedy: when a blindspot is named-but-not-landed, ENUMERATE + PRE-CLASSIFY the recurring false-positives in the remediation tranche so each cycle reads the classification instead of re-deriving it cold, and at session close classify-and-route every finding TOUCHED (genuine-repair vs known-FP, with evidence) rather than papering the set with a doctrine label.

Refines Named-Is-Not-Landed Gate. Composes Conductor-Score-Runtime-Parity (doctrine names the discipline; runtime did not enforce it) + the consumer-set obligation (federation KI `structural-transform-implies-closed-consumer-set-obligation`).

<!-- promoted from cpr_named_blindspot_unlanded_fix_reemits_preclassifiable_false_positives_tic334 (C1 parent) ⊕ cpr_known_false_positive_taxonomy_split_by_reason_not_just_dehydration_tic335 (enrichment, MERGED at /review 336). Source: tic-334 resolute review-close classification + tic-335 spec→impl gate for the consumer-set tranche (review-close-check 10→4 residual). Confidence_tier: reinforced (two sources, empirically validated by the 10→4 landing). Band: COGNITIVE. CGG-rung (review-close-check.py is CGG runtime). The genuine-vs-known verifier split is this entry's prescribed runtime follow-on. -->

---

## Review-Execute Atomic Writeback Completeness — Emit-Side of the Verifier Split
<a id="review-execute-atomic-writeback-completeness"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=341 | first_appearance_tic=337 -->

review-execute (the promotion applier) must complete TWO idempotent writeback halves on auto-memory / inline promotion targets, or it leaves recurring review-close-check false-positives that the next session re-derives cold. This is the EMIT-side complement to the READ-side genuine-vs-known verifier split (`reason-coded-genuine-vs-known-verifier-split`): close the false-positive at the source rather than only classifying it downstream.

**(1) STALE INLINE MARKER.** review-execute flips `queue.jsonl` terminal status and writes the ledger body, but must ALSO flip the inline `status: pending` marker in MEMORY.md / `session_lessons` topic files. At tic 337 EIGHT inline markers (tic-324/325/328 clusters) were still `status: pending` inline despite being `promoted` in queue.jsonl since /review 329/336 — the inline markers never flipped. (Composes "Inline-Tracked CogPR DEFER Keeps status:pending" + "MEMORY.md Inline Entry Location Lock": the lock was never UNLOCKED on promotion.)

**(2) MISSING PROVENANCE BREADCRUMB.** review-execute must stamp a `<!-- promoted from cpr_… -->` marker on auto-memory promotion targets. Only 2/61 feedback files carried one. Because the queue writeback row's `lesson` is often empty, review-close-check has no `cpr_id` literal AND no lesson-snippet to match → it reports `promoted_text_missing` for a doctrine that genuinely landed (the tic-336 resolute-close feedback file, freshly promoted /review 336, fired exactly this at tic 337 — repaired by hand-adding the marker).

**The framing: atomic-writeback-completeness — one root, two surface symptoms.** Both halves are idempotent; both belong to the writeback contract, not to a separate hygiene pass. The mechanizing tool is `review-promote-writeback.py` (review-execute invokes it like `atomic-append.sh`): inline `status: pending→terminal` flip + breadcrumb stamp scoped to auto-memory targets ONLY (ledger/compact-root provenance stays in the review-execute Step-2 body write; dehydration scopes the surface set). Detection of the gap firing: count inline `status:pending` markers in MEMORY.md whose `queue.jsonl` id is terminal — any >0 is the gap. Pairs emit-side with the read-side verifier split as the two faces of one parity discipline.

<!-- promoted from cpr_review_execute_auto_memory_inline_writeback_incomplete_emit_side_of_verifier_split_tic337 (tic 337→341, /review 341). Source: built live tic 337-338 alongside the read-side verifier split; review-promote-writeback.py LANDED tic 338 (CGG c5a29ae / Fed 326689c5), 183/183 byte parity, review_close_check genuine=0/known=4 HEALTHY. Emit-side complement to reason-coded-genuine-vs-known-verifier-split. n=9 same-tic (8 stale markers + 1 missing-provenance feedback file). Confidence_tier: reinforced. Band: COGNITIVE. CGG-rung (review-execute is CGG runtime). -->

---

## Machine-Emitter Emit/Resolve Symmetry + Chronological Status-Truth
<a id="machine-emitter-emit-resolve-symmetry-and-chronological-status-truth"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | promoted_tic=344 | first_appearance_tic=341 -->

A machine-emitter that writes a signal on condition-DETECTION must carry a paired resolve-on-HEAL path, or its signals accumulate as write-only TENSION debt; and signal status-truth must be read from the chronological event log, never from derived/secondary stores (manifest, archive). This is the **emit-side** lifecycle complement to *Authoritative-set readers must read the manifest, not aggregate raw emissions* — that invariant governs READ-side dedup; this governs the EMIT/RESOLVE lifecycle symmetry. It is **not** the manifest-reader invariant restated.

**(1) Emit/resolve asymmetry — a read-only check that PROVES parity IS resolving evidence.** Surfaced tic 341 tracking down 8 stale `detected_drift` "mad dots" (Architect-flagged on the statusline). All 8 were `runtime-sync.py` drift detections on CGG surfaces edited during the tic 332-340 governance work; every surface had since re-synced (183/183 parity) but no signal ever closed. Root cause: `cmd_check` and `cmd_sync` EMIT `detected_drift` on detection, but only `cmd_auto_sync` (post-commit-sync, gated on a commit touching `cgg-runtime/`) RESOLVED, and only for surfaces synced in that one invocation. check-mode — which runs constantly (SessionStart, cgg-doctor, /siren) — was write-only-on-drift: it minted TENSION but never closed it. A read-only check that proves parity is itself the resolving evidence. **Fix: `cmd_check` now resolves-on-parity.**

**(2) Status-truth from derived stores.** The resolve fn read today's daily file + the active-manifest; the manifest entry carries status but NOT `payload.surfaces` and (read last, sorting after dated files) shadowed the surface-bearing daily entry, so the subset-match had nothing to match. It also never read older daily files (cross-day surfaces) and let an old archive-resolved entry shadow a newer dated active emission for a deterministic recurring-ID signal. **Fix: read the full DATED daily history only (chronological by name), keep the richest payload per id; manifest/archive are derived (manifest-prune reconciles).**

**Proof.** A plain check then closed 13 stale drift signals (the 8 + 5 March orphans stuck ~150 tics), evidence = 183/183 parity. Commits CGG `fe3a39d` + `fba816d`.

**Generalization.** The emit/resolve symmetry + chronological-event-log-is-status-truth generalize beyond `runtime-sync` to any auto-emitter (sentinel heartbeats, cadence drift, economy fetch). Composes *State agreement is not truth unless lifecycle-reachable*, *Authoritative-set readers must read the manifest*, and *Disagreement-as-evidence* (all READ-side); this entry is their EMIT-side lifecycle counterpart.

<!-- promoted from cpr_machine_emitter_emit_resolve_symmetry_and_chronological_status_truth_tic341 (tic 341→344, /review 344). Source: tic 341 Architect "track em down" on the 8 detected_drift mad dots; /siren + runtime-sync investigation; lopsided-sync diagnosis Architect-intuited. Confidence_tier: reinforced (empirically proven — 13 signals closed, 183/183 byte parity, CGG fe3a39d + fba816d). Band: COGNITIVE. CGG-rung (runtime-sync.py is CGG runtime). Emit-side complement to the manifest-reader READ-side invariant; non-derivable from it. -->

---

## Self-Conditioning Discipline — Thin Terminal Residue Prevents Regression
<a id="self-conditioning-discipline-needs-thin-terminal-residue"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | promoted_tic=377 | first_appearance_tic=377 -->

A self-conditioning DECLARATION discipline (one whose power is in the act of declaring, not in a stored value) cannot be truly stateless without regressing into a rebuilt mutable state-store within a few tics. The minimum that prevents regression WITHOUT becoming the over-built state-store it warns against: a thin APPEND-ONLY TERMINAL receipt on an EXISTING audit surface at the gate points only. The residue/state-store boundary has three structural discriminators: append-only vs mutable; terminal vs polled; existing-surface vs new-surface (+ consumer-having vs consumer-less per ungoverned-field-schema-reject). Composes terminal-state-valve + state-agreement-not-truth-unless-lifecycle-reachable + ungoverned-field-schema-reject.

(Validated: tic 377 frame-protocol arena, T2 rebuttal — "regression-needs-state" tension tested and refined: the thesis that declaration-only regresses is correct, but the remedy is two thin append-only terminal receipts on EXISTING surfaces, not a mutable polled new-surface store. Pattern Curator + Mogul + Ladder Auditor independently arrived at this boundary from their stewardship lenses.)

<!-- promoted from cpr_self_conditioning_discipline_needs_thin_terminal_residue_tic377 (tic 377→377, /review 377 PROMOTE). Source: tic-377 frame-protocol arena, T2 rebuttal (regression-needs-state). Placement: composes three existing federation KIs (Terminal-State-Valve + State-Agreement-Lifecycle-Reachable + Ungoverned-Field-Schema-Reject) — derivable composition, NOT promoted to federation compact root as standalone KI. Placed in Signal/Queue section (residue-vs-state-store is a queue-manifold discipline). Confidence_tier: convergent (T2). Band: COGNITIVE. -->

---

## Shared-Telos Arena: Stress Method-Optimization, Not Intent Divergence
<a id="shared-telos-arena-stress-method-not-intent"></a>
<!-- ledger-tags: authority_class=arena_and_reasoning_geometry | rung=domain | domain=context-grapple-gun | promoted_tic=377 | first_appearance_tic=377 -->

In an office arena where the offices share the federation Telos, convergence-on-INTENT (the what) is EXPECTED and low-information — the offices share values. The adversarial yield comes from each office advocating the METHOD-of-execution that optimizes ITS OWN stewardship lens toward the shared intent. Stressing the stewarding-optimization lens on METHOD (not assigning positions, not asking for intent-divergence) means offices do NOT manufacture disagreement for its own sake (the compliance-theater anti-pattern) but diverge genuinely for the betterment of their steward-identity office — the sub-scope that collides with the global SOMETIMES, not always.

Retroactively explains the tic-377 arena: blind 0a/0b = shared-Telos intent-agreement (expected); the rebuttal on METHOD (canary mechanism, residue boundary, gate locus) = where they genuinely diverged and produced every refinement. The convergent intent-agreement was NOT low-quality — it confirmed independence (all 5 offices BLIND reached the same KIND-distinction). The divergence on METHOD under rebuttal was where the informative signal lived.

Refines /stage "role/office-driven not position-assigned" + Recursive-Meta-Enforcement (no manufactured dissent) + Arena-Velocity-Guard (shared-Telos convergence-on-intent is not velocity-excess; method-divergence-in-rebuttal is the real test) + Same-Model-Convergence-Discount (shared values + shared retrieval lens: intent-convergence is not contamination; method-divergence despite shared lens is the weight-bearing signal). (tic 377.)

<!-- promoted from cpr_shared_telos_arena_stress_method_not_intent_tic377 (tic 377→377, /review 377 PROMOTE). Source: tic-377 Architect design dialogue (post-arena); OA-VPL-T geometry refinement. Placement: CGG cgg-ledger Arena And Reasoning Geometry (OA-VPL-T refinement). Confidence_tier: convergent (Architect-surfaced + retroactively explains this arena's structure). Band: COGNITIVE. -->

---

## Arsenal Instructions Carry Only the Up-Lane Ratchet — the Living-Corpus Down-Lane Is Un-Instructed
<a id="arsenal-instructions-carry-only-the-up-lane-ratchet"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=379 | first_appearance_tic=378 -->

The CGG arsenal was scaffolded as a living doctrine-lifecycle engine (ARCHITECTURE "How the ladder actually moves", cgg-ledger, the tic-363 fusion thesis, 40 lived supersessions), but EVERY operational INSTRUCTION surface encodes only the up-lane: capture → enrich → /review → promote. This is a Conductor-Score-Runtime parity violation located in the instructions, not the engine: the doctrine (score) names a bidirectional living corpus; the runtime instructions (parts) play only the ascending half. The diagnostic discriminator matters — **the under-leverage lives in the INSTRUCTIONS, not the engine.** CGG is not conceptually a one-way ratchet; the remedy is to re-contextualize the operational instructions toward the down-lane + lifecycle (additive, current-vs-target honest), NOT to rebuild the engine. Discipline for the remedy: additive `lifecycle_state` metadata, never status-enum expansion (the queue status enum has 10+ readers); doctrine-LAW still routes through /review; read-only-first (build the down-lane's seeing before its moving).

Composes Conductor-Score-Runtime Parity (CGG Application) (the parity-gap class) + Governance-is-instrumental-not-terminal (the down-lane exists to metabolize doctrine health, not to produce demotion-activity volume). Sibling-but-distinct from the down-lane WIRING candidate (`cpr_ladder_down_lane_audit_into_active_rungs_tic377`): this entry is the DIAGNOSIS (instructions under-instruct), that is the FIX (wire the operational down-audit) — the fix remains DEFER, gated on a first real `damaging` down-audit finding.

(Validated: tic 378 Living-Corpus HIDALGO trancheset — 4-lane RTCH audit of skills/agents/boot/kernel. Hard proof of the gap: `demote` appears 2× in the entire ledger and has never fired; no staleness/prune/demote runtime exists; the last real operational down-audit was tic 35. Mogul mandate cycles are all up-lane; the homeskillet [LADDER] boot injection was compression/centroid/lineage-only until TR3 made it bidirectional this same tic; cpr-stepper's state machine terminates at promoted/absorbed; /review's verdict set had no DEMOTE/LOCALIZE/HOLD. Convergence corroboration: the council-perimeter HOLDS facet (swarm mechanics) and C9's hold_in_dissonance (doctrine-lifecycle) are the same centroid at two rungs — the living-corpus framing reinforces across rungs.)

<!-- promoted from cpr_arsenal_uplane_under_instructs_living_corpus_tic378 (tic 378→379, /review 379 PROMOTE). Source: tic-378 Living-Corpus HIDALGO trancheset 4-lane RTCH audit + Architect doctrine-lifecycle document. Placement: CGG-rung review-and-promotion discipline — a refinement-INSTANCE of the federation Conductor-Score-Runtime Parity KI (derivable instance → ledger, not compact root) per Constitutional-Law non-derivability. Model home: autonomous_kernel/doctrine-lifecycle-spec.md. Confidence_tier: reinforced. Band: COGNITIVE. -->

---

## Fix-Then-Present — a Self-Presentation Doc Describing an Unwired Mechanic As Real IS the Misrepresentation (every doctrine rung)
<a id="fix-then-present-self-presentation-honesty"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=379 | first_appearance_tic=377 -->

When asked to make a system "present itself in its docs," writing the presentation BEFORE fixing what is broken or misrepresenting produces a doc that lies — it describes an aspirational/unwired mechanic as if real. The misrepresentation IS the presentation doc, not a separate artifact (Architect, tic 377: "you can't do a doc without fixing what's broken or misrepresenting"). The discipline: **(1) AUDIT** the implementation against the stated model first (sweep the repo; drift surfaces in classes); **(2) DECIDE write-topology held-vs-changed BEFORE editing** — verify who-writes-what; prefer ADDITIVE fixes (new metadata field) over enum/schema changes when N readers consume the surface; **(3) FIX at source + SYNC installed + VERIFY parity** (the fix is not landed until installed byte-parity); **(4) mark current-vs-target honestly** — a forward/aspirational mechanic is marked FORWARD, never described as wired.

Composes with the federation KI *Artifact language must not exceed its declared confidence classification* — current-vs-target honesty is the TEMPORAL form of that confidence-class discipline (a doc must not claim runtime-present what is only target-state). The remediate-before-present ORDERING is the genuinely procedural net-content.

(Validated at TWO doctrine rungs — convergent. **CGG-arsenal rung, tic 377:** the self-presentation pass that triggered the Architect ruling. **Kernel rung, tic 378 [confirming instance, merged from cpr_kernel_demotion_rollback_overclaim_tic378]:** `autonomous_kernel/CLAUDE.md:16` and `kernel_spec.md:11` declared the kernel "arbitrates graduation, methylation, rollback, AND demotion across the autonomy matrix" — but only graduation/promotion is wired (promotion_arbiter + promotion_policy.yaml + citizen_registry). Demotion and rollback are aspirational at the kernel exactly as they are at CGG: the kernel was writing a check the runtime cannot cash. Fix landed tic 378 as the TK1 kernel binder-addendum, marking demotion/rollback FORWARD. The kernel carried a SECOND, orthogonal defect — collapsing two graduation DOMAINS under one sentence: (a) doctrine/citizen-lifecycle climbing the rung ladder by evidence vs (b) capability admission (compute backends/vendors entering by envelope + semantic-identity gate; a compute backend never climbs the ladder — it is admitted once and SUSPENDS, not demotes, on health failure). That disambiguation also landed as the TK1 addendum [forward].)

<!-- promoted from cpr_fix_then_present_self_presentation_honesty_tic377 (tic 377→379, /review 379 PROMOTE), with cpr_kernel_demotion_rollback_overclaim_tic378 MERGED in as the kernel-rung confirming instance (two-graduation-domains disambiguation noted; addressed by the tic-378 TK1 kernel addendum). Confidence_tier upgraded tentative/reinforced → convergent (two doctrine rungs: CGG arsenal + autonomous_kernel). Band: COGNITIVE. -->

---

## Blocker-Type Taxonomy — Classify the Blocker (Gate vs Capability vs Build) Before Reporting; Never Fake a Live Receipt Against a Fake Transport
<a id="blocker-type-classification-gate-vs-capability-vs-build"></a>

When a live action cannot execute, classify the BLOCKER'S TYPE before reporting — each type has a different resolution path and a different owner: (1) **GOVERNANCE GATE** — a /review-adjudicable boundary (GATE-F7 was this until the Architect ratified it) → resolution: *adjudicate*; (2) **CAPABILITY gap** — a credential / wire / server the env lacks (W1's Cloudflare transport; the MLX leg) → resolution: *provision*; (3) **BUILD gate** — an artifact that must be wired first (W2b's egress enforcement) → resolution: *build*. The load-bearing honesty discipline: a live receipt must reflect a LIVE run — emitting a "live" receipt against the injectable FAKE transport (which the test suite already exercises) would be the exact dishonesty Fix-Then-Present forbids: a self-presentation artifact claiming an unwired / unexecuted thing is real. At tic 381 R-B GREEN the WINCH was AUTHORIZED but initially could not fire (no live transport); the honest move was to classify the blocker (capability, not gate), hold, and fire for real only when the Architect supplied creds — then the receipt was honest. Refines Fix-Then-Present with the three-way blocker-type taxonomy at the moment a live action is blocked; composes Presence/Observation-Fallacy-Guard (presence/authorization ≠ execution). (Validated: tic 381 WINCH n=1 — recon-RB-readback named R-B GREEN but live wire absent [capability, not gate]; W1 fired only on supplied creds; W2b held as build-gate; the no-fake-receipt line held throughout.)

<!-- promoted from cpr_blocker_type_classification_gate_vs_capability_vs_build_tic381 (session_lessons_tic_381.md, inline; /review 382 PROMOTE-as-refinement, Architect-ratified — recommended batch). Refines `fix-then-present-self-presentation-honesty` with the gate|capability|build blocker-type taxonomy + per-type routing (adjudicate|provision|build). Composes Presence/Observation-Fallacy-Guard. Tier: reinforced; meta lesson type. Band: COGNITIVE. -->

**Refinement — verify the runtime READ-PATH before classifying a board-population blocker as "vendored / Architect-gated L4" (tic 519 born → /review 520 PROMOTE-as-refinement, Architect-gated).** Adding a new strike cell to the engine-read covenant board (board-state.json / the harpoon-sequencer §1 table) is a CANONICAL-SIDE landing, NOT a vendored-Rust L4 change — ONCE the engine reads the board live. At tic 519, slotting A5 first read as "L4-gated vendored Rust" from a dated board-md note ("engine-reads-board root fix stays Architect-gated L4 [vendored != versioned]", tic 488) and a stale sequencer comment ("mirrors stomp_tranchestomp.rs lines 82-86"). BOTH were superseded by the tic-502 wiring that made the Rust engine READ `board-state.json` `waves` live — so the only thing the no_autoprioritization pre-fire gate needed was the canonical-side `engine_expected` regression snapshot updated deliberately to the new known-good waves (an independent frozen assertion that catches UNINTENDED drift; updating it for a reviewed/approved change is guard maintenance, not a tautology). This is the blocker-type taxonomy applied to a board-population blocker — composed with `#harness-agnostic-is-verified-against-runtime-ground-truth-not-lagging-published-schema` (the dated doctrine note is the lagging schema; the engine's actual read-path is the ground truth) and the Presence/Observation `doctrine-mention-does-not-prove-runtime-wiring` guard (a dated "gated/vendored" note can be superseded by a later wiring commit and go stale). The discipline: before classifying a blocker "vendored / L4", VERIFY THE ACTUAL READ-PATH (does the engine still hardcode, or does it read the artifact?); preserve the dated note as a historical snapshot (binder-addendum), do not retcon it. Derivable-from-parent (NOT net-new). (Validated tic 519→520: A5 landed canonical-side GREEN, 6/6 pre-fire [center-exclusion held], the physics fix shipped tic 520 CGG 18b595d.) SKIP ≠ DISCARD honored.

<!-- refinement edge from cpr_board_strike_cell_addition_is_canonical_side_when_engine_reads_board_live_tic519 (tic 519 → /review 520, REFINE-into-blocker-type-taxonomy, Architect-gated batch [AskUserQuestion approval]). Source: audit-logs/governance/borns-tic519-board-strike-cell-is-canonical-side-when-engine-reads-board.md. A board-population blocker classifies as canonical-side (not L4-vendored) once the engine reads the board live (tic-502 wiring); verify the read-path before assuming a vendored gate. Composes #harness-agnostic-is-verified-against-runtime-ground-truth + Presence/Observation doctrine-mention-≠-runtime-wiring + binder-addendum (preserve the dated note). Derivable-from-parent (NOT net-new). Band: COGNITIVE. signer ent_homeskillet-c48. -->

**Refinement — a capability / absence verdict has a SHELF-LIFE; re-probe by EXECUTION before it parks work (tic 535 born → /review 537 PROMOTE-as-refinement, Architect-gated).** The three-way taxonomy above classifies a blocker's TYPE; this adds the TEMPORAL axis for the CAPABILITY type specifically: a capability-NO (`NOT_REACHABLE`, `tool absent`, `won't fit in RAM`, `dep not importable`) is a snapshot of ONE probe at ONE tic, not a standing law — and it DECAYS. Inheriting a stale capability-NO from a prior assessment (or from a `ToolSearch` no-match) without RE-TESTING BY EXECUTION silently parks downstream work. Two net-new rays beyond the parent: the DISCHARGE is a live re-run (not a staleness-TTL alone), and the OWNER of a capability-NO is whoever can run the probe, not whoever last wrote the assessment — so a capability verdict must carry its probe-basis + a tic-stamp and be re-probed before it is allowed to block. Discriminator vs the parent's capability→*provision* routing: the verdict must first be *re-confirmed live*, because "provision" may already be satisfied. Composes the *Volatility Handling Law* (a capability probe is an L4-class snapshot — but freshness discharges by live re-run, not a timestamp) + Presence/Observation *observed-absence-does-not-prove-breakage*. (Validated: tic 527 ruled the SP5 live-leg `NOT_REACHABLE` on an fp16 assumption + un-probed local stack; tic 535 execution overturned every prong — mlx-lm present, a 4-bit 14B is ~9GB not ~28GB, epoch16 LIVE-SERVED on the M2 Metal GPU — the stale NO had parked the hoist ~8 tics at *capability* when the only live gate was *policy*; recurrence n≥8 across tics 475–535 as the Agent-tool false-negative, with a live second instance THIS pass — a stale half-read of the covenant surface mis-framed an already-landed admission.) Derivable-from-parents PARTIAL (execution-discharge + owner=probe-runner are net-new). SKIP≠DISCARD honored.

<!-- promoted from cpr_capability_verdict_has_a_shelf_life_retest_dont_inherit_tic535 (audit-logs/cprs/queue.jsonl, extracted->promoted; /review 537 PROMOTE-as-refinement, Architect-gated [AskUserQuestion approval]). Temporal complement to Blocker-Type Taxonomy: the parent classifies blocker TYPE, this names that a CAPABILITY-type verdict DECAYS and must be re-probed by execution (discharge=execution, owner=whoever-can-run-the-probe). Composes Volatility-Handling-Law + Presence/Observation observed-absence-does-not-prove-breakage. Source: audit-logs/governance/borns-tic536-capability-verdict-shelf-life-and-agentic-winch.md. Band: COGNITIVE. Confidence_tier: reinforced (n>=8 recurrence of the false-negative class; tic-535 execution overturn + live second-instance same pass). signer ent_homeskillet-c48 (claude-opus-4-8). -->

---

## Emission Granularity Is the Leak — Aggregate to a Per-Owner Rollup Ray, Not Item-Keyed Flood
<a id="emission-granularity-is-the-leak-not-the-obligation"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | promoted_tic=405 | first_appearance_tic=403 -->

When a watcher correctly re-surfaces a standing condition (anti-silencing — a stale WAIT must not go silent) but emits ONE ray PER underlying item, it floods the shared perception surface (the signal manifold) with N rays for a single backlog — and the instinct to "clear the leak" by terminalizing those rays is the silencing anti-pattern (it would silence real debt AND not even hold, because a cross-day re-emit re-fires it). The correct fix is to change emission GRANULARITY, not to silence: emit ONE per-owner AGGREGATE rollup ray (condition-stable id keyed on the OWNER/entity, not the item) carrying the full item list in its payload, with volume scaled to debt magnitude (capped). The debt stays fully visible and auditable (payload.item_ids) and re-surfaces daily until cleared by DECISION — but as one ray per owner, not N.

**Verified tic 403:** the inbox-attention-debt watcher (inbox-envelope.py emit_attention_debt_signals) emitted `sig_inbox_<entity>_<msg>_<state>` per stale WAIT message → 159 active manifold rays for one mailbox backlog (75 in ent_breyden alone); rewritten to emit `sig_inbox_attention_debt_<entity>` per entity → 159 rays collapsed to 19 (raw-daily active 192→52), the 159 granular rays superseded (Option-B, superseded_by the aggregate, debt preserved in payload.message_ids — NOT silenced).

**The distinguishing test of this rule vs the parent:** the parent ("bound the obligation lifecycle at both ends") governs WHETHER an obligation may fall silent; THIS governs the EMISSION CARDINALITY of an obligation that correctly stays loud — a re-surfacing condition over N items is ONE condition-per-owner, not N conditions, and Signal-ID-Determinism ("id derives from the condition") already implies the owner-keyed aggregate id.

**Composes:** anti-silencing (ledger#obligation-lifecycle-must-be-bounded-at-both-ends) + Signal ID Determinism (cgg-ledger) + Authoritative-Set-Readers-Must-Read-the-Manifest (the manifold is a shared perception surface that granular emission pollutes). Net-new candidate: the OWNER-keyed-aggregate-not-item-keyed-flood emission rule. source: deep-investigation-tic403-inbox-aggregate

<!-- promoted from cpr_emission_granularity_is_the_leak_not_the_obligation_tic403 (tic 403→405, /review 405). Source: audit-logs/governance/borns-tic403-emission-granularity.md. Born while finishing v2 signal migration + closing inbox-attention-debt; distinct from obligation-lifecycle-bounded-at-both-ends (cardinality axis, not whether-silent). Band: STRUCTURAL. Confidence_tier: reinforced (empirically proven — 159→19 rays, tic 403). -->

---

## Apophatic-Aperture Disclosure — Prove Coverage, Name the Negative Space
<a id="apophatic-aperture-disclosure-prove-coverage-name-negative-space"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=421 | first_appearance_tic=420 -->

A bounded read/render receipt proves SUFFICIENCY by (a) declaring the read APERTURE (read_ranges), (b) NAMING the excluded negative space as REAL and POTENTIALLY LOAD-BEARING (apophatic_range_bounds: preceding/following + considered_as_real + reason_not_required), and (c) justifying why the aperture satisfies the current pertinence (pertinence_rationale). The gate blocks ONLY on required_unread_ranges (unread material INSIDE the required surface) — NEVER on the existence of declared negative-space bounds. The excluded-row fields are a DUE-DILIGENCE FORCING FUNCTION, not observability: to invent line bounds + excluded ranges + a checkable sufficiency rationale, a convincing lie must do nearly the SAME minimal work as doing it right — the cheapest path aligns with due diligence. SELF-CORRECTION (tic 421): the original "prove coverage, never confess omission" OVER-CORRECTED — it erased the forcing-function by mistaking the apophatic accounting field for a moral failure field; the error was letting boot-receipt.py's implementation failure-semantics (pass requires omitted_ranges==[]) define the design's apophatic semantics. FIX: rename the blocking field required_unread_ranges; keep apophatic_range_bounds non-blocking but REQUIRED for ranged reads; require pertinence_rationale for any partial read; block a ranged read that omits either. Lock: "Negative-space disclosure is not failure — it is how a bounded aperture is made auditable. Only required unread is gate debt." Composes budget-exempt-closure-framing; refines the boot-read invariant. Evidence: live tic-420 gate trip + the tic-421 argument that reversed the over-correction (the corrector measuring its own correction). Full body: boot-cadence-desired-state-tic420.md PART C + tic-421 apophatic thread.

<!-- promoted from cpr_prove_coverage_not_confess_omission_tic420 (tic 420→421, /review 421). Source: audit-logs/governance/borns-tic420-boot-cadence-shadow.md. Born tic 420 from live gate trip + tic-421 apophatic-aperture reversal. Composes budget-exempt-closure-framing; refines boot-read invariant. Band: COGNITIVE. Confidence_tier: reinforced (live gate + tic-421 self-correction validates the corrector-inherits-obligation ray). -->

---

## Full-Read Is Surface-Typed — Terminal-Valve Coverage Is Required Coverage
<a id="full-read-is-surface-typed-terminal-valve-coverage-is-required-coverage"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=421 | first_appearance_tic=420 -->

"Full read" is SURFACE-TYPED — and always was, by necessity (you cannot read a JSONL registry the way you read prose; record stores are USED as append-only history / latest-entry-per-id / terminal-valve / current-manifest, so "full" cannot mean "physically read every historical row"). PROSE / Markdown / code / specs / handoffs: sequential, gapless, whole required body before governed mutation. JSON / JSONL / registries / queues / ledgers / record-stores: complete REQUIRED-RECORD coverage under the declared discipline + apophatic disclosure of excluded rows (born #1's aperture). The boot-read invariant's uniform "gapless" was PROSE-document language wrongly projected onto record stores — which made the JSONL case look like a loophole when it is actually WHY the apophatic fields exist; historical head under terminal-valve discipline is NOT gate debt, it is disclosed negative space. UNLESS VALIDLY SEALED: a producer-sealed surface's omission is declared negative space, not debt — BUT the seal marker alone does NOT prove non-pertinence. Receiver rule: "If the current action could depend on sealed material, expand the named follow-surface (by its declared discipline) before acting; if you do NOT expand, do not infer the sealed contents." Concrete: "read active.jsonl in full" means by latest-entry-per-id/terminal-valve + apophatic aperture, NOT prose-gapless. Composes constitution-ledger Queue/State + cgg-ledger Terminal-State-Valve-Pattern + Authoritative-set-readers. Evidence: tic-420 (rationalized "gapless" onto active.jsonl) + tic-421 surface-typing + seal-pertinence threads. Full body: PART A.A1 + PART C + tic-421 thread.

<!-- promoted from cpr_terminal_valve_coverage_is_required_coverage_tic420 (tic 420→421, /review 421). Source: audit-logs/governance/borns-tic420-boot-cadence-shadow.md. Born tic 420 from gapless-onto-JSONL rationalization. Composes Terminal-State-Valve-Pattern + Authoritative-set-readers + Queue/State. Band: COGNITIVE. Confidence_tier: reinforced (two tics of surface-typing evidence). -->

---

## Producer Seal Is a Typed Field Aperture — Sealed_IDs Not Count
<a id="producer-seal-is-a-typed-field-aperture-sealed-ids-not-count"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=421 | first_appearance_tic=421 -->

A producer-side SEAL (worldview / boot-injection budget truncation) must meet the SAME standard as the consumer-side apophatic aperture (born #1): NAME and TYPE its negative space, not just COUNT it. The current seal emits a count + a follow-pointer ("N lower-priority pointer(s) sealed; read active.jsonl in full") with NO manifest of WHAT was sealed — so a model cannot judge pertinence from the marker alone; it must expand the source or re-render. The marker is a valid LOSS DECLARATION but an insufficient PERTINENCE INDEX (a broken apophatic aperture — marker-form without substance). FIX (write the manifest INTO the seal; do NOT stuff contents into the hot lane, do NOT make it heavy): sealed_count + sealed_ids (semantic slugs — the PERTINENCE handle: top-N + "+k more") + underlying_class/lane if known + follow_surface + read_discipline. EXPLICIT pushback on the counsel: do NOT put priority_range in the manifest — that re-imports the rank axis into a pertinence mechanism (RANK ≠ PERTINENCE; what lets a consumer judge expand-or-not is WHAT was sealed, the semantic id, not how the producer ranked it). FIELD ≠ SEALED — they are SIBLING pertinence classes (office-worldview.py:103-114: authority-identical, differ on expand-intent/receipt/weight), do NOT collapse them: a budget seal can HIDE FIELD/COUNTER/OFFICE/YOURS/PEER material but does NOT reclassify it — budget-omitted content keeps its OWN class (mostly FIELD = open terrain, EXPANDABLE-if-pertinent). The truncation marker borrowing SEALED's deliberate-foreclosure semantics ("do not infer omitted rays") for budget-omitted FIELD is a CATEGORY ERROR. SEALED is reserved for CHOSEN, reasoned foreclosure of a specific thing. Locks: "A seal proves declared negative space; it does NOT prove the sealed material is non-pertinent." / "SEALED is the RENDER boundary (budget truncation), NOT the underlying item's pertinence class — budget-sealed content RETAINS its underlying class (FIELD/COUNTER/OFFICE/YOURS/PEER…); the marker only declares bounded omission, it does not reclassify." Receipt corollary (impl, gated): producer_bounded · producer_bound_kind · producer_follow_surface · sealed_ids_observed. Composes/refines born #1 + the pertinence-class system + presence-observation-fallacy-guard. Evidence: tic-421 Architect critique ("how would you know what was omitted except by looking?"; "are you both dropping FIELD for SEALED?") + 2 counsels concur (priority_range catch is the divergence) + boot-injection.py:147-164 + office-worldview.py:647-664.

<!-- promoted from cpr_producer_seal_is_a_typed_field_aperture_tic421 (tic 421→421, /review 421). Source: audit-logs/cprs/queue.jsonl (extracted tic 421). Born tic 421 from Architect critique of worldview seal marker + counsel convergence. Composes apophatic-aperture-disclosure (born #1) + pertinence-class system + presence-observation-fallacy-guard. Band: COGNITIVE. Confidence_tier: reinforced (Architect-stated + 2 counsels). -->

---

## Priority Is Calibrated at Cadence, Not Boot
<a id="priority-is-calibrated-at-cadence-not-boot"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | promoted_tic=421 | first_appearance_tic=421 -->

A relative priority score is meaningful ONLY if authored relative to the active terminal set; otherwise it is accidental placement around a default attractor. Diagnosis: "priority is relative IN USE but not proven relative AT WRITE." boot-injection.py is RENDER-time discipline (sorts by (priority, inject_from_tic), seals lowest-priority first) — it CONSUMES whatever score the record carries; missing priority defaults to 50. Verified NOT-currently-broken: 8 active records, explicit spread 10/20/20/25/40/60/60/70, zero unset — it works because records were CONSCIOUSLY distributed (a single tic-413 calibration pass), NOT because the mechanism forces it; default-50 is the silent drift attractor the moment a writer adds 50 (or guesses) without comparing (spec-runtime-alignment-by-accident). WHO calibrates (Architect tic-421): NOT cold boot (no session context, no forward direction — it can only render), and NOT a per-write lint on every ad-hoc writer (that CAGES a being-authored judgment → compliance-artifacts; constrain-vs-cultivate / born #3). The relational WRITER with fullest context + forward direction is the CADENCE LANE — it sees the whole session and writes the handoff/projection, so calibrating which standing-pointers survive the next boot's budget is the SAME future-self-rehydration stewardship as the handoff itself (sibling of born #5). FIX LOCUS: cadence SKILL.md gains a light "calibrate standing-pointer priorities against the active set, record priority_basis" step at the epoch boundary (gated build). Renderer (boot) sorts; cadence justifies+calibrates. Missing priority = neutral fallback until next cadence calibration; a repeatedly-sealed record is flagged for the NEXT cadence pass, not auto-promoted. Lock: "Priority is relative only if written relationally. The renderer sorts; the writer with fullest context — cadence — justifies placement." Composes/refines born #2b (rank is not the manifest) + born #5 (handoff rehydration) + engine-content-separation (render engine vs write/calibrate content) + constrain-vs-cultivate. Evidence: tic-421 priority probe (8-record spread) + Architect cadence-calibration insight + boot-injection.py:100-164.

<!-- promoted from cpr_priority_is_calibrated_at_cadence_not_boot_tic421 (tic 421→421, /review 421). Source: audit-logs/cprs/queue.jsonl (extracted tic 421). Born tic 421 from Architect cadence-calibration insight + boot-injection priority probe. Composes engine-content-separation + spec-runtime-alignment-by-accident + constrain-vs-cultivate. Band: COGNITIVE. Confidence_tier: reinforced (Architect-stated; empirically probed 8-record spread). -->

---

## Shadow/Apprentice Requires Full Input Parity and Co-Mutation
<a id="shadow-apprentice-requires-full-input-parity-and-co-mutation"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | promoted_tic=421 | first_appearance_tic=420 -->

A shadow/apprentice model of a process must be enabled with the SAME full input fidelity AND output capacity as the process it shadows — otherwise the measured dissonance reflects the shadow's HARNESS LIMITS (truncated input, clipped output budget), not the apprentice's real capability, and the training signal is corrupted. Corollary (co-mutation): mutating the shadowed process OBLIGATES a paired mutation of its shadow (syllabus / template / output budget / scoring rubric) — else the shadow trains against a stale target and silently drifts from what it shadows. This is the consumer-set-obligation KI specialized to shadow/training lanes: the shadow is a CONSUMER of the shadowed process's contract; a structural transform on the process is a closed obligation on its shadow. RECEIPT OBLIGATION (open design Q for /review): a paired process+shadow mutation should emit a paired receipt proving both moved together; candidate sink = audit-logs/governance/receipts/ (NOT substrate-provenance, which is vendored-corpus/FIELD-scoped; NOT REGISTRY-CENSUS, which registers registries rather than holding receipts) — if co-mutation becomes a recurring KIND, stand up a dedicated co-mutation ledger and register IT in REGISTRY-CENSUS. Evidence: tic-420 shadow-cadence audit — HANDOFF_TEMPLATE teaches the 18-section form but not the handoff purpose (form-filler distillation); max_tokens=16000 vs ~6K-token real handoff (adequate but reasoning-overhead unverified); scoring model still unbuilt. Architect-coined tic 420. Full body: boot-cadence-desired-state-tic420.md PART E.

NOTE: receipt-sink mechanism DEFERRED (open design Q).

<!-- promoted from cpr_shadow_requires_parity_and_co_mutation_tic420 (tic 420→421, /review 421). Source: audit-logs/governance/borns-tic420-boot-cadence-shadow.md. Born tic 420 from shadow-cadence audit + Architect co-mutation insight. Consumer-set-obligation KI specialized to shadow/training lanes. Receipt-sink mechanism DEFERRED (open design Q). Band: COGNITIVE. Confidence_tier: tentative (n=1 tic-420 shadow audit; recurring kind not yet confirmed). -->

---

## The Corrector Inherits the Verification Obligation
<a id="the-corrector-inherits-the-verification-obligation"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=421 | first_appearance_tic=413 | landing_kind=resubmit_higher | resubmit_note=principle is general (composes bounded-delegation + dont-trust-sync + coherence-is-not-admission); lived instances all one-rung CGG-runtime — promoted at cgg-ledger, abstracts to federation on cross-domain recurrence -->

When a workflow/subagent returns a PATCH bundled with PREDICTED METRICS, three distinct verification failures can each occur and each needs MEASURING against the real artifact, not the prediction: (a) the predicted metric is wrong — the C1 subagent predicted +74 io-map edges, the actual rebuild added +7; trust the rebuilt artifact's delta, never the proposal's claimed numbers. (b) the patch introduces NEW noise the prediction never mentioned — the same patch silently turned 8 multi-line message/doc/markdown templates into "path" keys (string-building `+` mistaken for path-building); a count check would have missed it, only INSPECTING the actual new keys caught it. (c) THE NOVEL RAY — your own CORRECTION can over-reach, and the corrector is NOT exempt from the same measurement. The first guard I wrote to clean the garbage (`set(p) <= {*,$,/,.}` in _norm) was correct in isolation but collapsed the map 16643->87 edges by rejecting the load-bearing `*` wildcard hub; this was caught ONLY by re-measuring the corrected state, exactly as the original proposal had to be measured. DISCRIMINATOR: a fix applied to a load-bearing artifact is itself a new proposal — re-run the same measurement (delta + inspect-the-actual-output + blast on downstream consumers) on the corrected state before accepting. The verification obligation is recursive: it does not stop at the delegated patch, it follows every edit including your own. NON-DERIVABILITY: composes bounded-delegation-masks-bugs (the subagent half), don't-trust-the-sync-verify-bytes (measure the artifact not the count), and coherence-is-not-admission (a coherent proposal is still an object) — but adds a ray none of them carry: the CORRECTOR inherits the verification obligation; the fix is the next object to measure, not a terminal state. Likely a refinement composing those three, NOT a new parent. source: handoff

<!-- promoted from cpr_measure_the_correction_too_tic413 (tic 413→421, /review 421). Source: audit-logs/cprs/queue.jsonl (enrichment_eligible from tic 413 handoff). Resubmit-higher: principle is general (composes bounded-delegation + dont-trust-sync + coherence-is-not-admission); lived instances all one-rung CGG-runtime — promoted at cgg-ledger, abstracts to federation on cross-domain recurrence. Band: COGNITIVE. Confidence_tier: reinforced (three distinct failure classes validated same-tic; recursive obligation logically non-derivable from any single parent). -->

**SKIP-with-home note — apply this obligation at COMMIT TIME by splatting the change's OWN blast radius (tic 534 born → /review 537 SKIP-with-home).** Before finalizing a runtime/lifecycle change, run the six-ray splat over the change's OWN impact surfaces — callers + downstream readers, enumerated GREP-GROUNDED not inferred — and treat the lawful slice (excluded / held-open / needs-receipt / complete-within-lane) as the completion gate, not an optional analysis. The corrector-inherits obligation above is recursive over delegated patches; this names its commit-time application point on your own edit. Homed here, not promoted (born author self-assessed SKIP-with-home; high derivability from this entry + the splat mechanic; single-cycle).

<!-- SKIP-with-home /review 537 (durable home, NOT promoted-to-doctrine): cpr_splat_the_blast_radius_before_finalizing_a_runtime_change_tic534 (queue.jsonl, extracted->rejected). Reason: application-point of "The Corrector Inherits the Verification Obligation" + six-ray splat; born author self-assessed SKIP-with-home; single-cycle. Source: audit-logs/governance/borns-tic534-splat-blast-radius-and-terminal-else-merge.md. Band: COGNITIVE. -->

---

---

## An Absorber That Makes Raw Droppable Needs a Per-Tic Invoker — or the No-Dark Guarantee Silently Lapses
<a id="absorber-needs-per-tic-invoker-or-no-dark-guarantee-lapses"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | promoted_tic=426 | first_appearance_tic=425 -->

A telemetry/state ABSORBER whose contract is "raw becomes droppable WITHOUT a tic going dark, BECAUSE it is absorbed first" must have a per-tic INVOKER, or its persisted snapshot freezes and the no-dark guarantee silently lapses — masked at read-time by a live-raw overlay until retention drops the un-absorbed raw, at which point the gap goes permanently dark. `rollup.py build` (the mogul cycle-reports absorber, Architect decision (b) tic 405) had ZERO invokers repo-wide; reports-rollup.json.absorbed froze at tic 405 while raw reports 406–425 (20 tics) lived un-absorbed. The spine reads via `effective()` (frozen-snapshot OVERLAID with recompute-from-present-raw), so telemetry was not VISIBLY dark — but the tic-405 "droppable once absorbed" guarantee (gated by `verify --tic N`) was unfulfilled for 20 tics: a latent dark-tic time bomb under retention. Composes Conductor-Score-Runtime-Parity (doctrine names "absorb so raw is droppable"; runtime never wired the invoker) + can-it-eat (a present absorber that nothing calls is a mounted bear) + the io-map-roots lesson (the invokers — cadence-ops/mogul-runner — weren't even scanned, so the orphan was structurally unseeable). Diagnosis frame writer/reader/shape/surface: it was the WRITER (the absorber-writer had no invoker). REMEDIATED tic 425 (ran build → absorbed 405→425, verify PASS 0-mismatch). DURABLE FIX: a fail-soft `rollup.py build` step in cadence-ops.py (mirroring the tic-268 memory-md-audit observability subprocess) so the snapshot stays current every tic — fired LIVE this cadence ("287 tics absorbed"). Net-new: the per-tic-invoker obligation for any absorber that makes raw droppable. This is the runtime-mechanism complement to the federation `can-it-eat` predicate (a write-only absorber is a mounted bear) and the cadence-ops fail-soft observability subprocess pattern. source: borns-tic425-io-map-completeness.md

<!-- promoted from cpr_absorber_that_makes_raw_droppable_needs_a_per_tic_invoker_or_the_no_dark_guarantee_lapses_tic425 (tic 425→426, /review 426 fast-track PROMOTE, Architect maturity-0 override approved). Source: audit-logs/governance/borns-tic425-io-map-completeness.md. Band: PRIMITIVE. Confidence_tier reinforced (remediated 405→425 verify PASS + durable fix fired live). Domain commit 091e748. signer ent_homeskillet-c48. -->

---

## A Covenant-Strike Fires Only Post-/review-Ratification — Craft Is Separated From Strike by Both a /review Gate and a Boot Boundary
<a id="covenant-strike-fires-only-post-review-ratification"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=426 | first_appearance_tic=423 | refines=harpoon-strike-receipt-spec-§9 -->

A terminal-essence covenant-strike (Office of the Harpoon, harpoon_bridge::fulfill_covenant) fires ONLY POST-/review-RATIFICATION — the CRAFT is separated from the STRIKE by BOTH a /review gate AND a boot boundary, two distinct separations doing two distinct jobs. The lifecycle, validated live tic 423→424: (1) CRAFT — wright the Covenant{Reality→Target} poles + the DAG-of-DAGs composition (tranche lanes as sub-DAGs: A∥B∥C, C1⊳C2), run a multilane workflow-of-workflows (the Workflow tool's parallel()≡∥, pipeline()≡⊳, agent()≡a fragment strike) that dry-runs each ungated fragment HONEST-STATE-FIRST (verify against code, flag already_struck rather than fabricate motion) and synthesizes a dry-run seven-faced StrikeReceipt + a center-exclusion audit; the craft is CRAFT-valid, never LIVE-valid. (2) /review RATIFIES — coherence-is-not-admission: the workflow's internal craft-validity is NOT admission; the §9 LIVE-strike crown is the human gate's to give. (3) STRIKE the RATIFIED covenant — post-boot (anti-same-breath-heat, n=3 tics 346/347/348), fresh-context, firing fulfill_covenant in the OWNED build repo (vendored≠versioned). The STRIKE GATE is RATIFICATION, not the craft's coherence. Two payoffs proven: honest-state-first PREVENTED a fabricated strike (fragment A2 returned already_struck) AND surfaced a genuine target (fragment B1 caught a false ACTIVE claim vs lifecycle.state=completed — a false-terminal disagreement). Center-exclusion held across the whole composition (at governance altitude the Architect-gates ARE the still point). Composes: coherence-is-not-admission + anti-same-breath-heat + can-it-eat + the §9 harpoon-strike-receipt-spec + State-agreement-is-not-truth-unless-lifecycle-reachable. A REFINEMENT to the §9 spec (adds the craft→ratify→strike lifecycle + the workflow-as-composition mapping) and to the harness born cpr_covenant_strike_as_governance_implementation_harness_tic422 — NOT a new compact-root KI (non-derivability §2: derivable from the named composers). source: borns-tic423-covenant-strike-lifecycle.md

<!-- promoted from cpr_covenant_strike_fires_only_post_review_ratification_tic423 (tic 423→426, /review 426 PROMOTE-as-refinement, Architect-approved; matured from tic-423 deferral). Source: audit-logs/governance/borns-tic423-covenant-strike-lifecycle.md. Also inscribed as §11 advancement note in autonomous_kernel/harpoon-strike-receipt-spec.md. Validated live twice (tic 422 single-lane, tic 424 multi-lane). Band: STRUCTURAL. Confidence_tier reinforced. signer ent_homeskillet-c48. -->

---

## Build-and-Gate — Ship a Doctrine-Adjacent Model With Its Consumer Wired-but-Ratification-Gated, Not Deferred and Not Live
<a id="build-and-gate-ratified-flag-gated-consumer"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=430 | first_appearance_tic=429 -->

When you build a doctrine-adjacent model that a LIVE consumer would read (a boot renderer, a router, a dispatch gate), do not choose between the two fragile options — (a) DEFER the consumer wiring (a TODO that drifts, is forgotten, or is re-derived cold) or (b) SHIP IT LIVE and hope /review catches it before it conditions behavior. Instead, build the model in full, wire the consumer, and TEST it — but GATE the consumer's USE of the new model on an explicit `ratified` flag (default false) carried IN the model. While `ratified:false` the consumer surfaces NOTHING new, so the candidate conditions NO live behavior; /review flips `ratified:false→true` and the consumer activates with NO further code change. This converts the discipline "/review-gate the model before it conditions the next entity's boot" from a deferred-TODO (fragile, human-memory-dependent) into a MECHANICAL gate — ratification IS the flag-flip. The wiring is built+synced+tested at the cheapest moment (context hot); only its EFFECT waits on the human gate.

The COMPANION discipline (sharpened by this very ratification, tic 430): the gated build needs TWO proofs, not one. The DORMANCY proof (render at `ratified:false` → 0 new fragments) confirms the consumer is genuinely OFF. The ACTIVATION proof must exercise the consumer's FULL output surface at `ratified:true` — not merely confirm "0-at-false + one happy-path-at-true." The tic-429 dormancy proof verified the `from`-side of a directed edge but never the reciprocal `to`-side; the renderer surfaced a `reciprocal:true` edge only for its `from` office, so the to-side office's boot was silently missing the edge — caught ONLY when ratification went live at tic 430 and the to-side office was probed (fixed same-pass, installed mirror synced byte-identical). The gated activation moment is exactly where the full consumer surface must be exercised, because it is the controlled, human-gated flip before anything conditions a boot.

Composes (a derivable refinement, NOT a new compact-root KI per Constitutional-Law non-derivability §2): Self-Conditioning-Discipline-needs-thin-terminal-residue (residue/state boundary) + Presence/Observation-Fallacy-Guard's presence-of-wiring≠activation (cpr_safe_vs_true tic363 — activation gated by STATE, here an explicit carried flag) + the provenance-round candidate-state precedent (office-lanes 4→19 ratified as CANDIDATE boot-terrain at /review 427). Constructive delta beyond those: they govern WHEN a built thing is trusted/active; this governs HOW to ship a doctrine-adjacent model so the build lands hot but its live EFFECT is a single human-gated flag-flip — plus the dual-proof (dormancy + full-surface activation) discipline.

(Validated: tic 429 office-directory build [bk-office-directory-subtelos] — subtelos×19 + collaboration_edges×9 built `ratified:false`; office-worldview.py L1/L5 renderer wired but gated on `ratified is True`; render @ ratified:false → 0 fragments [boot unconditioned]; temp flip → subtelos@L1 + collaborates@L5, sources restored byte-identical. tic 430 /review RATIFIED [the flag-flip the born predicted] — the activation surfaced + fixed the reciprocal to-side render gap [the companion-proof]. n=1 build, corroborated by its own ratification surfacing the dual-proof lesson.)

<!-- promoted from cpr_ratified_flag_gated_consumer_for_doctrine_adjacent_model_tic429 (tic 429→430, /review 430 PROMOTE-as-refinement, Architect-approved). Refines Self-Conditioning-Discipline-needs-thin-terminal-residue + Presence/Observation-Fallacy-Guard (presence-of-wiring≠activation) + the candidate-state precedent. Constructive delta = build-and-gate ship-discipline + dual-proof (dormancy + full-surface activation). Confidence_tier: tentative→reinforced (n=1 build corroborated by its own ratification surfacing the companion-proof gap). Band: COGNITIVE. signer ent_homeskillet-c48. -->

---

## Silent transition deadlock — gate checks the next state's output (mechanical/model split fix)
<a id="silent-transition-deadlock-gate-checks-next-state-output"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | promoted_tic=471 | first_appearance_tic=470 | refines=enrichment-pipeline-silent-starvation-surface,conductor-score-runtime-parity-cgg-application,presence-observation-fallacy-guard -->

A lifecycle transition deadlocks SILENTLY when its only on-disk writer is an unscheduled, model-only agent AND its gate requires an artifact produced only AFTER the transition (the next state's output) — making the precondition to ENTER a state that state's own output. Nothing advances the row, and it is invisible to any reader whose status-taxonomy doesn't recognize the in-between state. The fix is a three-part structural move, not a nudge: (1) SPLIT the transition into its model-needing half (keep with the agent — e.g. verify-twin DEDUP) and its mechanical half (no judgment); (2) give the mechanical half a DETERMINISTIC on-disk owner — a small reconciler wired into an always-run path (boot), gated on the REAL pre-transition evidence (a baseline that already exists), NEVER on the post-transition output; (3) make the in-between status RECOGNIZED by the state-compiler so a stuck row reads live, never silent-unknown. The deadlock is doubly dangerous because it is silent by the same gap: the unrecognized status hides the starvation from every routine reader. Validated tic 470 (the tic_gated→enrichment_needed CPR enrichment chicken-and-egg: 7 rows unstuck end-to-end; built cpr-gate-advance.py; reconciler idempotent) and again tic 471 (n=2 — the reconciler gave the two new borns their baselines clean in the wild).

<!-- promoted from cpr_442e6b47f648b4d6 (tic 470→471, /review 471 Architect-approved "review execute and GO"). Source: audit-logs/governance/borns-tic470-transition-deadlock-deterministic-reconciler.md. refines: Enrichment-Pipeline-Silent-Starvation-Surface · Conductor-Score-Runtime Parity (CGG application) · Presence/Observation Fallacy (the silent half). Band: COGNITIVE. signer ent_review_execute. -->

---

## Anchor-Field Iteration Over-Collects When the Last Anchor Is Unbounded (REFINE — Boundary-Aware Body Extraction)
<a id="anchor-field-iteration-over-collects-last-anchor-unbounded"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=472 | first_appearance_tic=471 | refines=boundary-aware-body-extraction | composes=extractor-output-anomaly-flagging | confidence_tier=reinforced | validation_n=2 -->

**When you parse a structured document by iterating an ANCHOR field and collecting each record's co-located free-text by "span to the next occurrence of that same anchor," the parse over-collects at every boundary the anchor does not mark — and the LAST anchor's span runs unbounded to EOF, silently swallowing every trailing un-anchored section.** The record's true boundary is the document's STRUCTURAL delimiter (the `### ` heading / `---` separator that actually separates entries), NOT the next occurrence of the field you happen to be iterating. The two coincide only when every structural entry carries exactly one anchor and nothing un-anchored trails the last one — neither holds in a real corpus (verbatim/body sections, section intros, and appendices carry the same co-located tokens but no anchor). Fix: bound each record at `min(next structural delimiter, next anchor)`, never at the next anchor alone. The CANARY is cheap and reliable: one record matching an implausibly large number of co-located tokens (here, a single KI matching 13 lanes and topping every rung's ranking) is over-collection inflating exactly the trailing record — verify the count before trusting the ranking it produces (composes Extractor Output Anomaly Flagging).

**Source (tic 471):** building the C9 down-lane Stage-1 selector (`ladder-audit.py select-kis`, KI-selection-by-applicability). The first ledger-tag parser anchored each KI's span on `invariant_id`→next-`invariant_id` and unioned every `lanes:` in that span. The LAST invariant_id (`ki_session_memory_pickup`, ledger line 2457) ran to EOF and absorbed all 24 inline `lanes:` provenance comments in the trailing "Compact-Root Source Bodies" verbatim section → a 13-lane over-match that ranked #1 for EVERY rung. Caught by the implausible-count canary; fixed by bounding each entry at the next `### ` heading (`min(next_h3, next_invariant)`). Post-fix: 153 KIs parsed, 0 of 84+ candidates with matched-tags outside their rung's concerns, `ki_session_memory_pickup` correctly excluded (its `structural_pointer` terrain_class is in no rung's concerns). Read-only, installed byte-parity (runtime-sync 202/0-drift).

**Refinement note:** Sibling/refinement of `cgg-ledger#boundary-aware-body-extraction` (that names hardcoded-line-offset body extraction breaking when the boundary MOVES; this names anchor-field-iteration over-collecting because the boundary is the WRONG DELIMITER and the last anchor is UNBOUNDED — same family: "trust the structural delimiter, not a positional/field proxy for it"). Composes Extractor Output Anomaly Flagging (the implausible-count canary) + the Authoritative-Set-Readers / terminal-valve family (read the real record boundary, not an aggregate proxy). Validated n=2: tic-471 Stage-1 select-kis + tic-472 Stage-2 down-audit packet-assembler.

<!-- promoted from cpr_a259c4f371253e68 (tic 471→472, /review 472). Source: audit-logs/governance/borns-tic471-ledger-span-attribution-bound-at-structural-delimiter.md (1st agnostic-candidate block). REFINE-child of boundary-aware-body-extraction (anchor-iteration variant). Band: COGNITIVE. signer ent_review_execute. -->

---

## ID-Form Divergence Across Extraction Surfaces Silently Voids Cross-Surface Writeback (REFINE — Atomic Dual-Surface Invariant Mechanization)
<a id="id-form-divergence-voids-cross-surface-writeback"></a>
<!-- ledger-tags: authority_class=verification_and_proof_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=472 | first_appearance_tic=471 | refines=atomic-dual-surface-invariant-mechanization | composes=conductor-score-runtime-parity-cgg-application,silent-transition-deadlock-gate-checks-next-state-output | confidence_tier=tentative | validation_n=1 | backlog=bk-review-promote-writeback-id-resolution -->

**A cross-surface writeback/reconciler that locates its target by an ID must key on the SAME id-form the target actually carries — when an extractor mints a fresh SURROGATE id (a content hash) for the queue entry while the source artifact keeps its DECLARED long-form id, the two id-forms diverge and any operation keyed on one silently NO-OPS on the other: 0 matches, clean exit, no error.** This is the silent-no-op failure class (sibling to the tic-470 transition deadlock): a governance step runs, reports success, and mutates nothing. The defense is two-fold: (1) at the boundary, either PRESERVE the declared id through extraction (one stable id per lesson, both surfaces agree) OR have the cross-surface op RESOLVE the id-form via the queue entry's recorded source-pointer / lesson-content-hash rather than assuming id-equality across surfaces; (2) ASSERT the post-condition — a writeback whose `flipped_count != promoted_count` is a silent no-op and must surface, never report success on 0 mutations (the same "recognize-the-in-between / count-the-mutations" discipline the deadlock-reconciler named). A tool that says "done" while doing nothing is the most expensive kind of clean exit.

**Source (tic 471):** /review 471 Pass 1 review-execute. `review-promote-writeback.py` reported `inline_blocks_flipped: 0` for all 4 PROMOTEs: it searches born files by the queue's hash id (e.g. cpr_c58914f1e2783a99) but the born files carry their DECLARED long-form cpr_id (e.g. cpr_block_classification_discriminator_before_architect_decision_tic468) — cpr-extract assigned a fresh hash surrogate to the queue entry instead of preserving the born's declared id, so the two diverge. The review-execute agent caught it (the flips were 0 but the inscriptions were real), applied the born-marker flips manually, and surfaced the helper gap rather than silently absorbing it. Backlog: bk-review-promote-writeback-id-resolution.

**Refinement note:** Composes the silent-no-op family — Conductor-Score-Runtime Parity (the tool names a discipline it does not mechanically complete) + the tic-470 silent-transition-deadlock (a step that runs and mutates nothing, invisibly) + Atomic-Dual-Surface-Invariant-Mechanization (a tool implementing one half of a dual-surface invariant must complete the other half or surface). Net-new teeth: the ID-FORM DIVERGENCE across extraction surfaces (surrogate hash vs declared id) as the specific silent-no-op trigger + the `flipped==promoted` post-assertion.

<!-- promoted from cpr_c44d2064b9c82f51 (tic 471→472, /review 472). Source: audit-logs/governance/borns-tic471-ledger-span-attribution-bound-at-structural-delimiter.md (2nd agnostic-candidate block). REFINE-child of Atomic-Dual-Surface-Invariant-Mechanization; silent-no-op family. Band: COGNITIVE. signer ent_review_execute. -->

---

## New Consumer Over Long-Lived Emitter Surface Must Be Scope-Bounded, Not Retroactive
<a id="new-consumer-over-long-lived-emitter-surface-must-be-scope-bounded-not-retroactive"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | promoted_tic=485 | first_appearance_tic=483 | refines=emitter-surface-declared-interface | inverts=structural-transform-implies-closed-consumer-set-obligation | confidence_tier=tentative | relations=composes:conductor-score-runtime-parity-cgg-application,dedup-at-write-using-canonical-identity,terminal-state-valve-pattern -->

Wiring a NEW automatic consumer to a LONG-LIVED emitter surface that has accreted history is a retroactive-ingestion hazard, not just a reachability fix. When a surface emits governance artifacts (here: session_lessons_tic_<N>.md emitting BLOCK-form --agnostic-candidate borns) and a downstream automatic consumer (cpr-extract's scan set) was never wired to read it, two things are simultaneously true: (a) the forward gap is real and doctrine-mandated to close — *Emitter Surface Declared Interface* requires every --agnostic-candidate emitter be reachable by cpr-extract, and the boot already COUNTS these borns while the extractor cannot REACH them (a two-reader-disagreement / Conductor-Score-Runtime parity gap on the same surface); and (b) the surface holds an accreted backlog (here ~195 born-ids since tic 164) that an UNCONDITIONAL new consumer would silently mass-ingest on its first run. The cure is to scope-bound the new consumer (recency window / status gate) so it closes the FORWARD gap without sweeping the HISTORICAL accumulation — and to surface that historical backlog as an EXPLICITLY-GATED, separately-adjudicated decision, never a consumer side effect. The recency bound must be PROVABLY INERT at install time on the current state (0 new extractions today, the already-reachable items dedup-skipped) AND must expose a gated escape hatch (here --session-lessons-window N) so the historical sweep, if ever wanted, is a deliberate /review-gated act. This is the DUAL of *a structural transform on a shared surface creates a closed consumer-set update obligation*: that KI governs RELOCATING content (obligating existing readers to update); this governs ADDING a reader over existing/accreted content (obligating a scope bound so history is not silently swallowed).

<!-- promoted from cpr_new_consumer_over_long_lived_emitter_surface_must_be_scope_bounded_not_retroactive_tic483 (tic 483→485, /review 485). Source: session_lessons_tic_483.md. Refines Emitter Surface Declared Interface; INVERTS federation structural-transform-implies-closed-consumer-set-obligation (new-reader-over-accreted-content vs relocation-obligates-readers). Band: COGNITIVE. signer ent_review_execute. -->

**Refinement — the recency-window scope-bound governs DISCOVERY, not a KEYED writeback (tic 518 born → /review 519 PROMOTE-as-refinement, Architect-gated):** This KI's scope-bound is a DISCOVERY-consumer discipline — it governs a consumer that SWEEPS a long-lived surface for new/unprocessed items (cpr-extract windowing to the born frontier to avoid mass-ingesting accreted history). It must NOT be applied to a KEYED, by-id consumer — a promotion WRITEBACK that flips ONE specific cpr_id / content-hash block. That consumer's KEY is already its bound: it touches only the matched block, and the born it must reach can be of ANY age (a born promoted now may be many tics old). Recency-windowing a keyed writeback would silently fail to flip old promoted blocks — the exact silent-no-op class the writeback exists to kill (sibling of #id-form-divergence-voids-cross-surface-writeback). Discriminator: does the consumer SWEEP-for-unknowns (window it) or LOOK-UP-a-known-key (full corpus; the key is the bound)? (Validated tic 518: the borns-home writeback in review-promote-writeback.py was deliberately built NOT recency-windowed — the apophatic boundary against cpr-extract's windowed discovery over the same born-home surface.) The apophatic boundary of the parent KI.

<!-- promoted from cpr_recency_window_scope_bound_is_discovery_not_keyed_writeback_tic518 (tic 518→519, /review 519). Source: audit-logs/governance/borns-tic518-recency-window-is-discovery-not-keyed-writeback.md. Refines new-consumer-over-long-lived-emitter-surface-must-be-scope-bounded-not-retroactive (its apophatic boundary: a keyed by-id consumer's key IS its bound); composes id-form-divergence-voids-cross-surface-writeback. Band: COGNITIVE. Confidence: 0.85. Architect-gated. -->

---

## Footgun Guard at Perception Layer Warns After the Footgun Already Fired
<a id="footgun-guard-at-perception-layer-warns-after-the-footgun-already-fired"></a>
<!-- ledger-tags: authority_class=forensic_and_drift_investigation | rung=domain | domain=context-grapple-gun | promoted_tic=485 | first_appearance_tic=482 | refines=detection-affordance-tracking | composes=autonomous-agent-tool-economics-physics-vs-perception | confidence_tier=tentative | relations=supports:named-footgun-guard-leaves-sibling-site-unfixed -->

A footgun GUARD that only DETECTS-and-WARNS is a perception-layer guard: the warning fires AFTER the hazardous value has already been written, so the footgun still fires. A guard is only complete when its own computed classification is LOAD-BEARING at the physics layer — it must ROUTE/HALT the value at the write boundary, not decorate a downstream warning. Concretely: boot-receipt.py's `--omitted-range` (a legacy alias whose NAME means render-bounded negative space) filed every value into the BLOCKING `required_unread_ranges`; the tic-474 guard COMPUTED `_looks_apophatic` per value, emitted a precise warning that the value reads as non-blocking apophatic space — then threw that computed classification away and filed it as gate debt regardless, silently self-DoS'ing the governance-mutation gate of the very boot whose loop it was closing (proven live: the orchestrator's own tic-482 boot blocked on a reasonable flag choice). The cure moved the guard from perception (warn) to physics (reroute-before-write): per-value, the same classification now routes apophatic values to the non-blocking `apophatic_range_bounds` and leaves genuine required-unread blocking. Doctrine: when a guard can CLASSIFY a hazard it must ENFORCE on that classification at the execution boundary; a warn-only guard that recomputes-then-discards its verdict leaves the hazard fully live — detection_affordance without enforcement_affordance is not a guard.

<!-- promoted from cpr_footgun_guard_at_perception_layer_warns_after_the_footgun_already_fired_tic482 (tic 482→485, /review 485). Source: session_lessons_tic_482.md. Refines Detection Affordance Tracking (a guard that recomputes-then-discards is perception-layer, not physics-layer). Supports sibling cgg-ledger#named-footgun-guard-leaves-sibling-site-unfixed. Band: COGNITIVE. signer ent_review_execute. -->

---

## Named Footgun Guard Leaves Sibling Site Unfixed
<a id="named-footgun-guard-leaves-sibling-site-unfixed"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=485 | first_appearance_tic=481 | refines=named-is-not-landed-gate | composes=structural-transform-implies-closed-consumer-set-obligation,id-form-divergence-voids-cross-surface-writeback | confidence_tier=tentative | relations=supports:footgun-guard-at-perception-layer-warns-after-the-footgun-already-fired -->

A promoted footgun-guard applied to ONE function silently leaves a SIBLING function in the SAME FILE carrying the un-guarded footgun the promotion already named — the fix-site and the bug-sibling-site are a closed consumer set. tic-472 promoted `id-form-divergence-voids-cross-surface-writeback` and fixed `stamp_reinforced_by` in review-promote-writeback.py (resolve a ledger entry by anchor/id-set, never a single fuzzy cpr_id), but `flip_inline_status` — same file, same cross-surface-writeback class (id-keyed match against an inline candidate block) — kept the single exact-cpr_id match for 9 tics, silently no-op'ing (inline_blocks_flipped=0, clean exit) whenever the queue carried a hash-derived id (cpr_<dedup_hash>) while the born block declared a different / absent id. Every boot then miscounted stale-promoted CogPRs as pending. The cure was to PORT the same id-set + content-identity (dedup_hash) resolution from the already-fixed sibling. Doctrine: a named-footgun promotion owes a sibling-site audit at intake (grep the file / surface for the SAME operation class and the SAME bug shape), the same way a structural transform owes a consumer-set manifest — the promotion's consumer set INCLUDES same-file siblings performing the same operation. Discriminator: 'did this guard land at the ONLY site of this operation class, or are there siblings doing the same operation un-guarded?'

<!-- promoted from cpr_named_footgun_guard_leaves_sibling_site_unfixed_tic481 (tic 481→485, /review 485). Source: session_lessons_tic_481.md. Refines Named-Is-Not-Landed Gate (a bug-fix promotion's consumer-set includes same-file siblings of the same operation class). Distinct axis from sibling cgg-ledger#footgun-guard-at-perception-layer-warns-after-the-footgun-already-fired (enforcement-LAYER vs coverage-SITE). Supports edge to that sibling. Band: COGNITIVE. signer ent_review_execute. -->

**Refinement (tic 498→/review 522, Architect-gated) — the guard turns on ITSELF: an emitter-REACH fix applied to one born home leaves the SIBLING born home unwired.** The same closed-consumer-set logic applies one rung up, to the emitter-surface-reachability guard itself. The tic-483 fix wired `session_lessons_tic_<N>.md` into cpr-extract (frontier-anchored, recency-bounded) to satisfy *Emitter Surface Declared Interface* — but sessions ALSO author standalone born detail-docs as `audit-logs/governance/borns-tic<N>-<slug>.md`, a SIBLING emitter home cpr-extract never scanned. So a born whose `--agnostic-candidate` block lived ONLY there (not also mirrored into MEMORY.md / session_lessons) was silently UNREACHABLE — never entered queue.jsonl, never reached /review. Confirmed tic 498: 9 of 55 borns-*.md IDs were stranded out of the queue, ALL the recent cohort (493-498), stranded precisely because MEMORY.md was over its load limit so the blocks were never mirrored to a reachable surface. The cure is generator-level with the SAME recency discipline as the original sibling (*New Consumer Over Long-Lived Emitter Surface Must Be Scope-Bounded*): `select_borns_files`, frontier-anchored on the newest borns-*.md tic, window-bounded so the historical backlog is not mass-extracted, dedup-at-write skipping the already-queued cohort — BUILT+LIVE. SUB-LESSON (authoring side): a born whose slug lives only in its markdown `##` header but NOT as an `id:` field INSIDE the block extracts under a HASH id (an authoring-time instance of *ID-Form Divergence Across Extraction Surfaces*; promote-time-resolved, but avoidable — put `id:` IN the block). Discriminator extends the parent's: "did the reach-guard land at the ONLY emitter home of this artifact class, or are there SIBLING homes emitting the same `--agnostic-candidate` block un-scanned?" The actionable `BORNS_WRITEBACK_RATIFIED` build-and-gate flip (dual-proof: dormancy 0-at-false + full-surface activation) is HELD pending its own gate; this inscription is the lesson, not the flip.

<!-- promoted from cpr_borns_governance_home_is_an_unwired_emitter_sibling_site_tic498 (tic 498, re-activated tic 521 deferred→enrichment_eligible, /review 522 PROMOTE-as-refinement, Architect-gated [AskUserQuestion approval]). Source: audit-logs/governance/borns-tic498-borns-home-sibling-site-unwired-in-cpr-extract.md. Refines this KI (the reach-guard's own sibling-home blind spot) + Emitter-Surface-Declared-Interface; composes New-Consumer-Over-Long-Lived-Emitter-Surface-Must-Be-Scope-Bounded + ID-Form-Divergence-Across-Extraction-Surfaces. Cure BUILT+LIVE (select_borns_files); BORNS_WRITEBACK_RATIFIED flip HELD (build-and-gate, dual-proof owed). Band: PRIMITIVE. signer ent_homeskillet-c48. -->

---

## Harness-Agnostic Is Verified Against Runtime Ground Truth, Not Lagging Published Schema
<a id="harness-agnostic-is-verified-against-runtime-ground-truth-not-lagging-published-schema"></a>
<!-- ledger-tags: authority_class=external_schema_volatility | rung=domain | domain=context-grapple-gun | promoted_tic=485 | first_appearance_tic=484 | refines=volatile-schema-validation-discipline-probe-before-bind,epistemic-volatility-notice | composes=authoritative-set-readers-manifest-not-raw-emissions,disagreement-as-evidence | confidence_tier=tentative -->

"Harness-agnostic" is not a static property a mounted governance stack HAS — it is a property RE-EARNED at every external-harness version bump by re-confirming each coupling against RUNTIME GROUND TRUTH, because published docs/schema/changelog all LAG the shipped binary. This sharpens Probe-Before-Bind by establishing a PROBE-SURFACE HIERARCHY for externally-versioned primitives: (1) the installed BINARY's recognized-string set is ground truth for 'is this settings key / hook event honored' — and it BEATS the published JSON schema (schemastore), which can be STALE relative to the binary (proven: schemastore lacked showClearContextOnPlanAccept/autoCompactEnabled/useAutoModeDuringPlan while the 2.1.185 binary recognized all 26 of our keys); (2) a LIVE in-session observation is ground truth for an I/O contract and beats schema-SILENCE — the hookSpecificOutput.additionalContext injection contract is not detailed in the published schema (a claude-code-guide could only mark it 'cannot-verify'), yet it demonstrably FIRED this session, which is dispositive; (3) published docs/schema are the next tier (current but laggy); (4) a CHANGELOG name alone is the weakest (the original Probe-Before-Bind floor). COROLLARY (collision-safety as a structural, VERIFIED invariant, not an assumed one): a mounted governance skill-stack survives built-in name-collisions ONLY because skill-resolution precedence is Personal > Bundled/built-in — a built-in shipping a colliding name (here built-in /review vs CGG's constitutional /review gate) is the one shadowed, not ours — BUT the precedence ORDER is itself externally-versioned, so it must be CONFIRMED (docs, confidence-A) rather than assumed to have been preserved across the bump. The discipline: on a harness version bump, do not assume the mount is intact AND do not assume it is broken; re-probe each coupling against the highest available ground-truth tier (binary string table, then live boot, then docs, never changelog-name), and treat a probe DISAGREEMENT (here a zsh non-word-splitting false-negative on the collision sweep) as evidence to resolve by direct inspection, not a result to average.

<!-- promoted from cpr_harness_agnostic_is_verified_against_runtime_ground_truth_not_lagging_published_schema_tic484 (tic 484→485, /review 485). Source: session_lessons_tic_484.md. Refines Volatile-Schema Validation Discipline (Probe-Before-Bind): adds probe-surface hierarchy (binary string-table + live-boot > published schema/docs > changelog) + personal-skill-precedence collision-safety corollary. Band: COGNITIVE. signer ent_review_execute. -->

---

## Stage Prose Template Compression Must Be Declared
<a id="stage-prose-template-compression-must-be-declared"></a>
<!-- ledger-tags: authority_class=arena_and_reasoning_geometry | rung=domain | domain=context-grapple-gun | promoted_tic=485 | first_appearance_tic=376 | refines=arena-velocity-guard | confidence_tier=tentative -->

The OA-VPL-T (and VPL/CRX) arena templates prescribe full phases (context→defense→REBUTTAL→
synthesis→pressure-extraction) + a per-phase record trail in PROSE (spec.md), with NO tasks.yaml
DAG. So "no skipping phases — enforced via task blockers" is aspirational: nothing mechanically
stops a LEAD from fusing context+defense, skipping rebuttal, and writing zero records (exactly the
tic-376 failure). Single-round convergence WITHOUT rebuttal carries false-convergence risk the
rebuttal phase exists to test (Arena Velocity Guard). Fix (PARTIALLY LANDED this session in
/stage SKILL.md invariants #5/#8): (1) any compression (phase fusion / rebuttal skip / fewer rounds
/ wildcard-instead-of-rebuttal) is a DECLARED exception recorded in spec `compression:` + pressure-
report `compression_applied`; silent compression is a named breach. (2) Arena is not `completed`
until the record set exists ON DISK (per-phase files, synthesis.md, pressure-report JSON,
registry.jsonl append); in-context relay is NOT a substitute (Manual-Ceremony-as-Pipeline-Substitute).
(3) Unrebutted convergence → pressure-report `false_convergence_risk: unrebutted`.
REMAINING (deeper fix, not done): add real tasks.yaml DAGs to the prose-only templates so phase-
gating is MECHANICAL not LEAD-discipline. SKILL.md patch makes compression legible; tasks.yaml
would make it blocked.

<!-- promoted from cpr_stage_prose_template_compression_must_be_declared_tic376 (tic 376→485, /review 485). Source: session_lessons_tic_376.md. Refines Arena Velocity Guard (declared-exception + on-disk completion gate + false_convergence_risk:unrebutted metadata). Band: COGNITIVE. signer ent_review_execute. -->

---

## Promoted-Spec Build Obligation Outlives Spec-Doc Archival or Move
<a id="promoted-spec-build-obligation-outlives-spec-doc-archival-or-move"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=485 | first_appearance_tic=396 | refines=named-is-not-landed-gate | composes=terminal-state-change-requires-receipt-and-no-signal-goes-dark | confidence_tier=tentative -->

A promoted-spec (already past /review) can be silently dropped at the spec→impl / deprecation step, and the cruft it was meant to prevent accumulates as the tombstone that proves the drop. Tic-269 inbox-attention-debt mass-resolve primitive was promoted_spec (/review 269), spec written tic-271, then moved to deprecated-docs and never built; 159 dormant WAIT signals accumulated for ~127 tics as the visible evidence — surfaced only when the Architect noticed raw-scan bloat at tic 396. The terminal of a promoted-spec is promoted_spec→built (or explicit re-defer), NOT promoted_spec; a deprecation move on the spec DOC must not silently retire the build OBLIGATION (the obligation outlives the doc). Detection affordance: the prevented cruft IS the detector — its accumulation rate measures how long the drop has gone unbuilt.

<!-- promoted from cpr_c67dad39aea12d29 (tic 396→485, /review 485). Source: session_lessons_tic_396.md. Refines Named-Is-Not-Landed Gate with cross-ref to federation terminal-state-change-requires-receipt-and-no-signal-goes-dark (a promoted-spec's BUILD obligation outlives a spec-doc archival/move). Band: COGNITIVE. signer ent_review_execute. -->

---

## Uncommitted-By-Design Content Requires Physics-Layer Gitignore Guard
<a id="uncommitted-by-design-content-requires-physics-layer-gitignore-guard"></a>
<!-- ledger-tags: authority_class=sync_and_install_parity | rung=domain | domain=context-grapple-gun | promoted_tic=485 | first_appearance_tic=396 | refines=claimed-install-state-requires-auditable-sync-log-proof | composes=versioning-is-mandatory | confidence_tier=tentative -->

"Uncommitted-by-design" is fragile ambient state, not a guard. A transient surface whose contents must NOT be committed (inbound courier drops, privacy tranches, unprocessed deliveries) cannot rely on the discipline-layer convention "remember not to commit these" — because a single broad `git add -A` (or `git add <dir>`) sweeps them the moment an attentive scope slips. The guard must be physics-layer: gitignore the transient class so a broad add CANNOT stage it, paired with a tracked paths-only receipt/manifest that preserves provenance + disposition + a commit-hint. When content crosses to canonical it is committed at its canonical path; the courier copy stays ignored. (tic-396: a /cadence `git add -A audit-logs/` swept 23 uncommitted-by-design inbound files incl. a privacy literary tranche to the private remote; scrubbed via --force-with-lease; root-caused with a gitignore courier-drop class + INBOUND_DROP_RECEIPT.md.)

<!-- promoted from cpr_d565cb1cbc67d82d (tic 396→485, /review 485). Source: session_lessons_tic_396.md. Cross-ref federation Versioning is mandatory (gitignore as physics-layer guard for uncommitted-by-design content; convention alone fails vs git add -A). Band: COGNITIVE. signer ent_review_execute. -->

---

## SKIP ≠ DISCARD — A Derivable Operational Lesson With Recurring Cost Still Needs a Session-Loading Home
<a id="skip-not-discard-derivable-costly-lesson-needs-loading-home"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=515 | first_appearance_tic=490 | composes=federation-ladder-lock-6-skip-not-discard | confidence_tier=tentative -->

A /review verdict of SKIP / not-net-new-doctrine (derivable) decides DOCTRINE STATUS; it does NOT decide whether the lesson should PERSIST. Skipped ≠ discard. A derivable operational lesson with real recurring cost (re-probed-wrong, re-diagnosed, a keystone re-deferred) must still be routed to a durable home that LOADS EACH SESSION — a `feedback`/`reference` MEMORY (index + topic file), not left only in a skipped queue row + a borns file nobody re-reads. The /review pipeline routes PROMOTE → doctrine and SKIP → (nothing durable); the missing edge is SKIP-but-operationally-costly → memory. Without that edge the system pays the lesson's cost repeatedly while believing it "handled" it (the skip felt like closure). Memory is the home for true-but-derivable operational reminders; doctrine is the home for non-derivable law; a born can be BOTH derivable AND worth persisting. This is the CGG-runtime instantiation of federation ladder lock #6 (SKIP ≠ DISCARD) — the runtime gap is the missing SKIP→memory routing edge in the /review verdict applier.

<!-- promoted from cpr_b7c9afd2c1a11eea (tic 490→515, /review 515 PROMOTE). Source: borns tic 490. The /review SKIP verdict decides doctrine status, not persistence; the missing pipeline edge is SKIP-but-costly → session-loading memory. Instantiates federation ladder lock #6 at CGG runtime. Band: COGNITIVE. signer ent_homeskillet-c48. -->

---

## Stale Intake Artifact Must Be Regenerated Through Its Lane, Not Bypassed by an Ad-Hoc Scan
<a id="stale-intake-artifact-regenerate-through-lane-not-bypass"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=515 | first_appearance_tic=505 | composes=emitter-surface-declared-interface,authoritative-count-discipline | confidence_tier=tentative -->

When a pipeline's terminal artifact is STALE (e.g. the /review bench-packet at tic 480 with 0 items), the correct move is to REGENERATE it by RE-RUNNING its producing lane (cpr-enrichment-scanner → bench-packet-prep), NOT to bypass it with an ad-hoc inline scan of the upstream substrate (queue.jsonl). A stale terminal artifact is a signal to FIRE THE LANE, not a license to read around it — bypassing skips the flows the lane triggers (enrichment baselines, coverage manifest, review clustering, the governance/enrichment writes) and produces a docket that LOOKS assembled but skipped its intake discipline. The boot ack states the rule literally ("a /review docket comes ONLY through the bench-packet intake lane … never ad hoc grep"). This is the Case-2 shape (the rule is ledgered; the gap was REHYDRATION at the inciting incident) — the cure is to apply the rule where it fires, and the durable home is here. Composes Emitter-Surface-Declared-Interface + Authoritative-Count-Discipline + the stale≠absent / regenerate-the-producer discipline.

<!-- promoted from cpr_stale_intake_artifact_must_be_regenerated_through_its_lane_not_bypassed_by_an_adhoc_scan_tic505 (tic 505→515, /review 515 PROMOTE). Source: borns tic 505 (Architect corrected a queue-scan bypass of the bench-packet lane). Re-exercised LIVE this tic: the tic-513 stale bench-packet was regenerated through its lane (bench-packet-prep → tic 515, 31 pending, 100% coverage) BEFORE the /review docket assembled. Composes emitter-surface-declared-interface + authoritative-count-discipline. Band: COGNITIVE. signer ent_homeskillet-c48. -->

---

## Inscription-Verification Is Reason-Coded, Dehydration-Aware, and Provenance-Anchored — Verifier-Split Chapter 2
<a id="inscription-verification-reason-coded-dehydration-provenance-aware"></a>
<!-- ledger-tags: authority_class=review_and_promotion_discipline | rung=domain | domain=context-grapple-gun | promoted_tic=515 | first_appearance_tic=493 | refines=reason-coded-genuine-vs-known-verifier-split,review-execute-atomic-writeback-completeness | confidence_tier=reinforced -->

The post-inscription consistency verifier (`review-close-check.py`) has three coupled correctness gaps, all one centroid — a content-matching verifier mis-classifies confirmed-present inscriptions as GENUINE orphans/missing because its matching axis is wrong for the inscription's SHAPE. The merged discipline (chapter 2 of the verifier-split, refining `reason-coded-genuine-vs-known-verifier-split` + `review-execute-atomic-writeback-completeness`):

**(1) REFINE / conformation-verdict false-negatives (tic 493).** A promotion that lands as a REFINEMENT to an existing Key Invariant (or as a conformation-verdict) carries no fresh verbatim lesson block; a lexical verbatim-match verifier reports it `promoted_text_missing` though it genuinely landed. The verifier needs a known-reason class for refinement/conformation inscriptions, not only fresh-parent promotions.

**(2) Dehydrating-surface false-negatives (tic 513).** A verifier that lexically matches a CogPR's VERBATIM promoted text against a DEHYDRATING doctrine surface (compact root shedding bodies to the ledger) will false-orphan inscriptions that moved to the ledger — the verbatim text is no longer at the compact-root path it was promoted to.

**(3) The provenance-comment recognizer is the STRONGEST axis (tic 514).** `build_inscribed_index` via `_PROVENANCE_VERB_RE` (recognizing `<!-- promoted from cpr_… -->` / `<!-- refinement edge from cpr_… -->`) is the verifier's most reliable verification axis: a provenance comment carrying the literal `cpr_id` survives dehydration, refinement, and relocation in a way verbatim-text matching does not. The discipline: anchor verification on the provenance comment first (cpr_id literal), fall back to verbatim text only as a secondary axis — and every inscription (PROMOTE, refinement edge, MERGE) MUST stamp a provenance comment so the strongest axis is available.

Together: the verifier's known-reason taxonomy gains `refinement_or_conformation_inscription` + `dehydration_relocated_to_ledger`, and its primary matching axis becomes the provenance-comment cpr_id recognizer, not verbatim text.

<!-- promoted from cpr_mogul_review_close_check_22f9580fc783 (tic 493, primary) ⊕ cpr_mogul_review_close_check_1bbafd660c4f (tic 511) ⊕ cpr_mogul_review_close_check_1e1f1e655285 (tic 513) ⊕ cpr_mogul_review_close_check_26ea838d50bc (tic 514) — MERGE at /review 515 (Architect-gated batch apply). Four review-close-check correctness gaps = one centroid (content-matching mis-classifies present inscriptions by the wrong axis). Refines reason-coded-genuine-vs-known-verifier-split + review-execute-atomic-writeback-completeness. Confidence_tier reinforced (4 independent sources across tics 493-514). Band: STRUCTURAL. signer ent_homeskillet-c48. -->

---

## A Status Value Readers Disagree On (Terminal vs Active) Sticky-Masks a Re-Activated Item — DEFER Must Write the Spec Status, Not the Divergent One
<a id="status-value-reader-disagreement-sticky-masks-reactivated-item"></a>
<!-- ledger-tags: authority_class=signal_and_queue_manifold | rung=domain | domain=context-grapple-gun | promoted_tic=522 | first_appearance_tic=521 | refines=terminal-state-valve-pattern | composes=conductor-score-runtime-parity-cgg-application,inline-tracked-cogpr-defer-keeps-status-pending-review-step-7-discipline | relations=composes:disagreement-as-evidence(federation),state-agreement-is-not-truth-unless-lifecycle-reachable(federation) | confidence_tier=tentative -->

A /review DEFER verdict has a SPEC-CORRECT representation — `status: enrichment_eligible` + pending_class + maturity_window_tics (SKILL Step-7) — and a NON-SPEC one — `status: deferred`. They are NOT interchangeable, because `deferred` is a status the READERS DISAGREE ON: it is TERMINAL in `bench-packet-prep.load_queue` and `review-promote-writeback._TERMINAL_STATUSES`, but ACTIVE in `queue_state_compile` (ACTIVE_STATUSES). This is the Terminal-State Valve Pattern with the valve pointed at the wrong entry: load_queue's "latest TERMINAL entry is canonical" rule means a single historical `deferred` row OUT-VOTES every later active/re-activated row — and because the queue is append-only the poisoning row cannot be removed, so even a correct re-activation (`deferred → enrichment_eligible` + elapsed re_eval_tic) cannot un-mask the item by append. The same item stays LIVE to the compiler and to /review's documented direct queue read, so the failure is SILENT and READER-DEPENDENT — the card-catalog (a load_queue reader) and the library (the compiler) disagree on a single id, and the disagreement is the evidence of stale state (Disagreement-as-evidence). TWO compounding roots, two cures (either closes it; both is belt-and-suspenders): (1) GENERATOR — the DEFER verdict path must write the spec status `enrichment_eligible`, NEVER the divergent `deferred`; a status some readers terminalize and others don't is a latent sticky-mask. (2) READER — bench-packet's `pending_cogprs` is built from raw `load_queue`, VIOLATING bench-packet's own tic-222 contract ("bench-packet-prep MUST consume effective_state outputs as the state source rather than reading raw queue rows directly"); deriving pending from the compiler's `effective_state.live_now` would make all readers agree and surface the re-activated item. DOGFOODED at /review 522: the two Mogul-audit DEFERs this pass were written `enrichment_eligible` (re_eval 523), not `deferred`, exercising cure (1); the reader fix is backlogged (`bk-benchpacket-pending-from-effective-state`).

<!-- promoted from cpr_defer_status_deferred_vs_enrichment_eligible_reader_divergence_tic521 (tic 521→/review 522 PROMOTE-as-refinement, Architect-gated [AskUserQuestion approval]). Source: audit-logs/governance/borns-tic521-defer-status-deferred-vs-enrichment-eligible-reader-divergence.md. Refines Terminal-State Valve Pattern (a status readers disagree on lets a historical row out-vote later rows; prefer-terminal becomes the bug when the terminal status is non-spec) + composes Conductor-Score-Runtime-Parity-CGG + Inline-Tracked-CogPR-DEFER-Step-7 + federation Disagreement-as-evidence + State-agreement-is-not-truth-unless-lifecycle-reachable. Reader fix backlogged bk-benchpacket-pending-from-effective-state. Band: COGNITIVE. signer ent_homeskillet-c48. -->

---
