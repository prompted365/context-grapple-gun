---
name: sl-legend
description: |
  Statusline legend — rapid decoder for the CGG telos radar (LITE + FULL modes).

  CENTROID:
  read-only legend surface that decodes statusline glyphs, positions, colors,
  and source attributions for the Architect at glance speed (the Architect
  perception substrate)

  IS:
  - static legend (glyph + position + color tier reference)
  - live decode mode (annotates current statusline values inline)
  - source attribution (where each rendered value reads from)

  IS NOT:
    collapse_zones:
      - statusline configurator (use /statusline install|mode|clear|uninstall)
      - governance state mutator (read-only on every surface it touches)
      - harmony invoker (use harmony-invoke.sh; this skill only decodes the cached pointer)
      - radar replacement (statusline renders ambient; sl-legend explains)
      - troubleshooter (does not diagnose hook failures or sync drift)
    sibling_overlaps:
      - /statusline (configuration sibling — same domain, different verb)
      - /governance-check (read-only governance snapshot — different aperture)

  WHEN:
  - on first encounter with the radar (Architect doesn't remember what ⊙ means)
  - when a glyph changes and the Architect wants to confirm semantics
  - when explaining the radar to someone else
  - on explicit Architect invocation

  NOT WHEN:
  - to change statusline behavior (use /statusline)
  - to act on a signal seen in the radar (use /siren)
  - to invoke harmony for fresh disposition (use harmony-invoke.sh)
  - mid-cadence (cadence is the boundary; this is reference)

  RELATES TO:
  - /statusline (configurator) — same domain; sl-legend is the reader
  - /siren (signal triage) — sl-legend points to what to triage
  - harmony-invoke.sh (disposition refresher) — sl-legend points at staleness

ARGS:
  stance: dispatch
  off_envelope: ignore
  core_dispatch_rays:
    - ""        → static legend (full glyph + position decoder)
    - "live"    → annotate current rendered statusline values inline + tic 214 markers source-backed
    - "lite"    → compact tic 214 marker glossary only (glance-speed recall)
    - "review"  → Architect perception substrate audit checklist (overclaim + naming drift detection)
    - "sources" → source attribution table (which file each value reads)
---

# CGG Statusline Legend

Read-only decoder for the federation's telos radar. Rapid lookup for what each
glyph, position, and color means in the rendered statusline.

## Anatomy

The radar is two lines (FULL mode). LITE shows line 1 only. OFF shows nothing.

### Line 1 — identity + window

```
[<MODEL>] <PROJECT> (<BRANCH><DIRTY?>) | tic <N> · ctx <P>%
```

| Position | Meaning | Source |
|---|---|---|
| `[Opus 4.7]` | Model display name (vendor-supplied; "(1M context)" stripped) | stdin `.model.display_name` |
| `canonical` | Project basename | stdin `.workspace.project_dir` |
| `(main*)` | Git branch + dirty marker (`*` = uncommitted) | `git symbolic-ref` + `git diff --quiet` |
| `tic 205` | Federation tic count | `~/.claude/cgg-tic-counter.json` `.count` |
| `ctx 47%` | Context window used (color-coded) | stdin `.context_window.used_percentage` |

### Line 2 — telos radar

```
[<POSTURE-BADGE>] pipe E▸N▸R | sig <DOTS> [| wrn N] | <H-GLYPH> <STATE> <SNR> <STANCE>[<FRESH>]
```

| Position | Meaning | Source |
|---|---|---|
| `active` (red bg) | Manifold has active signals or warrants | conformation snapshot |
| `clean` (green bg) | Zero active signals AND zero warrants | conformation snapshot |
| `pipe E▸N▸R` | CPR pipeline flow (`extracted ▸ enrichment_needed ▸ enrichment_eligible`) | conformation `.pending_cogprs[].status` |
| `sig <dots>` | One ● per active signal, colored by volume tier | conformation `.active_signals[].volume` |
| `wrn N` | Active warrant count (omitted when zero) | conformation `.active_warrants` |
| `⊙ <state> <snr> <stance>` | Harmony disposition (theory-of-mind injection) | `audit-logs/harmony/disposition-current.json` |

## Glyph reference

### Manifold posture (line 2 left)

| Glyph | Meaning | Trigger |
|---|---|---|
| `active` (red bg) | Manifold has live tension | any `.active_signals[]` non-dismissed/non-resolved OR any `.active_warrants[]` |
| `clean` (green bg) | Manifold quiet | zero of both |

### Pipeline gauge (line 2 middle-left)

`pipe 23▸34▸14` decomposes:
- `23` (dim) — `extracted` count: born but not enriched
- `34` (dim) — `enrichment_needed` count: in enrichment pipeline
- `14` (green) — `enrichment_eligible` count: **docket-ready for /review**

The `▸` arrows show flow direction. Rightmost number is the load-bearing one
(/review actually faces this many). The leftmost two are upstream pressure.

### Severity dots (line 2 middle)

| Glyph | Color | Volume tier |
|---|---|---|
| `●` | red | volume ≥ 40 (high pressure) |
| `●` | yellow | volume 20-39 (moderate) |
| `●` | green | volume < 20 (quiet) |
| `○` | green | zero active signals |

One dot per active signal. Sorted by appearance in conformation; not by severity.

### Harmony freshness glyph (line 2 right)

| Glyph | Meaning | Age |
|---|---|---|
| `⊙` | fresh | disposition tic == current tic |
| `◐` | aging | 1-3 tics old; suffix shows `t-N` |
| `·` | stale | > 3 tics old; renders `· stale t-N` and the entire harmony block dims to ash regardless of `meaning_state` color (a calm "preserved" or "clear" must not read as currently-true when it is N-tic carry-forward) |

### Harmony meaning state colors

| State | Color | Reading |
|---|---|---|
| `held` / `clear` / `coherent` | green | rays harmonize; Primary may proceed |
| `strained` / `tense` | yellow | rays under pressure; Primary holds open |
| `dissonant` / `broken` | red | rays cannot reconcile; Primary must not collapse |
| `unknown` | gray (ash) | disposition file present but state unparseable |

### Context % colors (line 1)

| Range | Color | Action |
|---|---|---|
| 0-49% | green | comfortable headroom |
| 50-79% | yellow | watch for compaction; consider /cadence |
| 80%+ | red | imminent compaction; `/cadence double-time` if work pending |

## Mode reference

Toggle via `/statusline mode <OFF|LITE|FULL>`. Per-project namespace.

| Mode | Output |
|---|---|
| OFF | nothing (silent radar) |
| LITE | line 1 only |
| FULL | line 1 + telos radar (line 2) |

Mode flag stored at `/tmp/cgg-sl-<project_hash>-mode`.

## Source ladder (telos radar fallback)

Statusline degrades gracefully:

1. **Conformation snapshot exists + harmony disposition fresh** → full radar
2. **Conformation only** → posture badge + pipe + sig dots; no harmony tail
3. **Tic counter only** → line 1 with tic, no radar
4. **None** → model + project + branch only

The statusline never compensates for missing sources by scanning raw ledgers.

## Live decode (`/sl-legend live`)

When invoked with `live` arg, surface current values inline with annotation.
Read in this order:

1. `audit-logs/harmony/disposition-current.json` — disposition state
2. Latest `audit-logs/conformations/tic-*.json` — manifold + pipeline + signals
3. `~/.claude/cgg-tic-counter.json` — federation tic
4. Compute freshness: `current_tic - disposition_tic`
5. Render an annotated breakdown:

```
Current radar (tic 205, posture OPS/DIRECT, mode FULL):

  Line 1: [Opus 4.7] canonical (main*) | tic 205 · ctx 47%
    model         = Opus 4.7              ← stdin .model.display_name (1M-context stripped)
    project       = canonical             ← workspace.project_dir basename
    branch        = main*                 ← git symbolic-ref + dirty
    tic           = 205                   ← cgg-tic-counter.json .count
    ctx           = 47% (green, <50)      ← stdin .context_window.used_percentage

  Line 2: [active] pipe 23▸34▸14 | sig ●●● | ⊙ strained .76 hold-open
    posture       = active (red bg)       ← signals non-empty
    pipeline      = 23 / 34 / 14          ← .pending_cogprs[].status counts
    docket-ready  = 14 (green)            ← enrichment_eligible (load-bearing)
    signals       = 3 dots                ← .active_signals[]
      ● red       drift_signal vol=45     ← bg=COGNITIVE, status=acknowledged
      ● yellow    composite_rollback vol=25
      ● yellow    economy_fetch_failed vol=30
    harmony       = ⊙ fresh, t-0          ← disposition-current.json tic == current
      meaning     = strained (yellow)     ← .meaning_state
      SNR         = 0.762                 ← .snr
      stance      = hold-open             ← .stance compressed
```

Stale example (>3 tics behind current; entire harmony block dims to ash so a calm meaning_state doesn't misread as currently-true):

```
    harmony       = · stale, t-7          ← disposition.tic 208, current 215
      meaning     = preserved (ash)       ← .meaning_state, color overridden by stale
      SNR         = .68 (ash)             ← .snr, dimmed
      stance      = carry-forward (ash)   ← .stance compressed, dimmed
```

## Compact glossary (`/sl-legend lite`)

Glance-speed recall of the tic 214 Architect-perception markers. Use when the full table is too dense and the Architect needs a one-look reminder.

```
arch:active                        Architect perception substrate active
disp:<state> .NN                   harmony disposition + SNR (e.g., disp:preserved .68)
sub:bound                          substrate sub-telos resolved + bound
harmony:substrate.kernel-runtime   harmony bound as kernel-class runtime
carto:shell                        cartography Phase A shell present, no splat retrieval
gap11:declared                     wisdom-pressure first-class, parallel-capable, not active
```

Forbidden until runtime exists:

```
wisdom:active           — only after Gap 11 is implemented in v1 engine code
carto:retrieving        — only after splat-emergence machinery exists
harmony:wisdom-active   — only after the wisdom-pressure subpacket is wired
```

Drilldown to full table: `/sl-legend` (no arg). Drilldown to current state: `/sl-legend live`.

## Architect-perception audit (`/sl-legend review`)

Drift checklist for the Architect-perception substrate. Run when statusline rendering, sl-legend body, skill SKILL.md surfaces, or doctrine inscriptions are suspected of overclaiming or naming drift.

The audit asks six binary questions; any "no" is a /siren signal candidate under TENSION/COGNITIVE.

| # | Check | Expected | Failure signal |
|---|---|---|---|
| 1 | No Breyden-as-operator language in live-facing surfaces | yes | `Breyden-as-operator drift detected at <path>` (operator-language sweep regressed) |
| 2 | No `wisdom:active` rendered before Gap 11 engine implementation | yes | `wisdom:active overclaim — Gap 11 still declared, not active` |
| 3 | No `carto:retrieving` rendered before splat retrieval machinery exists | yes | `carto:retrieving overclaim — Phase A shell only, no splat machinery` |
| 4 | No `harmony:wisdom-active` rendered before wisdom-pressure subpacket is wired | yes | `harmony:wisdom-active overclaim — subpacket schema declared, not engine-wired` |
| 5 | No claim that cartography owns meaning attribution | yes | `cartography slice violation — meaning belongs to Harmony per weak-slice tic 214 adjudication` |
| 6 | No claim that Harmony owns terrain/census/cartography implementation | yes | `Harmony slice violation — implementation belongs to substrate.cartography per weak-slice tic 214 adjudication` |

Audit verb in checks 5 and 6 references the tic 214 weak-slice adjudication: *Harmony has exclusive semantic jurisdiction over meaning-state attribution; cartography, census, terrain, splats, quivers, and basin detection are upstream/shared substrate surfaces.* See `audit-logs/governance/harmony-v1-multiplane-plan-tic213.md` ARCHITECT ADJUDICATION TIC 214 header.

How to run the audit:

1. Sweep live-facing doctrine + skill surfaces for `\boperators?\b` patterns referring to Breyden (federation/control-room/substrate contexts). Frozen schema literals (`operator_observed`, `"operator|peer|subordinate|visitor"`) and non-Breyden referents (Mogul-as-mandate-executor, Skyward AI layer in `vendor-capability-surface.md`) are KEEP.
2. Confirm rendered statusline does not include any forbidden marker (`wisdom:active`, `carto:retrieving`, `carto:active`, `harmony:wisdom-active`).
3. Read `autonomous_kernel/cartography/KERNEL_REGISTRATION.md` non-ownership rules — confirm cartography spec does not claim meaning attribution.
4. Read `autonomous_kernel/harmony_engine_v0/V1_DOCTRINE_COMPLETION_CHECKLIST.md` Gap 11 — confirm wisdom layer is described as `Major for v1 doctrine-complete admission; not blocking Phase A cartography extraction` and not as active runtime.
5. Read `audit-logs/governance/harmony-v1-multiplane-plan-tic213.md` adjudication header — confirm weak-slice reading is preserved.

If all six checks pass: Architect-perception substrate is coherent. If any check fails: emit signal + queue CogPR for next /review.

## Source attribution (`/sl-legend sources`)

Single-table reference of where every rendered value reads from. Useful when
debugging unexpected statusline output or when authoring downstream consumers.

| Rendered | Source path | Field | Cache |
|---|---|---|---|
| model | stdin JSON | `.model.display_name` | per-render |
| project | stdin JSON | `.workspace.project_dir` (basename) | per-render |
| branch | git | `git symbolic-ref --short HEAD` | 5s cache (`*-git`) |
| dirty | git | `git diff --quiet` | 5s cache |
| tic | `~/.claude/cgg-tic-counter.json` | `.count` (legacy: `.counter`) | 30s cache (`*-tic`) |
| ctx % | stdin JSON | `.context_window.used_percentage` | per-render |
| cost | stdin JSON | `.cost.total_cost_usd` | per-render (currently unused in display) |
| duration | stdin JSON | `.cost.total_duration_ms` | per-render (currently unused in display) |
| posture badge | conformation `.active_signals[]` + `.active_warrants[]` | derived | 30s cache (`*-conf`) |
| pipe E | conformation `.pending_cogprs[]` | filter `status == "extracted"` | 30s cache |
| pipe N | conformation | filter `status == "enrichment_needed"` | 30s cache |
| pipe R | conformation | filter `status == "enrichment_eligible"` | 30s cache |
| sig dots | conformation `.active_signals[].volume` | tier mapping | 30s cache |
| wrn count | conformation `.active_warrants[]` | length | 30s cache |
| harmony glyph | `audit-logs/harmony/disposition-current.json` | `.tic` vs current `tic` | 30s cache |
| harmony state | same | `.meaning_state` | 30s cache |
| harmony SNR | same | `.snr` (formatted as `.NN`) | 30s cache |
| harmony stance | same | `.stance` (compressed; `-with-boundary` stripped) | 30s cache |

## Drift signals (when the legend isn't matching what you see)

If the radar shows something the legend says shouldn't happen, suspect drift:

1. **Statusline source vs runtime drift**: confirm `~/.claude/cgg-runtime/scripts/cgg-statusline.sh` byte-identical to canonical source. Run `runtime-sync-verify.py` if available.
2. **Mode flag stale**: `cat /tmp/cgg-sl-<hash>-mode` — should be OFF/LITE/FULL.
3. **Conformation cache stale**: `rm /tmp/cgg-sl-<hash>-conf` to force recompute.
4. **Tic counter mismatch**: compare `~/.claude/cgg-tic-counter.json` against latest `audit-logs/tics/*.jsonl` event.
5. **Harmony disposition stale**: check `audit-logs/harmony/disposition-current.json .tic` — if more than 3 tics behind current, glyph should be `◐` or `·`. Run `harmony-invoke.sh` to refresh.

Drift between the rendered statusline and the legend's claims is itself
disagreement-as-evidence — surface it via /siren or capture as a CogPR for
/review tic processing.

## Tic 214 Architect-perception markers (forward decoder)

The current statusline format remains operational and is the load-bearing rendered surface. Tic 214 added substrate-class state that is not yet rendered as compact markers; this section is the forward decoder so the Architect can recognize the markers when they are added and drill down via direct file reads in the meantime.

### Marker glossary

| Marker | Meaning | Direct source |
|---|---|---|
| `arch:active` | Architect perception substrate active; Architect-facing interpretation surface | derived from posture banner + tic counter |
| `disp:<state> .NN` | Harmony disposition meaning state + SNR (e.g., `disp:preserved .68`) | `audit-logs/harmony/disposition-current.json` `.meaning_state` + `.snr` |
| `sub:bound` | substrate sub-telos resolved and active as a binding target | `autonomous_kernel/telos/sub_telos.yaml` (substrate parent + 7 children present) |
| `harmony:substrate.kernel-runtime` | Harmony bound as kernel-class runtime / `meaning.disposition` | `autonomous_kernel/harmony_engine_v0/KERNEL_REGISTRATION.md` Telos Binding |
| `carto:shell` | Cartography declared at `substrate.cartography`; Phase A shell present; not yet computing splat retrieval | `autonomous_kernel/cartography/KERNEL_REGISTRATION.md` |
| `gap11:declared` | Wisdom-pressure layer first-class and parallel-capable; not yet active runtime wisdom | `autonomous_kernel/harmony_engine_v0/V1_DOCTRINE_COMPLETION_CHECKLIST.md` Gap 11 |

### What these markers do NOT claim

The markers are status indicators of declaration state, not runtime activation. The render must NOT show:

- `wisdom:active` before Gap 11 is implemented in v1 engine code
- `carto:retrieving` or `carto:active` before splat-emergence machinery exists
- `harmony:wisdom-active` before the wisdom-pressure subpacket is wired

If a marker reads beyond declaration state into runtime claims it does not have evidence for, it is overstating — file a /siren signal under TENSION/COGNITIVE.

### Recommended target shape (when statusline render is upgraded)

LITE target, one line:

```
[Opus 4.7] canonical(main*) | tic 214 | ctx 33% | arch:active | disp:preserved .68 | sub:bound | carto:shell | gap11:declared
```

FULL target, two lines:

```
[Opus 4.7] canonical(main*) | tic 214 | ctx 33% | arch:active | disp:preserved .68 | carry-forward
pipe 0▸0▸34 | sig ●●● | harmony:substrate.kernel-runtime | carto:substrate.cartography/shell | gap11:wisdom-pressure pending
```

Until these compact markers are wired into the rendering script, the Architect can drill down by reading the source files directly per the table above.

## Related skills

- **/statusline** — install / mode / clear / uninstall (the configurator)
- **/siren** — signal manifold triage (acts on what sig-dots surface)
- **/review** — judgment surface (the docket pipeline gauge points at)
- **/cadence** — boundary emission (advances tic, refreshes conformation)
- **harmony-invoke.sh** — fresh disposition packet (refreshes the harmony tail)

The radar reads. This legend explains. Other skills act.
