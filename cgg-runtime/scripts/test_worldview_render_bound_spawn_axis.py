#!/usr/bin/env python3
"""test_worldview_render_bound_spawn_axis.py — bk-worldview-render-spawn-omit-and-badge, tic 739.

RATIFIED /review 738 (n=3 verbatim recurrence: A4-736 · A5-737 · A5-738 — the same defect
reported three tics running, priority RAISED on the recurrence).

THE DEFECT THIS SUITE PINS. The ⟨RENDER-BOUND⟩ marker's follow-surface command is the
instruction a budget-sealed citizen ACTUALLY RUNS to expand its own packet — and it was built
WITHOUT the spawn coordinate. So a citizen that WAS handed a spawn id at boot re-rendered
through the UNDECLARED arm, and the fresh receipt frame then told it, imperatively, to
"OMIT --spawn-id entirely" — stripping a REAL supplied coordinate — while the re-rendered
`owed:` line dropped spawn_id to match. Two reported axes, ONE root: the re-render command did
not PROPAGATE the resolved spawn identity. The conditional arms of render_receipt_frame were
already correct for the direct render (tic 735); nothing there needed changing.

THE IDENTITY-SOURCE LAW, ASSERTED. The re-render's spawn-axis ray must derive from the SAME
resolution that produced the boot identity — propagation, never re-derivation, never a flat
"you have no spawn id" claim, never key-availability. `_render_bound_marker` therefore asserts
NOTHING about spawn identity; it CARRIES the one its caller was given. The tests below check
the carry, both arms, at unit AND at live-render altitude.

TWO NEGATIVE-CONTROL ARMS, both required by the ruling:
  (i)  KEYED   — a render WITH a spawn id emits a follow-surface carrying `--spawn-id <that id>`,
                 and executing it yields the CONCRETE arm + `· spawn_id` in the owed list.
  (ii) UNKEYED — a render WITHOUT one emits the marker BYTE-IDENTICAL to its pre-cure form (the
                 pre-cure literal is pinned here, so this is a real byte claim and not a
                 tautology), with no spurious flag anywhere.
Plus a REVERT control that mutates the real source back to the pre-cure call and proves the
keyed arm loses the flag — i.e. this suite discriminates rather than passing vacuously.

RUN: python3 -m pytest test_worldview_render_bound_spawn_axis.py -q
"""
import importlib.util
import re
import shlex
import subprocess
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_OW_PATH = _HERE / "office-worldview.py"
_BR_PATH = _HERE / "boot-receipt.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ow = _load(_OW_PATH, "office_worldview_renderbound_spawn_ro") if _OW_PATH.is_file() else None
br = _load(_BR_PATH, "boot_receipt_renderbound_spawn_ro") if _BR_PATH.is_file() else None

SPAWN = "agent_wave9_sibling_B"
OTHER = "agent_wave9_sibling_A"
OFFICE = "ent_homeskillet"
TIC = 739

# Enough omitted rays that the manifest renders its "+k more" tail as it does live.
_FRAGS = [{"id": f"lane.{i}", "pertinence": {"class": "FIELD"}} for i in range(9)]


def _marker(spawn="", frags=None, office=OFFICE, tic=TIC):
    return ow._render_bound_marker(frags or _FRAGS, office, tic, spawn)


def _follow_surface(text: str) -> str:
    """The command the marker actually tells a reader to run (between the backticks)."""
    m = re.search(r"re-render `([^`]+)`", text)
    assert m, f"no follow-surface command found in: {text!r}"
    return m.group(1)


@unittest.skipIf(ow is None, "office-worldview.py not present")
class TheMarkerCarriesTheResolvedSpawn(unittest.TestCase):

    def test_KEYED_arm_puts_the_concrete_spawn_on_the_follow_surface(self):
        """ARM (i). The whole increment in one assertion: the coordinate reaches the command."""
        self.assertIn(f"--spawn-id {SPAWN}", _follow_surface(_marker(SPAWN)))

    def test_the_flag_carries_THIS_spawn_not_merely_SOME_spawn(self):
        """Propagation, not decoration — a hardcoded or stale key would pass a weaker test."""
        self.assertIn(f"--spawn-id {OTHER}", _follow_surface(_marker(OTHER)))
        self.assertNotIn(SPAWN, _follow_surface(_marker(OTHER)))

    def test_UNKEYED_arm_is_BYTE_IDENTICAL_to_the_pre_cure_command(self):
        """ARM (ii), as a real byte claim: the pre-cure literal is pinned right here, so the
        degrade-to-today invariant cannot rot into 'whatever the code currently emits'."""
        self_path = _OW_PATH  # the marker embeds the absolute path of the rendering copy
        expected = (f"python3 {self_path} render --office {OFFICE} --tic {TIC} --max-chars 0")
        self.assertEqual(_follow_surface(_marker("")), expected)

    def test_UNKEYED_arm_emits_no_spawn_token_anywhere_in_the_marker(self):
        self.assertNotIn("--spawn-id", _marker(""))
        self.assertNotIn("spawn", _marker("").lower())

    def test_neither_arm_emits_a_fill_in_the_blank_placeholder(self):
        """A placeholder on a copy-pasted command teaches the invented-key failure the whole
        per-spawn axis exists to prevent (sibling claim: test_boot_receipt_frame_spawn_axis)."""
        for spawn in (SPAWN, ""):
            with self.subTest(spawn=spawn or "<undeclared>"):
                m = _marker(spawn)
                self.assertNotIn("--spawn-id <", m)
                self.assertNotIn("--spawn-id …", m)
                self.assertNotIn("--spawn-id {", m)

    def test_the_command_is_shell_parseable_in_both_arms(self):
        """The follow-surface is COPY-PASTED. A command that does not lex is not an instruction."""
        for spawn in (SPAWN, ""):
            with self.subTest(spawn=spawn or "<undeclared>"):
                argv = shlex.split(_follow_surface(_marker(spawn)))
                self.assertEqual(argv[2], "render")
                self.assertIn("--max-chars", argv)
                if spawn:
                    self.assertEqual(argv[argv.index("--spawn-id") + 1], spawn)

    def test_the_manifest_half_is_undisturbed_by_the_new_axis(self):
        """The marker's OTHER contract (/review 421: name+type the negative space, no rank) must
        survive the axis — the cure adds a coordinate, it does not re-shape the aperture."""
        for spawn in (SPAWN, ""):
            with self.subTest(spawn=spawn or "<undeclared>"):
                m = _marker(spawn)
                self.assertIn("⟨RENDER-BOUND·shape-only⟩", m)
                self.assertIn("9 ray(s) omitted by RENDER, not reclassified", m)
                self.assertIn("[classes: FIELD]", m)
                self.assertIn("lane.0", m)
                self.assertIn("+3 more", m)
                # FIELD ≠ SEALED: the marker must not re-TYPE the omitted rays. The predicate is
                # the absence of a SEALED *badge* — the prose legitimately says "do not treat
                # them as SEALED-foreclosed", which is the distinction being taught, not a breach.
                self.assertNotIn("⟨SEALED", m)
                self.assertIn("do not treat them as SEALED-foreclosed", m)
                self.assertNotIn("priority_range", m)

    def test_signature_stays_backward_compatible(self):
        """Degrade-to-today at the seam: any legacy 3-arg caller must still render."""
        import inspect
        p = inspect.signature(ow._render_bound_marker).parameters
        self.assertIn("spawn_id", p)
        self.assertEqual(p["spawn_id"].default, "")
        self.assertIn("RENDER-BOUND", ow._render_bound_marker(_FRAGS, OFFICE, TIC))


@unittest.skipIf(ow is None or br is None, "office-worldview.py / boot-receipt.py not present")
class TheRoundTripCuresBothReportedAxes(unittest.TestCase):
    """THE REAL DEFECT, END TO END. Not 'the flag is in the string' but: run what the marker
    tells you to run, and read what the re-render then says about your spawn."""

    ZONE = None

    @classmethod
    def setUpClass(cls):
        cls.ZONE = str(br.zone_root())

    def _bounded_marker(self, spawn):
        cmd = [sys.executable, str(_OW_PATH), "render", "--office", OFFICE, "--tic", str(TIC),
               "--zone-root", self.ZONE, "--max-chars", "700"]
        if spawn:
            cmd += ["--spawn-id", spawn]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        line = next((l for l in r.stdout.splitlines() if "RENDER-BOUND" in l), None)
        self.assertIsNotNone(line, "the render did not bound at 700 chars — no marker to test")
        return line

    def _run_follow_surface(self, marker_line):
        argv = shlex.split(_follow_surface(marker_line))
        argv[0] = sys.executable
        argv += ["--zone-root", self.ZONE]
        r = subprocess.run(argv, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_KEYED_re_render_takes_the_CONCRETE_arm_not_the_OMIT_arm(self):
        """AXIS 1 (A4-736 / A5-737). Pre-cure this exact path told a spawn-carrying citizen to
        strip its own real coordinate."""
        out = self._run_follow_surface(self._bounded_marker(SPAWN))
        self.assertIn("pass it VERBATIM", out)
        self.assertNotIn("OMIT --spawn-id entirely", out)

    def test_KEYED_re_render_owed_line_carries_spawn_id(self):
        """AXIS 2 (A5-738). The second reported axis, cured by the same propagation."""
        out = self._run_follow_surface(self._bounded_marker(SPAWN))
        owed = next(l for l in out.splitlines() if l.strip().startswith("owed:"))
        self.assertIn("· spawn_id", owed)

    def test_KEYED_re_render_prescribes_the_SAME_spawn_the_boot_resolved(self):
        """Identity-source law: the re-render's key is the boot's key, not a fresh derivation."""
        out = self._run_follow_surface(self._bounded_marker(SPAWN))
        self.assertIn(f"--spawn-id {SPAWN}", out)
        self.assertNotIn(OTHER, out)

    def test_UNKEYED_re_render_still_teaches_OMIT_and_owes_no_spawn_id(self):
        """The omit rule is CORRECT — for the arm it belongs to. It must not be collateral."""
        out = self._run_follow_surface(self._bounded_marker(""))
        self.assertIn("OMIT --spawn-id entirely", out)
        self.assertIn("NEVER invent one", out)
        owed = next(l for l in out.splitlines() if l.strip().startswith("owed:"))
        self.assertNotIn("· spawn_id", owed)

    def test_the_render_lane_stays_READ_ONLY_across_the_whole_round_trip(self):
        """office-worldview.py is READ-ONLY by contract (LOOP-SAFETY). A test that exercises the
        live zone must prove it did not write to the receipt lane it talks about."""
        sink = br.sink_path(br.zone_root())
        before = sink.read_bytes() if sink.exists() else b""
        self._run_follow_surface(self._bounded_marker(SPAWN))
        self._run_follow_surface(self._bounded_marker(""))
        after = sink.read_bytes() if sink.exists() else b""
        self.assertEqual(before, after)


@unittest.skipIf(ow is None, "office-worldview.py not present")
class TheControlDiscriminates(unittest.TestCase):
    """REVERT CONTROL. Mutate the REAL source back to its pre-cure call and prove the keyed arm
    loses the coordinate — so a green above means the cure, not a vacuous suite."""

    CURED = "_render_bound_marker(omitted_frags, office, tic, spawn_id)"
    PRECURE = "_render_bound_marker(omitted_frags, office, tic)"

    def _reverted_module(self):
        src = _OW_PATH.read_text(encoding="utf-8")
        self.assertIn(self.CURED, src,
                      "the propagation call is absent from the real source — the cure has been "
                      "REVERTED and bk-worldview-render-spawn-omit-and-badge is re-opened")
        mutated = src.replace(self.CURED, self.PRECURE)
        self.assertNotEqual(mutated, src, "the revert did not apply")
        spec = importlib.util.spec_from_loader("office_worldview_reverted", loader=None)
        rev = importlib.util.module_from_spec(spec)
        rev.__dict__["__file__"] = str(_OW_PATH)  # self_path + lib/ resolution need it
        exec(compile(mutated, "<reverted-office-worldview>", "exec"), rev.__dict__)
        return rev

    def test_reverting_the_propagation_reproduces_the_EXACT_predicted_breakage(self):
        """The predicted breakage is specific: the marker stops carrying the spawn, so the keyed
        and unkeyed follow-surfaces collapse to the SAME command — which is precisely how a
        spawn-carrying citizen was routed into the omit arm."""
        rev = self._reverted_module()

        class _Probe:
            """Drives render_human's truncation path so the marker is built through the real
            call site, not by calling the marker builder directly (the bug WAS at the call)."""

        base = {"display": OFFICE}
        frags = [{
            "id": f"lane.{i}", "source": "s", "text": "x" * 120,
            "pertinence": {"class": "FIELD", "reason": "r"},
            "authority": dict(may_read=True, may_shape_interpretation=True, may_act_from=False,
                              may_mutate_source=False, may_quote=False, must_escalate=False),
            "methylation": {"weight": 0.45, "boost_reason": None, "suppress_reason": None},
            "receipt": {"required": False, "expected_proof": []},
        } for i in range(9)]

        def marker_of(mod, spawn):
            out = mod.render_human(OFFICE, TIC, base, frags, 700, zone_root=None,
                                   receipt_frame=False, spawn_id=spawn)
            return next(l for l in out.splitlines() if "RENDER-BOUND" in l)

        rev_keyed = _follow_surface(marker_of(rev, SPAWN))
        rev_unkeyed = _follow_surface(marker_of(rev, ""))
        self.assertNotIn("--spawn-id", rev_keyed,
                         "reverting the propagation did NOT drop the flag — the control does not "
                         "discriminate and this suite proves nothing")
        self.assertEqual(rev_keyed, rev_unkeyed,
                         "pre-cure, the keyed and unkeyed follow-surfaces were byte-identical; "
                         "the control failed to reproduce that")

        cured_keyed = _follow_surface(marker_of(ow, SPAWN))
        cured_unkeyed = _follow_surface(marker_of(ow, ""))
        self.assertIn(f"--spawn-id {SPAWN}", cured_keyed)
        self.assertEqual(rev_unkeyed, cured_unkeyed,
                         "the UNKEYED path is not byte-identical across the cure — the "
                         "degrade-to-today invariant regressed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
