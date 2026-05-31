#!/usr/bin/env python3
"""subagent-citizen-boot.py — SubagentStart citizen-boot (Phase A, tic 318).

Generalizes the SessionStart boot (session-restore.sh boots ent_homeskillet and
surfaces ent_mogul's inbox) to EVERY spawned citizen, uniformly, at the only
per-spawn seam Claude Code exposes: SubagentStart.

This is Identity-precedes-capability AT ACTIVATION + Trigger-routing-is-mandatory
fulfilled at the boot boundary: a spawned citizen establishes standing, reads its
mail, and sees its brief BEFORE it acts.

Spec: autonomous_kernel/citizen-boot-reminders-spec.md (§2 injection points,
§8 build delta — Phase A). /review tic 317 PROMOTE-SPEC authorized Phase A build.

PHASE A SCOPE — HARD BOUNDARY (do not widen here):
  - SubagentStart wiring ONLY. Reuses the already-loop-safe inbox-envelope emitter.
  - Calls `inbox-envelope.py scan --format injection` — a READ-ONLY path that mints
    NO signals (signal emission lives only in `stale-check --emit-signals`).
  - NO wall-clock reminders (Phase B). NO missed-fire sweep (Phase C). NO daemon.
  - NO new signal class. NO doctrine/office-ledger expansion.

Loop-safety (spec §5): this hook does not mint signals at all, so the 200+ signal
runaway class cannot recur through it. The brief is dedup-on-unchanged (perception
layer) so per-spawn injection does not bloat context.

Compactness contract (spec §2 / Cognitive-budgets-must-be-task-routed):
  - Compact brief, SILENT-WHEN-EMPTY ("if nothing, just proceed").
  - Dedup-on-unchanged per (session, agent) so identical re-spawns stay quiet.

Payload shape (verified): Claude Code 2.1.69+ ships snake_case `agent_id` /
`agent_type` on per-spawn hooks (confirmed in session-restore.sh and against the
2.1.159 binary, which carries `executeSubagentStartHooks` + the `SubagentStart`
event key). camelCase fallbacks read defensively per Volatile-Schema discipline.

Fail-soft: this hook NEVER blocks a subagent spawn. Any error logs to stderr and
exits 0 with no injection.

Federation KI compose:
  - Identity precedes capability — resolve registered entity before injecting.
  - Trigger routing is mandatory — boot delivers the inbox brief at activation.
  - Wire-Cut Scoping by Capability Class — honors .wire-cut-all / .wire-cut-hooks.
  - Cognitive budgets must be task-routed — silent-when-empty + dedup-on-unchanged.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).parent.resolve()


def wire_cut_active() -> bool:
    """Honor the kill-switch scopes that bound this boot's capability class.

    Boot injects ambient context (not signals), so it answers to the broad
    cuts: .wire-cut-all (panic) and .wire-cut-hooks (hook lane). The
    signal-lane cut (.wire-cut-signals) is inherited by the emitter for the
    signal path, which this boot never travels.
    """
    wire_dir = Path.home() / ".claude"
    for scope in (".wire-cut-all", ".wire-cut-hooks"):
        if (wire_dir / scope).is_file():
            return True
    return False


def resolve_zone_root(start: Path) -> Path | None:
    """Walk up from the hook dir to the federation zone root (.ticzone marker)."""
    for p in [start, *start.parents]:
        if (p / ".ticzone").is_file():
            return p
    # Fallback: known canonical layout (hook is .../canonical_developer/context-grapple-gun/cgg-runtime/hooks)
    for p in start.parents:
        if (p / ".ticzone").is_file():
            return p
    return None


def resolve_inbox_envelope() -> Path | None:
    """Find inbox-envelope.py across canonical-source and installed layouts."""
    for cand in (
        HOOK_DIR.parent / "scripts" / "inbox-envelope.py",          # canonical source
        Path.home() / ".claude" / "cgg-runtime" / "scripts" / "inbox-envelope.py",  # installed
    ):
        if cand.is_file():
            return cand
    return None


def valid_entities(zone_root: Path) -> set[str]:
    """Load the registered entity-id set from the actor registry."""
    reg = zone_root / "autonomous_kernel" / "actor-registry.json"
    try:
        data = json.loads(reg.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    actors = data.get("actors", data) if isinstance(data, dict) else data
    out = set()
    for a in actors if isinstance(actors, list) else []:
        if isinstance(a, dict):
            eid = a.get("entity_id") or a.get("id")
            if eid:
                out.add(eid)
    return out


def resolve_entity(agent_id: str, agent_type: str, registered: set[str]) -> str | None:
    """Map a spawned subagent to its registered entity id (office-aware).

    Resolution order (first registered hit wins):
      1. explicit agent_id, if it is already a registered ent_* id
      2. ent_<agent_type with hyphens->underscores>   (the federation convention)
    Unknown / ad-hoc agents (no registry entry) get NO injection — boot only
    activates recognized citizens. Identity precedes capability.
    """
    candidates = []
    if agent_id:
        candidates.append(agent_id)
        if not agent_id.startswith("ent_"):
            candidates.append("ent_" + agent_id.replace("-", "_"))
    if agent_type:
        candidates.append("ent_" + agent_type.replace("-", "_"))
    for c in candidates:
        if c in registered:
            return c
    return None


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


def already_seen(zone_root: Path, session_id: str, entity: str, brief: str) -> bool:
    """Dedup-on-unchanged: True if this exact brief was already injected this
    session for this entity. Perception-layer observability state, not a signal.
    """
    seen_path = zone_root / "audit-logs" / "hooks" / "citizen-boot-seen.json"
    key = f"{session_id}:{entity}"
    digest = hashlib.sha256(brief.encode("utf-8")).hexdigest()[:16]
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
        pass  # dedup is best-effort; never block boot
    return False


def main() -> int:
    if wire_cut_active():
        return 0  # kill-switch armed — boot is cut

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        return 0

    # Defensive multi-field read (Volatile-Schema discipline): snake_case primary.
    agent_id = payload.get("agent_id") or payload.get("agentId") or ""
    agent_type = (
        payload.get("agent_type")
        or payload.get("agentType")
        or payload.get("subagent_type")
        or payload.get("subagentType")
        or ""
    )
    session_id = payload.get("session_id") or payload.get("sessionId") or "nosession"

    if not agent_id and not agent_type:
        return 0  # no identity to resolve; fail-soft silent

    zone_root = resolve_zone_root(HOOK_DIR)
    if zone_root is None:
        return 0
    registered = valid_entities(zone_root)
    entity = resolve_entity(str(agent_id), str(agent_type), registered)
    if entity is None:
        return 0  # unknown / ad-hoc agent — boot only activates recognized citizens

    scanner = resolve_inbox_envelope()
    if scanner is None:
        return 0

    tic = current_tic(zone_root)
    try:
        proc = subprocess.run(
            [
                sys.executable, str(scanner), "scan",
                "--entity", entity,
                "--format", "injection",
                "--current-tic", str(tic),
            ],
            capture_output=True, text=True, timeout=20,
            cwd=str(zone_root),
        )
    except (subprocess.SubprocessError, OSError) as e:
        sys.stderr.write(f"[citizen-boot] scan failed for {entity}: {e}\n")
        return 0

    brief = (proc.stdout or "").strip()
    if not brief:
        return 0
    # Silent-when-empty: the injection formatter returns "[INBOX: <id>] Empty."
    # when there is nothing actionable. Do not inject an empty-state line.
    if brief.endswith("] Empty."):
        return 0

    # Dedup-on-unchanged: same brief, same session, same entity -> stay quiet.
    if already_seen(zone_root, str(session_id), entity, brief):
        return 0

    context = (
        f"[CITIZEN-BOOT: {entity}] You are booting as a recognized federation "
        f"citizen (tic {tic}). Your inbox brief:\n{brief}\n"
        f"Process WAIT/ACTIVE items per your office before other work."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": context,
        }
    }))
    sys.stderr.write(f"[citizen-boot] booted {entity} (agent_type={agent_type}, tic={tic})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
