#!/usr/bin/env python3
"""Idempotent final v5 package/documentation/scan-boundary migration."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text.rstrip() + "\n", encoding="utf-8")


def insert_after(path: str, anchor: str, payload: str) -> None:
    text = read(path)
    if payload.strip() in text:
        return
    if anchor not in text:
        raise SystemExit(f"missing anchor in {path}: {anchor[:100]!r}")
    write(path, text.replace(anchor, anchor + payload, 1))


def replace_if_present(path: str, old: str, new: str) -> None:
    text = read(path)
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"missing replacement anchor in {path}: {old[:100]!r}")
    write(path, text.replace(old, new, 1))


# npm package graph.
pkg_path = ROOT / "package.json"
pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
for required in ["assets/", "docs/", "DEV-README.md", "ARCHITECTURE.md"]:
    if required not in pkg.setdefault("files", []):
        pkg["files"].append(required)
pkg_path.write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")

# Runtime payload copies the local documentation graph linked from README.
installer = read("lib/installer.mjs")
if "  'DEV-README.md'," not in installer:
    installer = installer.replace(
        "  'INSTALL.md',\n  'LICENSE',\n  'package.json',",
        "  'INSTALL.md',\n  'DEV-README.md',\n  'ARCHITECTURE.md',\n  'docs',\n  'assets',\n  'LICENSE',\n  'package.json',",
        1,
    )

# Path helpers use an alias so the existing audit-loop variable stays untouched.
installer = re.sub(
    r"import \{ basename, dirname(?:, isAbsolute)?, join(?:, relative)?, resolve(?:, sep)? \} from 'node:path';",
    "import { basename, dirname, isAbsolute, join, relative as relativePath, resolve, sep } from 'node:path';",
    installer,
    count=1,
)
if "relative as relativePath" not in installer:
    raise SystemExit("could not normalize installer node:path import")

if ".claude/cgg/\\n" not in installer:
    installer = installer.replace(
        "# Installed skill templates contain examples, not live CogPRs.\\n.claude/skills/\\n",
        "# Installed runtime and skill templates contain examples, not live CogPRs.\\n.claude/cgg/\\n.claude/skills/\\n",
        1,
    )

if "const runtimeTarget = opts.runtimeTarget" not in installer:
    installer = installer.replace(
        "  const dryRun = Boolean(opts.dryRun);\n  const tz =",
        "  const dryRun = Boolean(opts.dryRun);\n  const runtimeTarget = opts.runtimeTarget ? resolve(expandHome(opts.runtimeTarget)) : null;\n  const tz =",
        1,
    )

exclusion_block = """

  if (runtimeTarget) {
    const rel = relativePath(zone, runtimeTarget);
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
"""
if "append managed runtime exclusion" not in installer:
    marker = "  for (const relative of AUDIT_DIRECTORIES) {"
    if marker not in installer:
        raise SystemExit("could not locate audit-directory loop")
    installer = installer.replace(marker, exclusion_block + "\n" + marker, 1)

installer = installer.replace(
    "ensureZoneSurfaces(zoneRoot, { dryRun: true })",
    "ensureZoneSurfaces(zoneRoot, { dryRun: true, runtimeTarget: target })",
)
installer = installer.replace(
    "ensureZoneSurfaces(zoneRoot))",
    "ensureZoneSurfaces(zoneRoot, { runtimeTarget: target }))",
)
write("lib/installer.mjs", installer)

# Static distribution contract.
validator = read("scripts/validate-distribution.mjs")
if "  'assets/'," not in validator:
    validator = validator.replace(
        "for (const required of ['bin/', 'lib/', '.claude-plugin/', 'hooks/', 'cgg-runtime/', 'SESSION_LEARNING_PROTOCOL.md']) {",
        "for (const required of [\n  'bin/',\n  'lib/',\n  '.claude-plugin/',\n  'hooks/',\n  'cgg-runtime/',\n  'SESSION_LEARNING_PROTOCOL.md',\n  'assets/',\n  'docs/',\n  'DEV-README.md',\n  'ARCHITECTURE.md',\n]) {",
        1,
    )
if "CGG v5 currentness correction" not in validator:
    validator = validator.replace(
        "for (const doc of ['README.md', 'START-HERE.md', 'INSTALL.md']) validateMarkdownLinks(doc);",
        "for (const doc of ['README.md', 'START-HERE.md', 'INSTALL.md', 'DEV-README.md', 'ARCHITECTURE.md']) validateMarkdownLinks(doc);\n\nfor (const [path, marker] of [\n  ['ARCHITECTURE.md', 'CGG v5 currentness correction'],\n  ['DEV-README.md', 'CGG v5 source-set correction'],\n]) {\n  const text = readFileSync(join(root, path), 'utf-8');\n  if (!text.includes(marker)) fail(`${path} is missing its v5 currentness boundary`);\n}",
        1,
    )
write("scripts/validate-distribution.mjs", validator)

# Contract tests.
tests = read("tests/npm/distribution.test.mjs")
if "const runtimeTarget = join(zone, '.claude', 'cgg');" not in tests:
    tests = tests.replace(
        "  const first = ensureZoneSurfaces(zone);\n  const second = ensureZoneSurfaces(zone);",
        "  const runtimeTarget = join(zone, '.claude', 'cgg');\n  const first = ensureZoneSurfaces(zone, { runtimeTarget });\n  const second = ensureZoneSurfaces(zone, { runtimeTarget });",
        1,
    )
if "assert.match(readFileSync(join(zone, '.ticignore')" not in tests:
    tests = tests.replace(
        "  assert.equal(config.bands.includes('PRESTIGE'), false);",
        "  assert.equal(config.bands.includes('PRESTIGE'), false);\n  assert.match(readFileSync(join(zone, '.ticignore'), 'utf-8'), /^\\.claude\\/cgg\\/$/m);",
        1,
    )
if "    'docs'," not in tests:
    tests = tests.replace(
        "    'cgg-runtime/agents',\n  ])",
        "    'cgg-runtime/agents',\n    'docs',\n    'assets',\n  ])",
        1,
    )
if "'DEV-README.md', 'ARCHITECTURE.md'" not in tests:
    tests = tests.replace(
        "for (const file of ['README.md', 'START-HERE.md', 'INSTALL.md', 'LICENSE']) writeFileSync(join(source, file), `${file}\\n`);",
        "for (const file of ['README.md', 'START-HERE.md', 'INSTALL.md', 'DEV-README.md', 'ARCHITECTURE.md', 'LICENSE']) {\n    writeFileSync(join(source, file), `${file}\\n`);\n  }\n  writeFileSync(join(source, 'docs', 'TERMINOLOGY.md'), '# Terms\\n');\n  writeFileSync(join(source, 'assets', 'cgg-banner.jpeg'), 'banner\\n');",
        1,
    )
if tests.count("/^\\.claude\\/cgg\\/$/m") < 2:
    tests = tests.replace(
        "    assert.deepEqual(JSON.parse(readFileSync(join(zone, '.ticzone'), 'utf-8')).bands, ['PRIMITIVE', 'COGNITIVE', 'SOCIAL']);",
        "    assert.deepEqual(JSON.parse(readFileSync(join(zone, '.ticzone'), 'utf-8')).bands, ['PRIMITIVE', 'COGNITIVE', 'SOCIAL']);\n    assert.match(readFileSync(join(zone, '.ticignore'), 'utf-8'), /^\\.claude\\/cgg\\/$/m);",
        1,
    )
write("tests/npm/distribution.test.mjs", tests)

# Explicit currentness boundaries on long-form docs.
for path, title, body in [
    (
        "ARCHITECTURE.md",
        "CGG v5 currentness correction",
        "`/review` is an in-tic human constitutional judgment surface. It does not use Plan Mode as its approval authority; routing plan acceptance through a plan gate would invert the review boundary. Plan Mode language below is historical or forward-looking unless a newer receipt explicitly re-admits it. The v5 installer, plugin manifest, and loaded runtime contracts govern current behavior.",
    ),
    (
        "DEV-README.md",
        "CGG v5 source-set correction",
        "Auto-memory is not a governance source by default. The v5 SessionStart runtime separates model memory from zone-governed source because scanning unreachable memory candidates creates phantom CogPR counts. Governance scans the declared project zone and explicitly admitted surfaces; memory may inform work without silently becoming constitutional input.",
    ),
]:
    text = read(path)
    if title not in text:
        lines = text.splitlines()
        index = 1 if lines and lines[0].startswith('#') else 0
        lines[index:index] = ["", f"> **{title}.** {body}", ""]
        write(path, "\n".join(lines))

# Public documentation and real CI.
install_doc = read("INSTALL.md")
old_sentence = "Existing zone configuration, history, `MEMORY.md`, and user-authored `CLAUDE.md` content are never replaced."
new_sentence = old_sentence + " When the managed runtime is inside the zone, its exact relative path is added to `.ticignore` so packaged skills, examples, and held source cannot emit project CogPRs or signals."
if new_sentence not in install_doc:
    if old_sentence not in install_doc:
        raise SystemExit("INSTALL currentness anchor missing")
    install_doc = install_doc.replace(old_sentence, new_sentence, 1)
write("INSTALL.md", install_doc)

readme = read("README.md")
if "ships every local document and asset linked from the npm README" not in readme:
    readme = readme.replace(
        "- keeps PRESTIGE out of every new zone template;",
        "- keeps PRESTIGE out of every new zone template;\n- ships every local document and asset linked from the npm README;\n- excludes an in-zone managed runtime from governance scanning;",
        1,
    )
write("README.md", readme)

workflow = read(".github/workflows/distribution-contract.yml")
if "grep -q '^\\.claude/cgg/$'" not in workflow:
    workflow = workflow.replace(
        '          test -f "$PROJECT/.ticignore"\n          test -d "$PROJECT/audit-logs"',
        '          test -f "$PROJECT/.ticignore"\n          grep -q \'^\\.claude/cgg/$\' "$PROJECT/.ticignore"\n          test -d "$PROJECT/audit-logs"',
        1,
    )
write(".github/workflows/distribution-contract.yml", workflow)

# Remove all temporary migration/finalizer surfaces after confirming sync landed.
if "inspectSyncState" not in read("lib/sync.mjs") or "runtime_tree_sha256" not in read("lib/installer.mjs"):
    raise SystemExit("v5 receipt/tree sync migration is not present; refusing to delete its recovery surfaces")
for relative_path in [
    "scripts/apply-v5-sync-repair.py",
    ".github/workflows/apply-v5-sync-repair.yml",
    ".github/workflows/v5-admission-finalize.yml",
    "scripts/apply-v5-package-boundary-repair.py",
    ".github/workflows/apply-v5-package-boundary-repair.yml",
    ".github/workflows/recover-v5-package-boundary-repair.yml",
    "scripts/force-v5-package-boundary-repair.py",
    ".github/workflows/force-v5-package-boundary-repair.yml",
]:
    path = ROOT / relative_path
    if path.exists():
        path.unlink()
