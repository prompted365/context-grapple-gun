#!/usr/bin/env python3
"""boot-injection.py — shared tic-gated boot-injection lane (tic 320).

A lightweight, REUSABLE injection lane that both boot seams read:
  - session-restore.sh   (SessionStart — the interactive orchestrator, ent_homeskillet)
  - subagent-citizen-boot.py (SubagentStart — every recognized citizen)

so a pointer (e.g. the GLOSSARY doctrine-surface navigation frame) can be popped into
boot context for a bounded window of tics, with an auto re-evaluation reminder at a
target tic. This is the ambient-injection complement to the citizen-boot REMINDERS lane
(autonomous_kernel/citizen-boot-reminders-spec.md §3): that lane is per-actor scheduled
obligations; this lane is a broadcast pointer with a tic window.

LOOP-SAFETY (spec §5 — non-negotiable): this renderer is READ-ONLY. It mints NO signals
and writes NO governance state — it only reads a registry and prints text. The 200+ signal
runaway class cannot recur through it. Per-boot context bloat is prevented by the calling
hooks' existing dedup-on-unchanged (same rendered text → injected once per session/entity).

REGISTRY: audit-logs/boot-injections/active.jsonl  (append-only, latest-entry-per-id wins —
terminal-valve discipline). Record schema:
  {
    "injection_id": "<stable id>",          # condition-stable, not timestamp/uuid
    "inject_from_tic": 320,
    "inject_until_tic": 350,                 # inclusive; after this, the injection is dormant
    "reminder_at_tic": 350,                  # at/after this tic, render reminder_text instead
    "audience": "all",                       # "all" | "orchestrator" | "citizens" | ["ent_x", ...]
    "inject_text": "...",                    # the pointer/frame to inject during the window
    "reminder_text": "...",                  # the re-eval reminder at reminder_at_tic
    "status": "active"                       # "active" renders; any non-active state (retired|superseded|closed|...) => never render; missing => active
  }

CLI:
  boot-injection.py render --tic N --audience <orchestrator|citizens|ent_xxx>
      -> prints the concatenated active injection text for that audience at tic N
         (empty output + exit 0 when nothing is due — SILENT-WHEN-EMPTY)
"""

import argparse
import json
import sys
from pathlib import Path


def _zone_root(start: Path, explicit: str = None):
    """Resolve the canonical zone root (where audit-logs/ lives).

    Order: explicit --zone-root (the caller already resolved it) > walk up from
    __file__ (works when running from canonical source) > walk up from cwd (works
    when installed under ~/.claude but fired with cwd=project). The installed copy
    under ~/.claude CANNOT find .ticzone by __file__ walk — callers MUST pass
    --zone-root for the installed path."""
    if explicit:
        ep = Path(explicit)
        if (ep / ".ticzone").is_file():
            return ep
    for p in [start, *start.parents]:
        if (p / ".ticzone").is_file():
            return p
    cwd = Path.cwd()
    for p in [cwd, *cwd.parents]:
        if (p / ".ticzone").is_file():
            return p
    return None


def _load_registry(zone_root: Path):
    """Latest-entry-per-id wins (terminal-valve read over the append-only registry)."""
    reg = zone_root / "audit-logs" / "boot-injections" / "active.jsonl"
    byid = {}
    if not reg.is_file():
        return []
    for line in reg.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        iid = r.get("injection_id")
        if iid:
            byid[iid] = r
    return list(byid.values())


def _audience_match(record_audience, who: str) -> bool:
    """who is 'orchestrator', 'citizens', or a concrete 'ent_*' id."""
    if record_audience == "all":
        return True
    if isinstance(record_audience, list):
        return who in record_audience
    if record_audience == who:
        return True
    # citizens-class request matches a concrete ent_* audience only via the list/all forms above;
    # 'orchestrator' and 'citizens' are the two broad lanes.
    return False


def render(zone_root: Path, tic: int, who: str, max_chars: int = 0) -> str:
    # Collect (priority, from_tic, text) so the join is PRIORITY-ordered, not
    # registry-insertion-ordered. Lower priority int = more important (renders
    # first). `priority` is an OPTIONAL record field (default 50); a missing field
    # keeps today's behavior except for the deterministic (priority, from_tic) sort.
    items = []
    for r in _load_registry(zone_root):
        # Render ACTIVE only. A boot-injected pointer is itself a rehydration (a parent-law
        # pointer carried to a citizen's boot); a non-active record injected as if current
        # re-creates downstream staleness — the recursion-trap of the inheritance carrier
        # (No magical inheritance across rungs: boot pointers must resolve top-current).
        # Skip every non-active terminal state (retired | superseded | closed | <anything>),
        # defaulting a missing status to "active" for backward-compat with seed records.
        if r.get("status", "active") != "active":
            continue
        aud = r.get("audience", "all")
        # 'citizens' lane: a record addressed to "all" or "citizens" reaches every citizen;
        # 'orchestrator' lane: "all" or "orchestrator". Concrete ent_* audiences match exactly.
        reachable = (
            _audience_match(aud, who)
            or (who.startswith("ent_") and aud in ("all", "citizens"))
            or (who == "citizens" and aud in ("all", "citizens"))
            or (who == "orchestrator" and aud in ("all", "orchestrator"))
        )
        if not reachable:
            continue
        rem_at = r.get("reminder_at_tic")
        frm = r.get("inject_from_tic", 0)
        until = r.get("inject_until_tic", 10**9)
        txt = ""
        if rem_at is not None and tic >= rem_at:
            txt = (r.get("reminder_text") or r.get("inject_text") or "").strip()
        elif frm <= tic <= until:
            txt = (r.get("inject_text") or "").strip()
        if not txt:
            continue
        try:
            pri = int(r.get("priority", 50))
        except (TypeError, ValueError):
            pri = 50
        items.append((pri, frm, txt))

    items.sort(key=lambda t: (t[0], t[1]))

    # No budget -> render all (today's behavior, just priority-ordered).
    if not max_chars:
        return " ".join(t[2] for t in items).strip()

    # Budgeted: accumulate at UNIT boundaries; the lowest-priority pointers seal
    # first. The overflow marker points at the full registry so nothing goes dark —
    # same unit-safe SEALED discipline as the worldview truncation (budget-exempt
    # closure framing + unit-safe truncation). Never cut mid-fragment.
    kept, used, sealed_n = [], 0, 0
    for _pri, _frm, txt in items:
        add = (1 if kept else 0) + len(txt)  # +1 for the join space
        if used + add > max_chars and kept:
            sealed_n += 1
            continue
        kept.append(txt)
        used += add
    if sealed_n:
        kept.append(
            f"[BOOT-INJECTION BUDGET: {sealed_n} lower-priority pointer(s) sealed; "
            "read audit-logs/boot-injections/active.jsonl in full]"
        )
    return " ".join(kept).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("--tic", type=int, required=True)
    r.add_argument("--audience", required=True,
                   help="orchestrator | citizens | ent_<id>")
    r.add_argument("--zone-root", default=None,
                   help="explicit canonical zone root (required for the installed copy)")
    r.add_argument("--max-chars", type=int, default=0,
                   help="budget the joined output; 0 = unbounded (default, back-compat). "
                        "Lowest-priority pointers seal first with a SEALED marker.")
    args = ap.parse_args()

    zone_root = _zone_root(Path(__file__).resolve().parent, args.zone_root)
    if zone_root is None:
        return 0  # fail-soft: no zone, no injection
    try:
        text = render(zone_root, args.tic, args.audience, args.max_chars)
    except Exception as e:  # never break a boot
        sys.stderr.write(f"[boot-injection] render error: {e}\n")
        return 0
    if text:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
