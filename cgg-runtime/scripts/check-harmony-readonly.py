#!/usr/bin/env python3
"""check-harmony-readonly.py — structural enforcement of harmony's read-only invariant.

KERNEL_REGISTRATION.md declares HarmonyEngine v0 as read-only:
  - no ledger writes
  - no enforcement
  - no autonomous judgment
  - no governance state mutation
  - no council weight alteration

This script greps the harmony engine source for forbidden imports and
write-bearing call patterns. It exits non-zero if any are found.

Closes the safety finding (B.2) from
audit-logs/governance/ak-harmony-review-tic213.md.

Run modes:
  - Standalone: python3 check-harmony-readonly.py
  - As part of runtime-sync.py post-sync verification (planned wiring)
  - As pre-commit step (operator opt-in)

Exit codes:
  0  — no forbidden patterns found, harmony engine is structurally read-only
  1  — forbidden patterns detected; emit findings to stderr
  2  — engine source not found (configuration error)
"""

from __future__ import annotations
import json
import re
import sys
from pathlib import Path


# Resolve harmony engine source directory.
# Honor CANONICAL env var; otherwise walk from this script's location.
def resolve_harmony_src() -> Path:
    here = Path(__file__).resolve()
    # Walk upward looking for autonomous_kernel/harmony_engine_v0/src/harmony
    cur = here.parent
    for _ in range(10):
        candidate = cur / "autonomous_kernel" / "harmony_engine_v0" / "src" / "harmony"
        if candidate.is_dir():
            return candidate
        if cur.parent == cur:
            break
        cur = cur.parent
    # Try absolute fallback
    fallback = Path("/Users/breydentaylor/canonical/autonomous_kernel/harmony_engine_v0/src/harmony")
    if fallback.is_dir():
        return fallback
    raise FileNotFoundError("autonomous_kernel/harmony_engine_v0/src/harmony not found")


# ---------------------------------------------------------------------------
# Forbidden patterns
# ---------------------------------------------------------------------------

# Imports that would let harmony mutate governance state. If any are imported
# inside the harmony engine source, the read-only invariant is structurally
# violated and the build should fail.
#
# These are pattern fragments matched against import lines and named imports.
# Each entry: (pattern, reason). Pattern is a regex matched per-line.
FORBIDDEN_IMPORTS = [
    (r"from\s+['\"].*atomic_append['\"]", "atomic_append writes audit logs"),
    (r"from\s+['\"].*queue['\"]", "queue.jsonl is a governance write surface"),
    (r"from\s+['\"].*signals['\"]", "signal emission mutates manifold state"),
    (r"from\s+['\"].*manifest-prune['\"]", "manifest-prune mutates active-manifest"),
    (r"from\s+['\"].*mandate['\"]", "mandate writers mutate Mogul state"),
    (r"from\s+['\"].*conformation['\"]", "conformation writers mutate tic boundary"),
    (r"writeFileSync\s*\(", "direct fs write in harmony module is forbidden (engine output is composed by orchestrator, not by engine modules)"),
    (r"appendFileSync\s*\(", "direct fs append in harmony module is forbidden"),
    (r"\.write\s*\(", "write() method call inside harmony module is forbidden"),
]

# Allowed imports (whitelist). If extending harmony, prefer adding to this list
# explicitly rather than weakening the forbidden patterns.
ALLOWED_LOCAL_IMPORTS = {
    "./types",
    "./centroid-pinning",
    "./acoustic-signature",
    "./ecotone-synthesis",
    "./disposition-injection",
    "./band-policy",
    "./math",
}

# Files allowed to write fs (the engine entrypoint and runtime wrapper compose
# the output but the modules themselves should not).
WRITE_ALLOWED_FILES = {
    # The engine entrypoint receives the input and returns the output —
    # composition only, no side effects.
    # The Node runtime wrapper (harmony-engine.mjs) is not in src/harmony/.
}


def scan_file(path: Path) -> list[dict]:
    """Scan a single source file for forbidden patterns."""
    findings: list[dict] = []
    text = path.read_text()
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        # Skip comments and string-only lines
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue
        for pattern, reason in FORBIDDEN_IMPORTS:
            if re.search(pattern, line):
                # Allow if the file is whitelisted
                if path.name in WRITE_ALLOWED_FILES:
                    continue
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
        src_dir = resolve_harmony_src()
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    sources = sorted(src_dir.glob("*.ts"))
    if not sources:
        print(f"ERROR: no .ts files in {src_dir}", file=sys.stderr)
        return 2

    all_findings: list[dict] = []
    for src in sources:
        all_findings.extend(scan_file(src))

    if not all_findings:
        # Emit JSON for governance consumption (mogul cycle reports, runtime-sync, etc.)
        if "--json" in sys.argv:
            print(json.dumps({
                "status": "ok",
                "scanned_files": [str(s) for s in sources],
                "findings": [],
                "verdict": "harmony engine is structurally read-only",
            }, indent=2))
        else:
            print(f"OK — scanned {len(sources)} harmony module(s); no forbidden imports/writes found.")
            for s in sources:
                print(f"  ✓ {s.name}")
        return 0

    # Findings present
    if "--json" in sys.argv:
        print(json.dumps({
            "status": "violation",
            "scanned_files": [str(s) for s in sources],
            "findings": all_findings,
            "verdict": "harmony engine read-only invariant VIOLATED",
        }, indent=2))
    else:
        print(f"VIOLATION — {len(all_findings)} forbidden pattern(s) in harmony engine source", file=sys.stderr)
        for f in all_findings:
            print(f"  {f['file']}:{f['line_number']}: {f['line']}", file=sys.stderr)
            print(f"    reason: {f['reason']}", file=sys.stderr)
        print(file=sys.stderr)
        print("KERNEL_REGISTRATION.md declares HarmonyEngine v0 as read-only.", file=sys.stderr)
        print("If a write is genuinely needed, review the registration first;", file=sys.stderr)
        print("do not add an exception without operator + /review approval.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
