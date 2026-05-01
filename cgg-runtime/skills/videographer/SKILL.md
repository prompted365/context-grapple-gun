---
name: videographer
description: |
  Directed capture and narrative export — compose keyframe stories, record video (WebM/MP4), capture hi-res snapshots from the 3D substrate.

  CENTROID:
  directed capture and narrative export surface for the 3D substrate

  IS:
  - keyframe story composition with camera, overlay, and duration capture
  - video recording in WebM (VP9) or MP4 (H.264) at 1080p / 2K / 4K
  - hi-res and screen-resolution still snapshots
  - prep-mode playback with overlay cross-fade

  IS NOT:
    collapse_zones:
      - scene mutator (captures substrate state; never modifies the scene graph)
      - governance emitter (narrative capture only; no signal, tic, or warrant writes)
      - asset publisher (records locally; distribution belongs to downstream pipelines)
      - runtime scene editor (prep-mode captures configuration; never reshapes the live scene)
      - editorial deliverable pipeline (substrate capture is distinct from any future media-egress pipeline; current scope is substrate-only)
    sibling_overlaps:
      - /statusline (both are observation surfaces — statusline reads conformation text, videographer captures scene video)
      - fal_router.py / overshoot_router.py (vendor-trajectory media lanes — distinct asset lineage; videographer captures from substrate, routers dispatch to/from external vendors)

  WHEN:
  - when a substrate scene is composed and narrative export is needed
  - when demoing or narrating a substrate tour
  - when a publication-quality snapshot of substrate state is required

  NOT WHEN:
  - without a loaded substrate scene (nothing to capture)
  - as a signal-emission or governance-mutation surface
  - for non-substrate content (external editorial video flows through the vendor-trajectory media routers, not videographer)

  RELATES TO:
  - /statusline (both observe — statusline is textual ambient; videographer is visual capture)
  - fal_router.py / overshoot_router.py (vendor-trajectory media routing — videographer serves substrate; routers serve external vendor capability surface)

  ARGS:
    stance: dispatch
    off_envelope: proceed-with-note
    # off_envelope rationale: /videographer's established default is "capture the
    # current scene" with no args. Undeclared-arg most commonly means "apply default
    # capture" rather than caller confusion — proceed-with-note preserves flow.
    core_dispatch_rays:
      - ""         → prep-mode capture (compose + preview current scene)
      - "record"   → begin video recording at configured resolution
      - "snapshot" → hi-res still at selected resolution
    secondary_modulation_axes:
      - format: webm | mp4
      - resolution: 1080p | 2K | 4K
      - overlays: on | off
user-invocable: true
---

# /videographer

Directed capture skill for the Anchorage of Ubiquity 3D substrate. Use this to compose camera stories, record presentation videos, and capture publication-quality snapshots.

## Quick Reference

| Action | How |
|--------|-----|
| Enter prep mode | Press `A` until "Presentation Prep" banner appears |
| Add keyframe | Press `K` (captures camera + overlay state) |
| Play/stop | Press `Space` |
| Record | Press `R` or click Rec button |
| Hi-res snapshot | Click download icon in PREP panel header |
| Toggle shortcuts help | Press `?` |

## Workflow

### 1. Compose

Position your camera, then press `K` to add keyframes. Each keyframe captures:
- Camera position, target, and field of view
- Current overlay state (selected entity, viz mode, visible layers)
- A thumbnail plate for the shot card

Adjust duration and easing per shot in the shot cards. Duration = transit time to the next keyframe, not hold time.

### 2. Preview

Press `Space` to play the story. Camera interpolates continuously between keyframes. Overlays cross-fade at segment boundaries when consecutive shots have different overlay states.

### 3. Configure Export

In the EXPORT section of the PREP panel:
- **Format**: WebM (VP9, universal) or MP4 (H.264, Chrome/Edge only)
- **Recording resolution**: 1080p / 2K / 4K (renderer upscales during recording)
- **Mode**: "Export only" (download video) or "Export + archive" (persist story)
- **Playback overlays**: toggle which overlays appear during recording

### 4. Record

Press `R` to start recording. The renderer resizes to your selected resolution, playback begins, and the video auto-downloads when complete.

### 5. Snapshots

For still images, use the header buttons:
- Download icon = hi-res snapshot at selected resolution
- Image icon = screen-resolution plate capture

## Tips

- **Hold shots**: Set two consecutive keyframes at the same position — the camera holds static for that duration
- **Smooth arrivals**: Use `easeOut` on the final keyframe for a gentle landing
- **Drama**: Use `easeIn` at the start for a slow departure that accelerates
- **Overlay storytelling**: Select different entities at different keyframes — the detail panel cross-fades between them during playback
- **4K recording**: demanding on GPU. If frames drop, use 2K.

## Agent Delegation

The Videographer can be spawned as an agent for automated capture workflows:

```
Agent(videographer): "Record a 30-second fly-around of the substrate at 2K, starting from the arena bowl, orbiting to the chimney, ending at the federation ring."
```

The agent will compose keyframes, configure export, and report the result.
