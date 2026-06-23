#!/usr/bin/env python3
"""ladder-feedback-push.py — the down-lane RETURN leg (up-lane feedback to the originating rung).

THE GAP THIS CLOSES (Architect tic 493). The up-lane is wired: a rung's born is
dehydrated, stamped with birth_rung + origin_context (cpr-extract.py), shipped up with
advocacy (recommended_scopes), and judged at the federation /review. But the VERDICT —
promoted / rejected-with-reason / mapped-as-a-ray-to-an-existing-KI / refined — landed
only in the federation ledger+queue, retrievable by the originating rung ONLY on its next
boot PULL (via load_doctrine_chain reading the ledger). There was no PUSH home. This is
that push: it routes a rehydration instruction back to the originating rung's office inbox.

It is the COMPLEMENT of the C9 down-lane (autonomous_kernel/ladder-downlane-spec.md): that
lane carries federation doctrine DOWN into rungs to test rehydration-in-spirit; THIS carries
a /review verdict on a rung-born finding BACK to where it was born, carrying:
  - the verdict (promoted | rejected | skipped | ray_mapped | refined)
  - the ledger anchor it promoted to, OR the existing KI it maps to as a ray
  - improvement notes / why-denied (for rejected/skipped)
  - the evidence that proved or disproved it
  - how to rehydrate the verdict back into the rung's local context

CENTER-EXCLUSION. This producer NEVER mutates doctrine. It composes a feedback message and
routes it through the validated trigger surface (inbox-envelope.py write). It cables AROUND
the frozen centroid (the ledger), never into it.

BUILD-AND-GATE (cgg-ledger#build-and-gate-ratified-flag-gated-consumer, tic 430). This ships
DORMANT: RATIFIED = False. While dormant, every push is a no-op that returns
{"status":"dormant"} and writes nothing. /review flips RATIFIED to True (ratification IS the
flag-flip — no further code change). --force-ratified exercises the live surface for the
dual proof (dormancy-at-false + full-activation-at-true) WITHOUT flipping the real bit.
This honors fix-then-present (tic 377): the channel is registered + legitimate, the firing
is gated; the boot prose may describe it as build-and-gate/dormant, never as live.

LOOP-SAFE. Deterministic idempotency_key = ladder_feedback_{born_id}_{review_tic}, dedupe
first_wins — one feedback per (born, review verdict).

Usage:
  ladder-feedback-push.py --born-id <id> --verdict <v> --review-tic <N> \
      [--to-office <ent_...>] [--promoted-to <anchor>] [--ray-target <ki_id>] \
      [--reason <notes>] [--evidence <text>] [--rehydration-method <text>] \
      [--force-ratified] [--dry-run]
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path

# ── BUILD-AND-GATE FLAG ──────────────────────────────────────────────────────
# Default DORMANT. /review flips this to True to ratify the live down-lane return leg.
# Ratification IS this flag-flip; no other code changes. (build-and-gate, tic 430)
RATIFIED = False
# ─────────────────────────────────────────────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
try:
    from zone_root import resolve_zone_root  # noqa: E402
except Exception:
    resolve_zone_root = None

VALID_VERDICTS = ("promoted", "rejected", "skipped", "ray_mapped", "refined", "deferred")

# Best-effort rung/origin → owning-office map for sovereign/known rungs. Explicit
# --to-office always overrides; unmatched origins fall back to the orchestrator (flagged).
ZONE_OFFICE = {
    "global-environmental-fusion": "ent_office_global_environmental_fusion",
    "sovereign-sidecar": "ent_homeskillet",        # held by orchestrator
    "estate-seed": "ent_homeskillet",
    "substrate-anchorage": "ent_homeskillet",
    "ak-control-room": "ent_homeskillet",
    "canonical-mount": "ent_homeskillet",
}
FALLBACK_OFFICE = "ent_homeskillet"


def _zone_root(explicit=None) -> Path:
    if explicit:
        return Path(explicit)
    if resolve_zone_root:
        try:
            return Path(resolve_zone_root())
        except Exception:
            pass
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))


def load_born(zone_root: Path, born_id: str) -> dict | None:
    """Terminal-valve read: latest entry per id from queue.jsonl."""
    qp = zone_root / "audit-logs" / "cprs" / "queue.jsonl"
    if not qp.is_file():
        return None
    found = None
    with qp.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            cid = e.get("cogpr_id") or e.get("id") or e.get("cpr_id")
            if cid == born_id:
                found = e  # latest wins
    return found


def resolve_office(born: dict | None, explicit: str | None) -> tuple[str, str]:
    """Return (office, resolved_by). Explicit wins; else best-effort from origin/birth_rung."""
    if explicit:
        return explicit, "explicit"
    if born:
        origin = (born.get("origin_context") or "") + " " + (born.get("source") or "")
        for zone, office in ZONE_OFFICE.items():
            if zone in origin:
                return office, f"origin_match:{zone}"
    return FALLBACK_OFFICE, "fallback"


def compose_body(args, born: dict | None, office: str, resolved_by: str) -> str:
    birth_rung = args.birth_rung or (born.get("birth_rung") if born else None) or "unknown"
    lesson = (born.get("lesson") if born else None) or "(lesson text not resolved from queue)"
    rec = (born.get("recommended_scopes") if born else None) or []
    lines = [
        f"# Ladder rehydration feedback — verdict on a finding you sent up",
        "",
        f"**born_id:** `{args.born_id}`  ·  **birth_rung:** `{birth_rung}`  ·  **/review tic:** {args.review_tic}",
        f"**verdict:** **{args.verdict.upper()}**",
        f"**routed to:** `{office}` (resolved_by: {resolved_by})",
        "",
        "## What you sent up",
        f"> {lesson[:500]}",
    ]
    if rec:
        lines.append(f"\n_Your up-lane advocacy (recommended_scopes):_ {json.dumps(rec)}")
    lines.append("\n## How it was judged")
    if args.verdict in ("promoted", "refined"):
        lines.append(f"- Inscribed at: `{args.promoted_to or '(anchor not supplied)'}`")
        if args.verdict == "refined":
            lines.append("- Landed as a REFINEMENT/conformation edge on an existing entry (not a net-new KI).")
    if args.verdict == "ray_mapped":
        lines.append(f"- Mapped as a RAY to an existing ledger item: `{args.ray_target or '(KI not supplied)'}`")
        lines.append("- This is the common case (non-derivability gate): your finding sharpens an existing centroid rather than minting new law. SKIP ≠ DISCARD — it is homed, not discarded.")
    if args.verdict in ("rejected", "skipped", "deferred"):
        lines.append(f"- Not promoted to net-new doctrine. Reason: {args.reason or '(reason not supplied)'}")
        if args.ray_target:
            lines.append(f"- But it maps as a ray to: `{args.ray_target}` — rehydrate it there.")
    if args.evidence:
        lines.append(f"\n## Evidence\n{args.evidence}")
    lines.append("\n## How to rehydrate this at your rung")
    lines.append(args.rehydration_method or
                 "- Carry the JUDGMENT (the centroid/ray), not a copy of the federation text. "
                 "Load-bearing local semantics stay home. If ray_mapped/refined, follow the named "
                 "anchor and apply its spirit to your local friction — do not re-inscribe it locally.")
    lines.append("\n_— pushed by ladder-feedback-push.py (down-lane return leg). "
                 "This is feedback, not authority: it carries the verdict home; it does not act for you._")
    return "\n".join(lines)


def push(args) -> dict:
    zone_root = _zone_root(args.zone_root)
    if args.verdict not in VALID_VERDICTS:
        return {"status": "error", "reason": f"invalid verdict '{args.verdict}'; one of {VALID_VERDICTS}"}

    born = load_born(zone_root, args.born_id)
    birth_rung = args.birth_rung or (born.get("birth_rung") if born else None)
    if birth_rung == "federation":
        return {"status": "noop", "reason": "birth_rung=federation — finding was born at home; no cross-rung return leg needed", "born_id": args.born_id}

    office, resolved_by = resolve_office(born, args.to_office)
    body = compose_body(args, born, office, resolved_by)
    idem = f"ladder_feedback_{args.born_id}_{args.review_tic}"

    ratified = RATIFIED or args.force_ratified
    if not ratified:
        # DORMANCY (build-and-gate). No-op: write nothing, emit nothing.
        return {
            "status": "dormant", "ratified": False, "born_id": args.born_id,
            "would_route_to": office, "resolved_by": resolved_by,
            "idempotency_key": idem,
            "note": "build-and-gate: ratified=False. /review flips RATIFIED to ratify. "
                    "Re-run with --force-ratified to exercise the live surface for the dual proof.",
        }

    # RATIFIED (or forced) — full activation surface.
    if args.dry_run:
        return {
            "status": "ready", "ratified": True, "dry_run": True, "born_id": args.born_id,
            "recipient": office, "resolved_by": resolved_by, "type": "ladder.rehydration_feedback",
            "idempotency_key": idem, "verdict": args.verdict, "body_preview": body[:400],
        }

    # Write via the validated trigger surface (also validates the manifest type registration).
    ie = Path(_HERE) / "inbox-envelope.py"
    bodyfile = zone_root / "audit-logs" / "jobs-tmp-ladder-feedback-body.md"
    try:
        bodyfile.write_text(body, encoding="utf-8")
        cmd = [
            sys.executable, str(ie), "write",
            "--sender", "ent_homeskillet", "--recipient", office,
            "--type", "ladder.rehydration_feedback",
            "--subject", f"Rehydration feedback: {args.verdict} on {args.born_id} (/review {args.review_tic})",
            "--body-file", str(bodyfile),
            "--source-tic", str(args.review_tic),
            "--priority", "normal", "--delivery-mode", "session_scoped",
            "--idempotency-key", idem, "--dedupe-policy", "first_wins",
            "--source-event", "ladder.rehydration_feedback",
            "--producer", "ladder-feedback-push.py",
        ]
        p = subprocess.run(cmd, capture_output=True, text=True)
        out = p.stdout.strip()
        try:
            res = json.loads(out)
        except Exception:
            res = {"raw": out, "stderr": p.stderr[:200]}
        return {"status": "pushed", "ratified": True, "recipient": office, "resolved_by": resolved_by,
                "idempotency_key": idem, "write_result": res}
    finally:
        try:
            bodyfile.unlink()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser(description="Down-lane return leg: push a /review verdict back to the originating rung (build-and-gate).")
    ap.add_argument("--born-id", required=True)
    ap.add_argument("--verdict", required=True, help="|".join(VALID_VERDICTS))
    ap.add_argument("--review-tic", required=True, type=int)
    ap.add_argument("--birth-rung", help="override (else read from queue.jsonl)")
    ap.add_argument("--to-office", help="explicit recipient office (overrides origin resolution)")
    ap.add_argument("--promoted-to", help="ledger anchor (promoted/refined)")
    ap.add_argument("--ray-target", help="existing KI the born maps to as a ray")
    ap.add_argument("--reason", help="improvement notes / why-denied")
    ap.add_argument("--evidence", help="what proved/disproved it")
    ap.add_argument("--rehydration-method", help="how to carry the verdict back into local context")
    ap.add_argument("--force-ratified", action="store_true", help="exercise the live surface WITHOUT flipping RATIFIED (dual-proof test)")
    ap.add_argument("--dry-run", action="store_true", help="compose + resolve but do not write")
    ap.add_argument("--zone-root")
    args = ap.parse_args()
    print(json.dumps(push(args), indent=2))


if __name__ == "__main__":
    main()
