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
    topic file), flipping ONLY `status: pending` (terminal states are left untouched).
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


def flip_inline_status(cpr_id, new_status, review_tic, promoted_to,
                       dry_run=False, search_dir=None):
    """Flip `status: pending` -> new_status in the candidate block for cpr_id.

    Scans every *.md in the auto-memory dir (MEMORY.md + topic files). For each
    candidate block whose `id:` matches cpr_id and whose status is `pending`:
      - replaces the status value with new_status,
      - ensures a `promoted_to:` line is present (inserted after status if absent),
      - ensures a `promoted_tic:` line is present.

    Returns a list of action dicts (one per block touched / inspected).
    """
    search_dir = Path(search_dir) if search_dir else AUTO_MEMORY_DIR
    actions = []
    if not search_dir.is_dir():
        return actions

    for fpath in sorted(search_dir.glob("*.md")):
        try:
            text = fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if cpr_id not in text:
            continue
        lines = text.splitlines(keepends=True)
        changed = False
        for (start, end) in _iter_candidate_blocks(lines):
            block = lines[start:end + 1]
            id_match = any(
                re.match(r"\s*id:\s*[\"']?" + re.escape(cpr_id) + r"[\"']?\s*$", ln)
                for ln in block
            )
            if not id_match:
                continue
            # Locate the status line within the block.
            status_idx = None
            cur_status = None
            for k in range(start, end + 1):
                m = re.match(r"^(\s*)status:\s*[\"']?([\w-]+)[\"']?\s*$", lines[k])
                if m:
                    status_idx = k
                    cur_status = m.group(2)
                    indent = m.group(1)
                    break
            if status_idx is None:
                actions.append({
                    "file": str(fpath), "cpr_id": cpr_id,
                    "action": "skip", "reason": "no status line in block",
                })
                continue
            if cur_status != "pending":
                actions.append({
                    "file": str(fpath), "cpr_id": cpr_id,
                    "action": "noop", "reason": f"status already '{cur_status}'",
                })
                continue
            # Flip the status value.
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
                "file": str(fpath), "cpr_id": cpr_id,
                "action": "flip", "from": "pending", "to": new_status,
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
              birth_tic=None, source=None, dry_run=False, search_dir=None):
    """Run both writeback halves for one promoted CogPR. Returns a report dict."""
    birth_tic = _parse_birth_tic(cpr_id, birth_tic)
    inline = flip_inline_status(cpr_id, status, review_tic, promoted_to,
                                dry_run=dry_run, search_dir=search_dir)
    breadcrumb = stamp_breadcrumb(cpr_id, promoted_to, birth_tic, review_tic,
                                  source, dry_run=dry_run, am_dir=search_dir)
    flipped = sum(1 for a in inline if a.get("action") == "flip")
    return {
        "cpr_id": cpr_id,
        "promoted_to": promoted_to,
        "status": status,
        "review_tic": review_tic,
        "birth_tic": birth_tic,
        "dry_run": dry_run,
        "inline_status_flip": inline,
        "breadcrumb_stamp": breadcrumb,
        "summary": {
            "inline_blocks_flipped": flipped,
            "breadcrumb_action": breadcrumb.get("action"),
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
    )

    if args.output_json:
        print(json.dumps(report, indent=2))
    else:
        s = report["summary"]
        tag = " (dry-run)" if args.dry_run else ""
        print(f"Promote writeback {report['cpr_id']}{tag}:")
        print(f"  inline status blocks flipped: {s['inline_blocks_flipped']}")
        print(f"  breadcrumb: {s['breadcrumb_action']}")
        bc = report["breadcrumb_stamp"]
        if bc.get("action") == "skip":
            print(f"    ({bc['reason']})")
        elif bc.get("action") == "stamp":
            print(f"    -> {bc['target']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
