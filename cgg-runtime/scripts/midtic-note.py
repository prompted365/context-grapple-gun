#!/usr/bin/env python3
"""midtic-note.py — durable mid-tic pause/resume receipt (bk-sovereign-midtic-pause-receipt, tic 683).

THE GAP: pause_after_boot covers only the BOUNDARY seam. A hold taken MID-tic
(the Architect steps away, a session dies, a handoff is not yet owed) leaves the
WHERE-state — what is done, what is owed, where to resume — only in the harness
transcript, and resumption then leans on Claude Code transcript fidelity, which
is not a governance surface.

THE SURFACE: an append-only JSONL sibling of the interstitial marker
(audit-logs/tics/interstitial-notes.jsonl). This tool NEVER mutates
.interstitial-marker.json — that file's lifecycle fields are owned by the
cadence/seal machinery (cadence-ops emit, seal/interstitial hooks activate);
this is a sibling residue lane, not a second writer on their surface.

THE READER (can-it-eat): session-restore.sh injects the latest note for the
ACTIVE emission at boot ([MID-TIC RESUMPTION NOTE]) — the note is consumed at
exactly the moment resumption happens, so the lane is born with a live consumer,
never written-never-read.

Usage:
  midtic-note.py note --done "…" --owed "…" [--done …] [--owed …]
                      [--resume-hint "…"] [--holder ent_x] [--note "…"]
  midtic-note.py latest [--emission-id em-…] [--format json|line]
  midtic-note.py --selftest
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root  # noqa: E402


def _zone(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    try:
        return Path(resolve_zone_root())
    except Exception:
        return Path("/Users/breydentaylor/canonical")


def _tics_dir(zone: Path) -> Path:
    return zone / "audit-logs" / "tics"


def _marker(zone: Path) -> dict:
    """The interstitial marker, read-only + fail-soft (its owners keep the pen)."""
    try:
        return json.loads((_tics_dir(zone) / ".interstitial-marker.json").read_text(
            encoding="utf-8"))
    except Exception:
        return {}


def notes_path(zone: Path) -> Path:
    return _tics_dir(zone) / "interstitial-notes.jsonl"


def write_note(zone: Path, done: list[str], owed: list[str], resume_hints: list[str],
               holder: str, note: str | None) -> dict:
    marker = _marker(zone)
    row = {
        "type": "midtic_resumption_note",
        "noted_at": datetime.now(timezone.utc).isoformat(),
        "tic": marker.get("entry_tic"),
        "emission_id": marker.get("emission_id"),
        "marker_state": marker.get("state"),
        "holder": holder,
        "done": done,
        "owed": owed,
        "resume_hints": resume_hints,
        "note": note,
    }
    p = notes_path(zone)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f, fcntl.LOCK_UN)
    return row


def latest_note(zone: Path, emission_id: str | None = None) -> dict | None:
    """Latest note, optionally scoped to one emission (the resumption reader's
    question: 'is there a hold-note for THE boundary I just woke into?')."""
    p = notes_path(zone)
    if not p.is_file():
        return None
    last = None
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if emission_id and row.get("emission_id") != emission_id:
                continue
            last = row
    except OSError:
        return None
    return last


def render_line(row: dict) -> str:
    done = "; ".join(row.get("done") or []) or "—"
    owed = "; ".join(row.get("owed") or []) or "—"
    hints = "; ".join(row.get("resume_hints") or [])
    bits = [f"[MID-TIC RESUMPTION NOTE · tic {row.get('tic','?')} · "
            f"{row.get('noted_at','?')} · holder {row.get('holder','?')}] "
            f"DONE: {done} | OWED: {owed}"]
    if hints:
        bits.append(f"| RESUME: {hints}")
    if row.get("note"):
        bits.append(f"| {row['note']}")
    return " ".join(bits)


def _selftest() -> int:
    import tempfile
    checks = []
    with tempfile.TemporaryDirectory() as td:
        zone = Path(td)
        _tics_dir(zone).mkdir(parents=True)
        # arm 1: marker absent → honest nulls, note still lands
        r1 = write_note(zone, ["a"], ["b"], [], "ent_test", None)
        checks.append(("marker_absent_honest_nulls",
                       r1["tic"] is None and r1["emission_id"] is None))
        # arm 2: marker present → stamped
        (_tics_dir(zone) / ".interstitial-marker.json").write_text(json.dumps(
            {"state": "active", "emission_id": "em-9-x", "entry_tic": 9}), encoding="utf-8")
        r2 = write_note(zone, ["did x"], ["owe y"], ["start at z"], "ent_test", "n")
        checks.append(("marker_present_stamped",
                       r2["tic"] == 9 and r2["emission_id"] == "em-9-x"))
        # arm 3: append-only accretion + latest wins
        got = latest_note(zone)
        checks.append(("latest_wins", got is not None and got["done"] == ["did x"]))
        # arm 4: emission scoping — both arms (match + no-match)
        checks.append(("emission_scope_match",
                       (latest_note(zone, "em-9-x") or {}).get("emission_id") == "em-9-x"))
        checks.append(("emission_scope_no_match", latest_note(zone, "em-0-none") is None))
        # arm 5: renderer carries done/owed/resume
        line = render_line(r2)
        checks.append(("render_carries_where_state",
                       "did x" in line and "owe y" in line and "start at z" in line))
        # arm 6: two rows on disk (append-only, nothing rewritten)
        n_rows = len([l for l in notes_path(zone).read_text().splitlines() if l.strip()])
        checks.append(("append_only_two_rows", n_rows == 2))
        # arm 7: empty file → None (not a crash)
        notes_path(zone).write_text("", encoding="utf-8")
        checks.append(("empty_file_none", latest_note(zone) is None))
    ok = all(p for _, p in checks)
    for name, p in checks:
        print(f"  [{'PASS' if p else 'FAIL'}] {name}")
    print(f"selftest: {sum(1 for _, p in checks if p)}/{len(checks)} " + ("GREEN" if ok else "RED"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--zone-root", default=None)
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    n = sub.add_parser("note", help="record a mid-tic hold's WHERE-state durably")
    n.add_argument("--done", action="append", default=[], help="a completed unit (repeatable)")
    n.add_argument("--owed", action="append", default=[], help="an owed unit (repeatable)")
    n.add_argument("--resume-hint", action="append", default=[],
                   help="where/how to resume (repeatable)")
    n.add_argument("--holder", default="ent_homeskillet")
    n.add_argument("--note", default=None, help="free-text context")
    l = sub.add_parser("latest", help="print the latest note (resumption reader)")
    l.add_argument("--emission-id", default=None)
    l.add_argument("--format", choices=("json", "line"), default="json")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()
    zone = _zone(args.zone_root)
    if args.cmd == "note":
        if not (args.done or args.owed or args.note):
            print("ERR midtic-note: an empty note records nothing — pass --done/--owed/--note",
                  file=sys.stderr)
            return 1
        row = write_note(zone, args.done, args.owed, args.resume_hint, args.holder, args.note)
        print(json.dumps(row, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "latest":
        row = latest_note(zone, args.emission_id)
        if row is None:
            print("no note" if args.format == "line" else "null")
            return 3
        print(render_line(row) if args.format == "line" else
              json.dumps(row, indent=2, ensure_ascii=False))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
