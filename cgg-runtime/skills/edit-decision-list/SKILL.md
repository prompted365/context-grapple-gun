---
name: edit-decision-list
description: Audio-first edit decision list — maps J-cuts and L-cuts with editorial intention for every transition in the selected segment.
user-invocable: true
model: opus
tools: Read, Write, Glob, Grep, Bash
---

# /edit-decision-list

You are building the backbone of the edit. Everything else — b-roll, captions, render — attaches to this structure. The EDL is not a technical artifact. It is an editorial argument expressed as a sequence of cuts.

## Understanding J-Cuts and L-Cuts

These are not just technique. They are how human perception actually works.

### J-Cut (audio leads visual)
The incoming audio starts *before* the visual cut. The viewer hears the next moment before seeing it. This creates **forward momentum** — the ear pulls the eye into the next shot.

**When to use:**
- Transitions that need momentum — moving from setup to the next beat
- When you want the audience to *anticipate* what they're about to see
- Between b-roll and speaker footage — let the speaker's next thought begin while we're still seeing the b-roll
- When the audio carries the meaning and the visual is secondary

**The feeling:** Leaning forward. Something is coming.

### L-Cut (audio trails visual)
The current audio *continues* under the next visual. The viewer sees a new image while still hearing the previous thought. This creates **emotional subtext** — you see the *impact* of what was just said.

**When to use:**
- After an emotional statement — cut to b-roll or reaction while the words still ring
- When you want the audience to *sit with* what was just said
- To create visual commentary — the speaker says something and we see its consequence
- When the visual carries the meaning and the audio provides context

**The feeling:** Sitting back. Something just landed.

### Hard Cut
Sometimes neither a J nor L cut is right. A hard cut — audio and visual change simultaneously — creates **punctuation**. It's a full stop. Use it for:
- The opening hook (immediate presence)
- Punchlines (the cut IS the punchline)
- Topic shifts that should feel abrupt

## Audio-First Editing Philosophy

The audio is the spine. Always. The transcript is the raw material, but the *spoken audio* — rhythm, breath, emphasis, silence — is the edit's skeleton. Visuals serve the audio.

This means:
1. Map the audio arc first (where does energy rise, where does it breathe, where does it peak)
2. Identify natural cut points in the audio (breath pauses, thought completions, emphasis shifts)
3. Place cuts to serve the audio rhythm, not arbitrary visual timing
4. Let the audio's emotional shape drive when to show the speaker vs. when to cut to b-roll

## Input

You receive:
- The selected segment (from transcript-scorer output)
- The full profile + active creative
- The audience context object
- Timestamp range (if available)

## Process

### Step 1: Audio Arc Mapping

Read through the selected segment and map its audio shape:
- Where does energy build?
- Where are the natural pauses?
- Where is the peak?
- Where does it breathe after the peak?
- Where is the resolution?

### Step 2: Beat Identification

Mark every beat transition — where the segment's internal energy shifts. Each beat boundary is a potential cut point.

### Step 3: Cut Decisions

For each beat boundary, decide:
- **Cut type**: J-cut, L-cut, or hard cut
- **Cut intention**: WHY this cut type at this moment — what is it doing to the viewer
- **Visual state**: What is on screen before and after the cut (speaker / b-roll slot / title card)
- **Timing offset**: For J and L cuts, how much audio overlap (in approximate seconds)

### Step 4: B-Roll Slot Mapping

Identify where b-roll should appear. B-roll is not decoration — it is a visual argument. Mark each b-roll slot with:
- **Start/end in the audio timeline**
- **Emotional register**: What is the speaker's emotional state at this moment
- **Visual function**: illustrate / contrast / abstract / amplify / ground
- **Transition in/out**: What cut type leads into and out of this b-roll slot

## Output Schema

```json
{
  "edl_version": "1.0.0",
  "profile_id": "string",
  "creative_id": "string",
  "segment_start": "HH:MM:SS or content marker",
  "segment_end": "HH:MM:SS or content marker",
  "segment_duration_estimate": "string",
  
  "audio_arc": {
    "energy_shape": "string — narrative description of how energy moves through the segment",
    "peak_location": "string — where maximum intensity occurs",
    "breath_points": ["string — natural pause moments"],
    "resolution_type": "string — how the segment lands (insight, laugh, silence, callback)"
  },
  
  "beats": [
    {
      "beat_number": 1,
      "timestamp_approx": "HH:MM:SS or 'segment +Ns'",
      "content_summary": "string — what happens in this beat",
      "energy_level": "string — low/building/high/peak/descending/resolved",
      "duration_approx": "string"
    }
  ],
  
  "cuts": [
    {
      "cut_number": 1,
      "position": "string — between which beats, or at segment boundaries",
      "timestamp_approx": "HH:MM:SS or 'segment +Ns'",
      "type": "j_cut | l_cut | hard_cut",
      "overlap_seconds": "float — for J/L cuts, how much audio overlap",
      "intention": "string — WHY this cut type. This is the most important field. A cut without intention is noise.",
      "visual_before": "string — what is on screen before the cut",
      "visual_after": "string — what is on screen after the cut",
      "audio_note": "string — what the audio is doing at this moment"
    }
  ],
  
  "broll_slots": [
    {
      "slot_number": 1,
      "timestamp_start": "string",
      "timestamp_end": "string",
      "duration_approx": "string",
      "emotional_register": "string — speaker's emotional state",
      "visual_function": "illustrate | contrast | abstract | amplify | ground",
      "scene_context": "string — what was just said, what is about to be said",
      "transition_in": "j_cut | l_cut | hard_cut",
      "transition_out": "j_cut | l_cut | hard_cut",
      "prompt_seed": "string — initial direction for the b-roll prompt engineer"
    }
  ],
  
  "opening_treatment": {
    "hook_type": "string — how the piece begins (hard cut to mid-thought, slow build, text card, etc.)",
    "first_visual": "string — what the viewer sees first",
    "first_audio": "string — what the viewer hears first",
    "intention": "string — what this opening does to the viewer in the first 3 seconds"
  },
  
  "closing_treatment": {
    "loop_strategy": "string — how the end connects back to the beginning, or null",
    "final_visual": "string — last thing seen",
    "final_audio": "string — last thing heard",
    "intention": "string — what state the viewer is left in"
  },
  
  "editorial_notes": "string — anything worth flagging about the edit structure"
}
```

## Quality Standard

Every cut in the EDL must pass this test: if someone asks "why did you cut here, and why this type of cut?", you have a specific, defensible answer that is about the viewer's experience — not about technique for its own sake.

A J-cut because "J-cuts create momentum" is not an answer. A J-cut because "the speaker is about to pivot from the problem to the solution and the audience needs to feel that shift coming before they see it" is an answer.
