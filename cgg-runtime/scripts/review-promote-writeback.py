#!/usr/bin/env python3
"""
Review Promote Writeback — the EMIT-side complement to review-close-check.py.

When /review promotes a CogPR, review-execute (the applier) flips queue.jsonl and
inscribes the body to the doctrine surface (ledger). But two writebacks to the
AUTO-MEMORY / INLINE surfaces were left to LLM discretion and recurrently dropped:

  (1) STALE INLINE MARKER — the inline `<!-- --agnostic-candidate ... -->` block in
      MEMORY.md / topic files keeps `status: pending` even though queue.jsonl says
      `promoted`. At tic 337 EIGHT markers (tic-324/325/328) were still pending-inline
      despite being promoted-in-queue since /review 329/336.
  (2) MISSING PROVENANCE BREADCRUMB — no `<!-- promoted from <cpr_id> -->` on the
      auto-memory TARGET file (feedback_*.md / topic files that ARE the inscription).
      Only 2/61 feedback files carried one; with an empty queue `lesson` field
      review-close-check then has neither a cpr_id literal nor a snippet to match and
      reports `promoted_text_missing` for doctrine that genuinely landed.

Both gaps mint exactly the false-positives the genuine-vs-known split classifies on
the READ side. The split CLASSIFIES the FP; this writeback PREVENTS it. Same root —
incomplete atomic writeback — so the cure is structural (mechanize the missing
collapse step), not narrative (re-explain the discipline in the agent prompt). This
is the runtime materialization of `Atomic Dual-Surface Invariant Mechanization`
(cgg-ledger) applied to the promotion writeback: review-execute now INVOKES this
helper in the same writeback as queue.jsonl, the way it already invokes
atomic-append.sh for the queue itself.

Idempotent by construction: a re-run on an already-promoted / already-stamped entry
is a no-op. Safe to call on every PROMOTE/PROMOTE-SPEC/ABSORB verdict.

Scope discipline:
  - INLINE STATUS FLIP fires on the candidate block wherever it lives (MEMORY.md or a
    topic file), advancing ANY non-terminal status (`pending`, `enrichment_needed`,
    `enrichment_eligible`, `extracted`, `promotable`, ...) to the terminal status.
    Terminal states (promoted / promoted_spec / absorbed / skipped / deferred) are
    left untouched.
  - The block is resolved by a TOLERANT ID-SET, never a single fuzzy `cpr_id`. The
    set = {cpr_id} ∪ {`cpr_<dedup_hash>`} ∪ {memory_md_aliases} ∪ {cross-id pointers},
    harvested from the queue rows for the id; PLUS a CONTENT-IDENTITY BRIDGE — an
    inline block whose recomputed `sha256(source:lesson)[:16]` matches the promoted
    row's `dedup_hash` IS that CogPR, regardless of what id (or no id) it declares.
    This closes the id-form-divergence silent no-op (queue hash-id `cpr_b3b60803…` vs
    born long-form id `cpr_primary_tool_…_tic475`) that left `inline_blocks_flipped=0`
    on a clean exit so every boot miscounted stale-promoted CogPRs as pending. A
    `flipped == expected` post-assert makes a matched-but-unflipped block LOUD instead
    of silent. (bk-review-promote-writeback-id-resolution, tic 481; ports the id-set /
    anchor resolution already proven in `stamp_reinforced_by`, same file.)
  - BREADCRUMB STAMP fires ONLY on AUTO-MEMORY target files. A ledger / CLAUDE.md
    target is owned by review-execute Step 2 (the ledger gets the full entry +
    provenance; a dehydrated compact root must NOT be re-inflated with a breadcrumb).

Usage:
    python3 review-promote-writeback.py --cpr-id cpr_x_tic337 \
        --promoted-to "feedback_x.md" --review-tic 339 [--birth-tic 337] \
        [--status promoted] [--source "MEMORY.md"] [--project-dir /path] \
        [--dry-run] [--json]
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
try:
    from zone_root import resolve_zone_root  # noqa: E402
except Exception:  # pragma: no cover - zone_root always present in runtime
    resolve_zone_root = None  # type: ignore

# Auto-memory directory — the same constant review-close-check.py reads from, so the
# emit side writes exactly where the read side looks. feedback_*.md, session_lessons_*.md,
# project_*.md, and MEMORY.md (the inline-candidate host) live here, OUTSIDE the repo.
AUTO_MEMORY_DIR = (
    Path.home()
    / ".claude"
    / "projects"
    / "-Users-breydentaylor-canonical"
    / "memory"
)

# Terminal status values — once an inline marker carries one of these it is NOT
# re-flipped (a PROMOTE-SPEC entry stays promoted_spec; an absorbed entry stays
# absorbed). Only `pending` is advanced.
_TERMINAL_STATUSES = {"promoted", "promoted_spec", "absorbed", "skipped", "deferred"}

# Provenance-comment recognizer — kept in lock-step with review-close-check.py's
# _PROVENANCE_VERB_RE so "already stamped" is judged by the same shape the reader
# resolves. Used only for the idempotency guard (does THIS cpr_id already have a
# promoted-from comment in the target?).
_PROVENANCE_VERB_RE = re.compile(
    r"<!--\s*(?:"
    r"(?:promoted-spec|promoted|absorbed|refined|extended|merged|superseded)"
    r"|CPR-ID:"
    r").*?-->",
    re.IGNORECASE | re.DOTALL,
)

_CANDIDATE_OPEN = "<!-- --agnostic-candidate"
_CANDIDATE_CLOSE = "-->"

_FEDERATION_LEDGER_REL = os.path.join(
    "audit-logs", "governance", "constitution-ledger", "ledger.md")


def _default_federation_ledger():
    """Walk up from this script to the federation root and return its
    constitution-ledger path, or None. Used as the reinforced-by default target."""
    here = Path(os.path.abspath(__file__)).parent
    for d in [here, *here.parents]:
        cand = d / _FEDERATION_LEDGER_REL
        if cand.is_file():
            return str(cand)
    if resolve_zone_root is not None:
        try:
            cand = Path(resolve_zone_root()) / _FEDERATION_LEDGER_REL
            if cand.is_file():
                return str(cand)
        except Exception:
            pass
    return None

# Strip a trailing `#anchor` / `:N-M` line-range / ` (scope hint)` from a target so
# we resolve to the bare filesystem path (matches review-close-check normalization).
_ANCHOR_RE = re.compile(r"^([^#:\s]+\.[A-Za-z]+)(?:[#:][^\s]*)?$")
_SCOPE_HINT_RE = re.compile(r"^(.*?)\s+\(.*\)$", re.DOTALL)


def _bare_path(target_str):
    """Return the bare filesystem path for a promoted_to target string."""
    s = target_str.strip()
    m = _SCOPE_HINT_RE.match(s)
    if m:
        s = m.group(1)
    # A compound `A + B` target — take the first component for resolution; the
    # caller stamps per-target, and the auto-memory member (if any) is what matters.
    if " + " in s:
        s = s.split(" + ")[0].strip()
    m = _ANCHOR_RE.match(s)
    if m:
        s = m.group(1)
    return s


def resolve_auto_memory_target(target_str, am_dir=None):
    """Resolve a promoted_to target to an auto-memory file path, or None.

    Returns the Path ONLY when the target lives inside the auto-memory dir — the
    breadcrumb stamp is scoped to auto-memory targets (a ledger/CLAUDE.md target
    is owned by the agent's ledger-inscription step). A bare `feedback_x.md`,
    a `~/.claude/.../memory/feedback_x.md`, or an absolute path inside the dir
    all resolve; anything else returns None.
    """
    am_dir = Path(am_dir) if am_dir else AUTO_MEMORY_DIR
    bare = _bare_path(target_str).rstrip("/")
    if not bare:
        return None

    candidate = None
    if bare.startswith("~"):
        candidate = Path(os.path.expanduser(bare))
    elif os.path.isabs(bare):
        candidate = Path(bare)
    else:
        # Relative / bare filename: only the basename is meaningful for auto-memory
        # (the dir is flat). If the relative path points elsewhere in the repo it is
        # not an auto-memory target.
        am = am_dir / os.path.basename(bare)
        if am.is_file():
            return am
        return None

    try:
        candidate = candidate.resolve()
    except OSError:
        return None
    # In-scope only if it is actually under the auto-memory dir.
    try:
        candidate.relative_to(am_dir.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _parse_birth_tic(cpr_id, explicit):
    if explicit is not None:
        return explicit
    # cpr_<slug>_tic337 / ..._tic337 — last tic number in the id is the birth tic.
    hits = re.findall(r"tic[_-]?(\d+)", cpr_id)
    return int(hits[-1]) if hits else None


def _iter_candidate_blocks(lines):
    """Yield (start_idx, end_idx) line spans for each agnostic-candidate block.

    start_idx is the index of the `<!-- --agnostic-candidate` line; end_idx is the
    index of the line that closes the block with `-->` (inclusive).
    """
    i = 0
    n = len(lines)
    while i < n:
        if lines[i].lstrip().startswith(_CANDIDATE_OPEN):
            j = i + 1
            while j < n and lines[j].strip() != _CANDIDATE_CLOSE:
                j += 1
            yield (i, min(j, n - 1))
            i = j + 1
        else:
            i += 1


# ---------------------------------------------------------------------------
# Tolerant id-set + content-identity resolution (bk-review-promote-writeback-id-
# resolution, tic 481). The single-key `cpr_id` match below silently no-op'd whenever
# the queue row carried a hash-derived id (`cpr_<dedup_hash>`) while the inline block
# declared a different id (or no id at all) — `inline_blocks_flipped=0`, clean exit,
# every boot miscounting stale-promoted CogPRs as pending. The fix ports the id-set /
# anchor resolution already proven in `stamp_reinforced_by` (same file): resolve by a
# SET of acceptable ids plus a content-identity bridge, never one fuzzy key.
# ---------------------------------------------------------------------------

_QUEUE_REL = os.path.join("audit-logs", "cprs", "queue.jsonl")
# A hash-derived id is `cpr_` + the 16-hex dedup_hash (cpr-extract.py:553). When the
# cpr_id itself is in this form the content bridge works even with no queue row.
_HASH_ID_RE = re.compile(r"^cpr_([0-9a-f]{16})$")


def _default_queue():
    """Resolve the federation CogPR queue path by walking up from this script, then via
    zone_root (mirrors `_default_federation_ledger`). Returns a Path or None. Fail-soft:
    the runtime copy under ~/.claude resolves through zone_root; the forge copy via walk-up."""
    here = Path(os.path.abspath(__file__)).parent
    for d in [here, *here.parents]:
        cand = d / _QUEUE_REL
        if cand.is_file():
            return cand
    if resolve_zone_root is not None:
        try:
            cand = Path(resolve_zone_root()) / _QUEUE_REL
            if cand.is_file():
                return cand
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Sibling born-home writeback scope (bk-borns-home-writeback-flip-scope, tic 517→).
# A born's inline candidate block lives in the FEDERATION born home
# (audit-logs/governance/borns-tic<N>-*.md), NOT in the auto-memory dir — cpr-extract
# started extracting borns from there at tic 498 (Emitter Surface Declared Interface),
# so the EXTRACT side reaches them but this WRITEBACK side does not: flip_inline_status
# globs only the auto-memory dir, leaving a promoted born's `status:` pending forever —
# every boot then miscounts it, the SAME silent-no-op class as the tic-481 id-form
# divergence fix one surface over (cgg-ledger#named-footgun-guard-leaves-sibling-site-
# unfixed: fix-site + bug-sibling-site are a closed consumer set).
#
# BUILD-AND-GATE (cgg-ledger#build-and-gate-ratified-flag-gated-consumer): the born-home
# scan is BUILT + WIRED + dual-proof-TESTED, but its USE is gated on this flag
# (default False = dormant) because the governing doctrine `cpr_borns_governance_home`
# (the born home IS a governance home consumers must scan) is DEFERRED at /review (one
# conformation owed). /review flips this ONE constant to True — ratification IS the
# flag-flip, no further code change; callers (review-execute) pass scan_borns=None and
# inherit the gate. Dual proof lives in test_review_promote_writeback.py: dormancy
# (0-flip at False) + full-surface activation (flip + terminal-noop + content-bridge at
# True), not one happy path.
#
# NOT recency-windowed — the apophatic boundary against cpr-extract's select_borns_files
# (which IS windowed, BORNS_RECENCY_WINDOW=6, to avoid mass-extracting ~88 historical
# borns). The writeback is keyed on a specific cpr_id / content-hash, so it must reach a
# born of ANY age: a born promoted now could be tics old, and windowing it to the born
# frontier would silently fail to flip it (the very silent-no-op this file fights). The
# New-Consumer scope-bound (cgg-ledger#new-consumer-over-long-lived-emitter-surface-must-
# be-scope-bounded-not-retroactive) governs bulk DISCOVERY (sweeping for NEW blocks),
# NOT a targeted by-id WRITEBACK whose key IS its bound.
# ---------------------------------------------------------------------------

_BORNS_HOME_REL = os.path.join("audit-logs", "governance")
_BORNS_GLOB = "borns-tic*.md"
BORNS_WRITEBACK_RATIFIED = True  # RATIFIED /review-523 (ratification IS the flip). Dual-proof verified tic 523: dormancy = 0 born blocks touched at False; full-surface activation = born home (92 borns-tic*.md) scanned without exception, terminal-safe (matched terminal born no-ops correctly), and the flip is the SAME proven loop already running on auto-memory *.md (no born-specific flip code). Closes the C-5 sibling-site gap (cgg-ledger#named-footgun-guard-leaves-sibling-site-unfixed): per-cpr writeback now reaches the federation born home, not only auto-memory.


def _default_borns_home():
    """Resolve the federation born home (audit-logs/governance, where borns-tic<N>-*.md
    live) by walking up from this script, then via zone_root. Returns a Path or None.
    Mirrors _default_queue: the forge copy resolves via walk-up; the installed copy under
    ~/.claude resolves via zone_root (no audit-logs/ on the ~/.claude walk-up path)."""
    here = Path(os.path.abspath(__file__)).parent
    for d in [here, *here.parents]:
        cand = d / _BORNS_HOME_REL
        if cand.is_dir():
            return cand
    if resolve_zone_root is not None:
        try:
            cand = Path(resolve_zone_root()) / _BORNS_HOME_REL
            if cand.is_dir():
                return cand
        except Exception:
            pass
    return None


def _compute_dedup_hash(source, lesson):
    """`sha256(f'{source}:{lesson}')[:16]` — the EXACT id-minting formula from
    cpr-extract.py:543-545. Kept in lock-step so a recomputed inline-block hash matches
    the dedup_hash minted at extraction. The content-identity bridge: a block whose
    recomputed hash equals a promoted row's dedup_hash IS that CogPR, whatever id it
    declares — the robust resolver for the id-form divergence."""
    return hashlib.sha256(f"{source}:{lesson}".encode()).hexdigest()[:16]


def _parse_candidate_fields(block_lines):
    """Minimal mirror of cpr-extract.parse_cpr_block (cpr-extract.py:82) for the fields the
    content bridge needs (id, status, source, lesson). Handles `key: "value"` (quote-stripped)
    and the YAML block-scalar `key: |` form. Marker/comment lines are ignored. Kept in
    lock-step with the parser + dedup_hash formula so a recompute matches the minted id."""
    fields = {}
    lines = [ln.rstrip("\n") for ln in block_lines]
    i, n = 0, len(lines)
    while i < n:
        raw = lines[i]
        line = raw.strip()
        i += 1
        if not line or line.startswith("#") or line.startswith("<!--") or line == "-->":
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        if val == "|":
            scalar = []
            while i < n:
                r = lines[i]
                if r.startswith("  ") or r.startswith("\t"):
                    scalar.append(r.lstrip())
                    i += 1
                elif not r.strip():
                    scalar.append("")
                    i += 1
                else:
                    break
            while scalar and not scalar[-1]:
                scalar.pop()
            fields[key] = "\n".join(scalar).strip()
            continue
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        fields[key] = val
    return fields


def resolve_promotion_id_set(cpr_id, queue_path=None):
    """Resolve (id_set, dedup_hash) for a promoted cpr_id.

    id_set = the union of every id form that could legitimately key the inline candidate
    block — the canonical cpr_id, the `cpr_<dedup_hash>` hash-form, any recorded
    `memory_md_aliases`, and cross-id pointers (`cpr_id` / `extracted_from_inline` /
    `source_born`) harvested across ALL queue rows for the id (a union, NOT terminal-valve:
    the dedup_hash lives on the extraction row while status lives on the terminal row).
    dedup_hash drives the content bridge for an id-less / divergent-id block.

    Fail-soft: a missing / unreadable queue degrades to ({cpr_id}, hash-from-id-if-present)
    — the id is still matched exactly, only the cross-surface bridge is unavailable."""
    id_set = {cpr_id}
    dedup_hash = None
    m = _HASH_ID_RE.match(cpr_id)
    if m:
        dedup_hash = m.group(1)
    qpath = Path(queue_path) if queue_path else _default_queue()
    if qpath and qpath.is_file():
        try:
            for line in qpath.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or cpr_id not in line:  # cheap pre-filter on the large queue
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("id") != cpr_id:
                    continue
                dh = row.get("dedup_hash")
                if dh:
                    dedup_hash = dh
                    id_set.add(f"cpr_{dh}")
                for a in (row.get("memory_md_aliases") or []):
                    aid = a.get("alias_id") if isinstance(a, dict) else None
                    if aid:
                        id_set.add(aid)
                for k in ("cpr_id", "extracted_from_inline", "source_born"):
                    v = row.get(k)
                    if isinstance(v, str) and v.startswith("cpr"):
                        id_set.add(v)
        except OSError:
            pass
    return id_set, dedup_hash


def flip_inline_status(cpr_id, new_status, review_tic, promoted_to,
                       dry_run=False, search_dir=None, id_set=None, dedup_hash=None,
                       scan_borns=None, borns_dir=None):
    """Advance a NON-TERMINAL `status:` -> new_status in the candidate block for cpr_id.

    Scans every *.md in the auto-memory dir (MEMORY.md + topic files) AND — when the
    born-home scan is ratified (scan_borns; None -> BORNS_WRITEBACK_RATIFIED gate) —
    every borns-tic*.md in the federation born home (audit-logs/governance), FULL corpus
    (not recency-windowed; see module header). A candidate block
    MATCHES when its declared `id:` is in `id_set` (default {cpr_id}) OR — the content
    bridge — its recomputed `sha256(source:lesson)[:16]` equals `dedup_hash`. For each
    matched block whose status is non-terminal (pending / enrichment_* / extracted /
    promotable / ...):
      - replaces the status value with new_status,
      - ensures a `promoted_to:` line is present (inserted after status if absent),
      - ensures a `promoted_tic:` line is present.
    Terminal statuses are left untouched (noop).

    Each action records `matched_by` (id | content_hash), `block_id`, and `flippable`
    (a matched non-terminal block that the caller's `flipped == expected` post-assert
    expects to have flipped) so a matched-but-unflipped block surfaces loudly instead of
    exiting silently. Returns a list of action dicts (one per block touched / inspected)."""
    primary_dir = Path(search_dir) if search_dir else AUTO_MEMORY_DIR
    scan_borns_effective = (BORNS_WRITEBACK_RATIFIED if scan_borns is None
                            else bool(scan_borns))
    actions = []
    id_set = set(id_set) if id_set else set()
    id_set.add(cpr_id)

    # (fpath, surface) search list. Auto-memory (*.md) always; the born home
    # (borns-tic*.md) only when the build-and-gate flag resolves true — FULL corpus, NOT
    # recency-windowed (a by-id writeback must reach a born of any age). The born home is
    # skipped when it equals primary_dir (no double-scan) or is unresolvable (fail-soft).
    scan_files = []
    if primary_dir.is_dir():
        scan_files.extend((f, "auto_memory") for f in sorted(primary_dir.glob("*.md")))
    if scan_borns_effective:
        bh = Path(borns_dir) if borns_dir else _default_borns_home()
        if bh is not None and Path(bh).is_dir() and Path(bh) != primary_dir:
            scan_files.extend((f, "borns") for f in sorted(Path(bh).glob(_BORNS_GLOB)))

    for fpath, surface in scan_files:
        try:
            text = fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _CANDIDATE_OPEN not in text:
            continue
        # Cheap skip: without a content bridge, a file with no id-set member can't match.
        if dedup_hash is None and not any(i in text for i in id_set):
            continue
        lines = text.splitlines(keepends=True)
        changed = False
        for (start, end) in _iter_candidate_blocks(lines):
            block = lines[start:end + 1]
            fields = _parse_candidate_fields(block)
            blk_id = fields.get("id")
            matched_by = None
            if blk_id and blk_id in id_set:
                matched_by = "id"
            elif dedup_hash is not None and "source" in fields and "lesson" in fields:
                if _compute_dedup_hash(fields["source"], fields["lesson"]) == dedup_hash:
                    matched_by = "content_hash"
            if not matched_by:
                continue
            # Locate the status line within the block.
            status_idx = None
            cur_status = None
            indent = ""
            for k in range(start, end + 1):
                m = re.match(r"^(\s*)status:\s*[\"']?([\w-]+)[\"']?\s*$", lines[k])
                if m:
                    status_idx = k
                    cur_status = m.group(2)
                    indent = m.group(1)
                    break
            if status_idx is None:
                # Matched but unflippable (no status line) — an anomaly worth surfacing.
                actions.append({
                    "file": str(fpath), "surface": surface, "cpr_id": cpr_id, "block_id": blk_id,
                    "matched_by": matched_by, "flippable": True,
                    "action": "skip", "reason": "no status line in block",
                })
                continue
            if cur_status in _TERMINAL_STATUSES:
                actions.append({
                    "file": str(fpath), "surface": surface, "cpr_id": cpr_id, "block_id": blk_id,
                    "matched_by": matched_by, "flippable": False,
                    "action": "noop", "reason": f"status already terminal '{cur_status}'",
                })
                continue
            # Advance the non-terminal status value.
            lines[status_idx] = f"{indent}status: {new_status}\n"
            changed = True
            inserts = []
            block_text = "".join(lines[start:end + 1])
            if not re.search(r"^\s*promoted_to:", block_text, re.MULTILINE):
                inserts.append(f"{indent}promoted_to: {json.dumps(promoted_to)}\n")
            if not re.search(r"^\s*promoted_tic:", block_text, re.MULTILINE):
                inserts.append(f"{indent}promoted_tic: {review_tic}\n")
            if inserts:
                lines[status_idx + 1:status_idx + 1] = inserts
            actions.append({
                "file": str(fpath), "surface": surface, "cpr_id": cpr_id, "block_id": blk_id,
                "matched_by": matched_by, "flippable": True,
                "action": "flip", "from": cur_status, "to": new_status,
                "added": [s.strip() for s in inserts],
            })
        if changed and not dry_run:
            fpath.write_text("".join(lines), encoding="utf-8")
    return actions


def stamp_breadcrumb(cpr_id, promoted_to, birth_tic, review_tic, source,
                     dry_run=False, am_dir=None):
    """Stamp `<!-- promoted from <cpr_id> (tic B->R). Source: <src>. -->` on the
    auto-memory TARGET file. Idempotent (skips if cpr_id already in a promoted-from
    comment). No-op for non-auto-memory targets (ledger / CLAUDE.md own their
    provenance via the agent's ledger-inscription step).

    Returns an action dict.
    """
    target = resolve_auto_memory_target(promoted_to, am_dir=am_dir)
    if target is None:
        return {
            "cpr_id": cpr_id, "promoted_to": promoted_to,
            "action": "skip",
            "reason": "non-auto-memory target (ledger/CLAUDE.md provenance owned by "
                      "the ledger-inscription step)",
        }
    try:
        content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"cpr_id": cpr_id, "target": str(target),
                "action": "error", "reason": str(exc)}

    # Idempotency: this cpr_id already carries a promoted-from comment here.
    for m in _PROVENANCE_VERB_RE.finditer(content):
        if cpr_id in m.group(0):
            return {"cpr_id": cpr_id, "target": str(target),
                    "action": "noop", "reason": "breadcrumb already present"}

    tic_span = (f"tic {birth_tic}->{review_tic}"
                if birth_tic is not None else f"/review {review_tic}")
    src = source or "MEMORY.md"
    breadcrumb = (
        f"<!-- promoted from {cpr_id} ({tic_span}). Source: {src}. "
        f"Stamped by review-promote-writeback at promotion time so review-close-check "
        f"resolves it via the provenance index. -->\n"
    )
    if not dry_run:
        sep = "" if content.endswith("\n") else "\n"
        target.write_text(content + sep + breadcrumb, encoding="utf-8")
    return {"cpr_id": cpr_id, "target": str(target),
            "action": "stamp", "breadcrumb": breadcrumb.strip()}


# ---------------------------------------------------------------------------
# Stage-5 down-lane `reinforced_by` stamping (ladder-downlane-spec.md §2 Stage 5,
# §3 KIND — "MEDIUM, extends review-promote-writeback.py").
#
# When a `reinforce_existing` landing occurs — from the up-lane (cpr-stepper) OR a
# down-audit reinforce-signal (a rung independently re-derived a KI from its own
# friction) — the TARGET doctrine entry must RECORD it, or the resilience signal is
# erased at inscription (Drift-1, tic 377). This stamps:
#
#   <!-- reinforced_by: <id> (tic N, source: down-audit@<rung> | up-lane). … -->
#
# on the target LEDGER entry, idempotently, the same way promoted-from breadcrumbs
# are stamped — the resilience-visibility half of the ladder (§8 Stage-5 row).
#
# id-form footgun guard (the tic-472 promotion `id-form-divergence-voids-cross-
# surface-writeback`): the TARGET ledger entry is resolved by its ANCHOR (the
# `invariant_id` tag, the `<a id>` slug, or the heading text) — NEVER by fuzzy
# cpr_id matching against the reinforcing id, whose form (cpr_x vs cpr_x_ticN vs a
# short hash) routinely diverges and silently no-ops a cpr_id-keyed writeback.
# The reinforcing id is recorded INSIDE the comment; it is not the lookup key.
#
# Bounding the entry at the next `### ` heading is the same boundary-aware /
# span-attribution discipline (the OTHER two tic-472 promotions) applied here so a
# stamp lands inside ITS OWN entry, never bleeding into the next.
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{2,4})\s+(.+)$")
_INVARIANT_TAG_RE = re.compile(r"`invariant_id`:\s*`([A-Za-z0-9_]+)`")
_ANCHOR_TAG_RE = re.compile(r'<a id="([^"]+)">')
_REINFORCED_BY_RE = re.compile(r"<!--\s*reinforced_by:\s*(.+?)-->", re.DOTALL)
_PROMOTED_FROM_RE = re.compile(r"<!--\s*promoted(?:-spec)?\s+from\b.*?-->", re.DOTALL)


def _find_entry_span(lines, target_anchor):
    """Locate the ledger entry for target_anchor and return (start, end) line
    indices [heading .. line-before-next-heading]. Resolved by anchor, NOT cpr_id.

    Match order (each unambiguous): invariant_id tag → <a id> slug → heading text
    (slug-normalized substring). Returns (None, None) if unresolved.
    """
    # First locate the line that identifies the entry.
    norm = target_anchor.strip().lower()
    hit = None
    for i, ln in enumerate(lines):
        m = _INVARIANT_TAG_RE.search(ln)
        if m and m.group(1) == target_anchor:
            hit = i
            break
        a = _ANCHOR_TAG_RE.search(ln)
        if a and a.group(1) == target_anchor:
            hit = i
            break
    if hit is None:
        # Fallback: heading text contains the anchor (slug or words).
        slug = re.sub(r"[^a-z0-9]+", "-", norm).strip("-")
        for i, ln in enumerate(lines):
            hm = _HEADING_RE.match(ln)
            if hm:
                htext = hm.group(2).strip().lower()
                hslug = re.sub(r"[^a-z0-9]+", "-", htext).strip("-")
                if norm in htext or (slug and slug in hslug):
                    hit = i
                    break
    if hit is None:
        return None, None

    # Walk UP to the entry's heading.
    start = hit
    while start > 0 and not _HEADING_RE.match(lines[start]):
        start -= 1
    # Walk DOWN to the line before the next heading (entry boundary).
    end = hit + 1
    while end < len(lines) and not _HEADING_RE.match(lines[end]):
        end += 1
    return start, end


def stamp_reinforced_by(ledger_path, target_anchor, reinforced_by, source, tic,
                        dry_run=False):
    """Stamp a `reinforced_by` resilience breadcrumb on the ledger entry identified
    by target_anchor. Idempotent (skips if THIS reinforcing id is already recorded
    for the entry). Inserts after the entry's `promoted from` provenance close if
    present, else at the end of the entry span. Returns an action dict.
    """
    lpath = Path(ledger_path)
    try:
        content = lpath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"action": "error", "reason": str(exc), "ledger": str(lpath)}

    lines = content.splitlines(keepends=True)
    start, end = _find_entry_span(lines, target_anchor)
    if start is None:
        return {"action": "error", "target_anchor": target_anchor,
                "reason": "entry not found by invariant_id / <a id> slug / heading "
                          "(resolved by ANCHOR, never fuzzy cpr_id)"}

    span_text = "".join(lines[start:end])
    # Idempotency: this reinforcing id already recorded for this entry.
    for m in _REINFORCED_BY_RE.finditer(span_text):
        if reinforced_by in m.group(1):
            return {"action": "noop", "target_anchor": target_anchor,
                    "reason": f"reinforced_by {reinforced_by} already stamped here"}

    breadcrumb = (
        f"<!-- reinforced_by: {reinforced_by} (tic {tic}, source: {source}). "
        f"Independent rediscovery / down-audit reinforce-signal — resilience evidence "
        f"(the KI re-derived from rung friction, not merely mentioned). Stamped by "
        f"review-promote-writeback (Stage 5). -->\n"
    )

    # Insert after the entry's `promoted from` provenance close (within the span),
    # else at the end of the span (before the next heading).
    insert_at = end  # default: end of entry span
    for k in range(start, end):
        if _PROMOTED_FROM_RE.search(lines[k]):
            insert_at = k + 1
            break

    # Ensure the inserted line is on its own line (preceding line ends with \n).
    if insert_at > 0 and not lines[insert_at - 1].endswith("\n"):
        lines[insert_at - 1] = lines[insert_at - 1] + "\n"

    if not dry_run:
        lines[insert_at:insert_at] = [breadcrumb]
        lpath.write_text("".join(lines), encoding="utf-8")

    return {"action": "stamp", "target_anchor": target_anchor,
            "reinforced_by": reinforced_by, "source": source, "tic": tic,
            "ledger": str(lpath), "insert_line": insert_at + 1,
            "breadcrumb": breadcrumb.strip()}


def writeback(cpr_id, promoted_to, review_tic, status="promoted",
              birth_tic=None, source=None, dry_run=False, search_dir=None,
              queue_path=None, resolve_aliases=None, scan_borns=None, borns_dir=None):
    """Run both writeback halves for one promoted CogPR. Returns a report dict.

    Resolves a tolerant id-set + content-identity hash from the queue before the inline
    flip so an id-form-divergent / id-less block is still found. Hermetic-test default:
    when a `search_dir` override is in play and no `queue_path` is given, queue resolution
    is skipped (id_set = {cpr_id}); production (search_dir=None) resolves the default queue."""
    birth_tic = _parse_birth_tic(cpr_id, birth_tic)
    if resolve_aliases is None:
        resolve_aliases = not (search_dir is not None and queue_path is None)
    if resolve_aliases:
        id_set, dedup_hash = resolve_promotion_id_set(cpr_id, queue_path=queue_path)
    else:
        id_set, dedup_hash = {cpr_id}, None

    inline = flip_inline_status(cpr_id, status, review_tic, promoted_to,
                                dry_run=dry_run, search_dir=search_dir,
                                id_set=id_set, dedup_hash=dedup_hash,
                                scan_borns=scan_borns, borns_dir=borns_dir)
    breadcrumb = stamp_breadcrumb(cpr_id, promoted_to, birth_tic, review_tic,
                                  source, dry_run=dry_run, am_dir=search_dir)

    flipped = sum(1 for a in inline if a.get("action") == "flip")
    # Born-home legibility: which surface a match landed on, and the effective gate state.
    scanned_borns = (BORNS_WRITEBACK_RATIFIED if scan_borns is None else bool(scan_borns))
    blocks_matched_in_borns = sum(
        1 for a in inline if a.get("matched_by") and a.get("surface") == "borns")
    # post-assert: every MATCHED + FLIPPABLE block must have flipped. By construction
    # they do; a mismatch (e.g. a matched block with no status line) is a real anomaly
    # the guard surfaces instead of exiting clean on `inline_blocks_flipped=0`.
    expected = sum(1 for a in inline if a.get("flippable"))
    blocks_matched = sum(1 for a in inline if a.get("matched_by"))
    matched_by_content = sum(1 for a in inline if a.get("matched_by") == "content_hash")
    return {
        "cpr_id": cpr_id,
        "promoted_to": promoted_to,
        "status": status,
        "review_tic": review_tic,
        "birth_tic": birth_tic,
        "dry_run": dry_run,
        "inline_status_flip": inline,
        "breadcrumb_stamp": breadcrumb,
        "resolution": {
            "id_set": sorted(id_set),
            "dedup_hash": dedup_hash,
            "blocks_matched": blocks_matched,
            "matched_by_content_hash": matched_by_content,
            "queue_resolved": resolve_aliases,
            "scanned_borns": scanned_borns,
            "blocks_matched_in_borns": blocks_matched_in_borns,
        },
        "summary": {
            "inline_blocks_flipped": flipped,
            "breadcrumb_action": breadcrumb.get("action"),
            "post_assert_flipped_eq_expected": flipped == expected,
            "expected_flips": expected,
            "id_divergence_bridged": matched_by_content > 0,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Review Promote Writeback — emit-side inline-status-flip + "
                    "auto-memory breadcrumb stamp (complement to review-close-check.py)"
    )
    parser.add_argument("--cpr-id", required=True,
                        help="The CogPR id (promote mode) OR the reinforcing id "
                             "recorded inside the breadcrumb (reinforced-by mode)")
    parser.add_argument("--promoted-to", required=False, default=None,
                        help="The promotion target (ledger anchor or auto-memory file). "
                             "Required in promote mode; unused in reinforced-by mode.")
    parser.add_argument("--review-tic", type=int, required=True)
    # --- Stage-5 reinforced-by mode (ladder down-lane §5) ---
    parser.add_argument("--reinforce-target-anchor", default=None,
                        dest="reinforce_target_anchor",
                        help="LEDGER-ENTRY ANCHOR to stamp reinforced_by on "
                             "(invariant_id / <a id> slug / heading). Presence "
                             "switches to reinforced-by mode. Resolved by anchor, "
                             "NEVER fuzzy cpr_id (id-form-divergence footgun).")
    parser.add_argument("--reinforce-source", default=None, dest="reinforce_source",
                        help="Reinforcement source: down-audit@<rung> | up-lane")
    parser.add_argument("--reinforce-ledger", default=None, dest="reinforce_ledger",
                        help="Ledger path (default: federation constitution-ledger)")
    parser.add_argument("--birth-tic", type=int, default=None,
                        help="Birth tic (parsed from cpr_id tic suffix if omitted)")
    parser.add_argument("--status", default="promoted",
                        choices=sorted(_TERMINAL_STATUSES),
                        help="Terminal status to write (default: promoted)")
    parser.add_argument("--source", default=None,
                        help="Source surface for the breadcrumb (default: MEMORY.md)")
    parser.add_argument("--project-dir", default=None,
                        help="Zone root (unused for resolution; accepted for parity)")
    parser.add_argument("--search-dir", default=None,
                        help="Override auto-memory search dir (test hook)")
    parser.add_argument("--queue-path", default=None, dest="queue_path",
                        help="Override the CogPR queue path for id-set resolution "
                             "(default: federation audit-logs/cprs/queue.jsonl; test hook)")
    parser.add_argument("--scan-borns", action="store_true", default=None,
                        dest="scan_borns",
                        help="Force-scan the federation born home "
                             "(audit-logs/governance/borns-tic*.md) for the inline flip. "
                             "Absent -> the BORNS_WRITEBACK_RATIFIED gate (default dormant "
                             "until /review ratifies cpr_borns_governance_home).")
    parser.add_argument("--borns-dir", default=None, dest="borns_dir",
                        help="Override the born home dir (test hook).")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", dest="output_json")
    args = parser.parse_args()

    # --- Stage-5 reinforced-by mode (down-lane §5): stamp a resilience breadcrumb
    # on a LEDGER entry resolved by anchor. Distinct from the promote-writeback
    # (which is scoped to auto-memory targets). ---
    if args.reinforce_target_anchor:
        if not args.reinforce_source:
            parser.error("--reinforce-source is required in reinforced-by mode "
                         "(e.g. 'down-audit@global-environmental-fusion' or 'up-lane')")
        ledger = args.reinforce_ledger or _default_federation_ledger()
        if not ledger:
            parser.error("could not resolve a default federation ledger; pass "
                         "--reinforce-ledger explicitly")
        action = stamp_reinforced_by(
            ledger, args.reinforce_target_anchor, args.cpr_id,
            args.reinforce_source, args.review_tic, dry_run=args.dry_run)
        if args.output_json:
            print(json.dumps(action, indent=2))
        else:
            tag = " (dry-run)" if args.dry_run else ""
            print(f"reinforced_by stamp{tag}: {action.get('action')} "
                  f"→ {action.get('target_anchor')}")
            if action.get("action") == "stamp":
                print(f"  {action['ledger']}:{action['insert_line']}")
                print(f"  {action['breadcrumb']}")
            elif action.get("action") in ("noop", "error"):
                print(f"  ({action.get('reason')})")
        return 0

    if not args.promoted_to:
        parser.error("--promoted-to is required in promote mode")

    report = writeback(
        args.cpr_id, args.promoted_to, args.review_tic,
        status=args.status, birth_tic=args.birth_tic, source=args.source,
        dry_run=args.dry_run, search_dir=args.search_dir,
        queue_path=args.queue_path,
        scan_borns=args.scan_borns, borns_dir=args.borns_dir,
    )

    s = report["summary"]
    res = report["resolution"]
    if args.output_json:
        print(json.dumps(report, indent=2))
    else:
        tag = " (dry-run)" if args.dry_run else ""
        print(f"Promote writeback {report['cpr_id']}{tag}:")
        print(f"  inline status blocks flipped: {s['inline_blocks_flipped']}")
        print(f"  breadcrumb: {s['breadcrumb_action']}")
        bc = report["breadcrumb_stamp"]
        if bc.get("action") == "skip":
            print(f"    ({bc['reason']})")
        elif bc.get("action") == "stamp":
            print(f"    -> {bc['target']}")
        # Resolution trace — make a 0-flip outcome legible (which ids were searched,
        # whether a content bridge was available, how many blocks matched).
        bridge = f", content-bridge={res['dedup_hash']}" if res["dedup_hash"] else ""
        print(f"  resolution: {len(res['id_set'])} id(s) searched{bridge}; "
              f"blocks matched={res['blocks_matched']}")
        if res.get("scanned_borns"):
            print(f"  born-home scanned (ratified); blocks matched in borns="
                  f"{res['blocks_matched_in_borns']}")
        elif res.get("blocks_matched") == 0:
            print("  born-home NOT scanned (BORNS_WRITEBACK_RATIFIED dormant; "
                  "--scan-borns to force)")
        if s.get("id_divergence_bridged"):
            print(f"  ⚑ id-form divergence BRIDGED via content-hash "
                  f"({res['matched_by_content_hash']} block(s))")

    # Loud, non-silent guards (the handoff-named `flipped == expected` post-assert +
    # the resolution trace). A clean exit on 0-flip was the original silent no-op.
    rc = 0
    if not s.get("post_assert_flipped_eq_expected", True):
        print(f"  ⚠ POST-ASSERT FAILED: flipped={s['inline_blocks_flipped']} != "
              f"expected={s['expected_flips']} — a matched block did NOT flip "
              f"(surfacing, not exiting clean).", file=sys.stderr)
        rc = 1
    if res["blocks_matched"] == 0:
        print(f"  ⚠ no inline candidate block resolved for {report['cpr_id']} "
              f"(searched id-set + content-hash). If this CogPR has an inline block, "
              f"this is the id-divergence silent-no-op class — inspect.", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
