#!/usr/bin/env python3
"""Single-owner steppable predicate for the CPR-STEP lane marker.

Covenant: cpr_step_lane_marker_per_id_maturity_tic655 (admitted /review 655;
artifact audit-logs/governance/cpr-step-lane-marker-covenant-tic655.md).

The SessionStart CPR-STEP marker (session-restore.sh, writer of
audit-logs/hooks/cpr-step-lane-seen.json) previously computed the steppable
count as an AGGREGATE over extracted/tic_gated rows, without per-id
tic-maturity. Lived defect (tic 620): the marker said 2 steppable when the
honest per-id set was 1 — one extracted row matured only at 621. The boot
injection eats the marker count to shape stepper dispatch, so the over-count
shaped dispatch decisions.

This module is the single owner of the honest predicate — the same maturity
law the cpr-stepper agent itself derives (cpr-stepper.md lifecycle table +
provenance-class maturity key, enrichment-ontology spec §2):

  - `tic_gated`  → steppable (in-transit: the deterministic reconciler
    cpr-gate-advance.py owns the next step; maturity was already enforced at
    the prior extracted→tic_gated gate and is NOT re-checked here).
  - `extracted`  → steppable iff the row's own temporal gate passes at
    marker-write time:
      provenance_class == construction_authoritative → maturity waived
        (maturity_tics effectively 0);
      else (friction_born, or field absent — legacy rows) →
        current_tic - birth_tic >= maturity_tics (per-row override honored;
        default 3).
  - anything else → not steppable.

Fail-visible choices (surface-don't-hide — a silently hidden row starves the
lane; the stepper is the intelligent seat that resolves oddities):
  - extracted row with no derivable birth_tic → counted steppable;
  - clock failure (current_tic unknown/non-positive) → count_steppable falls
    back to the aggregate legacy count (maturity cannot be derived without
    the tic authority; hiding the whole lane on a clock fault would silently
    starve dispatch).

session-restore.sh imports this module when path-reachable and otherwise runs
a faithful embedded replica (same pattern as signal_active.py) — keep the
replica in lockstep with this file.
"""

DEFAULT_MATURITY_TICS = 3
STEPPABLE_STATUSES = ("extracted", "tic_gated")


def is_steppable(entry, current_tic):
    """Honest per-id steppable predicate at marker-write time."""
    status = entry.get("status", "")
    if status == "tic_gated":
        return True
    if status != "extracted":
        return False
    if entry.get("provenance_class") == "construction_authoritative":
        return True
    birth = entry.get("birth_tic")
    if not isinstance(birth, int):
        return True  # fail-visible: no derivable birth position
    try:
        maturity = int(entry.get("maturity_tics", DEFAULT_MATURITY_TICS))
    except (TypeError, ValueError):
        maturity = DEFAULT_MATURITY_TICS
    return (current_tic - birth) >= maturity


def count_steppable(entries, current_tic):
    """Count honest steppable rows over a latest-entry-per-id projection.

    entries: dict id -> latest row. current_tic: the hook's tic authority.
    Clock-fault arm: current_tic unknown/non-positive → legacy aggregate.
    """
    if not isinstance(current_tic, int) or current_tic <= 0:
        return sum(
            1 for e in entries.values()
            if e.get("status", "") in STEPPABLE_STATUSES
        )
    return sum(1 for e in entries.values() if is_steppable(e, current_tic))
