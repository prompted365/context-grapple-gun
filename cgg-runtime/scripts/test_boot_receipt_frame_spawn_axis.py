#!/usr/bin/env python3
"""test_boot_receipt_frame_spawn_axis.py — M1-734 legs (b) + (c), tic 735.

WHAT LANDED AND WHAT DID NOT
  (b) office-worldview.py::render_receipt_frame       — the BASH receipt prescription
  (c) subagent-citizen-boot.py::render_write_path_receipt_frame — the no-Bash WRITE-path drop
  (+) subagent-citizen-boot.py threads the harness `agent_id` into BOTH lanes
  (M2-734, hard prerequisite, same atom) receipt-drops-sweep.py hashes spawn_id

  (a) hooks/boot-read-gate.py — LANDED SEPARATELY AT TIC 735, after this suite was authored.
  Receipt: audit-logs/governance/harpoon-office/cable-receipts/bk-boot-gate-per-spawn-axis-reader-tic735.json
  This suite's rider class was written to FAIL the day that happened; it did, and it has been
  INVERTED (TheRiderIsRETIRED) rather than deleted — the retired rider text is quoted there so
  the retirement is auditable. The surviving half of the rider is the SOURCE-vs-INSTALLED
  boundary: the cure is in canonical source, and the harness fires ~/.claude/hooks/, so the
  live gate is cured only after the seat's commit + sync.

THE TWO ARMS, AND WHY THERE ARE ONLY TWO. An agent cannot read its own harness `agent_id` from
its environment (measured at tic 735: no agent/spawn variable is exported to the Bash lane), and
SubagentStart is the only seam that holds it. So a prescription containing a fill-in-the-blank
`--spawn-id <agent_id>` would be UNSERVABLE by its reader — the emitter-row/reader-predicate
mismatch cgg-ledger#boot-receipt-prescriptions-must-be-capability-gated-to-agent-tool-schema
names — and would teach citizens to invent spawn ids, which is strictly worse than an unkeyed
receipt. Hence: CONCRETE-VALUE when the boot context resolved one, explicit OMIT-INSTRUCTION
when it did not. Both arms are asserted below, including the absence of any placeholder.

RUN: python3 -m pytest test_boot_receipt_frame_spawn_axis.py -q
"""
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_OW_PATH = _HERE / "office-worldview.py"
_HOOK_PATH = _HERE.parent / "hooks" / "subagent-citizen-boot.py"
_BR_PATH = _HERE / "boot-receipt.py"

ow = _load(_OW_PATH, "office_worldview_spawnframe_ro") if _OW_PATH.is_file() else None
hk = _load(_HOOK_PATH, "subagent_citizen_boot_spawnframe_ro") if _HOOK_PATH.is_file() else None
br = _load(_BR_PATH, "boot_receipt_spawnframe_ro") if _BR_PATH.is_file() else None
_SWEEPER_PATH = (br.zone_root() / "audit-logs" / "boot-injections" / "receipt-drops-sweep.py"
                 if br is not None else None)
sw = (_load(_SWEEPER_PATH, "receipt_drops_sweep_spawnframe_ro")
      if _SWEEPER_PATH is not None and _SWEEPER_PATH.is_file() else None)

SPAWN = "agent_wave4_sibling_A"
OTHER = "agent_wave4_sibling_B"
TIC = 735


def _bash(spawn="", **kw):
    return ow.render_receipt_frame("ent_probe", TIC, "Probe", Path("."), spawn_id=spawn, **kw)


def _write(spawn=""):
    return hk.render_write_path_receipt_frame("ent_probe", TIC, spawn)


def _json_block(frame: str) -> str:
    """The literal JSON object the Write-path frame prescribes (between the first '{' line and
    its matching '}' line). Extracted so the prescription can be PARSED, not eyeballed."""
    lines = frame.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip() == "{")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "}")
    return "\n".join(lines[start:end + 1])


def _parse_prescribed_json(frame: str) -> dict:
    """Parse the prescribed drop template after replacing its authoring ellipses with real
    values — i.e. exactly what a compliant citizen would end up writing."""
    block = _json_block(frame)
    block = re.sub(r'"<[^"]*>"', '"filled"', block)   # <your model id …>, <EXACTLY five …>
    block = block.replace('"…"', '"filled"').replace('["…"]', '["filled"]')
    return json.loads(block)


# ───────────────────────────── leg (b): the Bash prescription ─────────────────────────────

@unittest.skipIf(ow is None, "office-worldview.py not present")
class BashFrameSpawnAxis(unittest.TestCase):

    def test_declared_spawn_is_prescribed_CONCRETELY(self):
        f = _bash(SPAWN)
        self.assertIn(f"--spawn-id {SPAWN}", f)
        self.assertIn("· spawn_id", f, "the owed list must name the field it now asks for")

    def test_declared_spawn_flag_is_a_valid_continuation_line_in_the_emit_command(self):
        """The prescription is a COPY-PASTED shell command. A flag on a line whose predecessor
        lost its backslash is a broken command, not a taught field."""
        f = _bash(SPAWN)
        lines = f.splitlines()
        idx = next(i for i, l in enumerate(lines) if "--spawn-id" in l and "SPAWN AXIS" not in l)
        self.assertTrue(lines[idx - 1].rstrip().endswith("\\"),
                        f"line before --spawn-id does not continue: {lines[idx-1]!r}")
        self.assertTrue(lines[idx].rstrip().endswith("\\"),
                        f"--spawn-id line does not continue: {lines[idx]!r}")

    def test_undeclared_spawn_prescribes_NO_flag_at_all(self):
        f = _bash("")
        cmd = f.split("⚠ boot-read attestation")[0]
        self.assertNotIn("--spawn-id", cmd,
                         "the undeclared arm must not put --spawn-id in the copyable command")
        self.assertNotIn("· spawn_id", f, "an unkeyed receipt does not owe spawn_id")

    def test_undeclared_arm_teaches_the_OMIT_rule_rather_than_going_silent(self):
        f = _bash("")
        self.assertIn("SPAWN AXIS", f)
        self.assertIn("OMIT --spawn-id", f)
        self.assertIn("NEVER invent one", f)

    def test_neither_arm_emits_a_fill_in_the_blank_placeholder(self):
        """THE CENTRAL DESIGN CLAIM. A placeholder is unservable (an agent cannot read its own
        agent_id) and invites a fabricated key, which is worse than no key."""
        for spawn in (SPAWN, ""):
            with self.subTest(spawn=spawn or "<undeclared>"):
                f = _bash(spawn)
                self.assertNotIn("--spawn-id <", f)
                self.assertNotIn("--spawn-id …", f)

    def test_the_axis_is_declared_an_identity_coordinate_not_an_attestation(self):
        self.assertIn("IDENTITY coordinate", _bash(SPAWN))
        self.assertIn("never an attestation", _bash(SPAWN))

    def test_ladder_and_declination_arms_are_undisturbed_by_the_new_axis(self):
        """The spawn axis must compose with the /review-724 arms, not displace them."""
        lad = _bash(SPAWN, ladder=True)
        self.assertIn("--ladder-explainback", lad)
        self.assertIn(f"--spawn-id {SPAWN}", lad)
        dec = _bash(SPAWN, declination="standing=guest render carried no ladder content")
        self.assertIn("--ladder-declination", dec)
        self.assertIn(f"--spawn-id {SPAWN}", dec)

    def test_cli_flag_threads_end_to_end_through_the_real_renderer(self):
        """Not a unit call: the actual `render` subcommand, as the hook invokes it."""
        zone = str(br.zone_root())
        base = [sys.executable, str(_OW_PATH), "render", "--office", "ent_homeskillet",
                "--tic", str(TIC), "--format", "human", "--zone-root", zone, "--max-chars", "600"]
        with_spawn = subprocess.run(base + ["--spawn-id", SPAWN], capture_output=True, text=True,
                                    timeout=60)
        without = subprocess.run(base, capture_output=True, text=True, timeout=60)
        self.assertEqual(with_spawn.returncode, 0, with_spawn.stderr)
        self.assertEqual(without.returncode, 0, without.stderr)
        self.assertIn(f"--spawn-id {SPAWN}", with_spawn.stdout)
        self.assertNotIn("--spawn-id", without.stdout.split("⚠ boot-read attestation")[0])

    def test_the_flag_is_optional_on_the_cli(self):
        """Degrade-to-today: every legacy caller (and the primary orchestrator's own session)
        invokes without it and must not error."""
        r = subprocess.run([sys.executable, str(_OW_PATH), "render", "--office", "ent_homeskillet",
                            "--tic", str(TIC), "--zone-root", str(br.zone_root())],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)


# ─────────────────────── leg (c): the no-Bash Write-path drop frame ───────────────────────

@unittest.skipIf(hk is None, "subagent-citizen-boot.py not present")
class WriteFrameSpawnAxis(unittest.TestCase):

    def test_declared_spawn_is_prescribed_CONCRETELY_in_the_json_body(self):
        f = _write(SPAWN)
        self.assertIn(f'"spawn_id": "{SPAWN}"', f)
        self.assertIn("· spawn_id", f)

    def test_the_prescribed_json_actually_PARSES_and_carries_the_spawn(self):
        """A drop template that does not parse is not a prescription, it is a trap."""
        obj = _parse_prescribed_json(_write(SPAWN))
        self.assertEqual(obj["spawn_id"], SPAWN)
        self.assertEqual(obj["entity_id"], "ent_probe")
        self.assertEqual(obj["tic"], TIC)

    def test_undeclared_arm_prescribes_no_spawn_key_and_still_parses(self):
        obj = _parse_prescribed_json(_write(""))
        self.assertNotIn("spawn_id", obj)
        self.assertNotIn("· spawn_id", _write(""))

    def test_both_arms_name_the_field_so_the_tripwire_is_ARMED(self):
        """DropLaneMirrorLatency's forward guard keys on the literal token `"spawn_id"` appearing
        in this frame. If the undeclared arm went silent, the tripwire — and the M2 negative
        control that depends on it — would pass vacuously."""
        for spawn in (SPAWN, ""):
            with self.subTest(spawn=spawn or "<undeclared>"):
                self.assertIn('"spawn_id"', _write(spawn))

    def test_undeclared_arm_teaches_conditional_addition_never_invention(self):
        f = _write("")
        self.assertIn("if — and only if", f)
        self.assertIn("OMIT the key entirely", f)
        self.assertIn("NEVER invent one", f)

    def test_signature_is_backward_compatible(self):
        """DropLaneMirrorLatency._drop_frame() calls this with two positional args."""
        self.assertIsInstance(hk.render_write_path_receipt_frame("ent_x", 1), str)


# ─────────────────────── the threading: SubagentStart is the only seam ───────────────────────

@unittest.skipIf(hk is None or br is None, "hook / boot-receipt.py not present")
class HookThreadsTheSpawnIdentity(unittest.TestCase):
    """render_worldview must PASS the flag, or leg (b) can only ever render its omit-arm."""

    def _captured_cmd(self, spawn):
        seen = {}

        class _R:
            returncode, stdout, stderr = 0, "", ""

        def fake_run(cmd, *a, **kw):
            seen["cmd"] = list(cmd)
            return _R()

        real = hk.subprocess.run
        hk.subprocess.run = fake_run
        try:
            hk.render_worldview(TIC, "ent_probe", br.zone_root(), spawn_id=spawn)
        finally:
            hk.subprocess.run = real
        return seen.get("cmd", [])

    def test_declared_spawn_reaches_the_renderer_argv(self):
        cmd = self._captured_cmd(SPAWN)
        self.assertIn("--spawn-id", cmd)
        self.assertEqual(cmd[cmd.index("--spawn-id") + 1], SPAWN)

    def test_empty_spawn_adds_no_flag(self):
        """Degrade-to-today at the seam: a harness that stops shipping agent_id must produce the
        exact pre-735 argv, never `--spawn-id ''` (an unmatchable key masquerading as a spawn)."""
        self.assertNotIn("--spawn-id", self._captured_cmd(""))

    def test_render_worldview_signature_is_backward_compatible(self):
        import inspect
        p = inspect.signature(hk.render_worldview).parameters
        self.assertIn("spawn_id", p)
        self.assertEqual(p["spawn_id"].default, "")


# ─────────── the atom end-to-end: frame → drop → sweeper identity (M2 is load-bearing) ───────────

@unittest.skipIf(hk is None or br is None or sw is None, "one of the three artifacts is absent")
class TheAtomHoldsEndToEnd(unittest.TestCase):
    """Leg (c) without M2-734 is the half-atom the tripwire exists to prevent. Proven here on the
    REAL sweeper's ingest path, not on the fingerprint function alone."""

    @staticmethod
    def _drop(tmp: Path, name: str, obj: dict) -> Path:
        p = tmp / name
        p.write_text(json.dumps(obj), encoding="utf-8")
        return p

    def _civic(self, spawn=None):
        rec = {"entity_id": "ent_probe", "tic": TIC, "understood_scope": "s",
               "accepted_constraints": ["c"], "abstentions": ["a"],
               "first_action_or_escalation": "f"}
        if spawn:
            rec["spawn_id"] = spawn
        return rec

    def test_two_wave_siblings_differing_only_in_spawn_get_DISTINCT_identities(self):
        """The collision M2 prevents: same entity, same tic, same civic body, two spawns."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            a = sw.classify_drop(self._drop(tmp, "a.json", self._civic(SPAWN)))
            b = sw.classify_drop(self._drop(tmp, "b.json", self._civic(OTHER)))
            self.assertEqual(a[0], "ok")
            self.assertEqual(b[0], "ok")
            self.assertNotEqual(a[1]["receipt_id"], b[1]["receipt_id"],
                                "two siblings' drops still collide — the mirror is not hashing "
                                "spawn_id and the second would DEDUP AWAY (M2-734)")

    def test_the_sweeper_identity_equals_the_emit_lane_identity(self):
        """One dedup space, two writers — asserted on a spawn-keyed record."""
        with tempfile.TemporaryDirectory() as td:
            rec = self._civic(SPAWN)
            kind, out = sw.classify_drop(self._drop(Path(td), "a.json", rec))
            self.assertEqual(kind, "ok")
            self.assertEqual(out["receipt_id"],
                             br.receipt_id("ent_probe", TIC, br.content_fingerprint(rec)))

    def test_unkeyed_drops_still_dedup_to_one_identity(self):
        """The axis must not have turned the deterministic id into a per-call nonce."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            a = sw.classify_drop(self._drop(tmp, "a.json", self._civic()))
            b = sw.classify_drop(self._drop(tmp, "b.json", self._civic()))
            self.assertEqual(a[1]["receipt_id"], b[1]["receipt_id"])

    def test_NEGATIVE_CONTROL_without_the_mirror_layer_the_siblings_collide(self):
        """Falsifiability against the LIVE artifact: delete M2's spawn layer from a copy of the
        real sweeper and show the two siblings collapse to ONE identity — i.e. this suite
        discriminates, and leg (c) genuinely required M2 in the same atom."""
        src = _SWEEPER_PATH.read_text(encoding="utf-8")
        anchor = ('    if rec.get("spawn_id"):\n'
                  '        sem["spawn_id"] = str(rec["spawn_id"])\n')
        self.assertIn(anchor, src, "negative-control anchor missing from the real sweeper")
        mutated = src.replace(anchor, "")
        self.assertNotEqual(mutated, src, "the deletion did not apply")
        spec = importlib.util.spec_from_loader("receipt_drops_sweep_reverted", loader=None)
        rev = importlib.util.module_from_spec(spec)
        exec(compile(mutated, "<reverted-sweeper>", "exec"), rev.__dict__)
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            a = rev.classify_drop(self._drop(tmp, "a.json", self._civic(SPAWN)))
            b = rev.classify_drop(self._drop(tmp, "b.json", self._civic(OTHER)))
            self.assertEqual(a[1]["receipt_id"], b[1]["receipt_id"],
                             "reverting the mirror layer did NOT reproduce the collision — the "
                             "control does not discriminate and proves nothing")


# ───────────────────────────────── the rider, asserted ─────────────────────────────────

@unittest.skipIf(hk is None, "hook not present")
class TheRiderIsRETIRED(unittest.TestCase):
    """THE RIDER THIS CLASS USED TO HOLD, quoted so its retirement is auditable rather than a
    silent deletion:

        "This increment lands the WRITERS only. It does NOT close A2-733: the live PreToolUse
         gate path still resolves on (entity, tic) — entity-grain — until the reader increment
         (M1-734 leg a) lands separately. Naming this cured would be naming a gated thing live."

    RETIRED AT TIC 735 BY THE LANDING OF LEG (a). Receipt:
    audit-logs/governance/harpoon-office/cable-receipts/bk-boot-gate-per-spawn-axis-reader-tic735.json

    The rider was authored to FAIL the day leg (a) landed — it asserted `--spawn-id` ABSENT from
    boot-read-gate.py — and it did exactly that, which is why it is being inverted rather than
    deleted. It is replaced by the assertion of the NEW truth, so this suite keeps saying
    something falsifiable about the reader instead of going quiet on it. The scope boundary the
    rider protected still stands and is asserted below: SOURCE-level cure is not INSTALLED-level
    cure until the seat commits + syncs (~/.claude/hooks/ is what the harness actually fires)."""

    _GATE = _HERE.parent / "hooks" / "boot-read-gate.py"

    def test_boot_read_gate_NOW_declares_a_spawn(self):
        """The inversion. Leg (a) landed: the reader declares."""
        if not self._GATE.is_file():
            self.skipTest("boot-read-gate.py not present")
        src = self._GATE.read_text(encoding="utf-8")
        self.assertIn("--spawn-id", src,
                      "boot-read-gate.py no longer declares a spawn — leg (a) has been REVERTED, "
                      "and A2-733 is re-opened at the source")

    def test_the_declaration_is_on_the_gate_check_argv_not_merely_in_a_comment(self):
        """A rider retired by a MENTION would be worse than the rider. The token must reach the
        subprocess argv — asserted structurally, not by prose match."""
        if not self._GATE.is_file():
            self.skipTest("boot-read-gate.py not present")
        gate = _load(self._GATE, "boot_read_gate_rider_ro")
        seen = {}

        class _R:
            returncode, stdout, stderr = 0, "", ""

        def fake_run(cmd, *a, **kw):
            seen["cmd"] = list(cmd)
            return _R()

        real = gate.subprocess.run
        gate.subprocess.run = fake_run
        try:
            gate.decide(json.dumps({
                "tool_name": "Edit",
                "tool_input": {"file_path": "audit-logs/governance/constitution-ledger/ledger.md"},
                "agent_id": "agent_stepper_1", "agent_type": "cpr-stepper",
                "session_id": "sess-RIDER",
            }))
        finally:
            gate.subprocess.run = real
        cmd = seen.get("cmd", [])
        self.assertIn("--spawn-id", cmd, f"gate-check argv carries no spawn declaration: {cmd}")
        self.assertEqual(cmd[cmd.index("--spawn-id") + 1], "agent_stepper_1")

    def test_the_writers_STILL_declare_one(self):
        """Unchanged half: the writers landed at tic 735 and must not have regressed."""
        self.assertIn("--spawn-id", _OW_PATH.read_text(encoding="utf-8"))
        self.assertIn("spawn_id", _HOOK_PATH.read_text(encoding="utf-8"))

    def test_the_SOURCE_vs_INSTALLED_boundary_is_still_real(self):
        """THE RIDER'S SURVIVING HALF. The cure lands in canonical SOURCE; the harness fires the
        INSTALLED copy under ~/.claude/hooks/. Until the seat commits and syncs, the live gate is
        whatever the installed tree holds. This test does not demand parity (the citizen may not
        commit) — it asserts the boundary is MEASURABLE, so 'source cured' can never be silently
        read as 'gate cured'."""
        installed = Path.home() / ".claude" / "hooks" / "boot-read-gate.py"
        if not installed.is_file():
            self.skipTest("no installed copy to compare against")
        src_declares = "--spawn-id" in self._GATE.read_text(encoding="utf-8")
        inst_declares = "--spawn-id" in installed.read_text(encoding="utf-8")
        self.assertTrue(src_declares, "source must declare — leg (a) landed here")
        if not inst_declares:
            self.assertNotEqual(
                src_declares, inst_declares,
                "install parity is OWED and this asymmetry is the evidence of it")


@unittest.skipIf(br is None, "boot-receipt.py not present")
class RealLaneUntouched(unittest.TestCase):
    def test_no_write_to_the_receipt_lane(self):
        real = br.sink_path(br.zone_root())
        before = real.read_bytes() if real.exists() else b""
        _bash(SPAWN)
        _write(SPAWN)
        after = real.read_bytes() if real.exists() else b""
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
