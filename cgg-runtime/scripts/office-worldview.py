#!/usr/bin/env python3
"""office-worldview.py — the Pertinence Compiler (tic 328).

NOT an instruction generator. A PERTINENCE COMPILER.

THE PRIMITIVE — Pertinence (the missing primary axis; scope was the wrong one):
  A piece of context can shape interpretation without granting authority to act.
  Scope collapses too much: "in scope" wrongly implies action; "out of scope" wrongly
  implies irrelevance. Pertinence preserves the middle: UNDERSTANDING WITHOUT MANDATE.

Three orthogonal axes, not one:
  1. Pertinence — does this matter to my interpretation?
  2. Authority  — am I allowed to act from it?
  3. Citation   — am I allowed to quote/name/use it as explicit support?
This prevents the classic collapse: relevant→actionable, background→irrelevant,
known→citable, inherited→owned.

WHAT IT DOES — compile, for (office, tic, zone_root), a typed worldview as a list of
`worldview_fragment` records, each carrying its pertinence CLASS, an authority block,
a methylation weight, and a receipt obligation. Two faces (dual legibility — DLC
discipline): --format json (typed, source of truth) and --format human (grouped brief
with authority badges). The substrate, made legible AND correctly-authorized, scoped
to an office.

PERTINENCE CLASSES (Architect-specified):
  YOURS     carry as purpose; may shape priority/judgment/resolve; act only if authority allows
  FIELD     background terrain; understand; do not act from; do not cite as mandate
  SUBSTRATE load-bearing invariant beneath the office; shapes all interpretation; not locally editable
  OFFICE    your role/aperture/obligations; authorizes action inside the office boundary
  PEER      another office at same standing; understand the relation; do not overwrite/impersonate
  ANCESTOR  prior lineage/inherited terrain; explains why current structure exists; does not authorize present action
  COUNTER   inversion/drift/warning shape; use diagnostically; do not emulate
  APOPHATIC what you/this are NOT — a definitional boundary that prevents misclassification;
            cite the boundary as a constraint, do not act from it; distinct from COUNTER
            (a failure-shape) — a defining negation, not a drift (tic 399; reconciles the
            tic-375 frame-protocol APO facet; /review 400+ for ledger inscription)
  SEALED    matters but not to be cited/expanded/acted from; exists to prevent misclassification
  ESCALATE  relevant but exceeds your authority; preserve and route upward

HARMONY frames how the compiled fragments mold/shape (L0): she calibrates RESOLVE —
the orchestrator gets the PRIMARY lens; everyone else gets it PROJECTED (same cores,
their centroid). Backwards via collapseZones/caution; forwards via siblingOverlaps/
invitation. Orientation only, non-citable by her own contract.

LOOP-SAFETY (boot-injection.py §5): READ-ONLY. Mints no signals, writes no state. Reads
registries + tic state and prints. Fail-soft PER FRAGMENT — a broken source is dropped,
never breaks a boot. SILENT-WHEN-EMPTY.

CLI:
  office-worldview.py render --office ent_xxx --tic N [--format human|json] [--zone-root P] [--max-chars N]
"""

import argparse
import json
import sys
from pathlib import Path

DEFAULT_MAX_CHARS = 3000

# The 3 normative directives (pertinence class table + authority + citation) now
# live in the shared Injection Fabric contract (lib/fragment_contract.py, tic 367)
# so the routed model (this file) and the registry/migration model (dsn_fragment.py)
# honor ONE source — the badge + table can never drift between them. Import from
# the sibling lib/ (synced as a scripts/ subdir, present in both source + installed
# trees). FAIL-SOFT: a catastrophic import failure falls back to the inline copy so
# a boot is NEVER broken (the parity-tested copy is degraded-mode only). Compile-time
# may tighten (never loosen); may_act_from is the Authority axis, may_quote the
# Citation axis.
_LIB = Path(__file__).resolve().parent / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
try:
    from fragment_contract import AUTHORITY_DEFAULTS, badge as _shared_badge  # type: ignore
except Exception:
    _shared_badge = None
    # boot-safety fallback ONLY (used iff the shared contract import fails); kept
    # byte-equal to fragment_contract.AUTHORITY_DEFAULTS and guarded by a parity test.
    AUTHORITY_DEFAULTS = {
        "YOURS":     dict(may_read=True, may_shape_interpretation=True, may_act_from=True,  may_mutate_source=True,  may_quote=True,  must_escalate=False, weight=0.90),
        "OFFICE":    dict(may_read=True, may_shape_interpretation=True, may_act_from=True,  may_mutate_source=True,  may_quote=True,  must_escalate=False, weight=0.88),
        "SUBSTRATE": dict(may_read=True, may_shape_interpretation=True, may_act_from=False, may_mutate_source=False, may_quote=True,  must_escalate=False, weight=0.82),
        "ESCALATE":  dict(may_read=True, may_shape_interpretation=True, may_act_from=False, may_mutate_source=False, may_quote=True,  must_escalate=True,  weight=0.75),
        "APOPHATIC": dict(may_read=True, may_shape_interpretation=True, may_act_from=False, may_mutate_source=False, may_quote=True,  must_escalate=False, weight=0.72),
        "COUNTER":   dict(may_read=True, may_shape_interpretation=True, may_act_from=False, may_mutate_source=False, may_quote=True,  must_escalate=False, weight=0.62),
        "PEER":      dict(may_read=True, may_shape_interpretation=True, may_act_from=False, may_mutate_source=False, may_quote=True,  must_escalate=False, weight=0.55),
        "FIELD":     dict(may_read=True, may_shape_interpretation=True, may_act_from=False, may_mutate_source=False, may_quote=False, must_escalate=False, weight=0.45),
        "ANCESTOR":  dict(may_read=True, may_shape_interpretation=True, may_act_from=False, may_mutate_source=False, may_quote=True,  must_escalate=False, weight=0.40),
        "SEALED":    dict(may_read=True, may_shape_interpretation=True, may_act_from=False, may_mutate_source=False, may_quote=False, must_escalate=False, weight=0.30),
    }


# Compact authority badge for the human face — delegates to the shared contract
# renderer; the inline algorithm is the boot-safety fallback (kept byte-equal).
def _badge(cls: str, auth: dict, gated: bool = False) -> str:
    if _shared_badge is not None:
        return _shared_badge(cls, auth, gated)
    bits = []
    bits.append("act" if auth["may_act_from"] else "shape-only")
    if not auth["may_quote"]:
        bits.append("no-cite")
    if auth["must_escalate"]:
        bits.append("ESCALATE↑")
    if not auth["may_mutate_source"] and auth["may_act_from"]:
        bits.append("no-mutate")
    if gated:
        # GATED sub-badge (REQ-2): a YOURS obligation whose execution would widen a Phase-A
        # boundary — authorized to carry, NOT authorized to silently widen. Route through /review.
        bits.append("GATED")
    return f"⟨{cls}·{'·'.join(bits)}⟩"


def _boot_receipt_path(zone_root: Path) -> str:
    """Resolve the boot-receipt.py sink path (source sibling, then installed).
    Returned as a runnable string for the receipt-request framing; the booting
    context runs whichever exists. Source is preferred (the live hook fires from
    $CLAUDE_PROJECT_DIR/...), installed is the ~/.claude fallback."""
    here = Path(__file__).resolve().parent
    for cand in (here / "boot-receipt.py",
                 Path.home() / ".claude" / "cgg-runtime" / "scripts" / "boot-receipt.py"):
        if cand.is_file():
            return str(cand)
    # last resort: a zone-relative path (may not exist, but points the right way)
    return str(zone_root / "canonical_developer" / "context-grapple-gun"
               / "cgg-runtime" / "scripts" / "boot-receipt.py")


def render_receipt_frame(office: str, tic: int, disp: str, zone_root: Path) -> str:
    """The receipt-REQUEST framing — explicit, warm, and DELIBERATELY budget-exempt.

    This is NOT the worldview body and is NOT counted against --max-chars. It is the
    first-response ritual that closes the Citizen-Boot Composite loop: prove you crossed
    the boot threshold consciously (did not collapse the badges) before touching
    governance. The sink (boot-receipt.py emit) verifies + greets back. The greeting sets
    session tone; the ledger (boot-receipts.jsonl) populates the long-run receipt lane."""
    rp = _boot_receipt_path(zone_root)
    return (
        "\n━━━ BOOT RECEIPT · your first response closes the boot loop "
        "(framing — NOT counted against the worldview budget) ━━━\n"
        f"Good morning, {disp}. You booted from a compiled civic orientation, not a memory "
        "paste. Before you touch governance, prove you did not collapse the badges — emit "
        "your receipt; the sink verifies it and greets you back:\n"
        f"  python3 {rp} emit --entity {office} --tic {tic} \\\n"
        '    --understood "…" --constraint "…" --abstention "…" '
        '--first-action "…" --route "cadence/review" \\\n'
        '    --model "<your model id, e.g. claude-opus-4-8>"\n'
        "  owed: understood_scope · accepted_constraints · abstentions · "
        "first_action_or_escalation\n"
        "  (signer = --entity; model = --model — two distinct fields, never a "
        "conflated 'entity-modelcode' signature)"
    )


def _zone_root(start: Path, explicit: str = None):
    if explicit:
        ep = Path(explicit)
        if (ep / ".ticzone").is_file():
            return ep
    for p in [start, *start.parents]:
        if (p / ".ticzone").is_file():
            return p
    cwd = Path.cwd()
    for p in [cwd, *cwd.parents]:
        if (p / ".ticzone").is_file():
            return p
    return None


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None


def _frag(zone_root: Path, fid: str, source: str, text: str, cls: str,
          reason: str, weight: float = None, receipt: bool = None,
          boost: str = None, suppress: str = None, gated: bool = False,
          **auth_override) -> dict:
    """Build a typed worldview_fragment with class-default authority (tightenable).

    gated=True marks a YOURS obligation whose execution would widen a Phase-A boundary
    (REQ-2): the office carries it but may NOT silently widen — it routes through /review."""
    auth = dict(AUTHORITY_DEFAULTS.get(cls, AUTHORITY_DEFAULTS["FIELD"]))
    w = auth.pop("weight")
    auth.update({k: v for k, v in auth_override.items() if k in auth})
    # receipt required for classes where mis-handling is costly, unless overridden
    req = receipt if receipt is not None else cls in ("SEALED", "ESCALATE", "COUNTER", "OFFICE", "YOURS")
    frag = {
        "id": fid,
        "source": source,
        "text": text,
        "pertinence": {"class": cls, "reason": reason},
        "authority": auth,
        "methylation": {"weight": round(weight if weight is not None else w, 2),
                        "boost_reason": boost, "suppress_reason": suppress},
        "receipt": {"required": req,
                    "expected_proof": ["understood_scope", "accepted_constraints",
                                       "abstentions", "first_action_or_escalation"]},
    }
    if gated:
        frag["gated"] = True
    return frag


# ----- methylatable baseline (L1/L5) ---------------------------------------------

def _office_baseline(zone_root: Path, office: str, tic: int) -> dict:
    wv = zone_root / "audit-logs" / "boot-injections" / "worldview"
    override = _load_json(wv / f"tic-{tic}.{office}.json")
    if isinstance(override, dict) and override.get("office") == office:
        return override
    lanes = _load_json(wv / "office-lanes.json") or {}
    return (lanes.get("offices") or {}).get(office) or {}


def _is_primary_office(zone_root: Path, office: str) -> bool:
    reg = _load_json(zone_root / "autonomous_kernel" / "actor-registry.json")
    if not reg:
        return False
    actors = reg.get("actors", reg) if isinstance(reg, dict) else reg
    me = next((a for a in actors if isinstance(a, dict) and a.get("entity_id") == office), None) if isinstance(actors, list) else None
    return any(r in ((me or {}).get("roles") or []) for r in ("interactive_orchestrator", "session_lead"))


# ----- STANDING-CAP POLICY (full all-cell coverage, tic 399, Architect-approved) -----
# Every entity-state gets an injection; the PLANES it hydrates and the MAX authority
# (pertinence cap) scale to its standing. A non-citizen's act-fragments are tightened to the
# cap (tighten-not-loosen); an APOPHATIC boundary ("what you are NOT") is prepended. citizen
# = full worldview, no cap. Standing taxonomy: autonomous_kernel/entity-ontology.md (Seven
# Axes). `ephemeral` is the lifecycle axis, NOT a standing (tic-390/391 collision fix); the
# ephemeral COMPUTE leg has no standing and is injected at the harness dispatch seam, not here.
_ALL_PLANES = {"L0", "L1", "L2", "L3", "L4", "L5", "L6"}
STANDING_POLICY = {
    "citizen":             dict(cap=None,        planes=_ALL_PLANES,                    boundary=None),
    "resident":            dict(cap="SUBSTRATE", planes={"L0", "L1", "L2", "L3", "L4"}, boundary="you are a RESIDENT — limited standing; you participate, but you are NOT a citizen (no request/fulfill/decide rights)"),
    "recognized_body":     dict(cap="PEER",      planes={"L0", "L2", "L3", "L4"},       boundary="you are a RECOGNIZED BODY — a collective with formal standing, NOT an individual actor"),
    "registered_artifact": dict(cap="FIELD",     planes={"L1", "L3"},                   boundary="you are a REGISTERED ARTIFACT — tracked by the polity, NOT an actor; you carry no agency"),
    "guest":               dict(cap="FIELD",     planes={"L0", "L2"},                   boundary="you are a GUEST — external, minimal permissions, NOT a citizen; you arrived via the visa/Dock lane"),
    "task_scoped_worker":  dict(cap="FIELD",     planes={"L1", "L3"},                   boundary="you are a TASK-SCOPED WORKER — an internal delegated non-citizen; NO persistent identity, NO inbox, NO memory across spawns, NO inscription authority; your outputs are owned by your lead"),
}
# unknown/unmapped standing → most restrictive cell (fail-closed, never fail-open)
_DEFAULT_POLICY = dict(cap="FIELD", planes={"L3"}, boundary="standing unresolved — minimal hydration; you are NOT authorized to act; route upward")

_PLANE_BY_PREFIX = (
    ("harmony.", "L0"),
    ("lane.", "L1"), ("ki.", "L1"),
    ("office.", "L2"),
    ("rung.", "L3"),
    ("tic.", "L4"),
    ("arc.", "L5"),
    ("gated_arc.", "L6"), ("review.", "L6"), ("office_counter.", "L6"),
    ("standing.", "L0"),  # the boundary fragment rides with the framer
)


def _fragment_plane(fid: str) -> str:
    for pref, plane in _PLANE_BY_PREFIX:
        if fid.startswith(pref):
            return plane
    return "L?"


def _entity_standing(zone_root: Path, office: str) -> str:
    """The booting entity's standing (entity-ontology.md axis). Fail-closed to a non-citizen
    cell when unresolved — never silently grant citizen authority to an unknown entity."""
    reg = _load_json(zone_root / "autonomous_kernel" / "actor-registry.json")
    if not reg:
        return "task_scoped_worker"
    actors = reg.get("actors", reg) if isinstance(reg, dict) else reg
    me = next((a for a in actors if isinstance(a, dict) and a.get("entity_id") == office), None) if isinstance(actors, list) else None
    return (me or {}).get("standing", "task_scoped_worker")


def _apply_standing_policy(zone_root: Path, frags: list, standing: str) -> list:
    """Full-cell coverage: select planes + cap authority + prepend the APOPHATIC boundary,
    per the entity's standing. citizen = identity (no cap, all planes, no boundary)."""
    pol = STANDING_POLICY.get(standing, _DEFAULT_POLICY)
    if pol["cap"] is None and pol["planes"] == _ALL_PLANES and not pol["boundary"]:
        return frags  # citizen — full worldview unchanged
    cap_ceiling = AUTHORITY_DEFAULTS.get(pol["cap"]) if pol["cap"] else None
    kept = []
    # APOPHATIC boundary FIRST — "what you are NOT" is a citable constraint, not a drift
    if pol["boundary"]:
        kept.append(_frag(zone_root, "standing.boundary", "entity-ontology.md (standing policy)",
            pol["boundary"], "APOPHATIC",
            "your standing boundary — a definitional negation that prevents misclassification; "
            "cite it as a constraint, do not act past it"))
    for f in frags:
        if _fragment_plane(f["id"]) not in pol["planes"]:
            continue  # plane not hydrated for this standing
        if cap_ceiling is not None:
            a = f["authority"]
            for k in ("may_act_from", "may_mutate_source", "may_quote"):
                a[k] = bool(a.get(k)) and bool(cap_ceiling.get(k))  # tighten (AND), never loosen
        kept.append(f)
    return kept


# ----- THE COMPILER --------------------------------------------------------------

def compile_fragments(zone_root: Path, office: str, tic: int) -> list:
    """Produce the typed worldview_fragment list for (office, tic). Fail-soft per source."""
    frags = []
    base = _office_baseline(zone_root, office, tic)
    primary = _is_primary_office(zone_root, office)

    # --- L0 HARMONY (the framer; orientation only, non-citable by her own contract) ---
    try:
        hd = zone_root / "audit-logs" / "harmony"
        disp = _load_json(hd / f"disposition-tic-{tic}.json") or _load_json(hd / "disposition-current.json")
        if isinstance(disp, dict):
            d = disp.get("disposition") or {}
            if d.get("stance"):
                lens = "primary lens — calibrates your resolve directly" if primary else "primary lens projected onto your office — same cores, your centroid"
                frags.append(_frag(zone_root, "harmony.stance", f"harmony/disposition-tic-{tic}",
                    f"({lens}) stance: {d['stance']}", "SUBSTRATE",
                    "Harmony calibrates resolve; orientation only, hold the tension — do not flatten it",
                    may_quote=False, boost="framer of all interpretation"))
            if d.get("caution"):
                frags.append(_frag(zone_root, "harmony.caution", f"harmony/disposition-tic-{tic}",
                    f"backwards (don't collapse into): {d['caution']}", "COUNTER",
                    "the failure-shape behind this tic — diagnostic, do not emulate"))
            pc = disp.get("primaryContextCentroid") or {}
            avoid = list(dict.fromkeys(pc.get("collapseZones") or []))
            for r in disp.get("rays") or []:
                for z in (r.get("sourceCentroid") or {}).get("collapseZones") or []:
                    if z not in avoid:
                        avoid.append(z)
            if avoid:
                frags.append(_frag(zone_root, "harmony.collapse_zones", f"harmony/disposition-tic-{tic}",
                    "failure-shapes anchored behind: " + ", ".join(avoid[:6]), "COUNTER",
                    "collapse zones — use diagnostically, do not fall into them"))
            if d.get("invitation"):
                frags.append(_frag(zone_root, "harmony.invitation", f"harmony/disposition-tic-{tic}",
                    f"forwards (winch toward): {d['invitation']}", "FIELD",
                    "the orientation to winch toward — shapes, does not mandate"))
            if d.get("boundary"):
                frags.append(_frag(zone_root, "harmony.boundary", f"harmony/disposition-tic-{tic}",
                    f"constraint (unified core): {d['boundary']}", "SUBSTRATE",
                    "the active constraint — shapes all interpretation, not locally editable"))
    except Exception:
        pass

    # --- L1 SUBSTRATE: your lanes (YOURS) + binding KIs (SUBSTRATE) ---
    try:
        for i, ln in enumerate(base.get("substrate_lanes") or []):
            frags.append(_frag(zone_root, f"lane.{i}", "worldview/office-lanes.json", ln, "YOURS",
                "a lane you carry as your own purpose"))
        for i, ki in enumerate(base.get("load_bearing_kis") or []):
            frags.append(_frag(zone_root, f"ki.{i}", "federation/CLAUDE.md", ki, "SUBSTRATE",
                "federation Key Invariant binding your lane — shapes interpretation, follow the pointer for the body"))
    except Exception:
        pass

    # --- L2 TERRAIN: your role (OFFICE), who you answer to (ESCALATE), peers (PEER) ---
    try:
        reg = _load_json(zone_root / "autonomous_kernel" / "actor-registry.json")
        actors = (reg.get("actors", reg) if isinstance(reg, dict) else reg) if reg else []
        me = next((a for a in actors if isinstance(a, dict) and a.get("entity_id") == office), None) if isinstance(actors, list) else None
        if me:
            roles = ", ".join(me.get("roles") or []) or "?"
            standing = me.get("standing", "?")
            answers_to = me.get("accountability_owner") or me.get("parent_entity_id") or "?"
            frags.append(_frag(zone_root, "office.role", "autonomous_kernel/actor-registry.json",
                f"standing={standing} · roles={roles}", "OFFICE",
                "your role/aperture/obligations — authorizes action inside your office boundary"))
            frags.append(_frag(zone_root, "office.answers_to", "autonomous_kernel/actor-registry.json",
                f"you answer to {answers_to}", "ESCALATE",
                "your accountability owner — anything exceeding your authority routes here"))
            peers = sorted([a.get("entity_id") for a in actors
                if isinstance(a, dict) and a.get("entity_id") != office
                and a.get("standing") == standing and a.get("status") == "active"
                and a.get("entity_kind") == "agent"])[:10]
            if peers:
                frags.append(_frag(zone_root, "office.peers", "autonomous_kernel/actor-registry.json",
                    "peer offices (same standing): " + ", ".join(peers), "PEER",
                    "other offices at your standing — understand the relation; do not overwrite or impersonate"))
    except Exception:
        pass

    # --- L3 RUNG: governance chain (SUBSTRATE) ---
    try:
        lib = zone_root / "canonical_developer" / "context-grapple-gun" / "cgg-runtime" / "scripts" / "lib"
        sys.path.insert(0, str(lib))
        import load_doctrine_chain as ldc  # type: ignore
        meta = ldc.briefing_metadata(str(zone_root / "CLAUDE.md"))
        rungs = meta.get("rungs_found") if isinstance(meta, dict) else None
        if rungs:
            chain = " → ".join(r.get("rung", r.get("name", "?")) for r in rungs)
            frags.append(_frag(zone_root, "rung.chain", "load_doctrine_chain",
                f"governance chain: {chain} (doctrine=law; CLAUDE.md/ledger=surfaces; follow the pointer, do not assume the body)",
                "SUBSTRATE", "the rung chain beneath you — shapes all interpretation, not locally editable"))
    except Exception:
        pass

    # --- L4 TIC: the shared field (mandate → OFFICE/FIELD, signals → COUNTER/FIELD, mesh → PEER) ---
    try:
        al = zone_root / "audit-logs"
        mandate = _load_json(al / "mogul" / "mandates" / "current.json")
        if isinstance(mandate, dict):
            cyc = (mandate.get("cycle_request") or {}).get("run_now") or []
            actor_off = (mandate.get("actor") or {}).get("office") or ""
            mine = actor_off and (f"ent_{actor_off}" == office or actor_off == office)
            if cyc:
                # REQ-1 (GAP-1): a FIELD mandate fragment must carry its consumption-guard.
                # When the mandate is owned by another office (esp. Mogul, the headless cycle
                # consumer), the guard names WHO consumes it so the reading office does not
                # double-spawn. The pertinence class is already correct (FIELD·no-cite for a
                # mandate that isn't mine); REQ-1 adds the operational guard to the text.
                guard = ""
                if not mine:
                    owner = actor_off or "another office"
                    owner_disp = "Mogul" if owner in ("mogul", "ent_mogul") else owner
                    guard = f" — {owner_disp}-owned; do NOT double-spawn ({owner_disp} consumes it)"
                frags.append(_frag(zone_root, "tic.mandate", "mogul/mandates/current.json",
                    f"mandate[{mandate.get('status','?')}]: {', '.join(cyc)}{guard}",
                    "OFFICE" if mine else "FIELD",
                    "the current mandate is yours to consume" if mine else "another office's mandate — field context, understand but do not act on or re-spawn"))
        man = al / "signals" / "active-manifest.jsonl"
        if man.is_file():
            sigs = []
            for line in man.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line:
                    try: sigs.append(json.loads(line))
                    except ValueError: pass
            if sigs:
                loud = max(sigs, key=lambda s: s.get("effective_volume", s.get("volume", 0)))
                drift = "drift" in str(loud.get("signal_id", ""))
                frags.append(_frag(zone_root, "tic.signals", "signals/active-manifest.jsonl",
                    f"{len(sigs)} active · loudest {loud.get('signal_id','?')} (vol {loud.get('effective_volume', loud.get('volume','?'))}, band {loud.get('band','?')})",
                    "COUNTER" if drift else "FIELD",
                    "drift/warning shape — diagnostic" if drift else "shared signal field — context, triage is /siren/review's gate"))
        mesh = _cross_agent_mesh(zone_root, tic)
        if mesh:
            frags.append(_frag(zone_root, "tic.mesh", "agent-mailboxes",
                "offices live this tic: " + ", ".join(mesh) + " (your activity contributes back to this mesh)",
                "PEER", "the cross-agent mesh — conformation contribution; understand the relation, do not act on others' lanes"))
    except Exception:
        pass

    # --- L5 OFFICE: your active arcs (YOURS) ---
    try:
        for i, a in enumerate(base.get("active_arcs") or []):
            frags.append(_frag(zone_root, f"arc.{i}", "worldview/office-lanes.json", a, "YOURS",
                "your current active arc — part of your purpose this tic"))
    except Exception:
        pass

    # --- L6 PER-TIC OBLIGATIONS: gated arcs + active /review hold (YOURS·GATED) [REQ-2] ---
    # GAP-2: YOURS must hydrate per-tic obligations, not only standing roadmap arcs. Two kinds:
    #   (a) gated tasks — carry an explicit GATED sub-badge (do-not-silently-widen)
    #   (b) the active /review obligation when review_due_tic == current tic, with its holds
    try:
        for i, g in enumerate(base.get("gated_arcs") or []):
            frags.append(_frag(zone_root, f"gated_arc.{i}", "worldview/office-lanes.json", g, "YOURS",
                "a per-tic obligation whose execution would widen a Phase-A boundary — carry it, "
                "do not silently widen; route through /review", gated=True))
        # (b) /review obligation — source the due tic from the mandate's tic_context (fail-soft)
        mandate = _load_json(zone_root / "audit-logs" / "mogul" / "mandates" / "current.json")
        tcx = (mandate or {}).get("tic_context") or {}
        review_due = tcx.get("review_due_tic")
        if isinstance(review_due, int) and review_due <= tic + 1:
            holds = base.get("review_holds") or []
            hold_txt = ("; holds: " + " | ".join(holds)) if holds else ""
            due_word = "DUE this tic" if review_due == tic else f"due tic {review_due}"
            frags.append(_frag(zone_root, "review.obligation", "mogul/mandates/current.json",
                f"/review {review_due} {due_word} — extract+adjudicate born candidates{hold_txt}",
                "YOURS",
                "your active /review obligation — act on it, but the named holds are constraints "
                "you may not collapse", gated=True))
    except Exception:
        pass

    # --- L6 COUNTER: office-specific failure-shapes [REQ-3] ---
    # GAP-3: COUNTER must hydrate office-specific recent corrections (hedging-as-honesty,
    # grinding-to-compensate, correction-without-altitude-check) ALONGSIDE Harmony's generic
    # anchored collapse-zones. Source: methylatable per-office office_counters (in-zone).
    try:
        for i, c in enumerate(base.get("office_counters") or []):
            frags.append(_frag(zone_root, f"office_counter.{i}", "worldview/office-lanes.json", c,
                "COUNTER",
                "an office-specific failure-shape recently corrected — diagnostic, do not re-enact"))
    except Exception:
        pass

    # --- STANDING-CAP: full all-cell coverage (tic 399). Select planes + cap authority +
    # prepend the APOPHATIC boundary per the entity's standing. citizen = unchanged. ---
    try:
        standing = _entity_standing(zone_root, office)
        frags = _apply_standing_policy(zone_root, frags, standing)
    except Exception:
        pass

    return frags


def _cross_agent_mesh(zone_root: Path, tic: int) -> list:
    live = set()
    mandate = _load_json(zone_root / "audit-logs" / "mogul" / "mandates" / "current.json")
    if isinstance(mandate, dict):
        off = (mandate.get("actor") or {}).get("office")
        if off:
            live.add(f"ent_{off}" if not str(off).startswith("ent_") else str(off))
    mb = zone_root / "audit-logs" / "agent-mailboxes"
    if mb.is_dir():
        try:
            import time
            now = time.time()
            for d in mb.iterdir():
                if not d.is_dir() or not d.name.startswith("ent_"):
                    continue
                for sub in ("inbound", "outbound", "processing"):
                    p = d / sub
                    if p.is_dir() and (now - p.stat().st_mtime) < 6 * 3600:
                        live.add(d.name)
                        break
        except OSError:
            pass
    return sorted(live)[:8]


# ----- RENDER FACES --------------------------------------------------------------

# Group order for the human face: framer + yours first, then office authority, then the wider field.
_CLASS_ORDER = ["SUBSTRATE", "YOURS", "OFFICE", "ESCALATE", "APOPHATIC", "PEER", "FIELD", "COUNTER", "ANCESTOR", "SEALED"]


def render_human(office: str, tic: int, base: dict, frags: list, max_chars: int,
                 zone_root: Path = None, receipt_frame: bool = True) -> str:
    if not frags:
        return ""
    disp = base.get("display", office)
    head = (
        f"[WORLDVIEW — {disp} @ tic {tic}] — a compiled PERTINENCE map, not instructions. "
        "Each line carries a class + authority badge: ⟨CLASS·act|shape-only·no-cite·ESCALATE↑⟩. "
        "Pertinence ≠ authority ≠ citation: some of this is yours to act on, some only to understand, "
        "some not to quote. Hold it; honor the badges; close the receipt."
    )
    by_class = {}
    for f in frags:
        by_class.setdefault(f["pertinence"]["class"], []).append(f)
    lines = [head]
    for cls in _CLASS_ORDER:
        items = by_class.get(cls)
        if not items:
            continue
        for f in items:
            lines.append(f"  {_badge(cls, f['authority'], f.get('gated', False))} {f['text']}")
    # compact in-body reminder (the explicit, command-bearing request frame is appended
    # AFTER truncation below so it can never be cut)
    need_receipt = sorted({f["id"] for f in frags if f["receipt"]["required"]})
    if need_receipt:
        lines.append("  ⟜ receipt owed: understood_scope · accepted_constraints · abstentions · first_action_or_escalation")
    body = "\n".join(lines)
    # --max-chars bounds the WORLDVIEW BODY only. Truncation is LINE-SAFE: badge-bearing
    # lines are atomic civic units — a half-cut line can read as a different ray (a
    # mangled ⟨YOURS·act⟩ is dangerous), so we cut at the last COMPLETE line that fits
    # and append an explicit SEALED boundary marker (Architect hardening, tic 332).
    if max_chars and len(body) > max_chars:
        sealed = ("  ⟨SEALED·shape-only⟩ worldview body truncated at budget boundary; "
                  "do not infer omitted rays")
        budget = max_chars - len(sealed) - 1  # reserve room for the marker line
        kept, used = [], 0
        for ln in lines:
            if used + len(ln) + 1 > budget:
                break
            kept.append(ln)
            used += len(ln) + 1
        if not kept:            # head alone overran budget — keep it anyway (never empty)
            kept = [lines[0]]
        kept.append(sealed)
        body = "\n".join(kept)
    # The receipt-request framing is DELIBERATELY budget-exempt — appended after the body
    # is bounded, so the loop-closing ritual is never truncated away (Architect, tic 332).
    if receipt_frame:
        body = body + "\n" + render_receipt_frame(office, tic, disp, zone_root or Path("."))
    return body


def render_json(office: str, tic: int, frags: list) -> str:
    return json.dumps({
        "schema": "boot-injections/worldview/pertinence-compiled@1",
        "office": office, "tic": tic,
        "axes": ["pertinence", "authority", "citation"],
        "fragments": frags,
    }, indent=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("--office", required=True)
    r.add_argument("--tic", type=int, required=True)
    r.add_argument("--format", choices=["human", "json"], default="human")
    r.add_argument("--zone-root", default=None)
    r.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    r.add_argument("--no-receipt-frame", dest="receipt_frame", action="store_false",
                   default=True, help="suppress the budget-exempt boot-receipt request framing")
    args = ap.parse_args()

    zone_root = _zone_root(Path(__file__).resolve().parent, args.zone_root)
    if zone_root is None:
        return 0
    try:
        frags = compile_fragments(zone_root, args.office, args.tic)
        if not frags:
            return 0
        if args.format == "json":
            text = render_json(args.office, args.tic, frags)
        else:
            base = _office_baseline(zone_root, args.office, args.tic)
            text = render_human(args.office, args.tic, base, frags, args.max_chars,
                                zone_root=zone_root, receipt_frame=args.receipt_frame)
    except Exception as e:
        sys.stderr.write(f"[office-worldview] compile error: {e}\n")
        return 0
    if text:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
