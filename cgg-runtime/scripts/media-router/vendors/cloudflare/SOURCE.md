# Cloudflare — vendor reference

- **File:** `llms.txt` — Cloudflare's master developer-documentation index (the `llms.txt` convention: a machine-readable map of the docs, where each product entry links to its own per-product `llms.txt`).
- **Source URL:** https://developers.cloudflare.com/llms.txt
- **Fetched:** 2026-06-08 (tic 383) · HTTP 200 · 15,538 bytes / 135 lines
- **Verbatim:** `llms.txt` is the unmodified upstream artifact. To refresh, re-fetch the source URL and update this provenance block (date + size).

## Why it lives here

This `vendors/` subfolder sits beside the media-router vendor lanes (`fal_router.py`, `overshoot_router.py`). Cloudflare is the **live remote compute backend** for the sovereign harness (W1 — Workers AI inference, creds in `.env`); this index is reference material for navigating Cloudflare's developer surface (Workers AI, R2, AI Gateway, etc.) when wiring or debugging that lane. It is documentation only — no router, no credentials, no runtime behavior.
