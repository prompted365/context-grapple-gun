#!/usr/bin/env python3
"""Crisis injection condition checker for session-restore hook.

Reads signal files, mandate history, inbox registries, and runtime-sync
status to detect crisis conditions. Outputs injection text for each
triggered condition. Returns nothing if all clear.

Conditions checked (from crisis-response/README.md):
  1. Signal storm: >50 signal lines/tic or >3 duplicate IDs
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
from datetime import date


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
            sid = d.get("id", "")
            if sid:
                latest[sid] = d
    return sum(1 for d in latest.values() if d.get("status") in active_states)


def _raw_emissions_today(signal_dir: str) -> int:
    """Raw emission VOLUME in today's daily file (signal rows). This is emission
    telemetry, NEVER active-state — labeled explicitly so it can never be mistaken
    for the authoritative count again."""
    today = date.today().isoformat()
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


def check_signal_storm(signal_dir: str, current_tic: int) -> str | None:
    """Check for active signal storm.

    Two structurally distinct checks, each reading the CORRECT surface:
      1. Raw per-ID row explosion at the current tic (>50 rows for one ID) — this
         is a genuine emission-runaway indicator and is read from the raw daily
         file BY DESIGN; it is explicitly labeled as raw-row volume.
      2. Authoritative ACTIVE-signal count (>10) — read from active-manifest.jsonl
         (the curated truth), NOT from raw daily emissions. The raw daily volume is
         attached only as a separately-labeled telemetry field, never as the
         threshold input. (Fix tic 406 — bk-boot-crisis-check-manifest-parity:
         the old Check 2 counted raw daily rows and cried "20 active / runaway"
         while the manifest held 4.)
    """
    today = date.today().isoformat()
    signal_file = os.path.join(signal_dir, f"{today}.jsonl")

    # Check 1: Raw per-ID row explosion at current tic (>50 rows for single ID).
    # Read from the daily file by design — this IS raw-emission-volume detection.
    if os.path.isfile(signal_file):
        row_counts_current_tic = Counter()
        with open(signal_file) as f:
            for line in f:
                try:
                    d = json.loads(line)
                    sid = d.get("id", "")
                    if sid and d.get("tic", 0) == current_tic:
                        row_counts_current_tic[sid] += 1
                except (json.JSONDecodeError, KeyError):
                    pass
        explosions = {k: v for k, v in row_counts_current_tic.items() if v > 50}
        if explosions:
            worst = max(explosions, key=explosions.get)
            return (
                f"[CRISIS SIGNAL: signal ID '{worst}' has {explosions[worst]} raw "
                f"rows in today's file (threshold: 50). Emission runaway detected. "
                f"Wire cutter available: touch ~/.claude/.wire-cut-signals to halt "
                f"signal emission while you investigate. Check: (1) inbox-registry.json "
                f"for phantom stale entries, (2) installed vs source inbox-envelope.py "
                f"for dedup guard, (3) signal file for duplicate IDs. Do not assume "
                f"which is needed — diagnose first.]"
            )

    # Check 2: Authoritative ACTIVE-signal count — from the MANIFEST, not raw daily.
    active_count = _active_manifest_count(signal_dir)
    if active_count is None:
        # No manifest => cannot assert active-state truth. Do NOT fall back to raw
        # daily counting (that reintroduces the false-alarm bug). The raw-row
        # explosion check above still guards genuine emission runaway.
        return None
    if active_count > 10:
        raw_today = _raw_emissions_today(signal_dir)
        return (
            f"[CRISIS SIGNAL: {active_count} active signals "
            f"(authoritative active-manifest.jsonl, threshold: 10). "
            f"Possible unresolved storm. ({raw_today} raw emissions in today's "
            f"daily file — emission VOLUME, not active state; do not conflate.) "
            f"Wire cutter available: touch ~/.claude/.wire-cut-signals to halt "
            f"signal emission while you investigate.]"
        )

    return None


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

    # Check mandate history for excessive entries per tic
    today = date.today().isoformat()
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
    args = parser.parse_args()

    signal_dir = os.path.join(args.audit_logs, "signals")
    injections = []

    # Check each condition
    result = check_signal_storm(signal_dir, args.current_tic)
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
