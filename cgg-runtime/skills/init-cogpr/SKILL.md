---
name: init-cogpr
description: Install CGG v3 signal conventions — CogPR + Siren + Warrant block formats, band budget, /grapple integration. Manual-only.
user-invocable: true
disable-model-invocation: true
---

# /init-cogpr v3 — Install Signal Manifold Conventions

This skill installs the CGG v3 (Context Grapple Gun — Signal Manifold) conventions into the current project, enabling the full signal lifecycle: CogPR flags, Siren signals, Warrants, and the `/grapple` + `/siren` review workflow.

## What It Creates/Updates

### Creates

| File | Purpose |
|------|---------|
| `.claude/skills/grapple/SKILL.md` | `/grapple` v3 — unified CogPR + Warrant docket reviewer |

### Updates

| File | Change |
|------|--------|
| `CLAUDE.md` | Add unified signal schema (all 3 block formats), band budget hierarchy, signal capture rules, warrant recognition rules |

### Optional

| File | Purpose |
|------|---------|
| `.claude/skills/cogpr-status/SKILL.md` | `/cogpr-status` v3 — print CogPR count + signal count + warrant count |

## Installation Steps

### Step 1: Create `/grapple` v3 skill

Write `.claude/skills/grapple/SKILL.md` (or verify existing is v3) with:
- `user-invocable: true`
- Two-section docket: Section A (Warrant Triage) + Section B (CogPR Review)
- Harmonic triad detection (auto-promoted to top of docket)
- Check `~/.claude/grapple-proposals/latest.md` first (precomputed proposals)
- Scan for `<!-- --agnostic-candidate -->` flags AND `audit-logs/signals/*.jsonl` active signals/warrants
- Inline tick logic for active signals (volume accrual, TTL, warrant minting)
- Warrant verdicts: ACKNOWLEDGE / DISMISS / ESCALATE
- CogPR verdicts: PROMOTE / SKIP / MODIFY
- Log all decisions to `~/.claude/grapple-meta-log.jsonl`
- Protected files require extra confirmation (`~/.claude/CLAUDE.md`, `[GLOBAL_INVARIANT]`)
- References `/siren` as the operational companion for day-to-day signal management

### Step 2: Add unified signal schema to CLAUDE.md

Add to the Session Learning Protocol section all 3 block formats:

**CogPR block** (`<!-- --agnostic-candidate -->`):
```html
<!-- --agnostic-candidate
  lesson: "one-line lesson summary"
  source_date: "YYYY-MM-DD"
  source: "file:line"
  band: "COGNITIVE"
  motivation_layer: "COGNITIVE"
  subsystem: "ecotone"
  recommended_scopes:
    - "path/to/broader/CLAUDE.md"
  rationale: "why this is broader than local"
  review_hints: "what to check when evaluating"
  civilization_prior_refs:
    - "Aesop: ..."
  status: "pending"
-->
```

Required fields (v3): `band`, `motivation_layer`, `subsystem`, `source` (was implicit in v2).

**Siren block** (`<!-- --signal -->`):
```html
<!-- --signal
  id: "sig_YYYY-MM-DDTHH:MMZ_subsystem_event"
  kind: "BEACON"
  band: "PRIMITIVE"
  motivation_layer: "PRIMITIVE"
  source: "file:line"
  source_date: "YYYY-MM-DD"
  subsystem: "ruvector"
  volume: 42
  volume_rate: 12
  max_volume: 100
  ttl_hours: 24
  hearing_targets:
    - actor: "mogul"
      threshold: 50
    - actor: "homeskillet"
      threshold: 80
  escalation:
    warrant_threshold: 80
    warrant_id: ""
  payload:
    signature: "descriptive_string"
    suggested_checks:
      - "verify X"
    links:
      - "path/to/relevant/file"
  status: "active"
  last_tick_at: ""
  tick_count: 0
-->
```

**Warrant block** (`<!-- --warrant -->`):
```html
<!-- --warrant
  id: "wrn_YYYY-MM-DDTHH:MMZ_subsystem"
  source_signal_ids:
    - "sig_..."
  minting_condition: "volume_threshold"
  band: "PRIMITIVE"
  motivation_layer: "PRIMITIVE"
  priority: 1
  source_date: "YYYY-MM-DD"
  subsystem: "ruvector"
  scope: "estate"
  target_actors:
    - "homeskillet"
    - "mogul"
  payload:
    summary: "what happened"
    action_required: "what to do"
  status: "active"
  acknowledged_by: ""
  acknowledged_at: ""
  dismissed_at: ""
-->
```

### Step 3: Add Band Budget Hierarchy to CLAUDE.md

| Band | dB Equiv | Propagation | Governance |
|------|----------|-------------|------------|
| PRIMITIVE | 0 dB (foreground) | Always audible. Never fully muffled. | Required for safety/survival signals |
| COGNITIVE | -6 dB (midground) | Moderate. Standard working level. | Default band for lessons and insights |
| SOCIAL | -12 dB (background) | Suppressed. High muffling. | Collaboration signals only |
| PRESTIGE | auto-muted | Auto-decay. Blocked by governance filter. | NEVER optimized for (CANON_INDEX rule) |

Distance model: `effective_volume = volume - (directory_hops * muffling_per_hop)`, default `muffling_per_hop = 5`.

### Step 4: Add signal capture rules to Session Learning Protocol

Document when to emit each primitive:
- **CogPR**: durable lesson, cross-scope applicability, needs governance review
- **Siren**: persistent condition, accumulating pressure, needs attention/monitoring
- **Warrant**: minted automatically — volume threshold crossed, harmonic triad detected, or circuit breaker tripped

### Step 5: (Optional) Create `/cogpr-status` v3 skill

Write `.claude/skills/cogpr-status/SKILL.md`:
- `user-invocable: true`
- Scans project for pending CPR flags
- Scans `audit-logs/signals/*.jsonl` for active signals and warrants
- Checks `~/.claude/grapple-proposals/latest.md` for pending proposals
- Prints summary:
  ```
  CGG v3 Status:
  - Pending CPR flags: N
  - Active signals: M
  - Active warrants: K
  - Harmonic triads: T
  - Last handoff processed: <id> (<date>)
  - Proposals waiting: Y/N
  - /grapple for full docket | /siren for signal dashboard
  ```

### Step 6: Verify

- Confirm all 3 block format schemas are documented in CLAUDE.md
- Confirm `band` and `motivation_layer` are listed as required fields on all primitives
- Confirm `/grapple` appears in available skills (or verify existing is v3)
- Confirm band budget hierarchy is documented with PRESTIGE blocking rule
- (If created) Confirm `/cogpr-status` appears in available skills

Report results to user.
