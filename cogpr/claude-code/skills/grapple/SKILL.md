---
name: grapple
description: "[LEGACY — prefer /review] CogPR + Warrant review. Redirects to /review."
user-invocable: true
---

# /grapple (legacy)

**This command redirects to `/review`.**

`/grapple` is a supported legacy entrypoint for the CogPR + Warrant review flow. Use it when the alternate command surface makes sense for your workflow.

When the user invokes `/grapple`, inform them:

> Running `/review` (CogPR + Warrant docket). Note: `/grapple` is a legacy alias — prefer `/review` in future sessions.

Then execute the full review workflow exactly as `/review`.
