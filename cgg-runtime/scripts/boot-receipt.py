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


# The four semantic fields a complete boot receipt owes (the verification surface).
_OWED_FIELDS = ("understood_scope", "accepted_constraints", "abstentions",
                "first_action_or_escalation")


def receipt_missing(rec: dict) -> list:
    """Verify the receipt carries all four owed fields non-empty. Returns the list
    of missing/empty fields (empty list == complete). The verification half of the
    handshake — a receipt that proves uptake must actually carry the proof."""
    miss = []
    for k in _OWED_FIELDS:
        v = rec.get(k)
        if not v or (isinstance(v, (list, str)) and len(v) == 0):
            miss.append(k)
    return miss


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
                f"Have a great tic!")
    return (f"🌅 receipt received — good morning, {entity}! "
            f"Boot loop closed for tic {tic}. "
            f"🜂 hold the tension, do not flatten it: the perimeter is wide so the center can wait. "
            f"Have a great tic!")


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
    e.set_defaults(func=emit)

    l = sub.add_parser("list", help="list receipts (optionally for a tic)")
    l.add_argument("--tic", type=int)
    l.set_defaults(func=list_receipts)

    c = sub.add_parser("compact", help="collapse same-id duplicates")
    c.set_defaults(func=compact)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
