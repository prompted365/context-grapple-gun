#!/usr/bin/env python3
"""
Doctrine surface resolution — the single, shared, dehydration-aware body locator.

A DEHYDRATED rung's CLAUDE.md is a compact POINTER INDEX: the doctrine BODIES
have been relocated to a sibling ledger.md (federation: constitution-ledger/;
CGG domain: cgg-ledger/). Any consumer that reads a CLAUDE.md FOR ITS BODY
CONTENT — rule extraction, promoted-id scanning, shape analysis, coherence
audit, inscription verification — that reads CLAUDE.md ALONE silently audits the
table of contents, not the law. Post-dehydration it sees pointers, not bodies.

This module is the SINGLE OWNER of two primitives so the dehydration blindspot
is fixed once, at the source, for every consumer rather than re-patched
whack-a-mole per script:

  - resolve_doctrine_surfaces(claude_md_path) -> [claude_md, ledger_md?]
      Given a CLAUDE.md path, return ALL body-bearing doctrine surfaces. For a
      non-dehydrated rung: just [claude_md]. For a dehydrated rung (a sibling
      ledger.md exists): [claude_md, ledger_md].

  - find_doctrine_ids(text) -> set[str]
      Match BOTH doctrine-id forms: the legacy numeric `CogPR-<N>` and the
      current slug `cpr_<slug>`. A scanner that matches only `CogPR-\\d+` is
      blind to every CogPR promoted after the id scheme changed to slugs.

Provenance: this is the runtime materialization of the federation KI
*A structural transform on a shared surface creates a closed consumer-set update
obligation* (tic 333, PROMOTED tic 334). The Pass-4 dehydration relocated
doctrine bodies CLAUDE.md -> ledger.md; that relocation silently obligated an
update on EVERY reader of the old surface. `_find_ledger` and the dehydration
walk were first written inside `load_doctrine_chain.py` (tic 333, the briefing
consumer); they are promoted here so the remaining body-consumers
(ladder-audit, prompt-stack-audit, bench-packet-prep, pattern-mining-context,
rtch, review-close-check) route through one resolver instead of each re-deriving
ledger discovery. See spec_consumer_set_resolve_doctrine_surfaces_tranche_tic334.
"""

from __future__ import annotations

import glob as _glob
import os
import re
from pathlib import Path
from typing import Optional, Union

_PathLike = Union[str, os.PathLike]

# ---------------------------------------------------------------------------
# Ledger discovery (promoted from load_doctrine_chain.py, tic 335)
# ---------------------------------------------------------------------------
#
# Federation's ledger lives under audit-logs/ (not a direct sibling of the
# federation CLAUDE.md); domain ledgers (e.g. CGG's cgg-ledger/) sit beside
# the CLAUDE.md. The rung-keyed globs let a caller that KNOWS the rung name
# narrow the search; the rung-agnostic path (rung=None) tries the federation
# globs and the default sibling globs in turn, so a consumer holding only a
# CLAUDE.md path (and no rung label) still resolves the right ledger.
_LEDGER_GLOBS_BY_RUNG = {
    "federation": [
        "audit-logs/governance/*ledger*/ledger.md",
        "*ledger*/ledger.md",
    ],
}
_DEFAULT_LEDGER_GLOBS = ["*ledger*/ledger.md", "*-ledger/ledger.md"]
# Rung-agnostic union: a consumer that does not know the rung name searches
# the federation-nested location AND the sibling locations. Federation-first so
# a federation root resolves its nested constitution-ledger before any stray
# sibling match; order is otherwise immaterial (first existing match wins).
_AGNOSTIC_LEDGER_GLOBS = [
    "audit-logs/governance/*ledger*/ledger.md",
    "*ledger*/ledger.md",
    "*-ledger/ledger.md",
]


def find_ledger(rung_dir: _PathLike, rung: Optional[str] = None) -> Optional[str]:
    """Locate a dehydrated rung's ledger.md, or None if the rung is not
    dehydrated.

    Args:
        rung_dir: The directory containing the rung's CLAUDE.md.
        rung: Optional rung name ("federation", "domain", ...). When provided
            and a rung-specific glob set exists, it is used; otherwise a
            rung-agnostic union of known ledger locations is searched.

    Returns the first match (sorted) so resolution is deterministic, or None.
    """
    rung_dir = os.fspath(rung_dir)
    if rung is not None and rung in _LEDGER_GLOBS_BY_RUNG:
        patterns = _LEDGER_GLOBS_BY_RUNG[rung]
    elif rung is not None:
        patterns = _DEFAULT_LEDGER_GLOBS
    else:
        patterns = _AGNOSTIC_LEDGER_GLOBS
    for pat in patterns:
        hits = sorted(_glob.glob(os.path.join(rung_dir, pat)))
        hits = [h for h in hits if os.path.isfile(h)]
        if hits:
            return hits[0]
    return None


def resolve_doctrine_surfaces(
    claude_md_path: _PathLike, rung: Optional[str] = None
) -> list[str]:
    """Return ALL body-bearing doctrine surfaces for a CLAUDE.md path.

    The dehydration-aware locator every body-consumer should route through.

    Args:
        claude_md_path: Path to a CLAUDE.md (need not exist — a non-existent
            path yields an empty list, mirroring "no body surface here").
        rung: Optional rung name to narrow ledger discovery.

    Returns:
        [claude_md] for a non-dehydrated rung; [claude_md, ledger_md] for a
        dehydrated rung whose doctrine bodies live in a sibling ledger.md.
        Paths are returned as strings (absolute or as given). Empty list if
        the CLAUDE.md itself does not exist.

    The compact root is returned FIRST (it carries the pointer index and any
    not-yet-dehydrated bodies); the ledger SECOND (the relocated bodies). A
    consumer that wants "the law" must read both; a consumer that wants only
    navigation can read the first.
    """
    p = Path(claude_md_path)
    if not p.is_file():
        return []
    surfaces = [str(p)]
    ledger = find_ledger(p.parent, rung)
    if ledger and os.path.abspath(ledger) != os.path.abspath(str(p)):
        surfaces.append(ledger)
    return surfaces


def is_dehydrated(claude_md_path: _PathLike, rung: Optional[str] = None) -> bool:
    """True iff the rung containing this CLAUDE.md is dehydrated (a sibling
    ledger.md exists). Mirrors the `is_dehydrated` signal in
    load_doctrine_chain.briefing_metadata, sourced from the same resolver."""
    p = Path(claude_md_path)
    if not p.is_file():
        return False
    return find_ledger(p.parent, rung) is not None


def read_doctrine_body(
    claude_md_path: _PathLike, rung: Optional[str] = None, sep: str = "\n"
) -> str:
    """Convenience: concatenate the text of every body-bearing surface for a
    CLAUDE.md path. Consumers that do whole-content lexical analysis
    (redundancy/contradiction/shape scans) can read the dehydrated body in one
    call instead of looping. Unreadable surfaces are skipped silently."""
    parts = []
    for surface in resolve_doctrine_surfaces(claude_md_path, rung):
        try:
            parts.append(Path(surface).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
    return sep.join(parts)


# ---------------------------------------------------------------------------
# Surface-alias resolution for '<surface>#<anchor>' scope forms
# (bk-enrichment-scanner-surface-anchor-target-resolution, struck tic 692)
# ---------------------------------------------------------------------------
#
# The /review lane standardized doctrine scopes as '<surface>#<anchor>'
# (cgg-ledger#mandate-lifecycle-defects, constitution-ledger#...). The surface
# alias IS the ledger directory's basename by that convention. A consumer that
# treats the form as a literal filesystem path manufactures FALSE
# 'target_absence_confirmed (file missing)' evidence on every ledger-scoped
# CogPR — the t691 find. This module owns ledger discovery, so the alias→file
# mapping lives here (extend the single owner; consumers route through it).
_SURFACE_ALIAS_GLOBS = [
    "audit-logs/governance/*-ledger/ledger.md",   # federation rung (nested)
    "*-ledger/ledger.md",                          # zone-root siblings
    "canonical_developer/*/*-ledger/ledger.md",    # developer-estate domain rungs
]


def ledger_alias_map(zone_root: _PathLike) -> dict[str, str]:
    """Map ledger-directory basenames (the '<surface>' in '<surface>#<anchor>'
    scope forms) to their ledger.md paths, discovered from the zone root.
    First-found wins per alias (deterministic: globs searched in declared
    order, hits sorted)."""
    zone_root = os.fspath(zone_root)
    aliases: dict[str, str] = {}
    for pat in _SURFACE_ALIAS_GLOBS:
        for hit in sorted(_glob.glob(os.path.join(zone_root, pat))):
            if os.path.isfile(hit):
                aliases.setdefault(os.path.basename(os.path.dirname(hit)), hit)
    return aliases


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def anchor_present(text: str, anchor: str) -> bool:
    """True iff the anchor exists in a doctrine body — as an explicit
    `<a id="...">`/`<a name="...">` tag (the cgg-ledger form) or as a markdown
    heading whose GitHub-style slug matches (the constitution-ledger form).
    Prefix containment is accepted either way because compact-root pointers
    truncate long slugs (e.g. `...-architect-authorized-c`)."""
    want = _slug(anchor)
    if not want:
        return False
    for m in re.finditer(r'<a\s+(?:id|name)="([^"]+)"', text):
        got = _slug(m.group(1))
        if got == want or got.startswith(want) or want.startswith(got):
            return True
    for line in text.splitlines():
        if line.startswith("#"):
            got = _slug(line.lstrip("#").strip())
            if got and (got == want or got.startswith(want) or want.startswith(got)):
                return True
    return False


def resolve_surface_anchor(
    scope: str, zone_root: _PathLike
) -> tuple[Optional[str], Optional[str]]:
    """Resolve a '<surface>#<anchor>' scope form to (ledger_path, anchor).

    Returns (None, None) when the scope is not a surface#anchor form (a path
    containing '/' before the '#' is a literal file path with a fragment, not
    an alias). Returns (None, anchor) when the form matches but no ledger
    resolves for the alias — the caller keeps its literal-path fallback."""
    if "#" not in scope:
        return None, None
    surface, anchor = scope.split("#", 1)
    surface = surface.strip()
    if not surface or "/" in surface or "." in surface:
        return None, None
    ledger = ledger_alias_map(zone_root).get(surface)
    return ledger, anchor.strip()


# ---------------------------------------------------------------------------
# Doctrine-id matching (legacy CogPR-N + current cpr_<slug>)
# ---------------------------------------------------------------------------
#
# Two id schemes coexist in the corpus:
#   - legacy:  CogPR-26, CogPR-160   (numeric, pre-slug era)
#   - current: cpr_<lowercase_slug>  (e.g. cpr_structural_transform_..._tic333)
# A scanner that matches only `CogPR-\d+` is structurally blind to every
# CogPR promoted after the scheme changed — which is the majority of the live
# corpus. DOCTRINE_ID_RE matches both; find_doctrine_ids returns the set.
#
# cpr_<slug> requires a lowercase-letter lead and at least one more char so it
# does not match a bare "cpr_" prefix or an UPPER token; the legacy alternative
# is anchored to the literal "CogPR-" + digits.
DOCTRINE_ID_RE = re.compile(r"CogPR-\d+|cpr_[a-z][a-z0-9_]+")
# Legacy-only matcher, kept named for callers that still need to distinguish
# the numeric form (e.g. doctrine_ref gating that compares against CogPR-N).
LEGACY_COGPR_RE = re.compile(r"CogPR-\d+")


def find_doctrine_ids(text: str) -> set[str]:
    """Return the set of all doctrine ids (both schemes) referenced in text."""
    if not text:
        return set()
    return set(DOCTRINE_ID_RE.findall(text))


def find_doctrine_ids_in_surfaces(
    claude_md_path: _PathLike, rung: Optional[str] = None
) -> set[str]:
    """Return all doctrine ids found across every body-bearing surface for a
    CLAUDE.md path (compact root + ledger if dehydrated). The dehydration-aware
    replacement for `set(re.findall(r'CogPR-\\d+', claude_md_text))`."""
    return find_doctrine_ids(read_doctrine_body(claude_md_path, rung))
