"""
Chapter 5: Gamified Completion Layer

Track chapter progress, generate proof-of-work artifacts (SVG certificate + badge),
record completion events, and produce share metadata.

This is the same pattern CGG uses: audit trails ARE proof. The system doesn't just
record that you finished — it generates durable, inspectable artifacts that encode
what you did, when, and what passed.
"""
import json
import os
import subprocess
from datetime import datetime, timezone


# Chapter directory names mapped to human-readable labels
CHAPTERS = {
    "01-append-only-truth": "Append-Only Truth",
    "02-dedup-and-identity": "Dedup & Identity",
    "03-signals-and-decay": "Signals & Decay",
    "04-human-gated-review": "Human-Gated Review",
}


def check_chapter_status(project_root: str) -> dict[str, bool]:
    """Check which chapters have passing tests. Returns {chapter_name: passed}.

    Runs pytest for each chapter's test file via subprocess.
    A chapter passes if pytest exits 0 (all tests pass).
    """
    results = {}
    chapters_dir = os.path.join(project_root, "chapters")

    for chapter_dir, label in CHAPTERS.items():
        chapter_path = os.path.join(chapters_dir, chapter_dir)
        if not os.path.isdir(chapter_path):
            results[label] = False
            continue

        # Find test files in the chapter directory
        test_files = [
            f for f in os.listdir(chapter_path)
            if f.startswith("test_") and f.endswith(".py")
        ]
        if not test_files:
            results[label] = False
            continue

        # Run pytest on the chapter's test file(s)
        test_path = os.path.join(chapter_path, test_files[0])
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", test_path, "-x", "--tb=no", "-q"],
                capture_output=True,
                text=True,
                cwd=project_root,
                timeout=30,
            )
            results[label] = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            results[label] = False

    return results


def generate_certificate_svg(
    student_name: str, completed_at: str, chapters: dict[str, bool]
) -> str:
    """Generate an SVG certificate string showing completion.

    Dark theme with hex grid background and circuit-board aesthetic.
    Includes student name, date, chapter checkmarks, and Grappler designation.
    """
    width = 800
    height = 520

    # Build chapter checkmark rows
    chapter_rows = []
    y_start = 280
    for i, (name, passed) in enumerate(chapters.items()):
        y = y_start + i * 36
        icon = _check_icon(passed)
        color = "#4ade80" if passed else "#6b7280"
        chapter_rows.append(
            f'    <g transform="translate(200, {y})">'
            f'      {icon}'
            f'      <text x="30" y="5" fill="{color}" font-family="monospace" '
            f'font-size="15" dominant-baseline="middle">{_escape_xml(name)}</text>'
            f"    </g>"
        )
    chapter_block = "\n".join(chapter_rows)

    all_passed = all(chapters.values())
    grappler_color = "#f59e0b" if all_passed else "#4b5563"
    designation_text = "GRAPPLER" if all_passed else "IN PROGRESS"

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <pattern id="hexgrid" width="56" height="49" patternUnits="userSpaceOnUse" patternTransform="scale(0.5)">
      <path d="M28,0 L56,14 L56,35 L28,49 L0,35 L0,14 Z" fill="none" stroke="#1e293b" stroke-width="1"/>
    </pattern>
    <linearGradient id="border_grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#3b82f6"/>
      <stop offset="100%" stop-color="#8b5cf6"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="{width}" height="{height}" rx="12" fill="#0f172a"/>
  <rect width="{width}" height="{height}" rx="12" fill="url(#hexgrid)" opacity="0.6"/>

  <!-- Border -->
  <rect x="4" y="4" width="{width - 8}" height="{height - 8}" rx="10" fill="none" stroke="url(#border_grad)" stroke-width="2"/>

  <!-- Circuit traces -->
  <line x1="40" y1="100" x2="40" y2="420" stroke="#1e3a5f" stroke-width="1" opacity="0.5"/>
  <line x1="760" y1="100" x2="760" y2="420" stroke="#1e3a5f" stroke-width="1" opacity="0.5"/>
  <circle cx="40" cy="100" r="3" fill="#3b82f6" opacity="0.4"/>
  <circle cx="40" cy="420" r="3" fill="#3b82f6" opacity="0.4"/>
  <circle cx="760" cy="100" r="3" fill="#8b5cf6" opacity="0.4"/>
  <circle cx="760" cy="420" r="3" fill="#8b5cf6" opacity="0.4"/>

  <!-- Title -->
  <text x="{width // 2}" y="60" fill="#e2e8f0" font-family="monospace" font-size="24" font-weight="bold" text-anchor="middle">CGG Field Guide</text>
  <text x="{width // 2}" y="90" fill="#94a3b8" font-family="monospace" font-size="14" text-anchor="middle">Course Complete</text>

  <!-- Divider -->
  <line x1="150" y1="110" x2="650" y2="110" stroke="#334155" stroke-width="1"/>

  <!-- Student info -->
  <text x="{width // 2}" y="150" fill="#f8fafc" font-family="monospace" font-size="20" text-anchor="middle">{_escape_xml(student_name)}</text>
  <text x="{width // 2}" y="180" fill="#64748b" font-family="monospace" font-size="12" text-anchor="middle">{_escape_xml(completed_at)}</text>

  <!-- Designation -->
  <rect x="300" y="200" width="200" height="36" rx="6" fill="none" stroke="{grappler_color}" stroke-width="2"/>
  <text x="{width // 2}" y="224" fill="{grappler_color}" font-family="monospace" font-size="16" font-weight="bold" text-anchor="middle">{designation_text}</text>

  <!-- Divider -->
  <line x1="150" y1="254" x2="650" y2="254" stroke="#334155" stroke-width="1"/>

  <!-- Chapter checklist -->
{chapter_block}

  <!-- Footer -->
  <text x="{width // 2}" y="{height - 30}" fill="#475569" font-family="monospace" font-size="10" text-anchor="middle">Context Grapple Gun — Proof of Work</text>
</svg>"""

    return svg


def generate_badge_svg(student_name: str) -> str:
    """Generate a small 'Grappler' badge SVG.

    Compact badge suitable for display alongside a profile or README.
    """
    width = 200
    height = 200

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <linearGradient id="badge_grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#3b82f6"/>
      <stop offset="100%" stop-color="#8b5cf6"/>
    </linearGradient>
    <pattern id="badge_hex" width="28" height="24" patternUnits="userSpaceOnUse" patternTransform="scale(0.4)">
      <path d="M14,0 L28,7 L28,17 L14,24 L0,17 L0,7 Z" fill="none" stroke="#1e293b" stroke-width="0.5"/>
    </pattern>
  </defs>

  <!-- Background circle -->
  <circle cx="100" cy="100" r="96" fill="#0f172a"/>
  <circle cx="100" cy="100" r="96" fill="url(#badge_hex)" opacity="0.5"/>
  <circle cx="100" cy="100" r="94" fill="none" stroke="url(#badge_grad)" stroke-width="3"/>

  <!-- Inner ring -->
  <circle cx="100" cy="100" r="76" fill="none" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4 4"/>

  <!-- Grapple hook icon -->
  <g transform="translate(100, 72)">
    <path d="M0,-24 L0,0 M-12,0 C-12,12 12,12 12,0 M-12,0 L-12,-6 M12,0 L12,-6" fill="none" stroke="#f59e0b" stroke-width="3" stroke-linecap="round"/>
  </g>

  <!-- Text -->
  <text x="100" y="115" fill="#f59e0b" font-family="monospace" font-size="14" font-weight="bold" text-anchor="middle">GRAPPLER</text>
  <text x="100" y="140" fill="#94a3b8" font-family="monospace" font-size="9" text-anchor="middle">{_escape_xml(student_name)}</text>

  <!-- Bottom accent -->
  <text x="100" y="170" fill="#475569" font-family="monospace" font-size="8" text-anchor="middle">CGG Field Guide</text>
</svg>"""

    return svg


def record_completion(
    filepath: str, student_name: str, chapters: dict[str, bool]
) -> dict:
    """Record completion event to JSONL. Returns the completion record.

    Uses Chapter 1's append-only pattern: append a JSON line with an id field,
    timestamp, student name, and chapter results.
    """
    completed_count = sum(1 for v in chapters.values() if v)
    total_count = len(chapters)
    now = datetime.now(timezone.utc).isoformat()

    record = {
        "id": f"completion_{student_name}_{now}",
        "type": "completion",
        "student_name": student_name,
        "completed_at": now,
        "chapters": chapters,
        "completed_count": completed_count,
        "total_count": total_count,
        "all_passed": completed_count == total_count,
    }

    # Ensure directory exists
    directory = os.path.dirname(filepath)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(filepath, "a") as f:
        f.write(json.dumps(record) + "\n")

    return record


def get_share_metadata(
    student_name: str, completed_chapters: int, total_chapters: int
) -> dict:
    """Generate OG-compatible share metadata.

    Returns a dict with title, description, and image_alt suitable for
    social sharing / Open Graph tags.
    """
    if completed_chapters == total_chapters:
        title = f"{student_name} completed the CGG Field Guide"
        description = (
            f"{student_name} completed all {total_chapters} chapters of the "
            f"Context Grapple Gun Field Guide and earned the Grappler designation."
        )
        image_alt = (
            f"CGG Field Guide completion certificate for {student_name} "
            f"showing all {total_chapters} chapters passed"
        )
    else:
        title = f"{student_name} is working through the CGG Field Guide"
        description = (
            f"{student_name} has completed {completed_chapters} of "
            f"{total_chapters} chapters in the Context Grapple Gun Field Guide."
        )
        image_alt = (
            f"CGG Field Guide progress for {student_name}: "
            f"{completed_chapters}/{total_chapters} chapters complete"
        )

    return {
        "title": title,
        "description": description,
        "image_alt": image_alt,
    }


# --- Internal helpers ---


def _escape_xml(text: str) -> str:
    """Escape text for safe inclusion in XML/SVG."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _check_icon(passed: bool) -> str:
    """Return an SVG checkmark or X icon."""
    if passed:
        return (
            '<circle cx="10" cy="0" r="10" fill="#065f46"/>'
            '<path d="M5,-2 L9,3 L16,-5" fill="none" stroke="#4ade80" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    else:
        return (
            '<circle cx="10" cy="0" r="10" fill="#451a1a"/>'
            '<path d="M5,-5 L15,5 M15,-5 L5,5" fill="none" stroke="#ef4444" '
            'stroke-width="2" stroke-linecap="round"/>'
        )
