#!/usr/bin/env python3
"""boot-receipt.py — the receipt SINK that closes the Citizen-Boot Composite loop.

The worldview compiler (office-worldview.py) emits a receipt OBLIGATION ("⟜ receipt
owed: ...") but, until now, there was nowhere for the receipt to LAND. This is that
sink: proof-of-boot-uptake, mapped to (entity, tic), append-only, concurrency-safe.

WHY a dedicated sink (not the mailbox receipts.jsonl):
  The mailbox indexes/receipts.jsonl is message-ACK/NACK scoped (keyed by message_id,
  closing an inbound trigger). A boot receipt is not a response to a message — it is
  the office proving it crossed the boot threshold consciously without collapsing the
  pertinence badges. Overloading the mailbox receipts surface would silently term-
  overload two receipt semantics (cf. ledger#semantic-identity-admission-gate). So the
  boot receipt lands co-located with the boot-injection lane it closes.

CONCURRENCY (the "many firing the same nanosecond" requirement):
  - Append-only JSONL; POSIX O_APPEND writes under PIPE_BUF are atomic across procs.
  - flock(LOCK_EX) serializes the read-existing-IDs + append within/across processes.
  - DETERMINISTIC ID = sha256(entity:tic:content_fingerprint)[:16]. Same office booting
    the same tic with the same understanding AND the same boot-read attestation =>
    identical id => dedups to ONE line. This is the same loop-guard as the boot-injection
    lane + the 200+ signal-loop class (deterministic-ID + dedup-at-write). Idempotent by
    construction — but idempotent on the WHOLE semantic record, not on a civic-only slice
    of it (see content_fingerprint below; tic 643 covenant).

USAGE:
  boot-receipt.py emit --entity ent_homeskillet --tic 329 --payload receipt.json
  boot-receipt.py emit --entity ent_x --tic 329 \
      --understood "..." --constraint "a" --constraint "b" \
      --abstention "x" --first-action "..." --route "cadence/review"
  # a NON-citizen boot whose worldview render carried no ladder content declines, typed
  # (/review 724) — recorded as a first-class state, never as a missing field:
  boot-receipt.py emit --entity ent_cpr_stepper --tic 724 ... \
      --ladder-declination "standing=resident render carried no ladder content"
  boot-receipt.py list --tic 329
  boot-receipt.py compact          # collapse same-id duplicates (dedup-at-read pass)

  # every subcommand takes --sink <path> to point the lane at a TEST/ISOLATION file
  # (flag-only, never an env var — see sink_path() for why the gate must not inherit it)
  boot-receipt.py emit --sink /tmp/fixture.jsonl --entity ent_x --tic 1 ...
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
import re
import sys
from pathlib import Path


def zone_root() -> Path:
    """Resolve the federation/zone root by walking up for audit-logs/."""
    p = Path(__file__).resolve()
    for anc in [p] + list(p.parents):
        if (anc / "audit-logs" / "boot-injections").is_dir():
            return anc
    # fallback: known canonical root
    cand = Path("/Users/breydentaylor/canonical")
    if (cand / "audit-logs" / "boot-injections").is_dir():
        return cand
    raise SystemExit("boot-receipt: could not locate zone root (audit-logs/boot-injections)")


def sink_path(root: Path, override: str = None) -> Path:
    """The receipt lane. `override` (the CLI `--sink` flag ONLY — deliberately NOT an
    environment variable) points the lane at a TEST/ISOLATION file so a fixture can prove
    emit / dedup / gate behaviour end-to-end without writing the real ledger.

    WHY FLAG-ONLY, NEVER ENV (this is load-bearing, not style): boot-read-gate.py invokes
    `boot-receipt.py gate-check` via subprocess.run, which INHERITS os.environ. An env-var
    sink override would therefore be inheritable by the fail-closed mutation gate — i.e. a
    silent gate bypass (point the env at a hand-written sink, every mutation allows). A CLI
    flag cannot reach the gate's fixed argv, so the hook always reads the real lane. This is
    Self-Locating Artifact Test Isolation (cgg-ledger#self-locating-artifact-test-isolation)
    applied to an ENFORCEMENT engine: pin the fixture root EXPLICITLY, never ambiently."""
    if override:
        return Path(override).expanduser().resolve()
    return root / "audit-logs" / "boot-injections" / "boot-receipts.jsonl"


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# The BOOT-READ ATTESTATION fields that participate in the dedup fingerprint (tic 643;
# covenant `boot_receipt_fingerprint_includes_boot_read_fields_tic635`, ADMITTED /review 635;
# source cpr_boot_receipt_fingerprint_excludes_boot_read_fields_tic422).
#
# THE DEFECT THIS CLOSES: the fingerprint keyed on the FOUR CIVIC fields ONLY. So a SECOND
# emit for the same (entity, tic) carrying identical civic fields but a DIFFERENT boot-read
# attestation — precisely the fields the mutation gate READS (boot_read_passes) — minted an
# IDENTICAL receipt_id, deduped, and was silently DROPPED. The honest agent who closed its
# civic boot loop first and then tried to append its full-read proof could not: its proof
# vanished into the dedup, the gate found no passing receipt, and the honest attestation
# self-DoS'd the very gate it was satisfying.
#
# THE FIX SHAPE — ADDITIVE, never replacing: the attestation sub-dict enters the fingerprint
# ONLY when at least one of these fields is PRESENT on the record. Consequences:
#   * a civic-only receipt hashes EXACTLY as it did pre-fix — every historical receipt_id in
#     boot-receipts.jsonl stays valid, and a civic-only re-emit still dedups to ONE line;
#   * a civic+attestation receipt mints a DISTINCT id and LANDS beside the civic-only row;
#   * two attestations that differ in ANY gate-read field are distinguishable, so a corrected
#     or widened attestation can always be appended.
# Coverage: every field boot_read_passes() reads, PLUS the observability attestation fields
# (clipped_preview_detected, the producer-seal observations) — the admission's target_state
# says "every semantically distinguishing boot-read field", not "every gate-blocking one".
# `omitted_ranges` is kept in the set because pre-tic-422 receipts carry it as the ONLY form.
_FINGERPRINT_ATTESTATION_FIELDS = (
    "full_boot_injection_read", "boot_read_mode", "chunking",
    "required_unread_ranges", "omitted_ranges", "apophatic_range_bounds",
    "pertinence_rationale", "clipped_preview_detected", "coverage_proof_alternate",
    "producer_bounded", "producer_bound_kind", "producer_follow_surface",
    "sealed_ids_observed",
)


def _fp_norm(v):
    """Order-insensitive normalization for list-valued attestation fields — mirrors the
    civic fields' sorted() treatment, so re-declaring the SAME set of ranges in a different
    order still dedups to one line. Non-list values pass through unchanged; a heterogeneous
    list that cannot be key-sorted is left as-is rather than raising (the fingerprint must
    never be the thing that crashes a boot receipt)."""
    if isinstance(v, list):
        try:
            return sorted(v, key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
        except (TypeError, ValueError):
            return v
    return v


def content_fingerprint(rec: dict) -> str:
    """Stable fingerprint over the SEMANTIC fields only (not timestamps/model/provenance).

    TWO layers, and the second is ADDITIVE (see _FINGERPRINT_ATTESTATION_FIELDS above):
      1. the four CIVIC fields — the boot-LOOP close. Always present.
      2. the BOOT-READ ATTESTATION fields — the mutation-GATE surface. Included under the
         `boot_read_attestation` key ONLY when the record carries at least one of them, so a
         civic-only record's digest is byte-identical to the pre-tic-643 algorithm.
    """
    sem = {
        "understood_scope": rec.get("understood_scope", ""),
        "accepted_constraints": sorted(rec.get("accepted_constraints", [])),
        "abstentions": sorted(rec.get("abstentions", [])),
        "first_action_or_escalation": rec.get("first_action_or_escalation", ""),
    }
    # presence-keyed, NOT value-keyed: `required_unread_ranges: null` (the three-state N/A)
    # is semantically distinct from the field being absent, and must stay distinguishable.
    attest = {k: _fp_norm(rec[k]) for k in _FINGERPRINT_ATTESTATION_FIELDS if k in rec}
    if attest:
        sem["boot_read_attestation"] = attest
    # A7-644 (bk-a7-explainback-fingerprint): the ladder explain-back is a SEMANTIC field —
    # the drift-audit lane keys on its per-tic regeneration — so a corrected re-emit that
    # differs ONLY in explainback must mint a distinct id, not dedup away. Presence-keyed
    # and additive like the attestation layer: records without it hash exactly as before.
    if "ladder_explainback" in rec:
        sem["ladder_explainback"] = rec["ladder_explainback"]
    # /review 724 (typed ladder declination): a DECLINED explain-back is a first-class semantic
    # state, so it participates in the fingerprint the same way the explain-back does — presence-
    # keyed and additive. Consequences mirror the tic-643 attestation layer exactly: a receipt
    # WITHOUT a declination hashes byte-identically to the pre-724 algorithm (every historical
    # receipt_id stays valid), and a declination that is later CORRECTED (different standing or
    # reason) mints a distinct id and LANDS beside the first rather than dedup-vanishing.
    if rec.get("ladder_explainback_declined"):
        sem["ladder_explainback_declined"] = {
            "reason": rec.get("ladder_declination_reason", ""),
            "standing": rec.get("ladder_declination_standing", ""),
        }
    blob = json.dumps(sem, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def receipt_id(entity: str, tic: int, fp: str) -> str:
    return hashlib.sha256(f"{entity}:{tic}:{fp}".encode("utf-8")).hexdigest()[:16]


# The four semantic fields a complete CIVIC boot receipt owes (the verification surface).
_OWED_FIELDS = ("understood_scope", "accepted_constraints", "abstentions",
                "first_action_or_escalation")

# The BOOT-READ fields (tic 406, bk-boot-full-injection-read-invariant; apophatic-aperture
# rename tic 422, /review-421-ratified): the mutation-gate owed surface. The civic fields above
# close the boot LOOP; these close the boot-READ precondition that gates governance mutation
# (perception debt cannot authorize mutation). The pass-state the NARROW + FAIL-CLOSED gate
# requires:
#   full_boot_injection_read == True  AND  boot_read_mode == "full"
#   AND chunking in {"gapless", "surface_typed"}  AND  required_unread_ranges == []
# APOPHATIC-APERTURE DISCIPLINE (cgg-ledger#apophatic-aperture-disclosure, /review 421): the
# gate blocks ONLY on `required_unread_ranges` (unread material INSIDE the required surface) —
# NEVER on declared negative space (`apophatic_range_bounds`). Declaring + typing the excluded
# rows is how a bounded aperture is made AUDITABLE, not a confession of failure. A ranged/partial
# read OWES that disclosure (the forcing function): `apophatic_range_bounds` + `pertinence_rationale`.
# SURFACE-TYPED READ (cgg-ledger#full-read-is-surface-typed): prose/markdown/spec reads are
# `gapless`; JSON/JSONL/registry reads are `surface_typed` (terminal-valve / latest-entry-per-id —
# the historical head under terminal-valve discipline is declared negative space, NOT gate debt).
# clipped_preview_detected is recorded for audit but does NOT block (a clip that was then
# expanded-and-read-in-full is a PASS — the point is reading in full, not never-clipped).
# The PRODUCER-SEAL OBSERVATION fields (producer_bounded · producer_bound_kind ·
# producer_follow_surface · sealed_ids_observed) record what the booting agent saw a producer
# SEAL (budget truncation, worldview/boot-injection); they are observability, never a gate input —
# a producer seal is declared negative space (cgg-ledger#producer-seal-is-a-typed-field-aperture).
# FINGERPRINT PARTICIPATION (tic 643): these fields — and the rest of the emitted boot-read
# block — now participate in content_fingerprint via _FINGERPRINT_ATTESTATION_FIELDS, so a
# second emit that ADDS or CORRECTS the attestation is no longer dedup-dropped.
_BOOT_READ_FIELDS = ("full_boot_injection_read", "boot_read_mode", "chunking",
                     "required_unread_ranges", "apophatic_range_bounds",
                     "pertinence_rationale", "clipped_preview_detected")
# legacy aliases honored on READ for backward-compat with pre-tic-422 receipts
_BOOT_READ_FIELDS_LEGACY = ("omitted_ranges",)


def _required_unread(rec: dict):
    """The gate-blocking coverage field. Backward-compatible: prefer the ratified name
    `required_unread_ranges`; fall back to the legacy `omitted_ranges` for receipts emitted
    before the tic-422 apophatic-aperture rename. Returns the value (list / None / missing→[])."""
    if "required_unread_ranges" in rec:
        return rec.get("required_unread_ranges")
    if "omitted_ranges" in rec:
        return rec.get("omitted_ranges")
    return []


# A boot-read range value "reads apophatic" (non-blocking render-bounded negative space) when it
# carries one of these self-identifying markers. The worldview RENDER-BOUND banner uses exactly this
# vocabulary ("N rays omitted by RENDER … expand if pertinent"), which is what primes an agent to
# reach for --omitted-range for material that is genuinely non-blocking.
_APOPHATIC_MARKERS = ("render", "omitted by", "budget", "expand if pertinent",
                      "expand-if-pertinent", "apophatic", "negative space", "field-class")


def classify_boot_read_ranges(required_unread_range, omitted_range):
    """Split boot-read range declarations into (BLOCKING required-unread, NON-BLOCKING apophatic).

    --required-unread-range is always BLOCKING (real unread inside the required surface).
    --omitted-range is a legacy alias whose NAME means render-bounded negative space. The tic-474
    guard merely WARNED while still filing every --omitted-range value as gate debt — a named footgun
    whose teeth stayed in (cpr_named_footgun_guard_leaves_sibling_site_unfixed_tic481). Here the
    classification is LOAD-BEARING: each --omitted-range value that self-reads apophatic (carries an
    _APOPHATIC_MARKERS token) is REROUTED to the non-blocking apophatic set instead of silently
    self-DoS'ing the boot it was closing; a non-apophatic value stays BLOCKING (legacy semantics
    preserved for genuine required-unread, recoverable via the loud emit-time warning).

    Returns (req_unread: list, rerouted_apophatic: list).
    """
    req_unread = list(required_unread_range or [])
    rerouted = []
    for v in (omitted_range or []):
        if any(m in str(v).lower() for m in _APOPHATIC_MARKERS):
            rerouted.append(v)
        else:
            req_unread.append(v)
    return req_unread, rerouted


# ── THE TYPED LADDER DECLINATION (/review 724) ────────────────────────────────────────────
# Ratified adjudication closing bk-worldview-ladder-retype-adjudication; parent doctrine
# cgg-ledger#boot-attestation-demand-must-be-capability-gated-to-worldview-content (/review 723).
#
# THE DEFECT: this sink demanded a ladder explain-back "regenerated from THIS boot's text" from
# every entity class, while office-worldview.py citizen-gates the LADDER block — so a NON-citizen
# standing (resident, recognized_body, registered_artifact, guest, task_scoped_worker) booted with
# ZERO ladder content at ANY budget and could only fabricate from memory (the copy-forward shape
# the drift audit exists to catch) or comply silently-not-at-all. Both outcomes are INVISIBLE in
# the corpus: a seat that was never HANDED the ladder is indistinguishable from a seat that carries
# it thinly, which corrupts the drift audit at its core crux.
#
# THE CURE (emitter/reader pair — office-worldview.py renders the withheld-ray line, this sink
# records it): decline-to-fabricate becomes a FIRST-CLASS, corpus-visible state. It is NEVER a
# missing field (the ladder was never in _OWED_FIELDS) and NEVER silently equal to absence — the
# ack, the emitted JSON, and the stored record all distinguish declined from simply-omitted.
# NOT a gate input: boot_read_passes() is untouched; the declination cannot block or unblock a
# mutation, exactly as the explain-back never could.
#
# The machine token the RENDER stamps into its withheld-ray line. Load-bearing, not prose: an agent
# that pastes the render's declination line into --ladder-explainback is REROUTED to the declination
# path rather than filing a fabricated-looking explain-back into the drift corpus. Same reroute
# discipline as classify_boot_read_ranges() above — keyed on an EXACT emitted token, never a fuzzy
# prose classifier (a genuine explain-back that happens to discuss declination is not misfiled,
# because the token is machine vocabulary the render emits, not language a human writes).
_LADDER_DECLINATION_TOKEN = "typed_declination"
_LADDER_STANDING_RE = re.compile(r"standing\s*=\s*([A-Za-z0-9_\-]+)")


def parse_ladder_declination(reason: str) -> dict:
    """Type a --ladder-declination reason string into the stored declination block.

    Returns the fields to merge onto the record. `ladder_declination_standing` is extracted
    from a `standing=<token>` clause when present (the form office-worldview.py emits) and is
    simply ABSENT when the reason does not carry one — fail-soft, never a fabricated standing.
    The raw reason is always preserved verbatim; the parse is an ADDITIVE index over it, never
    a replacement for it."""
    rec = {"ladder_explainback_declined": True,
           "ladder_declination_reason": reason}
    m = _LADDER_STANDING_RE.search(reason or "")
    if m:
        rec["ladder_declination_standing"] = m.group(1)
    return rec


def boot_read_passes(rec: dict) -> tuple:
    """(passes: bool, reason: str) for the boot-read mutation-gate pass-state.

    Apophatic-aperture discipline (/review 421): the gate keys on `required_unread_ranges`
    (real unread debt INSIDE the required surface), NEVER on `apophatic_range_bounds` (declared,
    typed negative space). A ranged read owes its disclosure; declared space owes its rationale."""
    if rec.get("full_boot_injection_read") is not True:
        return False, "full_boot_injection_read is not true"
    if rec.get("boot_read_mode") != "full":
        return False, f"boot_read_mode={rec.get('boot_read_mode')!r} (need 'full'; 'preview_only'/'not_available' block)"
    if rec.get("chunking") not in ("gapless", "surface_typed"):
        return False, f"chunking={rec.get('chunking')!r} (need 'gapless' for prose or 'surface_typed' for record-stores)"
    # A RANGED / partial read owes its apophatic disclosure: naming the excluded negative space
    # (apophatic_range_bounds) AND justifying that the aperture suffices (pertinence_rationale).
    # The forcing function — to fake it costs nearly the same work as doing it right.
    if rec.get("apophatic_range_bounds") is not None and not rec.get("pertinence_rationale"):
        return False, "apophatic_range_bounds declared without pertinence_rationale (a bounded aperture must justify its sufficiency)"
    # Three-state coverage gate (cgg-ledger#apophatic-aperture-disclosure):
    #   []        = measured clean coverage           -> PASS
    #   null/None = N/A / not line-computable          -> PASS only with an alternate coverage proof
    #               (else `null` becomes the new dodge that the rename was meant to close)
    #   non-empty = real unread debt in the required surface -> BLOCK
    ru = _required_unread(rec)
    if ru is None:
        if rec.get("coverage_proof_alternate"):
            return True, "required_unread_ranges N/A with alternate coverage proof (PASS)"
        return False, "required_unread_ranges is null without an alternate coverage proof (null is not a coverage dodge)"
    if ru:  # non-empty list (or truthy) = required surface left unread
        return False, f"required_unread_ranges non-empty ({ru})"
    return True, "boot-read receipt complete (full · surface-typed · required surface fully covered)"


def receipt_missing(rec: dict) -> list:
    """Verify the receipt carries all four owed CIVIC fields non-empty. Returns the list
    of missing/empty fields (empty list == complete). The verification half of the
    handshake — a receipt that proves uptake must actually carry the proof."""
    miss = []
    for k in _OWED_FIELDS:
        v = rec.get(k)
        if not v or (isinstance(v, (list, str)) and len(v) == 0):
            miss.append(k)
    return miss


def _read_records(path: Path) -> list:
    """All receipt records (raw, in file order). Fail-soft to []."""
    out = []
    if not path.exists():
        return out
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return out


def gate_decision(root: Path, entity: str, tic: int, path: str = None, sink: str = None) -> dict:
    """The boot-read mutation gate's CORE decision (one source; the hook is a thin shell).

    NARROW + FAIL-CLOSED: allow a governed mutation iff EITHER
      (1) a valid boot-read receipt exists for (entity, tic) (boot_read_passes), OR
      (2) a non-expired OVERRIDE receipt covers this (tic[, path]).
    PRECEDENCE (tic 407): a valid boot-read receipt is checked FIRST and OUTRANKS an
    override. The override is the fallback for when a clean full read cannot exist (clipped
    packet, unavailable injection) — not a substitute that pre-empts a genuine receipt. If
    the override were evaluated first, a stale/broad cadence-boundary override would MASK an
    honestly-emitted full-read receipt, reporting via='override' when the clean proof path
    was in fact satisfied (the exact mis-provenance observed at tic 407 entry). Clean proof
    wins; override only fills the gap when no clean proof is present.
    Else BLOCK. (This function only DECIDES; it never blocks the caller — the hook maps
    a non-allow decision to PreToolUse exit 2. Note: 'no receipt at all' => BLOCK, by
    design — missing perception proof is perception debt.)"""
    recs = [r for r in _read_records(sink_path(root, sink)) if r.get("tic") == tic]
    # (1) valid boot-read receipt — checked FIRST so a clean proof outranks any override
    for r in recs:
        if entity not in (r.get("entity_id"), r.get("actor")):
            continue
        ok, why = boot_read_passes(r)
        if ok:
            return {"allow": True, "via": "boot_read_receipt", "reason": why,
                    "receipt_id": r.get("receipt_id")}
    # (2) override path — explicit, audited, non-silent — only when NO clean receipt exists
    for r in recs:
        if r.get("override") is True and (r.get("entity_id") == entity or r.get("actor") == entity):
            scope = r.get("override_scope")
            tp = r.get("touched_path")
            # scope 'tic' covers any path this tic; a path-scoped override must match the path tail
            if scope in (None, "", "tic", "all") or not path or not tp or tp in path or path in tp:
                return {"allow": True, "via": "override", "reason": r.get("reason", ""),
                        "receipt_id": r.get("receipt_id")}
    # fail-closed
    near = next(((boot_read_passes(r)[1]) for r in recs
                 if entity in (r.get("entity_id"), r.get("actor"))), "no receipt for this (entity,tic)")
    return {"allow": False, "via": "none", "reason": near}


# Emitted into the agent's context the moment the receipt is turned in — a couple
# load-bearing lanes + a read-discipline tripwire. The receipt attests
# `boot_read_mode=full`; this tail is the perception-layer reminder that the
# attestation is a promise about the REQUIRED files (NAVIGATION whole/gapless;
# the bench-packet intake lane for any /review docket), not a formality.
_BOOT_CLOSE_TAIL = (
    "🧭 Load-bearing lanes: NAVIGATION.md is the router of routers — read it "
    "WHOLE & gapless before you build or ask 'where does X live?'; a /review docket "
    "comes ONLY through the bench-packet intake lane "
    "(borns → cpr-extract → queue.jsonl → cpr-enrichment-scanner → "
    "governance/enrichment → bench-packet-prep), never ad hoc grep. "
    "⚠️ IF YOU DIDNT READ THE REQUIRED FILES MANDATED TO BE READ IN FULL AND "
    "GAPLESS, YOU BETTER EITHER FIX THAT, OR MOVE FASTER THAN THE ARCHITECT's "
    "TAXIDERMY SWEEP... DONT BE A SLOPSKILLET, HOMESKILLET :)"
)


def greeting(entity: str, tic: int, missing: list, deduped: bool = False) -> str:
    """The warm form-ack that closes the boot loop and sets session tone.
    Complete + recorded -> good-morning greeting; incomplete -> gentle nudge;
    deduped -> welcome-back. This is the perception-layer reward for crossing the
    boot threshold consciously (the loop the rendered '⟜ receipt owed' opened)."""
    if missing:
        return (f"📋 receipt recorded for {entity} @ tic {tic}, but incomplete — "
                f"owed fields still empty: {', '.join(missing)}. "
                "Fill them and re-emit to close the loop cleanly.")
    if deduped:
        return (f"🌅 already on file — good to see you, {entity}. "
                f"Receipt for tic {tic} is closed. "
                f"🜂 hold the tension, do not flatten it: the perimeter is wide so the center can wait. "
                f"Have a great tic! "
                f"{_BOOT_CLOSE_TAIL}")
    return (f"🌅 receipt received — good morning, {entity}! "
            f"Boot loop closed for tic {tic}. "
            f"🜂 hold the tension, do not flatten it: the perimeter is wide so the center can wait. "
            f"Have a great tic! "
            f"{_BOOT_CLOSE_TAIL}")


def existing_ids(path: Path) -> set:
    ids = set()
    if not path.exists():
        return ids
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line).get("receipt_id"))
            except json.JSONDecodeError:
                continue
    return ids


def _sink_for(args, root: Path) -> Path:
    """Resolve the lane for this invocation, warning LOUDLY (never silently) when a
    non-default sink is in play — an isolation sink must never be mistaken for the real lane."""
    override = getattr(args, "sink", None)
    path = sink_path(root, override)
    if override:
        sys.stderr.write(f"⚠️  NON-DEFAULT SINK (test/isolation mode): {path}\n")
    return path


def emit(args) -> int:
    root = zone_root()
    path = _sink_for(args, root)
    path.parent.mkdir(parents=True, exist_ok=True)

    if args.payload:
        rec = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    else:
        rec = {
            "understood_scope": args.understood or "",
            "accepted_constraints": list(args.constraint or []),
            "abstentions": list(args.abstention or []),
            "first_action_or_escalation": args.first_action or "",
            "receipt_route": args.route or "",
        }
    rec["entity_id"] = args.entity
    rec["tic"] = args.tic
    rec.setdefault("booted_from", args.booted_from or "compiled_civic_orientation")
    rec.setdefault("model_of_record", args.model or os.environ.get("CGG_MODEL", "unknown"))
    # LADDER explain-back (tic 491): the baked-in drift-audit field. Recorded as-is; the canonical
    # ladder text is fixed in the worldview render, so divergence across these explain-backs (scanned
    # across tics in boot-receipts.jsonl) is the drift signal at the crux. Sentence count is
    # observability only — NEVER gate-blocking (a 4- or 6-sentence explain-back still records).
    # /review 724 — TYPED LADDER DECLINATION, resolved BEFORE the explain-back is recorded.
    # Two entry paths, both announced and never silent:
    #   (a) --ladder-declination — the explicit, typed flag (the render prescribes it);
    #   (b) REROUTE — an --ladder-explainback value carrying the render's machine token
    #       `typed_declination`, i.e. the agent pasted the withheld-ray line into the wrong
    #       flag. Filing that verbatim into the drift corpus would pollute exactly the lane
    #       this cures, so it is rerouted LOUDLY (same discipline as the --omitted-range
    #       apophatic reroute above).
    # PAYLOAD CONFLICT GUARD: a --payload carrying a real ladder_explainback ALONGSIDE
    # --ladder-declination is contradictory (you cannot both ground it and decline it). The
    # grounded explain-back is the stronger proof and WINS; the declination is dropped with a
    # loud warning rather than writing a record that claims both. (The CLI form of the conflict
    # is refused earlier by argparse's mutually-exclusive group.)
    _declination = getattr(args, "ladder_declination", None)
    _lb = getattr(args, "ladder_explainback", None)
    if _lb and _LADDER_DECLINATION_TOKEN in _lb:
        sys.stderr.write(
            "WARN boot-receipt: --ladder-explainback carries the render's machine token "
            f"'{_LADDER_DECLINATION_TOKEN}' — this is the WITHHELD-RAY line, not an explain-back. "
            "REROUTED to --ladder-declination (recorded as a typed declination, NOT filed into the "
            "drift-audit corpus). Prefer --ladder-declination directly.\n")
        _declination = _declination or _lb
        _lb = None
    if _declination and rec.get("ladder_explainback"):
        sys.stderr.write(
            "WARN boot-receipt: --ladder-declination given alongside a payload ladder_explainback — "
            "a grounded explain-back OUTRANKS a declination (you cannot both ground it and decline "
            "it). The declination is DROPPED; the explain-back stands.\n")
        _declination = None
    if _declination:
        rec.update(parse_ladder_declination(_declination))
    if _lb:
        rec["ladder_explainback"] = _lb
        # A2-711: allow closing quotes/brackets after terminal punctuation — a sentence ending
        # ."  .'  .)  .] must still split (the bare (?:\s|$) form undercounted doctrine-quoting
        # explain-backs, biasing the drift-audit lane against them).
        rec["ladder_explainback_sentence_count"] = len(
            [s for s in re.split(r"[.!?]+['\")\]”’]*(?:\s|$)", _lb.strip()) if s.strip()])
    # Boot-read fields (tic 406): present iff the caller supplied them (a payload may also
    # carry them). Recorded as-is; the gate evaluates them via boot_read_passes().
    if getattr(args, "boot_read_mode", None) is not None:
        rec["full_boot_injection_read"] = bool(args.full_boot_read)
        rec["boot_read_mode"] = args.boot_read_mode
        # surface-typed: prose=gapless, record-stores=surface_typed; default gapless for a full read
        rec["chunking"] = args.chunking or ("gapless" if args.boot_read_mode == "full" else "n/a")
        # the gate-blocking field: required unread INSIDE the required surface. --required-unread-range
        # is the ratified BLOCKING name; --omitted-range is the legacy alias whose NAME means
        # non-blocking render-bounded space. classify_boot_read_ranges() splits per-value: a value that
        # self-reads apophatic is REROUTED to the non-blocking apophatic field instead of silent gate debt
        # (tic 482 load-bearing fix; see the helper for the full rationale). Announced, never silent.
        req_unread, _rerouted = classify_boot_read_ranges(args.required_unread_range, args.omitted_range)
        if args.omitted_range:
            if _rerouted:
                sys.stderr.write(
                    f"WARN boot-receipt: {len(_rerouted)} --omitted-range value(s) read as RENDER-bounded "
                    "negative space and were REROUTED to apophatic_range_bounds (non-blocking), not filed as "
                    "gate debt. Prefer --apophatic-bound; apophatic space obligates --pertinence-rationale. "
                    "If any rerouted value is GENUINELY required-unread, re-emit with --required-unread-range.\n"
                )
            if len(req_unread) > len(list(args.required_unread_range or [])):
                sys.stderr.write(
                    "WARN boot-receipt: --omitted-range is a LEGACY BLOCKING ALIAS for --required-unread-range; "
                    "non-apophatic value(s) were filed as required_unread_ranges (gate debt). "
                    "Use --required-unread-range to be explicit.\n"
                )
        rec["required_unread_ranges"] = req_unread
        rec["omitted_ranges"] = req_unread  # back-compat mirror (blocking set only)
        # apophatic_range_bounds: the NAMED, TYPED negative space of a ranged read — non-blocking,
        # but REQUIRED for partial reads (and obligates pertinence_rationale). None = full read,
        # no excluded space declared. Includes any --omitted-range values rerouted above.
        _apophatic = list(args.apophatic_bound or []) + _rerouted
        if _apophatic:
            rec["apophatic_range_bounds"] = _apophatic
        if args.pertinence_rationale:
            rec["pertinence_rationale"] = args.pertinence_rationale
        if args.coverage_proof_alternate:
            rec["coverage_proof_alternate"] = args.coverage_proof_alternate
        # producer-seal OBSERVATION — what the agent saw a producer SEAL (budget truncation):
        # observability of declared negative space, NEVER a gate input.
        if args.producer_bounded:
            rec["producer_bounded"] = True
            if args.producer_bound_kind:
                rec["producer_bound_kind"] = args.producer_bound_kind
            if args.producer_follow_surface:
                rec["producer_follow_surface"] = args.producer_follow_surface
            if args.sealed_id:
                rec["sealed_ids_observed"] = list(args.sealed_id)
        rec["clipped_preview_detected"] = bool(args.clipped_preview)

    fp = content_fingerprint(rec)
    rid = receipt_id(args.entity, args.tic, fp)
    rec["content_fingerprint"] = fp[:16]
    rec["receipt_id"] = rid
    rec["created_at"] = now_iso()

    missing = receipt_missing(rec)

    lock = path.with_suffix(path.suffix + ".lock")
    with lock.open("w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            if rid in existing_ids(path):
                ack = greeting(args.entity, args.tic, missing, deduped=True)
                sys.stderr.write(ack + "\n")
                print(json.dumps({"status": "deduped", "receipt_id": rid,
                                  "entity": args.entity, "tic": args.tic,
                                  "missing_fields": missing, "ack": ack,
                                  "sink_override": bool(getattr(args, "sink", None)),
                                  "note": "identical boot receipt already recorded for this (entity,tic) "
                                          "— identical INCLUDING its boot-read attestation (tic 643)"}))
                return 0
            line = json.dumps(rec, ensure_ascii=False, sort_keys=True)
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644), "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)

    ack = greeting(args.entity, args.tic, missing)
    lb = rec.get("ladder_explainback")
    declined = bool(rec.get("ladder_explainback_declined"))
    if lb:
        ack += (f" 🪜 ladder explain-back recorded ({rec.get('ladder_explainback_sentence_count')} "
                "sentences) to the drift-audit lane.")
    elif declined:
        # /review 724: a DECLINED explain-back is a first-class recorded state — it must never
        # read as the plain no-explainback nudge below, and must never be counted as a missing
        # field. Declining to fabricate against a render that carried no ladder content IS the
        # correct behavior; the corpus now says so out loud.
        _st = rec.get("ladder_declination_standing")
        ack += (" 🪜 ladder explain-back DECLINED (typed) and RECORDED"
                + (f" · standing={_st}" if _st else "")
                + f": {rec.get('ladder_declination_reason')}"
                " — a first-class receipt state, NOT a missing field. The drift-audit lane counts"
                " this as declined-by-standing, never as silent non-compliance; refusing to"
                " fabricate against a render that carried no ladder content is correct.")
    else:
        ack += " 🪜 NOTE: no --ladder-explainback this tic — the crux drift-audit wants your 5 sentences every tic."
    sys.stderr.write(ack + "\n")
    try:
        sink_disp = str(path.relative_to(root))
    except ValueError:
        sink_disp = str(path)  # an isolation sink outside the zone
    out = {"status": "recorded", "receipt_id": rid, "entity": args.entity,
           "tic": args.tic, "sink": sink_disp,
           "sink_override": bool(getattr(args, "sink", None)),
           "missing_fields": missing, "ack": ack,
           "ladder_explainback_recorded": bool(lb)}
    # /review 724 — THREE distinguishable states on this axis, never two: recorded / declined /
    # absent. The declination keys are emitted ONLY when a declination is present, so an existing
    # --ladder-explainback (or plain) emit keeps a byte-identical stdout envelope; a declination-
    # aware consumer reads .get("ladder_explainback_declined", False). Presence-keyed, additive.
    if declined:
        out["ladder_explainback_declined"] = True
        out["ladder_declination_standing"] = rec.get("ladder_declination_standing")
        out["ladder_declination_reason"] = rec.get("ladder_declination_reason")
    print(json.dumps(out))
    return 0


def list_receipts(args) -> int:
    root = zone_root()
    path = _sink_for(args, root)
    if not path.exists():
        print("(no boot receipts yet)")
        return 0
    seen = {}
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if args.tic is not None and r.get("tic") != args.tic:
                continue
            seen[r.get("receipt_id")] = r  # latest-per-id
    for r in seen.values():
        print(f"[{r.get('tic')}] {r.get('entity_id'):20s} {r.get('receipt_id')} "
              f"route={r.get('receipt_route','-')} :: {r.get('first_action_or_escalation','')[:60]}")
    print(f"-- {len(seen)} unique receipt(s)" + (f" at tic {args.tic}" if args.tic is not None else ""))
    return 0


def compact(args) -> int:
    """Collapse same-id duplicates (latest-per-id), rewrite the sink atomically.

    NOTE (tic 643): 'same-id' means the STORED receipt_id — compact never recomputes a
    fingerprint, so widening content_fingerprint cannot retroactively collapse or split
    historical rows. Two rows for one (entity,tic) that differ in boot-read attestation are
    DISTINCT receipts, not duplicates, and compact correctly preserves both."""
    root = zone_root()
    path = _sink_for(args, root)
    if not path.exists():
        print("(nothing to compact)")
        return 0
    lock = path.with_suffix(path.suffix + ".lock")
    with lock.open("w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            seen = {}
            order = []
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    rid = r.get("receipt_id")
                    if rid not in seen:
                        order.append(rid)
                    seen[rid] = r
            tmp = path.with_suffix(".jsonl.tmp")
            with tmp.open("w", encoding="utf-8") as out:
                for rid in order:
                    out.write(json.dumps(seen[rid], ensure_ascii=False, sort_keys=True) + "\n")
            os.replace(tmp, path)
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
    print(json.dumps({"status": "compacted", "unique": len(order)}))
    return 0


def emit_override(args) -> int:
    """Emit an OVERRIDE receipt — the explicit, audited, NON-SILENT escape from the
    boot-read mutation gate (tic 406 spec). Carries actor/tic/reason/touched_path/
    timestamp/override_scope. The gate honors it; the audit trail records WHY a clipped
    or receipt-less boot was permitted to mutate. Never a silent bypass."""
    root = zone_root()
    path = _sink_for(args, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "override": True,
        "actor": args.actor,
        "entity_id": args.actor,
        "tic": args.tic,
        "reason": args.reason,
        "touched_path": args.touched_path or "",
        "override_scope": args.override_scope or "tic",
        "created_at": now_iso(),
        "model_of_record": args.model or os.environ.get("CGG_MODEL", "unknown"),
    }
    rec["receipt_id"] = receipt_id(args.actor, args.tic,
                                   hashlib.sha256(("override:" + (args.reason or "")).encode()).hexdigest())
    lock = path.with_suffix(path.suffix + ".lock")
    with lock.open("w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            if rec["receipt_id"] not in existing_ids(path):
                with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644), "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
    sys.stderr.write(f"⚠️  OVERRIDE receipt recorded for {args.actor} @ tic {args.tic} "
                     f"(scope={rec['override_scope']}): {args.reason}\n")
    print(json.dumps({"status": "override_recorded", "receipt_id": rec["receipt_id"],
                      "actor": args.actor, "tic": args.tic, "scope": rec["override_scope"]}))
    return 0


def gate_check(args) -> int:
    """Boot-read mutation-gate decision for (entity, tic[, path]). Prints JSON.
    Exit 0 = ALLOW, exit 3 = BLOCK (distinct from argparse's 2 so callers can tell a
    block from a usage error)."""
    root = zone_root()
    if getattr(args, "sink", None):
        sys.stderr.write(f"⚠️  NON-DEFAULT SINK (test/isolation mode): "
                         f"{sink_path(root, args.sink)}\n")
    d = gate_decision(root, args.entity, args.tic, args.path, getattr(args, "sink", None))
    d["sink_override"] = bool(getattr(args, "sink", None))
    print(json.dumps(d))
    return 0 if d.get("allow") else 3


def main():
    ap = argparse.ArgumentParser(description="Citizen-Boot receipt sink (concurrency-safe, tic-mapped).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def _add_sink(p):
        """--sink: point the lane at a TEST/ISOLATION file. FLAG-ONLY by design — an env
        var would be inherited by boot-read-gate.py's subprocess gate-check (a bypass).
        See sink_path()."""
        p.add_argument("--sink", default=None,
                       help="TEST/ISOLATION override for the receipts lane path "
                            "(default: <zone>/audit-logs/boot-injections/boot-receipts.jsonl). "
                            "Flag-only — never an env var; the mutation gate must not inherit it.")

    e = sub.add_parser("emit", help="record a boot receipt (idempotent per entity+tic+content)")
    e.add_argument("--entity", required=True)
    e.add_argument("--tic", type=int, required=True)
    e.add_argument("--payload", help="path to JSON file with receipt fields")
    e.add_argument("--understood")
    e.add_argument("--constraint", action="append")
    e.add_argument("--abstention", action="append")
    e.add_argument("--first-action", dest="first_action")
    e.add_argument("--route")
    e.add_argument("--booted-from", dest="booted_from")
    e.add_argument("--model")
    # LADDER explain-back (tic 491) — the 5-sentence regenerated-from-boot crux re-statement;
    # the baked-in drift-audit field. Recorded as-is; never gate-blocking (observability lane).
    # The explain-back and its typed DECLINATION are mutually exclusive by construction: you
    # cannot both ground the crux from THIS boot's text and declare that this boot carried none
    # (/review 724). argparse refuses the contradictory CLI form; the payload form is caught at
    # runtime in emit() where the grounded explain-back outranks.
    _ladder = e.add_mutually_exclusive_group()
    _ladder.add_argument("--ladder-explainback", dest="ladder_explainback",
                   help="EXACTLY five sentences explaining the dehydration↔rehydration ladder, "
                        "regenerated from THIS boot's worldview text (not copied from a handoff). "
                        "Recorded to the drift-audit lane; the canonical ladder text is fixed, so "
                        "divergence across explain-backs is the drift signal at the crux.")
    # TYPED LADDER DECLINATION (/review 724, closing bk-worldview-ladder-retype-adjudication).
    _ladder.add_argument("--ladder-declination", dest="ladder_declination",
                   help="decline the ladder explain-back as UNSERVABLE from this boot, with a "
                        "reason (e.g. \"standing=resident render carried no ladder content\"). "
                        "Use when office-worldview.py rendered the [LADDER RAY WITHHELD · "
                        "typed_declination] line: the ladder block is citizen-gated, so a "
                        "non-citizen standing carries NO ladder content at ANY budget and an "
                        "explain-back could only be fabricated from memory. Records "
                        "ladder_explainback_declined + the standing + the reason as a FIRST-CLASS "
                        "corpus state — never a missing field, never silently equal to absence, "
                        "and never a mutation-gate input.")
    # boot-read fields (tic 406) — supply --boot-read-mode to activate the boot-read block
    e.add_argument("--full-boot-read", dest="full_boot_read", action="store_true",
                   help="record full_boot_injection_read=true")
    e.add_argument("--boot-read-mode", choices=["full", "preview_only", "not_available"],
                   help="boot_read_mode (presence activates the boot-read fields)")
    e.add_argument("--chunking", choices=["gapless", "surface_typed", "partial", "n/a"],
                   help="prose/spec reads = 'gapless'; JSON/JSONL/registry reads = 'surface_typed' "
                        "(terminal-valve / latest-entry-per-id)")
    e.add_argument("--required-unread-range", dest="required_unread_range", action="append",
                   help="a range left UNREAD inside the REQUIRED surface (repeatable); none = clean "
                        "coverage. THE GATE BLOCKS ON THIS. (Ratified name; --omitted-range is the alias.)")
    e.add_argument("--omitted-range", dest="omitted_range", action="append",
                   help="[legacy alias for --required-unread-range] a range left unread (repeatable)")
    e.add_argument("--apophatic-bound", dest="apophatic_bound", action="append",
                   help="a NAMED, TYPED excluded negative-space bound for a ranged read (repeatable); "
                        "non-blocking but REQUIRED for partial reads (obligates --pertinence-rationale)")
    e.add_argument("--pertinence-rationale", dest="pertinence_rationale",
                   help="why the read aperture satisfies current pertinence (required when "
                        "--apophatic-bound is given)")
    e.add_argument("--coverage-proof-alternate", dest="coverage_proof_alternate",
                   help="an alternate coverage proof that lets required_unread_ranges=null PASS")
    e.add_argument("--producer-bounded", dest="producer_bounded", action="store_true",
                   help="record that a producer SEAL (budget truncation) was observed in the boot packet")
    e.add_argument("--producer-bound-kind", dest="producer_bound_kind",
                   help="the kind of producer bound observed (e.g. 'budget_truncation', 'worldview_seal')")
    e.add_argument("--producer-follow-surface", dest="producer_follow_surface",
                   help="the follow-surface the seal pointed at (e.g. 'audit-logs/boot-injections/active.jsonl')")
    e.add_argument("--sealed-id", dest="sealed_id", action="append",
                   help="a semantic id the producer sealed (repeatable) — the pertinence handle, NOT a priority")
    e.add_argument("--clipped-preview", dest="clipped_preview", action="store_true",
                   help="record clipped_preview_detected=true (informational; does not block)")
    _add_sink(e)
    e.set_defaults(func=emit)

    o = sub.add_parser("override", help="emit an audited, non-silent boot-read gate override")
    o.add_argument("--actor", required=True)
    o.add_argument("--tic", type=int, required=True)
    o.add_argument("--reason", required=True)
    o.add_argument("--touched-path", dest="touched_path")
    o.add_argument("--override-scope", dest="override_scope", default="tic",
                   help="'tic' (any path this tic) | a path substring | 'all'")
    o.add_argument("--model")
    _add_sink(o)
    o.set_defaults(func=emit_override)

    g = sub.add_parser("gate-check", help="boot-read mutation-gate decision (exit 0 allow / 3 block)")
    g.add_argument("--entity", required=True)
    g.add_argument("--tic", type=int, required=True)
    g.add_argument("--path", help="the surface being mutated (for path-scoped overrides)")
    _add_sink(g)
    g.set_defaults(func=gate_check)

    l = sub.add_parser("list", help="list receipts (optionally for a tic)")
    l.add_argument("--tic", type=int)
    _add_sink(l)
    l.set_defaults(func=list_receipts)

    c = sub.add_parser("compact", help="collapse same-id duplicates")
    _add_sink(c)
    c.set_defaults(func=compact)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
