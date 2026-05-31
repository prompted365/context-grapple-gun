"""Regression tests for cadence-ops.py prior-obligation closure.

Anchor (tic 312): /cadence routed one cadence.obligation WAIT into homeskillet's
own inbox each tic and never closed the prior one (28-tic leak). The first fix
closed priors with a raw filesystem move (Path.rename to processed/), which:
  - left inbox-registry.json + idempotency_index + envelope-body lifecycle.state
    stale (Inbox-Triple-Source-Sync violation), and
  - represented closure with no legal terminal state.
A second bad repair then wrote the backlog to DONE across all three sources — a
state that AGREED but was unreachable through the lifecycle contract (DONE is only
reachable WAIT->ACTIVE->DONE; DONE also falsely asserts a consumed obligation).

These tests pin the corrected behavior: closure goes through the canonical
lifecycle API (nack_envelope), producing WAIT->NACK with all four surfaces in
agreement, and a raw filesystem move is proven INSUFFICIENT to silence the stale
detector (registry is the source of truth detect_stale reads).
"""

import importlib.util
import json
import os
import tempfile
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(_HERE, "..", "cgg-runtime", "scripts")


def _load(mod_filename, mod_name):
    path = os.path.join(_SCRIPTS, mod_filename)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cadence_ops = _load("cadence-ops.py", "cadence_ops")
inbox_envelope = _load("inbox-envelope.py", "inbox_envelope")


def _seed_zone(tmp: str) -> str:
    """Minimal zone with a homeskillet inbox containing seeded obligations."""
    zone = os.path.join(tmp, "zone")
    audit = os.path.join(zone, "audit-logs")
    os.makedirs(audit, exist_ok=True)
    # .ticzone so audit_logs_path resolves predictably (no nested audit dir).
    Path(os.path.join(zone, ".ticzone")).write_text(json.dumps({"name": "testzone"}))
    inbox = inbox_envelope.inbox_root(audit, "ent_homeskillet")
    inbox_envelope.ensure_inbox(inbox)
    return zone, inbox


def _seed_obligation(inbox: str, tic: int) -> str:
    env = inbox_envelope.build_envelope(
        sender_id="ent_homeskillet", recipient_id="ent_homeskillet",
        envelope_type="cadence.obligation",
        subject=f"cadence.obligation — tic {tic}",
        body={"tic": tic}, source_tic=tic, priority="urgent",
        category="directive", source_event="cadence.emit",
        producer="cadence-ops.py", idempotency_key=f"cadence_{tic}_test",
    )
    inbox_envelope.write_envelope(env, inbox, dedupe_policy="latest_wins")
    return env["message_id"]


def _obligations_by_tic(inbox: str):
    """Return {source_tic: (state, filename)} from the registry."""
    reg = json.loads(Path(os.path.join(inbox, "indexes", "inbox-registry.json")).read_text())
    out = {}
    for mid, m in reg["messages"].items():
        fn = m.get("filename", "")
        if "obligation" in fn:
            import re
            mt = re.search(r"obligation_t(\d+)_", fn)
            if mt:
                out[int(mt.group(1))] = (m.get("state"), fn)
    return out


def test_prior_obligations_close_as_nack_current_stays_wait():
    """Seed priors + current; run closure; priors -> NACK in archive, current -> WAIT."""
    with tempfile.TemporaryDirectory() as tmp:
        zone, inbox = _seed_zone(tmp)
        for t in (284, 285, 286):
            _seed_obligation(inbox, t)
        _seed_obligation(inbox, 312)  # current/live

        res = cadence_ops._close_prior_cadence_obligations(zone, 312)

        assert res["ran"] is True
        assert res["closed"] == 3, res
        assert res["preserved_current"] == 1, res
        assert res["errors"] == [], res

        by_tic = _obligations_by_tic(inbox)
        for t in (284, 285, 286):
            assert by_tic[t][0] == "NACK", (t, by_tic[t])
            assert by_tic[t][1].startswith("NACK_"), by_tic[t]
        assert by_tic[312][0] == "WAIT"
        assert by_tic[312][1].startswith("WAIT_")


def test_closure_keeps_all_four_surfaces_in_agreement():
    """registry messages[] state, idempotency_index, envelope body, filename agree."""
    with tempfile.TemporaryDirectory() as tmp:
        zone, inbox = _seed_zone(tmp)
        mid = _seed_obligation(inbox, 290)
        _seed_obligation(inbox, 312)

        cadence_ops._close_prior_cadence_obligations(zone, 312)

        reg = json.loads(Path(os.path.join(inbox, "indexes", "inbox-registry.json")).read_text())
        entry = reg["messages"][mid]
        # 1. registry state
        assert entry["state"] == "NACK"
        # 2. filename prefix
        assert entry["filename"].startswith("NACK_")
        # 3. idempotency_index agreement (where indexed)
        for v in reg.get("idempotency_index", {}).values():
            if v.get("message_id") == mid:
                assert v["state"] == "NACK"
        # 4. physical file is in archive with NACK_ prefix; envelope body agrees
        fpath = os.path.join(inbox, "archive", entry["filename"])
        assert os.path.isfile(fpath)
        body = json.loads(Path(fpath).read_text())
        assert body["lifecycle"]["state"] == "NACK"
        # truthful reason persisted in the body itself, not DONE/fulfilled/consumed
        nack_reason = (body["lifecycle"].get("nack_reason") or "").lower()
        assert "superseded" in nack_reason, nack_reason
        assert "fulfilled" not in nack_reason and "consumed" not in nack_reason
        # no stray WAIT remains for the closed obligation
        assert not list(Path(os.path.join(inbox, "inbound")).glob(f"WAIT_*t290_*"))


def test_closed_obligation_does_not_trip_detect_stale():
    """After lifecycle closure, detect_stale must NOT flag the closed obligation."""
    with tempfile.TemporaryDirectory() as tmp:
        zone, inbox = _seed_zone(tmp)
        _seed_obligation(inbox, 280)  # very old -> would be stale if left WAIT
        _seed_obligation(inbox, 312)

        cadence_ops._close_prior_cadence_obligations(zone, 312)

        stale = inbox_envelope.detect_stale(inbox, current_tic=312)
        stale_oblig = [s for s in stale if "obligation" in s.get("subject", "")]
        # t280 closed as NACK (terminal) -> excluded; t312 is current, age 0 -> not stale
        assert stale_oblig == [], stale_oblig


def test_raw_filesystem_move_cannot_silence_detect_stale():
    """Requirement #5: a raw filesystem move cannot silence detect_stale.

    This proves WHY the lifecycle API is mandatory. detect_stale reads the
    REGISTRY. A raw mv updates the filesystem only, leaving the registry's WAIT
    entry untouched — so the stale detector still flags it. The raw-mv "fix" is
    therefore not a fix at all; it produces a registry/filesystem divergence
    (Inbox-Triple-Source-Sync violation) while the stale condition persists.

    Scope boundary (asserted truthfully, not papered over): a raw mv lands the
    file in an off-contract directory (processed/) that the lifecycle resolver
    (find_envelope_file -> STATE_CHANNELS) never searches. The cadence closer
    therefore CANNOT heal this corruption — and importantly it does not pretend
    to: it surfaces the un-closable orphan in result["errors"] with closed==0,
    rather than reporting a false success. Healing arbitrary registry/filesystem
    divergence is out of scope for the cadence closer; eliminating the raw-mv
    codepath (this whole change) is what prevents the corruption arising.
    """
    with tempfile.TemporaryDirectory() as tmp:
        zone, inbox = _seed_zone(tmp)
        _seed_obligation(inbox, 280)

        # Simulate the OLD broken fix: raw filesystem move, registry untouched.
        inbound = os.path.join(inbox, "inbound")
        processed = os.path.join(inbox, "processed")
        os.makedirs(processed, exist_ok=True)
        for f in list(Path(inbound).glob("WAIT_*obligation*")):
            f.rename(Path(processed) / f.name)

        # File is gone from inbound, but the registry still says WAIT, so the
        # stale detector STILL flags it. This is the core requirement-#5 invariant.
        stale = inbox_envelope.detect_stale(inbox, current_tic=312)
        stale_oblig = [s for s in stale if "obligation" in s.get("subject", "")]
        assert stale_oblig, (
            "raw move must NOT silence detect_stale — registry is the source of "
            "truth and still shows WAIT; this is why lifecycle closure is required"
        )

        # The closer, run against this corrupted state, does NOT falsely claim
        # success: the file is in an off-contract dir the resolver cannot reach,
        # so it surfaces the orphan in errors[] with closed==0 (honest failure,
        # not silent papering-over).
        res = cadence_ops._close_prior_cadence_obligations(zone, 312)
        assert res["closed"] == 0, res
        assert len(res["errors"]) == 1, res
        # And detect_stale still flags it — the corruption is genuinely unhealable
        # via the lifecycle API once a raw mv has displaced the file off-contract.
        stale2 = inbox_envelope.detect_stale(inbox, current_tic=312)
        assert [s for s in stale2 if "obligation" in s.get("subject", "")], (
            "an off-contract orphan from a raw mv remains flagged; the closer "
            "must not pretend to have healed it"
        )


def test_closure_is_fail_soft_on_missing_inbox():
    """No inbox -> closure returns a captured result, never raises (must not block cadence)."""
    with tempfile.TemporaryDirectory() as tmp:
        zone = os.path.join(tmp, "empty-zone")
        os.makedirs(os.path.join(zone, "audit-logs"), exist_ok=True)
        Path(os.path.join(zone, ".ticzone")).write_text(json.dumps({"name": "z"}))
        res = cadence_ops._close_prior_cadence_obligations(zone, 312)
        assert res["closed"] == 0
        assert res["ran"] is False
