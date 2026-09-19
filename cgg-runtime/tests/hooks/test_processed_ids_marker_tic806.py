#!/usr/bin/env python3
"""Selftests for the tic-806 ruled increment — the processed-ids marker stops defeating
plan discovery.

Ruling: audit-logs/governance/receipts/2026-09-19-tic805-processed-ids-marker-and-drill-slip-ruling.md
(3094 bytes, 16 lines, sha256 head-16 ca3d37435ac4d15b), /review 805 round 3, Architect-ratified,
recommended option verbatim "Rule the cure for 806 entry; slip the drill one boundary".

THE RULED INCREMENT: the marker is created-if-missing WITHOUT bumping its mtime, so its mtime
advances only when an id is recorded. The id check stays the dedup.

DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT flip the payload switch, does NOT establish how long the loci have been dark or when the touch was introduced, does NOT change what a processed id means, and does NOT serve the successor session (manifest row B13).

INSTRUMENT UNIT: the pytest NODE ID. Every parametrized arm is a @pytest.mark.parametrize case,
which pytest expands into a DISTINCT node — there is no subTest in this file, so no arm can
report a PASSING parent while its children fail.

THE REAL ZONE IS NEVER A TEST SUBJECT. Every hook execution runs with
(i) the zone root pinned EXPLICITLY to a tmp_path fixture zone (.ticzone + CLAUDE_PROJECT_DIR),
(ii) HOME pointed at a fixture HOME — which is what keeps the REAL marker untouched, since the
     hook derives the marker path from $HOME — and
(iii) the process CWD INSIDE the fixture zone.
Row 172 of the real audit-logs/hooks/handoff-seals.jsonl is a prior seat's fixture row that
reached the real journal through a resolver CWD fallback; all three pins together are what make
that unreachable here. The real marker's own untouchedness is asserted, not prosed.

A MOGUL RUNNER SPAWN IS MADE IMPOSSIBLE TWO INDEPENDENT WAYS: the fixture mandate is never
`pending`, and mogul-runner.sh is absent from ALL THREE resolve_script roots.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[2] / "hooks"
SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
SESSION_RESTORE = HOOKS / "session-restore.sh"
CGG_GATE = HOOKS / "cgg-gate.sh"
SEAL = HOOKS / "cadence-handoff-seal.py"

RIDER = (
    "this increment does NOT flip the payload switch, does NOT establish how long the loci "
    "have been dark or when the touch was introduced, does NOT change what a processed id "
    "means, and does NOT serve the successor session (manifest row B13)."
)

MARKER_NAME = "cgg-processed-handoff-ids.txt"

L1 = "CGG EVALUATION PENDING"
L2_NEXT = "CGG HANDOFF NEXT ACTIONS"
L3 = "CGG CHARTER"
L4 = "CGG CONSUMPTION PROTOCOL"
CONTROL = "[TIC: #"

# The marker's live shape: last written when an id was recorded, months ago. Back-dating the
# FIXTURE marker (never the real one) removes any sub-second ordering ambiguity from the arms.
BACKDATE = 1773201600  # 2026-03-11T00:00:00Z — the real marker's last recorded id is dated 2026-03-11
FUTUREDATE = 1798779600  # 2027-01-01 — used ONLY to put the marker NEWER than the plan


RICH = """# Handoff — fixture RICH shape

<!-- cgg-handoff
  handoff_id: "{hid}"
  project_dir: "{zone}"
  entry_tic: 806
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
  entry_tic: 806
-->

Prose only, carrying neither Next Actions nor Not Started.
"""

POINTER = """STOP — THIS IS A POINTER, NOT THE PLAN.

<!-- cgg-handoff
  handoff_id: "{hid}"
  project_dir: "{zone}"
  entry_tic: 806
-->

<!-- cgg-handoff-pointer
  payload_mode: "pointer"
  durable_home: "{home}"
  handoff_id: "{hid}"
  entry_tic: 806
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

        for sub in ("tics", "mogul/mandates", "hooks", "cprs", "signals", "handoffs"):
            (self.zone / "audit-logs" / sub).mkdir(parents=True)
        self.tmpdir.mkdir()

        (self.zone / ".ticzone").write_text(json.dumps(
            {"name": "fixture-marker-806", "tz": "UTC", "include": ["."],
             "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"], "muffling_per_hop": 5}),
            encoding="utf-8")
        (self.zone / "audit-logs" / "tics" / "2026-09-19.jsonl").write_text(json.dumps(
            {"type": "tic", "count_mode": "counted", "global_counter_after": 806}) + "\n",
            encoding="utf-8")
        # NEVER `pending` — guard #1 against a runner spawn.
        (self.zone / "audit-logs" / "mogul" / "mandates" / "current.json").write_text(json.dumps(
            {"mandate_id": "fixture-806", "status": "consumed",
             "tic_context": {"current_tic": 806},
             "cycle_request": {"run_now": ["queue_refresh", "signal_scan"]}}), encoding="utf-8")
        (self.zone / "audit-logs" / "cprs" / "queue.jsonl").write_text("", encoding="utf-8")
        (self.zone / "audit-logs" / "signals" / "active-manifest.jsonl").write_text("", encoding="utf-8")

        self.project_key = str(self.zone).replace("/", "-")
        self.plans = self.home / ".claude" / "plans"
        self.projects = self.home / ".claude" / "projects" / self.project_key
        self.plans.mkdir(parents=True)
        self.projects.mkdir(parents=True)
        self.marker = self.home / ".claude" / MARKER_NAME

        # guard #2 against a runner spawn: mogul-runner.sh is absent from every resolve root.
        (self.proot / "cgg-runtime" / "hooks").mkdir(parents=True)
        (self.proot / "cgg-runtime" / "scripts").mkdir(parents=True)
        os.symlink(SEAL, self.proot / "cgg-runtime" / "hooks" / "cadence-handoff-seal.py")
        os.symlink(SCRIPTS / "effective-record.py",
                   self.proot / "cgg-runtime" / "scripts" / "effective-record.py")
        os.symlink(SCRIPTS / "lib", self.proot / "cgg-runtime" / "scripts" / "lib")

        self.switch = root / "switch.json"
        self.set_mode("body")

    # -- marker helpers: the FIXTURE marker only, never the real one -------------
    def make_marker(self, content: str = "", when: int = BACKDATE) -> Path:
        self.marker.write_text(content, encoding="utf-8")
        os.utime(self.marker, (when, when))
        return self.marker

    def marker_mtime_ns(self) -> int:
        return self.marker.stat().st_mtime_ns

    def set_mode(self, mode: str) -> None:
        self.switch.write_text(json.dumps({"handoff_payload_mode": mode}), encoding="utf-8")

    def runner_roots(self) -> list[Path]:
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

    def run(self, hook: Path = SESSION_RESTORE, stdin: str = "{}") -> subprocess.CompletedProcess:
        # CWD is INSIDE the fixture zone — the third pin.
        return subprocess.run(
            ["bash", str(hook)], input=stdin, text=True, capture_output=True,
            cwd=str(self.zone), env=self.env(), timeout=120,
        )


@pytest.fixture()
def fx(tmp_path):
    return Fixture(tmp_path)


def _loci(out: str) -> dict:
    return {"L1": L1 in out, "L2": L2_NEXT in out, "L3": L3 in out, "L4": L4 in out}


# ---------------------------------------------------------------------------
# THE RULED CURE — created-if-missing, mtime never bumped by the boot itself.
# ---------------------------------------------------------------------------

def test_marker_is_created_when_missing(fx):
    """Created-if-missing is the half of the rule the `touch` was also doing."""
    assert not fx.marker.exists()
    r = fx.run()
    assert CONTROL in r.stdout, "positive control DARK — the run proves nothing"
    assert fx.marker.exists(), "the marker must still be CREATED when absent"
    assert fx.marker.read_text(encoding="utf-8") == "", "creation must not invent content"


def test_creation_keeps_the_find_reference_present(fx):
    """`find -newer <missing>` errors and matches nothing, and that stderr is discarded.

    The cure must therefore never open a path where the marker is absent at the find.
    """
    assert not fx.marker.exists()
    fx.run()
    assert fx.marker.exists(), (
        "an absent marker at the find would silently match nothing — the reference must exist")


@pytest.mark.parametrize("shape,expected", [
    ("rich", {"L1": True, "L2": True, "L3": False, "L4": True}),
    ("bare", {"L1": False, "L2": False, "L3": True, "L4": True}),
])
def test_live_shaped_plan_is_discovered_without_future_dating(fx, shape, expected):
    """THE ARM THE RULING NAMES. A plan with a LIVE (present) mtime, against a marker last
    written when an id was recorded, now lights its loci. Before the cure this arm was the
    one that stayed DARK (finding F-805-2, arm E1b) even with the two-directory cure in.

    L2 and L3 are MUTUALLY EXCLUSIVE — CGG CHARTER is the ELSE of both awk ranges — so the
    RICH and BARE shapes light different loci and no single run can light both.
    """
    fx.make_marker()
    template = RICH if shape == "rich" else BARE
    p = fx.plant(fx.plans, f"live-{shape}.md", template, f"fx806-{shape}")
    r = fx.run()
    assert CONTROL in r.stdout, "positive control DARK — the run proves nothing"
    assert _loci(r.stdout) == expected
    assert str(p) in r.stdout


@pytest.mark.parametrize("shape", ["rich", "bare", "no-plan"])
def test_marker_mtime_is_unchanged_across_a_run_that_records_nothing(fx, shape):
    """session-restore.sh never records an id — cgg-gate.sh's append is the only content
    writer — so NO session-restore run may advance the marker's mtime. Read at nanosecond
    resolution (st_mtime_ns) before and after the SAME run.
    """
    fx.make_marker()
    if shape != "no-plan":
        fx.plant(fx.plans, "live.md", RICH if shape == "rich" else BARE, f"fx806-mt-{shape}")
    before = fx.marker_mtime_ns()
    r = fx.run()
    after = fx.marker_mtime_ns()
    assert CONTROL in r.stdout
    assert before == after, f"the boot advanced the marker's mtime: {before} -> {after}"
    assert before == BACKDATE * 1_000_000_000


# ---------------------------------------------------------------------------
# THE DEDUP STILL HOLDS — on BOTH mtime orderings, which are different paths.
# ---------------------------------------------------------------------------

def test_dedup_holds_when_the_marker_is_OLDER_than_the_plan(fx):
    """The plan passes the `-newer` filter and is then refused by the id check."""
    fx.make_marker("fx806-dedup\n", when=BACKDATE)
    p = fx.plant(fx.plans, "already.md", RICH, "fx806-dedup")
    assert fx.marker_mtime_ns() < p.stat().st_mtime_ns, "arm requires marker OLDER than plan"
    r = fx.run()
    assert CONTROL in r.stdout
    assert _loci(r.stdout) == {"L1": False, "L2": False, "L3": False, "L4": False}


def test_dedup_holds_when_the_marker_is_NEWER_than_the_plan(fx):
    """The plan never enters the loop at all — a different path to the same refusal."""
    p = fx.plant(fx.plans, "already.md", RICH, "fx806-dedup")
    fx.make_marker("fx806-dedup\n", when=FUTUREDATE)
    assert fx.marker_mtime_ns() > p.stat().st_mtime_ns, "arm requires marker NEWER than plan"
    r = fx.run()
    assert CONTROL in r.stdout
    assert _loci(r.stdout) == {"L1": False, "L2": False, "L3": False, "L4": False}


def test_an_unrecorded_id_is_still_processed(fx):
    """The dedup must refuse RECORDED ids only — it is not a blanket mute."""
    fx.make_marker("some-other-id\n", when=BACKDATE)
    fx.plant(fx.plans, "fresh.md", RICH, "fx806-fresh")
    r = fx.run()
    assert CONTROL in r.stdout
    assert _loci(r.stdout)["L1"] is True


# ---------------------------------------------------------------------------
# THE ABSENT-MARKER ARM AND ITS HONEST LIMIT.
# ---------------------------------------------------------------------------

def test_first_boot_after_creation_is_dark_for_a_pre_existing_plan(fx):
    """THE HONEST LIMIT, asserted rather than prosed.

    Creating a file gives it mtime NOW, so nothing that already existed can be newer than it.
    On the first boot after a fresh install the pre-existing plans therefore stay dark. The
    ruling did not rule a back-dated creation and this increment does not invent one.
    """
    assert not fx.marker.exists()
    fx.plant(fx.plans, "pre-existing.md", RICH, "fx806-pre")
    r = fx.run()
    assert CONTROL in r.stdout
    assert _loci(r.stdout) == {"L1": False, "L2": False, "L3": False, "L4": False}
    assert fx.marker.exists()


def test_the_limit_costs_exactly_one_boot(fx):
    """The bound on the limit above: the very next plan written after the creation lights."""
    fx.plant(fx.plans, "pre-existing.md", RICH, "fx806-pre")
    fx.run()
    created_ns = fx.marker_mtime_ns()
    (fx.plans / "pre-existing.md").unlink()
    p = fx.plant(fx.plans, "written-after.md", RICH, "fx806-after")
    assert p.stat().st_mtime_ns > created_ns, "arm requires the plan to post-date the creation"
    r = fx.run()
    assert CONTROL in r.stdout
    assert _loci(r.stdout)["L2"] is True
    assert fx.marker_mtime_ns() == created_ns, "the second boot must not advance it either"


# ---------------------------------------------------------------------------
# STRUCTURAL — the cured site itself.
# ---------------------------------------------------------------------------

def test_the_boot_does_not_unconditionally_touch_the_marker(fx):
    """An unconditional `touch` of the marker is the defect; it must not return."""
    code = "\n".join(
        ln for ln in SESSION_RESTORE.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#"))
    assert 'touch "$PROCESSED_IDS"' not in code, (
        "session-restore.sh touches the marker again — F-805-2 has regressed")


def test_creation_is_conditional_on_absence(fx):
    code = SESSION_RESTORE.read_text(encoding="utf-8")
    assert '[ -e "$PROCESSED_IDS" ] || : > "$PROCESSED_IDS"' in code


def test_cgg_gate_remains_the_only_content_writer(fx):
    """The ruling keeps what a processed id means and where one is recorded."""
    assert 'echo "$HANDOFF_ID" >> "$PROCESSED_IDS"' in CGG_GATE.read_text(encoding="utf-8")
    sr = SESSION_RESTORE.read_text(encoding="utf-8")
    assert '>> "$PROCESSED_IDS"' not in sr, "session-restore.sh must never record an id"


def test_rider_travels_verbatim_as_one_contiguous_unit(fx):
    """A rider wrapped across comment-prefix lines does not exist as a verbatim unit."""
    text = SESSION_RESTORE.read_text(encoding="utf-8")
    assert text.count(RIDER) >= 1
    carrier = [ln for ln in text.splitlines() if RIDER in ln]
    assert len(carrier) >= 1, "the rider must live on ONE line, not wrapped across comment lines"


def test_the_rider_comment_donates_zero_cpr_shaped_tokens(fx):
    """A provenance comment citing a cpr id or a cpr-shaped filename mints a phantom token in
    the inscribed index. The checker's OWN regex is the judge, not a recalled approximation.
    """
    spec = importlib.util.spec_from_file_location("rcc806", SCRIPTS / "review-close-check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = SESSION_RESTORE.read_text(encoding="utf-8")
    block = [ln for ln in text.splitlines()
             if ln.lstrip().startswith("#") and ("MARKER IS CREATED-IF-MISSING" in ln
                                                 or RIDER in ln)]
    assert block, "the cure's provenance comment is missing"
    for ln in block:
        assert not mod._CPR_REF_RE.findall(ln), f"comment donates a cpr-shaped token: {ln!r}"


# ---------------------------------------------------------------------------
# THE SWITCH IS READ, NEVER WRITTEN — body and a FIXTURE-ONLY pointer.
# ---------------------------------------------------------------------------

def test_switch_honoured_under_body(fx):
    fx.set_mode("body")
    fx.make_marker()
    p = fx.plant(fx.plans, "live.md", RICH, "fx806-body")
    r = fx.run()
    assert CONTROL in r.stdout
    assert str(p) in r.stdout, "under body the emitted path IS the approval artifact"


def test_switch_honoured_under_fixture_only_pointer(fx):
    """Exercised through the seal's OWN documented seam against a fixture file. The real
    cgg-runtime/config/handoff-payload-mode.json is never written by this test.
    """
    fx.set_mode("pointer")
    fx.make_marker()
    durable = fx.zone / "audit-logs" / "handoffs" / "806-fx-durable.md"
    durable.write_text(RICH.format(hid="fx806-ptr", zone=fx.zone), encoding="utf-8")
    fx.plant(fx.plans, "ptr.md", POINTER, "fx806-ptr",
             home="audit-logs/handoffs/806-fx-durable.md")
    r = fx.run()
    assert CONTROL in r.stdout
    assert str(durable) in r.stdout, "the emitted path must be the durable home"
    assert "POINTER-SUMMARY-SENTINEL" not in r.stdout


def test_every_run_pins_the_switch_inside_the_fixture(fx):
    """Guard against a future edit letting these runs fall through to the real switch: the
    seam is pinned on EVERY run, and it resolves inside tmp_path.
    """
    env = fx.env()
    pinned = Path(env["CGG_HANDOFF_PAYLOAD_MODE_CONFIG"])
    assert pinned == fx.switch and pinned.is_file()
    assert str(pinned).startswith(str(fx.root)), "the switch must live inside the fixture"
    assert Path(env["HOME"]) == fx.home, "HOME must be the fixture HOME on every run"


# ---------------------------------------------------------------------------
# REAL-ZONE SAFETY — asserted, never prosed.
# ---------------------------------------------------------------------------

def test_runner_spawn_is_impossible_in_this_fixture(fx):
    for cand in fx.runner_roots():
        assert not cand.exists(), f"mogul-runner.sh reachable at {cand}"
    mandate = json.loads(
        (fx.zone / "audit-logs" / "mogul" / "mandates" / "current.json").read_text(encoding="utf-8"))
    assert mandate["status"] != "pending", "a pending mandate is the gate's spawn precondition"


def test_hook_runs_never_write_the_real_seal_journal(fx):
    real = Path("/Users/breydentaylor/canonical/audit-logs/hooks/handoff-seals.jsonl")
    if not real.exists():
        pytest.skip("real journal absent on this machine")
    before = real.stat().st_size
    fx.make_marker()
    fx.plant(fx.plans, "live.md", RICH, "fx806-safety")
    fx.run()
    assert real.stat().st_size == before, "a fixture run reached the REAL seal journal"


def test_hook_runs_never_touch_the_real_marker(fx):
    """The fixture HOME is what keeps the real marker untouched — the hook derives the marker
    path from $HOME. This asserts that, rather than trusting it.
    """
    real = Path.home() / ".claude" / MARKER_NAME
    if not real.exists():
        pytest.skip("real marker absent on this machine")
    before = (real.stat().st_mtime_ns, real.stat().st_size,
              real.read_bytes())
    fx.make_marker()
    fx.plant(fx.plans, "live.md", RICH, "fx806-realmarker")
    fx.run()
    after = (real.stat().st_mtime_ns, real.stat().st_size, real.read_bytes())
    assert before == after, "a fixture run reached the REAL processed-ids marker"
