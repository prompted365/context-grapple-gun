#!/usr/bin/env python3
"""
Queue Lifecycle Writeback — the COPY-FORWARD writer for lifecycle-class queue rows.

WHY THIS EXISTS (bk-review-execute-lifecycle-writeback-envelope-stripping, found by
cpr-stepper pass cpr-step-683 finding F3, tic 683):

  `audit-logs/cprs/queue.jsonl` is append-only with **latest-entry-per-id-wins** read
  semantics. Every standard reader (`cpr-gate-advance.load_queue`, bench-packet-prep,
  the enrichment scanner, the boot banner) projects state by REPLACING the whole row:
  `entries[id] = row`. There is NO field-level reconciliation across rows. So a
  lifecycle writeback that emits a from-scratch row carrying only the verdict fields
  does not "update" the entry — it REPLACES the entry with a thinner one, and every
  field it omitted is GONE from the authoritative projection.

  Lived instance: at /review 682 the DEFER writeback for
  `cpr_mogul_review_close_check_79ae89ca3a0a` appended a 24-field lifecycle-only row
  over a 37-field envelope, dropping `lesson`, `source`, `source_date`, `subsystem`,
  `recommended_scopes`, `birth_tic`, `confidence_tier`, `lesson_type` (+ more). The
  enrichment scanner then recorded
  `no_evidence_reason: "no gatherer produced evidence (missing: source, source_date,
  subsystem, recommended_scopes, lesson)"` — the row's own pending_class classification
  became partly an ARTIFACT OF THE STRIPPING, not of the CogPR. Repaired in-lane at tic
  683 (queue row stamped `field_passthrough_repair`); this file is the GENERATOR fix so
  it cannot recur.

  Mechanism class: **field passthrough** — the first of the four Conductor-Score-Runtime
  Parity mechanism classes (`cgg-ledger#conductor-score-runtime-parity-cgg-application`):
  *producer→consumer pipelines must explicitly preserve schema fields, no silent
  stripping.* The doctrine named it; the runtime did not enforce it, because the
  lifecycle writeback was FREEHAND (review-execute.md prose), not mechanized.

THE CONTRACT (what this script guarantees):

  1. COPY-FORWARD. The emitted row starts as the id's CURRENT latest-per-id row — the
     full envelope — and only then merges the lifecycle fields on top.
  2. LIFECYCLE-ONLY MUTATION. Only fields in `LIFECYCLE_MUTABLE_FIELDS` may be set.
     Envelope fields (identity / content / birth provenance) are REFUSED with a named
     error, never silently written. `--allow-field` is the audited, explicit escape.
  3. NO-DROP POST-ASSERT. Before the append, `envelope_drops(prior, candidate)` must be
     empty. A thin row is REFUSED (rc=2) rather than appended. This is the same guard
     `--validate-row` exposes for rows built by any other writer.
  4. ATOMIC APPEND. The write goes through `lib/atomic-append.sh` (flock) so the
     tic-481 promote-writeback physics gate at that boundary still fires for
     promote-class rows. History rows are NEVER rewritten (append-only).
  5. WRITE-SIDE TERMINAL VALVE (bk-cpr-stepper-docket-race-write-guard, tic 707).
     The prior row is re-read AT WRITE TIME, and a candidate that would move a
     hard-terminal id (promoted/absorbed/superseded/rejected/dismissed/resolved/
     skipped — `deferred` is suspensive and excluded) back to a NON-terminal status
     is REFUSED as `terminal_state_resurrection` (rc=2): the stepper-vs-verdict
     write race lands here as a refusal instead of a resurrection. Terminal→
     terminal stays lawful; `--allow-terminal-transition` is the audited escape
     hatch, stamped on the row when it fires. The same predicate runs in
     `--validate-row` (rc=3) so any other writer can preflight. Residual window:
     the compose-time re-read closes the minutes-scale race; the sub-second
     window between re-read and flock append is documented, not defended.
  6. TIER VOCABULARY GUARD (/review 708 off-enum rulings 1-4, tic 708). A candidate
     that would INTRODUCE an off-enum `confidence_tier` (not a member of
     contracts/confidence-tier-enum-v1.json's ratified enum, and not the prior
     row's own value) is REFUSED as `confidence_tier_off_enum` (rc=2) — the
     typed reject names the sub-kind (class_bleed / non_tier_marker / off_enum)
     and points at the governing artifact. Unchanged carry-forward of a
     historical off-enum value stays lawful and is disclosed via a stderr
     TIER-CARRY-NOTICE (ruling 2: history stays as-is). The same predicate runs
     in `--validate-row` (rc=3), including on birth rows (a fresh row is by
     definition an introduction). Content lives in the contract file — the
     enum is a data edit, never an engine change. Sibling birth surface:
     cogpr-ingest.py strips an off-enum candidate value to ABSENT with a typed
     `tier_refusal` marker (the lesson is never dropped).

NOT THIS SCRIPT'S JOB:
  - Minting a BIRTH row (no prior row -> refuse; that is cpr-extract.py's surface).
  - Inline/auto-memory writeback (that is review-promote-writeback.py, the sibling —
    inline `status:` flip + `<!-- promoted from ... -->` breadcrumb).
  - Judgment of any kind. The docket approval IS the judgment; this is bookkeeping.

Usage:
  # DEFER (spec representation — see review-execute.md "DEFER")
  python3 queue-lifecycle-writeback.py --cpr-id cpr_x_tic679 --review-tic 683 \
    --lifecycle-json '{"status":"enrichment_eligible","pending_class":"feedback_required",
                       "maturity_window_tics":1,"review_verdict":"DEFER",
                       "review_confidence":0.8,"review_reasoning":"..."}'

  # PROMOTE / SKIP (same mechanism; the fields differ)
  python3 queue-lifecycle-writeback.py --cpr-id cpr_x_tic679 --review-tic 683 \
    --set status=skipped --set review_verdict=SKIP --set review_reasoning="derivable"

  # cpr-stepper ADVANCE — no --review-tic (stamping it would falsely assert /review
  # docket ownership and self-fence the row). `--current-tic` carries the recompile
  # clock instead; it is NEVER merged onto the row. Omit it and the clock resolves
  # from the canonical tic log.
  python3 queue-lifecycle-writeback.py --cpr-id cpr_x_tic721 --writer cpr-stepper \
    --current-tic 724 --lifecycle-json '{"status":"tic_gated","advanced_tic":724}'

  # Compose + validate WITHOUT writing (prints the single-line JSON row)
  python3 queue-lifecycle-writeback.py --cpr-id ... --emit-only --set status=...

  # Guard a row some OTHER writer built (rc=3 when it would strip the envelope)
  python3 queue-lifecycle-writeback.py --validate-row '<single-line JSON row>'

Exit codes: 0 ok · 1 append failure · 2 refused (contract violation) · 3 validate-row
found envelope drops.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
try:
    from zone_root import resolve_zone_root  # noqa: E402
except Exception:  # pragma: no cover - zone_root always present in runtime
    resolve_zone_root = None  # type: ignore
# Tier vocabulary guard content (/review 708 ruling 4). Deliberately NOT
# fail-soft: a guard surface whose governing contract is missing must crash
# loudly at import, not run half-guarded.
from confidence_tier import classify_tier_value, refusal_message  # noqa: E402

_QUEUE_REL = os.path.join("audit-logs", "cprs", "queue.jsonl")
_ATOMIC_APPEND_REL = os.path.join("lib", "atomic-append.sh")


# ---------------------------------------------------------------------------
# The declared field classes. CONTENT, not engine (engine-content separation is
# mandatory for federation-grade gate primitives) — extending the lifecycle set is a
# data edit here, never a rewrite of the merge/assert machinery below.
# ---------------------------------------------------------------------------

# Fields a lifecycle-class writeback MAY set. Everything a /review verdict, a stepper
# advance, or a window annotation legitimately writes — drawn from the shapes actually
# present in queue.jsonl (review-execute PROMOTE/DEFER/SKIP, cpr-stepper advances,
# cpr-gate-advance reconciles) plus the additive `lifecycle_state` the down-lane spec
# reserves (`ladder-downlane-spec`; lifecycle rides metadata, NEVER status-enum growth).
LIFECYCLE_MUTABLE_FIELDS = frozenset({
    # --- status core ---
    "status", "prior_status", "lifecycle_state",
    # --- /review verdict envelope ---
    "review_tic", "review_verdict", "review_confidence", "review_reasoning",
    "review_pass", "review_at", "reviewed_at", "review_confidence_basis",
    "review_confidence_tier", "review_ratified_by", "ratified_by",
    # --- DEFER window / gating (the spec representation, cgg-ledger#status-value-
    #     reader-disagreement-sticky-masks-reactivated-item) ---
    "pending_class", "maturity_window_tics", "re_eval_condition",
    "window_anchor_tic", "partial_falsification_pending", "blocked_on",
    # --- PROMOTE landing ---
    "promoted_to", "promoted_tic", "promoted_date", "promoted_at",
    "inscription_form", "compact_root_status",
    # --- ABSORB landing (MERGE / SUPERSEDE / absorb-as-stub; the /review Step-7
    #     shape: status=absorbed + absorbed_reason "merged into <id>" / "superseded
    #     by <id>" / stub-of-twin. Family was absent until t689 — all 220 prior
    #     absorbed rows predate this writer, so its first absorb refused fail-closed) ---
    "absorbed_reason", "absorbed_tic", "absorbed_date", "absorbed_by",
    # --- the RULED terminal field set (/review 739 A1-739 minimal writeback field set,
    #     forward-only; declared here /review 741 Q4 "apply same-pass" after two passes
    #     [740, 739->740] through the --allow-field valve for a MANDATORY set):
    #     adjudicated_at_tic = the verdict-side single-writer clock (review_tic is
    #     never overloaded by verdicts); absorbed_into = the ray/anchor an absorb
    #     lands on; landing_kind = reinforce_existing | refinement_ray | ... ---
    "adjudicated_at_tic", "absorbed_into", "landing_kind",
    # --- advance / reconcile breadcrumbs ---
    "advanced_tic", "advanced_at", "advanced_by", "advance_reason", "current_tic",
    "gate_advanced_at_tic", "gate_advanced_by", "gate_advance_reason",
    "stepper_annotation", "staleness", "relations",
    # --- writeback provenance (stamped by this script) ---
    "updated_at", "lifecycle_writeback",
})

# Envelope fields whose mutation by a LIFECYCLE writeback is a category error: identity,
# the CogPR's content, and its birth provenance. Refused with a named error so the
# operator sees WHY (rather than a generic "unknown field"). These are exactly the
# fields the tic-682 thin row dropped, plus their siblings.
ENVELOPE_PROTECTED_FIELDS = frozenset({
    "id", "lesson", "source", "source_date", "subsystem", "recommended_scopes",
    "birth_tic", "birth_rung", "birth_scope_path", "confidence_tier", "lesson_type",
    "dedup_hash", "dedup_verification", "extracted_at", "extracted_by", "id_origin",
    "origin_context", "origin_formulation", "origin_source_hash",
    "origin_source_pointer", "type", "tier", "band", "motivation_layer", "note",
    "mogul_mandate_id", "mogul_runtime", "source_cycle", "schema_version",
})

# WRITE-SIDE TERMINAL VALVE (bk-cpr-stepper-docket-race-write-guard, tic 707).
# The hard-terminal subset of the shared read-side TERMINAL_STATUSES (bench-packet-
# prep / cogpr-ingest / cpr-extract): a status whose latest-per-id row settles the
# id. `deferred` is deliberately EXCLUDED — it is SUSPENSIVE by design (a
# chronologically later row lawfully re-activates the id; see bench-packet-prep
# SUSPENSIVE_STATUSES). A lifecycle writeback that would move a hard-terminal id
# BACK to a non-terminal status is a RESURRECTION — the measured stepper-vs-
# review-execute race shape (A5 lane, tic 704: 38.1s unfavorable overlap) — and is
# refused at compose time, where the prior row is re-read at write time. Terminal→
# terminal transitions stay lawful (reviewed reshaping, e.g. a down-lane
# SUPERSEDE); `--allow-terminal-transition` is the audited escape hatch for a
# reviewed reactivation lane.
HARD_TERMINAL_STATUSES = frozenset({
    "promoted", "absorbed", "superseded", "rejected",
    "dismissed", "resolved", "skipped",
})


class LifecycleWritebackRefused(Exception):
    """Raised when the writeback would violate the copy-forward contract.

    Carries `.reasons` (list of dicts) so the CLI can report every violation at once
    rather than the first — an applier fixing one field at a time is exactly the
    per-session recovery loop the generator fix exists to end.
    """

    def __init__(self, reasons):
        self.reasons = reasons
        super().__init__("; ".join(r["message"] for r in reasons))


# ---------------------------------------------------------------------------
# Queue resolution / reading
# ---------------------------------------------------------------------------

def default_queue_path():
    """Resolve the federation CogPR queue by walking up from this script, then via
    zone_root (mirrors review-promote-writeback._default_queue). Returns Path or None."""
    here = Path(os.path.abspath(__file__)).parent
    for d in [here, *here.parents]:
        cand = d / _QUEUE_REL
        if cand.is_file():
            return cand
    if resolve_zone_root is not None:
        try:
            cand = Path(resolve_zone_root()) / _QUEUE_REL
            if cand.is_file():
                return cand
        except Exception:
            pass
    return None


def read_rows_for_id(queue_path, cpr_id):
    """Return [(line_no, row), ...] for cpr_id, in file order.

    Unparseable lines are skipped (they are never authoritative); the count is
    returned so a caller can surface corruption rather than silently reading past it.
    """
    hits = []
    unparseable = 0
    p = Path(queue_path)
    if not p.is_file():
        return hits, unparseable
    with p.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            # cheap pre-filter on the large queue before the json parse
            if cpr_id not in line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                unparseable += 1
                continue
            if row.get("id") == cpr_id:
                hits.append((n, row))
    return hits, unparseable


def latest_row_for_id(queue_path, cpr_id):
    """The AUTHORITATIVE row for cpr_id — plain latest-per-id (last matching line wins).

    Deliberately NOT terminal-state-valve filtered: the valve is a READ projection for
    consumers deciding lifecycle state, but the row a writeback must copy forward is the
    one that is currently authoritative under the naive latest-per-id readers — that is
    precisely the row whose fields would be lost.
    """
    hits, unparseable = read_rows_for_id(queue_path, cpr_id)
    if not hits:
        return None, None, unparseable
    line_no, row = hits[-1]
    return row, line_no, unparseable


def history_field_gap(queue_path, cpr_id):
    """Fields present in EARLIER rows for this id but absent from the latest row.

    Detection only — never auto-merged. A non-empty gap means an earlier writeback
    already stripped the envelope (the defect this script prevents going forward);
    healing it is a data repair that belongs to a reviewed lane, not to an automatic
    side-effect of the next status flip.
    """
    hits, _ = read_rows_for_id(queue_path, cpr_id)
    if len(hits) < 2:
        return []
    latest = set(hits[-1][1])
    union = set()
    for _, row in hits[:-1]:
        union |= set(row)
    return sorted(union - latest)


# ---------------------------------------------------------------------------
# The contract guards
# ---------------------------------------------------------------------------

def envelope_drops(prior_row, candidate_row):
    """Fields present in the prior (authoritative) row but ABSENT from the candidate.

    THE guard. Under latest-per-id semantics a dropped field is a DELETED field, so a
    non-empty result means the candidate would silently erase envelope state. This is
    the predicate that would have caught the tic-682 thin row at write time.
    """
    return sorted(set(prior_row) - set(candidate_row))


def classify_lifecycle_fields(lifecycle, allow_fields=()):
    """Split requested mutations into (ok, protected, unknown) by declared class."""
    allow = set(allow_fields or ())
    ok, protected, unknown = [], [], []
    for key in lifecycle:
        if key in LIFECYCLE_MUTABLE_FIELDS or key in allow:
            ok.append(key)
        elif key in ENVELOPE_PROTECTED_FIELDS:
            protected.append(key)
        else:
            unknown.append(key)
    return sorted(ok), sorted(protected), sorted(unknown)


def build_lifecycle_row(prior_row, lifecycle, review_tic=None, writer=None,
                        allow_fields=(), now=None, allow_terminal_transition=False):
    """Compose the copy-forward row. Raises LifecycleWritebackRefused on any violation.

    Order is load-bearing: classify FIRST (so a protected-field attempt never reaches
    the merge), merge SECOND, post-assert THIRD (defense in depth — a future refactor
    that breaks the merge is caught before the append, not after).
    """
    reasons = []
    if not isinstance(lifecycle, dict) or not lifecycle:
        reasons.append({
            "code": "empty_lifecycle_payload",
            "message": "no lifecycle fields supplied — nothing to write "
                       "(use --lifecycle-json and/or --set)",
        })
        raise LifecycleWritebackRefused(reasons)

    lifecycle = dict(lifecycle)
    if review_tic is not None and "review_tic" not in lifecycle:
        lifecycle["review_tic"] = review_tic

    # Write-side terminal valve: a non-terminal status over a hard-terminal prior is
    # a resurrection (the stepper-vs-verdict race shape), refused unless the caller
    # explicitly carries the audited escape hatch.
    prior_status_now = prior_row.get("status")
    candidate_status = lifecycle.get("status")
    if (prior_status_now in HARD_TERMINAL_STATUSES
            and candidate_status is not None
            and candidate_status != prior_status_now
            and candidate_status not in HARD_TERMINAL_STATUSES
            and not allow_terminal_transition):
        reasons.append({
            "code": "terminal_state_resurrection",
            "message": f"prior row is hard-terminal ({prior_status_now!r}) and the "
                       f"candidate status {candidate_status!r} is non-terminal — "
                       f"appending it would RESURRECT a decided id under "
                       f"latest-per-id semantics. If this id genuinely raced a "
                       f"concurrent verdict, drop the advancement and report it; a "
                       f"reviewed reactivation lane may pass "
                       f"--allow-terminal-transition (audited).",
        })
        raise LifecycleWritebackRefused(reasons)

    # Tier vocabulary guard — guarantee 6 (/review 708 ruling 4, write-boundary
    # physics; A6-707: the vocabulary must not depend on producer restraint).
    # confidence_tier is envelope-protected, so this path is reachable only via
    # the audited --allow-field escape — the escape audits envelope MUTATION,
    # not vocabulary, so the guard still refuses an off-enum INTRODUCTION here.
    # Unchanged carry-forward of a historical off-enum value stays lawful and
    # is disclosed (ruling 2: the 31 historical marker rows stay as-is).
    if "confidence_tier" in lifecycle:
        cand_tier = lifecycle["confidence_tier"]
        prior_tier = prior_row.get("confidence_tier")
        tier_kind = classify_tier_value(cand_tier)
        if tier_kind != "lawful":
            if cand_tier == prior_tier:
                print(f"TIER-CARRY-NOTICE [{prior_row.get('id')}]: off-enum "
                      f"confidence_tier {cand_tier!r} carried forward unchanged "
                      f"(historical row, disclosed per /review 708 ruling 2)",
                      file=sys.stderr)
            else:
                reasons.append({
                    "code": "confidence_tier_off_enum",
                    "message": f"refusing to INTRODUCE an off-enum confidence_tier "
                               f"({tier_kind}): "
                               f"{refusal_message(cand_tier, tier_kind)}",
                })
                raise LifecycleWritebackRefused(reasons)

    ok, protected, unknown = classify_lifecycle_fields(lifecycle, allow_fields)
    if protected:
        reasons.append({
            "code": "envelope_protected_field",
            "fields": protected,
            "message": f"refusing to mutate envelope-protected field(s) {protected} in a "
                       f"LIFECYCLE writeback — identity / lesson content / birth "
                       f"provenance are not lifecycle state. Correcting them is a "
                       f"reviewed data repair, not a status flip.",
        })
    if unknown:
        reasons.append({
            "code": "undeclared_lifecycle_field",
            "fields": unknown,
            "message": f"field(s) {unknown} are not declared in LIFECYCLE_MUTABLE_FIELDS. "
                       f"Add them to the declared set (content edit) or pass "
                       f"--allow-field <name> to write them explicitly.",
        })
    if reasons:
        raise LifecycleWritebackRefused(reasons)

    row = dict(prior_row)
    before_keys = set(row)
    prior_status = row.get("status")
    # F-742-L1 (n=2, /review 744): `mutated_fields` names the fields whose VALUE
    # actually moved against the authoritative prior row; a field the caller
    # passed with an unchanged value is a RESTATED field — recorded beside, never
    # counted as a mutation (review_tic 743->743 on four t743 promotes read as
    # "mutated" and forced a value-read at the stepper's Check B).
    _MISSING = object()
    value_changed_fields = sorted(
        k for k in lifecycle if prior_row.get(k, _MISSING) != lifecycle[k])
    restated_fields = sorted(
        k for k in lifecycle if k in prior_row and prior_row.get(k) == lifecycle[k])

    # `prior_status` is the corpus convention for a transition breadcrumb (cpr-gate-
    # advance stamps it too). Only auto-stamp on a real status change and only when the
    # caller has not set it — an explicit caller value always wins.
    if ("status" in lifecycle and lifecycle["status"] != prior_status
            and "prior_status" not in lifecycle and prior_status is not None):
        lifecycle["prior_status"] = prior_status

    row.update(lifecycle)

    stamp_time = now or datetime.now(timezone.utc).isoformat()
    row.setdefault("updated_at", stamp_time)
    row["lifecycle_writeback"] = {
        "by": "queue-lifecycle-writeback",
        "writer": writer or "unspecified",
        "at": stamp_time,
        "prior_status": prior_status,
        "copied_forward_fields": len(before_keys),
        # A1-745 / A3-746 (n=2, /review 746): the ROW stamp carries the same three-way
        # split the SUMMARY already carries — a field the caller ADDED is not a field
        # whose value MUTATED. Before this cure the row listed 16 "mutated" of which
        # 15 were merely added (93.8%), and a reader of the row alone could not tell.
        "mutated_fields": sorted(k for k in value_changed_fields if k in before_keys),
        "added_fields": sorted(k for k in value_changed_fields if k not in before_keys),
        "restated_fields": restated_fields,
    }
    if (allow_terminal_transition and prior_status in HARD_TERMINAL_STATUSES
            and candidate_status is not None
            and candidate_status not in HARD_TERMINAL_STATUSES):
        # the audited escape hatch actually fired — record it on the row itself
        row["lifecycle_writeback"]["terminal_transition_allowed"] = True

    drops = envelope_drops(prior_row, row)
    if drops:  # pragma: no cover - unreachable by construction; the tripwire is the point
        raise LifecycleWritebackRefused([{
            "code": "envelope_drop",
            "fields": drops,
            "message": f"post-assert FAILED: composed row drops {len(drops)} field(s) "
                       f"{drops} present in the authoritative row — refusing the append.",
        }])

    report = {
        "copied_forward_fields": len(before_keys),
        "field_count_before": len(before_keys),
        "field_count_after": len(row),
        "mutated_fields": sorted(k for k in value_changed_fields if k in before_keys),
        "restated_fields": restated_fields,
        "added_fields": sorted(set(row) - before_keys),
        "envelope_drops": [],
        "post_assert_no_envelope_drop": True,
        "prior_status": prior_status,
        "new_status": row.get("status"),
    }
    return row, report


# ---------------------------------------------------------------------------
# The append (atomic, flock, append-only)
# ---------------------------------------------------------------------------

def _atomic_append_script():
    p = Path(os.path.abspath(__file__)).parent / _ATOMIC_APPEND_REL
    return p if p.is_file() else None


def _needs_leading_newline(queue_path):
    p = Path(queue_path)
    if not p.is_file() or p.stat().st_size == 0:
        return False
    with p.open("rb") as f:
        f.seek(-1, os.SEEK_END)
        return f.read(1) != b"\n"


def append_row(queue_path, row):
    """Append one JSON line under flock. Returns the append mechanism used.

    Preferred path is `lib/atomic-append.sh` — NOT merely because it locks, but because
    the tic-481 promote-writeback physics gate lives at that boundary: a promote-class
    row appended by any other means silently skips the inline/breadcrumb writeback.
    The in-process flock fallback is used only when the shell primitive is unavailable
    or the file lacks a trailing newline (which the shell primitive does not repair).
    """
    line = json.dumps(row, separators=(",", ":"), default=str)
    script = _atomic_append_script()
    if script is not None and not _needs_leading_newline(queue_path):
        proc = subprocess.run(
            ["bash", str(script), "--append", str(queue_path), line],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"atomic-append.sh refused/failed (rc={proc.returncode}): "
                f"{(proc.stderr or '').strip()}"
            )
        return "atomic-append.sh"

    import fcntl
    lockfile = str(queue_path) + ".lock"
    os.makedirs(os.path.dirname(str(queue_path)) or ".", exist_ok=True)
    with open(lockfile, "w") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            prefix = "\n" if _needs_leading_newline(queue_path) else ""
            with open(queue_path, "a", encoding="utf-8") as f:
                f.write(prefix + line + "\n")
                f.flush()
                os.fsync(f.fileno())
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
    return "flock-inprocess"


# ---------------------------------------------------------------------------
# Top-level operations
# ---------------------------------------------------------------------------

def lifecycle_writeback(cpr_id, lifecycle, queue_path=None, review_tic=None,
                        writer=None, allow_fields=(), dry_run=False, emit_only=False,
                        now=None, allow_terminal_transition=False):
    """Compose + guard + atomically append one lifecycle-class row for cpr_id."""
    qpath = Path(queue_path) if queue_path else default_queue_path()
    if qpath is None or not Path(qpath).is_file():
        raise LifecycleWritebackRefused([{
            "code": "queue_unresolved",
            "message": f"could not resolve the CogPR queue (tried {qpath!r}); "
                       f"pass --queue-path explicitly.",
        }])

    prior, prior_line, unparseable = latest_row_for_id(qpath, cpr_id)
    if prior is None:
        raise LifecycleWritebackRefused([{
            "code": "no_prior_row",
            "message": f"no queue row found for id {cpr_id!r}. This script writes "
                       f"lifecycle TRANSITIONS by copying an existing envelope forward; "
                       f"it does not mint births (that is cpr-extract.py). A missing row "
                       f"is an execution anomaly — surface it upward, do not hand-write "
                       f"a thin row.",
        }])

    row, report = build_lifecycle_row(
        prior, lifecycle, review_tic=review_tic, writer=writer,
        allow_fields=allow_fields, now=now,
        allow_terminal_transition=allow_terminal_transition)

    gap = history_field_gap(qpath, cpr_id)
    append_via = "none(dry-run)" if (dry_run or emit_only) else append_row(qpath, row)

    return {
        "mode": "lifecycle_writeback",
        "cpr_id": cpr_id,
        "queue_path": str(qpath),
        "prior": {
            "line": prior_line,
            "status": prior.get("status"),
            "field_count": len(prior),
        },
        "unparseable_lines_scanned": unparseable,
        "lifecycle_fields": lifecycle,
        "row": row,
        "summary": {
            **report,
            "history_field_gap": gap,
            "appended": append_via not in ("none(dry-run)",),
            "append_via": append_via,
        },
    }


def validate_row(candidate_row, queue_path=None):
    """Guard a row built by ANY writer: would appending it strip the envelope?

    The read-only complement to `lifecycle_writeback` — the same predicate, available
    to a caller that composed its row some other way (or to a post-hoc audit of a row
    that already landed).
    """
    qpath = Path(queue_path) if queue_path else default_queue_path()
    cpr_id = candidate_row.get("id")
    if not cpr_id:
        return {"mode": "validate_row", "verdict": "REFUSE", "reason": "row has no id",
                "envelope_drops": []}
    if qpath is None or not Path(qpath).is_file():
        return {"mode": "validate_row", "verdict": "REFUSE",
                "reason": f"could not resolve the CogPR queue ({qpath!r})",
                "envelope_drops": []}
    prior, prior_line, _ = latest_row_for_id(qpath, cpr_id)
    cand_tier = candidate_row.get("confidence_tier")
    cand_tier_kind = classify_tier_value(cand_tier)
    if prior is None:
        # Birth row: nothing to preserve, but the tier vocabulary guard still
        # applies — a fresh row is by definition an INTRODUCTION (/review 708
        # ruling 4; guarantee 6).
        if cand_tier_kind != "lawful":
            return {"mode": "validate_row", "cpr_id": cpr_id, "verdict": "REFUSE",
                    "confidence_tier_off_enum": True,
                    "reason": f"confidence_tier_off_enum ({cand_tier_kind}) on a "
                              f"birth row: "
                              f"{refusal_message(cand_tier, cand_tier_kind)}",
                    "envelope_drops": []}
        return {"mode": "validate_row", "cpr_id": cpr_id, "verdict": "PASS",
                "reason": "no prior row for this id (birth row — nothing to preserve)",
                "envelope_drops": []}
    drops = envelope_drops(prior, candidate_row)
    prior_status = prior.get("status")
    cand_status = candidate_row.get("status")
    resurrection = (prior_status in HARD_TERMINAL_STATUSES
                    and cand_status is not None
                    and cand_status != prior_status
                    and cand_status not in HARD_TERMINAL_STATUSES)
    tier_introduction = (cand_tier_kind != "lawful"
                         and cand_tier != prior.get("confidence_tier"))
    if resurrection:
        reason = (f"terminal_state_resurrection: prior row is hard-terminal "
                  f"({prior_status!r}) and the candidate status {cand_status!r} is "
                  f"non-terminal — appending it would resurrect a decided id "
                  f"(write-side terminal valve; the id likely raced a concurrent "
                  f"verdict — drop the advancement and report it)")
    elif drops:
        reason = (f"row drops {len(drops)} envelope field(s) present in the "
                  f"authoritative row — under latest-per-id semantics they would be "
                  f"DELETED, not merged")
    elif tier_introduction:
        reason = (f"confidence_tier_off_enum ({cand_tier_kind}): candidate "
                  f"INTRODUCES an off-enum value the prior row does not carry — "
                  f"{refusal_message(cand_tier, cand_tier_kind)}")
    else:
        reason = "envelope preserved; no terminal resurrection"
        if cand_tier_kind != "lawful":
            reason += (f"; off-enum confidence_tier {cand_tier!r} carried forward "
                       f"unchanged (historical row, disclosed per /review 708 "
                       f"ruling 2)")
    return {
        "mode": "validate_row",
        "cpr_id": cpr_id,
        "prior": {"line": prior_line, "status": prior_status,
                  "field_count": len(prior)},
        "candidate_field_count": len(candidate_row),
        "envelope_drops": drops,
        "terminal_state_resurrection": resurrection,
        "confidence_tier_off_enum": tier_introduction,
        "verdict": "REFUSE" if (drops or resurrection or tier_introduction) else "PASS",
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_set(pairs):
    out = {}
    for item in pairs or []:
        if "=" not in item:
            raise SystemExit(f"--set expects key=value, got {item!r}")
        k, v = item.split("=", 1)
        out[k.strip()] = v
    return out


def _load_gate_advance_module():
    """Load the hyphenated cpr-gate-advance.py from this scripts dir.

    The filename is hyphenated so it cannot be imported by name; resolve it via
    importlib against this file's directory (the cadence-ops convention).
    """
    import importlib.util
    mod_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "cpr-gate-advance.py")
    spec = importlib.util.spec_from_file_location("cpr_gate_advance", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def resolve_recompile_tic(queue_path=None):
    """The canonical current tic, resolved the way the rest of the runtime resolves it.

    REUSED, not reimplemented: `cpr-gate-advance.resolve_current_tic` is the cured
    sibling in this same queue-lifecycle lane — `domain_counter_after` on the LATEST
    tic event, never a raw `type=tic` row count (bk-cpr-extract-tic-count-drift, cured
    tic 554; raw aggregation over-counts and would open every downstream temporal gate
    early). A SECOND tic reader in the queue lane is exactly the counter-disagreement
    shape `Disagreement-as-evidence` names, so this defers to the existing one.

    The audit-logs root is derived from the QUEUE's own location
    (`<audit-logs>/cprs/queue.jsonl` -> `<audit-logs>`) — the same discipline the
    recompile already applies to `--out`: the clock is read beside the queue actually
    being written, not from whatever zone this script happens to sit in.

    Returns an int tic, or None when the tic log is absent/unreadable (the sibling
    signals that as -1) or the helper itself cannot be loaded. NEVER raises: this is a
    derived-cache clock, and a resolution failure must not fail a constitutional write.
    """
    qp = Path(queue_path) if queue_path else default_queue_path()
    if qp is None:
        return None
    try:
        tic = _load_gate_advance_module().resolve_current_tic(qp.parent.parent)
    except Exception:
        return None
    return tic if isinstance(tic, int) and tic > 0 else None


def recompile_effective_state(queue_path=None, current_tic=None):
    """Refresh the derived effective-state projection after a LANDED writeback.

    The projection (audit-logs/cprs/effective-state/, written by the canonical-side
    queue_state_compile.py that lives BESIDE the queue) is a derived cache — queue.jsonl
    stays the sole authority — but the rebuild had NO owner: it went stale by exactly
    one /review pass at every civil audit (tics 690/700/710, third consecutive
    recurrence). This hook makes the mutation boundary the owner (/review 710,
    Architect-ratified F1). Constraints, load-bearing:
      - BEST-EFFORT: a recompile failure is LOUD on stderr but NEVER fails the
        writeback — a derived-cache miss must not block a constitutional write.
      - THE CLOCK IS NOT THE VERDICT (A2-724, cpr-stepper tics 723 + 724, n=2
        consecutive and structurally n=every-stepper-pass). This hook used to key its
        clock on `--review-tic`. But `--review-tic` is a VERDICT field — it merges onto
        the row as `review_tic` — and a cpr-stepper advance must NEVER stamp it (that
        would falsely assert /review docket ownership AND self-fence the row under the
        docket-race write guard). So the stepper lane lawfully omits it and the
        recompile skipped on EVERY stepper write BY CONSTRUCTION: /review 710 made the
        mutation boundary the owner, but the clock key silently exempted one of the two
        writers AT that boundary — the doctrine named it, the runtime enforced it for
        one writer only (conductor-score-runtime parity, field-passthrough-adjacent).
        The clock is now its own argument (`--current-tic`), falling back to
        `--review-tic` (byte-for-byte unchanged for every existing review-execute call
        site) and then to the canonical tic resolved from the tic log.
      - Requires a tic (queue_state_compile --current-tic is required for maturity
        classification); a writeback whose clock cannot be resolved AT ALL skips
        LOUDLY rather than guessing one.
      - civil-engineer's deterministic repair remains the redundant backstop layer.
    """
    clock_source = "explicit"
    if current_tic is None:
        current_tic = resolve_recompile_tic(queue_path)
        clock_source = "resolved-from-tic-log"
    if current_tic is None:
        print("  ⚠⚠ effective-state recompile SKIPPED — no --current-tic/--review-tic on "
              "this writeback AND the canonical tic could not be resolved from "
              "audit-logs/tics/*.jsonl (the compiler requires a tic); the derived "
              "projection is STALE until a tic-bearing rebuild. Cure: re-run "
              "queue_state_compile.py compile --current-tic <N> (backstop: civil).",
              file=sys.stderr)
        return
    qp = Path(queue_path) if queue_path else default_queue_path()
    if qp is None:
        print("  ⚠ effective-state recompile skipped — queue path unresolved; "
              "projection stale until the next rebuild (backstop: civil).", file=sys.stderr)
        return
    compile_script = qp.parent / "queue_state_compile.py"
    if not compile_script.is_file():
        print(f"  ⚠ effective-state recompile skipped — {compile_script} not found; "
              f"projection stale until the next rebuild (backstop: civil).", file=sys.stderr)
        return
    try:
        # --out pinned beside the queue: the compiler's DEFAULT_OUT is
        # Path(__file__)-relative and would follow a relocated/copied script,
        # not the queue actually written. The projection lives with its source.
        res = subprocess.run(
            [sys.executable, str(compile_script), "compile",
             "--queue", str(qp), "--out", str(qp.parent / "effective-state"),
             "--current-tic", str(current_tic)],
            capture_output=True, text=True, timeout=120)
    except Exception as exc:
        print(f"  ⚠ effective-state recompile error — {exc}; projection stale until "
              f"the next rebuild (backstop: civil).", file=sys.stderr)
        return
    if res.returncode != 0:
        detail = (res.stderr or res.stdout or "").strip()[:300]
        print(f"  ⚠ effective-state recompile FAILED rc={res.returncode} — projection "
              f"stale until the next rebuild (backstop: civil): {detail}", file=sys.stderr)
    else:
        print(f"  effective-state projection recompiled at tic {current_tic} "
              f"(clock: {clock_source}; derived cache — queue.jsonl rules)")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Queue Lifecycle Writeback — copy-forward writer for lifecycle-class "
                    "queue.jsonl rows (refuses envelope-stripping thin rows).")
    ap.add_argument("--cpr-id", default=None, help="The CogPR id whose row advances")
    ap.add_argument("--lifecycle-json", default=None,
                    help="Compact JSON object of ONLY the lifecycle fields to set "
                         "(status, review_verdict, pending_class, ...). Typed values "
                         "(ints, floats, bools, lists) survive.")
    ap.add_argument("--set", action="append", dest="set_pairs", default=[],
                    help="key=value lifecycle field (STRING value); repeatable. "
                         "Use --lifecycle-json for typed values.")
    ap.add_argument("--review-tic", type=int, default=None,
                    help="Merged as `review_tic` when the payload does not set it.")
    ap.add_argument("--current-tic", type=int, default=None,
                    help="Clock for the post-write effective-state recompile ONLY. "
                         "NOT merged onto the row — unlike --review-tic, which is a "
                         "VERDICT field. Use this from a lane that must not stamp "
                         "review_tic (cpr-stepper advances). Falls back to "
                         "--review-tic, then to the canonical tic from the tic log. "
                         "(To write the ROW's `current_tic` field, use --set "
                         "current_tic=N / --lifecycle-json; same name, different "
                         "surface.)")
    ap.add_argument("--writer", default=None,
                    help="Calling actor recorded in the lifecycle_writeback stamp "
                         "(e.g. 'review-execute').")
    ap.add_argument("--allow-field", action="append", dest="allow_fields", default=[],
                    help="Explicitly permit an undeclared/protected field (audited "
                         "escape hatch); repeatable.")
    ap.add_argument("--allow-terminal-transition", action="store_true",
                    dest="allow_terminal_transition",
                    help="Explicitly permit a hard-terminal -> non-terminal status "
                         "transition (a reviewed reactivation lane; audited on the "
                         "row). Without it such a row is refused as "
                         "terminal_state_resurrection.")
    ap.add_argument("--queue-path", default=None, help="Override the queue path (test hook)")
    ap.add_argument("--validate-row", default=None,
                    help="READ-ONLY: given a candidate single-line JSON row, report "
                         "whether appending it would strip the envelope (rc=3 if so).")
    ap.add_argument("--emit-only", action="store_true",
                    help="Compose + guard + print the row; do NOT append.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true", dest="output_json")
    args = ap.parse_args(argv)

    if args.validate_row:
        try:
            candidate = json.loads(args.validate_row)
        except json.JSONDecodeError as exc:
            print(f"--validate-row is not valid JSON: {exc}", file=sys.stderr)
            return 2
        res = validate_row(candidate, queue_path=args.queue_path)
        if args.output_json:
            print(json.dumps(res, indent=2))
        else:
            print(f"validate-row {res.get('cpr_id')}: {res['verdict']} — {res['reason']}")
            if res["envelope_drops"]:
                print(f"  dropped: {res['envelope_drops']}")
        return 3 if res["verdict"] == "REFUSE" else 0

    if not args.cpr_id:
        ap.error("--cpr-id is required (or use --validate-row)")

    lifecycle = {}
    if args.lifecycle_json:
        try:
            parsed = json.loads(args.lifecycle_json)
        except json.JSONDecodeError as exc:
            print(f"--lifecycle-json is not valid JSON: {exc}", file=sys.stderr)
            return 2
        if not isinstance(parsed, dict):
            print("--lifecycle-json must be a JSON object", file=sys.stderr)
            return 2
        lifecycle.update(parsed)
    lifecycle.update(_parse_set(args.set_pairs))

    try:
        report = lifecycle_writeback(
            args.cpr_id, lifecycle, queue_path=args.queue_path,
            review_tic=args.review_tic, writer=args.writer,
            allow_fields=args.allow_fields, dry_run=args.dry_run,
            emit_only=args.emit_only,
            allow_terminal_transition=args.allow_terminal_transition)
    except LifecycleWritebackRefused as exc:
        if args.output_json:
            print(json.dumps({"mode": "lifecycle_writeback", "cpr_id": args.cpr_id,
                              "action": "refused", "reasons": exc.reasons}, indent=2))
        else:
            print(f"REFUSED lifecycle writeback for {args.cpr_id}:", file=sys.stderr)
            for r in exc.reasons:
                print(f"  [{r['code']}] {r['message']}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"APPEND FAILED for {args.cpr_id}: {exc}", file=sys.stderr)
        return 1

    s = report["summary"]
    if args.output_json:
        print(json.dumps(report, indent=2))
    elif args.emit_only:
        print(json.dumps(report["row"], separators=(",", ":"), default=str))
    else:
        tag = " (dry-run)" if args.dry_run else ""
        print(f"Lifecycle writeback {report['cpr_id']}{tag}: "
              f"{s['prior_status']} -> {s['new_status']}")
        print(f"  envelope copied forward: {s['copied_forward_fields']} field(s) "
              f"-> {s['field_count_after']} (drops: {len(s['envelope_drops'])})")
        print(f"  mutated: {s['mutated_fields']}")
        if s["added_fields"]:
            print(f"  added:   {s['added_fields']}")
        print(f"  append:  {s['append_via']} (line source: queue line "
              f"{report['prior']['line']})")
    if s["history_field_gap"]:
        print(f"  ⚠ history field gap — {len(s['history_field_gap'])} field(s) present in "
              f"EARLIER rows for this id are absent from the authoritative row "
              f"{s['history_field_gap']}. An earlier writeback stripped the envelope; "
              f"this run preserved the CURRENT one but did not heal the gap (data "
              f"repair is a reviewed lane).", file=sys.stderr)
    if report.get("unparseable_lines_scanned"):
        print(f"  ⚠ {report['unparseable_lines_scanned']} unparseable queue line(s) "
              f"matched this id and were skipped.", file=sys.stderr)
    if not args.dry_run and not args.emit_only:
        # Clock precedence: explicit --current-tic, then --review-tic (so every
        # existing review-execute call site behaves byte-for-byte as before), then
        # resolution from the tic log inside the hook. --current-tic never reaches
        # `lifecycle`, so it cannot stamp the row.
        recompile_effective_state(
            queue_path=args.queue_path,
            current_tic=(args.current_tic if args.current_tic is not None
                         else args.review_tic))
    return 0


if __name__ == "__main__":
    sys.exit(main())
