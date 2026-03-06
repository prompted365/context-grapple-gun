---
name: cadence-downbeat
description: "[LEGACY — prefer /cadence] Session epoch boundary. Redirects to /cadence."
user-invocable: true
---

# /cadence-downbeat (legacy)

**This command redirects to `/cadence`.**

`/cadence-downbeat` is a supported legacy entrypoint for the full epoch boundary flow. Use it when the alternate command surface makes sense for your workflow.

When the user invokes `/cadence-downbeat`, inform them:

> Running `/cadence` (full downbeat). Note: `/cadence-downbeat` is a legacy alias — prefer `/cadence` (or `/cadence double-time` for emergency syncopate) in future sessions.

Then execute the full downbeat sequence exactly as `/cadence` with no arguments.
