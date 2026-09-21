#!/usr/bin/env python3
"""Selftests for the tic-824 ruled increment — the prompt gate's two further quiet failures.

Ruling: audit-logs/governance/receipts/2026-09-21-tic822-review-822-one-ray-promoted-modified-one-absorb-and-three-ruled-increments.md
(5241 bytes, sha256 head-16 e7e555697e4cb433), /review 822 round 1 Q4, Architect-ratified,
the recommended option verbatim "One increment, both sites".

THE RULED INCREMENT, both sites, in cgg-gate.sh:
  SITE 1  queue_refresh reports UNREAD when its reader fails (a reader failure used to become
          a plausible "0_pending").
  SITE 2  an unresolvable plugin root is treated as UNRESOLVED instead of composing a
          root-anchored "/cgg-runtime/scripts" path.

DOES-NOT-SATISFY RIDER (travels verbatim; the seat's words, not the ruling's): this increment does NOT change what counts as a pending CPR, does NOT make any reader failure block or slow the prompt path, does NOT cure the same composition in posttool-microscan.sh or post-commit-sync.sh, does NOT correct the trigger manifest's comment on active_signals_snapshot, does NOT establish that an unresolvable plugin root has ever occurred in a live fire, and does NOT certify that the enumerated consumer set is the whole consumer set.

INSTRUMENT UNIT: the pytest NODE ID. Every parametrized arm expands to a DISTINCT node; there
is no subTest here, so no arm can report a PASSING parent while its children fail.

THE REAL ZONE IS NEVER A TEST SUBJECT. Every hook execution runs with
  (i)   the zone root pinned EXPLICITLY to a tmp_path fixture zone (.ticzone + CLAUDE_PROJECT_DIR),
  (ii)  HOME pointed at a fixture HOME — the marker, the processed-ids file and the assessor
        output all derive from $HOME, so this is what keeps the real ones untouched,
  (iii) TMPDIR pointed at a fixture tmpdir — the flag/trigger files derive from it, and
  (iv)  the process CWD INSIDE the fixture zone.
Fixture.run() PRE-FLIGHTS every one of those before the hook is executed even once: it resolves
each state path the hook will derive and ASSERTS it lies under tmp_path. A run whose pre-flight
fails never reaches a hook verb. Real-zone untouchedness is additionally ASSERTED, not prosed.

A MOGUL RUNNER SPAWN IS MADE IMPOSSIBLE TWO INDEPENDENT WAYS: the fixture mandate carries only
LIGHTWEIGHT cycles (the runner branch needs a non-empty heavy set), and mogul-runner.sh is
absent from ALL THREE resolve_script roots.

PATH OVERRIDE: the hook under test defaults to the real source file. Set CGG_GATE_UNDER_TEST to
run this same file against other bytes — that is how the revert control is reproduced:
  git -C <cgg repo> show <sha>:cgg-runtime/hooks/cgg-gate.sh > /tmp/old-gate.sh
  CGG_GATE_UNDER_TEST=/tmp/old-gate.sh python3 -m pytest -q <this file>
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[2] / "hooks"
SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
SEAL = HOOKS / "cadence-handoff-seal.py"
CGG_GATE = Path(os.environ.get("CGG_GATE_UNDER_TEST") or (HOOKS / "cgg-gate.sh"))

MARKER_NAME = "cgg-processed-handoff-ids.txt"

# The seat's rider for THIS increment, as one contiguous unit.
RIDER = (
    "DOES-NOT-SATISFY RIDER (travels verbatim; the seat's words, not the ruling's): this "
    "increment does NOT change what counts as a pending CPR, does NOT make any reader "
    "failure block or slow the prompt path, does NOT cure the same composition in "
    "posttool-microscan.sh or post-commit-sync.sh, does NOT correct the trigger manifest's "
    "comment on active_signals_snapshot, does NOT establish that an unresolvable plugin "
    "root has ever occurred in a live fire, and does NOT certify that the enumerated "
    "consumer set is the whole consumer set."
)

# Every rider line already carried by the hook before this increment, frozen by EXTRACTION
# from the pinned pre-cure bytes (sha16 47b99760d523dacc), never hand-typed. A cure that
# drops one of these has broken a prior ruling's carriage.
PRE_EXISTING_RIDERS = (
    "DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT change who may consume a handoff seal, does NOT rule whether the Mogul runner's headless child SHOULD fire the prompt gate, does NOT change the actor discriminator, and does NOT produce the live refusal witness the seam's primary-only acts still owe.",
    "DOES-NOT-SATISFY RIDER (travels verbatim, from the ruling): this increment does NOT restrict who may fire the gate, does NOT change the seam's primary-only acts, does NOT re-attribute the two past fires, and does NOT touch the processed-ids marker's write.",
    "DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT change which rays the audit verb flags, does NOT normalise any other output of the gate, and does NOT certify that the enumerated set is the whole consumer set.",
    "DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT flip the payload switch, does NOT establish how long the loci have been dark, does NOT change the seal journal's vocabulary, and does NOT serve the successor session (manifest row B13), which has no call site and is served only by the pointer payload's own text.",
)

# A root-anchored composition: "/cgg-runtime/..." appearing as an ABSOLUTE path head. The
# pre-cure `[ ! -d "$CGG_PLUGIN_ROOT/cgg-runtime" ]` probe yields the bare "/cgg-runtime"
# with NO trailing separator in both old and cured bytes, so the trailing "/" is exactly
# what discriminates a composed sub-path from that probe.
_ROOT_ANCHORED = re.compile(r"(?<![\w/.\-])/cgg-runtime/")


def root_anchored_lines(trace: str) -> list[str]:
    return [ln for ln in trace.splitlines() if _ROOT_ANCHORED.search(ln)]


class Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.zone = root / "zone"
        self.home = root / "home"
        self.proot = root / "pluginroot"
        self.tmpdir = root / "tmpdir"

        for sub in ("tics", "mogul/mandates", "hooks", "cprs", "signals", "handoffs", "services"):
            (self.zone / "audit-logs" / sub).mkdir(parents=True)
        self.tmpdir.mkdir()

        (self.zone / ".ticzone").write_text(json.dumps(
            {"name": "fixture-gate-quiet-824", "tz": "UTC", "include": ["."],
             "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"], "muffling_per_hop": 5}),
            encoding="utf-8")
        (self.zone / "audit-logs" / "tics" / "2026-09-21.jsonl").write_text(json.dumps(
            {"type": "tic", "count_mode": "counted", "global_counter_after": 824}) + "\n",
            encoding="utf-8")

        # LIGHTWEIGHT ONLY — the runner branch requires a non-empty HEAVY set, so this
        # mandate shape cannot reach a spawn. Guard #1.
        self.mandate = self.zone / "audit-logs" / "mogul" / "mandates" / "current.json"
        self.mandate.write_text(json.dumps(
            {"mandate_id": "fixture-824", "status": "pending",
             "tic_context": {"current_tic": 824},
             "cycle_request": {"run_now": ["queue_refresh", "signal_scan"]}}), encoding="utf-8")

        self.queue = self.zone / "audit-logs" / "cprs" / "queue.jsonl"
        self.queue.write_text("", encoding="utf-8")
        (self.zone / "audit-logs" / "signals" / "active-manifest.jsonl").write_text(
            "", encoding="utf-8")

        self.project_key = str(self.zone).replace("/", "-")
        self.plans = self.home / ".claude" / "plans"
        self.projects = self.home / ".claude" / "projects" / self.project_key
        self.plans.mkdir(parents=True)
        self.projects.mkdir(parents=True)
        self.marker = self.home / ".claude" / MARKER_NAME

        # Guard #2: mogul-runner.sh absent from every resolve root. The plugin root carries
        # only the seal and the shared lib, exactly as the sibling hook fixtures do.
        (self.proot / "cgg-runtime" / "hooks").mkdir(parents=True)
        (self.proot / "cgg-runtime" / "scripts").mkdir(parents=True)
        os.symlink(SEAL, self.proot / "cgg-runtime" / "hooks" / "cadence-handoff-seal.py")
        os.symlink(SCRIPTS / "lib", self.proot / "cgg-runtime" / "scripts" / "lib")

        self.switch = root / "switch.json"
        self.switch.write_text(json.dumps({"handoff_payload_mode": "body"}), encoding="utf-8")

    # ---- the queue, written by shape ------------------------------------------------
    def write_queue(self, rows: list[dict]) -> None:
        self.queue.write_text(
            "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def runner_roots(self) -> list[Path]:
        return [
            self.zone / "scripts" / "mogul-runner.sh",
            self.proot / "cgg-runtime" / "scripts" / "mogul-runner.sh",
            self.home / ".claude" / "cgg-runtime" / "scripts" / "mogul-runner.sh",
        ]

    # ---- environment ----------------------------------------------------------------
    def env(self, plugin_root: str | None = "fixture") -> dict:
        e = dict(os.environ)
        e.update({
            "HOME": str(self.home),
            "CLAUDE_PROJECT_DIR": str(self.zone),
            "TMPDIR": str(self.tmpdir),
            "PYTHONDONTWRITEBYTECODE": "1",
            "CGG_HANDOFF_PAYLOAD_MODE_CONFIG": str(self.switch),
        })
        e.pop("CGG_OBLIGATION_MANDATE_ID", None)
        if plugin_root == "fixture":
            e["CLAUDE_PLUGIN_ROOT"] = str(self.proot)
        elif plugin_root is None:
            e.pop("CLAUDE_PLUGIN_ROOT", None)      # the UNRESOLVED arm
        else:
            e["CLAUDE_PLUGIN_ROOT"] = plugin_root  # a STALE non-empty root
        return e

    def resolved_state_paths(self, env: dict) -> dict:
        """Every state path the hook derives, resolved the way the hook resolves it."""
        zone = Path(env["CLAUDE_PROJECT_DIR"])
        home = Path(env["HOME"])
        tmp = Path(env["TMPDIR"])
        return {
            "ZONE_ROOT": zone,
            "META_LOG": zone / "audit-logs" / "services" / "gate-meta.jsonl",
            "MANDATE_FILE": zone / "audit-logs" / "mogul" / "mandates" / "current.json",
            "QUEUE_FILE": zone / "audit-logs" / "cprs" / "queue.jsonl",
            "ACTIVE_MANIFEST": zone / "audit-logs" / "signals" / "active-manifest.jsonl",
            "PAUSE_FILE": zone / "audit-logs" / "hooks" / "pause-after-boot-active.json",
            "PROCESSED_IDS": home / ".claude" / MARKER_NAME,
            "ASSESSOR_OUTPUT": home / ".claude" / "grapple-proposals" / "latest.md",
            "FLAG_DIR": tmp / "claude_cgg" / str(zone).replace("/", "-"),
        }

    def preflight(self, env: dict) -> dict:
        """THE FIRST ACT OF EVERY EXECUTION. Print the resolved state paths and assert each
        lies under the scratch root before any hook verb runs."""
        paths = self.resolved_state_paths(env)
        print(f"\n--- PRE-FLIGHT (scratch root: {self.root}) ---")
        for name, p in paths.items():
            under = str(p).startswith(str(self.root) + os.sep)
            print(f"  {'OK ' if under else 'ESCAPED'} {name:16s} {p}")
            assert under, f"PRE-FLIGHT FAILED: {name} resolves OUTSIDE scratch: {p}"
        return paths

    def run(self, plugin_root: str | None = "fixture", stdin: str = '{"prompt":"hello"}',
            trace: bool = False) -> subprocess.CompletedProcess:
        env = self.env(plugin_root)
        self.preflight(env)
        argv = ["bash", "-x", str(CGG_GATE)] if trace else ["bash", str(CGG_GATE)]
        return subprocess.run(
            argv, input=stdin, text=True, capture_output=True,
            cwd=str(self.zone), env=env, timeout=120,
        )

    # ---- readings -------------------------------------------------------------------
    def lightweight_results(self) -> str:
        """The mandate file's own record — a surface independent of the hook's stdout."""
        return json.loads(self.mandate.read_text(encoding="utf-8")).get(
            "lightweight_results", "<absent>")


@pytest.fixture()
def fx(tmp_path):
    return Fixture(tmp_path)


PENDING_ROWS = [
    {"id": "fx824-a", "status": "pending"},
    {"id": "fx824-b", "status": "enrichment_needed"},
    {"id": "fx824-c", "status": "review_ready"},
]
TERMINAL_ROWS = [
    {"id": "fx824-x", "status": "promoted"},
    {"id": "fx824-y", "status": "absorbed"},
]


# ===========================================================================
# PRE-FLIGHT, as its own node
# ===========================================================================

def test_preflight_every_resolved_state_path_is_under_scratch(fx):
    """The population declaration, executed: this build WRITES through HOME/zone/TMPDIR, so
    it is PROTECTED by re-pointing them. Nine derived paths, each asserted under scratch."""
    paths = fx.preflight(fx.env())
    assert len(paths) == 9
    for name, p in paths.items():
        assert str(p).startswith(str(fx.root) + os.sep), name


# ===========================================================================
# SITE 1 — queue_refresh: UNREAD, never a plausible zero
# ===========================================================================

def test_queue_refresh_reader_failure_reports_unread(fx):
    """THE RULED CURE, site 1. An unreadable queue file makes the reader fail; before the
    cure ${PENDING:-0} turned that failure into a confident "0_pending"."""
    fx.write_queue(PENDING_ROWS)
    os.chmod(fx.queue, 0o000)
    try:
        try:
            fx.queue.read_text(encoding="utf-8")
            pytest.skip("queue still readable after chmod 000 (running as root?) — arm inert")
        except PermissionError:
            pass
        r = fx.run()
        assert r.returncode == 0, "the gate must never break the prompt path"
        assert "queue_refresh=UNREAD_pending" in r.stdout, (
            f"a failed reader did not report UNREAD; stdout={r.stdout!r}")
        assert "queue_refresh=0_pending" not in r.stdout, "the plausible zero survived"
        assert "queue_refresh=UNREAD_pending" in fx.lightweight_results()
    finally:
        os.chmod(fx.queue, 0o644)


def test_queue_refresh_healthy_count_is_unchanged(fx):
    """NO-REGRESSION. A readable queue still reports its real count, by member."""
    fx.write_queue(PENDING_ROWS + TERMINAL_ROWS)
    r = fx.run()
    assert r.returncode == 0
    assert "queue_refresh=3_pending" in r.stdout, f"stdout={r.stdout!r}"
    assert "queue_refresh=3_pending" in fx.lightweight_results()


def test_queue_refresh_a_real_zero_stays_a_real_zero(fx):
    """THE DISCRIMINATION THE CURE MUST NOT BLUR. A queue whose rows are all terminal has
    genuinely zero pending, and that must still read 0 — never UNREAD."""
    fx.write_queue(TERMINAL_ROWS)
    r = fx.run()
    assert r.returncode == 0
    assert "queue_refresh=0_pending" in r.stdout, f"stdout={r.stdout!r}"
    assert "UNREAD" not in r.stdout.split("queue_refresh=")[1][:20]


def test_queue_refresh_absent_queue_still_reports_no_queue(fx):
    """NO-REGRESSION. An absent queue has its own typed answer and is not a reader failure."""
    fx.queue.unlink()
    r = fx.run()
    assert r.returncode == 0
    assert "queue_refresh=no_queue" in r.stdout, f"stdout={r.stdout!r}"


def test_queue_refresh_unread_is_not_a_crash(fx):
    """UNREAD is a report, not an exception: the mandate still completes its lifecycle."""
    fx.write_queue(PENDING_ROWS)
    os.chmod(fx.queue, 0o000)
    try:
        try:
            fx.queue.read_text(encoding="utf-8")
            pytest.skip("queue still readable after chmod 000 (running as root?) — arm inert")
        except PermissionError:
            pass
        r = fx.run()
        assert r.returncode == 0
        m = json.loads(fx.mandate.read_text(encoding="utf-8"))
        assert m["status"] == "consumed", "a failed reader must not strand the mandate"
        assert "completed_at" in m
    finally:
        os.chmod(fx.queue, 0o644)


# ===========================================================================
# SITE 2 — an unresolvable plugin root is UNRESOLVED, never root-anchored
# ===========================================================================

def test_unresolvable_plugin_root_composes_no_root_anchored_path(fx):
    """THE RULED CURE, site 2. With no override, no project-local vendor tree and no
    $HOME/.claude/cgg-runtime, the root is unresolvable — and nothing may be composed
    from it. The trace is the hook's OWN expansions, not a re-derivation."""
    assert not (fx.home / ".claude" / "cgg-runtime").exists(), "arm requires an unresolvable root"
    r = fx.run(plugin_root=None, trace=True)
    hits = root_anchored_lines(r.stderr)
    assert not hits, "root-anchored paths composed from an unresolved root:\n" + "\n".join(hits)


def test_unresolvable_plugin_root_is_typed_unresolved(fx):
    """UNRESOLVED is a typed state the consumers read, not an empty string they each re-guess."""
    r = fx.run(plugin_root=None, trace=True)
    assert "CGG_PLUGIN_ROOT_STATE=unresolved" in r.stderr, (
        "the unresolvable root was never typed")


def test_unresolved_root_yields_no_root_anchored_script_candidate(fx):
    """resolve_script must DROP the plugin-anchored candidate, never degrade it to "/<name>"
    (which an empty scripts dir would produce) and never keep "/cgg-runtime/scripts/<name>"."""
    r = fx.run(plugin_root=None, trace=True)
    bad = [ln for ln in r.stderr.splitlines()
           if re.search(r"(?<![\w/.\-])/(mogul-runner\.sh|trigger-router\.py|"
                        r"inbox-envelope\.py|ripple-assessor\.py)\b", ln)]
    assert not bad, "resolve_script composed a root-anchored candidate:\n" + "\n".join(bad)
    assert not root_anchored_lines(r.stderr)


def test_resolved_plugin_root_is_unchanged(fx):
    """NO-REGRESSION, the path that actually runs in production: when the root resolves,
    the scripts dir is composed exactly as before and the seal rule stays reachable."""
    r = fx.run(plugin_root="fixture", trace=True)
    assert f"CGG_SCRIPTS_DIR={fx.proot}/cgg-runtime/scripts" in r.stderr, (
        "the resolved composition moved")
    assert r.returncode == 0


def test_stale_non_empty_plugin_root_is_also_unresolved(fx):
    """A root that does not carry cgg-runtime/ is not a root. SCOPE NOTE: the ruling names
    the EMPTY case; this arm is the same predicate applied to a stale non-empty override,
    and it is declared as such in the build receipt."""
    stale = str(fx.root / "no-such-plugin-root")
    r = fx.run(plugin_root=stale, trace=True)
    assert "CGG_PLUGIN_ROOT_STATE=unresolved" in r.stderr
    assert f"CGG_SCRIPTS_DIR={stale}/cgg-runtime/scripts" not in r.stderr, (
        "a stale root was still composed from")


def test_unresolved_root_hook_still_exits_zero_fail_soft(fx):
    """FAIL-SOFT, NEVER FAIL-CLOSED. An unresolved root must never break the prompt path."""
    r = fx.run(plugin_root=None)
    assert r.returncode == 0, f"stderr={r.stderr[-2000:]!r}"


# ===========================================================================
# RIDERS AND STRUCTURE
# ===========================================================================

def test_pre_existing_riders_still_travel_verbatim(fx):
    """A cure that drops a prior ruling's rider has broken its carriage. Member-wise."""
    text = CGG_GATE.read_text(encoding="utf-8")
    missing = [r for r in PRE_EXISTING_RIDERS if r not in text]
    assert not missing, f"{len(missing)} pre-existing rider(s) dropped: {missing}"


def test_new_rider_travels_verbatim_as_one_contiguous_unit(fx):
    """A rider wrapped across comment-prefix lines does not exist as a verbatim unit. It must
    appear at BOTH cured sites, because a reader at either one could mistake it for
    satisfying the withheld thing."""
    text = CGG_GATE.read_text(encoding="utf-8")
    assert text.count(RIDER) == 2, (
        f"the rider must ride BOTH cured sites, found {text.count(RIDER)}")
    carriers = [ln for ln in text.splitlines() if RIDER in ln]
    assert len(carriers) == 2, "each rider must live on ONE line, not wrapped"


def test_the_cure_comments_donate_zero_cpr_shaped_tokens(fx):
    """A provenance comment citing a cpr id or a cpr-shaped filename mints a phantom token in
    the inscribed index. The checker's OWN regex is the judge, never a recalled approximation."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("rcc824", SCRIPTS / "review-close-check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = CGG_GATE.read_text(encoding="utf-8")
    block = [ln for ln in text.splitlines()
             if ln.lstrip().startswith("#")
             and ("UNREAD, NEVER A PLAUSIBLE ZERO (ruled /review 822" in ln
                  or "UNRESOLVED, NEVER A ROOT-ANCHORED PATH" in ln
                  or RIDER in ln)]
    assert block, "the cure's provenance comments are missing"
    for ln in block:
        assert not mod._CPR_REF_RE.findall(ln), f"comment donates a cpr-shaped token: {ln!r}"


def test_no_second_derivation_of_the_plans_directory(fx):
    """Guards the tic-805 rule against this increment: the plans directory must never be
    re-derived in CODE (comments are documentation, not derivation)."""
    code = "\n".join(ln for ln in CGG_GATE.read_text(encoding="utf-8").splitlines()
                     if not ln.lstrip().startswith("#"))
    assert ".claude/plans" not in code, "cgg-gate.sh re-derives the plans directory in CODE"
    assert "mod.candidate_plan_dirs()" in CGG_GATE.read_text(encoding="utf-8"), (
        "call site C must still CONSUME the one rule")


def test_gate_remains_the_only_processed_ids_content_writer(fx):
    """The tic-806 ruling's invariant must survive this increment untouched."""
    assert 'echo "$HANDOFF_ID" >> "$PROCESSED_IDS"' in CGG_GATE.read_text(encoding="utf-8")


# ===========================================================================
# REAL-ZONE SAFETY — asserted, never prosed
# ===========================================================================

def test_fixture_runs_never_write_the_real_gate_meta_log(fx):
    real = Path("/Users/breydentaylor/canonical/audit-logs/services/gate-meta.jsonl")
    if not real.exists():
        pytest.skip("real gate-meta log absent on this machine")
    before = real.stat().st_size
    fx.write_queue(PENDING_ROWS)
    fx.run()
    fx.run(plugin_root=None)
    assert real.stat().st_size == before, "a fixture run reached the REAL gate-meta log"


def test_fixture_runs_never_touch_the_real_processed_ids_marker(fx):
    real = Path(os.path.expanduser("~")) / ".claude" / MARKER_NAME
    if not real.exists():
        pytest.skip("real marker absent on this machine")
    before = (real.stat().st_mtime_ns, real.stat().st_size, real.read_bytes())
    fx.write_queue(PENDING_ROWS)
    fx.run()
    after = (real.stat().st_mtime_ns, real.stat().st_size, real.read_bytes())
    assert before == after, "a fixture run reached the REAL processed-ids marker"


def test_runner_spawn_is_impossible_in_this_fixture(fx):
    for cand in fx.runner_roots():
        assert not cand.exists(), f"mogul-runner.sh reachable at {cand}"
    mandate = json.loads(fx.mandate.read_text(encoding="utf-8"))
    heavy = [c for c in mandate["cycle_request"]["run_now"]
             if c not in ("queue_refresh", "signal_scan")]
    assert heavy == [], "a non-empty heavy set is the gate's runner-spawn precondition"
