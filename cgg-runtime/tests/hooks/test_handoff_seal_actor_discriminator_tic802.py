#!/usr/bin/env python3
"""Handoff-seal actor discriminator — the born's test (tic 799 -> /review 802 Q5).

Guards the ruled increment in cgg-runtime/hooks/cadence-handoff-seal.py:
`handle_reconcile_at_start` derives an ACTOR and REFUSES consumption + marker
activation for any non-primary actor, recording the sighting and leaving the
staged seal byte-identical for the primary.

Doctrine home: cgg-ledger/ledger.md#boot-seam-duality-primary-sessionstart-
citizens-subagentstart -- the THIRD BOOT KIND face. A mogul-runner `claude -p`
child is a TOP-LEVEL session: it boots through SessionStart (the PRIMARY's seam,
not SubagentStart) with an EMPTY payload agent_id, so before this cure it
satisfied every predicate the primary would and consumed the primary's seal.
Measured at the entry-tic-800 boundary: consumed_by orchestrator_session_start
at 04:40:53Z, 44 s after the headless child logged Status -> running 04:40:09Z.

Three boot kinds are exercised here, BOTH arms of every documented conditional:
  primary           -- empty agent_id AND no obligation environment  -> consumes
  headless_citizen  -- empty agent_id + CGG_OBLIGATION_MANDATE_ID    -> refuses
  subagent          -- non-empty payload agent_id                    -> refuses
plus the no-seal-pending arm (a non-primary boot with nothing staged writes
NOTHING -- no noise row on every citizen boot) and the fail-soft arm (an
exception inside the refusal branch never blocks a boot; session-restore.sh
keeps `|| true` on the reconcile call).

EVIDENCE CLASS: FIXTURE-green. Every zone here is a tempdir pinned via
--zone-root; no real seal is ever staged, promoted or consumed. Fixture-green is
NOT live-green, and source-green is NOT installed-green on this seam -- the
SessionStart hook execs an INSTALLED copy via
~/.claude/hooks/session-restore-patch.sh (this entry's own sync-parity warning).

DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT rule or cure
which promoter is the seam's ordinary path (the PostToolUse promoter versus the
SessionStart recovery seam), does NOT touch the PostToolUse promoter, and does
NOT retire the recovery_promoted label; a sibling born adjudicates that at its
own round. It also does NOT prove the installed hook carries the cure -- that is
the seat's sync-and-verify motion after the commit.
"""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
HOOKS = HERE.parent.parent / "hooks"

# The hook under test is overridable so the NEGATIVE CONTROL can point at a
# reverted scratch copy OUTSIDE the measured tree without editing this file.
SEAL_HOOK = pathlib.Path(os.environ.get("SEAL_HOOK_UNDER_TEST") or (HOOKS / "cadence-handoff-seal.py"))
SESSION_RESTORE = HOOKS / "session-restore.sh"

EMISSION = "em-802-fixture01"
ENTRY_TIC = 802


# ---------------------------------------------------------------------------
# fixture zone
# ---------------------------------------------------------------------------

def _make_zone(staged=None, current=None, marker_state="interstitial",
               seals_log_as_dir=False):
    """Isolated zone: .ticzone + audit-logs/hooks + audit-logs/tics marker."""
    zone = pathlib.Path(tempfile.mkdtemp(prefix="seal-actor-fixture-"))
    (zone / ".ticzone").write_text("{}")
    hooks_dir = zone / "audit-logs" / "hooks"
    tics_dir = zone / "audit-logs" / "tics"
    hooks_dir.mkdir(parents=True)
    tics_dir.mkdir(parents=True)

    if marker_state is not None:
        (tics_dir / ".interstitial-marker.json").write_text(json.dumps({
            "emission_id": EMISSION,
            "entry_tic": ENTRY_TIC,
            "state": marker_state,
        }, indent=2))

    if staged is not None:
        (hooks_dir / "handoff-seal-staged.json").write_text(json.dumps(staged, indent=2))
    if current is not None:
        (hooks_dir / "handoff-seal-current.json").write_text(json.dumps(current, indent=2))
    if seals_log_as_dir:
        # Forces _atomic_append_jsonl to raise -- the fail-soft arm.
        (hooks_dir / "handoff-seals.jsonl").mkdir()
    return zone


def _seal(stage="staged_pre_approval", consumed_at=None):
    return {
        "type": "handoff_seal",
        "stage": stage,
        "staged_at": "2026-09-19T08:03:14.103380+00:00",
        "boundary_bound": True,
        "activation": {"emission_id": EMISSION, "entry_tic": ENTRY_TIC, "mode": "continuous"},
        "session_id": "fixture-session",
        "agent_id": "",
        "plan_captured": True,
        "plan_hash": "fixturehash00001",
        "plan_chars": 1234,
        "consumed_at": consumed_at,
        "consumed_by": None,
    }


def _reconcile(zone, agent_id="", mandate_id=None, obligation_tic=None):
    """Run the hook exactly as session-restore.sh does, with a controlled env."""
    env = dict(os.environ)
    env.pop("CGG_OBLIGATION_MANDATE_ID", None)
    env.pop("CGG_OBLIGATION_TIC", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if mandate_id is not None:
        env["CGG_OBLIGATION_MANDATE_ID"] = mandate_id
    if obligation_tic is not None:
        env["CGG_OBLIGATION_TIC"] = obligation_tic
    return subprocess.run(
        [sys.executable, str(SEAL_HOOK), "--reconcile-at-start",
         "--zone-root", str(zone), "--agent-id", agent_id],
        capture_output=True, text=True, env=env,
    )


def _journal(zone):
    p = zone / "audit-logs" / "hooks" / "handoff-seals.jsonl"
    if not p.is_file():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def _marker(zone):
    return json.loads((zone / "audit-logs" / "tics" / ".interstitial-marker.json").read_text())


# ---------------------------------------------------------------------------
# 1-3: the born's three assertions — the HEADLESS CHILD on the staged/recovery
#      shape (the real-world shape: the runner's `claude -p` child)
# ---------------------------------------------------------------------------

def test_headless_citizen_refuses_consumption_and_leaves_seal_byte_identical():
    zone = _make_zone(staged=_seal())
    staged_path = zone / "audit-logs" / "hooks" / "handoff-seal-staged.json"
    before = staged_path.read_bytes()

    r = _reconcile(zone, agent_id="", mandate_id="tic-802-20260919T090000")

    assert r.returncode == 0, r.stderr
    assert staged_path.read_bytes() == before, "staged seal must be BYTE-IDENTICAL"
    assert not (zone / "audit-logs" / "hooks" / "handoff-seal-current.json").exists(), \
        "a non-primary actor must not promote the staged seal to current"


def test_headless_citizen_does_not_activate_interstitial_marker():
    zone = _make_zone(staged=_seal())
    r = _reconcile(zone, agent_id="", mandate_id="tic-802-20260919T090000")
    assert r.returncode == 0, r.stderr
    m = _marker(zone)
    assert m["state"] == "interstitial", "the primary's boundary must stay unarmed"
    assert "activated_at" not in m and "activation_verified_at" not in m
    assert not (zone / "audit-logs" / "hooks" / "pause-after-boot-active.json").exists()


def test_headless_refusal_writes_exactly_one_row_with_actor_and_emission_id():
    zone = _make_zone(staged=_seal())
    mandate = "tic-802-20260919T090000"
    r = _reconcile(zone, agent_id="", mandate_id=mandate, obligation_tic="802")
    assert r.returncode == 0, r.stderr

    rows = _journal(zone)
    assert len(rows) == 1, "exactly ONE journal row; got %d" % len(rows)
    row = rows[0]
    assert row["journal_event"] == "consume_refused"
    assert row["reason"] == "non_primary_actor"
    assert row["actor"] == "headless_citizen:" + mandate
    assert row["actor_class"] == "headless_citizen"
    assert row["obligation_mandate_id"] == mandate
    assert row["obligation_tic"] == "802"
    assert row["seal_emission_id"] == EMISSION
    assert row["seal_entry_tic"] == ENTRY_TIC


def test_headless_citizen_refuses_the_current_path_seal_too():
    """Both pending kinds refuse: an unconsumed CURRENT seal, not only STAGED."""
    zone = _make_zone(current=_seal(stage="approved"))
    cur_path = zone / "audit-logs" / "hooks" / "handoff-seal-current.json"
    before = cur_path.read_bytes()

    r = _reconcile(zone, agent_id="", mandate_id="tic-802-20260919T090000")

    assert r.returncode == 0, r.stderr
    assert cur_path.read_bytes() == before, "current seal must be BYTE-IDENTICAL"
    rows = _journal(zone)
    assert len(rows) == 1 and rows[0]["reason"] == "non_primary_actor"
    assert _marker(zone)["state"] == "interstitial"


# ---------------------------------------------------------------------------
# 4: the non-empty agent_id arm — a subagent context reaching this seam
# ---------------------------------------------------------------------------

def test_subagent_agent_id_is_non_primary_and_refuses():
    zone = _make_zone(staged=_seal())
    staged_path = zone / "audit-logs" / "hooks" / "handoff-seal-staged.json"
    before = staged_path.read_bytes()

    r = _reconcile(zone, agent_id="agent_abc123")

    assert r.returncode == 0, r.stderr
    assert staged_path.read_bytes() == before
    rows = _journal(zone)
    assert len(rows) == 1
    assert rows[0]["reason"] == "non_primary_actor"
    assert rows[0]["actor"] == "subagent:agent_abc123"
    assert rows[0]["actor_class"] == "subagent"
    assert _marker(zone)["state"] == "interstitial"


# ---------------------------------------------------------------------------
# 5: the PRIMARY arm — consumption proceeds exactly as today
# ---------------------------------------------------------------------------

def test_primary_consumes_exactly_as_today_and_names_the_primary():
    zone = _make_zone(current=_seal(stage="approved"))
    r = _reconcile(zone, agent_id="")  # no obligation env at all
    assert r.returncode == 0, r.stderr

    cur = json.loads((zone / "audit-logs" / "hooks" / "handoff-seal-current.json").read_text())
    assert cur["consumed_at"] is not None, "the primary must still consume"
    assert cur["consumed_by"] == "orchestrator_session_start"

    rows = _journal(zone)
    assert len(rows) == 1 and rows[0]["journal_event"] == "consumed"
    assert rows[0]["consumed_by"] == "orchestrator_session_start"
    assert rows[0]["emission_id"] == EMISSION

    m = _marker(zone)
    assert m["state"] == "active", "the primary's boundary activates as before"
    assert m["activated_by"] == "orchestrator_session_start+seal_consumption"


# ---------------------------------------------------------------------------
# 6-7: the no-seal-pending arm — NOTHING is written (both actor kinds)
# ---------------------------------------------------------------------------

def test_non_primary_with_nothing_staged_writes_nothing():
    zone = _make_zone()  # no staged, no current
    r = _reconcile(zone, agent_id="", mandate_id="tic-802-20260919T090000")
    assert r.returncode == 0, r.stderr
    assert not (zone / "audit-logs" / "hooks" / "handoff-seals.jsonl").exists(), \
        "a citizen boot with no seal pending must not write a noise row"
    assert not (zone / "audit-logs" / "hooks" / "handoff-seal-current.json").exists()
    assert _marker(zone)["state"] == "interstitial"


def test_primary_with_nothing_staged_writes_nothing():
    zone = _make_zone()
    r = _reconcile(zone, agent_id="")
    assert r.returncode == 0, r.stderr
    assert not (zone / "audit-logs" / "hooks" / "handoff-seals.jsonl").exists()
    assert _marker(zone)["state"] == "interstitial"


# ---------------------------------------------------------------------------
# 8: actor derivation, unit — all three kinds + the both-discriminators case
# ---------------------------------------------------------------------------

def _load_hook_module():
    spec = importlib.util.spec_from_file_location("cadence_handoff_seal_uut", SEAL_HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_derive_actor_three_kinds_and_precedence():
    mod = _load_hook_module()
    saved = {k: os.environ.get(k) for k in ("CGG_OBLIGATION_MANDATE_ID", "CGG_OBLIGATION_TIC")}
    try:
        os.environ.pop("CGG_OBLIGATION_MANDATE_ID", None)
        os.environ.pop("CGG_OBLIGATION_TIC", None)

        primary = mod.derive_actor("")
        assert primary["is_primary"] is True
        assert primary["actor"] == "orchestrator_session_start"
        assert primary["actor_class"] == "primary"

        # whitespace-only agent_id is still the primary shape, not a subagent
        assert mod.derive_actor("   ")["is_primary"] is True

        sub = mod.derive_actor("agent_xyz")
        assert sub["is_primary"] is False and sub["actor"] == "subagent:agent_xyz"

        os.environ["CGG_OBLIGATION_MANDATE_ID"] = "tic-802-X"
        os.environ["CGG_OBLIGATION_TIC"] = "802"
        headless = mod.derive_actor("")
        assert headless["is_primary"] is False
        assert headless["actor"] == "headless_citizen:tic-802-X"
        assert headless["obligation_tic"] == "802"

        # BOTH discriminators present -> still non-primary; agent_id names the
        # immediate actor, the obligation id is retained for forensics.
        both = mod.derive_actor("agent_xyz")
        assert both["is_primary"] is False
        assert both["actor"] == "subagent:agent_xyz"
        assert both["obligation_mandate_id"] == "tic-802-X"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# 9-10: FAIL-SOFT — the call site keeps `|| true`; an exception never blocks boot
# ---------------------------------------------------------------------------

def test_session_restore_call_site_passes_agent_id_and_stays_fail_soft():
    text = SESSION_RESTORE.read_text()
    assert '--reconcile-at-start' in text
    assert '--agent-id "$AGENT_ID"' in text, "the payload agent_id must still reach the seam"
    # Anchor on the INVOCATION, never on the bare token -- the token also
    # appears in the section comment above the call site.
    call = 'python3 "$SEAL_HOOK_SCRIPT" --reconcile-at-start'
    assert call in text, "the reconcile invocation must still be the call site"
    window = text[text.index(call):text.index(call) + 300]
    assert '--agent-id "$AGENT_ID"' in window, "agent_id must be passed AT the call site"
    assert "|| true" in window, "the reconcile call must keep its `|| true` fail-soft guard"


def test_exception_in_refusal_branch_never_blocks_boot(tmp_path):
    """A raising reconcile must not stop the rest of a SessionStart hook."""
    zone = _make_zone(staged=_seal(), seals_log_as_dir=True)

    r = _reconcile(zone, agent_id="", mandate_id="tic-802-20260919T090000")
    assert r.returncode != 0, "the fixture must actually force the failure it claims to test"

    # Replay the session-restore.sh call-site shape: `... || true`, then more output.
    harness = tmp_path / "callsite.sh"
    harness.write_text(
        '#!/usr/bin/env bash\n'
        'SEAL_RECONCILE_MSG=$(python3 "$1" --reconcile-at-start '
        '--zone-root "$2" --agent-id "" 2>/dev/null || true)\n'
        'echo "SEAL_MSG=[$SEAL_RECONCILE_MSG]"\n'
        'echo "DOWNSTREAM_RENDERED=yes"\n'
        'exit 0\n'
    )
    env = dict(os.environ)
    env["CGG_OBLIGATION_MANDATE_ID"] = "tic-802-20260919T090000"
    out = subprocess.run(["bash", str(harness), str(SEAL_HOOK), str(zone)],
                         capture_output=True, text=True, env=env)
    assert out.returncode == 0, "the boot path must survive a raising reconcile"
    assert "DOWNSTREAM_RENDERED=yes" in out.stdout, \
        "the rest of the session-restore output must still render"
