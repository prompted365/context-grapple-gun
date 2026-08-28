#!/usr/bin/env python3
"""Crisis injection condition checker for session-restore hook.

Reads signal files, mandate history, inbox registries, and runtime-sync
status to detect crisis conditions. Outputs injection text for each
triggered condition. Returns nothing if all clear.

Conditions checked (from crisis-response/README.md):
  1. Signal storm: >50 raw rows for one id in today's file (Check 1, signal_id-or-id)
     + ACTIVE arrival predicate A1/A2/A3 (Check 2, ruled tic 744)
  2. Mandate pileup: >1 WAIT mandate per tic or >5 history entries per tic
  3. Inbox backlog: >20 pending messages per entity
  4. Source/runtime divergence: drifted hook-invoked scripts
"""

import argparse
import json
import glob
import os
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timezone


def _active_manifest_count(signal_dir: str) -> int | None:
    """Authoritative ACTIVE-state count from active-manifest.jsonl.

    The manifest is the curated, post-prune truth (latest-entry-per-id,
    statuses in {active, acknowledged, working}) — NOT the raw daily emission
    log. Reading raw daily files as if they were active-state is the exact
    failure mode the federation KI 'Authoritative-set readers must read the
    manifest, not aggregate raw emissions' (tic 111) + cgg-ledger
    'Authoritative Count Discipline' guard against. SIREN already reads the
    manifest; this check must too, or the same substrate yields two counters
    that disagree (Disagreement-as-evidence, tic 148).

    Returns the active count, or None if no manifest exists (in which case the
    caller must NOT fall back to raw-emission counting — raw is not authoritative).
    """
    manifest = os.path.join(signal_dir, "active-manifest.jsonl")
    if not os.path.isfile(manifest):
        return None
    active_states = {"active", "acknowledged", "working"}
    latest = {}
    with open(manifest) as f:
        for line in f:
            try:
                d = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            # F-742-C3 (HIGH, /review 742 Q5): manifest rows carry `signal_id`
            # (0/56 carried `id` at tic 742), so the old `d.get("id")` read counted
            # ZERO active rows over 54 and this detector was dead since the manifold
            # was born. `signal_id` is primary; `id` stays as the legacy fallback.
            sid = d.get("signal_id") or d.get("id", "")
            if sid:
                latest[sid] = d
    return sum(1 for d in latest.values() if d.get("status") in active_states)


def _active_manifest_ids(signal_dir: str) -> list[str]:
    """The ids behind _active_manifest_count — for the shadow record only."""
    manifest = os.path.join(signal_dir, "active-manifest.jsonl")
    if not os.path.isfile(manifest):
        return []
    active_states = {"active", "acknowledged", "working"}
    latest = {}
    with open(manifest) as f:
        for line in f:
            try:
                d = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            sid = d.get("signal_id") or d.get("id", "")
            if sid:
                latest[sid] = d
    return sorted(k for k, d in latest.items() if d.get("status") in active_states)


# ── Check 2 predicate (RULED tic 744 by the crisis-steward seat; ruling artifact
# audit-logs/sentinel/crisis-threshold-ruling-tic744.{json,md}; boot 5b38c4eedfbf1ffa) ──
# ACTIVE_THRESHOLD = 10 is RETIRED. It was an absolute test on the SIZE of a set that
# grows monotonically and is almost never pruned (4 -> 58 across 484 manifest
# revisions; 426/483 transitions added nothing): any fixed absolute threshold on that
# surface is a countdown to a permanent false alarm — wrong by SHAPE, not by value.
# The ruled predicate trips on ARRIVAL, composition-aware, with a state backstop:
#   A1  >= ARRIVAL_NON_CAMPAIGN new active ids from NON-campaign lanes since the
#       prior-tic observation (measured: 0/411 historical fires; all-time max 4)
#   A2  >= ARRIVAL_ANY_LANE new active ids from ANY lane in one tic (2/411, both the
#       C9 ladder-down campaign dumps of +34 and +35)
#   A3  standing active set > ACTIVE_ABSOLUTE_CEILING (0/484; max ever 59)
# The comparison base is the last shadow row from a PRIOR tic (per-tic, not per-boot).
# When no base exists the delta arms are SKIPPED — never default-fire, never
# synthesize a base. A3 rots if the standing corpus moves by >20 rows: re-derivation
# is owed then (ruling §honest_limits).
ARRIVAL_NON_CAMPAIGN = 5
ARRIVAL_ANY_LANE = 12
ACTIVE_ABSOLUTE_CEILING = 90
CAMPAIGN_LANE_PREFIXES = ("sig_ladder_down_audit_finding_",)
PREDICATE_VERSION = "tic744"
RAW_ROW_EXPLOSION = 50
SHADOW_SINK_REL = os.path.join("sentinel", "crisis-injection-shadow.jsonl")


def _shadow_record(audit_logs: str | None, record: dict) -> None:
    """The shadow lane — PROMOTED FROM EVIDENCE TO MECHANISM at tic 744. Every
    Check-2 evaluation appends one row, unconditionally, trip or no trip: the lane
    is the arrival predicate's ONLY state store (55/58 manifest rows carry no
    added_to_manifest_tic, so the manifold cannot say when its own rows arrived)
    AND the calibration evidence every future re-baseline re-derives from. A
    no-trip row is the negative control — a lane that only records fires cannot
    tell "nothing happened" from "the detector is dead again" (F-742-C3's exact
    ambiguity; ruling falsifier F4). Born /review 742 Q5 as detect+audit shadow
    (record, inject nothing); the tic-744 build keeps the write unconditional
    after the live flip. Fail-soft: a shadow write must never break the boot hook."""
    if not audit_logs:
        return
    try:
        path = os.path.join(audit_logs, SHADOW_SINK_REL)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError:
        pass


def _utc_today(now: "datetime | None" = None) -> str:
    """F-745 (two date clocks on one lane): every signal EMITTER in this corpus names the
    daily file by the UTC calendar date (biome-engine, inbox-envelope, contamination-handler,
    trust-progression-cycle, harpoon-orchestrator, border-stack, standing-engine,
    rebru-cadence-emit — datetime.now(timezone.utc)). This reader keyed date.today() (LOCAL)
    and therefore read a stale file for every hour between UTC midnight and local midnight
    (at the tic-745 boot, 02:46Z / 22:46 EDT: 61 rows in the local-dated 08-27 file vs the
    10 fresh rows — the four tic-745 rows among them — in the UTC-dated 08-28 file). A reader
    follows its WRITER's clock. `now` is injectable for tests; naive input is treated as UTC."""
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc)
    return now.date().isoformat()


def _local_today() -> str:
    """The mandate-history daily file is named by the LOCAL date by BOTH of its writers
    (mandate-write.py:416 datetime.now(); session-restore.sh TODAY=$(date +%Y-%m-%d)), so its
    reader stays on the local clock. Two clocks, each following its own writer — disclosed
    here rather than silently unified on one side."""
    return date.today().isoformat()


def _raw_emissions_today(signal_dir: str, now: "datetime | None" = None) -> int:
    """Raw emission VOLUME in today's daily file (signal rows). This is emission
    telemetry, NEVER active-state — labeled explicitly so it can never be mistaken
    for the authoritative count again."""
    today = _utc_today(now)  # F-745: the emitters date the file by UTC
    signal_file = os.path.join(signal_dir, f"{today}.jsonl")
    if not os.path.isfile(signal_file):
        return 0
    n = 0
    with open(signal_file) as f:
        for line in f:
            try:
                if json.loads(line).get("type") == "signal":
                    n += 1
            except (json.JSONDecodeError, ValueError):
                pass
    return n


def _prior_observation(audit_logs: str | None, current_tic: int) -> tuple[int | None, set[str]]:
    """The arrival predicate's base: the LAST shadow row whose tic != current_tic and
    which carries an active_ids list (rows of every schema vintage carry it). Returns
    (prior_tic, prior_ids); (None, set()) when no base exists — the caller SKIPS the
    delta arms. Fail-soft: an unreadable lane is no base, never a synthesized one."""
    if not audit_logs:
        return None, set()
    path = os.path.join(audit_logs, SHADOW_SINK_REL)
    if not os.path.isfile(path):
        return None, set()
    prior_tic, prior_ids = None, None
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if not isinstance(d, dict) or d.get("check") != "active_signal_count":
                    continue
                t = d.get("tic")
                ids = d.get("active_ids")
                if not isinstance(t, int) or t == current_tic or not isinstance(ids, list):
                    continue
                prior_tic, prior_ids = t, set(ids)   # last matching row wins
    except OSError:
        return None, set()
    if prior_tic is None:
        return None, set()
    return prior_tic, prior_ids


def _row_signal_id(d: dict) -> str:
    """F-744-CS1: daily rows carry `signal_id` (40/50 today) or `id` (10/50);
    Check 1 keyed `id` only and saw ZERO rows at tics 743/744. Same cure shape as
    F-742-C3 on the manifest read: signal_id primary, id fallback."""
    return d.get("signal_id") or d.get("id", "")


def check_signal_storm(signal_dir: str, current_tic: int,
                       audit_logs: str | None = None,
                       live_active_threshold: bool = False,
                       now: "datetime | None" = None) -> str | None:
    """Check for active signal storm. Two structurally distinct checks, each reading
    the CORRECT surface, both COLLECTED (F-744-CS2: Check 1 no longer early-returns
    and suppresses Check 2):
      1. Raw per-ID row explosion in today's daily file (> RAW_ROW_EXPLOSION rows for
         one id) — a genuine emission-runaway indicator, read from the raw daily file
         BY DESIGN and labeled as raw-row volume. Keyed signal_id-or-id (F-744-CS1);
         a row's tic is read when present, else the row is attributed to TODAY with
         its tic UNRESOLVED (only 4/50 rows carried a tic field on 2026-08-27) — the
         two populations are counted and disclosed separately, never merged silently.
      2. Authoritative ACTIVE-signal ARRIVAL (the tic-744 predicate above) — read from
         active-manifest.jsonl (the curated truth), compared against the prior-tic
         shadow observation. Raw daily volume rides as separately-labeled telemetry,
         never as a threshold input (tic 406, bk-boot-crisis-check-manifest-parity).
    """
    today = _utc_today(now)  # F-745: the daily file is UTC-dated by every emitter
    signal_file = os.path.join(signal_dir, f"{today}.jsonl")
    injections: list[str] = []

    # Check 1: raw per-ID row explosion — read from the daily file by design.
    if os.path.isfile(signal_file):
        rows_at_tic: Counter = Counter()
        rows_untimed_today: Counter = Counter()
        with open(signal_file) as f:
            for line in f:
                try:
                    d = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if not isinstance(d, dict):
                    continue
                sid = _row_signal_id(d)
                if not sid:
                    continue
                t = d.get("tic")
                if isinstance(t, int):
                    if t == current_tic:
                        rows_at_tic[sid] += 1
                else:
                    rows_untimed_today[sid] += 1
        explosions = {k: (v, "rows_at_current_tic") for k, v in rows_at_tic.items()
                      if v > RAW_ROW_EXPLOSION}
        for k, v in rows_untimed_today.items():
            if v > RAW_ROW_EXPLOSION and k not in explosions:
                explosions[k] = (v, "rows_today_tic_unresolved")
        if explosions:
            worst = max(explosions, key=lambda k: explosions[k][0])
            n, population = explosions[worst]
            injections.append(
                f"[CRISIS SIGNAL: signal ID '{worst}' has {n} raw rows in today's file "
                f"(population: {population}; threshold: {RAW_ROW_EXPLOSION}). Emission "
                f"runaway detected. Wire cutter available: touch ~/.claude/.wire-cut-signals "
                f"to halt signal emission while you investigate. Check: (1) inbox-registry.json "
                f"for phantom stale entries, (2) installed vs source inbox-envelope.py for dedup "
                f"guard, (3) signal file for duplicate IDs. Do not assume which is needed — "
                f"diagnose first.]"
            )

    # Check 2: authoritative ACTIVE-signal ARRIVAL — from the MANIFEST, not raw daily.
    active_count = _active_manifest_count(signal_dir)
    if active_count is None:
        # No manifest => cannot assert active-state truth. Do NOT fall back to raw
        # daily counting (that reintroduces the false-alarm bug).
        return " ".join(injections) if injections else None

    active_ids = _active_manifest_ids(signal_dir)
    active_set = set(active_ids)
    prior_tic, prior_ids = _prior_observation(audit_logs, current_tic)
    if prior_tic is None:
        new_ids: list[str] | None = None
        non_campaign_new: list[str] = []
    else:
        new_ids = sorted(active_set - prior_ids)
        non_campaign_new = [i for i in new_ids if not i.startswith(CAMPAIGN_LANE_PREFIXES)]

    arm = None
    if new_ids is not None and len(non_campaign_new) >= ARRIVAL_NON_CAMPAIGN:
        arm = "A1_non_campaign_arrival"
    elif new_ids is not None and len(new_ids) >= ARRIVAL_ANY_LANE:
        arm = "A2_any_lane_burst"
    elif active_count > ACTIVE_ABSOLUTE_CEILING:
        arm = "A3_absolute_ceiling"
    tripped = arm is not None
    raw_today = _raw_emissions_today(signal_dir, now)

    _shadow_record(audit_logs, {
        "type": "crisis_injection_shadow",
        "check": "active_signal_count",
        "predicate_version": PREDICATE_VERSION,
        "tic": current_tic,
        "active_count": active_count,
        "thresholds": {"A1_non_campaign_arrival": ARRIVAL_NON_CAMPAIGN,
                       "A2_any_lane_burst": ARRIVAL_ANY_LANE,
                       "A3_absolute_ceiling": ACTIVE_ABSOLUTE_CEILING},
        "prior_observation_tic": prior_tic,
        "delta_arms_evaluated": new_ids is not None,
        "new_since_prior_tic": (len(new_ids) if new_ids is not None else None),
        "new_ids": new_ids,
        "non_campaign_new": non_campaign_new if new_ids is not None else None,
        "tripped": tripped,
        "arm": arm,
        "would_inject": tripped,
        "injected": bool(tripped and live_active_threshold),
        "raw_emissions_today": raw_today,
        "active_ids": active_ids,
        "mode": "live" if live_active_threshold else "shadow",
        "ruling": "crisis-threshold-ruling-tic744 — arrival predicate; the lane records every evaluation",
    })

    if tripped and live_active_threshold:
        if arm == "A3_absolute_ceiling":
            detail = (f"standing active set {active_count} > ceiling {ACTIVE_ABSOLUTE_CEILING} "
                      f"(state backstop; base tic {prior_tic})")
        else:
            lanes = sorted({i.split("_")[0] if not i.startswith("sig_") else "_".join(i.split("_")[:3])
                            for i in (non_campaign_new if arm.startswith("A1") else new_ids)})
            detail = (f"{len(new_ids)} new active ids since tic {prior_tic} "
                      f"({len(non_campaign_new)} non-campaign; lanes {lanes[:6]}); "
                      f"standing base {active_count}")
        injections.append(
            f"[CRISIS SIGNAL: {arm} tripped — {detail} (authoritative active-manifest.jsonl; "
            f"predicate {PREDICATE_VERSION}). ({raw_today} raw emissions in today's daily file — "
            f"emission VOLUME, not active state; do not conflate.) Wire cutter available: "
            f"touch ~/.claude/.wire-cut-signals to halt signal emission while you investigate.]"
        )

    return " ".join(injections) if injections else None


def check_mandate_pileup(audit_logs: str, current_tic: int) -> str | None:
    """Check for >1 WAIT mandate per tic or >5 history entries per tic."""
    # Check inbox for WAIT mandate files
    mailbox_dir = os.path.join(audit_logs, "agent-mailboxes")
    if not os.path.isdir(mailbox_dir):
        return None

    # Count WAIT mandate files across all entity inboxes for current tic
    wait_count = 0
    for entity_dir in glob.glob(os.path.join(mailbox_dir, "ent_*")):
        inbound = os.path.join(entity_dir, "inbound")
        if not os.path.isdir(inbound):
            continue
        for f in os.listdir(inbound):
            if f.startswith("WAIT_") and f"_t{current_tic}_" in f and "mandate" in f.lower():
                wait_count += 1

    if wait_count > 1:
        return (
            f"[CRISIS SIGNAL: {wait_count} mandate envelopes detected for tic "
            f"{current_tic} (expected: 1). Possible mandate emission runaway. "
            f"Wire cutter available: touch ~/.claude/.wire-cut-mandates to halt "
            f"mandate emission. touch ~/.claude/.wire-cut-session to halt "
            f"session-restore entirely. Check: (1) trigger-manifest.yaml "
            f"idempotency_key for session-unique fields, (2) current.json tic "
            f"vs hook tic, (3) inbox-registry.json for duplicate entries. "
            f"Do not assume — investigate the lifecycle chain.]"
        )

    # Check mandate history for excessive entries per tic — LOCAL date by design: this
    # file's writers (mandate-write.py, session-restore.sh) name it by the local calendar.
    today = _local_today()
    history_file = os.path.join(audit_logs, "mogul", "mandates", "history", f"{today}.jsonl")
    if os.path.isfile(history_file):
        tic_counts = Counter()
        with open(history_file) as f:
            for line in f:
                try:
                    d = json.loads(line)
                    tic = d.get("tic_context", {}).get("current_tic", d.get("tic", 0))
                    if tic:
                        tic_counts[tic] += 1
                except (json.JSONDecodeError, KeyError):
                    pass

        # Only alert on current tic pileup (historical residue is not actionable)
        if current_tic in tic_counts and tic_counts[current_tic] > 5:
            worst_tic = current_tic
        else:
            worst_tic = None
        if worst_tic:
            return (
                f"[CRISIS SIGNAL: {tic_counts[worst_tic]} mandate history entries "
                f"for tic {worst_tic} (threshold: 5). Possible mandate emission "
                f"runaway. Wire cutter available: touch ~/.claude/.wire-cut-mandates "
                f"to halt mandate emission. Check: (1) trigger-manifest.yaml "
                f"idempotency_key, (2) current.json tic vs hook tic, "
                f"(3) inbox-registry.json for duplicate entries.]"
            )

    return None


def check_inbox_backlog(audit_logs: str) -> str | None:
    """Check for >20 pending messages in any entity inbox."""
    mailbox_dir = os.path.join(audit_logs, "agent-mailboxes")
    if not os.path.isdir(mailbox_dir):
        return None

    for entity_dir in glob.glob(os.path.join(mailbox_dir, "ent_*")):
        entity = os.path.basename(entity_dir)
        registry_file = os.path.join(entity_dir, "indexes", "inbox-registry.json")
        if os.path.isfile(registry_file):
            try:
                with open(registry_file) as f:
                    registry = json.load(f)
                pending = sum(
                    1 for entry in registry.values()
                    if isinstance(entry, dict) and entry.get("status") in ("WAIT", "ACTIVE")
                )
                if pending > 20:
                    return (
                        f"[CRISIS SIGNAL: {entity} inbox has {pending} pending "
                        f"messages (threshold: 20). Backlog may indicate emission "
                        f"runaway or consumption failure. Wire cutter available: "
                        f"touch ~/.claude/.wire-cut-all for full stop. Check: "
                        f"(1) are WAIT files on disk matching registry entries? "
                        f"(2) is the consuming agent running? (3) are new messages "
                        f"still being created? Registry is the source of truth "
                        f"for inbox state, not filesystem.]"
                    )
            except (json.JSONDecodeError, KeyError, OSError):
                pass

        # Fallback: count WAIT files if no registry
        inbound = os.path.join(entity_dir, "inbound")
        if os.path.isdir(inbound) and not os.path.isfile(registry_file):
            wait_files = [f for f in os.listdir(inbound) if f.startswith("WAIT_")]
            if len(wait_files) > 20:
                return (
                    f"[CRISIS SIGNAL: {entity} inbox has {len(wait_files)} WAIT "
                    f"files (threshold: 20). No registry found. Backlog may "
                    f"indicate emission runaway. Wire cutter available: "
                    f"touch ~/.claude/.wire-cut-all for full stop.]"
                )

    return None


def check_runtime_divergence(zone_root: str) -> str | None:
    """Check for source/runtime divergence on hook-invoked scripts."""
    sync_script = None
    for candidate in [
        os.path.join(zone_root, "scripts", "runtime-sync.py"),
        os.path.join(zone_root, "canonical_developer", "context-grapple-gun",
                     "cgg-runtime", "scripts", "runtime-sync.py"),
        os.path.expanduser("~/.claude/cgg-runtime/scripts/runtime-sync.py"),
    ]:
        if os.path.isfile(candidate):
            sync_script = candidate
            break

    if not sync_script:
        return None

    try:
        result = subprocess.run(
            ["python3", sync_script, "check", "--json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        summary = data.get("summary", data)
        drifted = summary.get("drifted", 0)
        if drifted > 0:
            names = summary.get("drifted_names", [])
            name_str = ", ".join(names[:5]) if names else "unknown"
            return (
                f"[CRISIS SIGNAL: {drifted} hook-invoked scripts diverge from "
                f"canonical source. Drifted: {name_str}. Installed runtime may "
                f"lack fixes present in source. Verify: diff source vs installed. "
                f"If the drift is unintentional, sync and verify. Wire cutter "
                f"available if the drifted script is causing side effects.]"
            )
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError, KeyError):
        pass

    return None


def main():
    parser = argparse.ArgumentParser(description="Crisis injection condition checker")
    parser.add_argument("--zone-root", required=True, help="Zone root directory")
    parser.add_argument("--audit-logs", required=True, help="Audit logs directory")
    parser.add_argument("--current-tic", type=int, required=True, help="Current tic number")
    parser.add_argument("--check-divergence", action="store_true",
                        help="Also check runtime divergence (slower)")
    parser.add_argument("--live-active-threshold", action="store_true",
                        help="Inject on the active-count check (default: SHADOW — record to "
                             "audit-logs/sentinel/crisis-injection-shadow.jsonl, inject nothing; "
                             "/review 742 Q5)")
    args = parser.parse_args()

    signal_dir = os.path.join(args.audit_logs, "signals")
    injections = []

    # Check each condition
    result = check_signal_storm(signal_dir, args.current_tic,
                                audit_logs=args.audit_logs,
                                live_active_threshold=args.live_active_threshold)
    if result:
        injections.append(result)

    result = check_mandate_pileup(args.audit_logs, args.current_tic)
    if result:
        injections.append(result)

    result = check_inbox_backlog(args.audit_logs)
    if result:
        injections.append(result)

    if args.check_divergence:
        result = check_runtime_divergence(args.zone_root)
        if result:
            injections.append(result)

    # Output all triggered injections
    if injections:
        print(" ".join(injections))


if __name__ == "__main__":
    main()
