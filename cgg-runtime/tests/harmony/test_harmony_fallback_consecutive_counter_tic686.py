#!/usr/bin/env python3
"""
Harmony Test — consecutive-fallback counter (bk-harmony-fallback-consecutive-counter, tic 686).

Guards the /review-685 ratified fix-site (cpr_mogul_harmony_invoke_bcc6d27fbdfd,
MODIFY+PROMOTE — ray on ledger#presence-observation-fallacy-guard): success-with-
fallback is an unreported outage, and fail-soft removes precisely the escalation
channel. The voice fingerprint (voice_source / validators_passed / fallback_reason)
has existed since the BR5 voice step; the 677-684 eight-tic fallback streak proved
NO CONSUMER read it per-tic — the streak was bounded only by the t683 stderr
channel plus a hand-run probe ladder. This build is that consumer:

  COUNTER    — every voice receipt carries `consecutive_fallbacks` (streak
               including the current run; 0 on a healthy llm run). "Consecutive"
               means consecutive INVOCATIONS (prior disposition files by tic
               order), never consecutive tic integers — heartbeats can skip tics.
  ESCALATION — at streak >= threshold (default 2, env-overridable via
               HARMONY_FALLBACK_STREAK_THRESHOLD) the receipt carries a
               `fallback_escalation` object AND an ESCALATION line lands on
               stderr — which harmony-invoke.sh captures to stderr-tic-N.log and
               announces as residue: the LOUD path fail-soft had removed.
  HONESTY    — a prior disposition with NO voice object STOPS the count
               (absence is not fallback: observed-absence-does-not-prove-
               breakage); the llm reset case is the t685 in-lane proof shape.
"""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent.parent / "scripts"
VOICE_SCRIPT = SCRIPTS / "harmony-voice.py"

_load_seq = 0


def _make_zone(prior_voices=None):
    """Isolated fixture zone. prior_voices: {tic: voice_source|None}.

    voice_source None writes a disposition WITHOUT a voice object (the
    pre-voice-era / failed-voice-step shape).
    """
    zone = pathlib.Path(tempfile.mkdtemp(prefix="harmony-fallback-fixture-"))
    hdir = zone / "audit-logs" / "harmony"
    hdir.mkdir(parents=True)
    for tic, source in (prior_voices or {}).items():
        body = {"meaningState": "preserved", "disposition": {"stance": "idle"}}
        if source is not None:
            body["voice"] = {"voice_source": source}
            if source == "template_fallback":
                # Post-t692 the streak is family-keyed on fallback_reason; a
                # reason-less prior fallback classifies as no family and never
                # counts. Fixtures must carry an infrastructure-family reason.
                body["voice"]["fallback_reason"] = "llm_timeout_120s"
        (hdir / f"disposition-tic-{tic}.json").write_text(json.dumps(body))
    return zone


def _load_module(zone):
    """Fresh harmony-voice module pinned to the fixture zone."""
    global _load_seq
    _load_seq += 1
    prior = os.environ.get("CGG_REPO_ROOT")
    os.environ["CGG_REPO_ROOT"] = str(zone)
    try:
        spec = importlib.util.spec_from_file_location(
            f"harmony_voice_fixture_{_load_seq}", str(VOICE_SCRIPT))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        if prior is None:
            os.environ.pop("CGG_REPO_ROOT", None)
        else:
            os.environ["CGG_REPO_ROOT"] = prior


_DISPOSITION = {
    "meaningState": "preserved",
    "acousticSignature": {"snr": 0.5},
    "disposition": {
        "stance": "idle",
        "caution": "A caution line for the fixture.",
        "oneWayInjection": "STANCE=idle | fixture",
    },
}

_GOOD_LINE = ("A quiet field tonight; the numbers hold their shape and the "
              "terrain reads steady.")


def _fallback_voice(mod):
    """Voice via propose_voice on the fallback path (runner errors)."""
    def _fails(prompt, model):
        raise RuntimeError("fixture transport failure")
    return mod.propose_voice(dict(_DISPOSITION), None, kill_switch="", runner=_fails)


def _llm_voice(mod):
    return mod.propose_voice(dict(_DISPOSITION), None, kill_switch="",
                             runner=lambda p, m: _GOOD_LINE)


def _apply(mod, voice, tic, threshold_env=None):
    """apply_fallback_counter with captured stderr; returns (voice, stderr)."""
    prior = os.environ.get("HARMONY_FALLBACK_STREAK_THRESHOLD")
    if threshold_env is not None:
        os.environ["HARMONY_FALLBACK_STREAK_THRESHOLD"] = str(threshold_env)
    else:
        os.environ.pop("HARMONY_FALLBACK_STREAK_THRESHOLD", None)
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            out = mod.apply_fallback_counter(voice, tic)
    finally:
        if prior is None:
            os.environ.pop("HARMONY_FALLBACK_STREAK_THRESHOLD", None)
        else:
            os.environ["HARMONY_FALLBACK_STREAK_THRESHOLD"] = prior
    return out, err.getvalue()


# ---------------------------------------------------------------------------
# [1] Fallback-streak arm: two prior fallback runs + current fallback → 3,
#     escalation FIRED, ESCALATION line on stderr (the ratified loud path).
# ---------------------------------------------------------------------------
def test_streak_arm_counts_and_escalates():
    zone = _make_zone({683: "template_fallback", 684: "template_fallback"})
    mod = _load_module(zone)
    voice, err = _apply(mod, _fallback_voice(mod), 685)
    assert voice["consecutive_fallbacks"] == 3
    esc = voice["fallback_escalation"]
    assert esc["fired"] is True
    assert esc["threshold"] == 2
    assert esc["streak"] == 3
    assert "DECORATIVE-BAND-NOTICE" in err and "fallback_reason=llm_error" in err


# ---------------------------------------------------------------------------
# [2] Healthy-reset arm (the t685 in-lane llm proof is the reset case): a
#     prior llm run breaks the streak — current fallback counts 1, no fire.
# ---------------------------------------------------------------------------
def test_healthy_reset_arm():
    zone = _make_zone({683: "template_fallback", 684: "template_fallback",
                       685: "llm"})
    mod = _load_module(zone)
    voice, err = _apply(mod, _fallback_voice(mod), 686)
    assert voice["consecutive_fallbacks"] == 1
    assert voice["fallback_escalation"]["fired"] is False
    assert "DECORATIVE-BAND-NOTICE" not in err


# ---------------------------------------------------------------------------
# [3] Current healthy run zeroes the counter — nothing loud on the happy path
#     (the stderr-residue file must stay removable-empty).
# ---------------------------------------------------------------------------
def test_current_healthy_zeroes():
    zone = _make_zone({684: "template_fallback"})
    mod = _load_module(zone)
    voice, err = _apply(mod, _llm_voice(mod), 685)
    assert voice["voice_source"] == "llm"
    assert voice["consecutive_fallbacks"] == 0
    assert voice["fallback_escalation"]["fired"] is False
    assert err == ""


# ---------------------------------------------------------------------------
# [4] First fallback with no history: streak 1, below default threshold 2 —
#     one degraded run is a fingerprint, not yet an outage.
# ---------------------------------------------------------------------------
def test_first_fallback_no_history():
    zone = _make_zone({})
    mod = _load_module(zone)
    voice, err = _apply(mod, _fallback_voice(mod), 685)
    assert voice["consecutive_fallbacks"] == 1
    assert voice["fallback_escalation"]["fired"] is False
    assert "DECORATIVE-BAND-NOTICE" not in err


# ---------------------------------------------------------------------------
# [5] A voiceless prior disposition STOPS the count — absence is not fallback
#     (observed-absence-does-not-prove-breakage; the pre-voice era must never
#     retroactively count as outage).
# ---------------------------------------------------------------------------
def test_voiceless_prior_stops_count():
    zone = _make_zone({683: "template_fallback", 684: None})
    mod = _load_module(zone)
    voice, _ = _apply(mod, _fallback_voice(mod), 685)
    assert voice["consecutive_fallbacks"] == 1


# ---------------------------------------------------------------------------
# [6] Consecutive means consecutive RUNS, not consecutive tic integers —
#     heartbeats can skip tics; the streak walks prior disposition files in
#     tic order regardless of numeric gaps.
# ---------------------------------------------------------------------------
def test_tic_gaps_still_count_as_consecutive_runs():
    zone = _make_zone({680: "template_fallback", 684: "template_fallback"})
    mod = _load_module(zone)
    voice, _ = _apply(mod, _fallback_voice(mod), 686)
    assert voice["consecutive_fallbacks"] == 3


# ---------------------------------------------------------------------------
# [7] Threshold is env-overridable (the Architect's dial, no code change):
#     raised threshold holds fire; threshold 1 fires on the first fallback.
# ---------------------------------------------------------------------------
def test_threshold_env_override():
    zone = _make_zone({683: "template_fallback", 684: "template_fallback"})
    mod = _load_module(zone)
    voice_hold, err_hold = _apply(mod, _fallback_voice(mod), 685, threshold_env=4)
    assert voice_hold["consecutive_fallbacks"] == 3
    assert voice_hold["fallback_escalation"]["fired"] is False
    assert "DECORATIVE-BAND-NOTICE" not in err_hold

    voice_fire, err_fire = _apply(mod, _fallback_voice(mod), 685, threshold_env=1)
    assert voice_fire["fallback_escalation"]["fired"] is True
    assert "DECORATIVE-BAND-NOTICE" in err_fire


# ---------------------------------------------------------------------------
# [8] End-to-end main() wiring: run the script for real (CLI unfindable —
#     zero network; post-t692 a kill_switch run counts toward nothing, so the
#     loud path needs an infrastructure-family fallback) against a zone with
#     one prior fallback; the written-back disposition must carry the counter
#     and the escalation, and the DECORATIVE-BAND-NOTICE line must land on
#     stderr (harmony-invoke.sh captures that stream to stderr-tic-N.log —
#     the announced residue channel).
# ---------------------------------------------------------------------------
def test_main_wiring_writes_counter_into_disposition():
    zone = _make_zone({684: "template_fallback"})
    hdir = zone / "audit-logs" / "harmony"
    disp_path = hdir / "disposition-tic-685.json"
    disp_path.write_text(json.dumps(_DISPOSITION))
    env = dict(os.environ,
               CGG_REPO_ROOT=str(zone),
               PATH=str(zone))
    proc = subprocess.run(
        [sys.executable, str(VOICE_SCRIPT), "--disposition", str(disp_path)],
        capture_output=True, text=True, env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    written = json.loads(disp_path.read_text())
    voice = written["voice"]
    assert voice["voice_source"] == "template_fallback"
    assert voice["consecutive_fallbacks"] == 2
    assert voice["fallback_escalation"]["fired"] is True
    assert "DECORATIVE-BAND-NOTICE" in proc.stderr


if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    passed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as exc:
            print(f"  [FAIL] {name}: {exc}")
    print("=" * 74)
    print(f"RESULT: {passed}/{len(fns)} — {'OK' if passed == len(fns) else 'FAIL'}")
    sys.exit(0 if passed == len(fns) else 1)
