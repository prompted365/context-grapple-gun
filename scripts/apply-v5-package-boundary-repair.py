#!/usr/bin/env python3
"""One-time v5 package-boundary and zone-exclusion migration.

The paired workflow validates, commits, and deletes this file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if old not in text:
        raise SystemExit(f"expected migration anchor missing in {path}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


# npm payload must contain every local document and asset linked from README.
pkg_path = ROOT / "package.json"
pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
files = list(pkg.get("files", []))
for required in ["assets/", "docs/", "DEV-README.md", "ARCHITECTURE.md"]:
    if required not in files:
        files.append(required)
pkg["files"] = files
pkg_path.write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")

# The managed runtime copy carries the same local documentation graph.
replace_once(
    "lib/installer.mjs",
    """  'INSTALL.md',
  'LICENSE',
  'package.json',
];""",
    """  'INSTALL.md',
  'DEV-README.md',
  'ARCHITECTURE.md',
  'docs',
  'assets',
  'LICENSE',
  'package.json',
];""",
)

replace_once(
    "lib/installer.mjs",
    "import { basename, dirname, join, resolve } from 'node:path';",
    "import { basename, dirname, isAbsolute, join, relative, resolve, sep } from 'node:path';",
)

replace_once(
    "lib/installer.mjs",
    """# Installed skill templates contain examples, not live CogPRs.\\n.claude/skills/\\n\\n# Stage artifacts are reference and learning material, not tic/signal emitters.\\nstage/\\n`;""",
    """# Installed runtime and skill templates contain examples, not live CogPRs.\\n.claude/cgg/\\n.claude/skills/\\n\\n# Stage artifacts are reference and learning material, not tic/signal emitters.\\nstage/\\n`;""",
)

# Existing zones also receive the exact in-zone managed target as an additive exclusion.
replace_once(
    "lib/installer.mjs",
    """export function ensureZoneSurfaces(zoneRoot, opts = {}) {
  const zone = resolve(zoneRoot);
  const actions = [];
  const dryRun = Boolean(opts.dryRun);
  const tz = process.env.TZ || Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
""",
    """export function ensureZoneSurfaces(zoneRoot, opts = {}) {
  const zone = resolve(zoneRoot);
  const actions = [];
  const dryRun = Boolean(opts.dryRun);
  const runtimeTarget = opts.runtimeTarget ? resolve(expandHome(opts.runtimeTarget)) : null;
  const tz = process.env.TZ || Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
""",
)

replace_once(
    "lib/installer.mjs",
    """  if (!existsSync(ticignorePath)) {
    actions.push(`create ${ticignorePath}`);
    if (!dryRun) writeFileSync(ticignorePath, TICIGNORE_TEMPLATE, 'utf-8');
  }

  for (const relative of AUDIT_DIRECTORIES) {
""",
    """  if (!existsSync(ticignorePath)) {
    actions.push(`create ${ticignorePath}`);
    if (!dryRun) writeFileSync(ticignorePath, TICIGNORE_TEMPLATE, 'utf-8');
  }

  if (runtimeTarget) {
    const rel = relative(zone, runtimeTarget);
    const insideZone = rel && rel !== '..' && !rel.startsWith(`..${sep}`) && !isAbsolute(rel);
    if (insideZone) {
      const exclusion = `${rel.split(sep).join('/').replace(/\\/$/, '')}/`;
      const existing = existsSync(ticignorePath)
        ? readFileSync(ticignorePath, 'utf-8')
        : TICIGNORE_TEMPLATE;
      const lines = new Set(existing.split(/\\r?\\n/).map((line) => line.trim()));
      if (!lines.has(exclusion)) {
        actions.push(`append managed runtime exclusion ${exclusion} to ${ticignorePath}`);
        if (!dryRun) {
          const prefix = existing.endsWith('\\n') ? existing : `${existing}\\n`;
          writeFileSync(
            ticignorePath,
            `${prefix}\\n# CGG managed runtime (generated)\\n${exclusion}\\n`,
            'utf-8',
          );
        }
      }
    }
  }

  for (const auditRelative of AUDIT_DIRECTORIES) {
""",
)
replace_once(
    "lib/installer.mjs",
    """  for (const relative of AUDIT_DIRECTORIES) {
    const path = join(zone, relative);
""",
    """  for (const auditRelative of AUDIT_DIRECTORIES) {
    const path = join(zone, auditRelative);
""",
)

replace_once(
    "lib/installer.mjs",
    "for (const action of ensureZoneSurfaces(zoneRoot, { dryRun: true }))",
    "for (const action of ensureZoneSurfaces(zoneRoot, { dryRun: true, runtimeTarget: target }))",
)
replace_once(
    "lib/installer.mjs",
    "for (const action of ensureZoneSurfaces(zoneRoot))",
    "for (const action of ensureZoneSurfaces(zoneRoot, { runtimeTarget: target }))",
)

# Static admission verifies npm/local-link parity rather than only repository existence.
replace_once(
    "scripts/validate-distribution.mjs",
    """for (const required of ['bin/', 'lib/', '.claude-plugin/', 'hooks/', 'cgg-runtime/', 'SESSION_LEARNING_PROTOCOL.md']) {
""",
    """for (const required of [
  'bin/',
  'lib/',
  '.claude-plugin/',
  'hooks/',
  'cgg-runtime/',
  'SESSION_LEARNING_PROTOCOL.md',
  'assets/',
  'docs/',
  'DEV-README.md',
  'ARCHITECTURE.md',
]) {
""",
)
replace_once(
    "scripts/validate-distribution.mjs",
    """for (const doc of ['README.md', 'START-HERE.md', 'INSTALL.md']) validateMarkdownLinks(doc);
""",
    """for (const doc of ['README.md', 'START-HERE.md', 'INSTALL.md', 'DEV-README.md', 'ARCHITECTURE.md']) validateMarkdownLinks(doc);

for (const [path, marker] of [
  ['ARCHITECTURE.md', 'CGG v5 currentness correction'],
  ['DEV-README.md', 'CGG v5 source-set correction'],
]) {
  const text = readFileSync(join(root, path), 'utf-8');
  if (!text.includes(marker)) fail(`${path} is missing its v5 currentness boundary`);
}
""",
)

# Tests exercise additive .ticignore repair and the expanded payload.
replace_once(
    "tests/npm/distribution.test.mjs",
    """  const first = ensureZoneSurfaces(zone);
  const second = ensureZoneSurfaces(zone);
""",
    """  const runtimeTarget = join(zone, '.claude', 'cgg');
  const first = ensureZoneSurfaces(zone, { runtimeTarget });
  const second = ensureZoneSurfaces(zone, { runtimeTarget });
""",
)
replace_once(
    "tests/npm/distribution.test.mjs",
    """  assert.equal(config.bands.includes('PRESTIGE'), false);
});
""",
    """  assert.equal(config.bands.includes('PRESTIGE'), false);
  assert.match(readFileSync(join(zone, '.ticignore'), 'utf-8'), /^\\.claude\\/cgg\\/$/m);
});
""",
)
replace_once(
    "tests/npm/distribution.test.mjs",
    """  for (const path of [
    '.claude-plugin',
    'hooks',
    'cgg-runtime/hooks',
    'cgg-runtime/scripts',
    'cgg-runtime/agents',
  ]) mkdirSync(join(source, path), { recursive: true });
""",
    """  for (const path of [
    '.claude-plugin',
    'hooks',
    'cgg-runtime/hooks',
    'cgg-runtime/scripts',
    'cgg-runtime/agents',
    'docs',
    'assets',
  ]) mkdirSync(join(source, path), { recursive: true });
""",
)
replace_once(
    "tests/npm/distribution.test.mjs",
    """  for (const file of ['README.md', 'START-HERE.md', 'INSTALL.md', 'LICENSE']) writeFileSync(join(source, file), `${file}\\n`);
""",
    """  for (const file of ['README.md', 'START-HERE.md', 'INSTALL.md', 'DEV-README.md', 'ARCHITECTURE.md', 'LICENSE']) {
    writeFileSync(join(source, file), `${file}\\n`);
  }
  writeFileSync(join(source, 'docs', 'TERMINOLOGY.md'), '# Terms\\n');
  writeFileSync(join(source, 'assets', 'cgg-banner.jpeg'), 'banner\\n');
""",
)
replace_once(
    "tests/npm/distribution.test.mjs",
    """    assert.deepEqual(JSON.parse(readFileSync(join(zone, '.ticzone'), 'utf-8')).bands, ['PRIMITIVE', 'COGNITIVE', 'SOCIAL']);
""",
    """    assert.deepEqual(JSON.parse(readFileSync(join(zone, '.ticzone'), 'utf-8')).bands, ['PRIMITIVE', 'COGNITIVE', 'SOCIAL']);
    assert.match(readFileSync(join(zone, '.ticignore'), 'utf-8'), /^\\.claude\\/cgg\\/$/m);
""",
)

# Currentness fences on older long-form docs. Preserve history; prevent it from claiming current authority.
for path, title, body in [
    (
        "ARCHITECTURE.md",
        "CGG v5 currentness correction",
        "`/review` is an in-tic human constitutional judgment surface. It does not use Plan Mode as its approval authority; routing plan acceptance through a plan gate would invert the review boundary. Any Plan Mode language below is historical or forward-looking unless a newer receipt explicitly re-admits it. The v5 installer, plugin manifest, and loaded runtime contracts govern current behavior.",
    ),
    (
        "DEV-README.md",
        "CGG v5 source-set correction",
        "Auto-memory is not a governance source by default. The v5 SessionStart runtime deliberately separates model memory from zone-governed source because scanning unreachable memory candidates creates phantom CogPR counts. Governance scans the declared project zone and explicitly admitted surfaces; memory may inform work without silently becoming constitutional input.",
    ),
]:
    text = read(path)
    if title not in text:
        lines = text.splitlines()
        insert_at = 1 if lines and lines[0].startswith("#") else 0
        correction = ["", f"> **{title}.** {body}", ""]
        lines[insert_at:insert_at] = correction
        write(path, "\n".join(lines).rstrip() + "\n")

# Public docs state the scan boundary and packaged documentation graph.
replace_once(
    "INSTALL.md",
    """Existing zone configuration, history, `MEMORY.md`, and user-authored `CLAUDE.md` content are never replaced.
""",
    """Existing zone configuration, history, `MEMORY.md`, and user-authored `CLAUDE.md` content are never replaced. When the managed runtime is inside the zone, its exact relative path is added to `.ticignore` so packaged skills, examples, and held source cannot emit project CogPRs or signals.
""",
)
replace_once(
    "README.md",
    "- keeps PRESTIGE out of every new zone template.\n",
    "- keeps PRESTIGE out of every new zone template;\n- ships every local document and asset linked from the npm README;\n- excludes an in-zone managed runtime from governance scanning.\n",
)

# Real CI checks the installed runtime exclusion.
replace_once(
    ".github/workflows/distribution-contract.yml",
    """          test -f \"$PROJECT/.ticignore\"
          test -d \"$PROJECT/audit-logs\"
""",
    """          test -f \"$PROJECT/.ticignore\"
          grep -q '^\\.claude/cgg/$' \"$PROJECT/.ticignore\"
          test -d \"$PROJECT/audit-logs\"
""",
)

# Self-delete both migration surfaces in the resulting commit.
(ROOT / "scripts/apply-v5-package-boundary-repair.py").unlink()
(ROOT / ".github/workflows/apply-v5-package-boundary-repair.yml").unlink()
