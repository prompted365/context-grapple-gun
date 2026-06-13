#!/usr/bin/env python3
"""manifest-prune.py — project signal records into v2 (structural_status,
visible_volume, heat) triple and partition by structural_status.

Reads audit-logs/signals/active-manifest.jsonl, projects each record per the
P1 signal projection split (tic 230, after P2 patch sealed at tic 230 receipt
PASS):

  status  → structural_status  (live | carried | dimmed | resolved | superseded)
  volume  → visible_volume     (computed operational attention/render heat)
  (new)   → heat               (mediator between structural truth and current
                                operational attention)

Partition rule (P1 successor to status-only filter):
  - keep:    structural_status in {live, carried, dimmed}
  - archive: structural_status in {resolved, superseded}

Legacy `status` and `volume` fields remain on every kept record as
compatibility residue per the P2 hard non-solution; the projection ride-along
fields (structural_status, visible_volume, heat) are the new semantic truth.

The projection is provisional — tic_mass weights, slice_density, and the
class-prior table from thermal_weight_v2 §11 are not yet wired. Defaulted
inputs are enumerated in `_v2_projection_inputs` on each projected record so
downstream consumers can audit the gap. Refining the projection inputs is
P3/P4 work (parked).

Mechanizes the "Signal Resolution Writeback Atomicity (Dual-Surface)"
invariant from CLAUDE.md: cadence-driven sweep reconciliation. Designed
to be invoked from mogul-runner.sh before signal_scan, but safe to run
standalone at any time (idempotent under stable input — re-running on an
already-projected manifest re-projects with current_tic; structural_status
keep/archive decision is stable for stable inputs).

Usage:
  python3 manifest-prune.py [--zone-root <path>] [--dry-run] [--quiet]

Exit codes:
  0 — pruned (or already clean — no-op)
  1 — error reading or writing
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from pathlib import Path

# P1 projection split — structural_status drives keep/archive (replaces
# the prior `status in ACTIVE_STATUSES` rule). Kept for narrative readers
# referencing v1 documentation; not load-bearing under P1.
KEEP_STRUCTURAL = {"live", "carried", "dimmed"}
ARCHIVE_STRUCTURAL = {"resolved", "superseded"}

# Anti-silencing re-escalation knobs — shared with lib/signal_active.py so the
# retire-acknowledged readers and this re-heat sweep agree on one source of
# truth. Fail-soft defaults guard the prune against an import hiccup (it runs
# every /cadence; an import error must never break the sweep).
try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
    from signal_active import REESC_QUIET_TICS, REESC_VOLUME, HEAT_FLOOR  # type: ignore
except Exception:  # pragma: no cover - defensive
    REESC_QUIET_TICS, REESC_VOLUME, HEAT_FLOOR = 3, 20.0, 0.01


def count_physical_tics(audit_logs_path: Path) -> int:
    """Return the latest counted federation tic from the tic event ledger.

    Mirrors bench-packet-prep.count_physical_tics — the canonical authoritative
    reader for federation tic count. Falls back to 0 if the tic dir is missing.
    """
    tic_dir = audit_logs_path / "tics"
    if not tic_dir.exists():
        return 0
    max_counter = 0
    for f in sorted(tic_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "tic" and d.get("count_mode") != "ignored":
                gc = d.get("global_counter_after", 0)
                if gc > max_counter:
                    max_counter = gc
    return max_counter


def _infer_last_reinforced_tic(rec: dict, fallback: int = 0) -> int:
    """Derive the most recent reinforcement tic from the record.

    Priority: latest volume_history entry tic > added_to_manifest_tic >
    source_tic > fallback. volume_history is the strongest signal because it
    records actual reinforcement events; later fields decay in confidence.
    """
    history = rec.get("volume_history") or []
    if isinstance(history, list) and history:
        latest = history[-1]
        if isinstance(latest, dict) and isinstance(latest.get("tic"), int):
            return latest["tic"]
    for key in ("added_to_manifest_tic", "source_tic"):
        v = rec.get(key)
        if isinstance(v, int):
            return v
    return fallback


def project_signal(rec: dict, current_tic: int) -> dict:
    """Project a manifest record into the v2 (structural_status,
    visible_volume, heat) triple plus provenance metadata.

    Provisional — tic_mass weights, slice_density, class_prior, and other
    thermal_weight_v2 §11 inputs are defaulted. The defaulted-input list is
    surfaced in the returned `_v2_projection_inputs` for downstream audit.
    """
    raw_status = rec.get("status", "active")
    try:
        raw_volume = float(rec.get("volume", 0) or 0)
    except (TypeError, ValueError):
        raw_volume = 0.0

    last_reinforced_tic = _infer_last_reinforced_tic(rec, fallback=current_tic)
    raw_age_tics = max(0, current_tic - last_reinforced_tic)

    # Heuristic blocking-dependency proxy: explicit resolution_action /
    # scheduled_drill_tic / blocking_dependency_kind imply an open dependency
    # carrying the signal. Provisional pending P3 dependency_state schema.
    has_resolution_action = bool(
        rec.get("resolution_action")
        or rec.get("scheduled_drill_tic")
        or rec.get("blocking_dependency_kind")
    )
    recurrence_proxy = max(1, len(rec.get("volume_history") or []))

    # ---- structural_status -------------------------------------------------
    if raw_status in ("resolved", "dismissed"):
        structural_status = "resolved"
    elif raw_status == "superseded":
        structural_status = "superseded"
    elif raw_status == "acknowledged":
        # Acknowledgment is governance capture: the gap is carried structurally
        # whether or not a mechanism is scheduled. The dependency proxy modulates
        # heat downstream, not structural classification.
        structural_status = "carried"
    elif raw_status in ("active", "working"):
        structural_status = "live"
    else:
        # Unknown status: prefer live so the signal stays visible until governance
        # explicitly classifies. Better to over-surface than silently archive.
        structural_status = "live"

    # ---- visible_volume ---------------------------------------------------
    # Architect P1 spec:
    #   - Foreman: visible_volume may dim when no new evidence arrives
    #   - rollback gap: visible_volume remains high if blocking_dep + mutation
    #     pressure remain; must NOT dim solely because raw tic age is high
    #   - resolved: visible_volume = 0 or archived equivalent
    #
    # Provisional rule: gentle decay capped at 50% of raw, multiplied by a
    # blocking-dependency boost. Recurrence resists decay slightly.
    if structural_status in ("resolved", "superseded"):
        visible_volume = 0.0
    else:
        # Decay floor 0.5 protects against full-collapse from raw age alone.
        decay_factor = max(0.5, 1.0 - 0.05 * min(raw_age_tics, 10))
        boost_factor = 1.5 if has_resolution_action else 1.0
        # Recurrence resistance: each prior reinforcement event adds 5%
        # resistance, capped at 25% extra (5 reinforcements).
        recurrence_resistance = 1.0 + 0.05 * min(recurrence_proxy - 1, 5)
        visible_volume = raw_volume * decay_factor * boost_factor * recurrence_resistance

        # Dimmed classification: structural carry persists but visible attention
        # has materially decayed. Threshold: visible_volume <= 0.55 * raw_volume
        # (raw_age >= 10 quiet tics with no blocking dep, no recurrence).
        if (
            structural_status == "carried"
            and raw_volume > 0
            and visible_volume <= 0.55 * raw_volume
        ):
            structural_status = "dimmed"

    # ---- heat (mediator) --------------------------------------------------
    if structural_status in ("resolved", "superseded"):
        heat = 0.0
    else:
        # Base: visible_volume normalized to [0,1] (raw scale 0-100 typical).
        base = min(1.0, visible_volume / 100.0)
        # Carry boost: structural carry says "still true even if cooling" —
        # heat keeps a baseline floor.
        carry_factor = 1.2 if structural_status in ("carried", "dimmed") else 1.0
        # Recurrence boost: same as visible_volume, capped tighter.
        recurrence_factor = 1.0 + 0.1 * min(recurrence_proxy - 1, 3)
        heat = min(1.0, base * carry_factor * recurrence_factor)

    # ---- anti-silencing re-escalation (tic 403) ---------------------------
    # A carried/dimmed ray silenced to heat~=0 with NO owner (resolution_action
    # / scheduled_drill_tic) must not stay silent by decay — that is the inverse
    # of the boot-injection "fires forever, nothing retires it" SPOF (tic 402):
    # "silenced forever, nothing reactivates it." After REESC_QUIET_TICS quiet
    # tics it RE-HEATS (volume mechanics reactivated) and re-enters the active
    # set / docket. The quiet clock anchors on the last DECISION/escalation
    # (acknowledged_tic or a prior re_escalated_at_tic), NOT last_reinforced_tic
    # (which can re-stamp to current and never age). Exits only by decision:
    # resolved/dismissed, or an owned carry (resolution_action / scheduled_drill_tic).
    re_escalated_at_tic = rec.get("re_escalated_at_tic")
    re_escalation_count = int(rec.get("re_escalation_count", 0) or 0)
    re_escalation_reminder = False
    re_escalated_volume = None
    if (
        structural_status in ("carried", "dimmed")
        and heat <= HEAT_FLOOR
        and not has_resolution_action
        and raw_status not in ("resolved", "dismissed", "superseded")
    ):
        anchors = [
            t for t in (re_escalated_at_tic, rec.get("acknowledged_tic"))
            if isinstance(t, int)
        ]
        quiet_anchor = max(anchors) if anchors else last_reinforced_tic
        quiet_tics = max(0, current_tic - int(quiet_anchor or current_tic))
        if quiet_tics >= REESC_QUIET_TICS:
            # Reactivate volume mechanics: re-heat above the floor so the ray is
            # active again (is_active_ray -> True), and stamp the re-escalation so
            # the next quiet window measures from NOW (sawtooth, not a one-shot).
            re_escalated_volume = REESC_VOLUME
            raw_volume = REESC_VOLUME
            visible_volume = round(REESC_VOLUME, 2)
            base = min(1.0, visible_volume / 100.0)
            carry_factor = 1.2  # carried/dimmed re-warmed carry
            heat = min(1.0, base * carry_factor)
            structural_status = "carried"
            re_escalated_at_tic = current_tic
            re_escalation_count += 1
            re_escalation_reminder = True

    projection = {
        "structural_status": structural_status,
        "visible_volume": round(visible_volume, 2),
        "heat": round(heat, 4),
        "_v2_projection_provisional": True,
        "_v2_projected_at_tic": current_tic,
        "_v2_projection_inputs": {
            "raw_status": raw_status,
            "raw_volume": raw_volume,
            "last_reinforced_tic": last_reinforced_tic,
            "raw_age_tics": raw_age_tics,
            "has_resolution_action": has_resolution_action,
            "recurrence_count": recurrence_proxy,
            "defaulted": [
                "tic_mass",
                "slice_density",
                "class_prior",
                "weighted_age_tics",
                "owner_status",
            ],
        },
    }
    if re_escalation_reminder:
        # Reactivate the legacy volume residue too so raw-enum-era readers and
        # the next projection see the re-heated volume (the "reactivation of the
        # volume mechanics" the contract requires), and surface a reminder marker
        # the docket can key on.
        projection["volume"] = re_escalated_volume
        projection["re_escalated_at_tic"] = re_escalated_at_tic
        projection["re_escalation_count"] = re_escalation_count
        projection["re_escalation_reminder"] = True
    elif re_escalated_at_tic is not None:
        # Preserve prior re-escalation provenance without re-firing.
        projection["re_escalated_at_tic"] = re_escalated_at_tic
        projection["re_escalation_count"] = re_escalation_count
    return projection


def resolve_zone_root(start: str | None = None) -> Path:
    if start is None:
        start = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    cur = Path(start).resolve()
    while cur != cur.parent:
        if (cur / ".ticzone").exists():
            return cur
        cur = cur.parent
    return Path(start).resolve()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone-root", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    zone_root = resolve_zone_root(args.zone_root)
    manifest = zone_root / "audit-logs" / "signals" / "active-manifest.jsonl"
    archive = zone_root / "audit-logs" / "signals" / "resolved-archive.jsonl"

    if not manifest.exists():
        if not args.quiet:
            print(f"manifest-prune: no manifest at {manifest} — nothing to prune")
        return 0

    current_tic = count_physical_tics(zone_root / "audit-logs")

    # First pass: parse rows + latest-entry-per-signal_id collapse.
    # Rationale: the manifest is the curated authoritative set after manifold-
    # prune sweeps and terminal-state filtering (federation KI Authoritative-Set
    # Readers Must Read the Manifest). Without per-id collapse before partition,
    # an append-a-resolved-row resolution writeback (the CGG KI Signal Resolution
    # Writeback Atomicity dual-surface append pattern) leaves orphan active rows
    # behind: the resolved row archives but the original active row remains in
    # keep, so the signal continues to surface as active on next read. Collapse
    # first ensures latest-entry-per-id wins before structural_status partition.
    latest_by_key: dict[object, dict] = {}
    collapsed_duplicates = 0
    malformed = 0
    fallback_idx = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        sid = rec.get("signal_id")
        if sid is None:
            # Defensive: records without signal_id are preserved as distinct
            # rows under a synthetic key. Should not occur in well-formed
            # manifests but never silently drop unidentified state.
            key: object = ("__no_id__", fallback_idx)
            fallback_idx += 1
        else:
            key = sid
            if key in latest_by_key:
                collapsed_duplicates += 1
        latest_by_key[key] = rec

    # Second pass: project + partition the collapsed set.
    keep: list[dict] = []
    archived: list[dict] = []
    for rec in latest_by_key.values():
        projection = project_signal(rec, current_tic)
        # Merge projection ride-along onto record. Legacy status/volume remain
        # as compatibility residue (P2 hard non-solution pattern); new
        # structural_status / visible_volume / heat carry semantic truth.
        projected = {**rec, **projection}
        structural_status = projection["structural_status"]
        if structural_status in ARCHIVE_STRUCTURAL:
            archived.append(projected)
        else:
            keep.append(projected)

    # Distribution of structural_status across kept records (for visibility).
    keep_dist: dict[str, int] = {}
    for rec in keep:
        ss = rec.get("structural_status", "unknown")
        keep_dist[ss] = keep_dist.get(ss, 0) + 1

    if args.dry_run:
        collapse_note = (
            f"; collapsed {collapsed_duplicates} duplicate signal_id rows"
            if collapsed_duplicates
            else ""
        )
        print(
            f"manifest-prune: [DRY RUN] tic={current_tic} — "
            f"{len(archived)} would archive (resolved/superseded); "
            f"{len(keep)} would remain active "
            f"({', '.join(f'{k}={v}' for k, v in sorted(keep_dist.items()))})"
            f"{collapse_note}"
        )
        return 0

    # Append archived entries (atomic append). Archived records carry the
    # projection too so resolved-archive consumers can audit closure inputs.
    if archived:
        try:
            from lib.atomic_append import atomic_append_jsonl  # type: ignore

            for rec in archived:
                atomic_append_jsonl(str(archive), rec)
        except ImportError:
            with archive.open("a", encoding="utf-8") as f:
                for rec in archived:
                    f.write(json.dumps(rec) + "\n")

    # Atomic replace of active-manifest with kept-and-projected entries.
    # Always rewrite when there are kept records — the projection mutates
    # visible_volume/heat each tic as quiet age accumulates, so the manifest
    # is a dynamic projected view, not a static carry-forward.
    if keep:
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=".manifest-prune-", suffix=".jsonl", dir=str(manifest.parent)
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                for rec in keep:
                    f.write(json.dumps(rec) + "\n")
            os.replace(tmp_path, manifest)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    elif archived:
        # All entries archived; truncate manifest to empty.
        manifest.write_text("", encoding="utf-8")

    if not args.quiet:
        dist_str = ", ".join(f"{k}={v}" for k, v in sorted(keep_dist.items())) or "none"
        collapse_note = (
            f"; collapsed {collapsed_duplicates} duplicate signal_id rows"
            if collapsed_duplicates
            else ""
        )
        if archived:
            print(
                f"manifest-prune: tic={current_tic} — pruned {len(archived)} "
                f"resolved/superseded entries to {archive.name}; "
                f"{len(keep)} remain active ({dist_str}){collapse_note}"
            )
        else:
            print(
                f"manifest-prune: tic={current_tic} — projection refreshed; "
                f"{len(keep)} active ({dist_str}){collapse_note}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
