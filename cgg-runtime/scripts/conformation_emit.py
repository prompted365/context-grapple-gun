#!/usr/bin/env python3
"""
Conformation Emitter — instruments the exercised->counted edge of the CogPR
lifecycle (the missing emitter surfaced in the tic-398 investigation:
audit-logs/governance/conformation-emitter-gap-investigation-tic398.md).

Centroid (pinned by the 6-facet non-collapse perimeter — labels subordinated):

  IS         — a point-of-use emitter: when a session genuinely exercises a
               pending CogPR's pattern, it appends ONE evidence-bound event to
               an append-only conformation ledger. /review tallies events into n.
  IS-NOT     — (leads) NOT a similarity counter (the pattern_miner word-overlap
               proxy that read n=18 from shared vocabulary alone); NOT a prose
               n re-asserted and inherited across the tic boundary; NOT an
               auto-promoter (emit != promote — /review still gates); NOT a
               self-certifying claim (every event MUST carry an evidence_ref or
               it is rejected); NOT a mutable polled state-store (append-only +
               deterministic-id dedup, never a rebuilt counter); NOT retroactive
               fabrication (the detect lane surfaces CANDIDATES, it never tallies).
  HOLDS      — self-reported (the exercising session knows best, cheaply) <->
               gameable (a session inflating its own n). Held by: self-report is
               ADMISSIBLE because every event is evidence-bound + spot-checkable,
               and the tally is /review-gated. Falsifiable, not trusted.
  COMPLEMENT — inert without: (1) /review reading the ledger and tallying;
               (2) a real evidence_ref to point at; (3) the pending-CogPR set.
  COUNTER    — what kills it: self-certification w/o evidence; counting
               similarity not exercise; a standing pattern re-emitting every tic
               with no NEW evidence (the signal-loop class); auto-promotion on
               threshold (gate bypass).
  TELOS      — a pending CogPR's n == count of DISTINCT TICS that genuinely
               exercised it, each event evidence-bound; /review re-derives n from
               events since last verdict (never inherits prose-n); `trigger: n/a`
               is outlawed.

Two lanes:
  EMIT (high-confidence, point-of-use)  — `emit` below. Evidence-bound, dedup-at-write.
  DETECT (low-confidence, retroactive)  — `detect_candidates` below. Structural
               anchors (id refs, source_cpr lineage) = strong candidates; optional
               NLP token-overlap = weak candidates. NEVER writes the ledger —
               surfaces a candidate set for /review to CONFIRM (mention != conformation).

Usage:
  conformation_emit.py emit --cpr cpr_x --tic 398 --evidence commit:abc123 \
      --kind applied --note "..."
  conformation_emit.py tally --cpr cpr_x [--since-tic 395]
  conformation_emit.py detect --cpr cpr_x [--nlp]      # candidates only, no write
  conformation_emit.py report                          # n for every pending CogPR
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Surfaces
# ---------------------------------------------------------------------------

def _audit_root():
    # resolve from this file: cgg-runtime/scripts/ -> walk to federation audit-logs
    here = Path(__file__).resolve()
    for anc in here.parents:
        cand = anc / "audit-logs" / "cprs" / "queue.jsonl"
        if cand.exists():
            return anc / "audit-logs"
    # fallback: cwd
    return Path.cwd() / "audit-logs"

AUDIT = _audit_root()
QUEUE = AUDIT / "cprs" / "queue.jsonl"
LEDGER = AUDIT / "cprs" / "conformations.jsonl"           # append-only event ledger
CANDIDATES = AUDIT / "cprs" / "conformation-candidates.jsonl"  # detect-lane output (advisory)

VALID_KINDS = {"applied", "extended", "validated", "instantiated", "corroborated"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _event_id(cpr_id, tic, evidence_ref):
    """Condition-stable id: same (cpr, tic, evidence) -> same id -> dedup-at-write.
    A standing pattern cannot re-inflate n every tic because a new event needs a
    NEW evidence_ref; same evidence -> same id -> skipped."""
    h = hashlib.sha256(f"conform:{cpr_id}:{tic}:{evidence_ref}".encode()).hexdigest()[:16]
    return f"cnf_{h}"


def _atomic_append(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from lib.atomic_append import atomic_append_jsonl  # type: ignore
        atomic_append_jsonl(str(path), obj)
    except Exception:
        import fcntl
        lock = str(path) + ".lock"
        with open(lock, "w") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(obj, separators=(",", ":")) + "\n")
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_ledger():
    """Latest-per-event-id wins (append-only); returns list of live events."""
    seen = {}
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("id"):
                seen[d["id"]] = d
    return list(seen.values())


def load_pending_cprs():
    """Latest-per-id queue projection, pending (non-terminal) only, with fullest lesson."""
    PENDING = {"born_truth_captured", "enrichment_eligible", "enrichment_in_progress",
               "enrichment_needed", "extracted", "pending", "promotable",
               "review_ready", "tic_gated", "deferred"}
    latest = {}
    lesson = {}
    if not QUEUE.exists():
        return {}
    for line in QUEUE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        i = d.get("id")
        if not i:
            continue
        latest[i] = d
        les = d.get("lesson", "")
        if les and len(les) > len(lesson.get(i, "")):
            lesson[i] = les
    out = {}
    for i, d in latest.items():
        if d.get("status") in PENDING:
            d = dict(d)
            d["_fullest_lesson"] = lesson.get(i, d.get("lesson", ""))
            out[i] = d
    return out


# ---------------------------------------------------------------------------
# EMIT lane
# ---------------------------------------------------------------------------

def emit(cpr_id, tic, evidence_ref, kind="applied", note="", emitted_by="ent_homeskillet-c48"):
    """Append one evidence-bound conformation event. Rejects empty evidence
    (IS-NOT self-certification). Dedup-at-write by condition-stable id."""
    if not evidence_ref or not str(evidence_ref).strip():
        return {"ok": False, "reason": "evidence_ref required (no self-certification)"}
    if kind not in VALID_KINDS:
        return {"ok": False, "reason": f"kind must be one of {sorted(VALID_KINDS)}"}
    eid = _event_id(cpr_id, tic, evidence_ref)
    existing = {e["id"] for e in load_ledger()}
    if eid in existing:
        return {"ok": True, "id": eid, "deduped": True,
                "reason": "same (cpr,tic,evidence) already counted"}
    event = {
        "type": "conformation",
        "id": eid,
        "cpr_id": cpr_id,
        "tic": int(tic),
        "evidence_ref": evidence_ref,
        "exercise_kind": kind,
        "emitted_by": emitted_by,
        "emitted_at": _now(),
        "note": note[:280],
    }
    _atomic_append(LEDGER, event)
    return {"ok": True, "id": eid, "deduped": False, "event": event}


# ---------------------------------------------------------------------------
# TALLY lane  (this is what /review imports — n is re-derived, never inherited)
# ---------------------------------------------------------------------------

def tally_n(cpr_id, since_tic=None):
    """n = count of DISTINCT TICS with at least one evidence-bound event.
    Distinct-tic (not distinct-event) so multiple evidence refs in one tic = 1
    conformation. Birth is instance 0; each distinct exercise-tic adds 1."""
    tics = set()
    events = []
    for e in load_ledger():
        if e.get("cpr_id") != cpr_id:
            continue
        if since_tic is not None and e.get("tic", 0) < since_tic:
            continue
        tics.add(e.get("tic"))
        events.append(e)
    return {"cpr_id": cpr_id, "n": len(tics), "distinct_tics": sorted(tics),
            "events": events}


# ---------------------------------------------------------------------------
# DETECT lane  (advisory candidates ONLY — never writes the ledger)
# ---------------------------------------------------------------------------

_STOP = set("the a an and or of to in is are be it its this that for on with as by "
            "not no its at from into per via NOT IS are was were has have had must "
            "should will can may a an each every some any when then than".split())


def _tokens(text):
    return {w for w in re.findall(r"[a-z0-9_]+", text.lower())
            if len(w) > 3 and w not in _STOP}


def detect_candidates(cpr_id, use_nlp=False, scan_globs=None):
    """Surface CANDIDATE conformations for /review to confirm. Two strengths:
      STRONG  — structural anchor: the cpr_id (or its source_cpr lineage) is
                explicitly referenced in a session record / commit message.
      WEAK    — (only if use_nlp) NLP token-overlap >= 0.25 between the CogPR
                lesson and a session record, surfaced as a low-confidence lead.
    Mention != conformation: WEAK candidates are NOT counted, only surfaced. A
    human/review confirms a candidate by calling `emit` with a real evidence_ref."""
    pend = load_pending_cprs()
    lesson = pend.get(cpr_id, {}).get("_fullest_lesson", "")
    if scan_globs is None:
        mem = os.path.expanduser("~/.claude/projects/-Users-breydentaylor-canonical/memory")
        scan_globs = [f"{mem}/session_lessons_tic_*.md"]
    strong, weak = [], []
    ltok = _tokens(lesson) if (use_nlp and lesson) else set()
    for g in scan_globs:
        for fn in glob.glob(g):
            try:
                txt = Path(fn).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            base = os.path.basename(fn)
            mtic = re.search(r"tic_(\d+)", base)
            tic = int(mtic.group(1)) if mtic else None
            if cpr_id in txt:
                strong.append({"source": base, "tic": tic, "strength": "strong",
                               "why": "explicit cpr_id reference"})
                continue
            if use_nlp and ltok:
                stok = _tokens(txt)
                inter = ltok & stok
                jac = len(inter) / max(1, len(ltok | stok))
                if jac >= 0.25:
                    weak.append({"source": base, "tic": tic, "strength": "weak",
                                 "jaccard": round(jac, 3),
                                 "why": "nlp token-overlap (candidate only — confirm with evidence)"})
    return {"cpr_id": cpr_id, "strong": strong, "weak": weak,
            "note": "STRONG = confirm by emit; WEAK = lead only, mention != conformation"}


# ---------------------------------------------------------------------------
# REPORT  (re-derive n for every pending CogPR — the /review surface)
# ---------------------------------------------------------------------------

def report():
    pend = load_pending_cprs()
    rows = []
    for cid in pend:
        t = tally_n(cid)
        rows.append((t["n"], cid, t["distinct_tics"]))
    rows.sort(reverse=True)
    return rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Conformation Emitter")
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("emit")
    pe.add_argument("--cpr", required=True)
    pe.add_argument("--tic", required=True, type=int)
    pe.add_argument("--evidence", required=True)
    pe.add_argument("--kind", default="applied")
    pe.add_argument("--note", default="")

    pt = sub.add_parser("tally")
    pt.add_argument("--cpr", required=True)
    pt.add_argument("--since-tic", type=int, default=None)

    pd = sub.add_parser("detect")
    pd.add_argument("--cpr", required=True)
    pd.add_argument("--nlp", action="store_true")

    sub.add_parser("report")

    args = p.parse_args()
    if args.cmd == "emit":
        print(json.dumps(emit(args.cpr, args.tic, args.evidence, args.kind, args.note), indent=2))
    elif args.cmd == "tally":
        print(json.dumps(tally_n(args.cpr, args.since_tic), indent=2))
    elif args.cmd == "detect":
        print(json.dumps(detect_candidates(args.cpr, use_nlp=args.nlp), indent=2))
    elif args.cmd == "report":
        rows = report()
        print(f"# Conformation n for {len(rows)} pending CogPRs (re-derived from events)")
        for n, cid, tics in rows:
            flag = "  <- ready (n>=2)" if n >= 2 else ""
            print(f"  n={n}  {cid}  tics={tics}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
