"""Lifecycle-contract tests for inbox-envelope.py.

Regression anchor (tic 312): the cadence self-obligation leak remediation first
moved 28 never-claimed WAIT obligations to DONE across registry + filesystem +
idempotency_index. All three AGREED — but on a state unreachable through the
lifecycle contract. DONE is only reachable WAIT -> ACTIVE -> DONE; a never-claimed
WAIT may close legally only as ACTIVE, DEFER, or NACK. DONE on an unclaimed item
also falsely asserts a consumed/fulfilled obligation.

Invariant under test:
    State agreement is not truth unless the agreed state is reachable through the
    lifecycle contract. A never-claimed WAIT obligation may not be marked DONE;
    it must transition to ACTIVE before DONE, or close as NACK/DEFER per the
    lifecycle semantics.
"""

import importlib.util
import os
import tempfile
from pathlib import Path

# Load inbox-envelope.py (hyphenated filename -> import via spec).
_HERE = os.path.dirname(os.path.abspath(__file__))
_MODPATH = os.path.join(_HERE, "..", "cgg-runtime", "scripts", "inbox-envelope.py")
_spec = importlib.util.spec_from_file_location("inbox_envelope", _MODPATH)
inbox_envelope = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(inbox_envelope)


def _mk_inbox(tmp: str) -> str:
    inbox = inbox_envelope.inbox_root(tmp, "ent_test")
    inbox_envelope.ensure_inbox(inbox)
    return inbox


def _write_wait_obligation(inbox: str, tic: int):
    env = inbox_envelope.build_envelope(
        sender_id="ent_test",
        recipient_id="ent_test",
        envelope_type="cadence.obligation",
        subject=f"cadence.obligation — tic {tic}",
        body={"tic": tic},
        source_tic=tic,
        priority="urgent",
        category="directive",
        source_event="cadence.emit",
        producer="cadence-ops.py",
        idempotency_key=f"cadence_{tic}_test",
    )
    res = inbox_envelope.write_envelope(env, inbox, dedupe_policy="latest_wins")
    assert res.get("status") in ("ok", "written", None) or "error" not in res, res
    return env["message_id"]


def test_wait_to_done_is_not_a_legal_transition_contract():
    """Contract level: DONE is not reachable directly from WAIT."""
    assert "DONE" not in inbox_envelope.STATE_TRANSITIONS["WAIT"]
    assert inbox_envelope.STATE_TRANSITIONS["WAIT"] == {"ACTIVE", "DEFER", "NACK"}
    # DONE is only reachable from ACTIVE.
    assert "DONE" in inbox_envelope.STATE_TRANSITIONS["ACTIVE"]


def test_never_claimed_wait_rejects_complete_to_done():
    """Runtime: complete_envelope (WAIT -> DONE) on an unclaimed item must error."""
    with tempfile.TemporaryDirectory() as tmp:
        inbox = _mk_inbox(tmp)
        mid = _write_wait_obligation(inbox, 10)
        res = inbox_envelope.complete_envelope(inbox, mid, "ent_test", 11)
        assert res["status"] == "error", (
            "WAIT -> DONE must be rejected for a never-claimed obligation; "
            f"got {res}"
        )


def test_never_claimed_wait_closes_legally_as_nack():
    """Runtime: WAIT -> NACK (superseded) is the correct terminal for an
    unclaimed, expired continuity obligation, and it propagates to the registry."""
    with tempfile.TemporaryDirectory() as tmp:
        inbox = _mk_inbox(tmp)
        mid = _write_wait_obligation(inbox, 10)
        res = inbox_envelope.nack_envelope(
            inbox, mid, "ent_test", 11, reason="superseded; never claimed"
        )
        assert res["status"] == "ok"
        assert res["to"] == "NACK"
        # Registry must agree (triple-source: filename + state + idempotency).
        reg_path = os.path.join(inbox, "indexes", "inbox-registry.json")
        import json
        reg = json.loads(Path(reg_path).read_text())
        entry = reg["messages"][mid]
        assert entry["state"] == "NACK"
        assert entry["filename"].startswith("NACK_")
        # And the file must physically be the NACK file, not a stray WAIT.
        archive = os.path.join(inbox, "archive", entry["filename"])
        assert os.path.isfile(archive)
        stray = list(Path(os.path.join(inbox, "inbound")).glob("WAIT_*"))
        assert stray == [], f"WAIT file must not remain after NACK: {stray}"


def test_legal_full_lifecycle_wait_active_done():
    """The legal path WAIT -> ACTIVE -> DONE still works (no over-restriction)."""
    with tempfile.TemporaryDirectory() as tmp:
        inbox = _mk_inbox(tmp)
        mid = _write_wait_obligation(inbox, 10)
        c = inbox_envelope.claim_envelope(inbox, mid, "ent_test", 11)
        assert c["status"] == "ok" and c["to"] == "ACTIVE"
        d = inbox_envelope.complete_envelope(inbox, mid, "ent_test", 12)
        assert d["status"] == "ok" and d["to"] == "DONE"
