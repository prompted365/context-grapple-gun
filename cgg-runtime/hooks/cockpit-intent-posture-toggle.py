#!/usr/bin/env python3
"""cockpit-intent-posture-toggle.py — T2b I-A: posture-toggle hook (tic 267).

UserPromptSubmit hook. Scans the user's submitted prompt for posture-toggle
declarations and emits a cockpit.intent envelope.

Detection patterns (per Homeskillet posture contract in ~/.claude/CLAUDE.md):
  - Toggle line:   "[Posture → ENG/DIRECT]" or "[Posture -> ENG/DIRECT]"
  - Banner line:   "POSTURE: ENG/DIRECT (reason: ...)"

intent_class assignment per T2b spec §I-A:
  - New posture is */META  → intent_class: observe
  - New posture is */DIRECT → intent_class: free
  - Compound declarations naming a target are deferred (no compound parser
    in v1; emitted as free + log to stderr that target was dropped)

Fail-soft: hook never blocks UserPromptSubmit. Validation errors and
dedup skips log to stderr but never raise.

Spec: audit-logs/governance/cockpit-intent-t2b-invocation-discipline-spec-tic264.md
PROMOTE-SPEC verdict at /review tic 267 authorizes implementation.

Federation KI compose:
  - Declared operational state must persist to a governed audit surface
  - Identity precedes capability (operator_ref required field)
  - Bounded delegation surfaces default to masking bugs (log visibly on error)
"""

import json
import os
import re
import sys
from pathlib import Path

# Resolve the lib directory robustly across install paths.
# Hook can run from canonical source OR from installed ~/.claude/cgg-runtime/hooks/.
_HOOK_DIR = Path(__file__).parent.resolve()
_CANDIDATE_LIBS = [
    _HOOK_DIR.parent / "scripts" / "lib",                          # canonical: cgg-runtime/scripts/lib
    Path.home() / ".claude" / "cgg-runtime" / "scripts" / "lib",   # installed
]
for _lib in _CANDIDATE_LIBS:
    if (_lib / "cockpit_intent_emit.py").exists():
        sys.path.insert(0, str(_lib))
        break

try:
    from cockpit_intent_emit import emit_intent, resolve_zone_root  # noqa: E402
except ImportError as e:
    # Library not yet synced to install location — fail-soft, log silently.
    sys.stderr.write(f"[cockpit-intent-posture-toggle] cockpit_intent_emit lib unavailable: {e}\n")
    sys.exit(0)

# Posture-toggle patterns. Both arrow forms (→ and ->) tolerated.
TOGGLE_PATTERN = re.compile(
    r"\[\s*Posture\s*(?:→|->)\s*(ENG/META|ENG/DIRECT|OPS/META|OPS/DIRECT)\b[^\]]*\]"
)
BANNER_PATTERN = re.compile(
    r"^POSTURE:\s*(ENG/META|ENG/DIRECT|OPS/META|OPS/DIRECT)\b",
    re.MULTILINE,
)


def detect_posture(text: str) -> str | None:
    """Return the most recently declared posture in text, or None.

    Strategy: scan for toggle pattern first (mid-session declaration is the
    authoritative edge); fall back to session-start banner.
    """
    matches = TOGGLE_PATTERN.findall(text)
    if matches:
        return matches[-1]  # last toggle in the prompt wins
    banner = BANNER_PATTERN.search(text)
    if banner:
        return banner.group(1)
    return None


def intent_class_for_posture(posture: str) -> str:
    """Map posture to intent_class per T2b spec §I-A."""
    return "observe" if posture.endswith("/META") else "free"


def read_statusline_mode(zone_root: str) -> str:
    """Best-effort statusline mode read. Defaults to LITE if unresolvable.

    The mode value is non-load-bearing for posture-toggle emissions but is a
    required envelope field. Falling back to LITE matches envelopes.yaml default.
    """
    # Try the user's ~/.claude/cgg-statusline-mode marker, then fall back.
    candidates = [
        Path.home() / ".claude" / "cgg-statusline-mode",
        Path(zone_root) / ".claude" / "cgg-statusline-mode",
    ]
    for c in candidates:
        if c.exists():
            try:
                v = c.read_text(encoding="utf-8").strip().upper()
                if v in ("LITE", "FULL", "OFF"):
                    return v
            except OSError:
                pass
    return "LITE"


def main() -> int:
    try:
        payload_raw = sys.stdin.read()
        payload = json.loads(payload_raw) if payload_raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        payload = {}

    # UserPromptSubmit shape: {"prompt": "...", "agent_id": "...", ...}
    prompt = ""
    if isinstance(payload, dict):
        prompt = payload.get("prompt") or payload.get("user_prompt") or ""
    if not isinstance(prompt, str) or not prompt.strip():
        return 0  # nothing to scan; fail-soft

    posture = detect_posture(prompt)
    if posture is None:
        return 0  # no toggle detected; nothing to emit

    zone_root = resolve_zone_root()
    intent_class = intent_class_for_posture(posture)
    mode = read_statusline_mode(zone_root)

    result = emit_intent(
        zone_root=zone_root,
        intent_class=intent_class,
        source_object_ref="homeskillet.session",
        source_path="user_prompt:posture_declaration",
        required_gate="G0_auto_audit",
        posture=posture,
        mode=mode,
        operator_ref="ent_breyden",
        actor="cockpit-intent-posture-toggle.hook",
        source_ref="cgg-runtime/hooks/cockpit-intent-posture-toggle.py",
    )

    if result.get("error"):
        # Per T2b §Error Handling + federation KI Bounded-Delegation-Masking:
        # log validation errors visibly; never silently swallow.
        sys.stderr.write(
            f"[cockpit-intent-posture-toggle] emit failed: {result.get('reason')}\n"
        )
    elif result.get("dedup_skipped"):
        sys.stderr.write(
            f"[cockpit-intent-posture-toggle] dedup-skipped: {result.get('reason')}\n"
        )
    elif result.get("emitted"):
        sys.stderr.write(
            f"[cockpit-intent-posture-toggle] emitted {result['intent_id']} "
            f"({intent_class}, posture={posture}, tic={result.get('tic')})\n"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
