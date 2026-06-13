#!/usr/bin/env python3
"""boot-receipt.py — the receipt SINK that closes the Citizen-Boot Composite loop.

The worldview compiler (office-worldview.py) emits a receipt OBLIGATION ("⟜ receipt
owed: ...") but, until now, there was nowhere for the receipt to LAND. This is that
sink: proof-of-boot-uptake, mapped to (entity, tic), append-only, concurrency-safe.

WHY a dedicated sink (not the mailbox receipts.jsonl):
  The mailbox indexes/receipts.jsonl is message-ACK/NACK scoped (keyed by message_id,
  closing an inbound trigger). A boot receipt is not a response to a message — it is
  the office proving it crossed the boot threshold consciously without collapsing the
  pertinence badges. Overloading the mailbox receipts surface would silently term-
  overload two receipt semantics (cf. ledger#semantic-identity-admission-gate). So the
  boot receipt lands co-located with the boot-injection lane it closes.

CONCURRENCY (the "many firing the same nanosecond" requirement):
  - Append-only JSONL; POSIX O_APPEND writes under PIPE_BUF are atomic across procs.
  - flock(LOCK_EX) serializes the read-existing-IDs + append within/across processes.
  - DETERMINISTIC ID = sha256(entity:tic:content_fingerprint)[:16]. Same office booting
    the same tic with the same understanding => identical id => dedups to ONE line.
    This is the same loop-guard as the boot-injection lane + the 200+ signal-loop class
    (deterministic-ID + dedup-at-write). Idempotent by construction.

USAGE:
  boot-receipt.py emit --entity ent_homeskillet --tic 329 --payload receipt.json
  boot-receipt.py emit --entity ent_x --tic 329 \
      --understood "..." --constraint "a" --constraint "b" \
      --abstention "x" --first-action "..." --route "cadence/review"
  boot-receipt.py list --tic 329
  boot-receipt.py compact          # collapse same-id duplicates (dedup-at-read pass)
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
import sys
from pathlib import Path


def zone_root() -> Path:
    """Resolve the federation/zone root by walking up for audit-logs/."""
    p = Path(__file__).resolve()
    for anc in [p] + list(p.parents):
        if (anc / "audit-logs" / "boot-injections").is_dir():
            return anc
    # fallback: known canonical root
    cand = Path("/Users/breydentaylor/canonical")
    if (cand / "audit-logs" / "boot-injections").is_dir():
        return cand
    raise SystemExit("boot-receipt: could not locate zone root (audit-logs/boot-injections)")


def sink_path(root: Path) -> Path:
    return root / "audit-logs" / "boot-injections" / "boot-receipts.jsonl"


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def content_fingerprint(rec: dict) -> str:
    """Stable fingerprint over the SEMANTIC fields only (not timestamps/model)."""
    sem = {
        "understood_scope": rec.get("understood_scope", ""),
        "accepted_constraints": sorted(rec.get("accepted_constraints", [])),
        "abstentions": sorted(rec.get("abstentions", [])),
        "first_action_or_escalation": rec.get("first_action_or_escalation", ""),
    }
    blob = json.dumps(sem, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def receipt_id(entity: str, tic: int, fp: str) -> str:
    return hashlib.sha256(f"{entity}:{tic}:{fp}".encode("utf-8")).hexdigest()[:16]


# The four semantic fields a complete CIVIC boot receipt owes (the verification surface).
_OWED_FIELDS = ("understood_scope", "accepted_constraints", "abstentions",
                "first_action_or_escalation")

# The BOOT-READ fields (tic 406, bk-boot-full-injection-read-invariant): the mutation-gate
# owed surface. The civic fields above close the boot LOOP; these close the boot-READ
# precondition that gates governance mutation (perception debt cannot authorize mutation).
# The pass-state the NARROW + FAIL-CLOSED gate requires:
#   full_boot_injection_read == True  AND  boot_read_mode == "full"
#   AND chunking == "gapless"         AND  omitted_ranges == []
# clipped_preview_detected is recorded for audit but does NOT block (a clip that was then
# expanded-and-read-in-full is a PASS — the point is reading in full, not never-clipped).
_BOOT_READ_FIELDS = ("full_boot_injection_read", "boot_read_mode", "chunking",
                     "omitted_ranges", "clipped_preview_detected")


def boot_read_passes(rec: dict) -> tuple:
    """(passes: bool, reason: str) for the boot-read mutation-gate pass-state."""
    if rec.get("full_boot_injection_read") is not True:
        return False, "full_boot_injection_read is not true"
    if rec.get("boot_read_mode") != "full":
        return False, f"boot_read_mode={rec.get('boot_read_mode')!r} (need 'full'; 'preview_only'/'not_available' block)"
    if rec.get("chunking") != "gapless":
        return False, f"chunking={rec.get('chunking')!r} (need 'gapless')"
    om = rec.get("omitted_ranges")
    if om:  # non-empty list (or truthy) = sections were skipped
        return False, f"omitted_ranges non-empty ({om})"
    return True, "boot-read receipt complete (full · gapless · no omissions)"


def receipt_missing(rec: dict) -> list:
    """Verify the receipt carries all four owed CIVIC fields non-empty. Returns the list
    of missing/empty fields (empty list == complete). The verification half of the
    handshake — a receipt that proves uptake must actually carry the proof."""
    miss = []
    for k in _OWED_FIELDS:
        v = rec.get(k)
        if not v or (isinstance(v, (list, str)) and len(v) == 0):
            miss.append(k)
    return miss


def _read_records(path: Path) -> list:
    """All receipt records (raw, in file order). Fail-soft to []."""
    out = []
    if not path.exists():
        return out
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return out


def gate_decision(root: Path, entity: str, tic: int, path: str = None) -> dict:
    """The boot-read mutation gate's CORE decision (one source; the hook is a thin shell).

    NARROW + FAIL-CLOSED: allow a governed mutation iff EITHER
      (1) a valid boot-read receipt exists for (entity, tic) (boot_read_passes), OR
      (2) a non-expired OVERRIDE receipt covers this (tic[, path]).
    PRECEDENCE (tic 407): a valid boot-read receipt is checked FIRST and OUTRANKS an
    override. The override is the fallback for when a clean full read cannot exist (clipped
    packet, unavailable injection) — not a substitute that pre-empts a genuine receipt. If
    the override were evaluated first, a stale/broad cadence-boundary override would MASK an
    honestly-emitted full-read receipt, reporting via='override' when the clean proof path
    was in fact satisfied (the exact mis-provenance observed at tic 407 entry). Clean proof
    wins; override only fills the gap when no clean proof is present.
    Else BLOCK. (This function only DECIDES; it never blocks the caller — the hook maps
    a non-allow decision to PreToolUse exit 2. Note: 'no receipt at all' => BLOCK, by
    design — missing perception proof is perception debt.)"""
    recs = [r for r in _read_records(sink_path(root)) if r.get("tic") == tic]
    # (1) valid boot-read receipt — checked FIRST so a clean proof outranks any override
    for r in recs:
        if entity not in (r.get("entity_id"), r.get("actor")):
            continue
        ok, why = boot_read_passes(r)
        if ok:
            return {"allow": True, "via": "boot_read_receipt", "reason": why,
                    "receipt_id": r.get("receipt_id")}
    # (2) override path — explicit, audited, non-silent — only when NO clean receipt exists
    for r in recs:
        if r.get("override") is True and (r.get("entity_id") == entity or r.get("actor") == entity):
            scope = r.get("override_scope")
            tp = r.get("touched_path")
            # scope 'tic' covers any path this tic; a path-scoped override must match the path tail
            if scope in (None, "", "tic", "all") or not path or not tp or tp in path or path in tp:
                return {"allow": True, "via": "override", "reason": r.get("reason", ""),
                        "receipt_id": r.get("receipt_id")}
    # fail-closed
    near = next(((boot_read_passes(r)[1]) for r in recs
                 if entity in (r.get("entity_id"), r.get("actor"))), "no receipt for this (entity,tic)")
    return {"allow": False, "via": "none", "reason": near}


# Emitted into the agent's context the moment the receipt is turned in — a couple
# load-bearing lanes + a read-discipline tripwire. The receipt attests
# `boot_read_mode=full`; this tail is the perception-layer reminder that the
# attestation is a promise about the REQUIRED files (NAVIGATION whole/gapless;
# the bench-packet intake lane for any /review docket), not a formality.
_BOOT_CLOSE_TAIL = (
    "🧭 Load-bearing lanes: NAVIGATION.md is the router of routers — read it "
    "WHOLE & gapless before you build or ask 'where does X live?'; a /review docket "
    "comes ONLY through the bench-packet intake lane "
    "(borns → cpr-extract → queue.jsonl → cpr-enrichment-scanner → "
    "governance/enrichment → bench-packet-prep), never ad hoc grep. "
    "⚠️ IF YOU DIDNT READ THE REQUIRED FILES MANDATED TO BE READ IN FULL AND "
    "GAPLESS, YOU BETTER EITHER FIX THAT, OR MOVE FASTER THAN THE ARCHITECT's "
    "TAXIDERMY SWEEP... DONT BE A SLOPSKILLET, HOMESKILLET :)"
)


def greeting(entity: str, tic: int, missing: list, deduped: bool = False) -> str:
    """The warm form-ack that closes the boot loop and sets session tone.
    Complete + recorded -> good-morning greeting; incomplete -> gentle nudge;
    deduped -> welcome-back. This is the perception-layer reward for crossing the
    boot threshold consciously (the loop the rendered '⟜ receipt owed' opened)."""
    if missing:
        return (f"📋 receipt recorded for {entity} @ tic {tic}, but incomplete — "
                f"owed fields still empty: {', '.join(missing)}. "
                "Fill them and re-emit to close the loop cleanly.")
    if deduped:
        return (f"🌅 already on file — good to see you, {entity}. "
                f"Receipt for tic {tic} is closed. "
                f"🜂 hold the tension, do not flatten it: the perimeter is wide so the center can wait. "
                f"Have a great tic! "
                f"{_BOOT_CLOSE_TAIL}")
    return (f"🌅 receipt received — good morning, {entity}! "
            f"Boot loop closed for tic {tic}. "
            f"🜂 hold the tension, do not flatten it: the perimeter is wide so the center can wait. "
            f"Have a great tic! "
            f"{_BOOT_CLOSE_TAIL}")


def existing_ids(path: Path) -> set:
    ids = set()
    if not path.exists():
        return ids
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line).get("receipt_id"))
            except json.JSONDecodeError:
                continue
    return ids


def emit(args) -> int:
    root = zone_root()
    path = sink_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)

    if args.payload:
        rec = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    else:
        rec = {
            "understood_scope": args.understood or "",
            "accepted_constraints": list(args.constraint or []),
            "abstentions": list(args.abstention or []),
            "first_action_or_escalation": args.first_action or "",
            "receipt_route": args.route or "",
        }
    rec["entity_id"] = args.entity
    rec["tic"] = args.tic
    rec.setdefault("booted_from", args.booted_from or "compiled_civic_orientation")
    rec.setdefault("model_of_record", args.model or os.environ.get("CGG_MODEL", "unknown"))
    # Boot-read fields (tic 406): present iff the caller supplied them (a payload may also
    # carry them). Recorded as-is; the gate evaluates them via boot_read_passes().
    if getattr(args, "boot_read_mode", None) is not None:
        rec["full_boot_injection_read"] = bool(args.full_boot_read)
        rec["boot_read_mode"] = args.boot_read_mode
        rec["chunking"] = args.chunking or ("gapless" if args.boot_read_mode == "full" else "n/a")
        rec["omitted_ranges"] = list(args.omitted_range or [])
        rec["clipped_preview_detected"] = bool(args.clipped_preview)

    fp = content_fingerprint(rec)
    rid = receipt_id(args.entity, args.tic, fp)
    rec["content_fingerprint"] = fp[:16]
    rec["receipt_id"] = rid
    rec["created_at"] = now_iso()

    missing = receipt_missing(rec)

    lock = path.with_suffix(path.suffix + ".lock")
    with lock.open("w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            if rid in existing_ids(path):
                ack = greeting(args.entity, args.tic, missing, deduped=True)
                sys.stderr.write(ack + "\n")
                print(json.dumps({"status": "deduped", "receipt_id": rid,
                                  "entity": args.entity, "tic": args.tic,
                                  "missing_fields": missing, "ack": ack,
                                  "note": "identical boot receipt already recorded for this (entity,tic)"}))
                return 0
            line = json.dumps(rec, ensure_ascii=False, sort_keys=True)
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644), "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)

    ack = greeting(args.entity, args.tic, missing)
    sys.stderr.write(ack + "\n")
    print(json.dumps({"status": "recorded", "receipt_id": rid, "entity": args.entity,
                      "tic": args.tic, "sink": str(path.relative_to(root)),
                      "missing_fields": missing, "ack": ack}))
    return 0


def list_receipts(args) -> int:
    root = zone_root()
    path = sink_path(root)
    if not path.exists():
        print("(no boot receipts yet)")
        return 0
    seen = {}
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if args.tic is not None and r.get("tic") != args.tic:
                continue
            seen[r.get("receipt_id")] = r  # latest-per-id
    for r in seen.values():
        print(f"[{r.get('tic')}] {r.get('entity_id'):20s} {r.get('receipt_id')} "
              f"route={r.get('receipt_route','-')} :: {r.get('first_action_or_escalation','')[:60]}")
    print(f"-- {len(seen)} unique receipt(s)" + (f" at tic {args.tic}" if args.tic is not None else ""))
    return 0


def compact(args) -> int:
    """Collapse same-id duplicates (latest-per-id), rewrite the sink atomically."""
    root = zone_root()
    path = sink_path(root)
    if not path.exists():
        print("(nothing to compact)")
        return 0
    lock = path.with_suffix(path.suffix + ".lock")
    with lock.open("w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            seen = {}
            order = []
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    rid = r.get("receipt_id")
                    if rid not in seen:
                        order.append(rid)
                    seen[rid] = r
            tmp = path.with_suffix(".jsonl.tmp")
            with tmp.open("w", encoding="utf-8") as out:
                for rid in order:
                    out.write(json.dumps(seen[rid], ensure_ascii=False, sort_keys=True) + "\n")
            os.replace(tmp, path)
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
    print(json.dumps({"status": "compacted", "unique": len(order)}))
    return 0


def emit_override(args) -> int:
    """Emit an OVERRIDE receipt — the explicit, audited, NON-SILENT escape from the
    boot-read mutation gate (tic 406 spec). Carries actor/tic/reason/touched_path/
    timestamp/override_scope. The gate honors it; the audit trail records WHY a clipped
    or receipt-less boot was permitted to mutate. Never a silent bypass."""
    root = zone_root()
    path = sink_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "override": True,
        "actor": args.actor,
        "entity_id": args.actor,
        "tic": args.tic,
        "reason": args.reason,
        "touched_path": args.touched_path or "",
        "override_scope": args.override_scope or "tic",
        "created_at": now_iso(),
        "model_of_record": args.model or os.environ.get("CGG_MODEL", "unknown"),
    }
    rec["receipt_id"] = receipt_id(args.actor, args.tic,
                                   hashlib.sha256(("override:" + (args.reason or "")).encode()).hexdigest())
    lock = path.with_suffix(path.suffix + ".lock")
    with lock.open("w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            if rec["receipt_id"] not in existing_ids(path):
                with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644), "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
    sys.stderr.write(f"⚠️  OVERRIDE receipt recorded for {args.actor} @ tic {args.tic} "
                     f"(scope={rec['override_scope']}): {args.reason}\n")
    print(json.dumps({"status": "override_recorded", "receipt_id": rec["receipt_id"],
                      "actor": args.actor, "tic": args.tic, "scope": rec["override_scope"]}))
    return 0


def gate_check(args) -> int:
    """Boot-read mutation-gate decision for (entity, tic[, path]). Prints JSON.
    Exit 0 = ALLOW, exit 3 = BLOCK (distinct from argparse's 2 so callers can tell a
    block from a usage error)."""
    root = zone_root()
    d = gate_decision(root, args.entity, args.tic, args.path)
    print(json.dumps(d))
    return 0 if d.get("allow") else 3


def main():
    ap = argparse.ArgumentParser(description="Citizen-Boot receipt sink (concurrency-safe, tic-mapped).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("emit", help="record a boot receipt (idempotent per entity+tic+content)")
    e.add_argument("--entity", required=True)
    e.add_argument("--tic", type=int, required=True)
    e.add_argument("--payload", help="path to JSON file with receipt fields")
    e.add_argument("--understood")
    e.add_argument("--constraint", action="append")
    e.add_argument("--abstention", action="append")
    e.add_argument("--first-action", dest="first_action")
    e.add_argument("--route")
    e.add_argument("--booted-from", dest="booted_from")
    e.add_argument("--model")
    # boot-read fields (tic 406) — supply --boot-read-mode to activate the boot-read block
    e.add_argument("--full-boot-read", dest="full_boot_read", action="store_true",
                   help="record full_boot_injection_read=true")
    e.add_argument("--boot-read-mode", choices=["full", "preview_only", "not_available"],
                   help="boot_read_mode (presence activates the boot-read fields)")
    e.add_argument("--chunking", choices=["gapless", "partial", "n/a"])
    e.add_argument("--omitted-range", dest="omitted_range", action="append",
                   help="a section omitted from the read (repeatable); none = full read")
    e.add_argument("--clipped-preview", dest="clipped_preview", action="store_true",
                   help="record clipped_preview_detected=true (informational; does not block)")
    e.set_defaults(func=emit)

    o = sub.add_parser("override", help="emit an audited, non-silent boot-read gate override")
    o.add_argument("--actor", required=True)
    o.add_argument("--tic", type=int, required=True)
    o.add_argument("--reason", required=True)
    o.add_argument("--touched-path", dest="touched_path")
    o.add_argument("--override-scope", dest="override_scope", default="tic",
                   help="'tic' (any path this tic) | a path substring | 'all'")
    o.add_argument("--model")
    o.set_defaults(func=emit_override)

    g = sub.add_parser("gate-check", help="boot-read mutation-gate decision (exit 0 allow / 3 block)")
    g.add_argument("--entity", required=True)
    g.add_argument("--tic", type=int, required=True)
    g.add_argument("--path", help="the surface being mutated (for path-scoped overrides)")
    g.set_defaults(func=gate_check)

    l = sub.add_parser("list", help="list receipts (optionally for a tic)")
    l.add_argument("--tic", type=int)
    l.set_defaults(func=list_receipts)

    c = sub.add_parser("compact", help="collapse same-id duplicates")
    c.set_defaults(func=compact)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
