#!/usr/bin/env python3
"""queue_event_writer.py — Repair Covenant B typed verdict writer (object-2, /review 635).

The ONE typed writer review-execute uses to append a verdict to the CogPR queue. It emits a
proper Option-B typed event that is ALSO a full-snapshot compatibility row (carries `lesson`
+ `status` so the legacy naive latest-per-id reader stays non-lossy during the transition),
and appends it through the REAL write boundary (lib/atomic-append.sh). It NEVER hand-writes.

Covers every verdict shape this review emits: PROMOTE / REFINEMENT_RAY (lifecycle_patch),
SKIP_WITH_HOME (relation), DEFER / HOLD (spec-correct lifecycle_patch: status=enrichment_eligible
+ pending_class + maturity_window, NEVER status=deferred — cgg-ledger#status-value-reader-
disagreement), MODIFY_PROMOTE (formulation_update — advances the ratified NEW wording), and
MERGE / SUPERSEDE (relation events with parent/predecessor hashes).

Hard invariant (#4): a formulation-bearing event with a BLANK current_formulation is REFUSED
UNCONDITIONALLY — there is no migration exception; the migration manifest PROVIDES a nonblank
origin so the body is never blank, and a genuinely blank body exits 2 LOUD.

Contract: audit-logs/governance/review-635-repair-covenant-b/spec.md
Usage:
  queue_event_writer.py --queue <path> --id <cpr_id> --verdict <V> --review-tic 635
     --authority <artifact> [--home <target>] [--promoted-to <anchor>]
     [--new-formulation <text>] [--pending-class <x>] [--maturity-window <n>]
     [--merge-parents id1,id2] [--supersedes id@ver] [--dry-run]
"""
from __future__ import annotations
import argparse, json, hashlib, subprocess, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import queue_event_materializer as M   # shadow_project, load_migration, _rows_for, _sha

ATOMIC_APPEND = _HERE / "lib" / "atomic-append.sh"
SCHEMA_VERSION = 1
REPAIR_B_EVENT_TYPES = {"birth", "formulation_update", "lifecycle_patch",
                        "enrichment_append", "merge", "supersede", "skip_with_home", "tombstone"}

def _sha(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()

def _prior(object_id: str, queue: Path) -> dict:
    rows = M._rows_for(object_id, queue)
    shadow = M.shadow_project(object_id, queue)
    return {"object_version": len(rows),  # monotonic; sorts after all legacy rows
            "current_formulation": shadow.get("current_formulation") or "",
            "current_hash": shadow.get("current_source_hash") or _sha(shadow.get("current_formulation") or ""),
            "origin_formulation": shadow.get("origin_formulation"),
            "origin_source_pointer": shadow.get("origin_source_pointer"),
            "origin_source_hash": shadow.get("origin_source_hash"),
            "birth_tic": shadow.get("birth_tic")}

def build_event(object_id, verdict, review_tic, authority, queue: Path,
                home=None, promoted_to=None, new_formulation=None,
                pending_class=None, maturity_window=None, merge_parents=None,
                supersedes=None) -> dict:
    p = _prior(object_id, queue)
    verdict = verdict.upper()
    # resolve the current formulation this event lands on
    if verdict in ("MODIFY_PROMOTE", "MERGE"):
        current = (new_formulation or "").strip()
        formulation_bearing = True
    else:
        current = (p["current_formulation"] or "").strip()
        formulation_bearing = verdict in ("PROMOTE", "REFINEMENT_RAY", "SKIP_WITH_HOME",
                                          "DEFER", "HOLD", "SUPERSEDE")
    # ---- UNCONDITIONAL blank refusal (#4) ----
    if formulation_bearing and not current:
        raise SystemExit(f"REFUSED: {verdict} on {object_id!r} has a BLANK current_formulation "
                         f"(no migration exception — a formulation-bearing event must carry a body).")

    ev = {
        "id": object_id,                       # legacy key (naive reader)
        "schema_version": SCHEMA_VERSION,
        "object_version": p["object_version"],
        "emitted_at_tic": review_tic,
        "emitted_by": "review-execute (review-635)",
        "governing_authority": authority,
        "review_tic": review_tic,
        "review": "review-635",
        "compat_snapshot": True,   # full-snapshot bridge: carries body forward for the naive reader
                                    # (the physics guard refuses a compat_snapshot row with a blank body)
        # immutable origin/provenance carried on every event for addressability
        "origin_source_pointer": p["origin_source_pointer"],
        "origin_source_hash": p["origin_source_hash"],
        "birth_tic": p["birth_tic"],
    }
    ev["event_id"] = _sha(f"{object_id}|{p['object_version']}|{verdict}|{review_tic}")[:16]

    if verdict in ("PROMOTE", "REFINEMENT_RAY"):
        ev.update({"event_type": "lifecycle_patch", "status": "promoted",
                   "promoted_to": promoted_to or home,
                   "lesson": current, "current_formulation": current,
                   "current_source_hash": _sha(current),
                   "patch": {"status": "promoted", "promoted_to": promoted_to or home},
                   "verdict_class": verdict.lower()})
    elif verdict == "SKIP_WITH_HOME":
        if not home:
            raise SystemExit("REFUSED: SKIP_WITH_HOME requires --home")
        ev.update({"event_type": "skip_with_home", "status": "skipped",
                   "home_relation": home, "lesson": current, "current_formulation": current,
                   "current_source_hash": _sha(current),
                   "patch": {"status": "skipped", "home_relation": home}})
    elif verdict in ("DEFER", "HOLD"):
        # spec-correct DEFER/HOLD — NEVER status=deferred
        ev.update({"event_type": "lifecycle_patch", "status": "enrichment_eligible",
                   "pending_class": pending_class or ("architect_ruling" if verdict == "HOLD"
                                                      else "maturity_window"),
                   "maturity_window_tics": maturity_window,
                   "lesson": current, "current_formulation": current,
                   "current_source_hash": _sha(current),
                   "patch": {"status": "enrichment_eligible",
                             "pending_class": pending_class or ("architect_ruling"
                             if verdict == "HOLD" else "maturity_window"),
                             "maturity_window_tics": maturity_window}})
    elif verdict == "MODIFY_PROMOTE":
        ev.update({"event_type": "formulation_update", "status": "promoted",
                   "promoted_to": promoted_to or home,
                   "current_formulation": current, "lesson": current,
                   "current_source_hash": _sha(current),
                   "formulation_version": p["object_version"],  # monotonic version
                   "replaces_version": "legacy" if p["object_version"] else 0,
                   "predecessor_hash": p["current_hash"],
                   "patch": {"status": "promoted", "current_formulation": current},
                   "verdict_class": "modify_and_promote"})
    elif verdict == "MERGE":
        parents = [x for x in (merge_parents or "").split(",") if x]
        ev.update({"event_type": "merge", "status": "promoted",
                   "current_formulation": current, "lesson": current,
                   "current_source_hash": _sha(current),
                   "parent_object_ids": parents,
                   "parent_hashes": [_sha(pp) for pp in parents],
                   "patch": {"status": "promoted", "current_formulation": current}})
    elif verdict == "SUPERSEDE":
        if not supersedes:
            raise SystemExit("REFUSED: SUPERSEDE requires --supersedes id@ver")
        ev.update({"event_type": "supersede", "status": "superseded",
                   "supersedes": supersedes, "lesson": current, "current_formulation": current,
                   "current_source_hash": _sha(current),
                   "patch": {"status": "superseded", "supersedes": supersedes}})
    else:
        raise SystemExit(f"REFUSED: unknown verdict {verdict!r}")
    return ev

def append_event(ev: dict, queue: Path) -> None:
    """Append through the REAL write boundary (lib/atomic-append.sh)."""
    line = json.dumps(ev, ensure_ascii=False, separators=(",", ":"))
    r = subprocess.run(["bash", str(ATOMIC_APPEND), "--append", str(queue), line],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"atomic-append failed (exit {r.returncode}): {r.stderr}")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--verdict", required=True)
    ap.add_argument("--review-tic", type=int, required=True)
    ap.add_argument("--authority", required=True)
    ap.add_argument("--home"); ap.add_argument("--promoted-to")
    ap.add_argument("--new-formulation"); ap.add_argument("--pending-class")
    ap.add_argument("--maturity-window", type=int)
    ap.add_argument("--merge-parents"); ap.add_argument("--supersedes")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    ev = build_event(a.id, a.verdict, a.review_tic, a.authority, Path(a.queue),
                     home=a.home, promoted_to=a.promoted_to, new_formulation=a.new_formulation,
                     pending_class=a.pending_class, maturity_window=a.maturity_window,
                     merge_parents=a.merge_parents, supersedes=a.supersedes)
    if a.dry_run:
        print(json.dumps(ev, indent=2, ensure_ascii=False)); return 0
    append_event(ev, Path(a.queue))
    print(json.dumps({"appended": True, "event_id": ev["event_id"], "id": ev["id"],
                      "event_type": ev["event_type"], "status": ev["status"],
                      "object_version": ev["object_version"],
                      "lesson_len": len(ev.get("lesson") or "")}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
