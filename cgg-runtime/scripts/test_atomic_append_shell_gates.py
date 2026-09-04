#!/usr/bin/env python3
"""Pytest wrapper for atomic-append.sh's two SHELL physics-gate tests.

OM-B8-1 (/review 771 round 2 Q8, Architect-ratified): scripts/lib/test_promote_gate.sh
and scripts/lib/test_atomic_append_arg_guard.sh are the ONLY tests of
lib/atomic-append.sh's two physics gates, and pytest collects test_*.py — so before
this wrapper a regression in atomic-append.sh (a library every queue writer routes
through) would pass the full pinned suite silently, and a "full pinned suite green"
claim over an atomic-append change claimed coverage it did not have (F-770-B8-2;
the suite tuple is proven INVOCATION-SCOPED ×3 at tic 770).

This wrapper adds no assertions of its own: each shell test remains the authority on
its gate's behavior; pytest merely learns to see them. Exit 0 is the contract — both
scripts count their own pass/fail and exit non-zero on any failure.
"""

import os
import subprocess

import pytest

_LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")

_SHELL_GATE_TESTS = [
    "test_promote_gate.sh",
    "test_atomic_append_arg_guard.sh",
]


@pytest.mark.parametrize("script", _SHELL_GATE_TESTS)
def test_shell_physics_gate(script):
    path = os.path.join(_LIB, script)
    assert os.path.isfile(path), f"{script} is missing — the physics gate lost its test"
    proc = subprocess.run(
        ["bash", path],
        cwd=_LIB,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, (
        f"{script} failed (exit {proc.returncode}) — atomic-append.sh's physics gate "
        f"regressed.\nLast output:\n{(proc.stdout or '')[-2000:]}\n{(proc.stderr or '')[-500:]}"
    )
