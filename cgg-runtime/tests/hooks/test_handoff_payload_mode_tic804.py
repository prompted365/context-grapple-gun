#!/usr/bin/env python3
"""Selftests for the handoff payload-mode switch (tic 804, /review-803 Deliverable 2).

LANDED INERT. The switch ships at "body"; these tests drive "pointer" ONLY inside
tempfile fixture zones with a fixture HOME and an env-pointed fixture switch file.
NOTHING here reads or writes the real zone, the real HOME, ~/.claude/plans/, the real
seals journal, or the real current-seal file.

Does-not-satisfy rider (travels verbatim):

**Does-not-satisfy rider (travels verbatim):** this increment does NOT remove or replace the local harness patch, does NOT rule which promoter is the seal seam's ordinary path (the tic-801 born, /review 804), does NOT cure the injected-plan-prompt dispatch gap (the tic-802 born, /review 805), and does NOT make any claim that the approval surface's budget is fixed across future harness versions — the born measured five versions and the pointer is chosen precisely so that the question stops mattering.

This seat's addition (ent_harpoon_build_citizen, tic 804 — MINE, not the ruling's):
this increment lands the pointer path INERT. No live boundary has been carried on it.
A fixture rollback is not a live rollback. The new path may not become the default
until the drill has passed.
"""

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

CGG = Path(__file__).resolve().parents[2]
SEAL_SRC = CGG / "hooks" / "cadence-handoff-seal.py"
SKILL = CGG / "skills" / "cadence" / "SKILL.md"
CGG_REPO = CGG.parent
SEAL_REPO_PATH = "cgg-runtime/hooks/cadence-handoff-seal.py"


def _load_seal_module():
    """Import the seal for its PURE helpers only. Never call a writer through this
    handle without rebinding the zone — import binds the REAL zone root."""
    spec = importlib.util.spec_from_file_location("cadence_handoff_seal_t804", SEAL_SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SEAL = _load_seal_module()


def _receipt(stderr: str) -> dict:
    """The stager prints a one-line JSON receipt on stderr, possibly alongside
    human-readable lines. Find the JSON line rather than assuming its position."""
    for line in stderr.strip().splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    raise AssertionError(f"no JSON receipt on stderr: {stderr!r}")


def sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class Fixture:
    def __init__(self, name, mode="body"):
        self.base = Path(tempfile.mkdtemp(prefix=f"t804-{name}-"))
        self.zone = self.base / "zone"
        self.home = self.base / "home"
        (self.zone / "audit-logs" / "tics").mkdir(parents=True)
        (self.zone / "audit-logs" / "hooks").mkdir(parents=True)
        (self.zone / "audit-logs" / "handoffs").mkdir(parents=True)
        (self.home / ".claude" / "plans").mkdir(parents=True)
        (self.zone / ".ticzone").write_text(json.dumps({"name": f"fx-{name}"}))
        self.switch = self.base / "handoff-payload-mode.json"
        self.set_mode(mode)
        self.env = dict(os.environ)
        self.env["HOME"] = str(self.home)
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"
        self.env["CGG_HANDOFF_PAYLOAD_MODE_CONFIG"] = str(self.switch)
        # the hook runs from a copy INSIDE the fixture zone, so its own zone walk-up
        # resolves the fixture .ticzone and never the real canonical zone.
        self.seal = self.zone / "cadence-handoff-seal.py"
        shutil.copy2(SEAL_SRC, self.seal)

    def set_mode(self, mode):
        """THE FLIP: one key, one file."""
        self.switch.write_text(json.dumps({"handoff_payload_mode": mode}, indent=2) + "\n")

    def marker(self, emission_id, work_tic, entry_tic, state="interstitial"):
        (self.zone / "audit-logs" / "tics" / ".interstitial-marker.json").write_text(
            json.dumps({"state": state, "emission_id": emission_id,
                        "work_tic": work_tic, "entry_tic": entry_tic}))

    def run(self, *args, stdin=""):
        return subprocess.run(["python3", str(self.seal), *args], input=stdin,
                              capture_output=True, text=True, env=self.env, timeout=60)

    def hook(self, payload):
        return self.run(stdin=json.dumps(payload))

    def reconcile(self):
        # agent_id EMPTY == the primary; only the primary may consume a seal.
        return self.run("--reconcile-at-start", "--zone-root", str(self.zone))

    def journal(self):
        j = self.zone / "audit-logs" / "hooks" / "handoff-seals.jsonl"
        return [json.loads(l) for l in j.read_text().splitlines()] if j.is_file() else []

    def current(self):
        c = self.zone / "audit-logs" / "hooks" / "handoff-seal-current.json"
        return json.loads(c.read_text()) if c.is_file() else None

    def staged(self):
        s = self.zone / "audit-logs" / "hooks" / "handoff-seal-staged.json"
        return json.loads(s.read_text()) if s.is_file() else None


def body_plan(project_dir, work_tic, entry_tic, handoff_id, filler="body line\n"):
    return (f"# {handoff_id}\n\n"
            f"<!-- cgg-handoff\n  handoff_id: \"{handoff_id}\"\n"
            f"  project_dir: \"{project_dir}\"\n  work_tic: {work_tic}\n"
            f"  entry_tic: {entry_tic}\n-->\n\n"
            f"## Next Actions\n\n" + filler * 40 +
            f"\n<!-- cgg-evaluate\n  handoff_id: \"{handoff_id}\"\n"
            f"  pending_cprs_expected: 0\n-->\n")


# ---------------------------------------------------------------------------
# 1. The durable-home key is a PURE function
# ---------------------------------------------------------------------------

def test_durable_home_filename_is_pure_and_deterministic():
    a = SEAL.durable_home_filename(805, "tic804-close-for-tic805-entry")
    b = SEAL.durable_home_filename(805, "tic804-close-for-tic805-entry")
    assert a == b, "same input must give the same filename"
    assert a != SEAL.durable_home_filename(806, "tic804-close-for-tic805-entry")


def test_durable_home_filename_is_filename_safe_for_colon_bearing_ids():
    # a handoff id carries colons — the live ones look like this
    name = SEAL.durable_home_filename(805, "2026-09-19T13:12:00Z-syncopate-drill")
    assert ":" not in name and "/" not in name and " " not in name
    assert re.fullmatch(r"[A-Za-z0-9._-]+\.md", name), name


def test_durable_home_filename_does_not_collide_after_sanitization():
    # two ids that SANITIZE alike must still map to distinct filenames
    one = SEAL.durable_home_filename(805, "a:b")
    two = SEAL.durable_home_filename(805, "a-b")
    assert one != two, "sanitization is lossy; the raw-id digest must disambiguate"


def test_durable_home_relpath_sits_outside_both_globbed_plan_dirs():
    rel = SEAL.durable_home_relpath(805, "x")
    assert rel.startswith("audit-logs/handoffs/")
    assert ".claude/plans" not in rel and ".claude/projects" not in rel


# ---------------------------------------------------------------------------
# 2. The switch FAILS TO BODY
# ---------------------------------------------------------------------------

def _mode_of(fx, extra_env=None):
    env = dict(fx.env)
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(["python3", str(fx.seal), "--payload-mode"], capture_output=True,
                       text=True, env=env, timeout=60)
    return json.loads(r.stdout), r.stderr


def test_absent_switch_means_body_and_says_so_on_stderr():
    fx = Fixture("absent")
    # every candidate absent: env points nowhere, the fixture copy has no ../config,
    # and the fixture HOME has no ~/.claude/cgg-runtime/config
    out, err = _mode_of(fx, {"CGG_HANDOFF_PAYLOAD_MODE_CONFIG": str(fx.base / "nope.json")})
    assert out["handoff_payload_mode"] == "body"
    assert out["source"] == "absent"
    assert "ABSENT" in err and "body" in err


def test_malformed_switch_means_body_and_says_so_on_stderr():
    fx = Fixture("malformed")
    fx.switch.write_text("{{{ not json")
    out, err = _mode_of(fx)
    assert out["handoff_payload_mode"] == "body"
    assert out["source"].startswith("malformed:")
    assert "MALFORMED" in err


def test_unrecognized_value_means_body_and_says_so_on_stderr():
    fx = Fixture("weird")
    fx.switch.write_text(json.dumps({"handoff_payload_mode": "Pointer!"}))
    out, err = _mode_of(fx)
    assert out["handoff_payload_mode"] == "body"
    assert "unrecognized" in out["source"]
    assert "unrecognized" in err


def test_switch_is_a_single_key_landed_at_body_in_the_repo():
    """THE SHIPPED STATE: inert. If this fails the increment is no longer inert."""
    cfg = json.loads((CGG / "config" / "handoff-payload-mode.json").read_text())
    assert cfg == {"handoff_payload_mode": "body"}, "the switch must ship at body"


# ---------------------------------------------------------------------------
# 3. BODY MODE IS UNCHANGED — against the pre-change hook from git
# ---------------------------------------------------------------------------

def _pre_change_seal(zone):
    """The pre-change hook, from git, placed INSIDE the fixture zone so its own
    fail-closed zone walk-up resolves the FIXTURE .ticzone (law #6)."""
    r = subprocess.run(["git", "-C", str(CGG_REPO), "show", f"HEAD:{SEAL_REPO_PATH}"],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        pytest.skip("pre-change hook not retrievable from git")
    p = Path(zone) / "prechange-cadence-handoff-seal.py"
    p.write_text(r.stdout, encoding="utf-8")
    return p


VOLATILE = {"staged_at", "approved_at", "promoted_at", "consumed_at", "at",
            "stamped_at", "session_id", "agent_id"}


def _strip(obj):
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k not in VOLATILE}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


def test_body_mode_journal_row_is_identical_to_the_pre_change_hook():
    """The proof the OLD path is untouched: the same boundary carried on the
    pre-change hook and on this hook journals the SAME row, modulo timestamps."""
    plan = None
    rows = {}
    for label in ("prechange", "postchange"):
        fx = Fixture(f"bodyparity-{label}", mode="body")
        fx.marker("em-P", 7, 8)
        if plan is None:
            plan = body_plan(str(fx.zone), 7, 8, "fixture-parity-handoff")
        seal = fx.seal
        if label == "prechange":
            seal = _pre_change_seal(fx.zone)
        pre = {"hook_event_name": "PreToolUse", "tool_input": {"plan": plan},
               "session_id": "fx"}
        post = {"hook_event_name": "PostToolUse", "tool_input": {"plan": plan},
                "tool_response": {"planFilePath": "/tmp/fixture-plan.md"},
                "session_id": "fx"}
        for payload in (pre, post):
            subprocess.run(["python3", str(seal)], input=json.dumps(payload),
                           capture_output=True, text=True, env=fx.env, timeout=60)
        rows[label] = _strip(fx.journal())
    assert rows["prechange"], "control produced no journal row — the parity test would be vacuous"
    assert rows["prechange"] == rows["postchange"], (
        "BODY MODE REGRESSION: the journal row changed shape against the pre-change hook")


def test_body_mode_writes_no_payload_mode_key():
    """Absence of a mode key MEANS body — no body-mode row may carry one."""
    fx = Fixture("bodynokey", mode="body")
    fx.marker("em-B", 7, 8)
    plan = body_plan(str(fx.zone), 7, 8, "fixture-nokey")
    fx.hook({"hook_event_name": "PreToolUse", "tool_input": {"plan": plan}})
    fx.hook({"hook_event_name": "PostToolUse", "tool_input": {"plan": plan},
             "tool_response": {"planFilePath": "/tmp/p.md"}})
    for row in fx.journal():
        assert "payload_mode" not in row
        assert "payload_chars" not in row
        assert "durable_home" not in row
        assert "payload_mode_epoch" not in row


# ---------------------------------------------------------------------------
# 4. POINTER MODE — staging, composition, B13
# ---------------------------------------------------------------------------

def _stage(fx, body, entry_tic, handoff_id):
    return fx.run("--stage-pointer-payload", "--zone-root", str(fx.zone),
                  "--entry-tic", str(entry_tic), "--handoff-id", handoff_id, stdin=body)


def test_pointer_stage_writes_the_durable_home_and_returns_a_pointer_payload():
    fx = Fixture("stage", mode="pointer")
    # a REALISTIC handoff: the three live plans measure 29-53KB
    body = body_plan(str(fx.zone), 7, 8, "fixture-stage-handoff", filler="body line\n" * 80)
    r = _stage(fx, body, 8, "fixture-stage-handoff")
    receipt = _receipt(r.stderr)
    assert receipt["payload_mode"] == "pointer" and receipt["fallback"] is False
    home = fx.zone / receipt["durable_home"]
    assert home.is_file(), "the body must land in the durable home BEFORE the payload exists"
    assert home.read_text() == body, "the durable home holds the body verbatim"
    assert receipt["content_sha16"] == sha16(body)
    assert len(body) > 25_000, "the control body must be live-sized for this comparison"
    assert len(r.stdout) < len(body) / 10, (
        "on a live-sized handoff the pointer payload must be a small fraction of the body")


def test_b13_successor_imperative_survives_verbatim_into_the_composed_payload():
    """B13 has NO call site. The imperative is the ONLY re-point available, so it
    must reach the payload as one contiguous, unaltered constant."""
    fx = Fixture("b13", mode="pointer")
    body = body_plan(str(fx.zone), 7, 8, "fixture-b13-handoff")
    r = _stage(fx, body, 8, "fixture-b13-handoff")
    assert SEAL.SUCCESSOR_IMPERATIVE in r.stdout, "B13 imperative did not survive verbatim"
    assert r.stdout.startswith(SEAL.SUCCESSOR_IMPERATIVE), "the imperative must come FIRST"


def test_both_machine_blocks_travel_verbatim_into_the_payload():
    """Every marker-referencer (M1, M2, M4, M5, M7, M9) is untouched only if BOTH
    blocks travel verbatim IN THE PAYLOAD, not merely in the durable home."""
    fx = Fixture("blocks", mode="pointer")
    body = body_plan(str(fx.zone), 7, 8, "fixture-blocks-handoff")
    r = _stage(fx, body, 8, "fixture-blocks-handoff")
    hb = SEAL.HANDOFF_BLOCK_FULL_RE.search(body).group(0)
    eb = SEAL.EVALUATE_BLOCK_FULL_RE.search(body).group(0)
    assert hb in r.stdout, "cgg-handoff block missing from the payload"
    assert eb in r.stdout, "cgg-evaluate block missing from the payload"


def test_pointer_payload_carries_path_id_hash_and_a_bounded_summary():
    fx = Fixture("fields", mode="pointer")
    body = body_plan(str(fx.zone), 7, 8, "fixture-fields-handoff")
    r = _stage(fx, body, 8, "fixture-fields-handoff")
    ptr = SEAL.parse_pointer_block(r.stdout)
    assert ptr["payload_mode"] == "pointer"
    assert ptr["handoff_id"] == "fixture-fields-handoff"
    assert ptr["content_sha16"] == sha16(body)
    assert ptr["durable_home"].startswith("audit-logs/handoffs/")
    assert "Bounded summary" in r.stdout


def test_durable_home_write_failure_falls_back_to_body():
    """A pointer is NEVER submitted to a home that does not hold its body."""
    fx = Fixture("fallback", mode="pointer")
    body = body_plan(str(fx.zone), 7, 8, "fixture-fallback-handoff")
    # make the durable home undreatable: replace the directory with a FILE
    shutil.rmtree(fx.zone / "audit-logs" / "handoffs")
    (fx.zone / "audit-logs" / "handoffs").write_text("not a directory")
    r = _stage(fx, body, 8, "fixture-fallback-handoff")
    receipt = _receipt(r.stderr)
    assert receipt["payload_mode"] == "body" and receipt["fallback"] is True
    assert r.stdout == body, "the fallback must submit the BODY, unaltered"


# ---------------------------------------------------------------------------
# 5. POINTER MODE — the seal binds the DURABLE HOME, fail-closed
# ---------------------------------------------------------------------------

def _stage_and_capture(fx, entry_tic=8, handoff_id="fixture-bind-handoff"):
    body = body_plan(str(fx.zone), 7, entry_tic, handoff_id)
    r = _stage(fx, body, entry_tic, handoff_id)
    return body, r.stdout, _receipt(r.stderr)


def test_pointer_capture_binds_plan_hash_to_the_durable_home_content():
    fx = Fixture("bind", mode="pointer")
    fx.marker("em-PT", 7, 8)
    body, payload, receipt = _stage_and_capture(fx)
    fx.hook({"hook_event_name": "PreToolUse", "tool_input": {"plan": payload}})
    staged = fx.staged()
    assert staged["payload_mode"] == "pointer"
    assert staged["plan_captured"] is True
    assert staged["plan_hash"] == sha16(body), "plan_hash must bind the BODY, not the pointer"
    assert staged["plan_hash"] != sha16(payload)
    assert staged["plan_chars"] == len(body)
    assert staged["payload_chars"] == len(payload), "payload_chars is recorded SEPARATELY"


def test_dangling_pointer_is_refused_typed_and_loud():
    """The pre-approval write's failure story — the one no drill yet covered."""
    fx = Fixture("dangling", mode="pointer")
    fx.marker("em-DG", 7, 8)
    body, payload, receipt = _stage_and_capture(fx)
    (fx.zone / receipt["durable_home"]).unlink()          # the home goes away
    r = fx.hook({"hook_event_name": "PreToolUse", "tool_input": {"plan": payload}})
    staged = fx.staged()
    assert staged["plan_captured"] is False
    assert staged["plan_hash"] is None
    assert staged["plan_capture_refusal"]["reason"] == "pointer_durable_home_missing"
    assert "REFUSED" in r.stderr, "the refusal must be LOUD"


def test_carried_hash_mismatch_is_refused_typed_and_loud():
    fx = Fixture("mismatch", mode="pointer")
    fx.marker("em-MM", 7, 8)
    body, payload, receipt = _stage_and_capture(fx)
    (fx.zone / receipt["durable_home"]).write_text(body + "\nTAMPERED\n")
    r = fx.hook({"hook_event_name": "PreToolUse", "tool_input": {"plan": payload}})
    staged = fx.staged()
    assert staged["plan_captured"] is False
    assert staged["plan_capture_refusal"]["reason"] == "pointer_content_hash_mismatch"
    assert staged["plan_capture_refusal"]["carried_content_sha16"] == sha16(body)
    assert staged["plan_capture_refusal"]["recomputed_content_sha16"] != sha16(body)
    assert "REFUSED" in r.stderr


# ---------------------------------------------------------------------------
# 6. POINTER MODE — the recovery seam resolves the SAME binding
# ---------------------------------------------------------------------------

def _stage_for_recovery(fx, entry_tic=8, handoff_id="fixture-rec-handoff"):
    body, payload, receipt = _stage_and_capture(fx, entry_tic, handoff_id)
    # the harness auto-saves the APPROVED PAYLOAD as the plan file
    (fx.home / ".claude" / "plans" / "fixture-rec.md").write_text(payload)
    (fx.zone / "audit-logs" / "hooks" / "handoff-seal-staged.json").write_text(json.dumps({
        "type": "handoff_seal", "stage": "staged_pre_approval", "boundary_bound": True,
        "activation": {"emission_id": "em-RC", "entry_tic": entry_tic, "mode": "continuous"},
        "plan_captured": True, "plan_hash": sha16(body)}))
    return body, payload, receipt


def test_pointer_recovery_resolves_the_same_binding_deterministically():
    fx = Fixture("recover", mode="pointer")
    fx.marker("em-RC", 7, 8)
    body, payload, receipt = _stage_for_recovery(fx)
    fx.reconcile()
    cur = fx.current()
    assert cur is not None, "recovery must promote a verifying pointer boundary"
    assert cur["promoted_by"] == "sessionstart_recovery"
    assert cur["plan_hash"] == sha16(body), "recovery binds the DURABLE HOME's content"
    assert cur["payload_mode"] == "pointer"
    assert cur["plan_chars"] == len(body)
    assert cur["payload_chars"] == len(payload)


def test_pointer_recovery_refuses_a_missing_durable_home():
    fx = Fixture("recovermiss", mode="pointer")
    fx.marker("em-RC", 7, 8)
    body, payload, receipt = _stage_for_recovery(fx)
    (fx.zone / receipt["durable_home"]).unlink()
    fx.reconcile()
    assert fx.current() is None, "a pointer with no body must NOT be promoted"
    reasons = [r.get("reason") for r in fx.journal()
               if r.get("journal_event") == "recovery_refused"]
    assert "pointer_durable_home_missing" in reasons
    marker = json.loads((fx.zone / "audit-logs" / "tics" / ".interstitial-marker.json").read_text())
    assert marker["state"] == "interstitial", "a refused boundary stays interstitial"


# ---------------------------------------------------------------------------
# 7. The EPOCH MARKER — forward-only, first pointer row only
# ---------------------------------------------------------------------------

def test_first_pointer_row_carries_the_epoch_marker_and_later_rows_do_not():
    fx = Fixture("epoch", mode="pointer")
    stamped = []
    for i, entry in enumerate((8, 9)):
        fx.marker(f"em-E{i}", entry - 1, entry)
        body, payload, _ = _stage_and_capture(fx, entry, f"fixture-epoch-{i}")
        fx.hook({"hook_event_name": "PreToolUse", "tool_input": {"plan": payload}})
        fx.hook({"hook_event_name": "PostToolUse", "tool_input": {"plan": payload},
                 "tool_response": {"planFilePath": "/tmp/p.md"}})
        stamped.append([r for r in fx.journal() if "payload_mode_epoch" in r])
    assert len(stamped[0]) == 1, "the FIRST pointer row must carry the epoch marker"
    assert len(stamped[1]) == 1, "and no LATER pointer row may add another"
    epoch = stamped[0][0]["payload_mode_epoch"]
    assert epoch["first_pointer_row"] is True and epoch["epoch"] == "pointer"


def test_epoch_marker_is_never_backfilled_onto_body_rows():
    fx = Fixture("noback", mode="body")
    fx.marker("em-NB", 7, 8)
    plan = body_plan(str(fx.zone), 7, 8, "fixture-noback")
    fx.hook({"hook_event_name": "PreToolUse", "tool_input": {"plan": plan}})
    fx.hook({"hook_event_name": "PostToolUse", "tool_input": {"plan": plan},
             "tool_response": {"planFilePath": "/tmp/p.md"}})
    body_rows = list(fx.journal())
    fx.set_mode("pointer")
    fx.marker("em-NB2", 8, 9)
    body2, payload2, _ = _stage_and_capture(fx, 9, "fixture-noback-2")
    fx.hook({"hook_event_name": "PreToolUse", "tool_input": {"plan": payload2}})
    fx.hook({"hook_event_name": "PostToolUse", "tool_input": {"plan": payload2},
             "tool_response": {"planFilePath": "/tmp/p.md"}})
    after = fx.journal()
    assert _strip(after[:len(body_rows)]) == _strip(body_rows), (
        "landing a pointer epoch must not rewrite a single historical body-mode row")


# ---------------------------------------------------------------------------
# 8. ATOMIC HALVES — the two Step 4s and the two look-first gates
# ---------------------------------------------------------------------------

def _blocks(name):
    text = SKILL.read_text(encoding="utf-8")
    pat = re.compile(rf"<!-- payload-mode-switch:{name}:begin.*?"
                     rf"payload-mode-switch:{name}:end -->", re.DOTALL)
    return pat.findall(text)


@pytest.mark.parametrize("half", ["step4", "lookfirst"])
def test_the_two_switch_halves_are_present_exactly_twice(half):
    assert len(_blocks(half)) == 2, (
        f"ATOMIC HALF BROKEN: expected the {half} switch block in BOTH the downbeat and "
        f"syncopate paths, found {len(_blocks(half))}")


@pytest.mark.parametrize("half", ["step4", "lookfirst"])
def test_the_two_switch_halves_are_textually_identical(half):
    a, b = _blocks(half)
    assert a == b, (
        f"ATOMIC HALF DRIFT: the downbeat and syncopate {half} switch blocks differ. "
        f"Both branch on the switch identically, or neither lands.")


def test_body_mode_instructions_are_preserved_verbatim_in_the_skill():
    """In body mode every instruction the skill gives today is unchanged."""
    text = SKILL.read_text(encoding="utf-8")
    for sentence in [
        "The plan content IS the handoff",
        "Locate the active plan file in `~/.claude/plans/`.",
        "It is the source-of-truth for what was carried into this session.",
        "ACTIVE_PLAN=$(ls -t ~/.claude/plans/*.md 2>/dev/null | head -1)",
    ]:
        assert sentence in text, f"body-mode instruction lost: {sentence!r}"


# ---------------------------------------------------------------------------
# 9. F-804-D1-4 PROVEN BY EXECUTION, not by argument
# ---------------------------------------------------------------------------

def _recovery_pick(fx, entry_tic):
    """Which file does find_boundary_plan_file select for this boundary?"""
    code = (
        "import importlib.util,sys,json;"
        f"spec=importlib.util.spec_from_file_location('s',{str(fx.seal)!r});"
        "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
        f"m.bind_zone(__import__('pathlib').Path({str(fx.zone)!r}));"
        f"r=m.find_boundary_plan_file({entry_tic});"
        "print(str(r['path']) if r else 'NONE')"
    )
    out = subprocess.run(["python3", "-c", code], capture_output=True, text=True,
                         env=fx.env, timeout=60)
    return out.stdout.strip()


def test_F804D1_4_a_home_sited_inside_a_globbed_dir_goes_nondeterministic():
    """Siting the durable home inside ~/.claude/plans makes TWO files carry the same
    cgg-handoff entry_tic; the mtime sort then picks racily. THIS is the hazard that
    disqualified Candidate B — measured, not argued."""
    fx = Fixture("sited-inside", mode="pointer")
    body = body_plan(str(fx.zone), 7, 8, "fixture-inside-handoff")
    plans = fx.home / ".claude" / "plans"
    (plans / "the-body.md").write_text(body)              # MIS-SITED durable home
    (plans / "the-pointer.md").write_text(body)           # the approved plan file
    os.utime(plans / "the-body.md", (2_000_000_000, 2_000_000_000))
    picks = {_recovery_pick(fx, 8)}
    os.utime(plans / "the-pointer.md", (2_000_000_100, 2_000_000_100))
    picks.add(_recovery_pick(fx, 8))
    assert len(picks) == 2, (
        "EXPECTED HAZARD ABSENT: two same-entry_tic files inside a globbed dir must make "
        f"the selection mtime-ordered and therefore racy; got {picks}")


def test_F804D1_4_the_chosen_home_does_not_go_nondeterministic():
    """Candidate A sits OUTSIDE both globbed dirs, so no second file with the same
    entry_tic ever enters the selection set."""
    fx = Fixture("sited-outside", mode="pointer")
    body, payload, receipt = _stage_and_capture(fx)
    (fx.home / ".claude" / "plans" / "the-pointer.md").write_text(payload)
    home = fx.zone / receipt["durable_home"]
    assert home.is_file()
    picks = set()
    for mtime in (2_000_000_000, 2_000_000_500):
        os.utime(home, (mtime, mtime))
        picks.add(_recovery_pick(fx, 8))
    assert len(picks) == 1, f"selection must be stable regardless of durable-home mtime; got {picks}"
    assert picks.pop().endswith("the-pointer.md")
