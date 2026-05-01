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
    ├── *-evidence-scaffold.json   ← Phase 0b: shared retrieval seed
    ├── *-evidence-surface.json    ← Checkpoint A: committed evidence plane
    ├── *-audience-context.json
    ├── *-transcript-parsed.json
    ├── *-transcript-verified.json
    ├── *-source-analysis.json     (conditional)
    ├── *-scoring.json
    ├── *-selection.json           (includes editorial_thesis, trade_offs)
    ├── *-edl.json
    ├── *-broll-prompts.json
    ├── *-captions.json
    ├── *-adjudication.json
    ├── *-cut-audit.json
    ├── *-draft-review.json        (conditional)
    ├── *-post-copy.json
    ├── *-report.html
    ├── envelopes/         ← Router-ready fal.ai dispatch envelopes
    │   └── broll_slot_{N}.json
    └── assembly/          ← Locked base track + extracted frames
        ├── base_track_v3.wav
        ├── base_track_v3.json
        └── slot_N_*.png
```

## The Intelligence Stack

Every decision in this pipeline flows through four layers. The first three establish identity and context. The fourth commits evidence before reasoning begins.

### Layer 1: Profile (stable)
The show's permanent creative worldview. Set once via `/show-profile-manager create`. Rarely changes. Contains: mission, audience tribe, aesthetic invariants, editorial voice, growth scoring weights, anti-patterns, platform stack.

**A profile is not a settings file. It is a creative worldview.** The pipeline should be able to ask "what would this show do?" and answer from the profile alone.

### Layer 2: Creative (semi-stable)
A specific output configuration within a profile. One creative = one output type (Reel, Story, Short). Inherits from profile but can override: ratio, caption style, hook style, b-roll direction, copy tone, platform target, video gen tool.

### Layer 3: Audience Context (runtime, fresh)
Live platform intelligence built by `/audience-context-researcher` at the start of every run. Never persisted. Contains: current demographics, algorithm behavior, format conventions, aesthetic trust signals, trend signals, scoring implications.

### Layer 4: Evidence Surface (runtime, committed)
The canonical evidence plane committed at Checkpoint A after all Phase 1 discovery completes. Contains references to all gathered evidence (verified transcript, audience context, source analysis), declares what is NOT available (evidence gaps), and assigns retrieval rights per downstream lane. Every Phase 2+ agent receives this surface — it ensures all agents reason from the same committed evidence basis.

**These four layers assemble into a fully grounded editorial intelligence. Layers 1-3 establish identity and context. Layer 4 commits the evidence plane before reasoning begins.**

## How Skills Chain

Each skill reads from and writes to `./output/{show_slug}/`. The dependency chain is enforced by the orchestrator (`/podcast-pipeline`) which spawns subagents in the correct order.

### Skill → Reads → Writes

| Skill | Reads | Writes |
|-------|-------|--------|
| Lead (profile load) | profiles dir | `profile_loaded.json` |
| Lead (evidence scaffold) | profile, creative, source paths | `evidence-scaffold.json` |
| `/audience-context-researcher` | scaffold, profile, creative | `audience-context.json` |
| Lead (transcript ingest+verify) | source file, scaffold | `transcript-parsed.json`, `transcript-verified.json` |
| Lead (Checkpoint A) | scaffold, audience-context, verified transcript | `evidence-surface.json` |
| `/transcript-scorer` | evidence-surface, transcript, profile, creative, audience-context | `scoring.json` |
| Lead (segment selection) | scoring.json | `selection.json` (with editorial_thesis, trade_offs) |
| `/edit-decision-list` | selection, verified transcript, scaffold, profile, creative, audience-context | `edl.json` |
| `/broll-prompt-engineer` | edl, scaffold, profile, creative, audience-context | `broll-prompts.json` + `envelopes/*.json` |
| `/caption-semantic-layer` | edl, selection, scoring, profile, creative | `captions.json` |
| Visual adjudication | generated media, assembled draft | `adjudication.json` (via overshoot_router.py) |
| Cut auditor | edl, broll-prompts, captions, adjudication, **verified transcript**, evidence-surface, selection | `cut-audit.json` |
| `/post-copy-generator` | selection, scoring, edl, profile, creative, audience-context | `post-copy.json` |
| `/pipeline-report` | ALL prior outputs + evidence-scaffold + evidence-surface | `report.html` |

### Parallel Opportunities

These pairs have no dependency on each other and can run simultaneously:
- **Phase 1**: audience research + transcript ingest
- **Phase 5**: b-roll prompts + caption layer
- **Phase 7**: post copy + report assembly (if post copy finishes first, report can incorporate it)

### Dependency Gates

These stages MUST wait:
- Scoring waits for BOTH audience context AND verified transcript (via Checkpoint A evidence surface)
- EDL waits for segment selection (which now includes editorial thesis and trade-offs)
- B-roll AND captions both wait for timeline-locked EDL
- Cut audit waits for EDL + b-roll + captions + adjudication (it reviews the composite with adversarial retrieval rights)
- Report waits for everything

## Retrieval Architecture

The pipeline implements a hybrid retrieval pattern: shared seed first, then lane-local augmentation, then checkpoint before downstream reasoning.

### The Organizing Invariant

> Do not organize by who gets to retrieve. Organize by what evidence must be shared before the next reasoning layer is allowed to become real.

### Retrieval Shape

```
Phase 0b: Shared Retrieval Seed (evidence scaffold)
  Profile identity + common constraints + load-bearing context + retrieval rights map
  → committed before any agent spawns

Phase 1: Lane-Local Discovery (parallel)
  1a: External discovery — audience research (retrieval: EXPECTED)
  1b: Internal file read — transcript ingest (retrieval: EXPECTED)
  1c: Tool verification — transcript + audio comparison (retrieval: EXPECTED)
  1d: External tool — Overshoot source analysis (retrieval: EXPECTED)

Checkpoint A: Evidence Surface Commit
  Canonical evidence plane — all Phase 2+ agents reason from this
  → verified transcript + audience context + source analysis + evidence gaps

Phase 2-4: Specialized Reasoning (synthesis from committed evidence)
  2: Scoring (retrieval: GAP-FILL — may re-read transcript sections)
  3: Selection (lead inline — commits editorial thesis + trade-offs)
  4: EDL (retrieval: GAP-FILL — may re-read verified transcript)

Phase 4b: Timeline Lock Checkpoint
  Verifies EDL grounding against actual base track
  → prevents phantom references from cascading into generation

Phase 5: Execution + Generation (committed evidence only)
  5a: B-roll prompts (retrieval: GAP-FILL — may verify API constraints)
  5b: Captions (retrieval: COMMITTED-ONLY)
  5c: Dispatch (retrieval: NONE)
  5d: Adjudication (retrieval: COMMITTED-ONLY)

Phase 6: Adversarial Validation
  6: Cut audit (retrieval: ADVERSARIAL — may re-read originals to challenge claims)
  6b: Draft review (retrieval: COMMITTED-ONLY — tool-mediated)

Phase 7-8: Final Synthesis + Surface
  7a: Post copy (retrieval: COMMITTED-ONLY)
  7b: Report (retrieval: COMMITTED-ONLY — reads all artifacts)
  8: Surface (lead inline)
```

### Retrieval Rights Table

| Phase | Lane Type | Retrieval Right | Why |
|-------|-----------|-----------------|-----|
| 0/0b | Infrastructure | File read | Establishing scaffold |
| 1a | Discovery | Expected | Platform intelligence needs live data |
| 1b/1c | Verification | Expected | Transcript truth requires source material |
| 1d | Discovery | Expected | Visual evidence from Overshoot tool |
| 2 | Synthesis | Gap-fill | May need to re-read ambiguous transcript sections |
| 3 | Lead judgment | Inline | Lead reads scoring + makes selection |
| 4 | Design | Gap-fill | Must verify timestamp-to-content mappings |
| 4b | Checkpoint | Verification | Re-transcribes edited base track via Whisper |
| 5a | Design | Gap-fill | May verify API model constraints |
| 5b | Synthesis | Committed-only | Captions from locked EDL, no fresh retrieval |
| 5c | Execution | None | Dispatch only |
| 5d | Verification | Committed-only | Tool-mediated asset assessment |
| 6 | Adversarial | Adversarial | Re-reads originals to challenge editor claims |
| 6b | Verification | Committed-only | Tool-mediated draft assessment |
| 7a | Synthesis | Committed-only | Copy from committed editorial decisions |
| 7b | Synthesis | Committed-only | Report reads all artifact files directly |

### What Changes for Subagent Prompts

Every subagent prompt now includes:
1. Its **retrieval rights** declaration (expected / gap-fill / adversarial / committed-only / none)
2. A reference to or content from the **evidence scaffold** (Phase 0b) and **evidence surface** (Checkpoint A)
3. For Phase 6 (cut auditor): the **original verified transcript** alongside the EDL, so it can independently verify claims

## Subagent Briefing Protocol

When `/podcast-pipeline` spawns a subagent, the prompt must be **self-contained**. Subagents don't see the lead's conversation history. Every subagent prompt must include:

1. **Role**: what this agent is doing and why
2. **Skill reference**: which `/skill` protocol to follow
3. **Input data**: the actual JSON content from prior stages (not file paths — the agent may not have the same working directory)
4. **Profile**: the full show profile JSON
5. **Creative**: the active creative config
6. **Audience context**: the runtime intelligence object (if available at this phase)
7. **Evidence surface**: the Checkpoint A evidence surface (for Phase 2+ agents — the committed evidence plane)
8. **Retrieval rights**: explicitly state what the agent is allowed to retrieve (expected / gap-fill / adversarial / committed-only)
9. **Output instructions**: exact file path to write, exact schema to follow
10. **Model constraint**: "You are running as Opus/Sonnet. No Haiku anywhere in this pipeline."

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

| Model | Router Key | fal.ai ID | Type | Start Frame | End Frame | References |
|-------|-----------|-----------|------|-------------|-----------|------------|
| Nano Banana 2 | `nano-banana-2` | `fal-ai/nano-banana-2` | image | N/A | N/A | N/A |
| Kling v3 Pro i2v | `kling-v3-pro-i2v` | `fal-ai/kling-video/v3/pro/image-to-video` | video | `start_image_url` (required) | `end_image_url` (optional) | `elements[]` (identity anchors) |
| Seedance 2.0 i2v | `seedance-2.0-i2v` | `bytedance/seedance-2.0/image-to-video` | video | `image_url` (required) | `end_image_url` (optional) | NONE |
| Seedance 2.0 r2v | `seedance-2.0-r2v` | `bytedance/seedance-2.0/reference-to-video` | video | NONE | NONE | `image_urls[]` up to 9 |

**Seedance i2v** is the morph workhorse — deterministic start+end frame interpolation. No reference channel. The prompt carries all aesthetic intent.

**Seedance r2v** is for style transfer and mood boards — reference images guide the aesthetic, but you have zero control over start/end frames. The model decides temporal placement. NOT suitable for morph transitions where frame binding is required.

**Kling v3 Pro** accepts frame binding + identity anchors (`elements`). Use for character-preservation scenes where the speaker's likeness must be maintained in generated footage. The only model with partial frame binding + identity reference in one call.

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

### Morph Transition Grammar

Morph transitions (speaker dissolves into abstract energy and back) use a **3-frame deterministic chain**. This is the canonical morph architecture for the pipeline.

**Three frames per morph slot:**
1. **Departure frame** — last A-roll frame before b-roll IN. Extracted from locked base track at `(IN timestamp - 0.033s)`. Reframed to output aspect ratio (e.g., 9:16).
2. **Midpoint image** — abstract/conceptual target. Generated via Nano Banana at show palette. This serves as the END frame of Clip A and START frame of Clip B.
3. **Return frame** — first A-roll frame after b-roll OUT. Extracted from locked base track at OUT timestamp. Reframed to output aspect ratio.

**Two clips per morph slot, both using Seedance i2v deterministic path:**
- **Clip A (IN morph)**: `image_url`=departure, `end_image_url`=midpoint. Reality → abstraction.
- **Clip B (OUT morph)**: `image_url`=midpoint, `end_image_url`=return. Abstraction → reality.
- Clip B's `image_url` MUST be the same file as Clip A's `end_image_url` (the midpoint image). Different files = visible seam at crossover.
- Trim each clip to half the overlay window duration, concat, overlay on base track.

**API constraint — deterministic vs reference modes are mutually exclusive:**

| Model | Start frame | End frame | Reference images | Morph-safe |
|-------|------------|-----------|-----------------|------------|
| Seedance i2v | `image_url` | `end_image_url` | NONE | YES — deterministic frame binding |
| Seedance r2v | NONE | NONE | `image_urls[]` up to 9 | NO — no frame binding, model decides temporal placement |
| Kling v3 Pro | `start_image_url` | `end_image_url` | `elements[]` (identity) | PARTIAL — frame binding + identity anchors |

You cannot pass reference images AND start/end frames in the same Seedance call. For morph transitions, frame binding wins. The prompt carries all aesthetic intent.

The midpoint image prompt is load-bearing — it must produce the exact aesthetic target because there is no reference channel to enforce palette or style alongside the deterministic frame path.

**Non-morph slots (animated/static)** use the simpler two-step pattern below.

### Two-Step Pattern (non-morph slots)

Non-morph b-roll slots need a scene image first:
1. `nano-banana-2` → generates scene image ($0.08, ~10s)
2. `seedance-2.0-i2v` → animates from scene image as start frame, no end frame ($1.51 for 5s)

The b-roll prompt engineer handles this — it writes two envelopes per non-morph slot with `step: "scene_image"` and `step: "video_generation"` marked in pipeline_context.

For morph slots, three envelopes: `midpoint_image`, `morph_clip_a`, `morph_clip_b`.

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
