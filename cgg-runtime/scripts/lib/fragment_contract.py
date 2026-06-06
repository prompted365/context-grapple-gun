#!/usr/bin/env python3
"""fragment_contract.py — the Injection Fabric shared fragment contract (tic 367).

Implements the THREE NORMATIVE directives of the §4 fragment contract from
`autonomous_kernel/injection-fabric-spec.md` (PROMOTE-SPEC ratified DIRECTIONAL,
/review 353) as ONE canonical surface that every delivery model imports and honors:

    1. pertinence — which CLASS? (one of the 9; the missing primary axis)
    2. authority  — may_act_from / may_mutate_source / must_escalate (gated by
                    pertinence; compile-time may TIGHTEN, never LOOSEN)
    3. citation   — may_quote? (the no-cite axis — orientation that must not be
                    quoted as mandate)

WHY THIS EXISTS (spec §1.2 — the core problem). The fabric had TWO delivery
models that did not share a contract:
  - routed/governed (office-worldview.py): rich structured pertinence + authority
    block + a derived badge — but it OWNED the only copy of the 9-class table.
  - registry/migration (dsn_fragment.py): honored the contract with STRING
    approximations and a HARDCODED badge literal that duplicated what the routed
    model computes — a silent-drift hazard (edit the table, the literal rots).
  - blunt registry (active.jsonl): no pertinence/authority/citation at all.

This module is the single source of truth (federation discipline: single-source /
byte-identity over copy-parity). office-worldview.py and dsn_fragment.py both
consume it, so the 3 normative fields can never drift between models, and a
validator can ADMIT or REJECT any fragment from any seam against one contract.

GOVERNING INVARIANT (spec §6): canonical owns the lifecycle; runtimes produce
artifacts. This module is the canonical lifecycle surface for the 3 normative
fields. It NEVER mutates state, NEVER retires a fragment, NEVER writes a registry
(--audit-registry is strictly read-only) — admission/validation only.

SCOPE (Architect-gated, tic 367): the 3 normative directives ONLY. The 6
named-but-unenforced §4 fields (methylation, source, freshness, receipt
requirement, stop condition, follow-surface) are DECLARED NON-IMPLEMENTATION here
(see NAMED_UNENFORCED) — directional targets a later migration exercises before
any is promoted to normative (Governance-is-instrumental-not-terminal).
"""

from __future__ import annotations

# ── THE 3 NORMATIVE DIRECTIVES ───────────────────────────────────────────────

# Directive 1 — pertinence. The 9 classes (Architect-specified; mirrors the
# office-worldview.py compiler docstring). A fragment's pertinence.class MUST be
# one of these; an unrecognized class is inadmissible.
PERTINENCE_CLASSES = {
    "YOURS":     "carry as purpose; may shape priority/judgment/resolve; act only if authority allows",
    "FIELD":     "background terrain; understand; do not act from; do not cite as mandate",
    "SUBSTRATE": "load-bearing invariant beneath the office; shapes all interpretation; not locally editable",
    "OFFICE":    "your role/aperture/obligations; authorizes action inside the office boundary",
    "PEER":      "another office at same standing; understand the relation; do not overwrite/impersonate",
    "ANCESTOR":  "prior lineage/inherited terrain; explains why current structure exists; does not authorize present action",
    "COUNTER":   "inversion/drift/warning shape; use diagnostically; do not emulate",
    "SEALED":    "matters but not to be cited/expanded/acted from; exists to prevent misclassification",
    "ESCALATE":  "relevant but exceeds your authority; preserve and route upward",
}

# Directive 2 + 3 — authority (gated by pertinence) + citation (may_quote).
# Authority defaults per pertinence class. Compile-time may TIGHTEN (never loosen).
#   may_act_from  is the Authority axis; may_quote is the Citation axis.
# This is THE source of the table — moved out of office-worldview.py, which now
# imports it. (Identical values; provenance: office-worldview.py AUTHORITY_DEFAULTS.)
AUTHORITY_DEFAULTS = {
    "YOURS":     dict(may_read=True, may_shape_interpretation=True, may_act_from=True,  may_mutate_source=True,  may_quote=True,  must_escalate=False, weight=0.90),
    "OFFICE":    dict(may_read=True, may_shape_interpretation=True, may_act_from=True,  may_mutate_source=True,  may_quote=True,  must_escalate=False, weight=0.88),
    "SUBSTRATE": dict(may_read=True, may_shape_interpretation=True, may_act_from=False, may_mutate_source=False, may_quote=True,  must_escalate=False, weight=0.82),
    "ESCALATE":  dict(may_read=True, may_shape_interpretation=True, may_act_from=False, may_mutate_source=False, may_quote=True,  must_escalate=True,  weight=0.75),
    "COUNTER":   dict(may_read=True, may_shape_interpretation=True, may_act_from=False, may_mutate_source=False, may_quote=True,  must_escalate=False, weight=0.62),
    "PEER":      dict(may_read=True, may_shape_interpretation=True, may_act_from=False, may_mutate_source=False, may_quote=True,  must_escalate=False, weight=0.55),
    "FIELD":     dict(may_read=True, may_shape_interpretation=True, may_act_from=False, may_mutate_source=False, may_quote=False, must_escalate=False, weight=0.45),
    "ANCESTOR":  dict(may_read=True, may_shape_interpretation=True, may_act_from=False, may_mutate_source=False, may_quote=True,  must_escalate=False, weight=0.40),
    "SEALED":    dict(may_read=True, may_shape_interpretation=True, may_act_from=False, may_mutate_source=False, may_quote=False, must_escalate=False, weight=0.30),
}

# Tighten-not-loosen polarity. GRANT keys: a fragment may set them False (tighten)
# but may NOT set True where the class ceiling is False (loosen → REJECT).
_GRANT_KEYS = ("may_read", "may_shape_interpretation", "may_act_from", "may_mutate_source", "may_quote")
# RESTRICTION key: must_escalate may be raised True (tighten) but a required
# escalation may NOT be dropped to False (loosen → REJECT).
_RESTRICTION_KEYS = ("must_escalate",)

# The 6 §4 fields ratified NAMED-BUT-UNENFORCED — declared non-implementation for
# this slice. Enumerated so the contract is honest about what it does NOT yet gate.
NAMED_UNENFORCED = (
    "methylation", "source", "freshness",
    "receipt_requirement", "stop_condition", "follow_surface",
)


def class_authority(cls: str) -> dict:
    """Return a fresh copy of the default authority block for a class (no weight;
    weight is methylation, a NAMED_UNENFORCED field, not part of the 3 normative
    directives). Falls back to FIELD (the most restrictive grant profile) for an
    unknown class — fail-closed, never fail-open."""
    src = AUTHORITY_DEFAULTS.get(cls, AUTHORITY_DEFAULTS["FIELD"])
    auth = dict(src)
    auth.pop("weight", None)
    return auth


def badge(cls: str, auth: dict = None, gated: bool = False) -> str:
    """Canonical compact authority badge — the single renderer for the human face.

    Source of truth for the ⟨CLASS·…⟩ badge used by office-worldview.py (was its
    private _badge) AND dsn_fragment.py (was a hardcoded literal). Deriving both
    from here means the badge can never drift from AUTHORITY_DEFAULTS.

    auth defaults to the class ceiling when omitted, so badge("FIELD") renders the
    canonical FIELD badge with no caller bookkeeping."""
    if auth is None:
        auth = class_authority(cls)
    bits = []
    bits.append("act" if auth.get("may_act_from") else "shape-only")
    if not auth.get("may_quote"):
        bits.append("no-cite")
    if auth.get("must_escalate"):
        bits.append("ESCALATE↑")
    if not auth.get("may_mutate_source") and auth.get("may_act_from"):
        bits.append("no-mutate")
    if gated:
        bits.append("GATED")
    return f"⟨{cls}·{'·'.join(bits)}⟩"


def validate_fragment(frag: dict) -> tuple:
    """Validate a fragment against the 3 NORMATIVE directives.

    Returns (ok: bool, errors: list[str]). A fragment is admissible iff it can
    answer all three — the spec §4 admissibility test, scoped to the ratified
    normative tier. Orthogonality is enforced by checking each axis independently
    (pertinence ≠ authority ≠ citation): the citation axis (may_quote) is validated
    SEPARATELY from the action-authority axis even though both live in the
    authority block, so a fragment cannot satisfy citation by riding on authority.

    Tighten-not-loosen: a fragment's authority may be MORE restrictive than its
    class ceiling, never less. Loosening (granting a capability the class denies,
    or dropping a required escalation) is inadmissible.
    """
    errors = []

    if not isinstance(frag, dict):
        return False, ["fragment is not an object"]

    # ── Directive 1: pertinence ──────────────────────────────────────────────
    pert = frag.get("pertinence")
    cls = None
    if not isinstance(pert, dict) or "class" not in pert:
        errors.append("pertinence: missing pertinence.class (Directive 1) — a fragment "
                      "must declare which of the 9 classes it is")
    else:
        cls = pert["class"]
        if cls not in PERTINENCE_CLASSES:
            errors.append(f"pertinence: unknown class {cls!r} (Directive 1) — not one of "
                          f"{sorted(PERTINENCE_CLASSES)}")
            cls = None  # cannot gate authority against an unknown ceiling

    # ── Directive 2: authority (gated by pertinence; tighten-not-loosen) ──────
    auth = frag.get("authority")
    if not isinstance(auth, dict):
        errors.append("authority: missing authority block (Directive 2)")
        auth = None
    elif cls is not None:
        ceiling = AUTHORITY_DEFAULTS[cls]
        for k in _GRANT_KEYS:
            if k in auth and bool(auth[k]) and not bool(ceiling.get(k)):
                errors.append(f"authority: {k}=True LOOSENS class {cls} ceiling "
                              f"({k}={ceiling.get(k)}) — compile-time may tighten, never loosen")
        for k in _RESTRICTION_KEYS:
            if bool(ceiling.get(k)) and k in auth and not bool(auth[k]):
                errors.append(f"authority: {k}=False drops a required escalation for class "
                              f"{cls} — loosening a restriction is inadmissible")

    # ── Directive 3: citation (the no-cite axis, independent of action) ───────
    # may_quote lives in the authority block but is the SEPARATE citation axis.
    if auth is not None:
        if "may_quote" not in auth:
            errors.append("citation: missing may_quote (Directive 3) — the citation axis "
                          "must be answered independently of action authority")
        elif not isinstance(auth["may_quote"], bool):
            errors.append(f"citation: may_quote must be bool, got {type(auth['may_quote']).__name__}")
        elif cls is not None and auth["may_quote"] and not bool(AUTHORITY_DEFAULTS[cls].get("may_quote")):
            # loosening citation (already caught as a GRANT key, but named here for
            # the citation-axis error surface so the violation reads as a citation
            # collapse: known→citable)
            pass  # already reported under Directive 2; avoid duplicate

    return (len(errors) == 0), errors


# ── read-only registry audit (spec §1.2 gap, made visible) ───────────────────

def audit_registry_entry(entry: dict) -> tuple:
    """Validate a blunt-registry entry (active.jsonl shape) against the contract.

    These legacy entries carry audience/inject_text/freshness but NONE of the 3
    normative fields — so they REJECT. This is not a bug to fix by mutation; it is
    the §1.2 gap surfaced. A registry migration (e.g. the DSN/GLOSSARY slice) is
    what gives an entry a pertinence class + authority + citation. Read-only.
    """
    # Project the registry entry into a fragment shape for validation. The
    # projection invents NOTHING — absent fields stay absent, so the validator
    # reports exactly which normative directives the legacy entry cannot answer.
    proj = {
        "pertinence": entry.get("pertinence"),
        "authority": entry.get("authority"),
    }
    return validate_fragment(proj)


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import json
    import sys
    from pathlib import Path

    ap = argparse.ArgumentParser(description="Injection Fabric shared fragment contract — "
                                             "validate the 3 normative directives.")
    ap.add_argument("--validate", metavar="PATH",
                    help="validate a fragment / list / worldview-json file ('-' = stdin)")
    ap.add_argument("--audit-registry", metavar="PATH", nargs="?", const="AUTO",
                    help="read-only audit of a blunt registry (active.jsonl); "
                         "default path auto-resolves from zone root")
    ap.add_argument("--self-test", action="store_true", help="run contract self-checks")
    args = ap.parse_args()

    def _load(path):
        text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8", errors="replace")
        return json.loads(text)

    def _fragments_of(obj):
        # accept a single fragment, a list, or a worldview-json envelope
        if isinstance(obj, dict) and "fragments" in obj:
            return obj["fragments"]
        if isinstance(obj, list):
            return obj
        return [obj]

    if args.validate:
        obj = _load(args.validate)
        frags = _fragments_of(obj)
        bad = 0
        for i, f in enumerate(frags):
            ok, errs = validate_fragment(f)
            fid = f.get("id", f"#{i}") if isinstance(f, dict) else f"#{i}"
            if ok:
                print(f"ADMIT  {fid}")
            else:
                bad += 1
                print(f"REJECT {fid}")
                for e in errs:
                    print(f"         - {e}")
        print(f"\n{len(frags)-bad}/{len(frags)} admitted ({bad} rejected)")
        sys.exit(1 if bad else 0)

    if args.audit_registry:
        path = args.audit_registry
        if path == "AUTO":
            here = Path(__file__).resolve()
            root = None
            for p in here.parents:
                if (p / ".ticzone").is_file():
                    root = p
                    break
            if root is None:
                print("could not resolve zone root for AUTO registry path", file=sys.stderr)
                sys.exit(2)
            path = root / "audit-logs" / "boot-injections" / "active.jsonl"
        path = Path(path)
        print(f"# read-only registry audit: {path}")
        seen = {}
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            seen[e.get("injection_id", id(e))] = e  # latest-per-id wins
        gap = 0
        for iid, e in seen.items():
            ok, errs = audit_registry_entry(e)
            status = e.get("status", "?")
            if ok:
                print(f"ADMIT  {iid} [{status}]")
            else:
                gap += 1
                print(f"GAP    {iid} [{status}] — cannot answer the 3 normative directives:")
                for er in errs:
                    print(f"         - {er}")
        print(f"\n{gap}/{len(seen)} registry entries are pre-contract (the §1.2 gap; "
              f"migration — not mutation — closes it)")
        sys.exit(0)

    if args.self_test:
        failures = []

        def check(name, cond):
            print(("PASS" if cond else "FAIL"), name)
            if not cond:
                failures.append(name)

        # a well-formed fragment at the class ceiling ADMITs
        ok, _ = validate_fragment({"pertinence": {"class": "YOURS"},
                                   "authority": class_authority("YOURS")})
        check("ceiling YOURS fragment admits", ok)

        # tightening (FIELD with may_quote False already) ADMITs; OFFICE tightened to
        # shape-only ADMITs (False is more restrictive than the True ceiling)
        tightened = class_authority("OFFICE"); tightened["may_act_from"] = False
        ok, _ = validate_fragment({"pertinence": {"class": "OFFICE"}, "authority": tightened})
        check("tightened OFFICE (act→shape-only) admits", ok)

        # loosening REJECTs: FIELD granting may_act_from
        loosened = class_authority("FIELD"); loosened["may_act_from"] = True
        ok, errs = validate_fragment({"pertinence": {"class": "FIELD"}, "authority": loosened})
        check("FIELD granting may_act_from rejects (loosen)", not ok and any("LOOSEN" in e for e in errs))

        # loosening citation REJECTs: FIELD granting may_quote
        loosened_q = class_authority("FIELD"); loosened_q["may_quote"] = True
        ok, errs = validate_fragment({"pertinence": {"class": "FIELD"}, "authority": loosened_q})
        check("FIELD granting may_quote rejects (loosen citation)", not ok)

        # dropping a required escalation REJECTs: ESCALATE with must_escalate False
        dropped = class_authority("ESCALATE"); dropped["must_escalate"] = False
        ok, errs = validate_fragment({"pertinence": {"class": "ESCALATE"}, "authority": dropped})
        check("ESCALATE dropping must_escalate rejects", not ok)

        # unknown class REJECTs
        ok, errs = validate_fragment({"pertinence": {"class": "BOGUS"}, "authority": {"may_quote": True}})
        check("unknown class rejects", not ok and any("unknown class" in e for e in errs))

        # missing axes REJECT (the §1.2 registry shape)
        ok, errs = validate_fragment({"audience": "all", "inject_text": "..."})
        check("registry-shape (no axes) rejects all 3", not ok and len(errs) >= 2)

        # citation is INDEPENDENT: a fragment with authority but no may_quote rejects on citation
        no_quote = {k: v for k, v in class_authority("YOURS").items() if k != "may_quote"}
        ok, errs = validate_fragment({"pertinence": {"class": "YOURS"}, "authority": no_quote})
        check("missing may_quote rejects on citation axis", not ok and any("citation" in e for e in errs))

        # badge parity: badge() reproduces every class's canonical badge from the table
        # (the office-worldview _badge algorithm, now shared)
        expect = {
            "YOURS": "⟨YOURS·act⟩",
            "OFFICE": "⟨OFFICE·act⟩",
            "SUBSTRATE": "⟨SUBSTRATE·shape-only⟩",
            "ESCALATE": "⟨ESCALATE·shape-only·ESCALATE↑⟩",
            "COUNTER": "⟨COUNTER·shape-only⟩",
            "PEER": "⟨PEER·shape-only⟩",
            "FIELD": "⟨FIELD·shape-only·no-cite⟩",
            "ANCESTOR": "⟨ANCESTOR·shape-only⟩",
            "SEALED": "⟨SEALED·shape-only·no-cite⟩",
        }
        for cls, want in expect.items():
            check(f"badge({cls}) == {want}", badge(cls) == want)

        # the dsn_fragment.py hardcoded literal it replaces
        check("badge('FIELD') == dsn hardcoded literal",
              badge("FIELD") == "⟨FIELD·shape-only·no-cite⟩")

        print()
        if failures:
            print(f"{len(failures)} FAILED:", ", ".join(failures))
            sys.exit(1)
        print("all fragment-contract self-checks PASS")
        sys.exit(0)

    ap.print_help()
