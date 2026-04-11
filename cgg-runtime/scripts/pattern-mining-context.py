#!/usr/bin/env python3
"""pattern-mining-context.py — Pattern mining context procurement

Concatenates, shapes, and presents governance surfaces for pattern mining
agents. NOT a pattern detector — an intelligent context procurer that makes
mining cheaper and broader.

Design principles:
- Token-efficient: statistics over raw dumps
- Traversable: indexed sections with jump markers
- Honest: includes "surfaces NOT scanned" section
- Empowering: heuristic hints that suggest where to look, not what to find

Usage:
    python3 pattern-mining-context.py [--zone-root PATH] [--tic CURRENT_TIC]
        [--window N] [--output PATH] [--sections SECTION,SECTION,...]

Sections: queue, signals, tics, arenas, conformations, routing, biome,
          mogul_runs, memory, ak_specs, claude_md, all (default: all)
"""

import argparse
import collections
import glob
import hashlib
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Zone root resolution
# ---------------------------------------------------------------------------

def resolve_zone_root(start=None):
    p = Path(start or os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()
    for _ in range(20):
        if (p / ".ticzone").exists() or (p / "audit-logs").is_dir():
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path.cwd()


# ---------------------------------------------------------------------------
# NLP cheapies
# ---------------------------------------------------------------------------

def shannon_entropy(text):
    """Shannon entropy of character distribution — proxy for information density."""
    if not text:
        return 0.0
    freq = collections.Counter(text.lower())
    total = len(text)
    return -sum((c / total) * math.log2(c / total) for c in freq.values() if c > 0)


def bigram_frequency(texts, top_n=20):
    """Top bigrams across a corpus of texts — surfaces recurring concepts."""
    stop = {"the", "and", "for", "that", "this", "with", "from", "have", "not",
            "are", "was", "but", "been", "has", "its", "all", "can", "will",
            "each", "than", "into", "does", "must", "should", "would", "may",
            "also", "any", "when", "only", "more", "which", "their", "other",
            "via", "use", "new", "per", "one", "two", "see", "how", "what",
            "who", "why", "get", "set", "run", "add", "yet", "did", "got",
            "same", "both", "such", "just", "then", "some", "very", "over",
            "they", "were", "had", "our", "out", "own", "too", "you", "his",
            "her", "she", "him", "who", "its", "let"}
    bigrams = collections.Counter()
    for text in texts:
        words = re.findall(r'[a-z_]{3,}', text.lower())
        words = [w for w in words if w not in stop]
        for i in range(len(words) - 1):
            bigrams[(words[i], words[i + 1])] += 1
    return bigrams.most_common(top_n)


def temporal_clusters(events, time_key="timestamp", window_hours=24):
    """Find temporal clusters — periods of high event density."""
    times = []
    for e in events:
        ts = e.get(time_key, e.get("created_at", e.get("extracted_at", "")))
        if ts:
            try:
                t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                times.append(t)
            except (ValueError, TypeError):
                pass
    if not times:
        return []
    times.sort()
    clusters = []
    cluster_start = times[0]
    cluster_count = 1
    for i in range(1, len(times)):
        if (times[i] - times[i - 1]).total_seconds() < window_hours * 3600:
            cluster_count += 1
        else:
            if cluster_count >= 3:
                clusters.append({
                    "start": cluster_start.isoformat(),
                    "end": times[i - 1].isoformat(),
                    "count": cluster_count,
                })
            cluster_start = times[i]
            cluster_count = 1
    if cluster_count >= 3:
        clusters.append({
            "start": cluster_start.isoformat(),
            "end": times[-1].isoformat(),
            "count": cluster_count,
        })
    return clusters


def entity_cooccurrence(records, id_key="id", text_key="lesson"):
    """Which CogPR IDs / signal IDs co-occur in text fields."""
    id_pattern = re.compile(r'CogPR-\d+|PAT-T\d+-[A-Z]+-[A-Z]|sig_\S+|INV-[A-Z]+-\d+')
    cooccur = collections.Counter()
    for rec in records:
        text = str(rec.get(text_key, "")) + " " + str(rec.get("source", ""))
        mentions = set(id_pattern.findall(text))
        mentions_list = sorted(mentions)
        for i in range(len(mentions_list)):
            for j in range(i + 1, len(mentions_list)):
                cooccur[(mentions_list[i], mentions_list[j])] += 1
    return cooccur.most_common(15)


# ---------------------------------------------------------------------------
# Surface readers
# ---------------------------------------------------------------------------

def read_jsonl(path, limit=None):
    """Read JSONL file, return list of dicts."""
    records = []
    if not os.path.isfile(path):
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    if limit:
        records = records[-limit:]
    return records


def read_json(path):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Section generators
# ---------------------------------------------------------------------------

def section_queue(zone_root, window_tics, current_tic):
    """CPR queue shape analysis."""
    records = read_jsonl(zone_root / "audit-logs" / "cprs" / "queue.jsonl")
    if not records:
        return "## CPR Queue\n\nNo queue data found.\n"

    status_counts = collections.Counter(r.get("status", "unknown") for r in records)
    band_counts = collections.Counter(r.get("band", "unknown") for r in records)
    subsystem_counts = collections.Counter(r.get("subsystem", "unknown") for r in records)
    lesson_type_counts = collections.Counter(r.get("lesson_type", "unknown") for r in records)

    # Recent window
    recent = [r for r in records if r.get("birth_tic", 0) >= current_tic - window_tics]

    # Pending items
    pending = [r for r in records if r.get("status") == "pending"]

    # Lesson text corpus for bigrams
    lesson_texts = [r.get("lesson", "") for r in records if r.get("status") in ("pending", "promoted")]
    top_bigrams = bigram_frequency(lesson_texts, 15)

    # Co-occurrence
    cooccur = entity_cooccurrence(records)

    # Temporal clusters
    clusters = temporal_clusters(records, time_key="extracted_at")

    lines = [
        "## CPR Queue Shape",
        f"\nTotal: {len(records)} | Recent (last {window_tics} tics): {len(recent)}",
        f"\n### Status Distribution",
    ]
    for s, c in status_counts.most_common():
        lines.append(f"  {s}: {c}")

    lines.append(f"\n### Band Distribution")
    for b, c in band_counts.most_common():
        lines.append(f"  {b}: {c}")

    lines.append(f"\n### Subsystem Distribution")
    for s, c in subsystem_counts.most_common():
        lines.append(f"  {s}: {c}")

    lines.append(f"\n### Lesson Type Distribution")
    for t, c in lesson_type_counts.most_common():
        lines.append(f"  {t}: {c}")

    if pending:
        lines.append(f"\n### Pending CPRs ({len(pending)})")
        for p in pending:
            lines.append(f"  {p.get('id','?')}: {p.get('lesson','')[:100]}...")
            lines.append(f"    birth_tic={p.get('birth_tic','?')} band={p.get('band','?')} confidence={p.get('confidence_tier','?')}")

    if top_bigrams:
        lines.append(f"\n### Top Concept Bigrams (promoted+pending lessons)")
        for (a, b), c in top_bigrams:
            lines.append(f"  {a} {b}: {c}")

    if cooccur:
        lines.append(f"\n### Entity Co-occurrence (cross-references in lessons)")
        for (a, b), c in cooccur:
            lines.append(f"  {a} ↔ {b}: {c}")

    if clusters:
        lines.append(f"\n### Temporal Clusters (extraction bursts)")
        for cl in clusters:
            lines.append(f"  {cl['start'][:10]} to {cl['end'][:10]}: {cl['count']} CPRs")

    return "\n".join(lines) + "\n"


def section_signals(zone_root, window_tics, current_tic):
    """Signal manifold shape."""
    manifest = read_jsonl(zone_root / "audit-logs" / "signals" / "active-manifest.jsonl")
    active = [s for s in manifest if s.get("status") == "active"]
    resolved = [s for s in manifest if s.get("status") == "resolved"]

    # Raw signal history (recent files)
    signal_dir = zone_root / "audit-logs" / "signals"
    raw_signals = []
    for f in sorted(glob.glob(str(signal_dir / "*.jsonl"))):
        if "manifest" in f or "staging" in f:
            continue
        raw_signals.extend(read_jsonl(f))

    kind_counts = collections.Counter(s.get("kind", "?") for s in raw_signals)
    band_counts = collections.Counter(s.get("band", "?") for s in raw_signals)

    lines = [
        "## Signal Manifold Shape",
        f"\nActive: {len(active)} | Resolved: {len(resolved)} | Raw history: {len(raw_signals)}",
        f"\n### Active Signals",
    ]
    for s in active:
        age = current_tic - s.get("source_tic", current_tic)
        lines.append(f"  {s.get('kind','?')}/{s.get('volume','?')} age={age}t {s.get('signal_id','?')}")
        lines.append(f"    {s.get('summary','')[:120]}")

    if resolved:
        lines.append(f"\n### Recently Resolved ({len(resolved)})")
        for s in resolved[-5:]:
            lines.append(f"  {s.get('signal_id','?')}: {s.get('resolution','')[:100]}")

    lines.append(f"\n### Signal Kind Distribution (all history)")
    for k, c in kind_counts.most_common():
        lines.append(f"  {k}: {c}")

    lines.append(f"\n### Signal Band Distribution")
    for b, c in band_counts.most_common():
        lines.append(f"  {b}: {c}")

    # Dedup check — same signal_id appearing multiple times
    id_counts = collections.Counter(s.get("signal_id", s.get("id", "?")) for s in raw_signals)
    dupes = {k: v for k, v in id_counts.items() if v > 1}
    if dupes:
        lines.append(f"\n### Duplicate Signal IDs (potential dedup gaps)")
        for sid, cnt in sorted(dupes.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"  {sid}: {cnt}x")

    return "\n".join(lines) + "\n"


def section_tics(zone_root, window_tics, current_tic):
    """Tic event history shape."""
    tic_dir = zone_root / "audit-logs" / "tics"
    all_tics = []
    for f in sorted(glob.glob(str(tic_dir / "*.jsonl"))):
        all_tics.extend(read_jsonl(f))

    counted = [t for t in all_tics if t.get("count_mode") == "counted"]
    ignored = [t for t in all_tics if t.get("count_mode") == "ignored"]

    # Cadence position distribution
    pos_counts = collections.Counter(t.get("cadence_position", "?") for t in counted)

    # Tic velocity (tics per day)
    daily = collections.Counter()
    for t in counted:
        ts = t.get("tic", "")[:10]
        if ts:
            daily[ts] += 1

    lines = [
        "## Tic History Shape",
        f"\nTotal events: {len(all_tics)} | Counted: {len(counted)} | Ignored: {len(ignored)}",
        f"\n### Cadence Position",
    ]
    for p, c in pos_counts.most_common():
        lines.append(f"  {p}: {c}")

    if daily:
        lines.append(f"\n### Tic Velocity (tics/day, last 10 days)")
        for day in sorted(daily.keys())[-10:]:
            lines.append(f"  {day}: {daily[day]}")

    return "\n".join(lines) + "\n"


def section_arenas(zone_root, window_tics, current_tic):
    """Arena pressure report summaries."""
    arena_dir = zone_root / "audit-logs" / "arenas" / "pressure-reports"
    reports = []
    for f in sorted(glob.glob(str(arena_dir / "*.json"))):
        data = read_json(f)
        if data:
            reports.append(data)

    if not reports:
        return "## Arenas\n\nNo pressure reports found.\n"

    lines = [
        "## Arena Pressure Reports Shape",
        f"\nTotal reports: {len(reports)}",
    ]

    for r in reports:
        aid = r.get("arena_id", "?")
        template = r.get("template", "?")
        cds = r.get("convergent_discoveries", [])
        uts = r.get("unresolved_tensions", [])
        cprs = r.get("candidate_cogprs", [])
        lines.append(f"\n### {aid}")
        lines.append(f"  Template: {template}")
        lines.append(f"  Convergent: {len(cds)} | Unresolved: {len(uts)} | CogPR candidates: {len(cprs)}")
        for cd in cds:
            lines.append(f"  [CD] {cd.get('finding','')[:100]}")
        for ut in uts:
            lines.append(f"  [UT] {ut.get('tension','')[:100]} (severity={ut.get('severity','?')})")

    return "\n".join(lines) + "\n"


def section_conformations(zone_root, window_tics, current_tic):
    """Conformation history shape."""
    conf_dir = zone_root / "audit-logs" / "conformations"
    confs = []
    for f in sorted(glob.glob(str(conf_dir / "*.json")))[-window_tics:]:
        data = read_json(f)
        if data:
            confs.append((os.path.basename(f), data))

    if not confs:
        return "## Conformations\n\nNo conformation snapshots found.\n"

    lines = [
        "## Conformation History",
        f"\nSnapshots available: {len(confs)} (showing last {min(len(confs), window_tics)})",
    ]
    for fname, c in confs[-10:]:
        summary = c.get("summary", c.get("conformation_summary", {}))
        if isinstance(summary, dict):
            lines.append(f"  {fname}: signals={summary.get('active_signals', '?')} warrants={summary.get('active_warrants', '?')} pending_cprs={summary.get('pending_cprs', '?')}")
        else:
            lines.append(f"  {fname}: {str(summary)[:100]}")

    return "\n".join(lines) + "\n"


def section_routing(zone_root, window_tics, current_tic):
    """Routing decision shape."""
    records = read_jsonl(zone_root / "audit-logs" / "routing" / "decisions.jsonl")
    if not records:
        return "## Routing Decisions\n\nNo routing decisions found.\n"

    mode_counts = collections.Counter(r.get("routing", {}).get("mode", "?") for r in records)
    weight_counts = collections.Counter(r.get("input", {}).get("weight", "?") for r in records)
    outcomes = [r for r in records if r.get("outcome")]
    pending = [r for r in records if not r.get("outcome")]

    lines = [
        "## Routing Decision Shape",
        f"\nTotal: {len(records)} | Outcomes recorded: {len(outcomes)} | Pending: {len(pending)}",
        f"\n### Mode Distribution",
    ]
    for m, c in mode_counts.most_common():
        lines.append(f"  {m}: {c}")
    lines.append(f"\n### Weight Distribution")
    for w, c in weight_counts.most_common():
        lines.append(f"  {w}: {c}")

    return "\n".join(lines) + "\n"


def section_biome(zone_root, window_tics, current_tic):
    """Biome state shape."""
    topo = read_json(zone_root / "audit-logs" / "biome" / "state" / "topology.json")
    orgs = read_json(zone_root / "audit-logs" / "biome" / "state" / "organisms.json")

    if not topo or not orgs:
        return "## Biome\n\nNo biome state found.\n"

    nodes = topo.get("nodes", [])
    edges = topo.get("edges", [])
    visitors = orgs.get("visitors", [])
    cycle = topo.get("cycle", "?")

    # Resource distribution
    resources = [n.get("resource_level", 0) for n in nodes]
    sectors = collections.Counter(n.get("sector", "?") for n in nodes)

    # Standing distribution
    standings = collections.Counter(v.get("standing", "?") for v in visitors)

    # Connection distribution
    connections = [n.get("connection_count", 0) for n in nodes]
    isolated = sum(1 for c in connections if c == 0)

    lines = [
        "## Biome State Shape",
        f"\nCycle: {cycle} | Nodes: {len(nodes)} | Edges: {len(edges)} | Visitors: {len(visitors)}",
        f"\n### Resource Distribution",
        f"  min={min(resources):.1f} max={max(resources):.1f} mean={sum(resources)/len(resources):.1f} std={_std(resources):.1f}" if resources else "  (empty)",
        f"  Gini coefficient: {_gini(resources):.3f}" if resources else "",
        f"\n### Sector Distribution",
    ]
    for s, c in sectors.most_common():
        sector_resources = [n.get("resource_level", 0) for n in nodes if n.get("sector") == s]
        sector_sources = sum(1 for n in nodes if n.get("sector") == s and n.get("is_source"))
        lines.append(f"  sector {s}: {c} nodes, {sector_sources} sources, avg_resource={sum(sector_resources)/len(sector_resources):.1f}")

    lines.append(f"\n### Standing Distribution")
    for st, c in standings.most_common():
        lines.append(f"  {st}: {c}")

    lines.append(f"\n### Connectivity")
    lines.append(f"  Isolated nodes: {isolated}/{len(nodes)}")
    lines.append(f"  Connection range: {min(connections)}-{max(connections)}" if connections else "")

    # Per-visitor detail (compact)
    lines.append(f"\n### Visitor Detail")
    for n in nodes:
        vid = n.get("node_id", "?").replace("ent_visitor_", "")
        lines.append(f"  {vid:10s} s={n.get('sector','?')} res={n.get('resource_level',0):.1f} conn={n.get('connection_count',0)} src={'Y' if n.get('is_source') else 'N'}")

    return "\n".join(lines) + "\n"


def section_mogul_runs(zone_root, window_tics, current_tic):
    """Mogul run artifact shape."""
    run_dir = zone_root / "audit-logs" / "mogul" / "runs"
    runs = []
    for f in sorted(glob.glob(str(run_dir / "*.json")))[-5:]:
        data = read_json(f)
        if data:
            runs.append((os.path.basename(f), data))

    if not runs:
        return "## Mogul Runs\n\nNo run artifacts found.\n"

    lines = [
        "## Mogul Run History",
        f"\nRun artifacts: {len(runs)} (showing last 5)",
    ]
    for fname, r in runs:
        cycles = r.get("cycles_executed", [])
        method = r.get("pattern_mining", {}).get("method", "unknown")
        pm = r.get("pattern_mining", {})
        advance = pm.get("summary", {}).get("advance", 0)
        flag = pm.get("summary", {}).get("flag", 0)
        hold = pm.get("summary", {}).get("hold", 0)
        surprise = r.get("signal_scan", {}).get("surprise_assessment", "")[:120]
        lines.append(f"\n### {fname}")
        lines.append(f"  Cycles: {', '.join(cycles)}")
        lines.append(f"  Pattern method: {method}")
        lines.append(f"  Patterns: advance={advance} flag={flag} hold={hold}")
        if surprise:
            lines.append(f"  Surprise: {surprise}...")

    return "\n".join(lines) + "\n"


def section_ak_specs(zone_root, window_tics, current_tic):
    """Autonomous kernel spec inventory."""
    ak_dir = zone_root / "autonomous_kernel"
    if not ak_dir.is_dir():
        return "## AK Specs\n\nNo autonomous_kernel/ found.\n"

    specs = sorted(glob.glob(str(ak_dir / "*-spec.md")))
    other_md = sorted(glob.glob(str(ak_dir / "*.md")))
    other_md = [f for f in other_md if f not in specs]
    json_files = sorted(glob.glob(str(ak_dir / "*.json")))
    yaml_files = sorted(glob.glob(str(ak_dir / "*.yaml")))

    # Categorize specs by tranche (look for "Tranche N" in content)
    tranche_counts = collections.Counter()
    for spec in specs:
        try:
            text = Path(spec).read_text(encoding="utf-8")[:500]
            match = re.search(r'Tranche (\d+)', text)
            if match:
                tranche_counts[f"Tranche {match.group(1)}"] += 1
            else:
                tranche_counts["unclassified"] += 1
        except OSError:
            tranche_counts["unreadable"] += 1

    lines = [
        "## Autonomous Kernel Inventory",
        f"\nSpec files: {len(specs)} | Other MD: {len(other_md)} | JSON: {len(json_files)} | YAML: {len(yaml_files)}",
        f"Total: {len(specs) + len(other_md) + len(json_files) + len(yaml_files)}",
        f"\n### Spec Tranche Distribution",
    ]
    for t, c in tranche_counts.most_common():
        lines.append(f"  {t}: {c}")

    lines.append(f"\n### Spec Names")
    for s in specs:
        lines.append(f"  {os.path.basename(s)}")

    return "\n".join(lines) + "\n"


def section_claude_md(zone_root, window_tics, current_tic):
    """CLAUDE.md shape analysis."""
    targets = [
        ("federation", zone_root / "CLAUDE.md"),
        ("cgg_domain", zone_root / "canonical_developer" / "context-grapple-gun" / "CLAUDE.md"),
    ]

    # Also check global
    global_cmd = Path.home() / ".claude" / "CLAUDE.md"
    if global_cmd.exists():
        targets.append(("global", global_cmd))

    lines = ["## CLAUDE.md Shape Analysis\n"]

    all_texts = []
    for label, path in targets:
        if not path.exists():
            lines.append(f"### {label}: NOT FOUND at {path}")
            continue
        text = path.read_text(encoding="utf-8")
        line_count = text.count("\n")
        heading_count = len(re.findall(r'^#{1,3} ', text, re.MULTILINE))
        invariant_mentions = len(re.findall(r'Key Invariant|PRIMITIVE|invariant', text, re.IGNORECASE))
        cogpr_mentions = len(re.findall(r'CogPR-\d+', text))
        entropy = shannon_entropy(text)
        all_texts.append(text)

        lines.append(f"### {label} ({path.name})")
        lines.append(f"  Lines: {line_count} | Headings: {heading_count} | Entropy: {entropy:.2f}")
        lines.append(f"  Invariant mentions: {invariant_mentions} | CogPR references: {cogpr_mentions}")

        # Extract Key Invariant bullet points
        ki_matches = re.findall(r'^- \*\*(.+?)\*\*', text, re.MULTILINE)
        if ki_matches:
            lines.append(f"  Key Invariant bullets: {len(ki_matches)}")
            for ki in ki_matches[:5]:
                lines.append(f"    • {ki[:80]}")
            if len(ki_matches) > 5:
                lines.append(f"    ... and {len(ki_matches) - 5} more")

    if all_texts:
        top_bg = bigram_frequency(all_texts, 10)
        lines.append(f"\n### Cross-CLAUDE.md Concept Bigrams")
        for (a, b), c in top_bg:
            lines.append(f"  {a} {b}: {c}")

    return "\n".join(lines) + "\n"


def section_memory(zone_root, window_tics, current_tic):
    """MEMORY.md shape analysis."""
    memory_dir = Path.home() / ".claude" / "projects" / "-Users-breydentaylor-canonical" / "memory"
    memory_index = memory_dir / "MEMORY.md"

    if not memory_index.exists():
        return "## Memory\n\nNo MEMORY.md found.\n"

    text = memory_index.read_text(encoding="utf-8")
    line_count = text.count("\n")

    # Count memory files by type
    type_counts = collections.Counter()
    memory_files = list(memory_dir.glob("*.md"))
    for mf in memory_files:
        if mf.name == "MEMORY.md":
            continue
        prefix = mf.name.split("_")[0] if "_" in mf.name else "other"
        type_counts[prefix] += 1

    lines = [
        "## Memory Surface Shape",
        f"\nIndex lines: {line_count} | Memory files: {len(memory_files) - 1}",
        f"\n### File Type Distribution",
    ]
    for t, c in type_counts.most_common():
        lines.append(f"  {t}: {c}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _std(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))


def _gini(values):
    """Gini coefficient — 0 = perfect equality, 1 = perfect inequality."""
    if not values or all(v == 0 for v in values):
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    total = sum(sorted_vals)
    if total == 0:
        return 0.0
    cumulative = 0
    gini_sum = 0
    for i, v in enumerate(sorted_vals):
        cumulative += v
        gini_sum += cumulative
    return 1 - (2 * gini_sum) / (n * total) + 1 / n


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SECTION_MAP = {
    "queue": section_queue,
    "signals": section_signals,
    "tics": section_tics,
    "arenas": section_arenas,
    "conformations": section_conformations,
    "routing": section_routing,
    "biome": section_biome,
    "mogul_runs": section_mogul_runs,
    "memory": section_memory,
    "ak_specs": section_ak_specs,
    "claude_md": section_claude_md,
}


def main():
    parser = argparse.ArgumentParser(description="Pattern mining context procurement")
    parser.add_argument("--zone-root", type=str, default=None)
    parser.add_argument("--tic", type=int, default=None)
    parser.add_argument("--window", type=int, default=20, help="Lookback window in tics")
    parser.add_argument("--output", type=str, default=None, help="Output file (default: stdout)")
    parser.add_argument("--sections", type=str, default="all", help="Comma-separated sections or 'all'")
    args = parser.parse_args()

    zone_root = resolve_zone_root(args.zone_root)
    current_tic = args.tic

    # Auto-detect tic if not provided
    if current_tic is None:
        tic_dir = zone_root / "audit-logs" / "tics"
        count = 0
        for f in glob.glob(str(tic_dir / "*.jsonl")):
            for line in open(f, "r", encoding="utf-8"):
                try:
                    obj = json.loads(line.strip())
                    if obj.get("type") == "tic" and obj.get("count_mode") == "counted":
                        count += 1
                except (json.JSONDecodeError, ValueError):
                    pass
        current_tic = count

    # Select sections
    if args.sections == "all":
        sections = list(SECTION_MAP.keys())
    else:
        sections = [s.strip() for s in args.sections.split(",")]

    # Build output
    output_parts = [
        f"# Pattern Mining Context Briefing",
        f"",
        f"Generated: {datetime.now(timezone.utc).isoformat()[:19]}Z",
        f"Zone: {zone_root}",
        f"Current tic: {current_tic}",
        f"Lookback window: {args.window} tics",
        f"Sections: {', '.join(sections)}",
        f"",
        f"---",
        f"",
    ]

    surfaces_scanned = []
    surfaces_not_scanned = []

    for section_name in sections:
        gen = SECTION_MAP.get(section_name)
        if gen:
            try:
                content = gen(zone_root, args.window, current_tic)
                output_parts.append(content)
                surfaces_scanned.append(section_name)
            except Exception as e:
                output_parts.append(f"## {section_name}\n\nERROR: {e}\n")
                surfaces_not_scanned.append(f"{section_name} (error: {e})")
        else:
            surfaces_not_scanned.append(f"{section_name} (unknown section)")

    # Surfaces NOT scanned disclaimer
    all_known = set(SECTION_MAP.keys())
    not_requested = all_known - set(sections)
    if not_requested or surfaces_not_scanned:
        output_parts.append("## Surfaces NOT Scanned\n")
        output_parts.append("These surfaces were not included in this briefing. Pattern")
        output_parts.append("mining agents should be aware of blind spots.\n")
        for s in sorted(not_requested):
            output_parts.append(f"  - {s} (not requested)")
        for s in surfaces_not_scanned:
            output_parts.append(f"  - {s}")

    # Token estimate
    full_text = "\n".join(output_parts)
    token_est = len(full_text) // 4  # rough estimate
    output_parts.append(f"\n---\nEstimated tokens: ~{token_est} | Characters: {len(full_text)}")

    full_output = "\n".join(output_parts)

    if args.output:
        Path(args.output).write_text(full_output, encoding="utf-8")
        print(f"Written to {args.output} ({len(full_output)} chars, ~{token_est} tokens)")
    else:
        print(full_output)


if __name__ == "__main__":
    main()
