#!/usr/bin/env python3
"""fragment_receipt.py — per-fragment delivery auditability (Injection Fabric, tic 368).

Implements the SECOND genuinely-new build target of the Injection Fabric spec
(`autonomous_kernel/injection-fabric-spec.md` §1.3.2):

    "Per-fragment auditability — every delivered fragment leaves a receipt trail
     (what was carried, to whom, under what authority, why it was fresh, when it
     stops). Today the worldview emits a boot receipt for the *whole* injection;
     individual fragments are not independently accountable."

THE GAP THIS CLOSES. office-worldview.py already stamps each fragment with a
`receipt: {required: bool, expected_proof: [...]}` block — but the only receipt
SINK is the WHOLE-injection boot receipt (boot-receipt.py → boot-receipts.jsonl,
keyed by (entity, tic)). A single fragment that declares `receipt.required` has
no independent accountability: there is no record that *this* fragment, of *this*
pertinence class, under *this* authority, was delivered to *this* office at *this*
tic via *this* seam — and whether it was ADMISSIBLE against the contract. This
module is that per-fragment delivery-receipt lane.

WHERE IT SITS (three-layer economics, CLAUDE.md Tool Economics). This is the
PERCEPTION layer — a post-delivery receipt/observability artifact. It NEVER gates
delivery and NEVER enforces (that would be the physics layer); it RECORDS what was
delivered and whether the contract would admit it. A rejected fragment is still
recorded (with its admission errors) — the receipt surfaces the violation, it does
not suppress the delivery.

GOVERNING INVARIANT (spec §6): canonical owns the lifecycle; runtimes produce
artifacts. The per-fragment delivery receipt IS the artifact a runtime produces to
prove it rendered what canonical admitted. This module is read-only on the
lifecycle: it imports the canonical admission verdict from `fragment_contract`
(single-source, tic 367) and never decides admissibility itself, never mutates a
fragment, never retires anything, never writes the registry.

SELF-OPERATION SIGNAL DISCIPLINE (spec §6 / carried CogPR tic 350). The injection
surface is one the system uses for perception/execution/routing/boot — so the
receipt records, it does not self-admit. A runtime that could self-admit fragments
would be mutating the surface that grants it sight. It cannot.

CONCURRENCY + IDEMPOTENCE (mirrors boot-receipt.py exactly):
  - Append-only JSONL; O_APPEND writes under PIPE_BUF are atomic across procs.
  - flock(LOCK_EX) serializes read-existing-ids + append within/across processes.
  - DETERMINISTIC id = sha256(recipient:tic:seam:fragment_id:content_fp)[:16].
    The same fragment delivered to the same office at the same tic via the same
    seam dedups to ONE receipt. A CHANGED fragment text yields a NEW content_fp →
    a NEW receipt, so silent fragment drift is visible, not collapsed. This is the
    same loop-guard as the boot-injection lane + the 200+ signal-loop class
    (deterministic-id + dedup-at-write).

SCOPE (Architect-gated, tic 368). This slice builds the per-fragment receipt
emitter + auditor and proves it against real worldview emissions. It deliberately
does NOT wire emission into the live boot render path (that touches a boot-critical
surface and is the additive follow-on — "render+prove before wiring"; fixes are
additive, never remove a local activation). It runs as a separate, opt-in step
that consumes the SAME json envelope office-worldview.py already produces. The
sibling genuinely-new target (the task-touch seam, §1.3.1) is out of this slice.
"""

from __future__ import annotations

import argparse
import datetime
import fcntl
import hashlib
import json
import os
import sys
from pathlib import Path

# ── shared contract import (single-source; mirrors office-worldview.py) ───────
# The 3 normative directives + the admission verdict live in the shared Injection
# Fabric contract (lib/fragment_contract.py, tic 367). Import from the sibling lib/
# so the receipt records the SAME admission verdict every delivery model honors.
# FAIL-SOFT: a catastrophic import failure degrades the admission field to
# "unavailable" rather than crash — a receipt that records class/authority is still
# useful, and an auditability lane must never itself break delivery observability.
_LIB = Path(__file__).resolve().parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
try:
    from fragment_contract import validate_fragment, PERTINENCE_CLASSES  # type: ignore
    _CONTRACT_OK = True
except Exception:  # pragma: no cover - boot-safety only
    _CONTRACT_OK = False
    PERTINENCE_CLASSES = {}

    def validate_fragment(frag):  # type: ignore
        return (None, ["fragment_contract import unavailable — admission not evaluated"])


SCHEMA = "boot-injections/fragment-delivery-receipt@1"

# Fields the spec §4 names but does NOT yet enforce. We OBSERVE them descriptively
# in the receipt (never enforce), so the migration that exercises the contract has
# evidence about which of the 6 are load-bearing per delivery. (Instrumental-not-
# terminal: record before promoting any to normative.)
_OBSERVED_NAMED_UNENFORCED = (
    "methylation", "source", "freshness",
    "receipt_requirement", "stop_condition", "follow_surface",
)


def zone_root() -> Path:
    """Resolve the federation/zone root by walking up for audit-logs/boot-injections.
    Same resolver shape as boot-receipt.py (a __file__-rooted resolver finds the
    zone it lives in — self-locating-artifact discipline, tic 365)."""
    p = Path(__file__).resolve()
    for anc in [p] + list(p.parents):
        if (anc / "audit-logs" / "boot-injections").is_dir():
            return anc
    cand = Path("/Users/breydentaylor/canonical")
    if (cand / "audit-logs" / "boot-injections").is_dir():
        return cand
    raise SystemExit("fragment-receipt: could not locate zone root (audit-logs/boot-injections)")


def sink_path(root: Path) -> Path:
    return root / "audit-logs" / "boot-injections" / "fragment-receipts.jsonl"


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def content_fingerprint(frag: dict) -> str:
    """Stable fingerprint over the DELIVERED CONTENT (text + class + authority).
    Changing any of these is a different delivery — a new receipt, not a dedup.
    Excludes methylation weight + reason prose (volatile, non-semantic-to-delivery)."""
    auth = frag.get("authority") or {}
    sem = {
        "text": frag.get("text", ""),
        "class": (frag.get("pertinence") or {}).get("class", ""),
        "may_act_from": bool(auth.get("may_act_from")),
        "may_quote": bool(auth.get("may_quote")),
        "must_escalate": bool(auth.get("must_escalate")),
    }
    blob = json.dumps(sem, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def delivery_receipt_id(recipient: str, tic: int, seam: str, frag_id: str, fp: str) -> str:
    return hashlib.sha256(
        f"{recipient}:{tic}:{seam}:{frag_id}:{fp}".encode("utf-8")
    ).hexdigest()[:16]


def _observed(frag: dict) -> dict:
    """Descriptively observe the named-but-unenforced §4 fields present on the
    fragment. Invents NOTHING — absent fields stay None — so the receipt reports
    exactly what the delivery model carried, no more."""
    auth = frag.get("authority") or {}
    pert = frag.get("pertinence") or {}
    meth = frag.get("methylation") or {}
    rcpt = frag.get("receipt") or {}
    return {
        # methylation
        "methylation_weight": meth.get("weight"),
        # source / provenance handle
        "source": frag.get("source"),
        # freshness (registry-shape entries carry inject_from/until; worldview live-derives → absent)
        "freshness": {
            "inject_from_tic": frag.get("inject_from_tic"),
            "inject_until_tic": frag.get("inject_until_tic"),
        } if ("inject_from_tic" in frag or "inject_until_tic" in frag) else None,
        # receipt requirement (the field that motivates THIS lane)
        "receipt_required": bool(rcpt.get("required")),
        # stop condition
        "stop_condition": frag.get("reminder_at_tic") if "reminder_at_tic" in frag else None,
        # follow-surface (the pointer, not the body — post-dehydration discipline)
        "follow_surface": pert.get("follow_surface") or frag.get("follow_surface"),
        # gating sub-badge (a YOURS obligation that may not silently widen)
        "gated": bool(frag.get("gated")),
    }


def make_receipt(frag: dict, *, recipient: str, tic: int, seam: str) -> dict:
    """Build a per-fragment delivery receipt. Records the 3 NORMATIVE axes
    (pertinence / authority / citation), the canonical admission verdict (from the
    shared contract — NOT decided here), and the observed named-unenforced fields.
    Pure: reads the fragment, invents nothing, mutates nothing."""
    auth = frag.get("authority") or {}
    pert = frag.get("pertinence") or {}
    frag_id = str(frag.get("id", "<anon>"))
    fp = content_fingerprint(frag)

    admitted, errors = validate_fragment(frag)

    rec = {
        "schema": SCHEMA,
        "delivery_receipt_id": delivery_receipt_id(recipient, tic, seam, frag_id, fp),
        "fragment_id": frag_id,
        "content_fingerprint": fp[:16],
        "recipient": recipient,
        "tic": tic,
        "seam": seam,
        # ── the 3 normative axes, recorded independently (pertinence ≠ authority ≠ citation) ──
        "pertinence_class": pert.get("class"),
        "authority": {
            "may_act_from": bool(auth.get("may_act_from")),
            "may_mutate_source": bool(auth.get("may_mutate_source")),
            "must_escalate": bool(auth.get("must_escalate")),
        },
        "citation": {"may_quote": bool(auth.get("may_quote"))},
        # ── canonical admission verdict (imported, not decided) ──
        "admission": {
            "evaluated": _CONTRACT_OK,
            "admitted": admitted,
            "errors": errors,
        },
        # ── named-but-unenforced fields, OBSERVED descriptively (not gated) ──
        "observed": _observed(frag),
        "created_at": now_iso(),
    }
    return rec


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
                ids.add(json.loads(line).get("delivery_receipt_id"))
            except json.JSONDecodeError:
                continue
    return ids


def emit_receipts(frags: list, *, recipient: str, tic: int, seam: str,
                  root: Path = None) -> dict:
    """Emit one per-fragment delivery receipt per fragment, dedup-at-write.

    Concurrency-safe (flock + O_APPEND), idempotent by deterministic id. Returns a
    summary {recorded, deduped, rejected, by_class, sink}. A fragment whose contract
    admission FAILS is still RECORDED (admission.admitted=False + errors) — the lane
    surfaces violations, it does not suppress delivery (perception layer, not physics).
    """
    root = root or zone_root()
    path = sink_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)

    recorded, deduped, rejected = [], [], 0
    by_class: dict = {}

    lock = path.with_suffix(path.suffix + ".lock")
    with lock.open("w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            have = existing_ids(path)
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644),
                           "a", encoding="utf-8") as fh:
                for frag in frags:
                    rec = make_receipt(frag, recipient=recipient, tic=tic, seam=seam)
                    cls = rec.get("pertinence_class") or "<none>"
                    by_class[cls] = by_class.get(cls, 0) + 1
                    if rec["admission"]["evaluated"] and rec["admission"]["admitted"] is False:
                        rejected += 1
                    rid = rec["delivery_receipt_id"]
                    if rid in have:
                        deduped.append(rid)
                        continue
                    have.add(rid)
                    fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                    recorded.append(rid)
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)

    return {
        "status": "recorded",
        "recipient": recipient, "tic": tic, "seam": seam,
        "fragments": len(frags),
        "recorded": len(recorded),
        "deduped": len(deduped),
        "rejected_admission": rejected,
        "by_class": by_class,
        "sink": str(path.relative_to(root)),
        "contract_available": _CONTRACT_OK,
    }


def _fragments_from_worldview(obj: dict) -> tuple:
    """Pull (fragments, office, tic) from an office-worldview render --format json
    envelope (schema boot-injections/worldview/pertinence-compiled@1)."""
    frags = obj.get("fragments", [])
    return frags, obj.get("office"), obj.get("tic")


def audit(root: Path = None, tic: int = None, recipient: str = None) -> dict:
    """Read-only summary of the per-fragment receipt sink (latest-per-id)."""
    root = root or zone_root()
    path = sink_path(root)
    seen = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if tic is not None and r.get("tic") != tic:
                    continue
                if recipient is not None and r.get("recipient") != recipient:
                    continue
                seen[r.get("delivery_receipt_id")] = r
    by_class, by_recipient = {}, {}
    admitted = rejected = unevaluated = receipt_required = 0
    for r in seen.values():
        cls = r.get("pertinence_class") or "<none>"
        by_class[cls] = by_class.get(cls, 0) + 1
        by_recipient[r.get("recipient")] = by_recipient.get(r.get("recipient"), 0) + 1
        adm = r.get("admission", {})
        if not adm.get("evaluated"):
            unevaluated += 1
        elif adm.get("admitted"):
            admitted += 1
        else:
            rejected += 1
        if (r.get("observed") or {}).get("receipt_required"):
            receipt_required += 1
    return {
        "unique_receipts": len(seen),
        "admitted": admitted, "rejected": rejected, "unevaluated": unevaluated,
        "receipt_required": receipt_required,
        "by_class": by_class, "by_recipient": by_recipient,
        "sink": str(path.relative_to(root)) if path.exists() else None,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Injection Fabric per-fragment delivery auditability (§1.3.2). "
                    "Emit one receipt per delivered fragment; record the 3 normative "
                    "axes + canonical admission verdict; dedup-at-write.")
    ap.add_argument("--from-worldview", metavar="PATH",
                    help="emit receipts from an office-worldview render --format json "
                         "envelope ('-' = stdin); recipient+tic read from the envelope")
    ap.add_argument("--emit", metavar="PATH",
                    help="emit receipts from a raw fragments JSON (list or {fragments:[...]})")
    ap.add_argument("--seam", default="boot", help="delivery seam (default: boot)")
    ap.add_argument("--recipient", help="recipient office (required for --emit)")
    ap.add_argument("--tic", type=int, help="delivery tic (required for --emit)")
    ap.add_argument("--zone-root", default=None)
    ap.add_argument("--audit", action="store_true", help="read-only summary of the sink")
    ap.add_argument("--self-test", action="store_true", help="run receipt-lane self-checks")
    args = ap.parse_args()

    root = Path(args.zone_root).resolve() if args.zone_root else None

    def _load(path):
        text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8", errors="replace")
        return json.loads(text)

    if args.self_test:
        return _self_test()

    if args.from_worldview:
        obj = _load(args.from_worldview)
        frags, office, tic = _fragments_from_worldview(obj)
        if not office or tic is None:
            print("from-worldview: envelope missing office/tic", file=sys.stderr)
            return 2
        out = emit_receipts(frags, recipient=office, tic=tic, seam=args.seam, root=root)
        print(json.dumps(out, indent=1))
        return 0

    if args.emit:
        if not args.recipient or args.tic is None:
            print("--emit requires --recipient and --tic", file=sys.stderr)
            return 2
        obj = _load(args.emit)
        frags = obj.get("fragments", obj) if isinstance(obj, dict) else obj
        out = emit_receipts(frags, recipient=args.recipient, tic=args.tic, seam=args.seam, root=root)
        print(json.dumps(out, indent=1))
        return 0

    if args.audit:
        print(json.dumps(audit(root=root, tic=args.tic, recipient=args.recipient), indent=1))
        return 0

    ap.print_help()
    return 0


def _self_test() -> int:
    failures = []

    def check(name, cond):
        print(("PASS" if cond else "FAIL"), name)
        if not cond:
            failures.append(name)

    # a well-formed YOURS fragment receipt records the 3 axes + admits
    yours = {
        "id": "lane.0", "source": "worldview/office-lanes.json", "text": "centroid lane",
        "pertinence": {"class": "YOURS", "reason": "r"},
        "authority": {"may_read": True, "may_shape_interpretation": True, "may_act_from": True,
                      "may_mutate_source": True, "may_quote": True, "must_escalate": False},
        "methylation": {"weight": 0.9}, "receipt": {"required": True},
    }
    r = make_receipt(yours, recipient="ent_homeskillet", tic=368, seam="boot")
    check("YOURS receipt records pertinence_class", r["pertinence_class"] == "YOURS")
    check("YOURS receipt records citation axis independently", r["citation"]["may_quote"] is True)
    check("YOURS receipt admits (contract available)", (not _CONTRACT_OK) or r["admission"]["admitted"] is True)
    check("YOURS receipt observes receipt_required", r["observed"]["receipt_required"] is True)
    check("YOURS receipt observes source provenance", r["observed"]["source"] == "worldview/office-lanes.json")

    # deterministic id: same fragment+context → same id
    r2 = make_receipt(yours, recipient="ent_homeskillet", tic=368, seam="boot")
    check("deterministic id (same delivery → same id)", r["delivery_receipt_id"] == r2["delivery_receipt_id"])

    # changed text → different id (drift visible, not collapsed)
    drifted = dict(yours, text="centroid lane (edited)")
    r3 = make_receipt(drifted, recipient="ent_homeskillet", tic=368, seam="boot")
    check("changed text → new id (drift visible)", r3["delivery_receipt_id"] != r["delivery_receipt_id"])

    # different seam → different id
    r4 = make_receipt(yours, recipient="ent_homeskillet", tic=368, seam="midturn")
    check("different seam → new id", r4["delivery_receipt_id"] != r["delivery_receipt_id"])

    # a loosened fragment is RECORDED with admission rejected (perception, not suppression)
    loosened = {
        "id": "bad.0", "text": "field claiming act authority",
        "pertinence": {"class": "FIELD", "reason": "r"},
        "authority": {"may_read": True, "may_shape_interpretation": True, "may_act_from": True,
                      "may_mutate_source": False, "may_quote": False, "must_escalate": False},
        "receipt": {"required": False},
    }
    rbad = make_receipt(loosened, recipient="ent_x", tic=368, seam="boot")
    if _CONTRACT_OK:
        check("loosened fragment recorded with admission rejected", rbad["admission"]["admitted"] is False)
        check("rejected receipt still records the axes", rbad["pertinence_class"] == "FIELD")
    else:
        check("contract unavailable → admission unevaluated", rbad["admission"]["evaluated"] is False)

    # round-trip emit/dedup against a temp sink under the real zone (no prod write)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        troot = Path(td)
        (troot / "audit-logs" / "boot-injections").mkdir(parents=True)
        frags = [yours, drifted, loosened]
        out1 = emit_receipts(frags, recipient="ent_test", tic=368, seam="boot", root=troot)
        check("first emit records all 3", out1["recorded"] == 3 and out1["deduped"] == 0)
        out2 = emit_receipts(frags, recipient="ent_test", tic=368, seam="boot", root=troot)
        check("re-emit dedups all 3 (idempotent)", out2["recorded"] == 0 and out2["deduped"] == 3)
        summ = audit(root=troot)
        check("audit sees 3 unique receipts", summ["unique_receipts"] == 3)
        # yours + drifted both inherit receipt.required=True; loosened is False → 2
        check("audit counts receipt_required", summ["receipt_required"] == 2)

    print()
    if failures:
        print(f"{len(failures)} FAILED:", ", ".join(failures))
        return 1
    print("all fragment-receipt self-checks PASS"
          + ("" if _CONTRACT_OK else "  (NOTE: fragment_contract import unavailable — admission degraded)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
