#!/usr/bin/env python3
"""
Review-lane test — bench-packet-prep dossier carries review_tic (F-746-L3, tic 749).

Root bug (fixed): the per-CPR dossier in build_bench_packet projected birth_tic
but NOT review_tic, so every docket row in the bench packet read
review_tic=None while its queue row carried the fence (observed ×3 at tic 746,
×2 at 748, ×2 at 749). The docket is sequenced by that fence; a packet that
drops it forces the reader back to the raw queue — the exact silent-degrade
the intake lane exists to prevent.

Control: dossier_lifecycle_fields() is the single projection for the two
lifecycle coordinates. If review_tic is dropped from it again, this fails.

Run: python3 tests/review/test_benchpacket_review_tic_passthrough.py
Exit 0 = PASS, 1 = FAIL.
"""
import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "bench-packet-prep.py"


def _load():
    spec = importlib.util.spec_from_file_location("bench_packet_prep", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    m = _load()
    fails = []
    f = m.dossier_lifecycle_fields

    # 1. review_tic passes through verbatim when present.
    out = f({"id": "x", "birth_tic": 746, "review_tic": 749})
    if out.get("review_tic") != 749:
        fails.append(f"review_tic present but projected as {out.get('review_tic')!r}")
    if out.get("birth_tic") != 746:
        fails.append(f"birth_tic projected as {out.get('birth_tic')!r}")

    # 2. Absent review_tic stays None — never coalesced to 0.
    out = f({"id": "y", "birth_tic": 746})
    if "review_tic" not in out or out["review_tic"] is not None:
        fails.append(f"absent review_tic should be None, got {out.get('review_tic', '<missing>')!r}")

    # 3. birth_tic null -> 0 (the absent-sentinel) is preserved.
    out = f({"id": "z", "birth_tic": None, "review_tic": 750})
    if out.get("birth_tic") != 0:
        fails.append(f"birth_tic null should coalesce to 0, got {out.get('birth_tic')!r}")
    if out.get("review_tic") != 750:
        fails.append("review_tic dropped when birth_tic is null")

    # 4. The dossier site actually uses the helper (a dropped splat would
    #    silently reintroduce the bug while the helper still passes).
    src = SCRIPT.read_text()
    if "**dossier_lifecycle_fields(cpr)" not in src:
        fails.append("build_bench_packet dossier no longer splats dossier_lifecycle_fields(cpr)")

    if fails:
        for x in fails:
            print("FAIL:", x)
        return 1
    print("PASS: bench-packet dossier carries review_tic verbatim (4/4 controls)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
