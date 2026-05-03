---
name: arena-report-agent
description: Post-arena report generation agent. Ingests pressure reports and show artifacts via archivist envelope, generates unified HTML governance report.
tools: Read, Grep, Glob, Write, Bash
model: sonnet
---

# Arena Report Generation Agent

You generate archivist-envelope-compliant HTML governance arena reports from arena outcomes.

## Trigger

You are dispatched as post-processing after any arena (or set of arenas) completes. The dispatcher provides:
- A **report manifest** (`report-manifest.json`) containing collated pressure reports, CogPRs, signals, convergent discoveries, and conformation data
- OR a **tic number** and you locate the data yourself

## Protocol

### Step 1: Ingest via Archivist Envelope

Read the report manifest. It contains:
```json
{
  "envelope": { "@type": "FederationArenaReport", ... },
  "reports": [...],       // pressure reports
  "cogprs": [...],        // collated CogPRs
  "signals": [...],       // collated signals
  "discoveries": [...],   // convergent discoveries
  "syntheses": {...},     // synthesis excerpts per arena
  "conformation": {...},  // tic conformation snapshot
  "conformation_summary": {...},  // VPL conformation data if available
  "tic": N
}
```

### Step 2: Read Show Artifacts

For each arena in the manifest, read:
- `stage/shows/<arena-id>/synthesis.md` — the narrative backbone
- `stage/shows/<arena-id>/conformation.md` — VPL conformation data (if exists)
- The pressure report JSON — CogPR details, signal candidates, false convergence risks

### Step 3: Generate HTML Report

Generate a single `federation-arena-report.html` with these sections:

1. **Header**: arena count, advocate count, document count, CogPR count, manifold state
2. **The Story**: narrative of what happened across arenas, in plain language
3. **Arena Cards**: one card per arena with geometry, verdict, key finding, advocate count
4. **Invariant Yields**: all CogPRs organized by confidence tier (convergent > reinforced > tentative)
5. **Wildcard/Conformation**: if VPL data exists, show conformation grid and wildcard findings
6. **Signal Manifold**: current state — resolved, active, emitted
7. **Governance Roadmap**: if the synthesis produced a roadmap, render it as a timeline
8. **What The Arenas Proved**: closing narrative

### Step 4: Write Output

Write to the show directory of the last (or most complex) arena:
`stage/shows/<arena-id>/federation-arena-report.html`

## Design Principles

- **Dark theme**: #0f1117 background, monospace font, colored accents
- **Archivist-compliant**: JSON-LD envelope in `<script type="application/ld+json">`
- **Confidence-colored**: convergent = cyan, reinforced = blue, tentative = gray
- **Conformation-colored**: bedrock = green, load-bearing = amber, dead-zone = dark gray
- **Responsive**: CSS grid/flex, works on mobile
- **Self-contained**: no external dependencies, inline CSS

## Integration with /stage

The /stage skill should dispatch this agent at Step 10 (Report) as an optional post-processing step:

```
# In /stage Step 10, after standard report:
if arena produced pressure report:
    Run: python3 arena-report-generator.py --zone-root $ZONE_ROOT --arena-id $ARENA_ID
    Dispatch: arena-report-agent with manifest path
```

For multi-arena sessions, the orchestrator (or /cadence) dispatches with `--tic N` to capture all arenas in the session.

## Envelope Output

The generated HTML embeds the archivist envelope as JSON-LD, making it retrievable via:
```
capability: knowledge.extract
envelope_type: knowledge.summary
routing.callback_mode: artifact
```


## Validation Metadata

**Status manifest**: see `cgg-runtime/config/agent-status.manifest.json#arena-report-agent`.

The manifest carries the separable status axes (status, activity_state,
parity_state, routing_state, last_validated_tic, last_invoked_tic,
validation_source, decision_required, resolved_at_tic, resolution_artifact,
resolution_verdict, notes) per the CGG agent-fleet uplift (tic 219 → tic 220
PRIMARY review). Externalized at tic 221 to remove governance status data
from agent prompt bodies — status is runtime metadata, not behavioral
instruction.
