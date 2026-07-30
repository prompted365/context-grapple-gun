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
