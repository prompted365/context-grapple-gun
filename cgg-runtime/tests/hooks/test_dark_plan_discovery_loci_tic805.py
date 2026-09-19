#!/usr/bin/env python3
"""Selftests for the tic-805 ruled increment — the dark plan-discovery loci.

Ruling: audit-logs/governance/receipts/2026-09-19-tic804-drill-sequencing-and-dark-loci-ruling.md
(5083 bytes, sha256 head-16 e300490b2ccebec3), /review 804 round 3, Architect-ratified,
recommended option verbatim "Cure at 805, BEFORE the first pointer boundary".

DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT flip the payload switch, does NOT establish how long the loci have been dark, does NOT change the seal journal's vocabulary, and does NOT serve the successor session (manifest row B13), which has no call site and is served only by the pointer payload's own text.

THE REAL ZONE IS NEVER A TEST SUBJECT. Every hook execution in this file runs with
(i) the zone root pinned EXPLICITLY to a tmp_path fixture zone (.ticzone + CLAUDE_PROJECT_DIR),
(ii) HOME pointed at a fixture HOME, and
(iii) the process CWD INSIDE the fixture zone.
Row 172 of the real audit-logs/hooks/handoff-seals.jsonl is a prior seat's fixture row that
reached the real journal through a resolver CWD fallback; all three pins together are what
make that unreachable here.

A MOGUL RUNNER SPAWN IS MADE IMPOSSIBLE TWO INDEPENDENT WAYS:
  1. the fixture mandate is never `pending` (cgg-gate.sh only spawns on pending + heavy cycles);
  2. mogul-runner.sh is absent from ALL THREE resolve_script roots (fixture zone scripts/,
     fixture plugin root, fixture HOME) — so even a reached branch resolves an empty path.

THE SWITCH IS READ, NEVER WRITTEN. Every test pins CGG_HANDOFF_PAYLOAD_MODE_CONFIG (the seal's
own documented fixture seam) at a fixture-only JSON under tmp_path, so these tests are hermetic
against the real cgg-runtime/config/handoff-payload-mode.json whichever way it is later set.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[2] / "hooks"
SESSION_RESTORE = HOOKS / "session-restore.sh"
CGG_GATE = HOOKS / "cgg-gate.sh"
SEAL = HOOKS / "cadence-handoff-seal.py"

RIDER = (
    "this increment does NOT flip the payload switch, does NOT establish how long the loci "
    "have been dark, does NOT change the seal journal's vocabulary, and does NOT serve the "
    "successor session (manifest row B13), which has no call site and is served only by the "
    "pointer payload's own text."
)

L1 = "CGG EVALUATION PENDING"
L2_NEXT = "CGG HANDOFF NEXT ACTIONS"
L3 = "CGG CHARTER"
L4 = "CGG CONSUMPTION PROTOCOL"
CONTROL = "[TIC: #"

FUTURE = (2027, 1, 1, 0, 0, 0, 0, 0, -1)


def _future_stamp(p: Path) -> None:
    """Satisfy session-restore.sh's `find -newer $PROCESSED_IDS` guard.

    AS WRITTEN AT TIC 805: session-restore.sh touched PROCESSED_IDS to NOW immediately
    before the find, so no at-or-before-boot file was ever strictly newer (finding
    F-805-2), and future-dating was the only way to hold that variable constant while the
    DIRECTORY variable was under test.

    CURED AT TIC 806 (ruled /review 805 round 3): the marker is now created-if-missing
    WITHOUT bumping its mtime, so a live-dated plan written after the marker's last
    recorded id is already newer. Future-dating here is therefore still SUFFICIENT and
    no longer NECESSARY; it stays because these nodes hold the mtime variable constant
    by construction. The live-mtime arms live in test_processed_ids_marker_tic806.py.
    """
    ts = time.mktime(FUTURE)
    os.utime(p, (ts, ts))


RICH = """# Handoff — fixture RICH shape

<!-- cgg-handoff
  handoff_id: "{hid}"
  project_dir: "{zone}"
  entry_tic: 805
-->

<!-- cgg-evaluate
  pending_cprs_expected: 3
-->

## Next Actions
1. FIXTURE-NEXT-ACTION-ONE exists only to exceed the twenty character guard.
2. FIXTURE-NEXT-ACTION-TWO.

## Closing
fixture tail
"""

BARE = """# Handoff — fixture BARE shape

<!-- cgg-handoff
  handoff_id: "{hid}"
  project_dir: "{zone}"
  entry_tic: 805
-->

Prose only, carrying neither Next Actions nor Not Started.
"""

POINTER = """STOP — THIS IS A POINTER, NOT THE PLAN.

<!-- cgg-handoff
  handoff_id: "{hid}"
  project_dir: "{zone}"
  entry_tic: 805
-->

<!-- cgg-handoff-pointer
  payload_mode: "pointer"
  durable_home: "{home}"
  handoff_id: "{hid}"
  entry_tic: 805
  content_sha16: "deadbeefdeadbeef"
  body_chars: 123
-->

## Bounded summary — NOT the plan. The plan is the durable home named above.
POINTER-SUMMARY-SENTINEL must never reach the boot briefing.
"""


class Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.zone = root / "zone"
        self.home = root / "home"
        self.proot = root / "pluginroot"
        self.tmpdir = root / "tmpdir"

        (self.zone / "audit-logs" / "tics").mkdir(parents=True)
        (self.zone / "audit-logs" / "mogul" / "mandates").mkdir(parents=True)
        (self.zone / "audit-logs" / "hooks").mkdir(parents=True)
        (self.zone / "audit-logs" / "cprs").mkdir(parents=True)
        (self.zone / "audit-logs" / "signals").mkdir(parents=True)
        (self.zone / "audit-logs" / "handoffs").mkdir(parents=True)
        self.tmpdir.mkdir()

        (self.zone / ".ticzone").write_text(json.dumps(
            {"name": "fixture-darkloci-805", "tz": "UTC", "include": ["."],
             "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"], "muffling_per_hop": 5}), encoding="utf-8")
        (self.zone / "audit-logs" / "tics" / "2026-09-19.jsonl").write_text(json.dumps(
            {"type": "tic", "count_mode": "counted", "global_counter_after": 805}) + "\n",
            encoding="utf-8")
        # NEVER `pending` — guard #1 against a runner spawn.
        (self.zone / "audit-logs" / "mogul" / "mandates" / "current.json").write_text(json.dumps(
            {"mandate_id": "fixture-805", "status": "consumed",
             "tic_context": {"current_tic": 805},
             "cycle_request": {"run_now": ["queue_refresh", "signal_scan"]}}), encoding="utf-8")
        (self.zone / "audit-logs" / "cprs" / "queue.jsonl").write_text("", encoding="utf-8")
        (self.zone / "audit-logs" / "signals" / "active-manifest.jsonl").write_text("", encoding="utf-8")

        self.project_key = str(self.zone).replace("/", "-")
        self.plans = self.home / ".claude" / "plans"
        self.projects = self.home / ".claude" / "projects" / self.project_key
        self.plans.mkdir(parents=True)
        self.projects.mkdir(parents=True)
        (self.home / ".claude" / "cgg-processed-handoff-ids.txt").write_text("", encoding="utf-8")

        # Plugin root carries ONLY the rule's home and the effective-record resolver
        # (symlinked at their real paths) — no mogul-runner.sh anywhere, which is
        # guard #2 against a runner spawn. The resolver must be present because its
        # ABSENCE is a CAPABILITY blocker that fail-closes the whole boot before any
        # plan-discovery runs; without it every locus reads DARK for the wrong reason.
        (self.proot / "cgg-runtime" / "hooks").mkdir(parents=True)
        (self.proot / "cgg-runtime" / "scripts").mkdir(parents=True)
        os.symlink(SEAL, self.proot / "cgg-runtime" / "hooks" / "cadence-handoff-seal.py")
        real_scripts = HOOKS.parent / "scripts"
        os.symlink(real_scripts / "effective-record.py",
                   self.proot / "cgg-runtime" / "scripts" / "effective-record.py")
        os.symlink(real_scripts / "lib", self.proot / "cgg-runtime" / "scripts" / "lib")

        self.switch = root / "switch.json"
        self.set_mode("body")

    def set_mode(self, mode: str) -> None:
        self.switch.write_text(json.dumps({"handoff_payload_mode": mode}), encoding="utf-8")

    def runner_is_unreachable(self) -> list[Path]:
        return [
            self.zone / "scripts" / "mogul-runner.sh",
            self.proot / "cgg-runtime" / "scripts" / "mogul-runner.sh",
            self.home / ".claude" / "cgg-runtime" / "scripts" / "mogul-runner.sh",
        ]

    def plant(self, where: Path, name: str, template: str, hid: str, home: str = "") -> Path:
        p = where / name
        p.write_text(template.format(hid=hid, zone=self.zone, home=home), encoding="utf-8")
        return p

    def env(self) -> dict:
        e = dict(os.environ)
        e.update({
            "HOME": str(self.home),
            "CLAUDE_PROJECT_DIR": str(self.zone),
            "CLAUDE_PLUGIN_ROOT": str(self.proot),
            "TMPDIR": str(self.tmpdir),
            "PYTHONDONTWRITEBYTECODE": "1",
            "CGG_HANDOFF_PAYLOAD_MODE_CONFIG": str(self.switch),
        })
        e.pop("CGG_OBLIGATION_MANDATE_ID", None)
        return e

    def run(self, hook: Path, stdin: str = "{}") -> subprocess.CompletedProcess:
        # CWD is INSIDE the fixture zone — the third pin.
        return subprocess.run(
            ["bash", str(hook)], input=stdin, text=True, capture_output=True,
            cwd=str(self.zone), env=self.env(), timeout=120,
        )


@pytest.fixture()
def fx(tmp_path):
    return Fixture(tmp_path)


def _loci(out: str) -> dict:
    return {
        "L1": L1 in out,
        "L2": L2_NEXT in out,
        "L3": L3 in out,
        "L4": L4 in out,
    }


# ---------------------------------------------------------------------------
# The ruled cure: the two-directory rule at session-restore's call site.
# ---------------------------------------------------------------------------

def test_live_plan_in_plans_dir_is_discovered(fx):
    """THE RULED CURE. A plan in ~/.claude/plans/ lights all four consuming loci."""
    p = fx.plant(fx.plans, "live.md", RICH, "fx805-t1")
    _future_stamp(p)
    r = fx.run(SESSION_RESTORE)
    assert CONTROL in r.stdout, f"positive control DARK — run proves nothing: {r.stdout!r}"
    assert _loci(r.stdout) == {"L1": True, "L2": True, "L3": False, "L4": True}
    assert str(p) in r.stdout


def test_charter_fallback_for_bare_plan(fx):
    """L3 is the ELSE of both awk ranges — it can only light on a section-less plan."""
    p = fx.plant(fx.plans, "bare.md", BARE, "fx805-t2")
    _future_stamp(p)
    r = fx.run(SESSION_RESTORE)
    assert CONTROL in r.stdout
    assert _loci(r.stdout) == {"L1": False, "L2": False, "L3": True, "L4": True}


def test_projects_dir_still_discovered_no_regression(fx):
    """The directory that already worked must keep working — the cure ADDS, never moves."""
    p = fx.plant(fx.projects, "legacy.md", RICH, "fx805-t3")
    _future_stamp(p)
    r = fx.run(SESSION_RESTORE)
    assert CONTROL in r.stdout
    assert _loci(r.stdout) == {"L1": True, "L2": True, "L3": False, "L4": True}


def test_no_discoverable_plan_emits_no_loci_but_keeps_the_control(fx):
    """Negative control: nothing discoverable => all four DARK, tic line still LIT."""
    r = fx.run(SESSION_RESTORE)
    assert CONTROL in r.stdout
    assert _loci(r.stdout) == {"L1": False, "L2": False, "L3": False, "L4": False}


# ---------------------------------------------------------------------------
# One rule, three call sites, no second derivation.
# ---------------------------------------------------------------------------

def test_one_rule_three_call_sites(fx):
    """Both hooks CONSUME candidate_plan_dirs(); neither RE-DERIVES the plans directory."""
    sr = SESSION_RESTORE.read_text(encoding="utf-8")
    gt = CGG_GATE.read_text(encoding="utf-8")
    seal = SEAL.read_text(encoding="utf-8")

    assert "def candidate_plan_dirs():" in seal, "site A: the rule's home"
    assert "mod.candidate_plan_dirs()" in sr, "site B: session-restore consumes the rule"
    assert "mod.candidate_plan_dirs()" in gt, "site C: cgg-gate consumes the rule"

    # A SECOND DERIVATION would be a hardcoded plans directory in EXECUTABLE CODE.
    # Comment prose naming the directory is documentation, not derivation, so the
    # check strips comment lines before looking — otherwise the test fires on the
    # very comment that explains why the rule exists.
    def _code_only(text: str) -> str:
        return "\n".join(
            ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))

    for name, text in (("session-restore.sh", sr), ("cgg-gate.sh", gt)):
        assert ".claude/plans" not in _code_only(text), (
            f"{name} re-derives the plans directory in CODE — that is a SECOND RULE")


def test_rule_unreachable_fails_open_to_pre_cure_directory(fx):
    """Fail-open is the ABSENCE of the rule, never a silent re-invention of it.

    SEAL_HOOK_SCRIPT's FIRST candidate is `dirname($0)/cadence-handoff-seal.py`, so the
    rule stays reachable whenever the hook runs from its own directory. Making it
    genuinely unreachable therefore requires running a BYTE-IDENTICAL COPY from a
    directory that holds no seal, with a plugin root that holds none either.
    """
    (fx.proot / "cgg-runtime" / "hooks" / "cadence-handoff-seal.py").unlink()
    orphan_dir = fx.root / "orphan-hooks"
    orphan_dir.mkdir()
    orphan = orphan_dir / "session-restore.sh"
    orphan.write_bytes(SESSION_RESTORE.read_bytes())
    assert orphan.read_bytes() == SESSION_RESTORE.read_bytes(), "copy must be byte-identical"
    assert not (orphan_dir / "cadence-handoff-seal.py").exists()

    in_projects = fx.plant(fx.projects, "legacy.md", RICH, "fx805-t5a")
    _future_stamp(in_projects)
    r = fx.run(orphan)
    assert CONTROL in r.stdout
    assert _loci(r.stdout)["L2"] is True, "pre-cure directory must still resolve"

    in_projects.unlink()
    plans_plan = fx.plant(fx.plans, "live.md", RICH, "fx805-t5b")
    _future_stamp(plans_plan)
    r2 = fx.run(orphan)
    assert CONTROL in r2.stdout
    assert _loci(r2.stdout)["L2"] is False, (
        "with the rule unreachable the plans directory must NOT be invented")


def test_rider_travels_verbatim_as_one_contiguous_unit(fx):
    """A rider wrapped across comment-prefix lines does not exist as a verbatim unit."""
    assert SESSION_RESTORE.read_text(encoding="utf-8").count(RIDER) >= 1
    assert CGG_GATE.read_text(encoding="utf-8").count(RIDER) >= 1


# ---------------------------------------------------------------------------
# The body-consuming re-points (manifest rows B3..B6), under the one switch.
# ---------------------------------------------------------------------------

def test_body_mode_reads_the_approval_artifact_itself(fx):
    fx.set_mode("body")
    p = fx.plant(fx.plans, "live.md", RICH, "fx805-t6")
    _future_stamp(p)
    r = fx.run(SESSION_RESTORE)
    assert CONTROL in r.stdout
    assert str(p) in r.stdout, "under body the emitted path IS the approval artifact"


@pytest.mark.parametrize("bad_mode", ["", "{not json", '{"handoff_payload_mode": "banana"}'])
def test_unreadable_or_unrecognized_switch_means_body(fx, bad_mode):
    """Absent / malformed / unrecognized all MEAN body — the OLD path."""
    fx.switch.write_text(bad_mode, encoding="utf-8")
    p = fx.plant(fx.plans, "live.md", RICH, "fx805-t7")
    _future_stamp(p)
    r = fx.run(SESSION_RESTORE)
    assert CONTROL in r.stdout
    assert str(p) in r.stdout
    assert "CGG HANDOFF POINTER UNRESOLVED" not in r.stdout


def test_pointer_mode_body_consumers_read_the_durable_home(fx):
    """Rows B5/B6: under `pointer` the briefing comes from the durable home, never the envelope."""
    fx.set_mode("pointer")
    durable = fx.zone / "audit-logs" / "handoffs" / "805-fx805-t8-aaaaaaaa.md"
    durable.write_text(RICH.format(hid="fx805-t8", zone=fx.zone), encoding="utf-8")
    p = fx.plant(fx.plans, "ptr.md", POINTER, "fx805-t8",
                 home="audit-logs/handoffs/805-fx805-t8-aaaaaaaa.md")
    _future_stamp(p)
    r = fx.run(SESSION_RESTORE)
    assert CONTROL in r.stdout
    assert L2_NEXT in r.stdout
    assert str(durable) in r.stdout, "the emitted path must be the durable home"
    assert "POINTER-SUMMARY-SENTINEL" not in r.stdout, (
        "the pointer's bounded summary must never reach the boot briefing")


def test_pointer_mode_dangling_home_is_held_and_loud(fx):
    """A dangling durable home is REFUSED fail-closed and LOUD — never a thinner briefing."""
    fx.set_mode("pointer")
    p = fx.plant(fx.plans, "ptr.md", POINTER, "fx805-t9",
                 home="audit-logs/handoffs/NO-SUCH-FILE.md")
    _future_stamp(p)
    r = fx.run(SESSION_RESTORE)
    assert CONTROL in r.stdout
    assert "CGG HANDOFF POINTER UNRESOLVED" in r.stdout
    assert L2_NEXT not in r.stdout
    assert L3 not in r.stdout
    assert "POINTER-SUMMARY-SENTINEL" not in r.stdout


# ---------------------------------------------------------------------------
# cgg-gate.sh — call site C and M3's delegated path.
# ---------------------------------------------------------------------------

def _arm_gate_trigger(fx, handoff_id: str) -> Path:
    flag_dir = fx.tmpdir / "claude_cgg" / fx.project_key
    flag_dir.mkdir(parents=True, exist_ok=True)
    (flag_dir / "pending-trigger.txt").write_text(
        "<!-- cgg-evaluate\n  pending_cprs_expected: 3\n-->\n", encoding="utf-8")
    (flag_dir / "pending-handoff-id.txt").write_text(handoff_id, encoding="utf-8")
    return flag_dir


def _stub_assessor(fx) -> Path:
    """Records its own argv instead of assessing. Proves WHICH path was handed onward."""
    argv_sink = fx.root / "assessor-argv.json"
    stub = fx.proot / "cgg-runtime" / "scripts" / "ripple-assessor.py"
    stub.write_text(
        "import json, sys\n"
        f"open({str(argv_sink)!r}, 'w').write(json.dumps(sys.argv))\n",
        encoding="utf-8")
    return argv_sink


def _await_sink(sink: Path, timeout: float = 20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if sink.exists() and sink.read_text(encoding="utf-8").strip():
            return json.loads(sink.read_text(encoding="utf-8"))
        time.sleep(0.2)
    raise AssertionError(f"assessor sink never written: {sink}")


def test_gate_resolves_a_plan_in_the_plans_directory(fx):
    """Call site C: the gate's Branch-B resolution now reaches ~/.claude/plans/."""
    _arm_gate_trigger(fx, "fx805-t10")
    sink = _stub_assessor(fx)
    fx.plant(fx.plans, "live.md", RICH, "fx805-t10")
    r = fx.run(CGG_GATE, stdin=json.dumps({"prompt": "hello"}))
    assert r.returncode == 0
    argv = _await_sink(sink)
    plan_arg = argv[argv.index("--plan") + 1]
    assert plan_arg == str(fx.plans / "live.md")


def test_gate_delegated_path_resolves_the_durable_home_under_pointer(fx):
    """M3's delegated path: the surface handed to --plan is consumed as a BODY downstream."""
    fx.set_mode("pointer")
    _arm_gate_trigger(fx, "fx805-t11")
    sink = _stub_assessor(fx)
    durable = fx.zone / "audit-logs" / "handoffs" / "805-fx805-t11-bbbbbbbb.md"
    durable.write_text(RICH.format(hid="fx805-t11", zone=fx.zone), encoding="utf-8")
    fx.plant(fx.plans, "ptr.md", POINTER, "fx805-t11",
             home="audit-logs/handoffs/805-fx805-t11-bbbbbbbb.md")
    r = fx.run(CGG_GATE, stdin=json.dumps({"prompt": "hello"}))
    assert r.returncode == 0
    argv = _await_sink(sink)
    plan_arg = argv[argv.index("--plan") + 1]
    assert plan_arg == str(durable), "under pointer the assessor must receive the durable home"


def test_gate_body_mode_hands_on_the_plan_path_unchanged(fx):
    fx.set_mode("body")
    _arm_gate_trigger(fx, "fx805-t12")
    sink = _stub_assessor(fx)
    fx.plant(fx.plans, "live.md", RICH, "fx805-t12")
    r = fx.run(CGG_GATE, stdin=json.dumps({"prompt": "hello"}))
    assert r.returncode == 0
    argv = _await_sink(sink)
    plan_arg = argv[argv.index("--plan") + 1]
    assert plan_arg == str(fx.plans / "live.md")


# ---------------------------------------------------------------------------
# Real-zone safety, asserted rather than asserted-in-prose.
# ---------------------------------------------------------------------------

def test_runner_spawn_is_impossible_in_this_fixture(fx):
    for cand in fx.runner_is_unreachable():
        assert not cand.exists(), f"mogul-runner.sh reachable at {cand}"
    mandate = json.loads(
        (fx.zone / "audit-logs" / "mogul" / "mandates" / "current.json").read_text(encoding="utf-8"))
    assert mandate["status"] != "pending", "a pending mandate is the gate's spawn precondition"


def test_hook_runs_never_write_the_real_seal_journal(fx):
    real = Path("/Users/breydentaylor/canonical/audit-logs/hooks/handoff-seals.jsonl")
    if not real.exists():
        pytest.skip("real journal absent on this machine")
    before = real.stat().st_size
    p = fx.plant(fx.plans, "live.md", RICH, "fx805-t13")
    _future_stamp(p)
    fx.run(SESSION_RESTORE)
    fx.run(CGG_GATE, stdin=json.dumps({"prompt": "hello"}))
    assert real.stat().st_size == before, "a fixture run reached the REAL seal journal"
