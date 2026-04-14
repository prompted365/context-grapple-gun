---
name: podcast-conductor
description: "Full system guide for the podcast longform-to-shortform pipeline. Read this first — it maps every skill, agent, router, schema, and dependency in the editorial intelligence system."
user-invocable: true
model: opus
tools: Read, Write, Edit, Glob, Grep, Bash, Agent, WebSearch, WebFetch
---

# /podcast-conductor

This is the system manual for the podcast editorial intelligence pipeline. If you are the lead agent running a pipeline session, read this before `/podcast-pipeline`. If you are a subagent, your spawning prompt tells you what to do — but this document explains *why* and *how everything fits together*.

## System Map

### Two Governing Lanes

Every pipeline run is governed by two parallel truth lanes:

```
1. Local Transcript Verification Gate
   → establishes section-local lexical and timing truth
   → "what is actually being said here, exactly, and where?"

2. Overshoot Visual Adjudication Layer
   → establishes visual and stylistic truth across source, generated, and assembled artifacts
   → "what is visually happening here, what should be done with it, and did the resulting assets stay true to intent and canon?"
```

Together they govern whether the pipeline is reasoning over the right material before AND after transformation.

```
SKILLS (editorial intelligence)
├── /podcast-conductor     ← YOU ARE HERE. System guide. Read-first.
├── /podcast-pipeline      ← Team orchestrator. Entry point for runs.
├── /show-profile-manager  ← Profile CRUD. Show identity layer.
├── /audience-context-researcher  ← Runtime platform intel.
├── /transcript-scorer     ← Editorial judgment scoring.
├── /edit-decision-list    ← Audio-first EDL with J/L cut intentions.
├── /broll-prompt-engineer ← Scene-aware b-roll + router envelopes.
├── /caption-semantic-layer ← Two-tier captions with no-double gate.
├── /post-copy-generator   ← Platform copy from inside the show voice.
└── /pipeline-report       ← HTML report + conversational surface.

INFRASTRUCTURE
├── fal_router.py          ← Media generation egress (fal.ai)
│   ├── submit / subscribe / status / result
│   ├── budget enforcement (cap + window + per-job max)
│   └── completion events → audit-logs/media-router/completions/
│
├── overshoot_router.py    ← Visual Adjudication Layer (Overshoot)
│   ├── CLI: analyze / status / results / models / presets / budget / profile
│   ├── 3 responsibility surfaces:
│   │   ├── source: visual hinges, face-priority windows, reaction moments, edit grammar
│   │   ├── generated: style/intent/likeness fidelity, quality, additive vs decorative
│   │   └── draft: pacing, transitions, b-roll continuity, arc expression, caption sync
│   ├── 3 structured presets: source_assessment / generated_assessment / draft_review
│   ├── streaming via Overshoot SDK (FileSource + realtime pacing)
│   ├── default model: qwen3.5-9b (medium tier)
│   └── NOT the generation engine — the visual authority that governs when
│       generation is justified and whether generated outputs are acceptable
│
├── profiles/              ← Show profile JSON files (per-project)
│   └── {show-slug}.profile.json
│
└── output/{show_slug}/    ← Pipeline run artifacts (per-run)
    ├── *-scoring.json
    ├── *-selection.json
    ├── *-edl.json
    ├── *-broll-prompts.json
    ├── *-captions.json
    ├── *-cut-audit.json
    ├── *-post-copy.json
    ├── *-audience-context.json
    ├── *-report.html
    └── envelopes/         ← Router-ready fal.ai dispatch envelopes
        └── broll_slot_{N}.json
```

## The Three Intelligence Layers

Every decision in this pipeline flows through three layers that must be loaded before work begins:

### Layer 1: Profile (stable)
The show's permanent creative worldview. Set once via `/show-profile-manager create`. Rarely changes. Contains: mission, audience tribe, aesthetic invariants, editorial voice, growth scoring weights, anti-patterns, platform stack.

**A profile is not a settings file. It is a creative worldview.** The pipeline should be able to ask "what would this show do?" and answer from the profile alone.

### Layer 2: Creative (semi-stable)
A specific output configuration within a profile. One creative = one output type (Reel, Story, Short). Inherits from profile but can override: ratio, caption style, hook style, b-roll direction, copy tone, platform target, video gen tool.

### Layer 3: Audience Context (runtime, fresh)
Live platform intelligence built by `/audience-context-researcher` at the start of every run. Never persisted. Contains: current demographics, algorithm behavior, format conventions, aesthetic trust signals, trend signals, scoring implications.

**These three layers assemble into a fully grounded editorial intelligence before the transcript is ever touched.**

## How Skills Chain

Each skill reads from and writes to `./output/{show_slug}/`. The dependency chain is enforced by the orchestrator (`/podcast-pipeline`) which spawns subagents in the correct order.

### Skill → Reads → Writes

| Skill | Reads | Writes |
|-------|-------|--------|
| `/show-profile-manager` | user input | `profiles/{slug}.profile.json` |
| `/audience-context-researcher` | profile, creative | `audience-context.json` |
| `/transcript-scorer` | transcript, profile, creative, audience-context | `scoring.json` |
| Lead (segment selection) | scoring.json | `selection.json` |
| `/edit-decision-list` | selection, profile, creative, audience-context | `edl.json` |
| `/broll-prompt-engineer` | edl, profile, creative, audience-context | `broll-prompts.json` + `envelopes/*.json` |
| `/caption-semantic-layer` | edl, selection, scoring, profile, creative | `captions.json` |
| Visual adjudication | generated media, assembled draft | `adjudication-*.json` (via overshoot_router.py) |
| Cut auditor | edl, broll-prompts, captions, adjudication | `cut-audit.json` |
| `/post-copy-generator` | selection, scoring, edl, profile, creative, audience-context | `post-copy.json` |
| `/pipeline-report` | ALL prior outputs | `report.html` |

### Parallel Opportunities

These pairs have no dependency on each other and can run simultaneously:
- **Phase 1**: audience research + transcript ingest
- **Phase 5**: b-roll prompts + caption layer
- **Phase 7**: post copy + report assembly (if post copy finishes first, report can incorporate it)

### Dependency Gates

These stages MUST wait:
- Scoring waits for BOTH audience context AND transcript
- EDL waits for segment selection
- B-roll AND captions both wait for EDL
- Cut audit waits for EDL + b-roll + captions (it reviews the composite)
- Report waits for everything

## Subagent Briefing Protocol

When `/podcast-pipeline` spawns a subagent, the prompt must be **self-contained**. Subagents don't see the lead's conversation history. Every subagent prompt must include:

1. **Role**: what this agent is doing and why
2. **Skill reference**: which `/skill` protocol to follow
3. **Input data**: the actual JSON content from prior stages (not file paths — the agent may not have the same working directory)
4. **Profile**: the full show profile JSON
5. **Creative**: the active creative config
6. **Audience context**: the runtime intelligence object (if available at this phase)
7. **Output instructions**: exact file path to write, exact schema to follow
8. **Model constraint**: "You are running as Opus/Sonnet. No Haiku anywhere in this pipeline."

### Example subagent prompt (transcript-scorer):

```
You are the transcript scorer for the podcast editorial pipeline.

## Your Role
Read this transcript and score segments for shortform growth potential.
Follow the /transcript-scorer protocol exactly.

## Profile
{full profile JSON}

## Active Creative
{creative config JSON}

## Audience Context
{audience context JSON from Phase 1a}

## Transcript
{full transcript text with timestamps}

## Output
Write your scoring output as JSON to: ./output/{show_slug}/{date}-{creative}-scoring.json
Follow the schema defined in /transcript-scorer.

## Model
You are running as Opus. Editorial judgment is your primary operation.
Never delegate to Haiku for any part of this work.
```

## Media Router Guide

### Location
`canonical_developer/context-grapple-gun/cgg-runtime/scripts/media-router/fal_router.py`

### Environment
FAL_KEY is in `canonical/.env`. The router reads it automatically.

### Models Available

| Model | Router Key | fal.ai ID | Type | Input |
|-------|-----------|-----------|------|-------|
| Nano Banana 2 | `nano-banana-2` | `fal-ai/nano-banana-2` | image | prompt + aspect_ratio + resolution |
| Kling v3 Pro i2v | `kling-v3-pro-i2v` | `fal-ai/kling-video/v3/pro/image-to-video` | video | start_image_url + prompt + duration |
| Seedance 2.0 i2v | `seedance-2.0-i2v` | `bytedance/seedance-2.0/image-to-video` | video | start_frame + prompt + duration |
| Seedance 2.0 r2v | `seedance-2.0-r2v` | `bytedance/seedance-2.0/reference-to-video` | video | image_urls[] + video_urls[] + prompt |

Seedance r2v accepts up to 9 reference images, 3 reference videos, and 3 audio clips. Use with `extract-frames` to build the reference array from source video.

Kling v3 Pro accepts an optional `elements` param for @Element custom identity anchors — use this for likeness preservation when generating scenes featuring real people (guest/host).

### Envelope Format

```json
{
  "model": "nano-banana-2",
  "params": {
    "prompt": "string",
    "aspect_ratio": "9:16",
    "resolution": "1K",
    "num_images": 1
  },
  "pipeline_context": {
    "slot": 1,
    "step": "reference_frame",
    "edl_beat": 2
  }
}
```

### CLI Commands

```bash
# Check remaining budget
python3 fal_router.py budget

# Set budget controls
python3 fal_router.py budget set --cap 50 --window 48 --max-job 10

# Submit async (returns job ID)
python3 fal_router.py submit envelope.json

# Submit and wait (blocks)
python3 fal_router.py subscribe envelope.json

# Check job status
python3 fal_router.py status fal_abc123

# Get result (blocks until done)
python3 fal_router.py result fal_abc123

# Extract reference frames from source video (for r2v workflows)
python3 fal_router.py extract-frames <source_video> --count 8 --output-dir ./output/ref-frames [--start 10.5] [--end 25.0]
```

### Budget Enforcement (physics layer)

The router blocks dispatch when:
- Single job estimated cost > `max_single_job_usd` ($5 default)
- Total window spend + job cost > `cap_usd` ($25 default)
- Window auto-resets after `window_hours` (24h default)

Budget state: `audit-logs/media-router/budget.json`
Job records: `audit-logs/media-router/jobs/{job_id}.json`
Completion events: `audit-logs/media-router/completions/{job_id}.json`

### Two-Step Pattern (most common)

Most b-roll slots need a reference image first:
1. `nano-banana-2` → generates start frame ($0.08, ~10s)
2. `seedance-2.0-i2v` or `kling-v3-pro-i2v` → animates it ($0.56-1.50 for 5s)

The b-roll prompt engineer handles this — it writes two envelopes per slot when needed, with `step: "reference_frame"` and `step: "video_generation"` marked in pipeline_context.

### Cost Reference

| Operation | Cost |
|-----------|------|
| 1 reference image (1K) | $0.08 |
| 5s Kling video (no audio) | $0.56 |
| 5s Kling video (with audio) | $0.84 |
| 10s Kling video (with audio) | $1.68 |
| 5s Seedance video | $1.51 |
| 10s Seedance video | $3.02 |
| 5s Seedance r2v video | $1.51 |
| 10s Seedance r2v video | $3.02 |
| Full 4-slot run (image + 5s Kling each) | ~$2.56 |
| Full 4-slot run (image + 5s Seedance each) | ~$6.36 |

## Quick Start

### First time — create a profile:
```
/show-profile-manager create
```

### Run the full pipeline:
```
/podcast-pipeline
```
(Follow prompts — provide transcript, approve segment selection, approve b-roll budget)

### Run individual stages:
```
/transcript-scorer          # Just score a transcript
/edit-decision-list         # Just build an EDL from a selected segment
/broll-prompt-engineer      # Just craft b-roll prompts from an EDL
/caption-semantic-layer     # Just build captions from an EDL
/post-copy-generator        # Just write post copy
/audience-context-researcher # Just research a platform
```

### Manage media budget:
```bash
python3 fal_router.py budget              # View
python3 fal_router.py budget set --cap 50 # Adjust
python3 fal_router.py budget reset        # Reset window
```

## Overshoot Visual Adjudication Layer

Overshoot is not a step in the pipeline — it is a governing lane. It appears three times, as one authority operating over different artifact states:

### Pipeline Touchpoints

```
source media
→ local transcript verification
→ Overshoot source analysis (Phase 1d)
→ editorial decision
→ optional generation / augmentation
→ Overshoot generated-asset evaluation (Phase 5d)
→ assembly
→ Overshoot draft evaluation (Phase 6b)
→ final audit / delivery
```

### Responsibility Surfaces

**1. Source footage assessment** (Phase 1d, preset: `source_assessment`)
- Visual hinge detection — moments where visual energy shifts
- Face-priority windows — well-lit, in-focus, emotionally expressive segments
- Interruption-safe windows — where cutting to b-roll won't disrupt flow
- Reaction moments — visible reactions from the non-speaking person
- Edit grammar suggestions — J-cut and L-cut points from visual energy

**2. Generated asset assessment** (Phase 5d, preset: `generated_assessment`)
- Style fidelity — does it match the show's visual language?
- Intent fidelity — does it serve editorial meaning, not just illustrate?
- Likeness / identity fidelity — if a person is depicted, does it preserve their identity?
- Semantic relevance — is the asset connected to what's being said?
- Quality / coherence / artifact detection — technical quality check
- Whether asset is additive or decorative — does it add meaning or is it wallpaper?

**3. Draft-level assessment** (Phase 6b, preset: `draft_review`)
- Pacing coherence — does the rhythm serve the content?
- Transition coherence — do visual transitions serve the arc?
- B-roll continuity — is generated imagery continuous or fragmented mid-motion?
- Visual overreach / underreach — too much or too little visual support?
- Arc expression — does the final edit still express the intended emotional arc?
- Caption sync — are captions timed to speech?

### Non-Goal

Overshoot is not the generation engine. It is the visual authority that governs when generation is justified and whether generated outputs are acceptable.

### CLI

```bash
# Source analysis
python3 overshoot_router.py analyze <video_path> --preset source_assessment

# Generated asset evaluation
python3 overshoot_router.py analyze <asset_path> --preset generated_assessment

# Draft review
python3 overshoot_router.py analyze <draft_path> --preset draft_review

# Resolve a show profile for adjudication context
python3 overshoot_router.py profile <show-slug>
```

### Processing Presets

| Preset | FPS | Clip Length | Delay | Max Tokens | Use |
|--------|-----|------------|-------|------------|-----|
| snappy | 6 | 0.5s | 0.5s | 64 | Triage |
| balanced | 6 | 1.0s | 1.0s | 128 | Default |
| detailed | 10 | 2.0s | 1.5s | 192 | Deep analysis |

### Model Tier Guidance

- **medium** (qwen3.5-9b) — default for source and generated assessment. Fast, strong vision.
- **large** (qwen3.5-27b) — use for draft review. Best quality for final editorial judgment.
- **small** (qwen3.5-4b) — use for high-volume triage only.

## Transcript Verification Gate

The transcript verification gate is the pipeline's parallel truth lane for lexical and timing accuracy.

### Purpose
Establish section-local lexical and timing truth before any editorial decision is made. Auto-transcription tools (Whisper, Descript, etc.) produce timestamps that drift 3-5 seconds from actual audio position.

### Staged Verification
1. **Ingest** — raw transcript with auto-generated timestamps
2. **Re-align** — compare word boundaries and speaker turns against audio waveform peaks
3. **Confirm** — verify timing accuracy against audio; flag drift magnitude

### Output
A verified transcript with a `drift_correction_applied` field indicating whether timestamps were adjusted and by how much.

### Relationship to Overshoot
Together, transcript verification and the Overshoot Visual Adjudication Layer govern whether the pipeline is reasoning over the right material. Transcript verification handles the lexical/timing truth ("what is being said, when"); Overshoot handles the visual truth ("what is being shown, how does it serve the message").

## What This System Is Really Doing

The goal is not automation. The goal is an agent team that has **taste** — that can feel where the electricity is in a transcript, understand why a J-cut works emotionally, write a b-roll prompt that serves meaning rather than illustration, and generate post copy that sounds like the show, not a social media manager.

The three-layer intelligence architecture (profile + creative + audience context) is what makes this possible. A generic AI can clip a transcript. This system knows the show's soul, the platform's current behavior, and the craft of editing — and holds all three simultaneously while making every decision.

The profile is the identity. The audience context is the world. The craft skills are the hands. The orchestrator is the judgment that binds them.
