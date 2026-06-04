#!/usr/bin/env python3
"""
DSN fragment writer — the fabric-fragment writer for the GLOSSARY / Doctrine-
Surface-Navigation routed migration (slice: glossary-dsn-migration, tic 354 →
executed tic 355).

This is the ONE genuinely-new build target of the migration. Everything else
(the seam, the registry, the spine) is unification of live pieces. It emits the
GLOSSARY § "Doctrine Surface Navigation" frame as a *routed pointer fragment*
honoring the Injection Fabric §4 fragment contract
(`autonomous_kernel/injection-fabric-spec.md`), so the live primitive that went
taxidermied at tic 350 (payload→nag) can eat again — delivered only where it
shapes lawful motion, not blanket-injected at `audience:all`.

Design invariants (slice §7 gates):
  - FIELD never authorizes action. The fragment is `FIELD·shape-only·no-cite`
    terrain everywhere it is delivered. Office MOTION authority is a SEPARATE
    axis carried by the recipient's own mandate (YOURS/OFFICE·act). The fragment
    NEVER carries `·act`. This corrects the tic-353 identity-driven arena's own
    `FIELD·act` output against the Pertinence — three-axis KI.
  - The fragment is a POINTER, never inline prose. GLOSSARY.md stays reference
    terrain; only the delivery mechanism migrates. The body is ~1 sentence of
    navigation grammar + the follow-surface naming, resolving to the section.
  - Routing is data (the tic-353 identity-driven arena routing table). Unknown
    recipients get NO fragment (general-purpose injection is dishonest — the
    arena's self-omission geometry, honored).
  - Returns None on OMIT / SKIP / unknown / wrong-phase. None means "do not
    deliver" — the caller appends nothing.

The 8-field contract (slice §4): every emitted fragment can answer
  1 pertinence  → always FIELD where delivered (or OMIT). Never `·act`.
  2 authority   → FIELD: understand, do not act from. Motion is the office's own.
  3 citation    → no-cite (a navigation aid, not a doctrine quote)
  4 source      → GLOSSARY.md § "Doctrine Surface Navigation"
  5 freshness   → coarse /review-cadence TTL (re-verify each /review epoch)
  6 receipt     → phase-scoped (owed for ACT/JUDGE; optional for OBSERVE)
  7 stop        → per-recipient (the audience:all-fires-forever defect-fixer)
  8 follow      → which ledger the pointer resolves into (federation vs CGG)
(methylation DEFER → handled by pertinence-class routing.)
"""

from __future__ import annotations

from typing import Optional

# Stable source/freshness handles — the fragment's provenance, not its body.
SOURCE = 'GLOSSARY.md § "Doctrine Surface Navigation"'
SOURCE_ANCHOR = "GLOSSARY.md#doctrine-surface-navigation"
FRESHNESS = "coarse /review-cadence TTL (re-verify each /review epoch)"
# The fragment is FIELD for every recipient — the badge office-worldview.py
# would compile for class FIELD (may_act_from=False → shape-only; may_quote=False
# → no-cite; must_escalate=False → no ↑).
BADGE = "⟨FIELD·shape-only·no-cite⟩"

# Both ledgers named for the fleet cluster — review-execute inscribes and
# ladder-auditor verifies across both rungs; the navigation frame's whole point
# is "two ledgers, two rungs — do not cross them."
_BOTH_LEDGERS = "constitution-ledger (federation) + cgg-ledger (CGG) — two rungs, do not cross"

# The routing table IS the delivery contract (slice §3, from the tic-353
# identity-driven arena). Each entry carries the per-recipient contract fields.
# `deliver_phases`, when present, gates delivery on loop_phase (a phase-scoped
# recipient OMITs outside those phases — e.g. Homeskillet injects nothing at
# boot/judge/close, only at review-execute dispatch). Absence ⇒ the recipient's
# role fixes its phase and it always delivers. A `None` entry is an explicit OMIT.
_ROUTING = {
    # ── fleet cluster (PRIMARY seam = subdelegation-briefing) ──
    "review-execute": {
        "loop_phase": "ACT/inscribe", "seam": "subdelegation-briefing",
        "motion": "YOURS·act", "receipt": "owed",
        "stop": "pointer resolves to live ledger", "follow": _BOTH_LEDGERS,
    },
    "ladder-auditor": {
        "loop_phase": "JUDGE/verify", "seam": "subdelegation-briefing",
        "motion": "OFFICE·act (verification)", "receipt": "owed",
        "stop": "anchor resolves vs dangling", "follow": _BOTH_LEDGERS,
    },
    "ripple-assessor": {
        "loop_phase": "JUDGE/scope-fit", "seam": "subdelegation-briefing",
        "motion": "OFFICE·act (scope-fit)", "receipt": "optional",
        "stop": "overlap probed", "follow": _BOTH_LEDGERS,
    },
    "pattern-curators": {
        "loop_phase": "OBSERVE/mine", "seam": "subdelegation-briefing",
        "motion": "OFFICE·act (mine)", "receipt": "optional",
        "stop": "pointer→SKIP", "follow": _BOTH_LEDGERS,
    },
    # ── phase-gated recipients ──
    "mogul": {
        # runner-prompt seam (NOT subdelegation-briefing) — phase-scoped to the
        # two doctrine-traversing checks only.
        "seam": "runner-prompt", "motion": "YOURS·act", "receipt": "owed",
        "stop": "baked into check", "follow": _BOTH_LEDGERS,
        "deliver_phases": {"review_close_check", "review-close-check",
                           "ladder-audit", "ladder_audit"},
    },
    "homeskillet": {
        # dispatch-time only; OMIT at boot / judge / close.
        "seam": "subdelegation-briefing", "motion": "YOURS·act", "receipt": "owed",
        "stop": "target confirmed", "follow": _BOTH_LEDGERS,
        "deliver_phases": {"review-execute", "review-execute-dispatch", "dispatch"},
    },
    "cold-charter-office": {
        # projected office-worldview seam — soft receipt, own-charter motion.
        "seam": "projected-office-worldview", "motion": "OFFICE·act (own charter)",
        "receipt": "soft", "stop": "first traversal logged", "follow": _BOTH_LEDGERS,
    },
    "crisis": {
        # LEARNING / PREVENTION only; OMIT during high-urgency.
        "seam": "subdelegation-briefing", "motion": "OFFICE·act (prevention)",
        "receipt": "briefing artifact serves as the covenant trail for this phase",
        "stop": "OMIT during high-urgency", "follow": _BOTH_LEDGERS,
        "deliver_phases": {"LEARNING", "PREVENTION", "learning", "prevention"},
    },
    # ── explicit OMIT (the arena's self-omission, honored) ──
    "cpr-stepper": None,  # ROUTE phase — no doctrine traversal, no fragment.
}

# Recipient-name normalization: accept ent_*, snake_case, plural/singular drift.
_ALIASES = {
    "ent_homeskillet": "homeskillet",
    "ent_mogul": "mogul",
    "ladder-auditor": "ladder-auditor",
    "ladder_auditor": "ladder-auditor",
    "ladder-audit": "ladder-auditor",
    "ripple_assessor": "ripple-assessor",
    "pattern-curator": "pattern-curators",
    "pattern_curators": "pattern-curators",
    "review_execute": "review-execute",
    "cpr_stepper": "cpr-stepper",
    "crisis-steward": "crisis",
    "ent_crisis_steward": "crisis",
    "cold_charter_office": "cold-charter-office",
}


def _normalize(recipient: str) -> str:
    r = (recipient or "").strip().lower().replace(" ", "-")
    return _ALIASES.get(r, _ALIASES.get(r.replace("-", "_"), r))


def dsn_fragment_record(recipient: str, loop_phase: Optional[str] = None) -> Optional[dict]:
    """Return the structured 8-field DSN fragment record for (recipient, phase),
    or None when the routing table says OMIT / SKIP / unknown / wrong-phase.

    The record is the auditable shape; render_dsn_fragment() renders it to the
    briefing text. Kept separate so a proof artifact or test can assert the
    contract fields without parsing prose.
    """
    r = _normalize(recipient)
    cfg = _ROUTING.get(r)
    if cfg is None:
        # explicit OMIT (key present, value None) OR unknown recipient (no key).
        # Both correctly deliver nothing — general-purpose injection is dishonest.
        return None
    gate = cfg.get("deliver_phases")
    if gate is not None:
        if loop_phase is None or loop_phase not in gate:
            return None  # phase-gated recipient outside its delivery phase → OMIT
    return {
        "recipient": r,
        "pertinence": "FIELD",          # field 1 — never `·act`
        "authority": "FIELD — understand, do not act from; motion is the office's own mandate",  # field 2
        "citation": "no-cite",          # field 3
        "source": SOURCE,               # field 4
        "freshness": FRESHNESS,         # field 5
        "receipt": cfg["receipt"],      # field 6 (phase-scoped)
        "stop_condition": cfg["stop"],  # field 7 (the fires-forever defect-fixer)
        "follow_surface": cfg["follow"],  # field 8
        "office_motion": cfg["motion"],   # SEPARATE axis — the office's own mandate
        "seam": cfg["seam"],
        "loop_phase": loop_phase or cfg.get("loop_phase"),
        "badge": BADGE,
    }


def render_dsn_fragment(recipient: str, loop_phase: Optional[str] = None) -> Optional[str]:
    """Render the routed DSN fragment as pointer-shaped briefing text, or None
    when the routing table says do-not-deliver.

    The output is a POINTER — it names the GLOSSARY section and the follow-
    surface, and it does NOT inline the GLOSSARY prose. FIELD·shape-only·no-cite:
    it orients, it does not authorize. The office's motion authority is the
    SEPARATE `office_motion` axis from its own mandate, never granted here.
    """
    rec = dsn_fragment_record(recipient, loop_phase)
    if rec is None:
        return None
    return (
        f"{rec['badge']} Doctrine-surface navigation (terrain — orient, do not act from, do not cite "
        f"as mandate): if \"doctrine vs ledger vs CLAUDE.md vs compact-root vs pointer vs spec\" is at "
        f"all fuzzy before you traverse a doctrine surface, the map is {rec['source']}. Follow the "
        f"pointer — a Key Invariant's full body lives in the ledger ({rec['follow_surface']}), NOT in "
        f"the compact root; a CogPR's promoted_to CLAUDE.md does not mean the body lives there "
        f"post-dehydration. This fragment situates your orientation; it does NOT grant motion — your "
        f"action authority is {rec['office_motion']} from your own mandate. "
        f"[stop: {rec['stop_condition']} · freshness: {rec['freshness']}]"
    )


# ── self-test + dry-run CLI ─────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="DSN fabric-fragment writer.")
    parser.add_argument("--render", metavar="RECIPIENT", help="render the fragment for a recipient")
    parser.add_argument("--phase", default=None, help="loop phase (for phase-gated recipients)")
    parser.add_argument("--record", action="store_true", help="emit the structured record (with --render)")
    parser.add_argument("--self-test", action="store_true", help="run routing self-checks")
    args = parser.parse_args()

    if args.render:
        if args.record:
            rec = dsn_fragment_record(args.render, args.phase)
            print(json.dumps(rec, indent=2, ensure_ascii=False) if rec is not None else "null")
        else:
            frag = render_dsn_fragment(args.render, args.phase)
            print(frag if frag is not None else "(OMIT — no fragment for this recipient/phase)")
        sys.exit(0)

    if args.self_test:
        failures = []

        def check(name, cond):
            print(("PASS" if cond else "FAIL"), name)
            if not cond:
                failures.append(name)

        # fleet cluster delivers, pointer-shaped, FIELD, never ·act
        for rcp in ("review-execute", "ladder-auditor", "ripple-assessor", "pattern-curators"):
            f = render_dsn_fragment(rcp)
            check(f"{rcp} delivers", f is not None)
            check(f"{rcp} is FIELD·shape-only·no-cite", f is not None and BADGE in f)
            check(f"{rcp} carries no ·act badge", f is not None and "·act⟩" not in f)
            check(f"{rcp} is a pointer (names the section, no inline table)",
                  f is not None and "Doctrine Surface Navigation" in f and "| Layer |" not in f)
            rec = dsn_fragment_record(rcp)
            check(f"{rcp} record pertinence==FIELD", rec and rec["pertinence"] == "FIELD")
            check(f"{rcp} record carries office_motion (separate axis)", rec and rec.get("office_motion"))

        # alias normalization
        check("ent_homeskillet normalizes", _normalize("ent_homeskillet") == "homeskillet")
        check("ladder_auditor normalizes", _normalize("ladder_auditor") == "ladder-auditor")

        # explicit OMIT and unknown both deliver nothing
        check("cpr-stepper OMITs (ROUTE phase)", render_dsn_fragment("cpr-stepper") is None)
        check("unknown recipient OMITs (no general-purpose injection)",
              render_dsn_fragment("general-purpose") is None)

        # phase-gated: Mogul delivers ONLY at review_close_check / ladder-audit
        check("mogul OMITs with no phase", render_dsn_fragment("mogul") is None)
        check("mogul delivers at review_close_check", render_dsn_fragment("mogul", "review_close_check") is not None)
        check("mogul OMITs at signal_scan phase", render_dsn_fragment("mogul", "signal_scan") is None)
        check("mogul fragment is runner-prompt seam",
              (dsn_fragment_record("mogul", "ladder-audit") or {}).get("seam") == "runner-prompt")

        # phase-gated: Homeskillet OMITs at boot/judge/close, delivers at dispatch
        check("homeskillet OMITs at boot (no phase)", render_dsn_fragment("homeskillet") is None)
        check("homeskillet delivers at review-execute dispatch",
              render_dsn_fragment("homeskillet", "review-execute") is not None)

        # crisis: LEARNING/PREVENTION only
        check("crisis OMITs during high-urgency (no phase)", render_dsn_fragment("crisis") is None)
        check("crisis delivers at PREVENTION", render_dsn_fragment("crisis", "PREVENTION") is not None)

        print()
        if failures:
            print(f"{len(failures)} FAILED:", ", ".join(failures))
            sys.exit(1)
        print("all DSN-fragment self-checks PASS")
        sys.exit(0)

    parser.print_help()
