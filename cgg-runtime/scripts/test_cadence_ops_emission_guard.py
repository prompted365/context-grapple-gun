#!/usr/bin/env python3
"""Verify harness — cadence-ops counted-emission idempotency guard.

bk-cadence-ops-idempotency-guard (admitted /review 628, lowered t628, BUILT t629).
Exercises the four lowered fragments:

  wave 0 obj-0  second counted-emission within one session/tic refused at the
                execution boundary before any side effect lands
  wave 0 obj-1  refusal typed + visible (structured return + log line)
  wave 1 obj-0  single-emission happy path byte-for-byte unchanged
                (OLD-vs-NEW twin-zone byte parity under a frozen clock)
  wave 1 obj-1  phantom-tic recurrence class (266/579/580/588) can no longer
                mint a duplicate counted emission

Every arm runs in throwaway fixture zones with Path.home()/HOME patched to a
fixture home (self-locating-artifact-test-isolation: the counter mirror must
NEVER touch the real ~/.claude/cgg-tic-counter.json). Both arms of every
documented conditional get a fixture (selftest-fixtures-must-exercise-
documented-conditional-paths).

Run: python3 test_cadence_ops_emission_guard.py [--old-rev REV]
Exit 0 = all arms pass; exit 1 = failure (named arm).
"""

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
CADENCE_OPS = os.path.join(SCRIPTS_DIR, "cadence-ops.py")
FIXED_NOW = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)


class FakeDT(datetime):
    """Frozen clock for byte parity — subclass so strftime/isoformat behave."""
    @classmethod
    def now(cls, tz=None):
        return FIXED_NOW


def load_module(path, name):
    sys.path.insert(0, SCRIPTS_DIR)  # zone_root / mandate-write / lib resolve here
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_zone(root, name):
    zone = os.path.join(root, name)
    os.makedirs(os.path.join(zone, "audit-logs"), exist_ok=True)
    pathlib.Path(zone, ".ticzone").write_text(
        json.dumps({"name": "fixture-zone"}), encoding="utf-8")
    return zone


def read_bytes(p):
    return pathlib.Path(p).read_bytes() if os.path.exists(p) else None


def main():
    old_rev = "HEAD"
    if "--old-rev" in sys.argv:
        old_rev = sys.argv[sys.argv.index("--old-rev") + 1]

    failures = []
    results = {}

    with tempfile.TemporaryDirectory(prefix="cadence-guard-fixture-") as tmp:
        fixture_home = os.path.join(tmp, "home")
        os.makedirs(fixture_home, exist_ok=True)

        # Patch Path.home for every in-process arm (this process only).
        pathlib.Path.home = classmethod(lambda cls: cls(fixture_home))

        new_mod = load_module(CADENCE_OPS, "cadence_ops_new")

        # ------------------------------------------------------------------
        # ARM A — happy-path byte parity (wave 1 obj-0): OLD vs NEW emit_tic,
        # frozen clock, twin zones. Pre-existing artifacts byte-identical;
        # the guard sidecar is the one disclosed additive file.
        # ------------------------------------------------------------------
        try:
            old_src = subprocess.run(
                ["git", "-C", os.path.join(SCRIPTS_DIR, "..", ".."), "show",
                 f"{old_rev}:cgg-runtime/scripts/cadence-ops.py"],
                capture_output=True, text=True, check=True).stdout
            old_path = os.path.join(tmp, "cadence-ops-old.py")
            pathlib.Path(old_path).write_text(old_src, encoding="utf-8")
            old_mod = load_module(old_path, "cadence_ops_old")

            old_mod.datetime = FakeDT
            new_mod.datetime = FakeDT
            os.environ.pop("CLAUDE_CODE_SESSION_ID", None)

            zone_old = make_zone(tmp, "zone-old")
            zone_new = make_zone(tmp, "zone-new")

            r_old = old_mod.emit_tic(zone_old, "downbeat", "counted", "cadence")
            mirror_old = read_bytes(os.path.join(fixture_home, ".claude", "cgg-tic-counter.json"))
            r_new = new_mod.emit_tic(zone_new, "downbeat", "counted", "cadence")
            mirror_new = read_bytes(os.path.join(fixture_home, ".claude", "cgg-tic-counter.json"))

            day = FIXED_NOW.strftime("%Y-%m-%d")
            tic_old = read_bytes(os.path.join(zone_old, "audit-logs", "tics", f"{day}.jsonl"))
            tic_new = read_bytes(os.path.join(zone_new, "audit-logs", "tics", f"{day}.jsonl"))
            guard_new = os.path.join(zone_new, "audit-logs", "tics",
                                     new_mod.EMISSION_GUARD_FILENAME)

            assert tic_old == tic_new and tic_old is not None, "tic event rows differ"
            assert mirror_old == mirror_new, "counter mirrors differ"
            assert r_old["counter_after"] == r_new["counter_after"] == 1
            assert "emission_guard" not in r_new, "plain happy path grew a result key"
            assert os.path.exists(guard_new), "guard sidecar not written (additive artifact)"
            results["A_byte_parity"] = "PASS (tic row + mirror byte-identical; sidecar additive)"
        except Exception as err:  # noqa: BLE001
            failures.append(f"A_byte_parity: {err}")

        # Fresh zone for the refusal arms.
        zone = make_zone(tmp, "zone-guard")
        new_mod.datetime = datetime  # real clock from here on

        # ------------------------------------------------------------------
        # ARM B — same-session second emission REFUSED (wave 0 obj-0/obj-1).
        # ------------------------------------------------------------------
        try:
            os.environ["CLAUDE_CODE_SESSION_ID"] = "fixture-session-A"
            r1 = new_mod.emit_tic(zone, "downbeat", "counted", "cadence")
            assert r1["emitted"] and r1["counter_after"] == 1
            day_now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            tic_path = os.path.join(zone, "audit-logs", "tics", f"{day_now}.jsonl")
            guard_path = os.path.join(zone, "audit-logs", "tics",
                                      new_mod.EMISSION_GUARD_FILENAME)
            before_tic, before_guard = read_bytes(tic_path), read_bytes(guard_path)

            r2 = new_mod.emit_tic(zone, "downbeat", "counted", "cadence")
            assert r2.get("refused") is True, "second same-session emission NOT refused"
            assert r2["refusal_class"] == "same_session_counted_emission"
            assert r2.get("detail") and r2.get("last_emission"), "refusal not typed"
            assert read_bytes(tic_path) == before_tic, "refusal left a side effect (tic row)"
            assert read_bytes(guard_path) == before_guard, "refusal mutated guard state"
            results["B_same_session_refused"] = "PASS (typed refusal, zero side effects)"
        except Exception as err:  # noqa: BLE001
            failures.append(f"B_same_session_refused: {err}")

        # ------------------------------------------------------------------
        # ARM C — rapid cross-session re-emission REFUSED (t588's +10s shape
        # even when the session id changes).
        # ------------------------------------------------------------------
        try:
            os.environ["CLAUDE_CODE_SESSION_ID"] = "fixture-session-B"
            r3 = new_mod.emit_tic(zone, "downbeat", "counted", "cadence")
            assert r3.get("refused") is True, "rapid cross-session emission NOT refused"
            assert r3["refusal_class"] == "rapid_reemission_window"
            results["C_rapid_window_refused"] = "PASS"
        except Exception as err:  # noqa: BLE001
            failures.append(f"C_rapid_window_refused: {err}")

        # ------------------------------------------------------------------
        # ARM D — explicit arming flag authorizes a deliberate second boundary
        # (mid-session epoch); override lands VISIBLE in result + guard state.
        # ------------------------------------------------------------------
        try:
            os.environ["CLAUDE_CODE_SESSION_ID"] = "fixture-session-A"
            r4 = new_mod.emit_tic(zone, "downbeat", "counted", "cadence",
                                  allow_second_emission="fixture mid-session epoch")
            assert r4["emitted"] and r4["counter_after"] == 2
            assert r4["emission_guard"]["overridden"]["override_reason"] == \
                "fixture mid-session epoch"
            gstate = json.loads(pathlib.Path(
                zone, "audit-logs", "tics",
                new_mod.EMISSION_GUARD_FILENAME).read_text(encoding="utf-8"))
            assert gstate["override"]["override_reason"] == "fixture mid-session epoch"
            results["D_override_visible"] = "PASS (proceeds; override in result + state)"
        except Exception as err:  # noqa: BLE001
            failures.append(f"D_override_visible: {err}")

        # ------------------------------------------------------------------
        # ARM E — slow cross-session emission PASSES (the legitimate next
        # close): backdate the guard beyond the window, different session.
        # ------------------------------------------------------------------
        try:
            gpath = pathlib.Path(zone, "audit-logs", "tics",
                                 new_mod.EMISSION_GUARD_FILENAME)
            gstate = json.loads(gpath.read_text(encoding="utf-8"))
            gstate["emitted_at_epoch"] = time.time() - 3600
            gstate.pop("override", None)
            gpath.write_text(json.dumps(gstate) + "\n", encoding="utf-8")
            os.environ["CLAUDE_CODE_SESSION_ID"] = "fixture-session-C"
            r5 = new_mod.emit_tic(zone, "downbeat", "counted", "cadence")
            assert r5["emitted"] and r5["counter_after"] == 3, "legit next close blocked"
            assert "emission_guard" not in r5
            results["E_slow_cross_session_pass"] = "PASS (no over-block)"
        except Exception as err:  # noqa: BLE001
            failures.append(f"E_slow_cross_session_pass: {err}")

        # ------------------------------------------------------------------
        # ARM F — count_mode=ignored scopes OUT of the guard (documented
        # conditional, non-refusal arm): not refused, guard state untouched.
        # ------------------------------------------------------------------
        try:
            gpath = pathlib.Path(zone, "audit-logs", "tics",
                                 new_mod.EMISSION_GUARD_FILENAME)
            before_guard = gpath.read_bytes()
            r6 = new_mod.emit_tic(zone, "downbeat", "ignored", "experimental")
            assert r6["emitted"] and not r6.get("refused"), "ignored-mode emission refused"
            assert r6["counter_after"] == r6["counter_before"], "ignored mode counted"
            assert gpath.read_bytes() == before_guard, "ignored emission touched guard state"
            results["F_ignored_mode_scoped_out"] = "PASS"
        except Exception as err:  # noqa: BLE001
            failures.append(f"F_ignored_mode_scoped_out: {err}")

        # ------------------------------------------------------------------
        # ARM G — corrupt guard state fails OPEN with a DISCLOSED note (the
        # clock is load-bearing; a corrupt sidecar must not brick it — but
        # the fail-open is surfaced, never silent).
        # ------------------------------------------------------------------
        try:
            gpath = pathlib.Path(zone, "audit-logs", "tics",
                                 new_mod.EMISSION_GUARD_FILENAME)
            gpath.write_text("{not json", encoding="utf-8")
            os.environ["CLAUDE_CODE_SESSION_ID"] = "fixture-session-D"
            r7 = new_mod.emit_tic(zone, "downbeat", "counted", "cadence")
            assert r7["emitted"], "corrupt guard state bricked the clock"
            assert "unreadable" in r7.get("emission_guard", {}).get("note", ""), \
                "fail-open not disclosed"
            results["G_corrupt_state_disclosed"] = "PASS"
        except Exception as err:  # noqa: BLE001
            failures.append(f"G_corrupt_state_disclosed: {err}")

        # ------------------------------------------------------------------
        # ARM H — CLI runtime probe through the real argv surface: --fire
        # twice in a fixture zone (HOME redirected) → first exit 0, second
        # exit 3 + structured stdout refusal + stderr log line.
        # ------------------------------------------------------------------
        try:
            zone_cli = make_zone(tmp, "zone-cli")
            env = dict(os.environ)
            env["HOME"] = fixture_home
            env["CLAUDE_CODE_SESSION_ID"] = "fixture-cli-session"
            p1 = subprocess.run(
                [sys.executable, CADENCE_OPS, "--fire", "--zone-root", zone_cli,
                 "--mode", "downbeat"],
                capture_output=True, text=True, timeout=120, env=env)
            assert p1.returncode == 0, f"first CLI fire failed: {p1.stderr[:300]}"
            p2 = subprocess.run(
                [sys.executable, CADENCE_OPS, "--fire", "--zone-root", zone_cli,
                 "--mode", "downbeat"],
                capture_output=True, text=True, timeout=60, env=env)
            assert p2.returncode == 3, f"second CLI fire exit {p2.returncode}, want 3"
            out = json.loads(p2.stdout)
            assert out["tic"]["refused"] is True
            assert out["tic"]["refusal_class"] == "same_session_counted_emission"
            assert "conformation" not in out and "mandate" not in out, \
                "refusal ran downstream steps"
            assert "REFUSED: counted-emission idempotency guard" in p2.stderr
            results["H_cli_runtime_probe"] = "PASS (exit 3, structured stdout, stderr line, no downstream)"
        except Exception as err:  # noqa: BLE001
            failures.append(f"H_cli_runtime_probe: {err}")

    print(json.dumps({
        "harness": "test_cadence_ops_emission_guard",
        "route": "bk-cadence-ops-idempotency-guard",
        "arms": results,
        "failures": failures,
        "verdict": "PASS" if not failures else "FAIL",
    }, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
