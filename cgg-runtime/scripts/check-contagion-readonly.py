#!/usr/bin/env python3
"""check-contagion-readonly.py — structural enforcement of the contagion-match
kernel's read-only / pure-engine invariant.

Clone of check-harmony-readonly.py, scoped to the contagion engine source.

contagion_match_v0/KERNEL_REGISTRATION.md declares ContagionMatch v0 as:
  - read-only on other governance state
  - engine modules are PURE FUNCTIONS (no I/O); all writes live in the outer
    rings (contagion-invoke.sh + contagion-input-builder.py)

This script greps the contagion engine source for forbidden imports and
write-bearing call patterns. It exits non-zero if any are found.

Exit codes:
  0  — no forbidden patterns; engine is structurally read-only / pure
  1  — forbidden patterns detected; findings to stderr
  2  — engine source not found (configuration error)
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path


def resolve_contagion_src() -> Path:
    here = Path(__file__).resolve()
    cur = here.parent
    for _ in range(10):
        candidate = cur / "autonomous_kernel" / "contagion_match_v0" / "runtime"
        if candidate.is_dir():
            return candidate
        if cur.parent == cur:
            break
        cur = cur.parent
    fallback = Path("/Users/breydentaylor/canonical/autonomous_kernel/contagion_match_v0/runtime")
    if fallback.is_dir():
        return fallback
    raise FileNotFoundError("autonomous_kernel/contagion_match_v0/runtime not found")


# Imports/writes that would let the engine reach ACROSS the boundary into
# governance state or perform side effects inside the pure engine module.
FORBIDDEN_IMPORTS = [
    (r"from\s+['\"].*atomic_append['\"]", "atomic_append writes audit logs"),
    (r"from\s+['\"].*queue['\"]", "queue.jsonl is a governance write surface"),
    (r"from\s+['\"].*signals['\"]", "signal emission mutates manifold state"),
    (r"from\s+['\"].*manifest-prune['\"]", "manifest-prune mutates active-manifest"),
    (r"from\s+['\"].*mandate['\"]", "mandate writers mutate Mogul state"),
    (r"from\s+['\"].*conformation['\"]", "conformation writers mutate tic boundary"),
    (r"from\s+['\"].*office-lanes['\"]", "office-lanes.json is the forbidden lane-weight cheat (fence #1)"),
    (r"writeFileSync\s*\(", "direct fs write in engine module is forbidden (output is composed by the invoke wrapper)"),
    (r"appendFileSync\s*\(", "direct fs append in engine module is forbidden"),
    (r"\bfetch\s*\(", "network egress in the read-only matcher is forbidden"),
    (r"\.write\s*\(", "write() method call inside engine module is forbidden"),
]


def scan_file(path: Path) -> list:
    findings = []
    text = path.read_text()
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        # skip comment-only lines (the engine header documents the forbidden
        # surfaces in prose — those mentions are not code)
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue
        for pattern, reason in FORBIDDEN_IMPORTS:
            if re.search(pattern, line):
                findings.append({
                    "file": str(path),
                    "line_number": i,
                    "line": line.rstrip(),
                    "pattern": pattern,
                    "reason": reason,
                })
    return findings


def main() -> int:
    try:
        src_dir = resolve_contagion_src()
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    sources = sorted(src_dir.glob("*.mjs")) + sorted(src_dir.glob("*.ts"))
    if not sources:
        print(f"ERROR: no engine source (.mjs/.ts) in {src_dir}", file=sys.stderr)
        return 2

    all_findings = []
    for src in sources:
        all_findings.extend(scan_file(src))

    if not all_findings:
        if "--json" in sys.argv:
            print(json.dumps({
                "status": "ok",
                "scanned_files": [str(s) for s in sources],
                "findings": [],
                "verdict": "contagion engine is structurally read-only / pure",
            }, indent=2))
        else:
            print(f"OK — scanned {len(sources)} contagion module(s); no forbidden imports/writes found.")
            for s in sources:
                print(f"  ✓ {s.name}")
        return 0

    if "--json" in sys.argv:
        print(json.dumps({
            "status": "violation",
            "scanned_files": [str(s) for s in sources],
            "findings": all_findings,
            "verdict": "contagion engine read-only invariant VIOLATED",
        }, indent=2))
    else:
        print(f"VIOLATION — {len(all_findings)} forbidden pattern(s) in contagion engine source", file=sys.stderr)
        for f in all_findings:
            print(f"  {f['file']}:{f['line_number']}: {f['line']}", file=sys.stderr)
            print(f"    reason: {f['reason']}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
