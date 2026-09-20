#!/usr/bin/env python3
"""Fixtures for the LIVE-RENDERED MACHINE LIMITS sentence in office-worldview.py.

RULED /review 802 round 3 (Architect, recommended option verbatim "Render live figures at
boot"); ruling receipt audit-logs/governance/receipts/2026-09-19-tic802-boot-machine-limits-
live-render-ruling.md (3,445 bytes, sha256 head-16 a6663b340d3ad9b1). Built at tic 803 by the
harpoon-build seat.

WHAT ROTTED: the boot-verbatim STANDING SUBSTRATE block printed "MACHINE LIMITS (t748):
internal disk 13-15 GiB free at 99% - NO model pull is safe; ... T7 407 GiB free but a
membrane." By /review 802 the internal volume measured 94 GiB free at 90%, and inside tic 801
alone it had moved 97 -> 92 GiB. The stale figure was not only a number: it carried a standing
caution the measurement no longer supported. A swapped constant rots within a tic, so the
figures are read AT RENDER TIME instead.

DOES-NOT-SATISFY RIDER (attached by the ruling; reproduced verbatim because a file full of
disk-reading assertions is exactly what a reader could mistake for the withheld thing):

  "this increment does NOT add the sentinel's disk arm, does NOT build the `cold_unavailable`
  reader helper, and does NOT rule or start canonical-cold Increment 2; disk headroom stays
  unobserved by the sentinel until that arm is ruled and built."

Nothing here observes disk on a schedule, emits a signal, or writes state. It renders a
sentence at boot and proves that sentence fails soft.

Arms (every documented conditional, both sides - cgg-ledger#selftest-fixtures-must-exercise-
documented-conditional-paths):
  1. both volumes readable   - live figures + capacity + read-time stamp land
  2. T7 unmounted            - `not mounted`, and NO remembered T7 number reappears
  3. a read failure          - `unmeasured`, threshold declared un-evaluable, no remembered number
  4. threshold below         - the caution fires ON the live figure
  5. threshold above         - FITS, and "safe" is NOT claimed
  6. threshold boundary      - both sides of the exact threshold value
  7. wired limit both arms   - 0 keeps its gloss; a raised limit does NOT inherit it
  8. never blocks a boot     - a malformed reading still returns a sentence, never raises
  9. block integrity         - placeholder fully substituted; the out-of-fence block is verbatim
 10. live-instrument parity  - the rendered figure agrees with `df -g`, the ruling's instrument

Run:  python3 -m unittest test_worldview_machine_limits_live_tic803  (from cgg-runtime/scripts/)
"""

import importlib.util
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

_spec = importlib.util.spec_from_file_location("office_worldview", HERE / "office-worldview.py")
ow = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ow)

# The remembered numbers. If any of these ever reappears in a rendered sentence, the fail-stale
# regression this increment cures has returned.
REMEMBERED = ("13–15 GiB", "13-15 GiB", "407 GiB", "(t748): internal")

# The rider exactly as the ruling attached it. Asserted by equality, never by substring.
RIDER = ("this increment does NOT add the sentinel's disk arm, does NOT build the "
         "`cold_unavailable` reader helper, and does NOT rule or start canonical-cold "
         "Increment 2; disk headroom stays unobserved by the sentinel until that arm is "
         "ruled and built.")

NOWSTAMP = datetime(2026, 9, 19, 11, 0, tzinfo=timezone.utc)


def _reading(internal_free=85.5, internal_cap=91, internal_ok=True, internal_err=None,
             t7_free=1494.5, t7_cap=60, t7_mounted=True, t7_ok=True, t7_err=None,
             wired_ok=True, wired_value=0, wired_err=None):
    """A synthetic reading so each arm is deterministic - the live machine is read in arm 10."""
    return {
        "read_at": NOWSTAMP.strftime("%Y-%m-%dT%H:%MZ"),
        "internal": {"path": ow.INTERNAL_DATA_VOLUME, "mounted": True, "ok": internal_ok,
                     "free_gib": internal_free, "capacity_pct": internal_cap,
                     "error": internal_err},
        "t7": {"path": ow.T7_MOUNT, "mounted": t7_mounted, "ok": t7_ok,
               "free_gib": t7_free, "capacity_pct": t7_cap, "error": t7_err},
        "wired_limit_mb": {"ok": wired_ok, "value": wired_value, "error": wired_err},
        "model_pull_threshold_gib": ow.MODEL_PULL_THRESHOLD_GIB,
        "model_pull_threshold_basis": ow.MODEL_PULL_THRESHOLD_BASIS,
    }


class BothVolumesReadable(unittest.TestCase):
    """Arm 1 - the happy path: live figures for both volumes, stamped with their read time."""

    def test_live_figures_and_capacity_render(self):
        s = ow.render_machine_limits(_reading())
        self.assertIn("internal disk 85.5 GiB free at 91%", s)
        self.assertIn("T7 1494.5 GiB free at 60% but a membrane", s)

    def test_sentence_stamps_its_own_read_time(self):
        s = ow.render_machine_limits(_reading())
        self.assertIn("read live at 2026-09-19T11:00Z", s)
        self.assertNotIn("(t748)", s, "the sentence must date itself, never a remembered tic")

    def test_threshold_value_and_basis_are_both_named(self):
        s = ow.render_machine_limits(_reading())
        self.assertIn("8.1 GiB model-pull threshold", s)
        self.assertIn("threshold basis:", s)
        self.assertIn("lane-A-affordability.json", s,
                      "the basis must cite the evidence it was read from")


class T7Unmounted(unittest.TestCase):
    """Arm 2 - the membrane is a removable disk. Unmounted is a FIRST-CLASS state."""

    def test_unmounted_says_so_and_never_recites_a_remembered_number(self):
        s = ow.render_machine_limits(_reading(t7_mounted=False, t7_ok=False,
                                              t7_free=None, t7_cap=None, t7_err="not mounted"))
        self.assertIn("T7 not mounted (a membrane when present)", s)
        for stale in REMEMBERED:
            self.assertNotIn(stale, s)

    def test_unmounted_t7_does_not_disturb_the_internal_reading(self):
        s = ow.render_machine_limits(_reading(t7_mounted=False, t7_ok=False,
                                              t7_free=None, t7_cap=None, t7_err="not mounted"))
        self.assertIn("internal disk 85.5 GiB free at 91%", s)

    def test_absent_path_reads_as_unmounted_not_as_an_error(self):
        r = ow._read_volume("/Volumes/definitely-not-a-mount-tic803")
        self.assertIs(r["mounted"], False)
        self.assertFalse(r["ok"])
        self.assertIsNone(r["free_gib"])


class ReadFailure(unittest.TestCase):
    """Arm 3 - fail-soft, never fail-stale. An unreadable volume renders `unmeasured` and
    says the threshold cannot be evaluated; it never reaches for the old number."""

    def test_unmeasured_internal_declares_the_threshold_unevaluable(self):
        s = ow.render_machine_limits(_reading(internal_ok=False, internal_free=None,
                                              internal_cap=None, internal_err="OSError"))
        self.assertIn("internal disk unmeasured (OSError)", s)
        self.assertIn("CANNOT be evaluated", s)
        self.assertIn("no remembered figure is substituted", s)

    def test_unmeasured_never_recites_a_remembered_number(self):
        s = ow.render_machine_limits(_reading(internal_ok=False, internal_free=None,
                                              internal_cap=None, internal_err="OSError"))
        for stale in REMEMBERED:
            self.assertNotIn(stale, s)
        self.assertNotIn("NO model pull is safe", s,
                         "an unmeasured volume may not carry a verdict it cannot support")

    def test_t7_read_failure_is_distinct_from_unmounted(self):
        s = ow.render_machine_limits(_reading(t7_ok=False, t7_free=None, t7_cap=None,
                                              t7_mounted=True, t7_err="PermissionError"))
        self.assertIn("T7 unmeasured (PermissionError) but a membrane", s)
        self.assertNotIn("not mounted", s)


class ThresholdArms(unittest.TestCase):
    """Arms 4-6 - the caution is a THRESHOLD ON THE LIVE FIGURE, not a baked verdict."""

    def test_below_threshold_fires_the_caution(self):
        # CONSUMER-SET CURE (/review 804, built tic 812): this arm pinned the retired verdict
        # word. The below-threshold arm now states a fits read on the named PULL threshold
        # instead of a conversion-output verdict worn by a pull threshold (F-803-BL-2).
        s = ow.render_machine_limits(_reading(internal_free=5.0, internal_cap=99))
        self.assertIn("BELOW the 8.1 GiB model-pull threshold: the largest named pending "
                      "pull DOES NOT FIT", s)

    def test_above_threshold_says_fits_and_never_claims_safe(self):
        s = ow.render_machine_limits(_reading(internal_free=85.5, internal_cap=91))
        self.assertIn("above the 8.1 GiB model-pull threshold", s)
        self.assertIn("FITS", s)
        self.assertNotIn("is safe", s,
                         "fitting one named artifact is not a safety claim - the sentence "
                         "must not promote FITS to safe")
        self.assertIn("headroom beyond that one pull is NOT assessed here", s)

    def test_exactly_at_threshold_counts_as_above(self):
        s = ow.render_machine_limits(_reading(internal_free=ow.MODEL_PULL_THRESHOLD_GIB))
        self.assertIn("above the", s)

    def test_a_hair_under_threshold_counts_as_below(self):
        s = ow.render_machine_limits(_reading(internal_free=ow.MODEL_PULL_THRESHOLD_GIB - 0.1))
        self.assertIn("BELOW the", s)

    def test_the_t748_figure_would_now_fire_the_caution(self):
        """The historical 13-15 GiB reading sits ABOVE an 8.1 GiB threshold, which is exactly
        why the caution had to become live: the frozen verdict and the frozen figure disagreed
        with each other, not merely with today's disk."""
        s = ow.render_machine_limits(_reading(internal_free=15.0, internal_cap=99))
        self.assertIn("above the", s)
        self.assertNotIn("NO model pull is safe", s)


class WiredLimitArms(unittest.TestCase):
    """Arm 7 - the gloss "one engine resident at a time" was written FOR the value 0. It may
    not be carried forward onto a value that invalidates it."""

    def test_zero_keeps_its_gloss(self):
        s = ow.render_machine_limits(_reading(wired_value=0))
        self.assertIn("iogpu.wired_limit_mb=0 — one engine resident at a time", s)

    def test_raised_limit_does_not_inherit_the_zero_gloss(self):
        s = ow.render_machine_limits(_reading(wired_value=65536))
        self.assertIn("iogpu.wired_limit_mb=65536", s)
        self.assertNotIn("one engine resident at a time", s)

    def test_unreadable_sysctl_is_unmeasured_not_zero(self):
        s = ow.render_machine_limits(_reading(wired_ok=False, wired_value=None,
                                              wired_err="FileNotFoundError"))
        self.assertIn("iogpu.wired_limit_mb=unmeasured", s)
        self.assertNotIn("iogpu.wired_limit_mb=0", s,
                         "an unreadable sysctl must never be rendered as a measured 0")


class NeverBlocksABoot(unittest.TestCase):
    """Arm 8 - a render error in this sentence never blocks a boot."""

    def test_malformed_reading_returns_a_sentence_instead_of_raising(self):
        s = ow.render_machine_limits({})
        self.assertIn("MACHINE LIMITS", s)
        self.assertIn("unmeasured", s)
        for stale in REMEMBERED:
            self.assertNotIn(stale, s)

    def test_live_read_returns_a_complete_typed_reading(self):
        r = ow.read_machine_limits()
        for key in ("read_at", "internal", "t7", "wired_limit_mb",
                    "model_pull_threshold_gib", "model_pull_threshold_basis"):
            self.assertIn(key, r)

    def test_nonexistent_t7_mount_still_renders_the_whole_block(self):
        """The ruling's explicit proof: point the T7 at a path that does not exist and the
        full STANDING SUBSTRATE render must still succeed."""
        original = ow.T7_MOUNT
        try:
            ow.T7_MOUNT = "/Volumes/no-such-mount-tic803"
            block = ow.render_standing_substrate(803)
        finally:
            ow.T7_MOUNT = original
        self.assertIn("T7 not mounted (a membrane when present)", block)
        self.assertIn("THE STANDING SUBSTRATE", block)


class BlockIntegrity(unittest.TestCase):
    """Arm 9 - the live sentence is the ONLY thing that moved. Everything else in the block
    is out of fence by the ruling's own words and must render verbatim."""

    def test_placeholder_is_fully_substituted(self):
        block = ow.render_standing_substrate(803)
        self.assertNotIn(ow.MACHINE_LIMITS_PLACEHOLDER, block,
                         "a leaked placeholder would print a token into every boot packet")
        self.assertIn("MACHINE LIMITS (read live at", block)

    def test_no_remembered_figure_survives_anywhere_in_the_block(self):
        block = ow.render_standing_substrate(803)
        for stale in REMEMBERED:
            self.assertNotIn(stale, block)

    def test_out_of_fence_block_content_is_untouched(self):
        block = ow.render_standing_substrate(803)
        for verbatim in (
            "THIRTEEN entries, not three",
            "organization-engine-lora (20G",
            "the law of this block is unchanged",
            "THE GAP IS THE JOIN, NOT ABSENCE",
            "THE PINKY — THE ECONOMICS OF A GOVERNED SUBSTRATE",
        ):
            self.assertIn(verbatim, block,
                          "the model inventory and the law of the block are OUT of fence")

    def test_rider_is_carried_verbatim_as_one_contiguous_value(self):
        """The rider must be VERBATIM, not merely present-as-wrapped-prose. The first build
        pass carried it only as a wrapped comment, so no reader could match it as a unit;
        this arm is why it now lives as a contiguous constant."""
        self.assertEqual(ow.DOES_NOT_SATISFY_RIDER_TIC803, RIDER)


class LiveInstrumentParity(unittest.TestCase):
    """Arm 10 - the rendered figure must agree with `df -g`, the instrument /review 802
    measured with. A renderer that reads a different quantity than the ruling did would be
    live and wrong at the same time."""

    def _df(self, mount):
        try:
            out = subprocess.run(["/bin/df", "-g", mount], capture_output=True, text=True,
                                 timeout=10)
        except Exception:  # noqa: BLE001
            return None
        if out.returncode != 0:
            return None
        lines = [ln for ln in out.stdout.splitlines() if ln.startswith("/dev/")]
        if not lines:
            return None
        f = lines[0].split()
        return {"avail_gib": float(f[3]), "capacity_pct": int(f[4].rstrip("%"))}

    def test_internal_volume_matches_df(self):
        ref = self._df(ow.INTERNAL_DATA_VOLUME)
        if ref is None:
            self.skipTest("df unavailable on this host")
        r = ow._read_volume(ow.INTERNAL_DATA_VOLUME)
        self.assertTrue(r["ok"])
        self.assertLessEqual(abs(r["free_gib"] - ref["avail_gib"]), 1.0,
                             "free space must match df within rounding")
        self.assertLessEqual(abs(r["capacity_pct"] - ref["capacity_pct"]), 1,
                             "capacity must be computed the way df computes it")


if __name__ == "__main__":
    unittest.main(verbosity=2)
