#!/usr/bin/env python3
"""
Signal active-ray predicate — the single, shared, v2-projection-aware
"is this signal live?" decision (tic 403).

THE STALLED MIGRATION THIS CLOSES
---------------------------------
The P1/P2 signal projection (tic 230) was meant to RETIRE the raw
`status in {active, acknowledged, working}` predicate and replace it with the
v2 projection triple (structural_status / visible_volume / heat) that
manifest-prune.py computes. manifest-prune said so literally: structural_status
"replaces the prior `status in ACTIVE_STATUSES` rule." But the migration
stalled — SEVEN readers kept counting `acknowledged` as active by the raw enum,
while the v2 projection had already cooled silenced rays to heat=0. That
divergence is why a `volume=0 acknowledged` ray (cooled to heat=0, carried for
lineage) still inflated `active_signal_count` and read as hot-path-eligible to
Harmony. This module is the SINGLE OWNER of the predicate so the retirement is
finished once, at the source, for every consumer.

THE PREDICATE
-------------
`acknowledged` is no longer an auto-active status. A ray is ACTIVE (counts
toward active_signal_count / hot-path / docket) iff it carries LIVE TENSION:

  - terminal (resolved | dismissed | superseded)               -> NOT active
  - structurally live (status active|working, or structural_status==live) -> ACTIVE
  - carried | dimmed (the acknowledged projection)             -> ACTIVE iff heat > 0

The discriminator is HEAT, not structural_status: `carried` legitimately spans
a still-pressured ray (heat 0.26) and a silenced one (heat 0.0). Counting all
carried as active re-inflates; dropping all carried wrongly silences a pressured
gap. heat is the only field that separates them.

heat is read from the v2 projection when present; for an un-projected record
(a raw daily-file signal that never passed through manifest-prune) heat is
derived from visible_volume/volume so the predicate is robust on both surfaces.

ANTI-SILENCING (paired law, enforced in manifest-prune.py)
----------------------------------------------------------
Retiring acknowledged-as-active is only half the contract. The dual hazard is
that silence becomes PERMANENT: a ray cooled to heat=0 with no owner would
simply vanish from the docket forever — the inverse of the boot-injection
"fires forever, nothing retires it" SPOF (tic 402). So manifest-prune carries
the re-escalation half: a carried/dimmed ray at heat~=0 with no owner
(resolution_action / scheduled_drill_tic) that stays quiet >= REESC_QUIET_TICS
is re-heated (volume reactivated) and re-enters the docket. Silence is always
temporary until a ray is CARRIED BY DECISION (resolved/dismissed, or an owned
carry), never by decay. This module exports the shared constants/predicate that
half relies on.
"""
from __future__ import annotations

# Reader-side terminal statuses: a ray in any of these is never active.
TERMINAL_STATUSES = frozenset({"resolved", "dismissed", "superseded"})

# Terminal v2 structural states (manifest-prune ARCHIVE set).
TERMINAL_STRUCTURAL = frozenset({"resolved", "superseded"})

# The v2 carry states (the acknowledged projection): kept in the manifest, but
# active ONLY when still hot. dimmed is a decayed carry; both are heat-gated.
CARRY_STRUCTURAL = frozenset({"carried", "dimmed"})

# heat at or below this floor reads as "no live tension" (silenced).
HEAT_FLOOR = 0.01

# Anti-silencing re-escalation knobs (consumed by manifest-prune.py).
REESC_QUIET_TICS = 3      # quiet tics at heat~0 / no owner before re-heat
REESC_VOLUME = 20.0       # volume reactivated on re-escalation (heat ~0.24 carried)


def signal_heat(rec: dict) -> float:
    """Return the ray's heat in [0,1]. Prefer the v2 projection; fall back to
    a compat heat derived from visible_volume/volume for un-projected records."""
    h = rec.get("heat")
    if h is not None:
        try:
            return float(h)
        except (TypeError, ValueError):
            pass
    if rec.get("status", "active") in TERMINAL_STATUSES:
        return 0.0
    vv = rec.get("visible_volume")
    if vv is None:
        vv = rec.get("volume", 0) or 0
    try:
        return min(1.0, max(0.0, float(vv) / 100.0))
    except (TypeError, ValueError):
        return 0.0


def is_active_ray(rec: dict) -> bool:
    """The single shared active-ray predicate (retires the raw acknowledged enum).

    A ray is active iff it carries live tension:
      - terminal           -> False
      - structurally live  -> True   (status active|working or structural_status==live)
      - carried | dimmed   -> True iff heat > HEAT_FLOOR
      - unknown shape       -> heat-gated (prefer over-surface only if hot)
    """
    status = rec.get("status", "active")
    ss = rec.get("structural_status")
    if status in TERMINAL_STATUSES or ss in TERMINAL_STRUCTURAL:
        return False
    if ss == "live" or (ss is None and status in ("active", "working")):
        return True
    if ss in CARRY_STRUCTURAL:
        return signal_heat(rec) > HEAT_FLOOR
    # No structural_status projected and status is acknowledged (or unknown):
    # heat-gate it — an un-projected acknowledged ray is active only if it still
    # carries volume/heat. This is the precise retirement of acknowledged-as-active.
    return signal_heat(rec) > HEAT_FLOOR


def active_rays(records) -> list:
    """Filter an iterable of signal records to the active set."""
    return [r for r in records if is_active_ray(r)]


def latest_per_id(records) -> list:
    """Terminal-valve latest-per-id projection over manifest rows
    (bk-boot-banner-latest-per-id-reader, tic 686).

    The active manifest is append-only BETWEEN prune sweeps — an update/resolve
    appends a NEW row for the same signal, so a reader that counts every row
    counts stale predecessors (the 65/62-vs-57 banner divergence) and can crown
    a resolved row loudest. 'Latest' is input order (file-append order within
    the ONE manifest file = chronological provenance); the key is signal_id
    with id as fallback. Id-less rows cannot be projected and pass through
    unprojected (conservative — never silently dropped). Run is_active_ray on
    the PROJECTED rows, never the raw ones.
    """
    latest = {}
    unkeyed = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        sid = rec.get("signal_id") or rec.get("id")
        if sid:
            latest[sid] = rec
        else:
            unkeyed.append(rec)
    return list(latest.values()) + unkeyed


# ---------------------------------------------------------------------------
# Escalation-attention readers (tic 674, bk-age-unknown-escalation-reader —
# the MOUTH for the t671 anti-silencing canary).
#
# manifest-prune (the producer half of the anti-silencing law above) re-heats
# an unowned silent carried/dimmed ray and stamps `re_escalation_reminder` —
# "a reminder marker the docket can key on" — and renders unknown age as the
# explicit `age_unknown` marker (null is UNKNOWN, never fresh). Until tic 674
# NO reader keyed on either: the re-heat entered the active set via volume/
# heat, but the marker itself was written-never-read. These predicates are the
# reader half; cadence-ops write_conformation is the standing per-downbeat
# consumer (sparse per-signal markers + escalation_attention count).
# ---------------------------------------------------------------------------

def is_reescalated_ray(rec: dict) -> bool:
    """True iff the ray carries the LIVE re-escalation reminder — re-heated by
    the anti-silencing pass this projection cycle because it was silent with no
    owner. Such a ray needs a DECISION (resolve/dismiss, or an owned carry),
    not another decay cycle. Past-cycle provenance (re_escalated_at_tic without
    the reminder) does not count — the docket keys on the live marker."""
    return bool(rec.get("re_escalation_reminder"))


def is_age_unknown_ray(rec: dict) -> bool:
    """True iff the ray's reinforcement age is UNKNOWN. Prefer the projected
    marker (_v2_projection_inputs.age_unknown); for an un-projected record,
    derive it the same way the producer does — no volume_history tic, no
    added_to_manifest_tic, no source_tic. The t671 law this reads for:
    absence of age evidence is never freshness, and on an unowned silent
    carried/dimmed ray an unmeasurable quiet window is escalation-ELIGIBLE."""
    inputs = rec.get("_v2_projection_inputs")
    if isinstance(inputs, dict) and "age_unknown" in inputs:
        return bool(inputs["age_unknown"])
    history = rec.get("volume_history") or []
    if isinstance(history, list) and history:
        latest = history[-1]
        if isinstance(latest, dict) and isinstance(latest.get("tic"), int):
            return False
    return not any(isinstance(rec.get(k), int)
                   for k in ("added_to_manifest_tic", "source_tic"))


def escalation_attention_rays(records) -> list:
    """The re-escalation docket: ACTIVE rays carrying the live reminder marker.
    A subset of the active set, never a parallel state machine — a terminal or
    cooled ray with a stale marker is excluded by the single-owner predicate."""
    return [r for r in records if is_active_ray(r) and is_reescalated_ray(r)]


# ---------------------------------------------------------------------------
# THE READ-TIME JOIN (tic 821) — RULED at /review 820 round 1 Q2, "Join at the
# reader". ONE helper, living beside the predicate, for TWO consumers:
# cpr-enrichment-scanner's signal-correlation arm and ripple-assessor's triad
# window. Two private joins would be two truths.
#
# DOES-NOT-SATISFY RIDER (travels verbatim):
# this increment does NOT touch the manifest-prune engine or any emitter, does NOT change the manifest's row shape, does NOT change what counts as an active signal, and does NOT certify that the enumerated set is the whole consumer set.
#
# THE SHAPE OF THE PROBLEM (MEASURED on the real manifold at tic 821, not assumed):
#   * 0 of 59 active manifest rows carry `subsystem`; 0 of 59 carry `created_at`.
#     A reader that moves its population onto the curated manifest and keeps
#     filtering on either field reads NOTHING, silently, with no error. That is
#     precisely the cure held back at tic 820, and the reason this helper exists.
#   * 59 of 59 active ids DO join some daily emission row; 57 get a `subsystem`
#     from it and 56 get a `created_at`.
#   * The real UNJOINED-by-row set is EMPTY, while 2 ids have a donor row carrying
#     no `subsystem` and 3 have one carrying no `created_at`. A row-wise-only
#     "could I join this id?" declaration therefore declares ZERO on today's
#     manifold while those ids still vanish from a field filter in silence.
#     THE DECLARATION IS FIELD-WISE, never merely row-wise.
#
# MEMBERSHIP IS NOT DECIDED HERE. The ACTIVE SET comes from the curated manifest
# under is_active_ray; the daily rows supply fields and decide nothing. A ray that
# is resolved in the manifest and still reads active in a daily row is NOT active.
# This is a READ-TIME join: it builds no cache, no index and no artifact on disk.
# ---------------------------------------------------------------------------

# Derived/secondary projections are never donors: a curated manifest row and an
# archive row are projections OF the daily corpus, not emissions in it.
DERIVED_SIGNAL_SURFACES = frozenset({"active-manifest.jsonl", "resolved-archive.jsonl"})

# `created_at` asks for the ray's FIRST emission, so it is the MIN of the values
# its donor rows carry -- never the last row by file-sort order. MEASURED reason:
# 17 of 56 joinable ids have first != latest created_at, and one real id
# (sig_2026-04-05_vpl_composite_rollback_gap) carries an EMPTY created_at on its
# file-sort-LAST donor row, so a last-row-wins join loses that ray's age entirely.
FIRST_EMISSION_FIELDS = frozenset({"created_at"})


def join_daily_fields(signals_dir, ids, fields=("subsystem", "created_at")):
    """Join fields the curated manifest does not carry from each ray's OWN daily
    emission row, BY ID. Read-time only.

    `ids` is the ACTIVE SET, already decided by the manifest under is_active_ray.
    This helper never adds to it, never removes from it, and never invents a value.

    Returns a typed result:
      {
        "fields":        {signal_id: {field: value}},  # only fields actually found
        "unjoined":      [signal_id, ...],             # NO donor row at all
        "field_missing": {field: [signal_id, ...]},    # donor row(s) exist, field absent
        "conflicts":     {field: [{"id": …, "values": [...]}, ...]},
        "donor_row_count": {signal_id: int},
      }

    `unjoined` and `field_missing` are DISJOINT: an id with no donor row at all is
    declared exactly once, as unjoined. Both lists are part of the reader's output
    contract -- an id the join cannot complete stays IN the active set and is NAMED,
    never dropped and never given an invented value.
    """
    import json as _json
    from pathlib import Path as _Path

    wanted = list(dict.fromkeys(ids))
    wanted_set = set(wanted)
    fields = tuple(fields)
    donors = {sid: [] for sid in wanted}

    d = _Path(signals_dir)
    if d.exists():
        # File-name order is the daily corpus's chronological provenance (files are
        # date-named, append-only within a day). It orders DONOR ROWS; it never
        # decides a first-emission VALUE -- see FIRST_EMISSION_FIELDS.
        for f in sorted(d.glob("*.jsonl")):
            if f.name in DERIVED_SIGNAL_SURFACES:
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except OSError:
                continue
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = _json.loads(line)
                except _json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict):
                    continue
                sid = rec.get("id") or rec.get("signal_id")
                # The donor row is NOT filtered on type/status: membership was
                # already decided by the manifest, and a donor that "decides
                # nothing" must not re-decide it here by shape.
                if sid in wanted_set:
                    donors[sid].append(rec)

    out_fields = {}
    unjoined = []
    field_missing = {f: [] for f in fields}
    conflicts = {f: [] for f in fields}

    for sid in wanted:
        rows = donors[sid]
        if not rows:
            unjoined.append(sid)
            continue
        got = {}
        for field in fields:
            values = [r.get(field) for r in rows if r.get(field) not in (None, "")]
            if not values:
                field_missing[field].append(sid)
                continue
            distinct = sorted({str(v) for v in values})
            if len(distinct) > 1:
                if field in FIRST_EMISSION_FIELDS:
                    # Not a conflict: several emissions, and the FIRST one is asked for.
                    pass
                else:
                    # The ruling does not say which donor row wins when they differ.
                    # Report it rather than silently picking; measured 0 occurrences
                    # on the real manifold at tic 821.
                    conflicts[field].append({"id": sid, "values": distinct})
            got[field] = min(values) if field in FIRST_EMISSION_FIELDS else values[0]
        if got:
            out_fields[sid] = got

    return {
        "fields": out_fields,
        "unjoined": unjoined,
        "field_missing": field_missing,
        "conflicts": conflicts,
        "donor_row_count": {sid: len(donors[sid]) for sid in wanted},
    }


def joined_field(join_result, signal_id, field, default=None):
    """Read one joined field, or `default` when the join could not supply it.
    Never invents a value -- an absent field is absent, and the id is already
    named in the join result's `unjoined` / `field_missing` declaration."""
    return (join_result.get("fields", {}).get(signal_id) or {}).get(field, default)
