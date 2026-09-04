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
     [--waive-enum-guard pending_class]

Enum vocabulary guard (B2 wave 10, /review 772 Q9): a DEFER/HOLD write whose
resolved `pending_class` is not one of the ratified values in
contracts/pending-class-enum-v1.json is REFUSED rc=2 (`pending_class_off_enum`)
and NOTHING is appended. This writer's OWN hardcoded defaults are off-table, so
a bare DEFER/HOLD now requires an explicit lawful --pending-class or the audited
--waive-enum-guard. What the defaults should become is /review 773's map-vs-admit
fork (proposal: audit-logs/governance/backlog-gunslinger-hoist/
om-w10-pending-class-default-map-vs-admit-fork-tic772.md) — NOT this writer's call.
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

# ---------------------------------------------------------------------------
# PENDING_CLASS ENUM VOCABULARY GUARD at this writer's write boundary
# (B2 wave 10; RULED /review 772 round 3 Q9, Architect-signed "SIGN"; basis
# /review 772 round 2 Q6; row `bk-off-enum-drift-field-generic-writer-topology`;
# staged audit-logs/governance/backlog-gunslinger-hoist/B2-wave-10-STAGED-tic772.json,
# signed B2-wave-10-SIGNED-tic772.json).
#
# WHY HERE, AND WHY IT BITES IMMEDIATELY. /review 767 Q4 guarded pending_class
# at queue-lifecycle-writeback.py ONLY. The contract's own `writer_topology`
# key names this script as the second unguarded birth writer, and — unlike
# cpr-extract, whose mints are on-table — THIS writer's hardcoded DEFER/HOLD
# defaults are THEMSELVES off-table against the ratified five:
#     HOLD  -> "architect_ruling"   (ruled a DIFFERENT QUANTITY at /review 768
#                                    round 2; it therefore NEVER enters the enum)
#     DEFER -> "maturity_window"
# So the guard refuses this writer's own defaults. That is the ruled effect,
# not an accident: a DEFER/HOLD write must now either pass an explicit LAWFUL
# --pending-class, or pass the audited --waive-enum-guard pending_class. What
# the defaults SHOULD become is the map-vs-admit fork, and that is /review
# 773's to adjudicate — this increment PROPOSES it (arm B) and never rules it.
# The defaults below are therefore left EXACTLY as they were.
#
# ENGINE-CONTENT SEPARATION (federation KI): the enum stays contract DATA,
# never inlined here. Extending it is a data edit in contracts/ authorized by
# a /review verdict. NOT fail-soft (the confidence_tier discipline): a missing
# contract crashes loudly at import rather than running half-guarded.
#
# NO CARRY-FORWARD ARM, by construction: build_event resolves pending_class
# from the CLI arg or the default and never reads the prior row's value, so
# every write at this site is an INTRODUCTION. The lifecycle writer's
# ENUM-CARRY-NOTICE exemption has no counterpart here — nothing to carry.
_CONTRACTS_DIR = _HERE.parent / "contracts"
PENDING_CLASS_CONTRACT_FILE = "pending-class-enum-v1.json"


def _load_pending_class_contract():
    with open(_CONTRACTS_DIR / PENDING_CLASS_CONTRACT_FILE, encoding="utf-8") as fh:
        return json.load(fh)


PENDING_CLASS_CONTRACT = _load_pending_class_contract()
PENDING_CLASS_ENUM = frozenset(PENDING_CLASS_CONTRACT["enum"].keys())


def classify_pending_class(value):
    """"lawful" for an enum member or the lawful no-value forms (None / "");
    "off_enum" for any other coinage, including a non-string."""
    if value is None or value == "":
        return "lawful"
    if not isinstance(value, str):
        return "off_enum"
    return "lawful" if value in PENDING_CLASS_ENUM else "off_enum"


def pending_class_refusal_message(value, locator):
    """Typed reject text: names the value, the RATIFIED FIVE, the CONTRACT FILE,
    and — load-bearing per the ruling — /review as the MINTING AUTHORITY."""
    return (
        f"{value!r} is not a ratified pending_class value. Lawful values: "
        f"{sorted(PENDING_CLASS_ENUM)} or absent. Governing artifact: "
        f"contracts/{PENDING_CLASS_CONTRACT_FILE} "
        f"({PENDING_CLASS_CONTRACT['ratified']}). "
        f"MINTING AUTHORITY: {PENDING_CLASS_CONTRACT['minting_authority']} "
        f"Refused at {locator}."
    )


class PendingClassOffEnum(Exception):
    """Raised when this writer would MINT an off-table pending_class."""

    code = "pending_class_off_enum"

    def __init__(self, value, locator):
        self.value = value
        self.locator = locator
        super().__init__(pending_class_refusal_message(value, locator))

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
                supersedes=None, waive_enum_guard=()) -> dict:
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
        #
        # RESOLVED ONCE (B2 wave 10). The prior code computed the same default
        # expression TWICE — once for the row, once for the `patch` mirror. Two
        # independently-evaluated copies of one value are a latent drift site
        # (edit one, miss the other, and the row disagrees with its own patch);
        # the guard needs a single value to classify anyway, so the duplication
        # is collapsed here rather than guarded twice.
        resolved_pending_class = pending_class or (
            "architect_ruling" if verdict == "HOLD" else "maturity_window")
        # ENUM VOCABULARY GUARD — refuse an off-table INTRODUCTION with the
        # typed code, BEFORE any append (build_event runs ahead of
        # append_event, and --dry-run goes through here too, so a refused value
        # can never be printed as a lawful preview either).
        if classify_pending_class(resolved_pending_class) != "lawful":
            locator = f"{object_id} ({verdict})"
            if "pending_class" in set(waive_enum_guard or ()):
                print(f"ENUM-GUARD-WAIVE-NOTICE [{object_id}]: off-table "
                      f"pending_class {resolved_pending_class!r} minted by "
                      f"queue_event_writer ({verdict}) and admitted by the "
                      f"caller (audited, visible — never silent; stamped at "
                      f"queue_event_writer.enum_guard_waived). If /review "
                      f"minted this value, land the contract amendment in the "
                      f"same pass.", file=sys.stderr)
                ev["queue_event_writer"] = {
                    "enum_guard_waived": {"pending_class": resolved_pending_class}
                }
            else:
                raise PendingClassOffEnum(resolved_pending_class, locator)
        ev.update({"event_type": "lifecycle_patch", "status": "enrichment_eligible",
                   "pending_class": resolved_pending_class,
                   "maturity_window_tics": maturity_window,
                   "lesson": current, "current_formulation": current,
                   "current_source_hash": _sha(current),
                   "patch": {"status": "enrichment_eligible",
                             "pending_class": resolved_pending_class,
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
    ap.add_argument("--waive-enum-guard", action="append", dest="waive_enum_guard",
                    default=[], metavar="FIELD",
                    help="Audited escape hatch for the enum vocabulary guard "
                         "(currently `pending_class`). Admits an off-table value "
                         "this writer would otherwise REFUSE (rc=2), with a stderr "
                         "ENUM-GUARD-WAIVE-NOTICE and a stamp at "
                         "queue_event_writer.enum_guard_waived on the row — never "
                         "silent. Mirrors --waive-enum-guard at "
                         "queue-lifecycle-writeback.py. /review is the minting "
                         "authority for the vocabulary itself "
                         "(contracts/pending-class-enum-v1.json); the hatch admits "
                         "a value, it does not ratify one.")
    a = ap.parse_args()
    try:
        ev = build_event(a.id, a.verdict, a.review_tic, a.authority, Path(a.queue),
                         home=a.home, promoted_to=a.promoted_to, new_formulation=a.new_formulation,
                         pending_class=a.pending_class, maturity_window=a.maturity_window,
                         merge_parents=a.merge_parents, supersedes=a.supersedes,
                         waive_enum_guard=a.waive_enum_guard)
    except PendingClassOffEnum as exc:
        print(f"queue_event_writer REFUSED [{exc.code}]: refusing to MINT an "
              f"off-table pending_class. {exc} Pass --waive-enum-guard "
              f"pending_class to admit it anyway (audited escape hatch, stamped "
              f"on the row). NOTHING was appended to the queue.", file=sys.stderr)
        return 2
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
