# P1 Signal Projection Split — Receipt Evidence

> Canonical source: `audit-logs/governance/p1-signal-projection-split-receipt-tic230.md`. Embedded copy for skill self-containment.

## Closure statement

P1 — Signal Projection Split: **RECEIPT PASS at tic 230.**

The first runtime consumer that collapsed signal truth into raw `status` and signal attention into raw `volume` has been patched. The runtime no longer believes:

- `status` is evidence (the projection now derives `structural_status` from status + governance touch + dependency state)
- `volume` is truth (the projection now derives `visible_volume` from raw volume + reinforcement age + blocking dependency + recurrence)

A new field `heat` mediates between structural truth and current operational attention, satisfying the v2 thermal §11.5 substitution map.

## Patch surface

- File: `canonical_developer/context-grapple-gun/cgg-runtime/scripts/manifest-prune.py`
- CGG commit: `6345228`
- Source diff: 132 → 335 lines (+203 / −2)
- Install diff: byte-identical post sync (`runtime-sync.py sync` → `[SYNCED] script:manifest-prune`)

## Substitution map applied (Thermal TTL §11.5)

```text
status → structural_status + visible_volume
(new) → heat (mediator)
```

Implemented as `project_signal(rec, current_tic) -> dict` returning the v2 triple plus provenance metadata. Legacy `status` and `volume` remain on every kept record as compatibility residue (P2 hard non-solution pattern).

## Three Architect fixtures — result table

| # | Fixture | Raw inputs | Projected output | Pass |
|---|---|---|---|---|
| 1 | Foreman projected signal (`economy_fetch_failed` ack) | status=acknowledged, volume=30, age=8, no resolution | structural_status=**carried**, visible_volume=**18.0**, heat=**0.216** | ✓ carried (not falsely resolved); visible dimmed gracefully |
| 2 | transient drift post-sync (synthetic) | status=resolved, volume=18 | structural_status=**resolved**, visible_volume=**0.0**, heat=**0.0** | ✓ resolved; archived; no status residue |
| 3 | rollback gap (`vpl_composite_rollback_gap`) | status=acknowledged, volume=25, age=99, scheduled_drill_tic=160 | structural_status=**carried**, visible_volume=**19.69**, heat=**0.2599** | ✓ carried; visible_volume preserved (~79% of raw) by blocking-dep boost |

## Closeout proofs

- **No live signal is resolved by render cooling**: low visible_volume does NOT downgrade structural_status to `resolved`. ✓
- **No resolved signal remains hot by status residue**: status=resolved + high raw volume → visible_volume=0, heat=0. ✓

## structural_status derivation

```text
resolved | dismissed         → resolved   (archive-bound)
superseded                   → superseded (archive-bound)
acknowledged                 → carried    (governance-captured)
active | working             → live       (currently active)
carried + visible<55% of raw → dimmed     (structural carry + decayed attention)
```

## Provisional markers

The projection is provisional until thermal_weight_v2 §11 inputs are wired:

- `tic_mass` — defaulted 1.0
- `slice_density` — defaulted 1.0
- `class_prior` — defaulted 1.0
- `weighted_age_tics` — provisional from `raw_age_tics * 1.0`
- `owner_status` — defaulted

Each projected record carries `_v2_projection_inputs.defaulted` enumerating the gap. Refining is P3/P4 work (parked).

## Routing consequence

Active Goal #36 closes at the projection-seam boundary. Downstream surfaces (signal_scan, bench-packet-prep, harmony-input-builder, /siren, statusline) now see structural_status / visible_volume / heat ride-along fields and may begin consuming them. Existing readers that key on legacy status / volume continue to work via compat residue.

## Frederick's treatment

Frederick reads P1 as the second probity-class patch in a single-tic pair (after P2 sealed the Harmony input boundary). The pattern is now established: doctrine names what runtime is forbidden to believe; the first consumer that still believes the scalar is patched; receipt-proven; committed narrowly. Two patches inside one tic, no sprawl.

The spine line, paired with P2's: *P2 made manifold shape real to Harmony. P1 makes signal truth legible without lying about heat.*
