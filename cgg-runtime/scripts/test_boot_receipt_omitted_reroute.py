#!/usr/bin/env python3
"""Tests for boot-receipt.py --omitted-range apophatic REROUTE (tic 482 footgun fix).

The tic-474 guard WARNED that --omitted-range (a legacy alias whose NAME means render-bounded
negative space) was still filed as required_unread_ranges gate debt — but left the footgun firing:
an agent declaring RENDER-bounded rays via --omitted-range silently self-DoS'd the very boot whose
loop it was closing. This makes the guard's classification LOAD-BEARING — apophatic-reading values
reroute to the non-blocking apophatic field; non-apophatic values stay blocking (legacy preserved).
Live instance + 2nd conformation of cpr_named_footgun_guard_leaves_sibling_site_unfixed_tic481.

These cases test the pure helper + the gate predicate directly — nothing touches the real sink
(zone_root() walks from __file__, so a subprocess emit would write to the real receipts ledger).

Run:  python3 -m unittest test_boot_receipt_omitted_reroute   (from cgg-runtime/scripts/)
"""
import importlib.util
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "boot_receipt", os.path.join(_HERE, "boot-receipt.py")
)
br = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(br)


def _rec(req_unread, rerouted, pertinence=None):
    """Build the boot-read slice of a receipt the way emit() does, to feed boot_read_passes()."""
    apophatic = list(rerouted)
    rec = {
        "full_boot_injection_read": True,
        "boot_read_mode": "full",
        "chunking": "gapless",
        "required_unread_ranges": req_unread,
        "omitted_ranges": req_unread,
    }
    if apophatic:
        rec["apophatic_range_bounds"] = apophatic
    if pertinence:
        rec["pertinence_rationale"] = pertinence
    return rec


class ClassifyBootReadRanges(unittest.TestCase):
    def test_apophatic_value_reroutes_off_the_blocking_set(self):
        # The exact shape that blocked the tic-482 orchestrator boot.
        req, rerouted = br.classify_boot_read_ranges(
            None, ["worldview:25-rays-render-bounded (telos.founding,...)"]
        )
        self.assertEqual(req, [], "apophatic value must NOT land in the blocking set")
        self.assertEqual(len(rerouted), 1, "apophatic value must reroute to the non-blocking set")

    def test_non_apophatic_omitted_value_stays_blocking(self):
        # No marker token -> genuine required-unread -> legacy blocking semantics preserved.
        req, rerouted = br.classify_boot_read_ranges(None, ["section 5: the middle I skipped"])
        self.assertEqual(req, ["section 5: the middle I skipped"])
        self.assertEqual(rerouted, [])

    def test_mixed_split_per_value(self):
        req, rerouted = br.classify_boot_read_ranges(
            None,
            ["boot-injections:6-pointers omitted by budget", "ledger rows 40-80 I did not read"],
        )
        self.assertEqual(req, ["ledger rows 40-80 I did not read"])
        self.assertEqual(len(rerouted), 1)

    def test_explicit_required_unread_is_always_blocking(self):
        # --required-unread-range never reroutes, even with a marker word in it.
        req, rerouted = br.classify_boot_read_ranges(["render-pipeline section UNREAD"], None)
        self.assertEqual(req, ["render-pipeline section UNREAD"])
        self.assertEqual(rerouted, [])

    def test_required_plus_omitted_apophatic_combine_correctly(self):
        req, rerouted = br.classify_boot_read_ranges(
            ["real unread block"], ["field-class rays expand if pertinent"]
        )
        self.assertEqual(req, ["real unread block"])
        self.assertEqual(len(rerouted), 1)

    def test_empty_inputs(self):
        self.assertEqual(br.classify_boot_read_ranges(None, None), ([], []))
        self.assertEqual(br.classify_boot_read_ranges([], []), ([], []))


class GateOutcome(unittest.TestCase):
    """The reroute changes the gate outcome from a SILENT over-block to either a self-heal
    (when justified) or an HONEST aperture-justification block."""

    def test_self_heal_apophatic_plus_pertinence_passes(self):
        # The tic-482 orchestrator's natural first emit: render-bounded rays + a pertinence rationale.
        req, rerouted = br.classify_boot_read_ranges(
            None, ["worldview:25-rays-render-bounded", "boot-injections:6-pointers-render-bounded"]
        )
        rec = _rec(req, rerouted, pertinence="FIELD-class doctrine already resident in CLAUDE.md")
        passes, reason = br.boot_read_passes(rec)
        self.assertTrue(passes, f"apophatic reroute + pertinence must PASS the gate, got: {reason}")

    def test_apophatic_without_pertinence_blocks_honestly(self):
        # Reroute still blocks if unjustified — but on the HONEST "justify your aperture" reason,
        # not the dishonest "you left required material unread" reason.
        req, rerouted = br.classify_boot_read_ranges(None, ["render-bounded rays"])
        rec = _rec(req, rerouted, pertinence=None)
        passes, reason = br.boot_read_passes(rec)
        self.assertFalse(passes)
        self.assertIn("pertinence_rationale", reason)
        self.assertNotIn("required_unread_ranges non-empty", reason)

    def test_genuine_required_unread_still_blocks(self):
        # A non-apophatic --omitted-range value remains gate debt — the safety property is preserved.
        req, rerouted = br.classify_boot_read_ranges(None, ["the required middle, unread"])
        rec = _rec(req, rerouted, pertinence="irrelevant")
        passes, reason = br.boot_read_passes(rec)
        self.assertFalse(passes)
        self.assertIn("required_unread_ranges non-empty", reason)

    def test_old_silent_overblock_no_longer_happens(self):
        # Direct regression on the tic-482 defect: render-bounded rays must NOT produce a
        # required_unread_ranges-non-empty block.
        req, rerouted = br.classify_boot_read_ranges(
            None, ["worldview:25-rays-render-bounded (expand if pertinent)"]
        )
        self.assertEqual(req, [], "render-bounded rays must not become required_unread gate debt")


if __name__ == "__main__":
    unittest.main()
