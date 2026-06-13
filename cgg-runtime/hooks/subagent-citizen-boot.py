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
    """Walk up from the hook dir to the federation zone root (.ticzone marker).

    The live hook fires from source ($CLAUDE_PROJECT_DIR/...), where this walk finds
    .ticzone. The cwd fallback (mirrors session-restore.sh's PWD resolution) keeps it
    working if ever fired from the installed ~/.claude copy with cwd=project."""
    for p in [start, *start.parents]:
        if (p / ".ticzone").is_file():
            return p
    # cwd fallback — Claude Code fires hooks with cwd at the project dir.
    cwd = Path.cwd()
    for p in [cwd, *cwd.parents]:
        if (p / ".ticzone").is_file():
            return p
    # CLAUDE_PROJECT_DIR fallback — set by the harness for project-scoped hooks.
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir and (Path(env_dir) / ".ticzone").is_file():
        return Path(env_dir)
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


def resolve_boot_injection() -> Path | None:
    """Find the shared boot-injection renderer across source + installed layouts."""
    for cand in (
        HOOK_DIR.parent / "scripts" / "boot-injection.py",          # canonical source
        Path.home() / ".claude" / "cgg-runtime" / "scripts" / "boot-injection.py",  # installed
    ):
        if cand.is_file():
            return cand
    return None


def resolve_office_worldview() -> Path | None:
    """Find the pertinence-compiler (office-worldview.py) across source + installed."""
    for cand in (
        HOOK_DIR.parent / "scripts" / "office-worldview.py",          # canonical source
        Path.home() / ".claude" / "cgg-runtime" / "scripts" / "office-worldview.py",  # installed
    ):
        if cand.is_file():
            return cand
    return None


def render_worldview(tic: int, entity: str, zone_root: Path) -> str:
    """Compile this citizen's pertinence worldview (office-worldview.py). Read-only,
    mints no signals, fail-soft to empty. The compiled fragments give the booting
    citizen its typed pertinence map (YOURS/FIELD/SUBSTRATE/...) WITH authority badges,
    plus the budget-exempt boot-receipt request frame. Primary office gets the direct
    lens; every other recognized citizen gets it projected (compiler-side). This is the
    Phase-A boot-boundary widening authorized by the Architect at the tic-332 gate
    (PROMOTE-SPEC /review 332 + explicit confirming look)."""
    script = resolve_office_worldview()
    if script is None:
        return ""
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "render", "--office", entity,
             "--tic", str(tic), "--format", "human", "--zone-root", str(zone_root),
             "--max-chars", "2200"],
            capture_output=True, text=True, timeout=10,
        )
        return (proc.stdout or "").strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def render_boot_injection(tic: int, entity: str, zone_root: Path) -> str:
    """Tic-gated broadcast pointers (e.g. GLOSSARY doctrine-surface nav). Read-only,
    mints no signals, fail-soft to empty. Every citizen is a 'citizens'-lane recipient.
    Passes the already-resolved canonical zone root — the installed renderer cannot
    find .ticzone by __file__ walk from ~/.claude."""
    script = resolve_boot_injection()
    if script is None:
        return ""
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "render", "--tic", str(tic),
             "--audience", entity, "--zone-root", str(zone_root), "--max-chars", "1500"],
            capture_output=True, text=True, timeout=10,
        )
        return (proc.stdout or "").strip()
    except (subprocess.SubprocessError, OSError):
        return ""


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


# Internal generic delegated worker types: spawned by a lead to execute a bounded
# slice, never registered as citizens by design. These resolve to the `task_scoped_worker`
# standing (entity-ontology.md) — a minimal rung/zone boot, NOT a citizen boot, NOT silence.
KNOWN_EPHEMERAL_TYPES = {"general-purpose"}


def resolve_entity(agent_id: str, agent_type: str, registered: set[str]) -> str | None:
    """Map a spawned subagent to its registered entity id (office-aware), or None.

    Resolution order (first registered hit wins):
      1. explicit agent_id, if it is already a registered ent_* id
      2. ent_<agent_type with hyphens->underscores>   (the federation convention)
    Returns None when no registry entry matches. Standing classification (citizen vs
    task_scoped_worker vs unresolved_standing) is decided by classify_standing below.
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


def classify_standing(agent_id: str, agent_type: str, registered: set[str]) -> tuple[str, str | None]:
    """Decide the booting subagent's STANDING (entity-ontology.md axis).

    Implements the resolve_entity guard for `task_scoped_worker` standing (inscribed
    /review 391). Returns (standing, entity_or_none):

      ("citizen", ent_id)        — recognized citizen → full citizen boot
      ("task_scoped_worker", None) — internal generic delegated worker (KNOWN_EPHEMERAL
                                     agent_type, no registry hit) → minimal rung/zone boot
      ("unresolved_standing", id) — a CITIZEN-SHAPED id (ent_*-prefixed) that did NOT
                                    resolve → refuse boot, log. A typo MUST NOT silently
                                    demote a citizen to a worker (No magical inheritance:
                                    unresolved-citizen-id → error, not ephemeral downgrade).
      ("none", None)             — nothing to boot (ad-hoc/unknown, not citizen-shaped,
                                    not a known worker type) → honest-constraint silence.
    """
    entity = resolve_entity(agent_id, agent_type, registered)
    if entity is not None:
        return ("citizen", entity)
    # Not a registered citizen. Is it a known internal generic delegated worker?
    if agent_type in KNOWN_EPHEMERAL_TYPES:
        return ("task_scoped_worker", None)
    # Citizen-shaped but unresolved → refuse (typo guard); never downgrade to worker.
    if agent_id.startswith("ent_"):
        return ("unresolved_standing", agent_id)
    return ("none", None)


# Minimal rung/zone law a task_scoped_worker receives: enough to stay inside the
# hierarchy, no authority to become the thing it is helping (entity-ontology.md).
TASK_SCOPED_WORKER_FRAME = (
    "You are booting as a TASK-SCOPED WORKER (standing: task_scoped_worker — an internal "
    "delegated non-citizen). You have NO persistent identity, NO inbox, NO memory across "
    "spawns, and NO inscription authority. Your action scope is the bounded task your lead "
    "delegated; your outputs are owned by that lead. Defer to the lead for anything beyond "
    "the task. Doctrine you may need is RETRIEVED, never reconstructed from a principle — "
    "read the exact local schemas/config/contracts at their rung; do not invent them "
    "(load-bearing local semantics stay home). Parent-rung law shapes your judgment but "
    "does not define local reality."
)


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
    standing, entity = classify_standing(str(agent_id), str(agent_type), registered)

    if standing == "unresolved_standing":
        # A citizen-shaped id that did not resolve. Refuse boot — never silently downgrade
        # a (typo'd) citizen to a worker. Fail-soft: log, no injection, do not block spawn.
        sys.stderr.write(
            f"[citizen-boot] unresolved_standing: citizen-shaped id '{entity}' not in "
            f"registry (agent_type={agent_type}) — refusing boot, no worker downgrade\n"
        )
        return 0

    if standing == "task_scoped_worker":
        # Minimal rung/zone boot: tic-gated broadcast pointers + the worker frame.
        # No inbox (no standing to receive mail), no office-worldview (no office), no
        # identity/memory/inscription. Receipt scales to stakes — kept compact here.
        tic = current_tic(zone_root)
        inject = render_boot_injection(tic, "task_scoped_worker", zone_root)
        parts = [TASK_SCOPED_WORKER_FRAME]
        if inject:
            parts.append(inject)
        # Boot-receipt MANDATORY FOR ALL standings (tic 399, Architect-directed) — compact for
        # the worker's stakes, but never absent. "Scales to stakes" never means "skip."
        parts.append(
            "━━━ BOOT RECEIPT (mandatory · compact) ━━━ Before your first task action, "
            "acknowledge in ONE line that you booted as a task-scoped worker and accept the "
            "boundary (no inscription authority; lead-owned outputs). This closes the worker "
            "boot loop — every standing closes it, scaled to its stakes."
        )
        combined = "\n".join(parts).strip()
        if already_seen(zone_root, str(session_id), "task_scoped_worker:" + str(agent_type), combined):
            return 0
        context = (
            f"[TASK-SCOPED-WORKER BOOT] (agent_type={agent_type}, tic {tic})\n" + combined
        )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SubagentStart",
                "additionalContext": context,
            }
        }))
        sys.stderr.write(
            f"[citizen-boot] booted task_scoped_worker (agent_type={agent_type}, tic={tic})\n"
        )
        return 0

    if standing != "citizen":
        return 0  # "none" — ad-hoc/unknown, not citizen-shaped, not a known worker type

    # standing == "citizen": full recognized-citizen boot (inbox + worldview + pointers).
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
    # Silent-when-empty: the injection formatter returns "[INBOX: <id>] Empty."
    # when there is nothing actionable. Treat as no inbox brief (not an early return —
    # a citizen with an empty inbox still receives tic-gated boot injections below).
    if brief.endswith("] Empty."):
        brief = ""

    # Compiled pertinence worldview (office-worldview.py): the citizen's typed civic
    # orientation WITH authority badges + the budget-exempt boot-receipt request frame.
    # Phase-A boot-boundary widening authorized at the tic-332 gate.
    world = render_worldview(tic, entity, zone_root)

    # Shared boot-injection lane (same registry session-restore.sh reads): tic-gated
    # broadcast pointers (e.g. GLOSSARY doctrine-surface navigation). Reaches the citizen
    # even when the inbox is empty.
    inject = render_boot_injection(tic, entity, zone_root)

    if not brief and not inject and not world:
        return 0  # nothing to deliver — stay silent

    # Dedup-on-unchanged over the COMBINED payload: same content, same session/entity -> quiet.
    combined_key = (world + "\n" + brief + "\n" + inject).strip()
    if already_seen(zone_root, str(session_id), entity, combined_key):
        return 0

    parts = []
    if world:
        parts.append(world)
    if brief:
        parts.append(
            f"Your inbox brief:\n{brief}\n"
            f"Process WAIT/ACTIVE items per your office before other work."
        )
    if inject:
        parts.append(inject)
    context = (
        f"[CITIZEN-BOOT: {entity}] You are booting as a recognized federation entity "
        f"(tic {tic}). Your STANDING and its boundary are stamped in the worldview below — "
        f"a citizen carries full authority; a resident/guest/recognized_body/registered_artifact "
        f"carries a capped, shape-only worldview with an ⟨APOPHATIC⟩ boundary naming what it is "
        f"NOT. Honor your badge.\n" + "\n".join(parts)
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
