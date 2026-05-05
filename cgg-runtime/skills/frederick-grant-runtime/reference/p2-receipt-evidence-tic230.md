# P2 Harmony Manifold Input Patch — Receipt Evidence

## Closure statement

P2 — Harmony Manifold Input Patch: **RECEIPT PASS at tic 230.**

The runtime no longer believes `max_volume == manifold_shape` at the input boundary, and the post-patch envelope was observed in a live cycle producing the expected shape-bearing object on the `council.manifold_active` pole.

## Receipt cycle

- Mandate: `tic-230-20260505T101346`
- `harmony_invoke` fired: 2026-05-05T10:24:19Z
- Input file: `audit-logs/harmony/input-tic-230.json`
- Disposition file: `audit-logs/harmony/disposition-tic-230.json`
- Post-patch boundary: tic 230 input produced after CGG commit `b00a964`.

## Three confirmations

1. `manifold_active` child object exists on `council.manifold_active` pole.
2. Pole-level `pressure` is compatibility residue.
3. Shape fields are populated.

Observed shape:

```yaml
active_signal_count: 2
unique_signal_count: 2
volume_max: 30
volume_sum: 55
volume_mean: 27.5
volume_entropy: 0.689
volume_gini: 0.0455
cluster_count: 1
oldest_active_age_tics: 0
newest_active_age_tics: 0
recurrence_count: 0
pressure_scalar_compat: 0.3
```

## Routing consequence

Active Goal #35 closes fully. Active Goal #36, P1 signal projection split, is unblocked and remains operator-paced.

## Compatibility residue

The pole-level pressure scalar remains for unaudited downstream consumers. Hunting consumers that treat it as semantic truth belongs to the P1 implementation lane, not this receipt.
