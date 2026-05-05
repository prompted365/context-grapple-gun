# Video Contact Sheet Method

This method documents how the source video was inspected without retaining media in the final package.

1. Sample the source video into temporary frames.
2. Build a temporary contact sheet for visual review.
3. Inspect the contact sheet and selected frames.
4. Write robust frame-by-frame descriptions to `reference/substrate-story-video-vision.md` and `.json`.
5. Delete or exclude all frames, contact sheets, and source video from the delivered archive.

Example command shape:

```bash
mkdir -p /tmp/frederick-video-frames
ffmpeg -i substrate-story-1777821849095.mp4 -vf "fps=1.25,scale=640:-1" /tmp/frederick-video-frames/frame_%02d.jpg
# create contact sheet temporarily, inspect, then exclude/delete media outputs
```

The package intentionally keeps the method and the descriptions, not the media.
