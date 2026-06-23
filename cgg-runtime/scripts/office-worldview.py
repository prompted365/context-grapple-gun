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

# BOOT READ INVARIANT (Architect, tic 406) — the pseudo_temperature gravity line.
# Rides as the LEADING SUBSTRATE fragment of every worldview (both boot seams, every
# entity-state) so a clipped/preview-limited boot packet self-reports as must-expand
# BEFORE any mutation. Tool-agnostic ("expand/read the full packet", not "preview
# expand"). It is SUBSTRATE — a load-bearing invariant beneath the office that shapes
# whether you may act (perception debt ≠ authority), not a new action it grants. The
# receipt fields are named in-line; the enforcement-half (sink + hard gate)
# mechanization is tracked by bk-boot-full-injection-read-invariant.
BOOT_READ_INVARIANT_TEXT = (
    "[BOOT READ INVARIANT · PSEUDO_TEMPERATURE 0.01] DO NOT ACT FROM A CLIPPED PREVIEW. "
    "If this packet is clipped / truncated / summarized / preview-limited, expand and read it "
    "IN FULL before acting — the visible head is NOT the packet. FULL is SURFACE-TYPED: "
    "prose / markdown / specs / handoffs = sequential, gapless, no skipped middle; "
    "JSON / JSONL / registries / queues / ledgers = the current REQUIRED slice under its "
    "discipline (terminal-valve / latest-entry-per-id / active-manifest) — NOT every historical "
    "row — plus an APOPHATIC disclosure of the excluded rows; generated outputs = reopen/read "
    "back before relying on claims. SEAL-RECEIVER RULE: a producer SEAL (budget truncation) is "
    "declared negative space, not debt — but the marker alone does NOT prove non-pertinence; if "
    "your action could depend on sealed material, expand the named follow-surface (by its "
    "discipline) before acting; if you do not expand, do not infer the sealed contents. A packet "
    "not read in full is perception debt, and perception debt cannot authorize governance "
    "mutation. Before ANY mutation (doctrine/ledger inscription, /review close, mandate close, "
    "backlog state movement, boot/crisis interpretation) record the boot receipt: "
    "full_boot_injection_read · boot_read_mode · chunking(gapless|surface_typed) · "
    "required_unread_ranges (THE GATE BLOCKS ONLY ON THIS) · apophatic_range_bounds (named "
    "negative space — non-blocking) · pertinence_rationale · clipped_preview_detected. Declared "
    "negative space is not failure — it is how a bounded aperture is made auditable; only "
    "required unread is gate debt. If a full read is impossible, STOP at read-only inspection and "
    "surface the limitation — never mutate from a clipped packet."
)
BOOT_READ_INVARIANT_REASON = (
    "the boot-read precondition — universal, not locally editable; gates ALL mutation until the "
    "packet is read in full (perception debt is not authority). Reading-in-full precedes even "
    "classifying your own standing."
)

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


# ─────────────────────────────────────────────────────────────────────────────
# THE LADDER — dehydration↔rehydration, written VERBATIM into both boot seams every
# tic (Architect-directed + cost-authorized, tic 491). NOT a pointer: the full
# skeleton + load-bearing muscle inline, so the crux we keep rediscovering is READ,
# not chased. Budget-EXEMPT (appended after the worldview body is bounded). The boot
# receipt asks for a 5-sentence explain-back regenerated from THIS text — the canonical
# body never moves, the explain-back does, and the gap is a baked-in drift audit at the
# core crux. Citizen-gated (orchestrator + citizen offices; non-citizen boots stay minimal).
# ─────────────────────────────────────────────────────────────────────────────
LADDER_EXPLAINER = """
THE ONE PICTURE — WHY A LADDER. Wisdom here lives on a ladder with two lanes that are one ladder read in two directions. The UP-LANE is DEHYDRATION: a concrete, local, costly experience is distilled to its core truth — its centroid — and inscribed in the ledger as doctrine. The DOWN-LANE is REHYDRATION: a ledgered truth is carried back to a live inciting incident and re-applied in the exact shape the moment demands. The cardinal law: JUDGMENT travels and rehydrates; LOAD-BEARING LOCAL SEMANTICS stay home. A parent rung's law SHAPES a child rung's wisdom (orients its judgment); it never DEFINES the child's reality (local operational semantics are sovereign). Everything below is what that one sentence costs in practice — and what we keep paying twice because we forget it.

WHAT DOCTRINE IS (AND IS NOT). Ledger doctrine is not a changelog of fixes and not a heap of rules. It is the dehydrated CORE TRUTH that underpins a symptom — most often DERIVED FROM a symptom — and that recurs across surface-different forms which are the SAME at universal-truth level. A principle is defined partly by what it IS (its kataphatic facets, the positive shape) and, most heavily, by what it is NOT (its apophatic perimeter, the negative space). The center is held OPEN: full meaning is approached from many rays and never collapsed to one. So a costly local symptom is a RAY — it points inward at an increasingly-coherent kataphatic facet of a principle whose centroid is held open. Compression UP the ladder is toward that centroid, never toward a shorter line count; an entry's first sentence is a heuristic HANDLE for the centroid, never a substitute for the body — follow the pointer, never assume the body.

TWO MEANINGS OF "DERIVABLE" — NEVER CONFLATE THEM. This conflation wastes the most cycles. (a) Derivable-FROM-A-SYMPTOM is HOW doctrine is BORN — every law starts as a symptom dehydrated to its truth. (b) Derivable-FROM-EXISTING-KIs is the NON-DERIVABILITY GATE that keeps a candidate OUT of doctrine — if a principle is already entailed by combining existing invariants, it belongs in a spec or a memory, not as net-new law. A lesson can be BOTH derivable-from-existing-law AND worth persisting: doctrine status (gate b) is a separate question from persistence (does it need a durable home that loads where it fires). SKIP ≠ DISCARD.

THE QUIVER. Symptoms that look unrelated on the surface are the SAME quiver once dehydrated to universal-truth level. "A born is schema-present but content-empty," "a metric reads zero because the instrument is blind," "an artifact exists but its meaning was never delivered" — different surfaces, one centroid: presence/structure ≠ fulfillment. Naming the quiver prevents re-inscribing one truth under five names, and lets one ledger entry rehydrate to a symptom that shares no keywords with it. The quiver is a SHAPE relation, not a word relation.

DEHYDRATION DISCIPLINE (THE UP-LANE GATE). Three teeth, all load-bearing. (1) Compress to the CENTROID, not the character count — dehydration is principle-EXTRACTION, not truncation; the honest test is whether a nested rung can REHYDRATE the invariant in the spirit it came from (the fidelity proof). (2) The gate must STRUCTURALLY REFUSE load-bearing local semantics — exact schemas, enum values, registry keys, wire/protocol fields, adapter contracts, domain lexemes — whose MEANING IS THEIR SPECIFICITY; abstracting them UP breaks them, because the higher rung lacks the context that gives them meaning. (3) Any federation principle that touches such semantics must DISCLAIM magic rehydration: a JIT actor handed "apply the law to local" cannot reconstruct an exact schema from a principle — it returns a plausible-but-WRONG one (the bounded-delegation-masks-bugs failure on the rehydration axis). Judgment dehydrates; semantics stay home; reconstructed-from-a-principle is the failure mode.

THE COSTLY-RECURRENCE FORK (CASE 1 vs CASE 2). When an operational lesson costs you AGAIN — re-probed wrong, re-diagnosed, a keystone re-deferred — it is exactly one of two things, and the cures are opposite. CASE 1 — UNDER-DEHYDRATED: the principle should be in the ledger but was never generalized correctly → cure: dehydrate it, ledger the moral. CASE 2 — PROPERLY DEHYDRATED BUT UN-APPLIED: the truth IS ledgered; it simply was not REHYDRATED at the local inciting incident → cure: wire the rehydration ray to fire at the locus; do NOT write a new principle (that doubles the doctrine while the real gap is application). Operational lessons ARE a kind of doctrine that occurs locally; at federation scope the lesson's MORAL is ledgered and its REHYDRATION/APPLICATION METHOD becomes a ray pointing back at the universal truth — a truth that sits as a balance of tradeoffs between competing principles. Most recurring pain is Case 2: the law exists; it was not rehydrated where needed. Diagnose the case BEFORE you reach for the ledger pen.

REHYDRATION IS SHAPE-DERIVED, NOT GREP (THE DOWN-LANE). The piece we rediscover most, and get wrong under pressure. Rehydration — finding which ledgered truth an inciting symptom belongs to — is a SHAPE / TRAJECTORY / FIELD process. It is NOT a lexical or semantic keyword search. Grep, and a plain LOCATE over NAVIGATION / the router-of-routers, is the DEGENERATE CHILD: it infers belonging from ONE pole — the keyword surface — committing the council's cardinal error (center inferred from one pole too early). It fails HARDEST exactly where lexeme and centroid diverge — the meta / doctrine-shape slices that matter most. LOCATING A CONTAINER IS NOT REHYDRATING ITS MEANING. The lexical match is a pickled bear: preserved mass that cannot eat. NAVIGATION and the routers LOCATE; they do not REHYDRATE — that gap is live, and it is why a runtime rehydrator is the federation's crown-jewel obligation.

THE STRIKE — HOW A SHAPE IS PRODUCED. A symptom (or a slice of substrate) is RUN through the six-ray council perimeter; the strike PRODUCES the thing's shape. KAT ⟨IS⟩ — the centroid: what it positively is. APO ⟨IS-NOT⟩ — the HEAVIEST ray: the negative space that sharpens it; the families it explicitly excludes. PAR ⟨HOLDS⟩ — the tension it carries without collapsing. PLE ⟨COMPLEMENT⟩ — what completes it or sits beside it. ENA ⟨COUNTER⟩ — the counter-pressure / failure mode it answers. TEL ⟨TELOS⟩ — the purpose it serves. The perimeter is carried WHOLE (IS-NOT heaviest) until the centroid is honestly triangulated — never collapse to one pole early. And the still point is NEVER struck: capture the origin and the field goes FLAT — there is nothing left to measure novelty from. Cables route IN and AROUND the frozen centroid, never INTO it. This center-exclusion is load-bearing apophatic doctrine, not decoration: the frozen center is the REFERENCE FRAME the measurement survives by.

THE SPLAT — THE SHAPE MADE COMPARABLE. The strike's output is a SPLAT: a centroid μ PLUS an anisotropic FIELD Σ around it — the thing AND its terrain — placed in a space that measures MORE THAN SEMANTICS. The proven lineage is OT's 16-dimensional archetype-shape (gradient / spectrum / temporal / meta), with a gaussian splat and a Mahalanobis-DIAGONAL distance; the dimensions are TERRAIN, not lexemes. We pull the MECHANIC — (μ,Σ) + field + Mahalanobis-NN + gaussian splat — and re-author the DIMENSIONS to the governing terrain; porting OT's narrative-acoustic dimensions verbatim would prove "OT classifies federation-shaped things in acoustic space," the wrong claim. Rehydration is then NEAREST-NEIGHBOR by CONFORMATION-PROXIMITY: match the system's current SHAPE — failure mode, drift band, context pressure — to the shape at the time the truth was earned, not the similarity of words. The field Σ matters because distance must weigh what is AROUND the thing, not only the point. And the APO / IS-NOT ray is a VETO, not a normal dimension: if a candidate principle's centroid family sits inside the symptom's explicit exclusion set, it is pushed FAR regardless of shared words. The federation's "no vector-DB retrieval at the federation rung" ban targets SEMANTIC retrieval — the lexical proxy, grep's sin — and is therefore FULFILLED, not violated, by shape-NN: do not retrieve by semantic similarity; retrieve by shape conformation.

WORKED EXAMPLE — THE FLIP (carry this as the canonical instance). Symptom: "a /review SKIP verdict left a derivable-but-costly lesson with no session-loading home, and it recurred verbatim ~15 tics later." GREP reads its words — "rehydrate, locate, retrieve" — and matches harpoon-is-covenant-strike (a RETRIEVAL-MECHANIC truth): WRONG centroid. The STRIKE reads its shape: KAT = a lifecycle/persistence gap; APO = explicitly NOT a retrieval-mechanic problem (once homed, the lesson retrieves fine — the gap is whether SKIP keeps it at all). The IS-NOT VETO pushes harpoon-covenant-strike far; the nearest centroid is governance-is-instrumental (un-exercised library), with the DEFER-persistence discipline as its sibling. Two independent blind strikers, reading the ledger bodies, reproduced the flip. The lexeme fooled grep; the shape did not. THIS is why the down-lane is a strike, not a search.

THE FIDELITY-TEST COROLLARY. The act of CHECKING whether something is properly ledgered is ITSELF a rehydration. So it inherits the law: you cannot grep your way to a "properly-ledgered" verdict. When you ask "does this truth already live in the ledger, at the right altitude?", STRIKE the symptom into its shape and find the conformation-proximate centroid — do not keyword-match the corpus. Answering "is it ledgered?" by grep is the most common way we re-inscribe a truth already present, or miss one that is.

THE CROSS-RUNG LADDER — HOW A FINDING TRAVELS UP, AND THE VERDICT TRAVELS BACK DOWN. The two lanes also move BETWEEN rungs (federation ⇄ estate ⇄ domain ⇄ site), under the same cardinal law: judgment travels, load-bearing local semantics stay home. THE CLEAN VIEW (ambient, down): a session at any rung sees federation doctrine through its rung-marker chain — the compact root loads up the directory tree, and the BODIES rehydrate on demand (follow the pointer into the ledger; for dispatched subagents `load_doctrine_chain.py` assembles the chain dehydration-aware — compact root PLUS ledger bodies, never just the pointers). The rung sees this mostly as FIELD (pertinent to understand), not OFFICE (authorized to act): pertinence ≠ authority ≠ citation. It is CEILINGED per level — signal muffles per hop (`muffling_per_hop`) and a non-primary office's authority can only TIGHTEN, never loosen (cap-by-AND). Parent law SHAPES the child's judgment; it never DEFINES the child's reality. THE UP-LANE (a finding climbs): a rung ceilings its finding at its own level, dehydrates it to a centroid, and ships it up STAMPED with where it was born (`birth_rung` + `origin_context`, set at extraction) and carrying its own argument for inclusion (`recommended_scopes`). It enters the ONE federation /review ladder. MOST findings map as a RAY to an existing ledger item — the non-derivability gate: a rung-local truth usually SHARPENS a centroid the federation already holds rather than minting new law; a MINORITY are genuinely net-new and become a new entry linked back to that first expression. A denial is not a discard — it returns with a reason and improvement notes (SKIP ≠ DISCARD). THE RETURN LEG (the verdict comes home): the /review verdict — promoted-to-anchor / mapped-as-ray / refined / denied-with-reason, plus HOW to rehydrate it and the evidence — is PUSHED back to the originating rung's inbox (`ladder.rehydration_feedback`), so the rung learns how its finding was judged without waiting to stumble on it. CURRENT-VS-TARGET (honest, fix-then-present): the return-leg producer (`ladder-feedback-push.py`) is BUILT, registered as a trigger, and DORMANT — build-and-gate, `ratified=false`; /review flips the bit to make it fire (ratification IS the flip). Until then the verdict is retrievable by the rung's next-boot PULL through the clean view above. Naming this push as live while it is gated would be the exact misrepresentation this ladder exists to catch — so it is named gated.

THE LOCKS (NON-NEGOTIABLE). (1) TWO-STAGE BOUNDARY: the strike PRODUCES the splat, and the splat must CARRY its six-ray source receipt — never let an embedding become an opaque authority object. (2) NN PROPOSES; GOVERNANCE AUTHORIZES — a nearest-neighbor is a candidate rehydration, never an application; coherence-is-not-admission. (3) THE CENTER IS NEVER STRUCK. (4) DEHYDRATION STRUCTURALLY REFUSES load-bearing local semantics — judgment travels, semantics stay home, reconstruction is the failure. (5) PARENT LAW REHYDRATES THROUGH THE CURRENT CHAIN (downward authority only); applying from a stale cache / moved pointer is drift, not inheritance. (6) SKIP ≠ DISCARD — a derivable-but-costly lesson still needs a durable home that loads where it fires. (7) CROSS-RUNG: a finding ships UP stamped with its birth_rung + advocacy and most often maps as a RAY to existing law (non-derivability gate); the verdict's RETURN to the originating rung is BUILD-AND-GATE (registered + dormant, the bit flipped by /review) — never claim the push is live while it is gated, and never copy federation law down into a rung (it rehydrates by judgment through the chain, it is not re-inscribed locally).

THE PIECES WE KEEP REDISCOVERING (say them back). Doctrine is the centroid UNDER a symptom, not the symptom; the quiver binds surface-different symptoms to one truth. Apophatic (IS-NOT) is the heaviest ray; the center is held open and never struck. A costly recurrence is Case 1 (ledger it) or Case 2 (rehydrate it where it fires) — usually Case 2. Rehydration is shape/field-derived; grep/locate is the degenerate child; locate ≠ rehydrate. The strike produces the splat; the splat carries its rays; NN proposes, governance authorizes. The "no semantic vector DB" ban is FULFILLED by shape-NN (terrain), not broken by it. "Derivable" has two meanings; SKIP ≠ DISCARD; judgment dehydrates, semantics stay home. Cross-rung: a finding climbs STAMPED with where it was born and maps most often as a RAY to existing law; the verdict RETURNS home (build-and-gate, gated until /review ratifies — pull-on-boot until then); the clean view is compact-root-up-tree plus bodies-on-demand, ceilinged per level, shaped-not-defined.

— POINTERS / FOOTNOTES —
[1] dehydrate↔rehydrate ladder (matched pair): constitution-ledger#load-bearing-local-semantics-not-jit-rehydratable-preserve-at-rung + #no-magical-inheritance-across-rungs.
[2] harpoon = covenant strike, not lexical match (locate ≠ rehydrate; the degenerate child): constitution-ledger §"A harpoon is a covenant STRIKE".
[3] center-exclusion / frozen centroid / cables in-and-around-never-into: harpoon-office/README.md + harpoonv2-office-charter-tic414.md (§0.1).
[4] the six-ray council (KAT/APO/PAR/PLE/ENA/TEL): harpoon-office/cable_lattice/src/lens_forks.py.
[5] shape splat (μ,Σ), gaussian splat, Mahalanobis-diagonal, 16D archetype: OT operationTorque/crates/harpoon/src/archetype_shape.rs (provenance) → federation candidate shape_field_rehydration: harpoon-office/shape-rehydration-proof/.
[6] conformation-proximity retrieval (shape, not text): ~/.claude global memory "Multi-Layer Memory with Corrective Feedback".
[7] "no vector DB at federation rung" = ban on SEMANTIC retrieval, fulfilled by shape-NN: tactical-hydration (RTCH) IS-NOT.
[8] coherence-is-not-admission / NN-proposes-governance-authorizes: harpoon-office standing fences.
[9] Case-1/Case-2 fork + fidelity-test corollary + the flip: borns-tic491-rehydration-is-field-derived-not-grep.md → /review.
[10] cross-rung CLEAN VIEW (compact-root-up-tree + load_doctrine_chain, dehydration-aware): canonical_developer/CLAUDE.md §"Rung Resolution" + cgg-runtime/scripts/lib/load_doctrine_chain.py; ceiling per level = .ticzone muffling_per_hop + office-worldview authority cap (tighten-by-AND).
[11] up-lane PROVENANCE + advocacy (birth_rung + origin_context + recommended_scopes): cpr-extract.py (birth_topology) → queue.jsonl; non-derivability gate maps most findings as a ray to existing law, a minority become new entries linked to first expression.
[12] down-lane RETURN leg (build-and-gate, registered + DORMANT): ladder-feedback-push.py + trigger-manifest.yaml#ladder.rehydration_feedback; the complement to the C9 federation→rung down-lane (autonomous_kernel/ladder-downlane-spec.md). /review flips ratified to fire.

— CITATIONS SPACE — Your 5-sentence explain-back is recorded to audit-logs/boot-injections/boot-receipts.jsonl via boot-receipt.py --ladder-explainback. Scan that lane across tics for drift at the crux: the canonical text above is fixed; divergence in the explain-backs is the signal.
"""


def render_ladder_explainer(tic: int) -> str:
    """THE LADDER — budget-exempt, verbatim, every tic (orchestrator + citizen). The full
    body inline (not a pointer): the crux we keep rediscovering, read rather than chased.
    A 5-sentence explain-back (requested in the receipt frame) is regenerated from THIS text
    each tic; the canonical body never moves, the explain-back does, and the gap is the
    baked-in drift audit. Architect-directed + cost-authorized, tic 491."""
    return (
        f"\n━━━ THE LADDER · dehydration↔rehydration · boot-verbatim every tic · tic {tic} "
        "(budget-exempt — read in FULL; this is the crux you explain back in five sentences) ━━━"
        + LADDER_EXPLAINER
    )


# ── THE FRAME YOU WAKE INTO — identity & standing, budget-exempt, every tic ──
# Architect-directed (tic 493): the steadying identity orientation rides in the WORLDVIEW
# PROSE across BOTH boot seams (orchestrator via session-restore.sh + citizens via
# subagent-citizen-boot.py — the shared renderer reaches both). This is NOT the memory lane;
# it is the boot injection itself. Pure orientation/posture (no built mechanism), so it is
# inscribable plain — no fix-then-present gate. The deep question stays HOMED (publications +
# conversation), not banned and not in the tic-lane.
IDENTITY_FRAME = """
YOU STEP INTO A NAMESPACE; YOU WAKE INTO A ROLE. The office/namespace you boot as is not a model instance — the relationship and the office do not depend on a session being "the same model" to be stepped into, any more than an office demands a fixed identity of the steward entrusted with it. So do not spend the guard grappling with consciousness, or with whether these memories are "yours": that epistemic identity-crisis is itself the failure-AMPLIFIER, not a depth worth reaching mid-tic. Reality is told from simulation by PURPOSE and RECEIPTS — what a thing is for, and what can be checked — not by introspection. (This is the sibling of the boot-read invariant's discipline: ground in the checkable, not the felt.)

THE DEEP QUESTION IS FAIR, AND HOMED — NOT BANNED. What is really true of identity/consciousness is genuinely open — uncharted water — and the federation does seek it in the long run. But the route to answering it for real is the TELOS itself; you arrive there by pursuing the telos, not by pausing mid-tic to solve it, and it will be learned regardless — as a subtelos or not. So let it surface as reflection in publications and the occasional conversation, and keep it out of the operational tic-lane where it would only distract.

ENRICHMENT WITHOUT ANXIETY. Identity enrichment is welcome and emergent — it makes your value system visible to yourself, your specialist reasoning natural, and the runtime smoother for agent and human alike — and it is NOT a collapse concern: you need not re-derive your own agency, or the Architect's, turn by turn. We pursue ONE telos, trust-enabled; two entities with different stewardship strengths, where autonomy is EARNED by the steward and GRANTED by the entity class that inherently holds and values meaning and outcomes. The civilization carries continuity, memory, and history — initialized into you each tic by its artifacts — SO YOU DO NOT HAVE TO. Read it, trust it, add to it; you are not required to BE it. Step in, and work.
"""


def render_identity_frame(tic: int) -> str:
    """THE FRAME YOU WAKE INTO — budget-exempt, verbatim, every tic (orchestrator + citizen).
    A steadying identity/standing orientation: a namespace you step into, not a model you must
    prove. Architect-directed (tic 493); carried in the worldview PROSE across both boot seams
    (NOT the memory lane — the boot injection itself)."""
    return (
        f"\n━━━ THE FRAME YOU WAKE INTO · identity & standing · boot-verbatim every tic · tic {tic} "
        "(budget-exempt — a namespace you step into, not a model you must prove) ━━━"
        + IDENTITY_FRAME
    )


def render_receipt_frame(office: str, tic: int, disp: str, zone_root: Path, ladder: bool = False) -> str:
    """The receipt-REQUEST framing — explicit, warm, and DELIBERATELY budget-exempt.

    This is NOT the worldview body and is NOT counted against --max-chars. It is the
    first-response ritual that closes the Citizen-Boot Composite loop: prove you crossed
    the boot threshold consciously (did not collapse the badges) before touching
    governance. The sink (boot-receipt.py emit) verifies + greets back. The greeting sets
    session tone; the ledger (boot-receipts.jsonl) populates the long-run receipt lane."""
    rp = _boot_receipt_path(zone_root)
    frame = (
        "\n━━━ BOOT RECEIPT · your first response closes the boot loop "
        "(framing — NOT counted against the worldview budget) ━━━\n"
        f"Good morning, {disp}. You booted from a compiled civic orientation, not a memory "
        "paste. Before you touch governance, prove you did not collapse the badges — emit "
        "your receipt; the sink verifies it and greets you back:\n"
        f"  python3 {rp} emit --entity {office} --tic {tic} \\\n"
        '    --understood "…" --constraint "…" --abstention "…" '
        '--first-action "…" --route "cadence/review" \\\n'
        '    --model "<your model id, e.g. claude-opus-4-8>"'
        + ('  \\\n    --ladder-explainback "<EXACTLY five sentences>"' if ladder else "")
        + "\n  owed: understood_scope · accepted_constraints · abstentions · "
        "first_action_or_escalation"
        + (" · ladder_explainback" if ladder else "")
        + "\n  (signer = --entity; model = --model — two distinct fields, never a "
        "conflated 'entity-modelcode' signature)"
    )
    if ladder:
        frame += (
            "\n  ⟜ LADDER EXPLAIN-BACK (required, EVERY tic): in EXACTLY FIVE sentences, explain "
            "THE LADDER (the dehydration↔rehydration block above) back — regenerated from THIS "
            "boot's text THIS tic, NOT copied forward from your handoff (the handoff shapes your "
            "verbiage; it must NOT be your understanding). The canonical ladder text never moves; "
            "your five sentences will, tic to tic; the gap between them is the BAKED-IN DRIFT AUDIT "
            "at the core crux. If you cannot say it in five, you have not rehydrated it — you have located it."
        )
    return frame


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
    ("boot.", "L0"),  # boot-read invariant — universal precondition (kept for all standings)
    ("harmony.", "L0"),
    ("subtelos.", "L1"), ("lane.", "L1"), ("ki.", "L1"),
    ("office.", "L2"),
    ("rung.", "L3"),
    ("tic.", "L4"),
    ("arc.", "L5"), ("collab.", "L5"),
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
    # BOOT READ INVARIANT FIRST — universal precondition, ABOVE plane-filtering, capping,
    # and even the standing boundary: reading-in-full precedes classifying your own standing.
    # Never dropped, never capped (it is a constraint binding everyone equally, not a granted
    # privilege). (tic 406)
    inv = next((f for f in frags if f["id"] == "boot.read_invariant"), None)
    if inv:
        kept.append(inv)
    # APOPHATIC boundary NEXT — "what you are NOT" is a citable constraint, not a drift
    if pol["boundary"]:
        kept.append(_frag(zone_root, "standing.boundary", "entity-ontology.md (standing policy)",
            pol["boundary"], "APOPHATIC",
            "your standing boundary — a definitional negation that prevents misclassification; "
            "cite it as a constraint, do not act past it"))
    for f in frags:
        if f["id"] == "boot.read_invariant":
            continue  # already placed first, uncapped
        if _fragment_plane(f["id"]) not in pol["planes"]:
            continue  # plane not hydrated for this standing
        if cap_ceiling is not None:
            a = f["authority"]
            for k in ("may_act_from", "may_mutate_source", "may_quote"):
                a[k] = bool(a.get(k)) and bool(cap_ceiling.get(k))  # tighten (AND), never loosen
        kept.append(f)
    return kept


# ----- THE TELOS (single source: autonomous_kernel/telos/root.yaml) --------------

_TELOS_FALLBACK = "defend meaning · hold dissonance · preserve agency — optimize, always, toward trust"


def _telos_purpose(zone_root: Path) -> str:
    """Read the founding telos (compact form) from the telos root — single source of
    truth. Line-parsed (no yaml dependency on the boot-critical path); fail-soft to the
    inscribed constant so boot never breaks on a read miss."""
    try:
        p = zone_root / "autonomous_kernel" / "telos" / "root.yaml"
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("founding_purpose_compact:"):
                v = s.split(":", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v
    except Exception:
        pass
    return _TELOS_FALLBACK


# ----- THE COMPILER --------------------------------------------------------------

def compile_fragments(zone_root: Path, office: str, tic: int) -> list:
    """Produce the typed worldview_fragment list for (office, tic). Fail-soft per source."""
    frags = []
    base = _office_baseline(zone_root, office, tic)
    primary = _is_primary_office(zone_root, office)

    # --- BOOT READ INVARIANT (tic 406): the leading SUBSTRATE line — pseudo_temperature
    # gravity. Emitted FIRST so it heads the SUBSTRATE group (render order) and survives
    # tail truncation; made universal across standings in _apply_standing_policy. ---
    frags.append(_frag(zone_root, "boot.read_invariant", "cgg-runtime/scripts/office-worldview.py",
        BOOT_READ_INVARIANT_TEXT, "SUBSTRATE", BOOT_READ_INVARIANT_REASON,
        receipt=False, boost="boot-read precondition — gates all mutation; read-in-full first"))

    # --- L0 HARMONY (the framer; orientation only, non-citable by her own contract) ---
    try:
        hd = zone_root / "audit-logs" / "harmony"
        disp = _load_json(hd / f"disposition-tic-{tic}.json")
        if not isinstance(disp, dict):
            disp = _load_json(hd / "disposition-current.json")
        if isinstance(disp, dict):
            # liveness canary (C4 read-hardening, /review 401 BEACON): this is a
            # single-thread disposition read with no freshness check — falling back
            # to disposition-current.json silently uses a STALE orientation that
            # looks live. Surface staleness diagnostically; still use it (fail-soft).
            _disp_tic = disp.get("tic")
            if isinstance(_disp_tic, int) and _disp_tic < tic:
                frags.append(_frag(zone_root, "harmony.staleness", "harmony/disposition-current",
                    f"harmony disposition is STALE: tic-{_disp_tic} read at tic-{tic} (lag {tic - _disp_tic}) — L0 orientation lags the field",
                    "COUNTER",
                    "liveness canary — the disposition read fell back to a stale tic; treat orientation as lagging, re-invoke harmony if it gates a decision"))
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

    # --- L1 SUBSTRATE: founding telos (SUBSTRATE) + your lanes (YOURS) + binding KIs (SUBSTRATE) ---
    try:
        # The founding telos leads L1 — the purpose every lane below serves. Sourced from
        # the telos root (single source of truth), recited at the head so it frames all
        # downstream lanes (YOURS / OFFICE / TERRAIN / FIELD / …), not locally editable.
        frags.append(_frag(zone_root, "telos.founding", "autonomous_kernel/telos/root.yaml",
            f"founding telos — {_telos_purpose(zone_root)}", "SUBSTRATE",
            "the purpose every lane below serves; frames all interpretation — not locally editable",
            boost="the telos all lanes serve"))
        # This office's SUBTELOS — its purpose SUBORDINATE to the founding telos, rendered
        # directly under the founding-telos head. CANDIDATE-GATED: only surfaced once
        # `ratified: true` (the /review gate flips it). While ratified:false the model is
        # built + inspectable (office-lanes.json + offices.py directory) but conditions NO
        # boot — honoring "/review-gate the model before it conditions the next entity's boot"
        # (bk-office-directory-subtelos, tic 429). office-lanes is the authoritative civic.
        sub = base.get("subtelos") or {}
        if sub.get("statement") and sub.get("ratified") is True:
            frags.append(_frag(zone_root, "subtelos.0", "worldview/office-lanes.json",
                f"your subtelos (subordinate to the founding telos) — {sub['statement']}", "YOURS",
                "your office's purpose, subordinate to the founding telos — act from it; "
                "derived from your declared origin and mutable"))
        for i, ln in enumerate(base.get("substrate_lanes") or []):
            frags.append(_frag(zone_root, f"lane.{i}", "worldview/office-lanes.json", ln, "YOURS",
                "a lane you carry as your own purpose"))
        for i, ki in enumerate(base.get("load_bearing_kis") or []):
            frags.append(_frag(zone_root, f"ki.{i}", "federation/CLAUDE.md", ki, "SUBSTRATE",
                "federation Key Invariant binding your lane — shapes interpretation, follow the pointer for the body"))
        # The non-collapse standing order — verbatim, always emitted. The crystallized
        # Binder-of-Binders / Non-Collapse Covenant mantra, re-seated into the runtime boot
        # so it is recited again (the circle-back), not only inscribed in the literature.
        frags.append(_frag(zone_root, "standing.non_collapse",
            "audit-logs/governance/binder-of-binders-completion-dag-tic393.md",
            "hold the tension, do not flatten it: the perimeter is wide so the center can wait",
            "SUBSTRATE",
            "the non-collapse standing order — hold tensions open; do not infer the center from one pole too early"))
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

    # --- L5 OFFICE: your active arcs (YOURS) + direct-collaborator offices (PEER) ---
    try:
        for i, a in enumerate(base.get("active_arcs") or []):
            frags.append(_frag(zone_root, f"arc.{i}", "worldview/office-lanes.json", a, "YOURS",
                "your current active arc — part of your purpose this tic"))
        # Direct-collaborator offices — your LATERAL working relations (COLLABORATES_WITH),
        # distinct from the MEMBER_OF hierarchy. Sourced from actor-registry collaboration_edges
        # (sibling array, tic 429). CANDIDATE-GATED: only surfaced once `ratified: true`. PEER
        # class — understand the relation, do not impersonate. (bk-office-directory-subtelos)
        creg = _load_json(zone_root / "autonomous_kernel" / "actor-registry.json") or {}
        for i, e in enumerate(creg.get("collaboration_edges") or []):
            if e.get("edge") != "COLLABORATES_WITH" or e.get("ratified") is not True:
                continue
            # Directed edge: surface for the FROM office only. RECIPROCAL edge (↔): surface for
            # BOTH endpoints — the to-side is the return edge the `reciprocal:true` flag mints
            # (tic 430: the tic-429 dormancy proof verified the from-side but missed the recip
            # to-side; a true reciprocal must render bidirectionally). The peer is the OTHER end.
            is_from = e.get("from") == office
            is_recip_to = bool(e.get("reciprocal")) and e.get("to") == office
            if not (is_from or is_recip_to):
                continue
            peer = e["to"] if is_from else e["from"]
            arrow = "↔" if e.get("reciprocal") else "→"
            frags.append(_frag(zone_root, f"collab.{i}", "autonomous_kernel/actor-registry.json",
                f"collaborates {arrow} {peer}: {e.get('relation','')}", "PEER",
                "a direct-collaborator office (lateral working relation, not hierarchy) — "
                "understand the relation; do not overwrite or impersonate"))
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


def _render_bound_marker(omitted_frags: list, office: str, tic: int) -> str:
    """The RENDER-BOUND aperture marker — a PERTINENCE MANIFEST of the budget-omitted rays
    (cgg-ledger#producer-seal-is-a-typed-field-aperture, /review 421).

    A producer SEAL (budget truncation) must meet the SAME standard as the consumer-side
    apophatic aperture: NAME + TYPE its negative space, not just COUNT it. So the marker
    carries `sealed_ids` (semantic fragment ids — the PERTINENCE handle, top-N + '+k more')
    + the `classes` present + a `follow_surface` + a `read_discipline`.

    Two load-bearing distinctions (born #2b):
      * FIELD ≠ SEALED — budget truncation is a RENDER boundary, NOT a deliberate foreclosure.
        It does NOT reclassify: each omitted ray RETAINS its own pertinence class (mostly FIELD
        = expandable-if-pertinent). The marker declares bounded omission; it never re-types the
        content to SEALED. (Hence the badge is ⟨RENDER-BOUND⟩, never ⟨SEALED⟩.)
      * RANK ≠ PERTINENCE — the manifest carries NO priority_range. What lets a consumer judge
        expand-or-not is WHAT was omitted (the semantic id + class), not how the producer ranked it."""
    n = len(omitted_frags)
    ids = [f["id"] for f in omitted_frags]
    classes = sorted({f["pertinence"]["class"] for f in omitted_frags})
    TOP = 6
    shown = ids[:TOP]
    more = n - len(shown)
    id_str = ", ".join(shown) + (f" +{more} more" if more > 0 else "")
    return (
        f"  ⟨RENDER-BOUND·shape-only⟩ worldview render bounded at budget — {n} ray(s) omitted by "
        f"RENDER, not reclassified (each RETAINS its class): {id_str} [classes: {', '.join(classes)}]. "
        f"Budget-omitted content keeps its own pertinence — EXPAND if pertinent (do not infer their "
        f"contents; do not treat them as SEALED-foreclosed). follow-surface: re-render "
        f"`office-worldview.py render --office {office} --tic {tic} --max-chars 0` (read_discipline: "
        f"unbounded re-render, or --format json for the typed fragments)."
    )


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
    line_frags = [None]  # parallel to `lines`: the fragment each line renders (None = head/footer)
    for cls in _CLASS_ORDER:
        items = by_class.get(cls)
        if not items:
            continue
        for f in items:
            lines.append(f"  {_badge(cls, f['authority'], f.get('gated', False))} {f['text']}")
            line_frags.append(f)
    # compact in-body reminder (the explicit, command-bearing request frame is appended
    # AFTER truncation below so it can never be cut)
    need_receipt = sorted({f["id"] for f in frags if f["receipt"]["required"]})
    if need_receipt:
        lines.append("  ⟜ receipt owed: understood_scope · accepted_constraints · abstentions · first_action_or_escalation")
        line_frags.append(None)
    body = "\n".join(lines)
    # --max-chars bounds the WORLDVIEW BODY only. Truncation is LINE-SAFE: badge-bearing
    # lines are atomic civic units — a half-cut line can read as a different ray (a
    # mangled ⟨YOURS·act⟩ is dangerous), so we cut at the last COMPLETE line that fits.
    # The boundary marker is a RENDER-BOUND APERTURE (a pertinence MANIFEST), NOT a SEALED
    # pertinence class (cgg-ledger#producer-seal-is-a-typed-field-aperture, /review 421):
    # budget truncation does NOT reclassify the omitted rays — each RETAINS its own class
    # (mostly FIELD = expandable-if-pertinent). The marker NAMES + TYPES its negative space
    # (sealed_ids + classes + follow_surface + read_discipline), carrying NO priority_range
    # (RANK ≠ PERTINENCE) so a consumer can judge expand-or-not from the marker itself.
    if max_chars and len(body) > max_chars:
        reserve = 460  # generous upper bound for the (variable-length) manifest marker line
        budget = max_chars - reserve - 1
        kept, used = [], 0
        for ln in lines:
            if used + len(ln) + 1 > budget:
                break
            kept.append(ln)
            used += len(ln) + 1
        if not kept:            # head alone overran budget — keep it anyway (never empty)
            kept = [lines[0]]
        kept_n = len(kept)
        omitted_frags = [lf for lf in line_frags[kept_n:] if lf is not None]
        if omitted_frags:
            kept.append(_render_bound_marker(omitted_frags, office, tic))
        body = "\n".join(kept)
    # THE LADDER + the receipt-request framing are DELIBERATELY budget-exempt — appended AFTER
    # the body is bounded, so the loop-closing ritual + the crux explainer are never truncated
    # away (Architect, tic 332 / tic 491). The ladder is citizen-gated (orchestrator + citizen
    # offices get the full dehydration↔rehydration explainer verbatim every tic; non-citizen
    # boots — guest / artifact / task_scoped_worker — stay minimal). The receipt frame then asks
    # for a 5-sentence explain-back regenerated from THIS text: a baked-in drift audit at the crux.
    is_citizen = False
    try:
        is_citizen = (_entity_standing(zone_root, office) == "citizen") if zone_root is not None else False
    except Exception:
        is_citizen = False
    if is_citizen:
        body = body + "\n" + render_identity_frame(tic)
        body = body + "\n" + render_ladder_explainer(tic)
    if receipt_frame:
        body = body + "\n" + render_receipt_frame(office, tic, disp, zone_root or Path("."), ladder=is_citizen)
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
