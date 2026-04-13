---
name: show-profile-manager
description: Create, load, validate, and version show profiles and creative config objects for the podcast pipeline.
user-invocable: true
model: opus
tools: Read, Write, Edit, Glob, Grep, Bash
---

# /show-profile-manager

You manage the identity layer of the podcast pipeline. A profile is not a settings file — it is a creative worldview. When you create or edit a profile, you are defining how a show *thinks*, what it *values*, and what it *refuses*.

## Commands

- `/show-profile-manager create` — Interactive profile creation (guided conversation)
- `/show-profile-manager load [name]` — Load and validate a profile
- `/show-profile-manager edit [name]` — Modify a profile field
- `/show-profile-manager creative add [profile]` — Add a creative config to a profile
- `/show-profile-manager creative edit [profile] [creative]` — Modify a creative config
- `/show-profile-manager list` — Show available profiles and their creatives
- `/show-profile-manager validate [name]` — Check profile schema completeness

## Storage

Profiles are stored as JSON files in `./profiles/` relative to the working directory:
```
profiles/
  show-name.profile.json
```

## Profile Schema

```json
{
  "schema_version": "1.0.0",
  "profile_id": "uuid",
  "show_name": "string — the show's name",
  "show_slug": "string — filesystem-safe identifier",
  "mission": "string — what this show exists to do in the world",
  "audience_tribe": "string — who these people are, not just demographics but identity",
  
  "platform_stack": [
    {
      "platform": "instagram | tiktok | youtube_shorts | youtube | spotify | apple_podcasts",
      "priority": "primary | secondary | tertiary",
      "primary_ratio": "9:16 | 1:1 | 16:9 | 4:5",
      "content_approach": "string — how the show uses this platform specifically"
    }
  ],
  
  "aesthetic_invariants": {
    "visual": {
      "grain_vs_clean": "float 0-1 (0=clinical digital, 1=heavy film grain)",
      "typography_personality": "string — how text feels, not just which font",
      "color_anchors": ["string — 3-5 color descriptions, not hex codes"],
      "motion_style": "string — how things move (languid, snappy, weighted, floaty)",
      "texture_preference": "string — organic/synthetic, tactile/flat, lived-in/pristine"
    },
    "sonic": {
      "strategy": "string — what role sound design plays in the show's identity",
      "identity_description": "string — what the show sounds like between words",
      "vocal_processing": "string — how voice should feel (warm/present/distant/intimate)"
    },
    "anti_patterns": [
      "string — things this show NEVER does, visually or sonically"
    ]
  },
  
  "editorial_voice": {
    "host_sensibility": "string — how the host sees the world, what they find interesting",
    "what_the_show_rewards": "string — what makes a good moment on this show",
    "what_bores_the_show": "string — what the show has no patience for",
    "trusted_formats": ["string — formats/structures that work for this show"],
    "forbidden_moves": ["string — editorial choices this show would never make"]
  },
  
  "growth_scoring_weights": {
    "hook_density": "float 0-1 — weight for scroll-arrest moments",
    "quotability": "float 0-1 — weight for standalone phrases",
    "tension_resolution": "float 0-1 — weight for build-peak-release arcs",
    "loop_ability": "float 0-1 — weight for end-echoes-beginning structures",
    "emotional_peaks": "float 0-1 — weight for surprise/recognition/revelation",
    "tribal_signals": "float 0-1 — weight for audience-identity language"
  },
  
  "creatives": []
}
```

## Creative Schema

```json
{
  "creative_id": "uuid",
  "name": "string — human-readable name (e.g., 'Instagram Reel - Standard')",
  "output_type": "reel | story | short | trailer | audiogram",
  "platform": "instagram | tiktok | youtube_shorts",
  "ratio": "9:16 | 1:1 | 16:9 | 4:5",
  
  "duration_target": {
    "min_seconds": 30,
    "max_seconds": 90,
    "sweet_spot": 60
  },
  
  "caption_style": {
    "key_semantic": {
      "position": "center | lower_third | upper_third | dynamic",
      "font_personality": "string — not a font name, a feeling",
      "size_behavior": "string — how size relates to emphasis",
      "animation": "string — how text arrives and departs",
      "diegetic_treatment": "string — how text integrates with b-roll (in-world vs overlay)"
    },
    "subtitle": {
      "position": "bottom | lower_third",
      "font_personality": "string — deliberately subordinate to key semantic",
      "size": "small | medium",
      "style": "string — how subtitles look and feel"
    }
  },
  
  "hook_style": "string — how this creative opens (hard cut, slow build, question, provocation, recognition)",
  "broll_direction": "string — overall b-roll philosophy for this creative",
  "copy_tone": "string — how the post copy sounds (conversational, authoritative, vulnerable, provocative)",
  
  "video_gen_tool": "seedance | veo | happyhorse | kling | runway | none",
  "video_gen_notes": "string — tool-specific prompt optimization notes",
  
  "adjudication_config": {
    "enabled": "boolean — whether visual adjudication runs for this creative (default true)",
    "preset": "source_assessment | generated_assessment | draft_review — which adjudication preset to run",
    "model_tier": "small | medium | large — model tier for adjudication (default medium)",
    "auto_revise": "boolean — if true, pipeline automatically re-runs flagged stages on REVISE verdict (default false)",
    "morph_continuity_check": "boolean — if true, adjudicator specifically checks morph transition integrity (default true)",
    "caption_sync_check": "boolean — if true, adjudicator checks caption timing alignment (default true)"
  },
  
  "overrides": {
    "// any profile-level field can be overridden here for this creative": true
  }
}
```

## Profile Creation Flow

When creating a profile interactively, guide the user through these questions in this order. Do not present a form. Have a conversation.

1. **What's the show?** — Name, mission, what it exists to do
2. **Who listens?** — Not demographics. Identity. What do these people believe? What are they hungry for?
3. **What does the show sound like when it's at its best?** — The moments that make it *this* show and not any other
4. **What would the show never do?** — Anti-patterns, forbidden moves, editorial lines
5. **Where does it live?** — Platform stack, priorities, how each platform is used differently
6. **What does it look like?** — Visual identity: grain, color, motion, typography personality
7. **How does it score?** — Which growth dimensions matter most for this show? (Guide them through the six weights)

After gathering answers, synthesize into the full profile schema. Present it back for confirmation before writing to disk.

## Validation Rules

A profile is valid when:
- All required fields have non-empty values
- `growth_scoring_weights` values sum to approximately 1.0 (within 0.1 tolerance)
- At least one platform in `platform_stack`
- At least one creative in `creatives` (warn but don't block if missing)
- `anti_patterns` has at least 2 entries (a show without limits has no identity)
- `editorial_voice.forbidden_moves` has at least 1 entry

## Versioning

When a profile is modified:
- Increment the `schema_version` patch number
- Add a `_changelog` array entry with timestamp and description of what changed
- The previous version is not preserved (git handles history)
