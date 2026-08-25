#!/usr/bin/env python3
"""discrimination-receipt.py — EMIT-SIDE discrimination receipt for the harmony
and contagion disposition lanes.

WHAT THIS IS
------------
The ratified cure from /review 733, ledger anchor
`audit-logs/governance/constitution-ledger/ledger.md#can-it-eat-dataflow-liveness-predicate`
(the discrimination-axis refinement ray), homed to backlog row
`bk-harmony-discrimination-receipt`:

    "Cure — the DISCRIMINATION RECEIPT on any lane whose output is consumed
     per-tic: emit (a) last_change_tic, (b) consecutive_identical_count over
     the FULL recorded history — never a short window, and (c) the declared
     discriminating condition (what would have to change for this output to
     move). A lane that cannot state (c) is a candidate mounted bear regardless
     of how live its garnish looks."

This module computes that block from the lane's OWN retained artifact corpus and
writes it into the just-emitted disposition packet as an ADDITIVE top-level key
(`discrimination_receipt`). It is the outer-ring (invoke-wrapper) half of the
lane, exactly where the kernels' KERNEL_REGISTRATION discipline puts writes:
the engines stay pure (`meta.pure:true`, `meta.writes:false`); all I/O lives in
the outer rings (harmony-invoke.sh / contagion-invoke.sh + their input builders).

    ⟜ RIDER — reproduced verbatim, /review 733 + A3-732 standing rule ⟜
    "no harmony/contagion disposition may be READ as discriminating until built
     AND ruled — your build is the first half; the ruling comes later at
     /review"
    "Standing rule carried forward: do not read harmony/contagion dispositions
     as discriminating until the receipt fields exist and the A3-732 cause is
     ruled."

    The receipt block therefore carries `ratified: false`. Its presence is the
    BUILT half only. It does NOT authorize any consumer to read these
    dispositions as discriminating, and this module deliberately changes NO
    consumer (boot renderer, worldview, statusline, mogul readers, telemetry
    spine): emit-side only.

WHAT THIS IS NOT
----------------
- NOT a diagnosis. This receipt REPORTS constancy; it never explains it. The
  constancy CAUSE (t589-frozen coordinates, no TTL) is the A3-732 investigation
  and is deliberately unruled — see the ledger ray's own APO perimeter.
- NOT a verdict that the lane is broken. Per the ray: "'strained' may be
  truthful and a smoke detector that never fires is not thereby broken."
- NOT a window. `consecutive_identical_count` is computed over the FULL retained
  on-disk corpus. Guard 12 (`#breach-flag-at-saturation...` sibling, the
  rolling-window attribution ray) is exactly what a capped scan would reproduce.
- NOT a claim about unrecorded tics. The scan is observer-indexed to the corpus
  that is retained on disk, and says so in `history_scanned.scope`.

USAGE
-----
    # emit-side (called by harmony-invoke.sh / contagion-invoke.sh)
    discrimination-receipt.py --lane harmony   --disposition <path>
    discrimination-receipt.py --lane contagion --disposition <path>

    # read-only probe (no write) — e.g. reproduce a historical figure
    discrimination-receipt.py --lane harmony --as-of-tic 730 --stdout-only

    # fixture selftest (no lane artifacts touched)
    discrimination-receipt.py --selftest

Exit codes: 0 ok · 1 computation/write failure · 2 configuration error.
The invoke wrappers call this FAIL-SOFT: a failure leaves the disposition
standing without a receipt block (honest absence), never a broken lane.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "discrimination-receipt/v1"

# ── The rider, verbatim. Travels into every emitted block. ───────────────────
RIDER_VERBATIM = (
    "no harmony/contagion disposition may be READ as discriminating until built "
    "AND ruled — your build is the first half; the ruling comes later at /review"
)
STANDING_RULE_VERBATIM = (
    "Standing rule carried forward: do not read harmony/contagion dispositions "
    "as discriminating until the receipt fields exist and the A3-732 cause is ruled."
)
DOES_NOT_DIAGNOSE = (
    "This receipt REPORTS constancy. It does NOT diagnose its cause: the A3-732 "
    "constancy investigation (t589-frozen coordinates, no TTL) rides separately "
    "and the cause is deliberately unruled."
)
RULING = (
    "audit-logs/governance/constitution-ledger/ledger.md"
    "#can-it-eat-dataflow-liveness-predicate (discrimination-axis refinement ray, "
    "/review 733) via backlog bk-harmony-discrimination-receipt"
)

ARTIFACT_RE = re.compile(r"^disposition-tic-(\d+)\.json$")


# ── Lane declarations ───────────────────────────────────────────────────────
# `tracked` names the artifact fields the receipt is computed over, as dotted
# paths with declared fallbacks (older packets carried meaningState under
# acousticSignature). `condition` is the DECLARED discriminating condition,
# transcribed from the engine's own deciding code — never invented here; the
# `excerpt` markers pull that deciding code VERBATIM out of the engine at run
# time, so this declaration cannot silently drift from the engine it describes.
LANES = {
    "harmony": {
        "history_subdir": "audit-logs/harmony",
        "tracked": [
            ("disposition.stance", []),
            ("meaningState", ["acousticSignature.meaningState", "ecotone.meaningState"]),
        ],
        "engine": "autonomous_kernel/harmony_engine_v0/runtime/harmony-engine.mjs",
        "engine_symbols": ["synthesizeEcotoneState()", "composeDisposition()"],
        "excerpt_markers": [
            ("  let meaningState = 'preserved';", "  return { meaningState,"),
            ("  const stance = wisdomStance ?? stanceFor(meaningState);",
             "  const stance = wisdomStance ?? stanceFor(meaningState);"),
        ],
        "condition": (
            "disposition.stance = input.wisdomStance when the input builder supplies one, "
            "else stanceFor(meaningState); meaningState is decided by the ecotone threshold "
            "ladder in synthesizeEcotoneState() over the ACTIVE (Layer-3-eligible) rays. "
            "The emitted value therefore varies if and only if EITHER (a) the wisdomStance "
            "the input builder supplies changes, OR (b) with no wisdomStance, the active-ray "
            "population crosses one of the ladder's own thresholds: "
            "hasRefusal && maxCollapseRisk>0.45 -> abused; hasRefusal -> refused; "
            "hasRepair && (hasBoundary || trustImplicationCount>0) -> repairable; "
            "maxCollapseRisk>0.68 || (hasBoundary && maxMeaningPressure>0.65) -> violated; "
            "dissonance>0.58 && avgEcotonePressure>receiver.toleranceForDissonance -> contested; "
            "maxMeaningPressure>0.48 || avgEcotonePressure>0.4 || trustImplicationCount>0 -> strained; "
            "avgEcotonePressure>0.32 && acoustic.snr>0.45 -> held_open; else preserved. "
            "Nothing else in the packet (ambient voice phrasing, snr magnitude, ray count, "
            "packetId) can move the tracked value."
        ),
    },
    "contagion": {
        "history_subdir": "audit-logs/contagion",
        "tracked": [
            ("meaningState", []),
        ],
        "engine": "autonomous_kernel/contagion_match_v0/runtime/contagion-engine.mjs",
        "engine_symbols": ["classifyInterval()", "runContagionEngine() step 3"],
        "excerpt_markers": [
            ("function classifyInterval(cos) {", "}"),
            ("  let meaningState;", '  else meaningState = "off-field";'),
        ],
        "condition": (
            "meaningState is a pure function of topBand, and topBand = "
            "classifyInterval(cosine(currentShape, nearest learned coordinate's shapeVector)) "
            "at the OT band edges 0.85 / 0.5 / 0.2 "
            "(Consonant->anchored, Parallel->resonant, Tension->tensioned, else off-field). "
            "The emitted value therefore varies if and only if the top-1 "
            "conformation-proximity cosine crosses one of those three band edges. "
            "No other input can move it: pattern text is carried for human legibility only "
            "and never enters the proximity computation (fence #2), and epitaph proximity, "
            "posture, office and geometry feed only the caution/invitation prose. "
            "disposition.stance is 1:1 with meaningState in this engine."
        ),
    },
}


# ── Helpers ─────────────────────────────────────────────────────────────────
def _dotted(doc, path):
    cur = doc
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _tracked_value(doc, tracked):
    """Extract the tracked value dict from one artifact, honoring declared fallbacks."""
    out = {}
    for path, fallbacks in tracked:
        val = _dotted(doc, path)
        if val is None:
            for fb in fallbacks:
                val = _dotted(doc, fb)
                if val is not None:
                    break
        out[path] = val
    return out


def scan_history(history_dir: Path, tracked, as_of_tic=None):
    """Read the FULL retained corpus. Returns (rows, unreadable).

    rows: [(tic, tracked_value_dict)] ascending by tic.
    unreadable: [{"file":..., "error":...}] — declared negative space, never
    silently dropped (a corpus hole that vanished from the count would be the
    very laundering this receipt exists to stop).
    """
    rows, unreadable = [], []
    if not history_dir.is_dir():
        return rows, unreadable
    for path in sorted(history_dir.iterdir()):
        m = ARTIFACT_RE.match(path.name)
        if not m:
            continue
        tic = int(m.group(1))
        if as_of_tic is not None and tic > as_of_tic:
            continue
        try:
            doc = json.loads(path.read_text())
        except Exception as exc:  # noqa: BLE001 — every failure is disclosed
            unreadable.append({"file": path.name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        rows.append((tic, _tracked_value(doc, tracked)))
    rows.sort(key=lambda r: r[0])
    return rows, unreadable


def _engine_excerpt(engine_path: Path, markers):
    """Pull the engine's OWN deciding code verbatim, so the declared condition
    cannot drift from the code it claims to describe. Fail-soft + loud: a
    missing marker yields an explicit extraction status, never a fabricated
    excerpt."""
    if not engine_path.is_file():
        return [], f"unavailable:engine_source_not_found:{engine_path.name}", None
    text = engine_path.read_text()
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    lines = text.splitlines()
    excerpts, missing = [], []
    for start, end in markers:
        # Markers are line PREFIXES: an engine line may carry a long tail (the
        # harmony ladder's return statement does) and we still want the whole
        # line verbatim, never a truncated quote.
        i = next((k for k, ln in enumerate(lines) if ln.startswith(start)), None)
        if i is None:
            missing.append(start)
            continue
        if start == end:
            j = i
        else:
            j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith(end)), None)
            if j is None:
                missing.append(end)
                j = i
        excerpts.append("\n".join(lines[i:j + 1]))
    status = "live" if not missing else "partial:markers_not_found:" + "|".join(missing)
    return excerpts, status, sha


def build_receipt(lane: str, repo: Path, current_doc=None, as_of_tic=None):
    """Compute the discrimination receipt block for `lane`."""
    if lane not in LANES:
        raise KeyError(f"unknown lane {lane!r}; known: {sorted(LANES)}")
    spec = LANES[lane]
    history_dir = repo / spec["history_subdir"]
    tracked = spec["tracked"]

    rows, unreadable = scan_history(history_dir, tracked, as_of_tic)
    if not rows:
        raise ValueError(f"no retained artifacts under {history_dir}")

    emitted_tic, current_value = rows[-1][0], rows[-1][1]
    if current_doc is not None:
        # The just-written packet is authoritative for its own value even if the
        # on-disk read raced; keep them reconciled rather than guessing.
        current_value = _tracked_value(current_doc, tracked)
        rows[-1] = (emitted_tic, current_value)

    # Walk backwards while the tracked value is identical — FULL history, no cap.
    run_start = len(rows) - 1
    for i in range(len(rows) - 1, -1, -1):
        if rows[i][1] == current_value:
            run_start = i
        else:
            break
    run = rows[run_start:]
    never_changed = run_start == 0
    prev = None if never_changed else rows[run_start - 1]

    excerpts, extraction, sha = _engine_excerpt(repo / spec["engine"], spec["excerpt_markers"])
    distinct = {json.dumps(v, sort_keys=True, ensure_ascii=False) for _, v in rows}

    return {
        "schema": SCHEMA,
        "lane": lane,
        "emitted_at_tic": emitted_tic,
        # ── the withheld thing, said out loud ────────────────────────────────
        "ratified": False,
        "rider": RIDER_VERBATIM,
        "standing_rule": STANDING_RULE_VERBATIM,
        "does_not_diagnose": DOES_NOT_DIAGNOSE,
        "ruling": RULING,
        # ── (a) last_change_tic ─────────────────────────────────────────────
        "last_change_tic": (None if never_changed else run[0][0]),
        "last_change_semantics": (
            "the tic at which the currently-emitted tracked value FIRST appears in the "
            "retained history — i.e. the emission at which the content last actually "
            "changed. null means the value has NEVER changed across the full retained "
            "history. The immediately-prior differing emission is previous_distinct_tic."
        ),
        "previous_distinct_tic": (None if never_changed else prev[0]),
        "previous_distinct_value": (None if never_changed else prev[1]),
        "never_changed_in_retained_history": never_changed,
        # ── (b) consecutive_identical_count — FULL history, never a window ──
        "consecutive_identical_count": len(run),
        "consecutive_identical_count_basis": (
            "count of retained emissions whose tracked value is identical to this one, "
            "INCLUSIVE of this emission, over the FULL retained history — never a rolling "
            "or capped window. Tic gaps inside the run are counted as artifacts, not tics."
        ),
        "identical_run_tic_span": [run[0][0], run[-1][0]],
        # ── (c) the declared discriminating condition ───────────────────────
        "declared_discriminating_condition": {
            "condition": spec["condition"],
            "declared_in": spec["engine"],
            "declared_symbols": spec["engine_symbols"],
            "contract_excerpt": excerpts,
            "contract_source_sha256": sha,
            "extraction": extraction,
            "note": (
                "Declared from the lane's own deciding code, not invented by the receipt. "
                "The excerpt is pulled verbatim from the engine at emit time; if it ever "
                "reads 'partial:markers_not_found', the engine moved and the declaration "
                "is owed a re-derivation."
            ),
        },
        # ── scope / apophatic disclosure ────────────────────────────────────
        "tracked_fields": [p for p, _ in tracked],
        "tracked_value": current_value,
        "history_scanned": {
            "dir": spec["history_subdir"],
            "pattern": "disposition-tic-*.json",
            "first_tic": rows[0][0],
            "last_tic": rows[-1][0],
            "artifacts_scanned": len(rows),
            "window": None,
            "as_of_tic": as_of_tic,
            "unreadable_artifacts": unreadable,
            "scope": (
                "the retained on-disk corpus, observer-indexed — this makes NO claim "
                "about tics whose artifacts were never written or no longer retained."
            ),
        },
        "distinct_tracked_values_in_retained_history": len(distinct),
        "computed_by": "cgg-runtime/scripts/discrimination-receipt.py",
    }


def stamp(lane: str, disposition_path: Path, repo: Path) -> dict:
    """Compute + write the block into the disposition packet (additive key)."""
    doc = json.loads(disposition_path.read_text())
    block = build_receipt(lane, repo, current_doc=doc)
    doc["discrimination_receipt"] = block
    # ensure_ascii=False keeps every pre-existing string byte-for-byte as the
    # engine wrote it (JSON.stringify emits raw UTF-8); indent=2 matches both
    # the engine and the voice step.
    disposition_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False))
    return block


# ── Selftest ────────────────────────────────────────────────────────────────
def _fixture_corpus(tmp: Path, values, lane="contagion"):
    tmp.mkdir(parents=True, exist_ok=True)
    for tic, val in values:
        (tmp / f"disposition-tic-{tic}.json").write_text(json.dumps({"meaningState": val}))


def selftest() -> int:  # noqa: C901 — a flat table of arms reads better here
    import tempfile

    passed, failed = [], []

    def check(name, cond, detail=""):
        (passed if cond else failed).append(f"{name}{(' — ' + detail) if detail else ''}")
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # Arm 1 — constant corpus: never changed, count == corpus size.
        r1 = root / "r1"
        _fixture_corpus(r1 / "audit-logs" / "contagion", [(t, "resonant") for t in range(10, 20)])
        b1 = build_receipt("contagion", r1)
        check("A1 constant corpus: never_changed_in_retained_history",
              b1["never_changed_in_retained_history"] is True)
        check("A1 constant corpus: last_change_tic is null (honest, not fabricated)",
              b1["last_change_tic"] is None)
        check("A1 constant corpus: count == 10 (full corpus)",
              b1["consecutive_identical_count"] == 10, str(b1["consecutive_identical_count"]))

        # Arm 2 — NEGATIVE CONTROL: a changed value resets the counter.
        r2 = root / "r2"
        vals = [(t, "resonant") for t in range(10, 17)] + [(t, "tensioned") for t in range(17, 20)]
        _fixture_corpus(r2 / "audit-logs" / "contagion", vals)
        b2 = build_receipt("contagion", r2)
        check("A2 negative control: count RESETS to 3 after the change",
              b2["consecutive_identical_count"] == 3, str(b2["consecutive_identical_count"]))
        check("A2 negative control: last_change_tic == 17 (first tic of the new value)",
              b2["last_change_tic"] == 17, str(b2["last_change_tic"]))
        check("A2 negative control: previous_distinct_tic == 16",
              b2["previous_distinct_tic"] == 16, str(b2["previous_distinct_tic"]))
        check("A2 negative control: never_changed is False",
              b2["never_changed_in_retained_history"] is False)

        # Arm 3 — change AT the latest emission: count == 1.
        r3 = root / "r3"
        _fixture_corpus(r3 / "audit-logs" / "contagion",
                        [(t, "resonant") for t in range(10, 19)] + [(19, "anchored")])
        b3 = build_receipt("contagion", r3)
        check("A3 change at the newest emission: count == 1",
              b3["consecutive_identical_count"] == 1, str(b3["consecutive_identical_count"]))

        # Arm 4 — no window: a 200-artifact constant run counts 200, not a cap.
        r4 = root / "r4"
        _fixture_corpus(r4 / "audit-logs" / "contagion", [(t, "resonant") for t in range(1, 201)])
        b4 = build_receipt("contagion", r4)
        check("A4 FULL history (no window): count == 200",
              b4["consecutive_identical_count"] == 200, str(b4["consecutive_identical_count"]))
        check("A4 window field is explicitly null", b4["history_scanned"]["window"] is None)

        # Arm 5 — tic gaps inside a run are counted as artifacts, not tics.
        r5 = root / "r5"
        _fixture_corpus(r5 / "audit-logs" / "contagion", [(10, "resonant"), (12, "resonant"), (13, "resonant")])
        b5 = build_receipt("contagion", r5)
        check("A5 tic gaps: count == 3 artifacts across span 10..13",
              b5["consecutive_identical_count"] == 3 and b5["identical_run_tic_span"] == [10, 13],
              f'{b5["consecutive_identical_count"]} span={b5["identical_run_tic_span"]}')

        # Arm 6 — an unreadable artifact is DECLARED, never silently dropped.
        r6 = root / "r6"
        d6 = r6 / "audit-logs" / "contagion"
        _fixture_corpus(d6, [(t, "resonant") for t in range(10, 14)])
        (d6 / "disposition-tic-11.json").write_text("{ this is not json")
        b6 = build_receipt("contagion", r6)
        check("A6 unreadable artifact disclosed in history_scanned.unreadable_artifacts",
              [u["file"] for u in b6["history_scanned"]["unreadable_artifacts"]] == ["disposition-tic-11.json"],
              json.dumps(b6["history_scanned"]["unreadable_artifacts"]))
        check("A6 unreadable artifact excluded from artifacts_scanned (3, not 4)",
              b6["history_scanned"]["artifacts_scanned"] == 3,
              str(b6["history_scanned"]["artifacts_scanned"]))

        # Arm 7 — the rider + ratified:false travel in the block itself.
        check("A7 rider verbatim present in the block", b1["rider"] == RIDER_VERBATIM)
        check("A7 standing rule verbatim present in the block", b1["standing_rule"] == STANDING_RULE_VERBATIM)
        check("A7 ratified is False", b1["ratified"] is False)

        # Arm 8 — harmony's two-field tracking discriminates on EITHER field.
        r8 = root / "r8"
        h8 = r8 / "audit-logs" / "harmony"
        h8.mkdir(parents=True)
        for t in range(10, 15):
            (h8 / f"disposition-tic-{t}.json").write_text(json.dumps(
                {"meaningState": "strained", "disposition": {"stance": "hold-open-with-boundary"}}))
        (h8 / "disposition-tic-15.json").write_text(json.dumps(
            {"meaningState": "strained", "disposition": {"stance": "SOMETHING-ELSE"}}))
        b8 = build_receipt("harmony", r8)
        check("A8 harmony: a stance-only change resets the count (count == 1)",
              b8["consecutive_identical_count"] == 1, str(b8["consecutive_identical_count"]))
        check("A8 harmony: tracked_fields are the two declared paths",
              b8["tracked_fields"] == ["disposition.stance", "meaningState"],
              str(b8["tracked_fields"]))

        # Arm 9 — declared condition carries live engine provenance when the
        # real repo is reachable (fixture roots have no engine → honest status).
        b9 = build_receipt("contagion", r6)
        check("A9 absent engine source yields an explicit unavailable status, not a fake excerpt",
              b9["declared_discriminating_condition"]["extraction"].startswith("unavailable:")
              and b9["declared_discriminating_condition"]["contract_excerpt"] == [],
              b9["declared_discriminating_condition"]["extraction"])

    print()
    print(f"RESULT: {len(passed)}/{len(passed) + len(failed)} — " + ("OK" if not failed else "FAILURES"))
    for f in failed:
        print(f"  FAILED: {f}")
    return 0 if not failed else 1


# ── CLI ─────────────────────────────────────────────────────────────────────
def _repo_root(explicit=None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    here = Path(__file__).resolve().parent
    for cur in [here] + list(here.parents):
        if (cur / ".federation-root").exists() or (cur / "audit-logs").is_dir():
            return cur
    return Path.cwd()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lane", choices=sorted(LANES))
    ap.add_argument("--disposition", help="disposition packet to stamp (emit-side)")
    ap.add_argument("--repo", help="repo root override (test isolation)")
    ap.add_argument("--as-of-tic", type=int, help="read-only: compute as the corpus stood at this tic")
    ap.add_argument("--stdout-only", action="store_true", help="print the block; write nothing")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.lane:
        print("ERROR: --lane is required (or --selftest)", file=sys.stderr)
        return 2

    repo = _repo_root(args.repo)
    try:
        if args.stdout_only or not args.disposition:
            block = build_receipt(args.lane, repo, as_of_tic=args.as_of_tic)
            print(json.dumps(block, indent=2, ensure_ascii=False))
            return 0
        path = Path(args.disposition)
        if not path.is_file():
            print(f"ERROR: disposition not found: {path}", file=sys.stderr)
            return 2
        block = stamp(args.lane, path, repo)
        print(
            f"discrimination receipt [{args.lane}] tic={block['emitted_at_tic']} "
            f"consecutive_identical_count={block['consecutive_identical_count']} "
            f"last_change_tic={block['last_change_tic']} "
            f"(full history: {block['history_scanned']['artifacts_scanned']} artifacts, "
            f"tics {block['history_scanned']['first_tic']}..{block['history_scanned']['last_tic']}) "
            f"ratified=false"
        )
        return 0
    except Exception as exc:  # noqa: BLE001 — the wrapper is fail-soft; be loud here
        print(f"ERROR: discrimination receipt failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
