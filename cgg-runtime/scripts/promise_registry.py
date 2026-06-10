#!/usr/bin/env python3
"""
Promise Registry — derive-from-boot (Binder node B3, Architect fork tic 398: Option 1).

Architect ruling (B3): "Promise truth originates in boot evidence, not in a parallel
authored registry. Derive the promise registry from boot receipts as the canonical
source of truth; do NOT fork a new promise-registry surface unless boot-derived
reconstruction fails under review."

Centroid (pinned by the 6-facet non-collapse perimeter — labels subordinated, IS-NOT leads
because the failure mode is forking a parallel authored surface):

  IS         — a DERIVE-FROM-BOOT reader: reconstructs promise truth (per-entity
               accepted_constraints / abstentions / understood_scope, latest-affirmed)
               by projecting the append-only boot-receipts ledger; surfaces missed-receipt
               findings as ADVISORY candidates for /review + the per-flow emit rules (B11).
  IS-NOT     — (leads) NOT a new authored promise-registry surface (boot receipts ARE
               canonical per the B3 ruling — a parallel surface is forked ONLY if
               reconstruction provably fails under review); NOT a promise ENFORCER (it
               reconstructs and surfaces; /review judges, per-flow emit rules act); NOT a
               missed-receipt FABRICATOR (it invents no expected-boot schedule — an
               event-driven citizen's boot gaps are EXPECTED, not missed; only a
               continuous-boot entity's intra-span gaps are candidate misses); NOT a
               conformance JUDGE (conformance_diff is the entity's self-report; this reads
               it, it does not adjudicate whether a promise was KEPT); NOT a mutable
               state-store (read-only projection — never writes a derived cache as a second
               source of truth that can drift from the receipts).
  HOLDS      — boot-receipt-as-canonical (cheap, evidence-grounded, single source) <->
               boot receipts are sparse + event-driven (a gap is ambiguous). Held by:
               reconstruct only from what was emitted, and CLASS every miss by the entity's
               own boot cadence (continuous vs event-driven), never by an invented schedule.
  COMPLEMENT — inert without: (1) the boot-receipt emitter actually firing with non-empty
               accepted_constraints (citizen-boot / cadence / mandate-runner); (2) the
               per-flow emit rules (B11) that consume promise truth into trust events;
               (3) /review to judge the missed-receipt findings.
  COUNTER    — what kills it: forking a parallel authored registry (the B3 anti-pattern —
               two sources of promise truth that drift); flagging event-driven citizen gaps
               as misses (false positives that train the reader to cry wolf); treating
               reconstruction as enforcement; caching the derived truth as a mutable store.
  TELOS      — promise truth == the projection of `accepted_constraints` across boot
               receipts, latest-affirmed per entity; a missed receipt is STRUCTURAL (a
               receipt with empty accepted_constraints) or CONTINUITY (an intra-span tic gap
               for a continuous-boot entity), advisory-only; the registry never AUTHORS
               promise truth, it DERIVES it.

Root resolution applies the tic-399-promoted KI (no-magical-inheritance / instrument-only-
what-emits): resolve the federation audit-logs by the DECLARED rung chain to .federation-root
via zone_root.resolve_rung_position — never by __file__ / nearest-audit-logs proximity.

Usage:
  promise_registry.py reconstruct [--entity ent_x] [--json]   # per-entity promise truth
  promise_registry.py missed [--entity ent_x] [--json]        # advisory missed-receipt findings
  promise_registry.py report                                  # both, human-readable
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Continuous-boot discriminator: an entity whose boot density across its own active span
# is >= this is treated as continuous (orchestrator / mandate-runner class); below it the
# entity is event-driven (citizen dispatch) and its intra-span gaps are EXPECTED, not missed.
CONTINUOUS_BOOT_DENSITY = 0.5


def _audit_root():
    """Resolve federation audit-logs by the DECLARED rung chain to .federation-root —
    never by bare audit-logs/ proximity (no-magical-inheritance KI, ledger /review 391/399).
    Order: CGG_AUDIT_ROOT env > zone_root.resolve_rung_position (from CLAUDE_PROJECT_DIR/cwd)
    > None (refuse; caller surfaces hierarchy_blocked)."""
    env = os.environ.get("CGG_AUDIT_ROOT")
    if env and (Path(env) / "audit-logs" / "boot-injections").is_dir():
        return Path(env) / "audit-logs"
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from zone_root import resolve_rung_position, load_ticzone, audit_logs_path
        rp = resolve_rung_position()
        fed = (rp.get("topology") or {}).get("federation")
        if fed and fed.get("path"):
            root = fed["path"]
            return Path(audit_logs_path(root, load_ticzone(root)))
    except Exception:
        pass
    return None


AUDIT = _audit_root()
HIERARCHY_BLOCKED = AUDIT is None
RECEIPTS = None if HIERARCHY_BLOCKED else AUDIT / "boot-injections" / "boot-receipts.jsonl"


def _require_root():
    if HIERARCHY_BLOCKED:
        sys.stderr.write(
            "[promise_registry] hierarchy_blocked: no .federation-root reachable from "
            "CLAUDE_PROJECT_DIR/cwd. Refusing to read a stray audit-logs/ (no magical "
            "inheritance across rungs). Run from within the federation or set CGG_AUDIT_ROOT.\n")
        sys.exit(2)


def load_receipts():
    """All boot receipts (append-only). Boot receipts are immutable per receipt_id, so no
    latest-per-id collapse — each receipt is a distinct boot event."""
    out = []
    if RECEIPTS and RECEIPTS.exists():
        for line in RECEIPTS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _by_entity(receipts):
    ents = {}
    for r in receipts:
        e = r.get("entity_id")
        if e:
            ents.setdefault(e, []).append(r)
    for e in ents:
        ents[e].sort(key=lambda r: (r.get("tic") is None, r.get("tic") or 0))
    return ents


def _tics(rs):
    return sorted({r.get("tic") for r in rs if r.get("tic") is not None})


def reconstruct(entity=None):
    """Promise truth = latest-affirmed accepted_constraints per entity, derived from boot
    receipts. NOT authored — projected."""
    ents = _by_entity(load_receipts())
    out = {}
    for e, rs in ents.items():
        if entity and e != entity:
            continue
        latest = rs[-1]
        tics = _tics(rs)
        out[e] = {
            "entity_id": e,
            "accepted_constraints": latest.get("accepted_constraints") or [],
            "abstentions": latest.get("abstentions") or [],
            "understood_scope": latest.get("understood_scope") or "",
            "last_affirmed_tic": latest.get("tic"),
            "last_receipt_id": latest.get("receipt_id"),
            "receipt_route": latest.get("receipt_route"),
            "receipt_count": len(rs),
            "span": [min(tics), max(tics)] if tics else [None, None],
            "source": "derived_from_boot_receipts",  # never authored
        }
    return out


def _cadence_class(rs):
    """continuous vs event_driven, by the entity's own boot density across its span."""
    tics = _tics(rs)
    if len(tics) < 2:
        return "event_driven", 0.0
    span = tics[-1] - tics[0] + 1
    density = len(set(tics)) / span if span > 0 else 0.0
    return ("continuous" if density >= CONTINUOUS_BOOT_DENSITY else "event_driven"), round(density, 3)


def missed(entity=None):
    """Advisory missed-receipt findings. Two honest classes, NO invented schedule:
      STRUCTURAL — a receipt with empty accepted_constraints (booted, did not promise).
      CONTINUITY — an intra-span tic gap for a CONTINUOUS-boot entity only (event-driven
                   citizens' gaps are expected, never flagged)."""
    ents = _by_entity(load_receipts())
    findings = []
    for e, rs in ents.items():
        if entity and e != entity:
            continue
        cls, density = _cadence_class(rs)
        # STRUCTURAL — applies to every cadence class
        for r in rs:
            if not (r.get("accepted_constraints") or []):
                findings.append({
                    "entity_id": e, "kind": "STRUCTURAL", "tic": r.get("tic"),
                    "receipt_id": r.get("receipt_id"),
                    "detail": "booted with empty accepted_constraints (no promise affirmed)",
                    "cadence_class": cls, "boot_density": density, "advisory": True,
                })
        # CONTINUITY — continuous-boot entities only
        if cls == "continuous":
            tics = _tics(rs)
            present = set(tics)
            gaps = [t for t in range(tics[0], tics[-1] + 1) if t not in present]
            if gaps:
                findings.append({
                    "entity_id": e, "kind": "CONTINUITY", "cadence_class": cls,
                    "boot_density": density, "span": [tics[0], tics[-1]],
                    "gap_count": len(gaps),
                    "gap_tics_sample": gaps[:20],
                    "detail": ("continuous-boot entity missing %d intra-span tic(s) — "
                               "candidate missed promise affirmations" % len(gaps)),
                    "advisory": True,
                })
    return findings


def report():
    pr = reconstruct()
    ms = missed()
    lines = ["# Promise Registry — derived from boot receipts (B3, derive-from-boot)\n"]
    lines.append("## Promise truth (latest-affirmed per entity)")
    for e, p in sorted(pr.items()):
        lines.append("  %-22s constraints=%d abstentions=%d last_affirmed_tic=%s route=%s span=%s n=%d"
                     % (e, len(p["accepted_constraints"]), len(p["abstentions"]),
                        p["last_affirmed_tic"], p["receipt_route"], p["span"], p["receipt_count"]))
    lines.append("\n## Missed-receipt findings (advisory — for /review + per-flow emit rules)")
    if not ms:
        lines.append("  (none)")
    for f in ms:
        if f["kind"] == "STRUCTURAL":
            lines.append("  STRUCTURAL %-20s tic=%s — %s" % (f["entity_id"], f["tic"], f["detail"]))
        else:
            lines.append("  CONTINUITY %-20s span=%s density=%s — %s (gaps: %s%s)"
                         % (f["entity_id"], f["span"], f["boot_density"], f["detail"],
                            f["gap_tics_sample"], " …" if f["gap_count"] > len(f["gap_tics_sample"]) else ""))
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Promise Registry — derive-from-boot (B3)")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("reconstruct"); pr.add_argument("--entity"); pr.add_argument("--json", action="store_true")
    pm = sub.add_parser("missed"); pm.add_argument("--entity"); pm.add_argument("--json", action="store_true")
    sub.add_parser("report")
    args = p.parse_args()
    _require_root()
    if args.cmd == "reconstruct":
        out = reconstruct(args.entity)
        print(json.dumps(out, indent=2) if args.json else report().split("## Missed")[0])
    elif args.cmd == "missed":
        out = missed(args.entity)
        print(json.dumps(out, indent=2) if args.json else "\n".join(
            "%s %s %s" % (f["kind"], f["entity_id"], f.get("tic") or f.get("span")) for f in out) or "(none)")
    elif args.cmd == "report":
        print(report())


if __name__ == "__main__":
    main()
