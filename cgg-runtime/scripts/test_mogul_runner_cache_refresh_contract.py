#!/usr/bin/env python3
"""Tests for the cache_refresh prescription/producer contract parity in
mogul-runner.sh (bk-mandate-cache-refresh-contract-producer-split, tic 696 —
filed from the /review-693 PROMOTE ray on cpr_mogul_cache_refresh_2039b17fe99f,
Architect-ratified 5/5).

The defect under cure: the mandate prompt's cache_refresh instruction
prescribed `visitor-economy-monitor.py --cache-refresh $TIC` — a producer whose
envelope emits `cache_state` ONLY — while demanding a results.cache_refresh
object of {cache_state, standing_decay, biome_health}. The two missing keys
could only be filled by the agent's inference, which then READS AS MEASUREMENT
in the verified artifact (n=2 lived: tics 687, 692). The cure at the DISPATCH
surface: prescribe `--full-cycle $TIC`, whose producer measures all three
demanded keys (plus census + economy_observation, both benign), so every key
in the report contract is measured, never derived.

These arms are deliberately STATIC (parse both surfaces, assert the contract
closes) rather than behavioral: visitor-economy-monitor.py's internal
_resolve_zone() ignores the zone_root parameter and always resolves from
SCRIPT_DIR, so EXECUTING full_cycle under test would write census artifacts
and signals into the REAL zone (Self-Locating Artifact Test Isolation; the
half-honored zone_root param is filed separately as
bk-visitor-economy-monitor-zone-root-half-honored).

Contract teeth:
  1. prescription-flag parity — the runner's cache_refresh instruction must
     prescribe a flag whose producer emits EVERY key the instruction demands
     (RED pre-fix: --cache-refresh emits cache_state only)
  2. producer emits demanded keys — full_cycle() assigns cache_refresh,
     standing_decay, biome_health (static AST-level pin on the producer side)
  3. envelope carries cache_state — cache_refresh_cycle()'s envelope includes
     the cache_state key (the one key the old prescription did measure)
  4. CLI routes --full-cycle — main() dispatches args.full_cycle to
     full_cycle() (the prescribed flag is actually wired)

Run:  python3 -m unittest test_mogul_runner_cache_refresh_contract
"""
import ast
import os
import re
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_RUNNER = os.path.join(_HERE, "mogul-runner.sh")
_MONITOR = os.path.join(_HERE, "visitor-economy-monitor.py")

DEMANDED_KEYS = {"cache_state", "standing_decay", "biome_health"}

# Which top-level result keys each monitor CLI flag's producer MEASURES.
# Verified against visitor-economy-monitor.py source (arms 2/3 pin this
# mapping statically so it cannot drift silently).
FLAG_MEASURES = {
    "--cache-refresh": {"cache_state"},
    "--full-cycle": {"cache_refresh", "cache_state", "standing_decay",
                     "biome_health", "census", "economy_observation"},
}


def _runner_cache_refresh_instruction():
    text = open(_RUNNER, encoding="utf-8").read()
    for line in text.splitlines():
        if "cache_refresh:" in line and "visitor-economy-monitor.py" in line:
            return line
    raise AssertionError("cache_refresh instruction line not found in runner")


class CacheRefreshContractParityTest(unittest.TestCase):
    # -- Arm 1: prescription flag must measure every demanded key -----------
    def test_prescribed_flag_measures_every_demanded_key(self):
        line = _runner_cache_refresh_instruction()
        m = re.search(r"visitor-economy-monitor\.py\s+(--[a-z-]+)", line)
        self.assertIsNotNone(m, "no flag found in the cache_refresh prescription")
        flag = m.group(1)
        measured = FLAG_MEASURES.get(flag)
        self.assertIsNotNone(
            measured, f"prescribed flag {flag!r} has no known producer mapping")
        missing = DEMANDED_KEYS - measured
        self.assertFalse(
            missing,
            f"prescription/producer split: instruction demands "
            f"{sorted(DEMANDED_KEYS)} but prescribed {flag} measures only "
            f"{sorted(measured)} — the gap ({sorted(missing)}) gets filled by "
            f"agent inference reading as measurement",
        )

    # -- Arm 2: producer really emits the demanded keys ----------------------
    def test_full_cycle_assigns_demanded_result_keys(self):
        tree = ast.parse(open(_MONITOR, encoding="utf-8").read())
        fc = next(
            (n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef) and n.name == "full_cycle"),
            None,
        )
        self.assertIsNotNone(fc, "full_cycle() not found in monitor")
        assigned = set()
        for node in ast.walk(fc):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Subscript)
                    and isinstance(node.targets[0].slice, ast.Constant)):
                assigned.add(node.targets[0].slice.value)
        for key in ("cache_refresh", "standing_decay", "biome_health"):
            self.assertIn(key, assigned,
                          f"full_cycle() no longer measures {key!r} — the "
                          f"FLAG_MEASURES mapping (and the runner contract) "
                          f"must be revisited")

    # -- Arm 3: cache_refresh envelope carries cache_state -------------------
    def test_cache_refresh_envelope_carries_cache_state(self):
        src = open(_MONITOR, encoding="utf-8").read()
        self.assertRegex(
            src, r"\"cache_state\":\s*artifact",
            "cache_refresh_cycle envelope no longer carries cache_state")

    # -- Arm 4: the prescribed flag is wired in the CLI ----------------------
    def test_cli_routes_full_cycle(self):
        src = open(_MONITOR, encoding="utf-8").read()
        self.assertIn('"--full-cycle"', src)
        self.assertRegex(src, r"args\.full_cycle is not None:\s*\n\s*result = full_cycle\(")

    # -- Arm 5: the measurement has a durable birth (t714, a4c8 no-path ray) --
    # A mandate-DEMANDED measurement whose producer emits only to stdout has no
    # durable birth: the consuming report becomes the sole record, and clipping
    # makes re-EXECUTION of a signal-emitting cycle the only recovery. Static
    # teeth on both halves of the cure: the producer persists full_cycle output
    # to an addressable artifact, and the runner instruction names that path.
    def test_full_cycle_persists_durable_artifact(self):
        tree = ast.parse(open(_MONITOR, encoding="utf-8").read())
        fc = next(
            (n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef) and n.name == "full_cycle"),
            None,
        )
        self.assertIsNotNone(fc, "full_cycle() not found in monitor")
        calls = {node.func.id for node in ast.walk(fc)
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)}
        self.assertIn("atomic_write_json", calls,
                      "full_cycle() no longer persists its output — the "
                      "measurement's only sink is stdout again (the a4c8 "
                      "no-path defect)")
        src = ast.get_source_segment(open(_MONITOR, encoding="utf-8").read(), fc)
        self.assertIn("full-cycle-tic-", src,
                      "full_cycle() artifact path lost its addressable "
                      "tic-keyed name")

    def test_runner_instruction_names_durable_artifact_path(self):
        line = _runner_cache_refresh_instruction()
        self.assertIn(
            "audit-logs/visitor-economy/full-cycle-tic-", line,
            "the cache_refresh instruction demands measured keys and names a "
            "producer but no longer names the producer's durable artifact "
            "path — the contract-completeness corollary of the a4c8 ray")


if __name__ == "__main__":
    unittest.main()
