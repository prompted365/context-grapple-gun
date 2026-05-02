#!/usr/bin/env python3
"""
Load Doctrine Chain — assemble rung-aware CLAUDE.md briefings for subagent dispatch.

The Claude Code harness loads only the project-root CLAUDE.md plus user-global
~/.claude/CLAUDE.md into a subagent's context. In a federation tree with
nested domain/estate doctrine surfaces (canonical_developer/*/CLAUDE.md),
those domain-rung surfaces are invisible to subagents by default.

This helper closes that gap by walking the rung-marker chain (.federation-root,
.estate-root, .domain-root, .site-root via .ticzone) and assembling a
concatenated briefing string that callers (skills, dispatch wrappers) include
in subagent prompts when work crosses rung.

Diagnostic frame: this is the runtime-side mechanism for the Conductor-Score-
Runtime Parity invariant (federation KI). The federation has the data (zone
markers + walk-up infrastructure in zone_root.py) but no read-side consumer
owned dispatch-briefing assembly until this helper. See:
- audit-logs/governance/zone-marker-utilization-audit-tic211.md
- audit-logs/governance/claudemd-hierarchy-probe-tic211.md
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

# Reuse zone_root infrastructure for marker detection
_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
sys.path.insert(0, _SCRIPTS)
from zone_root import resolve_rung_position, RUNG_ORDER  # noqa: E402

# Briefing format: rungs are concatenated lowest-to-highest (site → federation),
# inverting CLAUDE.md authority direction (federation → site) so that local
# context appears first when prepended to a system prompt. Authority is
# preserved in the section headers; ordering optimizes for cognitive locality.
RUNG_HEADERS = {
    "global": "## Global Persona Doctrine (~/.claude/CLAUDE.md)",
    "federation": "## Federation Doctrine (canonical/CLAUDE.md)",
    "estate": "## Estate Doctrine",
    "domain": "## Domain Doctrine",
    "site": "## Site Doctrine",
}

DEFAULT_TRUNCATE_PER_RUNG = 12000  # chars; trim long surfaces to keep briefing compact


def _read_claude_md(rung_dir: str) -> Optional[str]:
    """Read a CLAUDE.md adjacent to a rung marker. Returns None if absent."""
    candidate = Path(rung_dir) / "CLAUDE.md"
    if not candidate.is_file():
        return None
    try:
        return candidate.read_text(encoding="utf-8")
    except OSError:
        return None


def _truncate_for_briefing(text: str, limit: int) -> str:
    """Truncate text at limit chars, marking truncation point. Preserves first
    ~80% and last ~10% of the limit; truncation marker fills the gap."""
    if len(text) <= limit:
        return text
    head = int(limit * 0.80)
    tail = int(limit * 0.10)
    marker = (
        f"\n\n…[truncated for briefing — full file at named path; "
        f"{len(text) - head - tail} chars elided]…\n\n"
    )
    return text[:head] + marker + text[-tail:]


def assemble_rung_briefing(
    target_path: str,
    truncate_per_rung: int = DEFAULT_TRUNCATE_PER_RUNG,
    include_global: bool = False,
) -> str:
    """Assemble a multi-rung CLAUDE.md briefing for subagent dispatch.

    Walks up from `target_path` to find rung markers (.federation-root,
    .estate-root, .domain-root, .ticzone for site). For each rung found,
    reads the adjacent CLAUDE.md and concatenates them lowest-to-highest
    (site → federation) with explicit rung headers and source paths.

    Args:
        target_path: Filesystem path the subagent will work against. The
            briefing assembles doctrine for the rung chain containing this
            path, walking upward to filesystem root.
        truncate_per_rung: Char limit per rung's CLAUDE.md content. Long
            surfaces (e.g., CGG/CLAUDE.md at 117KB) are truncated to keep
            the assembled briefing compact. Set to 0 or large negative to
            disable truncation. Default 12000 chars (~250 lines).
        include_global: If True, prepend ~/.claude/CLAUDE.md content. Default
            False — the harness already loads global into subagent context;
            including it again duplicates and wastes context budget.

    Returns:
        Concatenated briefing string suitable for embedding in a subagent
        dispatch prompt. Empty string if no rungs found (target outside any
        federation tree).

    Discipline notes:
        - The briefing is text only; it does not invoke the harness or modify
          subagent state. Caller is responsible for embedding the returned
          string in the dispatch prompt.
        - Authority flows downward only (federation → site); the briefing
          presents lowest-rung-first for cognitive locality but rung headers
          and source paths preserve authority traceability.
        - When work crosses rung (e.g., dispatched at canonical/ but touches
          CGG-specific code), call with target_path inside the deeper rung
          to capture the relevant chain.
    """
    if not target_path:
        target_path = os.getcwd()

    rp = resolve_rung_position(target_path)
    topology = rp.get("topology", {})

    sections = []
    seen_paths = set()  # dedup: zone_root may return same path under multiple
                        # rung labels when a single dir carries multiple markers
                        # (e.g., canonical/ has both .ticzone [site] and
                        # .federation-root). The deepest rung label wins.

    # When a single directory carries multiple rung markers (e.g., canonical/
    # has both .ticzone [site] and .federation-root), prefer the highest rung
    # label (federation > estate > domain > site). Federation roots that also
    # carry a .ticzone should appear as Federation, not Site. Authority
    # supersedes specificity at this collision boundary.
    rung_assignments = {}  # path -> rung (highest-rung wins on collision)
    for rung in reversed(RUNG_ORDER):  # federation, estate, domain, site
        rung_info = topology.get(rung)
        if not rung_info:
            continue
        rung_dir = rung_info.get("path")
        if not rung_dir:
            continue
        if rung_dir not in rung_assignments:
            rung_assignments[rung_dir] = rung

    for rung in RUNG_ORDER:
        rung_info = topology.get(rung)
        if not rung_info:
            continue
        rung_dir = rung_info.get("path")
        rung_name = rung_info.get("name", rung)
        if not rung_dir or rung_dir in seen_paths:
            continue
        if rung_assignments.get(rung_dir) != rung:
            # Another rung label claimed this path more specifically; skip
            continue
        body = _read_claude_md(rung_dir)
        if not body:
            continue
        if truncate_per_rung > 0:
            body = _truncate_for_briefing(body, truncate_per_rung)
        header = f"{RUNG_HEADERS.get(rung, '## Doctrine')} — {rung_name} ({rung_dir}/CLAUDE.md)"
        sections.append(f"{header}\n\n{body.strip()}\n")
        seen_paths.add(rung_dir)

    if include_global and rp.get("global"):
        try:
            global_body = Path(rp["global"]).read_text(encoding="utf-8")
            if truncate_per_rung > 0:
                global_body = _truncate_for_briefing(global_body, truncate_per_rung)
            sections.append(
                f"{RUNG_HEADERS['global']}\n\n{global_body.strip()}\n"
            )
        except OSError:
            pass

    if not sections:
        return ""

    preamble = (
        "<!-- rung-aware doctrine briefing assembled by load_doctrine_chain.py.\n"
        "     Rungs are presented lowest-to-highest (site → federation) for cognitive\n"
        "     locality; authority flows downward only per federation invariant. -->\n\n"
    )
    return preamble + "\n---\n\n".join(sections)


def briefing_metadata(target_path: str) -> dict:
    """Return metadata about what assemble_rung_briefing would include for a
    given target_path, without reading or assembling the bodies. Useful for
    logging or for callers that want to decide briefing inclusion based on
    rung depth."""
    if not target_path:
        target_path = os.getcwd()
    rp = resolve_rung_position(target_path)
    topology = rp.get("topology", {})
    rungs_found = []
    for rung in RUNG_ORDER:
        info = topology.get(rung)
        if info and info.get("path"):
            claude_md = Path(info["path"]) / "CLAUDE.md"
            rungs_found.append({
                "rung": rung,
                "name": info.get("name", rung),
                "path": info["path"],
                "has_claude_md": claude_md.is_file(),
                "claude_md_bytes": claude_md.stat().st_size if claude_md.is_file() else 0,
            })
    return {
        "target_path": target_path,
        "current_rung": rp.get("current_rung"),
        "rungs_found": rungs_found,
        "system_map": rp.get("system_map"),
        "global": rp.get("global"),
    }


if __name__ == "__main__":
    # CLI usage: load_doctrine_chain.py <target_path> [--metadata|--no-truncate|--include-global]
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Assemble rung-aware CLAUDE.md briefing for subagent dispatch."
    )
    parser.add_argument(
        "target_path",
        nargs="?",
        default=os.getcwd(),
        help="Filesystem path to derive rung chain from (default: cwd)",
    )
    parser.add_argument(
        "--metadata",
        action="store_true",
        help="Print metadata about rung chain without assembling briefing",
    )
    parser.add_argument(
        "--no-truncate",
        action="store_true",
        help="Disable per-rung truncation (full bodies)",
    )
    parser.add_argument(
        "--include-global",
        action="store_true",
        help="Include ~/.claude/CLAUDE.md (default: false; harness loads it already)",
    )
    parser.add_argument(
        "--truncate-per-rung",
        type=int,
        default=DEFAULT_TRUNCATE_PER_RUNG,
        help=f"Max chars per rung body (default: {DEFAULT_TRUNCATE_PER_RUNG})",
    )
    args = parser.parse_args()

    if args.metadata:
        print(json.dumps(briefing_metadata(args.target_path), indent=2))
    else:
        truncate = 0 if args.no_truncate else args.truncate_per_rung
        briefing = assemble_rung_briefing(
            args.target_path,
            truncate_per_rung=truncate,
            include_global=args.include_global,
        )
        print(briefing)
