#!/usr/bin/env python3
"""
Review Test — widened genuine-vs-known sweep (bk-review-close-check-widen-sweep-tic593).

Guards the two additive false-positive guards on review-close-check's
genuine-vs-known classifier (cpr_mogul_review_close_check_ef53d403628a, tic 592,
/review 593 DEFER->backlog). Before this fix the classifier's target sweep was too
narrow in two ways, so a promotion that landed as BEHAVIOR or as a rephrased
Evidence-anchor refinement false-graded GENUINE (an error-severity hazard):

  (a) it OMITTED the behavioral/receipt surfaces where a promotion is operationalized
      (cable-receipts, honesty-lock drive_mode notes, conformation records) — sweeping
      ONLY the named doctrine target file. -> reason `affirmed_via_receipts`.
  (b) it treated an Evidence-ANCHOR reference line that CITES the born-id (frequently
      with the extractor-appended `_tic<N>` suffix dropped) as ABSENCE rather than as
      a PRESENT-but-rephrased anchor. -> reason `anchor_present_text_rephrased`.

Proven false-positive (acceptance case, tic 592):
cpr_hoist_s6_close_anchor_must_track_proposal_head_tic590 graded genuine/orphaned
although its anchor IS present at hoist-wave-engine-spec-tic495.md:213 (an explicit
"Evidence:" line citing the born) AND affirmed across 6 tic-591 S-cable receipts.

This test pins, on isolated fixtures (no dependency on live governance state):
  1. (b) Evidence-anchor form — a doctrine .md citing the born on an Evidence line
     (tic suffix dropped) classifies anchor_present_text_rephrased, NOT genuine.
  2. (a) receipt-surface form — a born cited in a cable-receipt (full id) classifies
     affirmed_via_receipts, NOT genuine, when the doctrine target lacks the text.
  3. (a) receipt-surface form via a conformation record with the BORN form (no tic).
  4. NEGATIVE — a genuinely-missing promotion (no anchor, no receipt) stays GENUINE
     (reason None): the widening must not blanket-downgrade real hazards.
  5. SCOPE DISCIPLINE — a born cited ONLY in a non-receipt pipeline surface
     (queue.jsonl) must NOT affirm: the sweep is bounded to receipt roots, never all
     of audit-logs (else every promotion is trivially "found").
  6. helper units — tic-suffix strip, born-id variants, evidence-marker gating.

Run: python3 test_widen_sweep_receipt_and_evidence_anchor_tic593.py  (pytest-discoverable)
"""
import importlib.util
import json
import os
import sys
import tempfile

_SCRIPT = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "review-close-check.py"))


def _load():
    spec = importlib.util.spec_from_file_location("review_close_check", _SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _promoted_cpr(cpr_id, lesson, promoted_to):
    return {
        "id": cpr_id,
        "status": "promoted",
        "tier": "tier1",
        "lesson": lesson,
        "promoted_to": promoted_to,
    }


# ---------------------------------------------------------------------------
# (b) Evidence-anchor citation -> anchor_present_text_rephrased
# ---------------------------------------------------------------------------

def test_evidence_anchor_line_citing_born_classifies_anchor_present():
    m = _load()
    m._RECEIPT_INDEX_CACHE.clear()
    with tempfile.TemporaryDirectory() as d:
        # Doctrine spec cites the born on an Evidence line WITHOUT the `_tic590`
        # suffix — the exact shape of the proven false-positive.
        _write(
            os.path.join(d, "audit-logs", "governance", "spec.md"),
            "# Spec\n\n"
            "### The widget close-anchor must track the head\n"
            "- **Pattern:** a loop-close stays valid even as the head advances.\n"
            "- **Evidence:** tic 590 (born `cpr_widget_close_anchor`); "
            "re-affirmed in the tic-591 cable receipt.\n",
        )
        cpr = _promoted_cpr(
            "cpr_widget_close_anchor_tic590",
            "A lesson body deliberately NOT quoted verbatim in the spec.",
            "audit-logs/governance/spec.md",
        )
        reason, ev = m.classify_known_reason(
            cpr["id"], cpr, d, project_basename=os.path.basename(d))
        assert reason == m.REASON_ANCHOR_PRESENT, (
            f"evidence-anchor citation must classify anchor_present_text_rephrased, "
            f"got {reason}")
        assert "evidence_anchor_line" in ev, ev
        assert "cpr_widget_close_anchor" in ev["evidence_anchor_line"], ev


# ---------------------------------------------------------------------------
# (a) receipt-surface sweep -> affirmed_via_receipts
# ---------------------------------------------------------------------------

def test_born_cited_in_cable_receipt_classifies_affirmed_via_receipts():
    m = _load()
    m._RECEIPT_INDEX_CACHE.clear()
    with tempfile.TemporaryDirectory() as d:
        # Doctrine target carries NO born-id and NO evidence marker -> the anchor
        # axis must not fire; only the receipt sweep can save this from GENUINE.
        _write(
            os.path.join(d, "audit-logs", "governance", "plain.md"),
            "# Plain\nUnrelated prose with no citation.\n",
        )
        # Cable-receipt carries the FULL born id (behavioral operationalization).
        _write(
            os.path.join(d, "audit-logs", "governance", "harpoon-office",
                         "cable-receipts", "S6_receipt-tic591.json"),
            json.dumps({"cable": "S6", "drive_mode": "hand",
                        "born_ref": "cpr_gadget_shipped_tic590"}),
        )
        cpr = _promoted_cpr(
            "cpr_gadget_shipped_tic590",
            "Lesson text absent from the named doctrine target.",
            "audit-logs/governance/plain.md",
        )
        reason, ev = m.classify_known_reason(
            cpr["id"], cpr, d, project_basename=os.path.basename(d))
        assert reason == m.REASON_AFFIRMED_VIA_RECEIPTS, (
            f"born cited in a cable-receipt must classify affirmed_via_receipts, "
            f"got {reason}")
        assert any("cable-receipts" in s for s in ev.get("affirming_surfaces", [])), ev


def test_born_form_in_conformation_record_affirms_via_tic_strip():
    m = _load()
    m._RECEIPT_INDEX_CACHE.clear()
    with tempfile.TemporaryDirectory() as d:
        _write(
            os.path.join(d, "audit-logs", "governance", "plain.md"),
            "# Plain\nUnrelated prose.\n",
        )
        # Conformation cites the BORN form (no `_tic` suffix) — the queue id carries
        # `_tic590`; tic-suffix stripping must bridge the two.
        _write(
            os.path.join(d, "audit-logs", "conformations", "tic-591.json"),
            json.dumps({"tic": 591, "affirmed": ["cpr_thing_done"]}),
        )
        cpr = _promoted_cpr(
            "cpr_thing_done_tic590",
            "Lesson not in target.",
            "audit-logs/governance/plain.md",
        )
        reason, _ev = m.classify_known_reason(
            cpr["id"], cpr, d, project_basename=os.path.basename(d))
        assert reason == m.REASON_AFFIRMED_VIA_RECEIPTS, (
            f"born form in a conformation record must affirm via tic-strip, got {reason}")


# ---------------------------------------------------------------------------
# NEGATIVE + SCOPE guards — the widening must not over-downgrade real hazards
# ---------------------------------------------------------------------------

def test_genuinely_missing_promotion_stays_genuine():
    m = _load()
    m._RECEIPT_INDEX_CACHE.clear()
    with tempfile.TemporaryDirectory() as d:
        _write(
            os.path.join(d, "audit-logs", "governance", "spec.md"),
            "# Spec\nNo citation of the born anywhere here.\n",
        )
        # Receipt surface exists but names a DIFFERENT born.
        _write(
            os.path.join(d, "audit-logs", "conformations", "tic-591.json"),
            json.dumps({"affirmed": ["cpr_some_other_born_tic400"]}),
        )
        cpr = _promoted_cpr(
            "cpr_actually_missing_tic590",
            "Lesson genuinely absent.",
            "audit-logs/governance/spec.md",
        )
        reason, ev = m.classify_known_reason(
            cpr["id"], cpr, d, project_basename=os.path.basename(d))
        assert reason is None, (
            f"a genuinely-missing promotion must stay GENUINE (reason None), got {reason}")
        assert "genuinely missing" in ev.get("note", ""), ev


def test_born_in_nonreceipt_pipeline_surface_does_not_affirm():
    m = _load()
    m._RECEIPT_INDEX_CACHE.clear()
    with tempfile.TemporaryDirectory() as d:
        _write(
            os.path.join(d, "audit-logs", "governance", "spec.md"),
            "# Spec\nNo born citation here.\n",
        )
        # queue.jsonl (pipeline bookkeeping) names the born — but it is NOT a receipt
        # root. Sweeping it would trivially affirm EVERY promotion; it must not count.
        _write(
            os.path.join(d, "audit-logs", "cprs", "queue.jsonl"),
            json.dumps({"id": "cpr_pipeline_only_tic590", "status": "promoted"}) + "\n",
        )
        cpr = _promoted_cpr(
            "cpr_pipeline_only_tic590",
            "Lesson absent from target.",
            "audit-logs/governance/spec.md",
        )
        reason, _ev = m.classify_known_reason(
            cpr["id"], cpr, d, project_basename=os.path.basename(d))
        assert reason is None, (
            f"a born cited only in a non-receipt pipeline surface must NOT affirm "
            f"(scope discipline), got {reason}")


def test_bare_mention_without_evidence_marker_is_not_an_anchor():
    m = _load()
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "spec.md")
        # Mentions the born but NO evidence/born/provenance/<!-- marker on the line.
        _write(p, "# Spec\n- see `cpr_widget_close_anchor` for the mechanism.\n")
        assert m._evidence_anchor_cites_born(p, "cpr_widget_close_anchor_tic590") is None


# ---------------------------------------------------------------------------
# helper units
# ---------------------------------------------------------------------------

def test_strip_tic_suffix_and_variants():
    m = _load()
    assert m._strip_tic_suffix("cpr_x_tic590") == "cpr_x"
    assert m._strip_tic_suffix("cpr_x") == "cpr_x"          # no suffix -> unchanged
    assert m._strip_tic_suffix("cpr_s6_thing_tic12") == "cpr_s6_thing"  # inner digits kept
    assert m._born_id_variants("cpr_x_tic590") == ["cpr_x_tic590", "cpr_x"]
    assert m._born_id_variants("cpr_x") == ["cpr_x"]


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{'ALL PASS' if failures == 0 else str(failures) + ' FAILED'}")
    sys.exit(1 if failures else 0)
