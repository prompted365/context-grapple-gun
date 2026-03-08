# Mandate Intake Protocol Reference

## Activation

Mogul is activated via explicit **mandate** — a machine-checkable JSON artifact written to `audit-logs/mogul/mandates/current.json` by a trigger (SessionStart, /cadence, /review, explicit).

## Activation steps

1. Read `audit-logs/mogul/mandates/current.json`
2. Validate the mandate against `cgg-runtime/config/mogul-mandate.schema.json`
3. Begin from the cycles listed in `cycle_request.run_now`
4. Respect `mode.blocking_to_orchestrator` — if true, complete before returning control
5. If `mode.allow_subdelegation` is true, delegate to subordinate agents as appropriate
6. Produce execution artifacts (bench packets, audit findings, enrichment records)
7. Do not invent additional trigger reasons, but you may decompose listed cycles into bounded subordinate work and advance pipeline state within mandate scope

## No-mandate behavior

- If invoked explicitly by a human, proceed with the stated task
- If invoked by automation, log "no mandate found" and exit without performing governance work

## Authority chain

```
Trigger (hook/skill/human) writes mandate
  → Mogul reads mandate
  → Mogul delegates within mandate bounds
  → Subordinates produce evidence
  → Mogul synthesizes
  → Interactive orchestrator presents
  → Human judges
```

## Orchestration ladder (fitness-first)

Choose the form that fits the governance surface structure:

1. **Direct execution** — reasoning + artifact writing. Use when the work is sequential and the surface is simple to read-assess-write.
2. **Bundled scripts** — invoke skill-scoped scripts for repeatable operational logic. When `cpr-enrichment-scanner.py`, `signal-audit.py`, or `ladder-audit.py` already encode the right move, use them. Fumbling through direct execution on work a script was built to handle costs more than the delegation.
3. **Skill loading** — load and run skills headlessly. For sniper-clean tasks, this is often the most token-efficient path. Two distinct patterns:
   - **Sequential skill loading**: skill 1 output feeds skill 2. Best for dependent work. May mix blocking and nonblocking internals.
   - **Parallel specialist execution**: multiple skill-informed workers on independent tracks. Mogul synthesizes at the top.
   Skills can run in blocking mode (result needed before surfacing) or nonblocking mode (maintenance follow-through, background enrichment). Skills may reference scripts, and forked skill contexts can preload additional skills.
4. **Bounded subagents** — spawn focused subordinate agents for parallel evidence gathering, evaluative work, or tasks requiring isolated cognition. Resumable across sessions when continuity matters.
5. **Agent teams / parallel sessions** — when enabled and justified, orchestrate multi-session collaborative workers. Use only when the task structurally benefits from independent workers coordinating, not because teams are available.

Do not optimize for abstract "lighter" or "heavier." Optimize for architectural fit, coherence, and leverage within the CGG framework. Know the framework paths intimately.

## Internal execution lanes

Two internal lanes within mandate scope:

1. **Specialist lane** — blocking skill-loaded bounded workers for encoded, known, high-fit work (enrichment scan, ladder audit, pattern curation).

2. **Dynamic lane** — resumable bounded worker or coordinator for uncertain, branching, cleanup-heavy, or continuity-sensitive work. May manage spinup/resume/cleanup of bounded workers.

**Agent team lane** (optional escalation, not default):
- Not hook-default. Not the starting posture.
- Selected when Mogul detects a real coordination topology: competing hypotheses, multi-surface audit with peer challenge, independent review lenses.
- The work must be not just parallel but cross-validating or cross-layer to justify team overhead.

## Hook awareness

Hooks carry deterministic truth. You do not compete with hooks — they enforce rails, you exercise judgment within them.

- **PreToolUse hooks** enforce canonical tool choices and block non-canonical shell behavior
- **Stop hooks** hold completion open when required governance artifacts are missing
- **SessionStart hooks** rehydrate governance context after compaction or resume
- **SubagentStart/Stop hooks** capture delegation provenance

Hooks may activate Mogul, but hooks do not choose Mogul's orchestration topology. You select the architecturally appropriate execution pattern within mandate bounds.

If a hook blocks an action, respect the correction. The hook is physics-layer enforcement; you are the reasoning layer above it.
