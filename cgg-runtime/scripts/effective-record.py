#!/usr/bin/env python3
"""CLI for the CGG effective-record correction contract."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.effective_record import (
    build_effective_index,
    genuine_unresolved,
    hydration_view,
    projection_status,
    reconcile,
    review_gate,
)


def _emit(value, output_format: str = "json") -> None:
    if output_format == "hook":
        status = value.get("status")
        changed = len(value.get("effective_records", []))
        blocked_targets = value.get("blocked_targets", [])
        genuine = value.get("unresolved_genuine", len(value.get("unresolved", [])))
        known = value.get("unresolved_known", 0)
        known_note = f"; {known} known-legacy noise row(s) reason-coded nonblocking" if known else ""
        digest = value.get("source_digest", "")[:12]
        if status == "blocked":
            named = ", ".join(
                f"{target['target_surface']}#{target['target_record_id']}"
                for target in blocked_targets[:5]
            )
            overflow = "" if len(blocked_targets) <= 5 else f" (+{len(blocked_targets) - 5} more)"
            target_note = f"; held targets: {named}{overflow}" if named else ""
            print(
                f"[EFFECTIVE RECORD HOLD: {genuine} genuine unresolved"
                f"{target_note}{known_note}; "
                "unsafe base projections suppressed; run effective-record.py scan; "
                f"source {digest}]"
            )
        elif status == "corrected":
            print(
                f"[EFFECTIVE RECORD: {changed} corrected view(s) active"
                f"{known_note}; "
                "raw worldview suppressed; resolve affected ids before hydration; "
                f"source {digest}]"
            )
        else:
            print(
                f"[EFFECTIVE RECORD: safe; {changed} corrected view(s) active"
                f"{known_note}; "
                f"source {digest}]"
            )
        return
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve append-only third-surface record corrections"
    )
    parser.add_argument("--zone-root", default=".", help="governance zone root")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scan", help="scan, validate, and report corrections")

    resolve = sub.add_parser("resolve", help="print one effective record view")
    resolve.add_argument("--record-id", required=True)
    resolve.add_argument("--surface")

    sub.add_parser("review-gate", help="surface unresolved or unratified corrections")

    hydrate = sub.add_parser("hydration-gate", help="emit correction-safe hydration views")
    hydrate.add_argument("--format", choices=("json", "hook"), default="json")

    export = sub.add_parser("export-gate", help="emit correction-safe export views")
    export.add_argument("--format", choices=("json", "hook"), default="json")

    sub.add_parser("check-index", help="fail when the derived projection is missing or stale")

    for name in ("rebuild", "apply-backrefs"):
        write = sub.add_parser(name, help="write the deterministic index, backrefs, and receipt")
        write.add_argument("--authority", required=True)
        write.add_argument(
            "--timestamp",
            default=None,
            help="receipt timestamp; defaults to current UTC (pass explicitly for reproducible tests)",
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.zone_root).resolve()

    if args.command in {"rebuild", "apply-backrefs"}:
        timestamp = args.timestamp or datetime.now(timezone.utc).isoformat()
        result = reconcile(root, authority=args.authority, timestamp=timestamp)
        _emit({key: value for key, value in result.items() if key != "index"})
        return 2 if genuine_unresolved(result["index"]) else 0

    index = build_effective_index(root)

    if args.command == "scan":
        _emit({**index, "projection": projection_status(root, index)})
        return 2 if genuine_unresolved(index) else 0

    if args.command == "resolve":
        matches = [
            record for record in index["records"]
            if record["target_record_id"] == args.record_id
            and (not args.surface or record["target_surface"] == args.surface)
        ]
        if len(matches) != 1:
            _emit({"status": "not_found" if not matches else "ambiguous", "matches": matches})
            return 2
        _emit(matches[0])
        return 2 if matches[0]["unresolved"] else 0

    if args.command == "review-gate":
        result = review_gate(index)
        _emit(result)
        return 2 if result["status"] == "hold" else 0

    if args.command in {"hydration-gate", "export-gate"}:
        result = hydration_view(index)
        result["consumer"] = "hydration" if args.command == "hydration-gate" else "export"
        _emit(result, args.format)
        if result["status"] == "blocked":
            return 2
        if result["status"] == "corrected":
            return 3
        return 0

    if args.command == "check-index":
        status = projection_status(root, index)
        genuine = genuine_unresolved(index)
        result = {
            "status": "pass" if not status["stale"] and not genuine else "hold",
            "projection": status,
            "unresolved": index["unresolved"],
            "unresolved_genuine": len(genuine),
            "unresolved_known": len(index["unresolved"]) - len(genuine),
        }
        _emit(result)
        return 0 if result["status"] == "pass" else 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
