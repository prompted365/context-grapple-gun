---
name: videographer
description: Directed capture and narrative export — compose keyframe stories, record video (WebM/MP4), capture hi-res snapshots from the 3D substrate.
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
