#!/usr/bin/env python3
"""
Pattern Miner — topology-aware recurrence detection for governance artifacts.

Reads CPR queue, signals, and participation data. Detects recurring patterns
across sessions, subsystems, and rungs. Writes pattern recurrence events to
audit-logs/patterns/YYYY-MM-DD.jsonl.

Classifies recurrence with rung context:
  - site_local: repeated within one site
  - cross_site_same_domain: repeated across sibling sites in same domain
  - cross_domain_same_estate: repeated across domains in same estate
  - cross_estate: repeated across estates

This script is the canonical authority for recurrence detection. The enrichment
scanner imports from it rather than maintaining its own inline logic.

It is ALSO the second independent writer into audit-logs/cprs/queue.jsonl
(cogpr-ingest.py is the first). Everything it appends there passes the
write-boundary admission contract below: shape refusal, terminal-derivative
binding, and the full lifecycle-field stamp.

Usage:
    python3 pattern-miner.py --project-dir /path/to/zone
    python3 pattern-miner.py --project-dir /path/to/zone --dry-run
    python3 pattern-miner.py --project-dir /path/to/zone --json
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow importing zone_root from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zone_root import resolve_zone_root, load_ticzone, audit_logs_path, birth_topology
# Shared active-ray predicate (tic 403): heat-based, retires acknowledged-as-active.
from lib.signal_active import is_active_ray


# ---------------------------------------------------------------------------
# Write-boundary admission contract
# ---------------------------------------------------------------------------
# AUTHORIZED at /review 723 (bk-pattern-miner-write-boundary-shape-predicate +
# bk-ingest-path-lifecycle-field-parity), carrying the two laws promoted from the
# tic-720 live event:
#   cgg-ledger#guarded-multi-writer-surface-carries-closed-producer-set-obligation
#     (cpr_mogul_pattern_mining_4805ae1ab6a4) — a shape-refusal cure installed at
#     ONE intake gate protects only the producers routing through THAT gate; a
#     guarded surface with MULTIPLE INDEPENDENT WRITERS carries a closed PRODUCER
#     -set obligation exactly as a relocated surface carries a closed consumer-set
#     one. cogpr-ingest.py was cured at tic 716; this writer was not, and at tic
#     720 it re-minted the same defect class the other gate already refuses.
#   cgg-ledger#recurrence-measure-invalid-over-shared-generator-corpus
#     (cpr_mogul_pattern_mining_86066d71a903) — a recurrence measure is valid only
#     over a corpus of INDEPENDENTLY AUTHORED records; where records share a
#     generator it measures the GENERATOR's repetition rate, not the system's
#     learning.
# Lane fence (unchanged): the id-keyed dedup in emit_pattern_envelopes stays
# id-keyed ONLY. These gates guard payload SHAPE and payload DERIVATION — never
# content similarity, which is judgment and stays with the cpr-stepper seat.

# Terminal states: an id whose LATEST-per-id status is one of these is a SETTLED
# CPR. Same content as cogpr-ingest.TERMINAL_STATUSES / bench-packet-prep's set —
# deliberately shared so the two queue writers cannot disagree about what
# "settled" means at their respective write boundaries.
TERMINAL_STATUSES = frozenset({
    "promoted", "absorbed", "superseded", "rejected",
    "deferred", "dismissed", "resolved", "skipped",
})

# The candidate-carrier field name. SHARED CONTENT with cogpr-ingest._CARRIER_FIELD
# by design (engine-content separation: the engine below is this file's, the
# content is the federation's one carrier-field name — a term-list, not logic).
# A payload naming its own carrier envelope's field is an intra-document
# cross-reference — "See top-level candidate_cogprs — 2 candidates …" — not a
# self-contained lesson: read divorced from the emitting report (which every
# latest-per-id queue reader is) it dangles, and it fails SILENTLY because the
# field is populated and schema-valid. Refusal is STRUCTURAL, not a content
# blacklist: the class is "lesson derives meaning from its carrier"
# (A1-716/A2-716, cogpr-ingest.extract_candidates).
_CARRIER_FIELD = "candidate_cogprs"

# Over-block guard. cogpr-ingest scopes its refusal to the BARE-STRING candidate
# form; the miner has no such axis (every lesson here is already a string), so the
# scoping discriminator is POSITIONAL + LENGTH, measured over the live corpus at
# tic 723 (all 13 queue rows whose lesson names the carrier field):
#   refused cohort  — 7 stubs, including the 2 rows THIS writer minted at tic 720
#                     (cpr_74d7624c815cad73, cpr_66f77f4e60dc3c8f): the carrier
#                     mention begins at char <= 35 and the whole lesson is
#                     <= 136 chars. The pointer IS the payload.
#   genuine cohort  — 6 self-contained lessons that DISCUSS the mechanism (the
#                     tic-716/720 cures themselves, incl. the two laws cited
#                     above): the carrier mention begins at char >= 597 and the
#                     lesson runs >= 1046 chars. The mechanism is a cited subject
#                     inside an argument.
# Both thresholds sit inside that 4-8x gap, so a lesson ARGUING ABOUT the
# carrier-pointer class is never refused for naming it. Widen only against a
# re-measurement of the corpus, never by feel.
_CARRIER_POINTER_LEAD_CHARS = 120
_CARRIER_POINTER_MIN_SELF_CONTAINED_CHARS = 400

# The A2-709 mint-site maturity convention: review_tic = birth_tic + maturity.
# Value matches lib/cpr_steppable.DEFAULT_MATURITY_TICS (the gate reader) and
# cogpr-ingest.DEFAULT_MATURITY_TICS (the sibling writer) — one clock, three
# surfaces, no value-coincidence agreement.
MATURITY_TICS = 3

# Measure-validity declaration — cure (b) of
# cgg-ledger#recurrence-measure-invalid-over-shared-generator-corpus. The miner
# does BOTH halves of the promoted discipline: (a) it excludes defect/template-
# classed text from the clustering corpus (is_carrier_pointer_stub, applied in
# mine_patterns + gather_recurrence), and (b) it DECLARES the assumption on every
# emitted envelope so a reader can tell a learned pattern from a generator echo.
# Declaration, never enforcement: it qualifies the claim, it refuses nothing.
CORPUS_AUTHORSHIP_ASSUMPTION = (
    "This recurrence count assumes INDEPENDENTLY AUTHORED records. Defect- and "
    "template-classed text (carrier-pointer stubs) is excluded from the "
    "clustering corpus, but the corpus still mixes human- and machine-authored "
    "records: where records share a generator, a count measures the generator's "
    "repetition rate, not the system's learning."
)

# Per-run refusal/exclusion counters. Module-level channel BY NECESSITY, not
# preference: mine_patterns' 2-tuple return arity is a consumer contract (main()
# and test_pattern_miner_suppression_reporting.py both unpack exactly two), so
# widening it to carry observability would break a reader to add a field — the
# closed-consumer-set obligation pointed at this file's own callers. Reset per run.
RUN_COUNTERS = {}


def _reset_run_counters():
    """Zero the per-run counters. Called at the top of every mine_patterns run."""
    RUN_COUNTERS.clear()
    RUN_COUNTERS.update({
        "corpus_excluded_stub": 0,
        "refused_stub_shape": 0,
        "refused_terminal_derivative": 0,
        "suppressed_unchanged": 0,
        "skipped_duplicate": 0,
    })


_reset_run_counters()


def is_carrier_pointer_stub(text):
    """True when `text` is a carrier-pointer stub rather than a lesson.

    Mirrors the cogpr-ingest.extract_candidates refusal (A1-716/A2-716) with the
    positional/length scoping guard documented on the constants above. Used at
    TWO distinct boundaries, deliberately:
      - the clustering corpus (mine_patterns / gather_recurrence) — so defect
        boilerplate cannot be ranked as the strongest recurrence in the corpus;
      - the queue write boundary (emit_pattern_envelopes) — the physics-layer
        gate that holds even if the corpus filter is bypassed or a pattern record
        predates it.
    """
    if not text:
        return False
    idx = text.lower().find(_CARRIER_FIELD)
    if idx < 0:
        return False
    return (idx <= _CARRIER_POINTER_LEAD_CHARS
            and len(text) <= _CARRIER_POINTER_MIN_SELF_CONTAINED_CHARS)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_queue(queue_path):
    """Load CPR queue (latest-entry-per-ID-wins). Returns dict of id->entry."""
    entries = {}
    p = Path(queue_path)
    if not p.exists():
        return entries
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            eid = d.get("id", "")
            if eid:
                entries[eid] = d
        except json.JSONDecodeError:
            continue
    return entries


def terminal_ids(queue_entries):
    """Ids whose LATEST-per-id status is terminal (terminal-state valve).

    load_queue already applies latest-entry-per-id-wins, so this reads the
    PROJECTION, never raw emissions (cgg-ledger#terminal-state-valve-pattern +
    the federation's authoritative-set-readers invariant). A stray later
    non-terminal row would already have won the projection; that is the queue's
    own contract and this reader does not second-guess it.
    """
    return {eid for eid, entry in queue_entries.items()
            if entry.get("status", "") in TERMINAL_STATUSES}


def get_tic_count(al_path):
    """Resolve the CURRENT canonical tic from audit-logs/tics/*.jsonl.

    Reads `domain_counter_after` off the LATEST tic event (Temporal Scope
    Discipline; mirrors cpr-extract.get_tic_count and
    ladder-audit._resolve_federation_tic) — NOT a count of raw `type=tic` rows.
    Raw aggregation over-counts the authority wherever duplicate/uncounted
    historical emissions exist (557 raw vs canonical 553 at tic 553), and a row
    stamped birth_tic > current tic sits in an unreachable state that silently
    over-holds its maturity gate. Raw-count is retained ONLY as the fallback for
    tic logs predating the domain_counter_after field.
    """
    tic_count = 0
    latest_counter = None
    tic_dir = Path(al_path) / "tics"
    if not tic_dir.is_dir():
        return tic_count
    for f in sorted(tic_dir.glob("*.jsonl")):
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if d.get("type") == "tic":
                tic_count += 1
                val = d.get("domain_counter_after")
                if isinstance(val, int):
                    latest_counter = val
    return latest_counter if latest_counter is not None else tic_count


def load_signal_store(signal_dir):
    """Load latest-per-ID signal state from all JSONL files."""
    entries = {}
    sd = Path(signal_dir)
    if not sd.exists():
        return entries
    for f in sorted(sd.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                sid = d.get("id", "")
                if sid:
                    entries[sid] = d
            except json.JSONDecodeError:
                continue
    return entries


def load_existing_patterns(patterns_dir):
    """Load existing pattern records (latest-per-ID-wins)."""
    entries = {}
    pd = Path(patterns_dir)
    if not pd.exists():
        return entries
    for f in sorted(pd.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                pid = d.get("id", "")
                if pid:
                    entries[pid] = d
            except json.JSONDecodeError:
                continue
    return entries


# ---------------------------------------------------------------------------
# Recurrence detection
# ---------------------------------------------------------------------------

def compute_word_overlap(text_a, text_b):
    """Compute Jaccard word overlap between two texts. Returns float in [0, 1]."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if len(words_a) < 3 or len(words_b) < 3:
        return 0.0
    total = len(words_a | words_b)
    if total == 0:
        return 0.0
    return len(words_a & words_b) / total


def classify_recurrence_scope(observations):
    """Classify recurrence scope from observation rung set.

    Returns (recurrence_kind, recurrence_scope, placement_target).
    """
    rungs = {obs.get("rung", "unknown") for obs in observations}
    subsystems = {obs.get("subsystem", "") for obs in observations}
    scope_paths = {obs.get("scope_path") for obs in observations if obs.get("scope_path")}

    if len(scope_paths) > 1:
        # Different paths — check if rungs differ
        if "estate" in rungs or "federation" in rungs:
            return "cross_domain_same_estate", "estate", "estate"
        if "domain" in rungs:
            return "cross_site_same_domain", "domain", "domain"

    if len(subsystems) > 1:
        return "cross_subsystem", "site", "site"

    return "site_local", "site", "site"


def gather_recurrence(cpr_id, cpr, queue_entries):
    """Find CPRs with similar lessons (canonical recurrence detection).

    Returns list of observation dicts for matching CPRs.

    Corpus exclusion (cure (a) of #recurrence-measure-invalid-over-shared-
    generator-corpus): defect/template-classed text never enters the clustering
    corpus, on EITHER side of the comparison. A generator stub is byte-identical
    across every emission — MORE textually identical than any genuine recurrence
    ever is — so left in, the Jaccard measure actively PREFERS it. Measured at
    tic 720: all three patterns this miner emitted were stub clusters, two
    crossed the >=3-observation envelope threshold and minted as `reinforced`,
    in the same run that early-gate-suppressed 63 genuine recurrences. The
    exclusion reaches gather_recurrence_count too — the enrichment scanner's
    recurrence evidence reads this same corpus and inherits the same hazard.
    """
    lesson = cpr.get("lesson", "")
    if not lesson or is_carrier_pointer_stub(lesson):
        return []

    observations = []
    for eid, entry in queue_entries.items():
        if eid == cpr_id:
            continue
        other_lesson = entry.get("lesson", "")
        if not other_lesson or is_carrier_pointer_stub(other_lesson):
            continue
        overlap = compute_word_overlap(lesson, other_lesson)
        if overlap >= 0.3:
            observations.append({
                "id": eid,
                "rung": entry.get("birth_rung", "unknown"),
                "scope_path": entry.get("birth_scope_path"),
                "subsystem": entry.get("subsystem", ""),
                "overlap": round(overlap, 3),
            })

    return observations


def gather_signal_recurrence(cpr, signals):
    """Find signals related to this CPR's subsystem."""
    subsystem = cpr.get("subsystem", "")
    if not subsystem:
        return []

    observations = []
    for sid, sig in signals.items():
        if sig.get("subsystem") != subsystem:
            continue
        if not is_active_ray(sig):
            continue
        observations.append({
            "id": sid,
            "rung": sig.get("birth_rung", "unknown"),
            "scope_path": None,
            "subsystem": subsystem,
            "kind": sig.get("kind", ""),
        })

    return observations


# ---------------------------------------------------------------------------
# Pattern mining pipeline
# ---------------------------------------------------------------------------

def mine_patterns(project_dir, dry_run=False):
    """Main mining pipeline: detect recurrence, classify, write patterns."""
    project_dir = os.path.abspath(project_dir)
    tz_config = load_ticzone(project_dir)
    al_path = audit_logs_path(project_dir, tz_config)
    topo = birth_topology(project_dir)

    queue_path = os.path.join(al_path, "cprs", "queue.jsonl")
    signal_dir = os.path.join(al_path, "signals")
    patterns_dir = os.path.join(al_path, "patterns")

    _reset_run_counters()

    queue = load_queue(queue_path)
    signals = load_signal_store(signal_dir)
    existing_patterns = load_existing_patterns(patterns_dir)

    # MINT-TIME tic authority, resolved once per run (bk-ingest-path-lifecycle-
    # field-parity). Every envelope this run births is stamped birth_tic =
    # mint_tic — never the pattern's inherited last_observed_tic, which backdated
    # the tic-720 rows to 716 and birthed them ALREADY MATURE, exempt from the
    # maturity hold every other queue row serves.
    mint_tic = get_tic_count(al_path)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    patterns_file = os.path.join(patterns_dir, f"{date_str}.jsonl")

    new_patterns = []
    # Early-gate suppression counter (cgg-ledger#extractor-anomaly-self-reporting,
    # refined /review 695): a detected recurrence dropped as count-unchanged is a
    # SUPPRESSION, and every suppression gate must self-report — otherwise this
    # loop's zero is indistinguishable from detection-zero at the reader (lived
    # t692: 57 detected / 57 suppressed / reader saw nothing). Symmetric with the
    # late gate's skipped_duplicate report in emit_pattern_envelopes.
    suppressed_unchanged = 0

    # For each CPR, check for recurrence across the queue
    for cpr_id, cpr in queue.items():
        lesson = cpr.get("lesson", "")
        if not lesson:
            continue
        # Corpus exclusion at the SOURCE side (the match side is excluded inside
        # gather_recurrence). A stub can neither seed a pattern nor join one.
        if is_carrier_pointer_stub(lesson):
            RUN_COUNTERS["corpus_excluded_stub"] += 1
            continue

        # Gather observations from queue + signals
        queue_obs = gather_recurrence(cpr_id, cpr, queue)
        signal_obs = gather_signal_recurrence(cpr, signals)

        all_obs = queue_obs + signal_obs
        if not all_obs:
            continue

        # Include the source CPR itself as an observation
        all_obs_with_self = [{
            "id": cpr_id,
            "rung": cpr.get("birth_rung", "unknown"),
            "scope_path": cpr.get("birth_scope_path"),
            "subsystem": cpr.get("subsystem", ""),
        }] + all_obs

        # Classify recurrence scope
        rec_kind, rec_scope, placement = classify_recurrence_scope(all_obs_with_self)

        # Compute stable pattern ID from lesson hash
        pattern_hash = hashlib.sha256(
            f"pattern:{cpr.get('subsystem', '')}:{lesson[:100]}".encode()
        ).hexdigest()[:16]
        pattern_id = f"pat_{pattern_hash}"

        # Check if this pattern already exists
        existing = existing_patterns.get(pattern_id)
        prev_count = existing.get("observation_count", 0) if existing else 0
        new_count = len(all_obs) + 1  # +1 for source CPR

        # Only emit if count increased or pattern is new
        if existing and new_count <= prev_count:
            suppressed_unchanged += 1
            continue

        # Determine confidence tier from observation count
        if new_count >= 5:
            confidence = "convergent"
        elif new_count >= 3:
            confidence = "reinforced"
        else:
            confidence = "tentative"

        # Get tic context
        first_tic = cpr.get("birth_tic", 0)
        if existing:
            first_tic = existing.get("first_observed_tic", first_tic)
        last_tic = max(
            (obs_entry.get("birth_tic", 0)
             for obs_entry in [queue.get(o["id"], {}) for o in queue_obs] + [cpr]
             if obs_entry),
            default=0,
        )

        pattern = {
            "type": "pattern_recurrence",
            "id": pattern_id,
            # Full lesson body — NOT lesson[:200]. The 200-char clip silently
            # starved every pattern-mined CPR: the queue envelope (below) inherits
            # this field as its `lesson`, so a clip here propagated a truncated,
            # un-conformable lesson into the queue (the "anonymous five" + the
            # pattern-mined cohort). Downstream consumers that need it short
            # re-clip locally (hash uses lesson[:100]; `summary` re-clips to 200;
            # CLI display clips to 60), so storing the full body is safe.
            "pattern": lesson,
            "pattern_summary": lesson[:200],
            "subsystem": cpr.get("subsystem", ""),
            "recurrence_kind": rec_kind,
            "recurrence_scope": rec_scope,
            "observed_in": [
                {"id": o["id"], "rung": o["rung"], "subsystem": o.get("subsystem", "")}
                for o in all_obs_with_self[:10]
            ],
            "observation_count": new_count,
            "first_observed_tic": first_tic,
            "last_observed_tic": last_tic,
            "placement_target": placement,
            "confidence_tier": confidence,
            # Declared measure-validity qualifier, sitting beside the count it
            # qualifies (cure (b) of #recurrence-measure-invalid-over-shared-
            # generator-corpus). The confidence ladder above is awarded for
            # observation COUNT; without this declaration a reader cannot tell a
            # learned pattern from a generator echo, and `reinforced` reads
            # highest precisely where the evidence would be worthless.
            "corpus_authorship_assumption": CORPUS_AUTHORSHIP_ASSUMPTION,
            "status": "observed",
            "birth_rung": topo["birth_rung"],
            "created_at": now.isoformat(),
            "source_cpr": cpr_id,
        }

        new_patterns.append(pattern)
        existing_patterns[pattern_id] = pattern

    RUN_COUNTERS["suppressed_unchanged"] = suppressed_unchanged

    # Corpus-exclusion self-report (same discipline as the suppression gate
    # below — cgg-ledger#extractor-anomaly-self-reporting): an exclusion that
    # shrinks the corpus is a suppression, and every suppression gate must
    # self-report or its zero is unreadable.
    if RUN_COUNTERS["corpus_excluded_stub"]:
        print(
            f"[pattern_miner] corpus exclusion: "
            f"{RUN_COUNTERS['corpus_excluded_stub']} carrier-pointer-stub "
            f"lesson(s) held OUT of the clustering corpus (measure-validity, "
            f"cgg-ledger#recurrence-measure-invalid-over-shared-generator-corpus) "
            f"— recurrence this run is measured over the remaining corpus, not "
            f"the whole queue",
            file=sys.stderr,
        )

    # Early-gate suppression self-report: label the zero by its cause-axis so a
    # suppression-zero never reads as pattern absence (not detection-zero).
    if suppressed_unchanged:
        print(
            f"[pattern_miner] early-gate suppression: {suppressed_unchanged} "
            f"detected recurrence(s) suppressed as count-unchanged vs existing "
            f"pattern records — an empty emission this run is suppression-aware, "
            f"not detection-zero",
            file=sys.stderr,
        )

    # Write patterns
    if new_patterns and not dry_run:
        os.makedirs(patterns_dir, exist_ok=True)
        try:
            from lib.atomic_append import atomic_append_jsonl
            for pat in new_patterns:
                atomic_append_jsonl(str(patterns_file), pat)
        except ImportError:
            import fcntl
            lockfile = str(patterns_file) + ".lock"
            with open(lockfile, "w") as lf:
                fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
                try:
                    with open(patterns_file, "a", encoding="utf-8") as f:
                        for pat in new_patterns:
                            f.write(json.dumps(pat, separators=(",", ":")) + "\n")
                finally:
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

    # Emit proposal envelopes for patterns crossing the threshold
    envelopes = []
    if new_patterns and not dry_run:
        envelopes = emit_pattern_envelopes(new_patterns, queue_path, topo, mint_tic)

    return new_patterns, envelopes


# ---------------------------------------------------------------------------
# Proposal envelope emission
# ---------------------------------------------------------------------------

ENVELOPE_THRESHOLD_COUNT = 3
ENVELOPE_THRESHOLD_SCOPES = {"domain", "estate", "federation"}

# Escalation rules — inspectable ladder logic for placement suggestions
_ESCALATION_RULES = {
    "site_local": "recurs within single site — promote at site level only",
    "cross_subsystem": "recurs across subsystems within site — may indicate site-level invariant",
    "cross_site_same_domain": "recurs across sibling sites — candidate for domain-level promotion",
    "cross_domain_same_estate": "recurs across domains — candidate for estate-level promotion",
    "cross_estate": "recurs across estates — candidate for federation or global review",
}


def _placement_escalation_rule(pattern):
    """Return human-readable escalation rule for this pattern's recurrence kind."""
    kind = pattern.get("recurrence_kind", "unknown")
    return _ESCALATION_RULES.get(kind, f"unknown recurrence kind: {kind}")


def emit_pattern_envelopes(patterns, queue_path, topo, mint_tic):
    """Emit proposal envelopes for patterns crossing review threshold.

    Threshold: observation_count >= 3 OR recurrence_scope is domain+.
    Writes to the CPR queue as extracted entries with artifact_kind: pattern_recurrence.

    mint_tic is the MINT-TIME canonical tic (resolved once per run by
    mine_patterns via get_tic_count). It is a required argument, not a defaulted
    one: a silently-defaulted 0 would birth every row at tic 0 — instantly
    mature, the same exemption the inherited-birth_tic defect produced.

    Three write-boundary gates run here, in physics-before-bookkeeping order:
    shape refusal, terminal-derivative binding, then the id-keyed dedup. The
    first two are the miner-side half of the closed producer-set obligation
    (/review 723); the third is the pre-existing re-flood valve.
    """
    now = datetime.now(timezone.utc).isoformat()
    envelopes = []

    # Dedup-at-write (CGG ledger#dedup-at-write-using-canonical-identity +
    # #terminal-state-valve-pattern). The pattern id is content-deterministic
    # (sha256 of subsystem+lesson), so a recurring lesson always re-mines to the
    # SAME cpr_<hash> id. Without this gate, emit re-appends that id as `extracted`
    # on every run whose observation_count grew — stacking a non-terminal row on
    # top of an already-terminal (promoted/absorbed/superseded) row and re-flooding
    # the extracted tier. That is the producer-without-reconciler starvation found
    # at tic 368 (250 raw rows for 17 ids, ~280 tics, invisible to every routine
    # surface). The fix is mechanical and id-keyed ONLY: if the canonical id is
    # already present in the queue's latest-entry projection (any status), do not
    # re-emit. Cross-id SEMANTIC dedup (cpr_<hash> ≡ a lesson promoted under a
    # different id) is a JUDGMENT task and stays with the cpr-stepper agent — it is
    # deliberately NOT done here (lane separation: foreground judgment, background
    # execution).
    # ONE queue read serves all three gates: the id-dedup set and the
    # terminal-state projection come from the same latest-per-id snapshot.
    queue_projection = load_queue(queue_path)
    existing_ids = set(queue_projection.keys())
    settled_ids = terminal_ids(queue_projection)
    skipped_duplicate = 0

    for pat in patterns:
        count = pat.get("observation_count", 0)
        scope = pat.get("recurrence_scope", "site")

        if count < ENVELOPE_THRESHOLD_COUNT and scope not in ENVELOPE_THRESHOLD_SCOPES:
            continue

        cpr_id = f"cpr_{pat['id'][4:]}"  # pat_xxx -> cpr_xxx (content-deterministic)

        # GATE 1 — SHAPE. Refuse a carrier-pointer-stub payload at the write
        # boundary, mirroring cogpr-ingest's cure (A1-716/A2-716). This is the
        # physics-layer gate: it fires before any append, so it holds even when
        # the clustering-corpus filter is bypassed or a pattern record predates
        # it. Loud + counted, never silent — a silently dropped emission is
        # indistinguishable from detection-zero at the reader.
        pattern_text = pat.get("pattern", "")
        if is_carrier_pointer_stub(pattern_text):
            RUN_COUNTERS["refused_stub_shape"] += 1
            print(
                f"[pattern_miner] SHAPE-REFUSAL [{pat.get('id', '?')}] "
                f"reason=carrier_pointer_stub: payload names its own carrier "
                f"field ('{_CARRIER_FIELD}') — an intra-document pointer, not a "
                f"self-contained lesson; refused at the write boundary "
                f"(/review 723, bk-pattern-miner-write-boundary-shape-predicate): "
                f"{pattern_text[:120]!r}",
                file=sys.stderr,
            )
            continue

        # GATE 2 — TERMINAL-DERIVATIVE BINDING. The envelope's lesson IS the
        # source CPR's lesson, so minting off a row whose latest status is
        # terminal re-opens an adjudicated payload under a NEW id — the
        # derivative writer resurrecting what /review already settled (measured
        # tic 720: both miner-minted rows carried payloads whose source rows were
        # `absorbed`). A terminalized payload binds its derivatives.
        # Two arms, reported distinctly:
        #   payload_from_terminal_source — the text itself is drawn from a
        #     settled row (the broader arm; the source is always an observed_in
        #     member, so this also covers the all-terminal case);
        #   all_observations_terminal   — every queue-resolvable observed_in
        #     member is settled, so the whole evidence base is adjudicated.
        # Signal observations are excluded from the second arm by construction:
        # a signal id is not a queue row and carries no queue lifecycle status,
        # so it can neither satisfy nor falsify a terminal claim. With zero
        # queue-resolvable members the arm does not fire (no evidence, no claim).
        # NO SIGNAL GOES DARK: the pattern RECORD still lands in
        # audit-logs/patterns/ with its full observation set — the recurrence
        # observation is preserved and readable. What is refused is only the
        # derivative QUEUE MINT, i.e. re-opening an adjudicated payload for
        # re-adjudication under a new id. The new information in such a pattern
        # is the recurrence count, not the lesson, and the count survives.
        source_cpr = pat.get("source_cpr", "")
        observed_queue_ids = [
            o.get("id") for o in pat.get("observed_in", [])
            if o.get("id") and o.get("id") in existing_ids
        ]
        source_terminal = bool(source_cpr) and source_cpr in settled_ids
        all_obs_terminal = bool(observed_queue_ids) and all(
            oid in settled_ids for oid in observed_queue_ids
        )
        if source_terminal or all_obs_terminal:
            RUN_COUNTERS["refused_terminal_derivative"] += 1
            reason = ("payload_from_terminal_source" if source_terminal
                      else "all_observations_terminal")
            print(
                f"[pattern_miner] TERMINAL-DERIVATIVE REFUSAL "
                f"[{pat.get('id', '?')}] reason={reason}: "
                f"source_cpr={source_cpr or '-'} "
                f"(terminal={source_terminal}), "
                f"{sum(1 for o in observed_queue_ids if o in settled_ids)}/"
                f"{len(observed_queue_ids)} queue-resolvable observed_in "
                f"member(s) terminal — an adjudicated payload may not be "
                f"re-minted under a derivative id "
                f"(/review 723, bk-pattern-miner-write-boundary-shape-predicate)",
                file=sys.stderr,
            )
            continue

        # GATE 3 — id-keyed dedup (pre-existing re-flood valve, see above).
        if cpr_id in existing_ids:
            skipped_duplicate += 1
            continue

        # Determine lesson type from pattern characteristics (pattern_text was
        # already bound for the shape gate above).
        if any(kw in pattern_text.lower() for kw in ["governance", "protocol", "invariant", "rule"]):
            lesson_type = "meta"
        elif any(kw in pattern_text.lower() for kw in ["workflow", "process", "pipeline", "step"]):
            lesson_type = "process"
        else:
            lesson_type = "subject"

        envelope = {
            "type": "cpr",
            "id": cpr_id,
            # LIFECYCLE-FIELD PARITY (bk-ingest-path-lifecycle-field-parity,
            # authorized /review 723). The tic-720 rows this writer minted
            # carried NO id_origin, NO tier, NO maturity_tics and NO review_tic —
            # a materially reduced schema against the other two ingest paths, so
            # queue_state_compile resolved them to
            # maturity.classification = schedule_not_resolvable: born
            # UNSCHEDULABLE. Admitting a writer to a guarded surface admits it to
            # the WHOLE lifecycle contract, not just the surface's shape.
            #   id_origin  — the cpr id is derived from the pattern hash
            #                (sha256 of subsystem+lesson), so hash_derived is
            #                literally true here, same as cogpr-ingest's lane.
            #   tier       — tier1 under cpr-extract._classify_tier's shared
            #                taxonomy: this row carries both `lesson` and
            #                `source`. Provenance for readers, not a ranking.
            "id_origin": "hash_derived",
            "tier": "tier1",
            "dedup_hash": pat["id"][4:],
            "status": "extracted",
            "lesson": pat["pattern"],
            "source": f"pattern_miner:{pat['id']}",
            "source_date": now[:10],
            "band": "COGNITIVE",
            "motivation_layer": "COGNITIVE",
            "subsystem": pat.get("subsystem", ""),
            "recommended_scopes": [],
            # MINT-TIME birth, never the inherited observation clock. The old
            # `pat.get("last_observed_tic", 0)` stamp backdated rows to the tic
            # of the newest OBSERVATION (716 for rows minted at 720), so they
            # were born already past their maturity window — exempt from the
            # hold every other queue row serves. The observation clock is
            # preserved below as its own honest field; it is evidence about the
            # PATTERN, not a birth position for the ROW.
            "birth_tic": mint_tic,
            "last_observed_tic": pat.get("last_observed_tic", 0),
            # One resolved clock feeds BOTH maturity fields (the
            # bk-cpr-maturity-field-name-mismatch cure, struck tic 694 on the
            # sibling writer): the gate readers (lib/cpr_steppable.is_steppable,
            # ripple-assessor, mandate-write) read `maturity_tics`, while the
            # compile layer (queue_state_compile._resolve_target_tic) parks
            # extracted rows on window_anchor + `maturity_window_tics` and
            # returns None — schedule_not_resolvable — when that field is absent.
            # Equal stamps from one source make the two reader families
            # structurally agree instead of agreeing by value-coincidence.
            "maturity_tics": MATURITY_TICS,
            "maturity_window_tics": MATURITY_TICS,
            # review_tic = birth + maturity, the A2-709 mint-site convention
            # (ruled BY-DESIGN at /review 709 for the sibling mint lane: this
            # cohort adjudicates directly from `extracted` at its review_tic).
            "review_tic": mint_tic + MATURITY_TICS,
            "birth_rung": topo["birth_rung"],
            "birth_scope_path": topo["birth_scope_path"],
            "extracted_at": now,
            "extracted_by": "pattern-miner",
            "source_file": "pattern_miner.py",
            "proposal_envelope": {
                "artifact_kind": "pattern_recurrence",
                "lesson_type": lesson_type,
                "confidence_tier": pat.get("confidence_tier", "tentative"),
                "relations": {
                    "supports": [],
                    "contradicts": [],
                    "refines": [],
                    "supersedes": [],
                    "depends_on": [],
                },
                "capture_policy": {
                    "persist_locally": True,
                    "route_to_review": True,
                    "route_to_governance": False,
                    "allow_signal_emission": pat.get("confidence_tier") in ("reinforced", "convergent"),
                    "allow_warrant_generation": False,
                },
                "evidence": {
                    "sources": [pat["id"]],
                    "supporting_artifacts": [o["id"] for o in pat.get("observed_in", [])[:5]],
                    "independent_confirmations": pat.get("observation_count", 0),
                    # The declared qualifier sits INSIDE evidence, immediately
                    # beside independent_confirmations — the exact claim it
                    # qualifies. Cure (b) of #recurrence-measure-invalid-over-
                    # shared-generator-corpus: a /review reader must be able to
                    # tell a learned pattern from a generator echo without
                    # leaving the row.
                    "corpus_authorship_assumption": CORPUS_AUTHORSHIP_ASSUMPTION,
                },
                "routing": {
                    "review_required": True,
                    "promotion_target": pat.get("placement_target", "site"),
                    "promotion_blockers": [],
                },
                "placement": {
                    "suggested_rung": pat.get("placement_target", "site"),
                    "suggested_target": "CLAUDE.md",
                    "reason": f"Recurs across {count} observations ({pat.get('recurrence_kind', 'unknown')})",
                },
                "placement_basis": {
                    "reason": f"{pat.get('recurrence_kind', 'unknown')} recurrence",
                    "observed_scope": scope,
                    "recommended_scope": pat.get("placement_target", "site"),
                    "observation_count": count,
                    "escalation_rule": _placement_escalation_rule(pat),
                },
                "payload": {
                    "pattern_id": pat["id"],
                    "recurrence_kind": pat.get("recurrence_kind", ""),
                    "recurrence_scope": scope,
                    "observation_count": count,
                    "summary": pat["pattern"][:200],
                },
            },
        }

        envelopes.append(envelope)

    # Write envelopes to CPR queue
    if envelopes:
        os.makedirs(os.path.dirname(queue_path), exist_ok=True)
        try:
            from lib.atomic_append import atomic_append_jsonl
            for env in envelopes:
                atomic_append_jsonl(queue_path, env)
        except ImportError:
            import fcntl
            lockfile = queue_path + ".lock"
            with open(lockfile, "w") as lf:
                fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
                try:
                    with open(queue_path, "a", encoding="utf-8") as f:
                        for env in envelopes:
                            f.write(json.dumps(env, separators=(",", ":")) + "\n")
                finally:
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

    # Extractor anomaly self-reporting (CGG ledger#extractor-anomaly-self-reporting):
    # surface the dedup-at-write skip count so the re-flood-prevention is observable,
    # not silent.
    if skipped_duplicate:
        print(
            f"[pattern_miner] dedup-at-write: skipped {skipped_duplicate} "
            f"already-queued envelope id(s) — no re-flood (terminal-state valve held)",
            file=sys.stderr,
        )
    RUN_COUNTERS["skipped_duplicate"] = skipped_duplicate

    return envelopes


# ---------------------------------------------------------------------------
# Public API for enrichment scanner import
# ---------------------------------------------------------------------------

def gather_recurrence_count(cpr, queue_entries):
    """Count recurrence for a single CPR against the queue.

    Drop-in replacement for the inline implementation formerly in
    cpr-enrichment-scanner.py. Returns list of evidence dicts.
    """
    cpr_id = cpr.get("id", "")
    observations = gather_recurrence(cpr_id, cpr, queue_entries)

    if not observations:
        return []

    return [{
        "evidence_type": "recurrence_count",
        "value": f"{len(observations)} similar CPRs detected",
        "detail": [o["id"] for o in observations[:5]],
    }]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Pattern Miner — topology-aware recurrence detection"
    )
    parser.add_argument("--project-dir", default=None,
                        help="Zone root (auto-resolved if omitted)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect patterns without writing")
    parser.add_argument("--json", action="store_true", dest="output_json",
                        help="Output structured JSON")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    project_dir = args.project_dir or resolve_zone_root()
    patterns, envelopes = mine_patterns(project_dir, dry_run=args.dry_run)

    if args.output_json:
        print(json.dumps({
            "patterns": patterns,
            "count": len(patterns),
            "envelopes_emitted": len(envelopes),
            # Refusal/exclusion counters ride the JSON so an emission count is
            # readable against its cause-axis (extractor-anomaly-self-reporting):
            # a low envelope count that is REFUSAL-shaped must never read as
            # detection-zero.
            "admission_counters": dict(RUN_COUNTERS),
        }, indent=2))
    elif not args.quiet:
        if patterns:
            for p in patterns:
                print(f"  {p['id']}: {p['pattern'][:60]}... "
                      f"({p['recurrence_kind']}, {p['observation_count']} obs, "
                      f"{p['confidence_tier']})")
        if envelopes:
            print(f"  → {len(envelopes)} proposal envelope(s) emitted to queue")
        refused = (RUN_COUNTERS["refused_stub_shape"]
                   + RUN_COUNTERS["refused_terminal_derivative"])
        if refused or RUN_COUNTERS["corpus_excluded_stub"]:
            print(f"  ⊘ admission: {RUN_COUNTERS['refused_stub_shape']} shape-refused, "
                  f"{RUN_COUNTERS['refused_terminal_derivative']} terminal-derivative-refused, "
                  f"{RUN_COUNTERS['corpus_excluded_stub']} corpus-excluded")
        print(len(patterns))

    return 0


if __name__ == "__main__":
    sys.exit(main())
