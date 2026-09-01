#!/usr/bin/env python3
"""harmony-voice-marker.py — the producer-side MID-WRITE MARKER for the harmony
two-phase disposition packet (/review 756 Q1, cpr_mogul_harmony_invoke_a5db1643a492
PROMOTED as the PRODUCER-LIVENESS face of #presence-observation-fallacy-guard; the
ruled consumer, producer half).

THE DEFECT IT CURES (measured at tic 753): harmony-invoke.sh lands the disposition
packet, then harmony-voice.py AMENDS it additively (fail-soft). A consumer that read
the packet mid-write saw a structurally valid JSON object with NO voice block —
indistinguishable, from the artifact alone, from a packet whose voice step had
FAILED, because the fail-soft path leaves the same legacy-equivalent shape behind
in both cases. The consumer had to probe the process table to know which absence
it was holding.

THE MARKER: the invoker stamps `voice_step` INTO the disposition before launching
the amender and again after it returns —

    {"state": "running", "started_at": ..., "producer": "harmony-voice.py"}
    {"state": "done" | "failed", "started_at": ..., "finished_at": ..., "exit_code": N}

— so the artifact carries its own producer-liveness fact, and the process-table
probe becomes the FALLBACK (for a marker that never advanced past `running`, i.e. a
crashed invoker), never the only signal.

THE READER (`classify`): types an absence from the marker, never from shape:

    voice present                          -> absence_type "none"
    voice absent, marker running           -> "amender_running"     (do NOT type as fault)
    voice absent, marker failed            -> "amender_failed"      (a real, typed failure)
    voice absent, marker done              -> "amender_done_without_voice" (voice step
                                              exited 0 but wrote nothing — a producer
                                              defect, typed as such)
    voice absent, no marker                -> "marker_absent_probe_liveness" (pre-756
                                              packet or a crashed invoker: probe the
                                              process table / exit status / audit row
                                              before typing anything)

Additive only: the marker never touches any other key of the disposition. Stdlib only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path

MARKER_KEY = "voice_step"
PRODUCER = "harmony-voice.py"
STATES = ("running", "done", "failed")


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_atomic(path: Path, value: dict) -> None:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def stamp(disposition: dict, state: str, *, exit_code: int | None = None,
          now: str | None = None) -> dict:
    """Return the disposition with `voice_step` advanced to `state` (pure; additive)."""
    if state not in STATES:
        raise ValueError(f"state must be one of {STATES}, got {state!r}")
    now = now or _now()
    prior = disposition.get(MARKER_KEY) if isinstance(disposition.get(MARKER_KEY), dict) else {}
    marker = {
        "producer": PRODUCER,
        "state": state,
        "started_at": prior.get("started_at") if state != "running" else now,
        "finished_at": now if state in ("done", "failed") else None,
        "exit_code": exit_code if state in ("done", "failed") else None,
        "law": (
            "/review 756 Q1 — a missing amendment block on a two-phase fail-soft artifact is "
            "typed by PRODUCER LIVENESS, never by the artifact's shape; this marker is the "
            "artifact's own liveness fact (ledger.md#two-phase-fail-soft-artifact-absence-is-"
            "typed-by-producer-liveness-not-shape)"),
    }
    if state == "running" and marker["started_at"] is None:
        marker["started_at"] = now
    out = dict(disposition)
    out[MARKER_KEY] = marker
    return out


def classify(disposition: dict) -> dict:
    """Type the voice block's presence/absence from the marker — never from shape."""
    voice_present = isinstance(disposition.get("voice"), dict) and bool(disposition.get("voice"))
    marker = disposition.get(MARKER_KEY) if isinstance(disposition.get(MARKER_KEY), dict) else None
    state = marker.get("state") if marker else None
    if voice_present:
        absence_type = "none"
        guidance = "voice block present; the marker (if any) is history, not a question"
    elif state == "running":
        absence_type = "amender_running"
        guidance = ("do NOT type this absence as a fault: the amender is (or was last known) "
                    "running; re-read after it finishes, or probe liveness if the marker is stale")
    elif state == "failed":
        absence_type = "amender_failed"
        guidance = "a typed failure: the voice step exited non-zero; the disposition stands without voice (fail-soft, legacy-equivalent)"
    elif state == "done":
        absence_type = "amender_done_without_voice"
        guidance = "producer defect: the voice step exited 0 and wrote no voice block — report as a producer finding, not an absence"
    else:
        absence_type = "marker_absent_probe_liveness"
        guidance = ("no marker: a pre-756 packet or a crashed invoker — probe the producer "
                    "(process table / exit status / harmony invocations.jsonl row) BEFORE typing "
                    "this absence; the artifact's shape cannot tell you which absence you hold")
    return {
        "voice_present": voice_present,
        "marker_present": marker is not None,
        "marker_state": state,
        "exit_code": marker.get("exit_code") if marker else None,
        "absence_type": absence_type,
        "guidance": guidance,
        "typed_from": "marker" if marker else ("shape:voice_present" if voice_present else "nothing — probe liveness"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    st = sub.add_parser("stamp", help="advance voice_step in the disposition (additive, atomic)")
    st.add_argument("--disposition", type=Path, required=True)
    st.add_argument("--state", choices=STATES, required=True)
    st.add_argument("--exit-code", type=int, default=None)
    rd = sub.add_parser("classify", help="type the voice block's presence/absence from the marker")
    rd.add_argument("--disposition", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        disposition = _read(args.disposition)
        if args.command == "stamp":
            updated = stamp(disposition, args.state, exit_code=args.exit_code)
            _write_atomic(args.disposition, updated)
            print(json.dumps({"ok": True, MARKER_KEY: updated[MARKER_KEY]}, ensure_ascii=False))
            return 0
        print(json.dumps({"ok": True, **classify(disposition)}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        # Fail-soft by contract: the marker must never take the disposition down with it.
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
