"""
atomic_append.py — JSONL-safe atomic append using fcntl file locking.

Usage:
    from lib.atomic_append import atomic_append_jsonl
    atomic_append_jsonl("/path/to/file.jsonl", {"key": "value"})
"""

import fcntl
import json
import os
import tempfile


def atomic_append_jsonl(target: str, data: dict) -> None:
    """Atomically append a JSON line to a JSONL file with exclusive locking."""
    os.makedirs(os.path.dirname(target), exist_ok=True)
    line = json.dumps(data, separators=(",", ":")) + "\n"
    lockfile = target + ".lock"

    with open(lockfile, "w") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            with open(target, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


def atomic_write_json(target: str, data: dict) -> None:
    """Atomically write a JSON file (temp + rename)."""
    os.makedirs(os.path.dirname(target), exist_ok=True)
    fd, tmppath = tempfile.mkstemp(
        dir=os.path.dirname(target), suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmppath, target)
    except Exception:
        os.unlink(tmppath)
        raise


def manifest_row_from_signal(signal: dict, target: str, sig_id: str) -> dict:
    """Project a raw daily-emission signal into an ACTIVE-MANIFEST row.

    THE ROW SHAPE IS DERIVED, NOT INVENTED (wave 12c, tic 742). Every field
    below is here because a manifest READER reads it or a ratified manifest
    WRITER writes it; nothing is fabricated. Citations are file:line as of
    tic 742.

    ALWAYS WRITTEN (the three the row cannot be a manifest row without):
      signal_id  — the identity key, resolved from the signal's `signal_id`
                   OR `id`. Written under `signal_id` ONLY, never `id`:
                   manifest-prune.py:365 collapses latest-per-id on
                   `rec.get("signal_id")` (an id-less row gets a synthetic
                   `__no_id__` key and is never collapsed) and
                   mogul-runner.sh:403 counts `obj.get('signal_id')` alone.
                   Measured: 56/56 live manifest rows carry `signal_id`,
                   0/56 carry `id`.
      status     — hardcoded "active": it is the semantic claim of entering
                   the ACTIVE manifest, both hand-rolled precedents hardcode
                   it (docks-signal-emitter.py:195, runtime-sync.py:783),
                   crisis-injection.py:53 requires the explicit key, and
                   manifest-prune.project_signal:139 reads it as raw_status.
      source_file— "<daily-dir>/<daily-file>" (e.g. "signals/2026-08-27.jsonl"),
                   the provenance pointer back to the raw emission. Form taken
                   from docks-signal-emitter.py:196 and measured dominant on
                   the live manifest (52 of the 54 rows that carry it).

    CARRIED FROM THE SIGNAL IF PRESENT — ABSENT STAYS ABSENT, NEVER INVENTED
    (the ratified observability-parity law: cgg-ledger#machine-emitter-emit-
    resolve-symmetry-and-chronological-status-truth section 3, /review 668;
    the same rule ladder-audit._carry_manifest_observability:663 enforces):
      kind, band, volume, max_volume — the ratified parity quartet. A thin row
                   becomes latest-per-id truth on the next collapse and drops
                   the fields every reader keys on (cadence-ops.py:709-712
                   band/volume/kind, harmony-input-builder.py:159 kind,
                   manifest-prune.project_signal:141 volume, /siren loudest).
      subsystem  — read by the per-downbeat conformation (cadence-ops.py:713).
      source_tic — carried when the emitter has one; PLUS added_to_manifest_tic,
                   stamped by this helper from the canonical tic ledger at ingest
                   (/review 742 Q7 — the anchor the projector reads when the
                   emitter carries no tic; ABSENT when the ledger is unreadable)
                   (manifest-prune._infer_last_reinforced_tic:94-119 reads
                   volume_history[-1].tic > added_to_manifest_tic > source_tic).
                   When the signal declares none the row is `age_unknown`,
                   which the projector handles explicitly (no decay, no fake
                   freshness) and which 53 of the 56 live rows already are.
                   This helper does NOT resolve the federation tic: it holds a
                   write lock and has no zone-root resolver, and inventing a
                   tic would manufacture the exact fake freshness the t671
                   anti-silencing law forbids.

    DERIVED WITH DISCLOSURE (two fields the readers key on that the emitters
    store under a different key — relocated, never fabricated):
      signal_type— the signal's explicit `signal_type`; else its `type` when
                   that value is not the record-type literal "signal".
                   biome-engine.py:409 stores the signal TYPE in `type`;
                   visitor-economy-monitor.py:66 and arena-pressure-ingest.py:102
                   store the record type "signal" there. Manifest readers filter
                   on `signal_type` (ladder-audit.py:2003, :3925). Measured:
                   54/56 live rows carry it.
      summary    — `summary`, else `description`, else `payload.summary`. The
                   readers treat these as one slot (arena-report-generator.py:161
                   summary→reason→description; ladder-audit.py:2024
                   payload.summary or summary). `reason` is deliberately NOT in
                   the chain — no signal emitter in this repo writes it.
                   Measured: 56/56 live rows carry `summary`.

    NEVER WRITTEN:
      `id` (see signal_id above); `payload` (the curated set is deliberately
      PAYLOAD-FREE — the tic-718 payload-free-exception ray on the same parent
      KI); and structural_status / visible_volume / heat / _v2_* which are
      manifest-prune.project_signal's to compute at the next sweep. An
      un-projected row is still counted by lib/signal_active.is_active_ray:104
      (structural_status absent + status "active" -> ACTIVE), so the row is
      visible to Mogul signal_scan the moment it lands.
    """
    row: dict = {
        "signal_id": sig_id,
        "status": "active",
    }

    signal_type = signal.get("signal_type")
    if not signal_type:
        raw_type = signal.get("type")
        if raw_type and raw_type != "signal":
            signal_type = raw_type
    if signal_type:
        row["signal_type"] = signal_type

    # Parity quartet + reader fields: carry only what the original actually has.
    for field in ("kind", "band", "volume", "max_volume", "subsystem"):
        if signal.get(field) is not None:
            row[field] = signal[field]

    if isinstance(signal.get("source_tic"), int):
        row["source_tic"] = signal["source_tic"]

    # DATE ANCHOR (ruled /review 742 Q7, Architect-ratified — F-742-C5): an ingested
    # row with no tic anchor projects as age_unknown -> structural_status live and
    # NEVER decays. Neither trusting emitter carries a tic (biome-engine's
    # federation_tic is 0 by design; visitor-economy-monitor has no tic context),
    # so `source_tic` is usually absent. The tic this helper CAN honestly supply is
    # the one it is writing at: added_to_manifest_tic — manifest-prune's
    # priority-2 anchor (_infer_last_reinforced_tic: volume_history[-1].tic >
    # added_to_manifest_tic > source_tic). Read from the canonical tic ledger beside
    # the signals dir (mirrors manifest-prune.count_physical_tics); ABSENT when the
    # ledger is unreadable — never a manufactured value.
    added_tic = _current_canonical_tic(os.path.dirname(os.path.abspath(target)))
    if isinstance(added_tic, int) and added_tic > 0:
        row["added_to_manifest_tic"] = added_tic

    abs_target = os.path.abspath(target)
    row["source_file"] = os.path.join(
        os.path.basename(os.path.dirname(abs_target)), os.path.basename(abs_target)
    )

    summary = signal.get("summary") or signal.get("description")
    if not summary:
        payload = signal.get("payload")
        if isinstance(payload, dict):
            summary = payload.get("summary")
    if summary:
        row["summary"] = summary

    return row


def _current_canonical_tic(signals_dir: str) -> int | None:
    """Latest counted federation tic from <audit-logs>/tics/*.jsonl, where
    <audit-logs> is the parent of the signals dir. Mirrors
    manifest-prune.count_physical_tics (type=tic rows, count_mode != ignored,
    max global_counter_after). None when the ledger is absent/unreadable."""
    tic_dir = os.path.join(os.path.dirname(os.path.abspath(signals_dir)), "tics")
    if not os.path.isdir(tic_dir):
        return None
    best = 0
    try:
        for name in sorted(os.listdir(tic_dir)):
            if not name.endswith(".jsonl"):
                continue
            with open(os.path.join(tic_dir, name), "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if d.get("type") == "tic" and d.get("count_mode") != "ignored":
                        gc = d.get("global_counter_after", 0)
                        if isinstance(gc, int) and gc > best:
                            best = gc
    except OSError:
        return None
    return best or None


def dedup_signal_append(target: str, signal: dict, manifest_path: str = None,
                        ingest_manifest: bool = False) -> bool:
    """Append a signal only if its ID doesn't already exist in the target file
    or the active manifest. Returns True if written, False if deduplicated.

    Signal ID is read from 'signal_id' or 'id' field.

    `manifest_path` IS A READ-ONLY DEDUP SOURCE UNLESS `ingest_manifest=True`
    (/review 741 disclosure on the PRODUCER-half ray of constitution-ledger#
    authoritative-set-readers-must-read-the-manifest-not-aggregate-raw-emissions,
    from cpr_mogul_memory_mining_012d4d5a42c0; the ingest arm built at tic 742
    on backlog row bk-signal-manifest-producer-ingestion-path, design fork (b)+(c)
    ruled at dispatch). Passing `manifest_path=` alone gets cross-day dedup
    against the curated set and NOTHING ELSE — the signal is NOT ingested into
    that set, so the authoritative reader (Mogul signal_scan) never sees it and
    the unlanded condition re-emits once per day forever. That was the whole
    defect: a helper parameter named for a surface it only READS.

    `ingest_manifest=True` closes it. The helper becomes the ONE lawful append
    path for both surfaces:

      - the arm fires ONLY when the row was ACTUALLY WRITTEN to `target` (a
        deduped-away row must not mint a manifest row — the daily file already
        carries that id, and the manifest row for it either exists or was
        deliberately pruned);
      - and ONLY when `manifest_path` is given and is not `target` itself;
      - and ONLY for a signal that HAS an id — an id-less signal cannot be
        collapsed by manifest-prune.py:365 or counted by mogul-runner.sh:403,
        so writing one would mint a row no reader can key on;
      - the manifest row is `manifest_row_from_signal()` above — a DERIVED
        projection of the signal, not a copy of it (see that docstring for the
        per-field reader citations);
      - the manifest append is itself dedup-by-identity (signal_id) against the
        manifest's existing ids, under the manifest's own exclusive lock — it
        re-checks rather than trusting the dedup set read a moment earlier,
        because another producer may have landed the same id in between.

    LOCK ORDER (the contract a future writer must not invert): `target`.lock is
    acquired FIRST and held while `manifest_path`.lock is acquired. Nesting the
    ingest inside the target's critical section is deliberate — the daily write
    and the manifest ingest are one atomic half-pair. If they were sequenced
    outside the lock, a crash between them would leave the id in the daily file
    with no manifest row, and the NEXT emission would dedup away against the
    daily file and never ingest: permanent invisibility, which is the exact
    defect this arm cures.

    NOT FAIL-SOFT, BY DESIGN: if the manifest ingest raises, the exception
    propagates. The daily write has already landed (no data loss), and a caller
    that opted in has declared it needs manifest visibility — swallowing the
    failure would silently recreate the invisibility class. The return value is
    unchanged (True iff the DAILY row was written); the ingest is not reported
    separately.

    DEFAULT False keeps every existing caller byte-identical in behaviour. The
    opt-in is per-call-site and forward-only; nothing is backfilled.
    """
    sig_id = signal.get("signal_id", signal.get("id", ""))
    if not sig_id:
        # No ID — can't dedup, just append. `ingest_manifest` is a documented
        # NO-OP here: a manifest row without signal_id is unreadable to every
        # authoritative reader (manifest-prune.py:365, mogul-runner.sh:403).
        atomic_append_jsonl(target, signal)
        return True

    os.makedirs(os.path.dirname(target), exist_ok=True)
    lockfile = target + ".lock"

    with open(lockfile, "w") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            # Check target file for existing ID
            existing_ids = set()
            if os.path.isfile(target):
                with open(target, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            d = json.loads(line)
                            eid = d.get("signal_id", d.get("id", ""))
                            if eid:
                                existing_ids.add(eid)
                        except (json.JSONDecodeError, ValueError):
                            pass

            # Check active manifest if provided and different from target
            if manifest_path and manifest_path != target and os.path.isfile(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            d = json.loads(line)
                            eid = d.get("signal_id", d.get("id", ""))
                            if eid:
                                existing_ids.add(eid)
                        except (json.JSONDecodeError, ValueError):
                            pass

            if sig_id in existing_ids:
                return False

            # Write signal
            sline = json.dumps(signal, separators=(",", ":")) + "\n"
            with open(target, "a", encoding="utf-8") as f:
                f.write(sline)
                f.flush()
                os.fsync(f.fileno())

            # INGEST ARM (opt-in, tic 742). Row WAS written, so the producer now
            # gets a REACHABLE WRITE PATH to the surface the readers were told to
            # trust. Nested inside the target lock on purpose (see docstring:
            # lock order + atomic half-pair). Recurses into this same function
            # with the manifest as `target` so the manifest append carries the
            # identical dedup-by-identity + flock + fsync discipline.
            if ingest_manifest and manifest_path and manifest_path != target:
                dedup_signal_append(
                    manifest_path,
                    manifest_row_from_signal(signal, target, sig_id),
                )
            return True
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


def dedup_queue_append(target: str, entry: dict) -> bool:
    """Append a CPR queue entry only if its id doesn't already exist in the
    target file. Returns True if written, False if deduplicated.

    Implements Dedup-at-Write doctrine (CogPR-117) for the CPR queue: dedup
    enforcement happens at the write boundary, keyed on canonical record
    identity (entry id). Mirrors dedup_signal_append for queue.jsonl.

    The function reads the target under exclusive lock, scans existing ids,
    and only writes if the new entry's id is absent. This catches duplication
    at the physics layer regardless of why the caller is attempting to write
    the same id again (race, loop bug, missed upstream check).

    For terminal-state preservation, callers should verify the existing entry
    is not already terminal BEFORE invoking this function — once an id is
    written, this function will never overwrite. The Terminal-State Valve
    pattern (CogPR-188) is the read-side complement.
    """
    eid = entry.get("id", "")
    if not eid:
        # No ID — fall back to plain append; caller is responsible
        atomic_append_jsonl(target, entry)
        return True

    os.makedirs(os.path.dirname(target), exist_ok=True)
    lockfile = target + ".lock"

    with open(lockfile, "w") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            existing_ids = set()
            if os.path.isfile(target):
                with open(target, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                            existing = d.get("id", "")
                            if existing:
                                existing_ids.add(existing)
                        except (json.JSONDecodeError, ValueError):
                            pass

            if eid in existing_ids:
                return False

            line = json.dumps(entry, separators=(",", ":")) + "\n"
            with open(target, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
            return True
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        data = json.loads(sys.argv[2])
        atomic_append_jsonl(sys.argv[1], data)
    else:
        print(f"Usage: {sys.argv[0]} <target.jsonl> '<json>'")
        sys.exit(1)
