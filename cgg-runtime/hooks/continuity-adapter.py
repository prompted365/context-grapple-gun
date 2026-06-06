#!/usr/bin/env python3
"""continuity-adapter.py — Primitive 9: compaction / continuity lifecycle seam.

Spec: audit-logs/governance/compaction-continuity-adapter-spec-tic364.md (tic 364).
Built tic 363 under the Architect's "build the seam" directive (the §6 install-gate go).

WHAT IT IS: the lifecycle-EXIT seam, opposite the hardened boot seam. It fires on the
lifecycle discontinuity events (PreCompact/PostCompact/Stop/SessionEnd), normalizes
them to a CanonicalLifecycleEvent, and emits a continuity-receipt-v0 — evidence that
the office's identity/task/governance survived (or did not survive) the discontinuity.

THE INVARIANT (load-bearing): this adapter is an ORIGINATOR — it produces a receipt
(evidence). It NEVER terminalizes governance state, never writes a mandate/queue/signal,
never blocks the lifecycle event. Observe + record. Canonical is the sole writer.

DISCIPLINE (spec §5, mirrors subagent-citizen-boot.py — copy the discipline):
  - fail-closed root resolution  : walk for .ticzone; NO hardcoded fallback (avoids the
                                   boot-receipt.py:49 defect class). No zone -> no-op.
  - atomic write                 : os.replace on the seen-file; atomic append on the sink.
  - session-keyed idempotency    : key {session}:{entity}:{event}; dedup-on-unchanged.
  - fail-soft                    : ANY error -> stderr + exit 0. Never blocks compaction/stop.
  - receipt emission only        : append-only evidence sink; zero governance-state write.
  - no authority expansion       : holds no capability to mutate state.

GRAMMAR LAW (spec §3): a pre receipt may only DECLARE expectation (observed=null); only a
post/stop receipt may CLAIM survival (observed filled, divergence computed).

v0 hash proxies (honest scope — sharpen in later increments):
  identity_hash         = office identity (entity + sorted roles from actor-registry)
  active_task_hash      = active obligation surface (mandates/current.json bytes)
  governance_state_hash = tic + digest(active-manifest.jsonl) + digest(mandates/current.json)
  render_source_hash    = digest(federation compact-root CLAUDE.md) — the instruction surface
"""

import hashlib
import json
import os
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).parent.resolve()
SCHEMA_VERSION = "continuity-receipt-v0"

# Vendor hook event -> canonical lifecycle event (defensive: read either source).
EVENT_MAP = {
    "precompact": "compact.pre",
    "postcompact": "compact.post",
    "stop": "stop",
    "sessionend": "session.end",
    "subagentstop": "stop",  # subagent close maps to a stop-class closure
}


def wire_cut_active() -> bool:
    """Honor the broad kill-switch scopes (this seam injects no signals)."""
    wire_dir = Path.home() / ".claude"
    return any((wire_dir / s).is_file() for s in (".wire-cut-all", ".wire-cut-hooks"))


def resolve_zone_root(start: Path) -> Path | None:
    """FAIL-CLOSED zone resolution: walk for .ticzone. NO hardcoded fallback.
    No resolvable zone -> return None -> the adapter no-ops (never default-mutates).
    This is spec §6 precondition #3 — the place to NOT repeat boot-receipt.py:49."""
    for p in [start, *start.parents]:
        if (p / ".ticzone").is_file():
            return p
    cwd = Path.cwd()
    for p in [cwd, *cwd.parents]:
        if (p / ".ticzone").is_file():
            return p
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir and (Path(env_dir) / ".ticzone").is_file():
        return Path(env_dir)
    return None  # fail-closed: no default mutation target


def _digest_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:32]


def _digest_file(path: Path) -> str:
    try:
        return _digest_bytes(path.read_bytes())
    except OSError:
        return _digest_bytes(b"")


def current_tic(zone_root: Path) -> int:
    """Max counted global_counter_after across the tic log (time authority)."""
    tic_dir = zone_root / "audit-logs" / "tics"
    if not tic_dir.is_dir():
        return 0
    mx = 0
    for f in sorted(tic_dir.glob("*.jsonl")):
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("type") != "tic" or d.get("count_mode", "counted") != "counted":
                    continue
                ca = d.get("global_counter_after", d.get("global_counter", 0))
                if isinstance(ca, int) and ca > mx:
                    mx = ca
        except OSError:
            continue
    return mx


def resolve_entity(payload: dict, zone_root: Path) -> str:
    """Resolve the office whose continuity is asserted. Defaults to the session
    primary (interactive orchestrator) when the lifecycle payload carries no agent."""
    agent_id = payload.get("agent_id") or payload.get("agentId") or ""
    agent_type = payload.get("agent_type") or payload.get("subagent_type") or ""
    reg = zone_root / "autonomous_kernel" / "actor-registry.json"
    registered = set()
    try:
        data = json.loads(reg.read_text(encoding="utf-8"))
        actors = data.get("actors", data) if isinstance(data, dict) else data
        for a in actors if isinstance(actors, list) else []:
            if isinstance(a, dict):
                eid = a.get("entity_id") or a.get("id")
                if eid:
                    registered.add(eid)
    except (OSError, ValueError):
        pass
    for c in (agent_id, "ent_" + str(agent_id).replace("-", "_"),
              "ent_" + str(agent_type).replace("-", "_")):
        if c in registered:
            return c
    return "ent_homeskillet"  # session primary (interactive orchestrator / session lead)


def office_roles(zone_root: Path, entity: str) -> list[str]:
    reg = zone_root / "autonomous_kernel" / "actor-registry.json"
    try:
        data = json.loads(reg.read_text(encoding="utf-8"))
        actors = data.get("actors", data) if isinstance(data, dict) else data
        for a in actors if isinstance(actors, list) else []:
            if isinstance(a, dict) and (a.get("entity_id") or a.get("id")) == entity:
                roles = a.get("roles") or a.get("role") or []
                return sorted(roles) if isinstance(roles, list) else [str(roles)]
    except (OSError, ValueError):
        pass
    return []


def compute_hashes(zone_root: Path, entity: str, tic: int) -> dict:
    """The four v0 continuity hashes (read-only, deterministic, cheap)."""
    roles = office_roles(zone_root, entity)
    identity_hash = _digest_bytes((entity + "|" + ",".join(roles)).encode("utf-8"))
    mandate = zone_root / "audit-logs" / "mogul" / "mandates" / "current.json"
    manifest = zone_root / "audit-logs" / "signals" / "active-manifest.jsonl"
    claude_md = zone_root / "CLAUDE.md"
    active_task_hash = _digest_file(mandate)
    governance_state_hash = _digest_bytes(
        f"{tic}|{_digest_file(manifest)}|{_digest_file(mandate)}".encode("utf-8")
    )
    render_source_hash = _digest_file(claude_md)
    return {
        "identity_hash": identity_hash,
        "active_task_hash": active_task_hash,
        "governance_state_hash": governance_state_hash,
        "render_source_hash": render_source_hash,
    }


def read_sink(sink: Path) -> list[dict]:
    out = []
    try:
        for line in sink.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    return out


def find_prior(records: list[dict], session_id: str, want_event: str | None = None) -> dict | None:
    """Most recent receipt for this session (optionally filtered to an event)."""
    for r in reversed(records):
        if r.get("session_id") != session_id:
            continue
        if want_event is None or r.get("lifecycle_event") == want_event:
            return r
    return None


def compute_divergence(observed: dict, prior_expected: dict | None) -> str:
    """v0 divergence semantics: identity loss = broken; task loss = drifted;
    identity+task preserved = intact (governance/render drift is legitimate);
    no linked prior = unverified."""
    if not prior_expected:
        return "unverified"
    if observed["identity_hash"] != prior_expected.get("identity_hash"):
        return "broken"
    if observed["active_task_hash"] != prior_expected.get("active_task_hash"):
        return "drifted"
    return "intact"


def already_emitted(zone_root: Path, key: str, digest: str) -> bool:
    """Dedup-on-unchanged (T-F idempotency): True if this exact receipt content was
    already emitted for this {session:entity:event}. Atomic os.replace on the seen-file."""
    seen_path = zone_root / "audit-logs" / "hooks" / "continuity-adapter-seen.json"
    try:
        state = json.loads(seen_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    if state.get(key) == digest:
        return True
    state[key] = digest
    try:
        seen_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = seen_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(tmp, seen_path)
    except OSError:
        pass  # best-effort; never block
    return False


def atomic_append(sink: Path, line: str) -> None:
    """Atomic append (O_APPEND single write). JSONL atomic-writes discipline."""
    sink.parent.mkdir(parents=True, exist_ok=True)
    data = (line + "\n").encode("utf-8")
    fd = os.open(str(sink), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def normalize_event(payload: dict, arg_event: str | None) -> str | None:
    raw = arg_event or payload.get("hook_event_name") or payload.get("hookEventName") or ""
    return EVENT_MAP.get(str(raw).replace("_", "").replace("-", "").lower())


def main() -> int:
    if wire_cut_active():
        return 0

    # --event override (used by wiring/tests where stdin lacks hook_event_name)
    arg_event = None
    argv = sys.argv[1:]
    if "--event" in argv:
        i = argv.index("--event")
        if i + 1 < len(argv):
            arg_event = argv[i + 1]
    zone_override = None
    if "--zone-root" in argv:
        i = argv.index("--zone-root")
        if i + 1 < len(argv):
            zone_override = Path(argv[i + 1])

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    event = normalize_event(payload, arg_event)
    if event is None:
        return 0  # not a lifecycle event we watch — silent no-op

    zone_root = zone_override if (zone_override and (zone_override / ".ticzone").is_file()) \
        else resolve_zone_root(HOOK_DIR)
    if zone_root is None:
        sys.stderr.write("[continuity-adapter] fail-closed: no .ticzone resolved; no-op\n")
        return 0  # fail-closed — never default-mutate

    try:
        session_id = payload.get("session_id") or payload.get("sessionId") or "nosession"
        tic = current_tic(zone_root)
        entity = resolve_entity(payload, zone_root)
        observed = compute_hashes(zone_root, entity, tic)

        sink = zone_root / "audit-logs" / "boot-injections" / "continuity-receipts.jsonl"
        records = read_sink(sink)

        is_pre = event == "compact.pre"
        # link target: post links to the matching pre; stop/end link to the latest receipt
        if event == "compact.post":
            prior = find_prior(records, session_id, "compact.pre")
        elif event in ("stop", "session.end"):
            prior = find_prior(records, session_id, None)
        else:
            prior = None
        prior_expected = (prior or {}).get("expected_continuity") if prior else None

        receipt = {
            "schema": SCHEMA_VERSION,
            "receipt_id": hashlib.sha256(
                f"{session_id}:{entity}:{event}:{tic}".encode("utf-8")
            ).hexdigest()[:16],
            "lifecycle_event": event,
            "entity_id": entity,
            "session_id": session_id,
            "tic": tic,
            **observed,
            "previous_receipt_pointer": (prior or {}).get("receipt_id") if prior else None,
            # grammar law: pre DECLARES expectation; only post/stop CLAIM survival
            "expected_continuity": observed if is_pre else (prior_expected or observed),
            "observed_continuity": None if is_pre else observed,
            "divergence_status": "unverified" if is_pre else compute_divergence(observed, prior_expected),
            "fail_soft": True,
        }

        key = f"{session_id}:{entity}:{event}"
        digest = hashlib.sha256(
            json.dumps({k: receipt[k] for k in (
                "lifecycle_event", "identity_hash", "active_task_hash",
                "governance_state_hash", "render_source_hash", "divergence_status")},
                sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        if already_emitted(zone_root, key, digest):
            return 0  # idempotent: identical event already recorded

        atomic_append(sink, json.dumps(receipt))
        sys.stderr.write(
            f"[continuity-adapter] {event} receipt {receipt['receipt_id']} "
            f"entity={entity} tic={tic} divergence={receipt['divergence_status']}\n"
        )
    except Exception as e:  # fail-soft: never block the lifecycle event
        sys.stderr.write(f"[continuity-adapter] fail-soft: {e}\n")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
