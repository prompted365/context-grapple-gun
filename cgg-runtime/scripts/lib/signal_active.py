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
