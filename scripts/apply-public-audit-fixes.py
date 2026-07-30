#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one exact match, found {count}")
    write(path, text.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str, *, flags: int = 0) -> None:
    text = read(path)
    updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex match, found {count}: {pattern}")
    write(path, updated)


# ---------------------------------------------------------------------------
# Distribution contract: mode-specific payload and exact expected inventory.
# ---------------------------------------------------------------------------
replace_once(
    "lib/distribution-contract.mjs",
    """export const INSTALL_PAYLOAD = Object.freeze([
  '.claude-plugin',
  'assets',
  'bin',
  'cgg-runtime',
  'docs',
  'hooks',
  'lib',
  'ARCHITECTURE.md',
  'CHANGELOG.md',
  'CGG_RUNTIME_TOPOLOGY_AND_LIFECYCLE.md',
  'DEV-README.md',
  'INSTALL.md',
  'LICENSE',
  'README.md',
  'START-HERE.md',
  'package.json',
]);

export function validateInstallOptions""",
    """export const INSTALL_PAYLOAD = Object.freeze([
  '.claude-plugin',
  'assets',
  'bin',
  'cgg-runtime',
  'docs',
  'hooks',
  'lib',
  'ARCHITECTURE.md',
  'CHANGELOG.md',
  'CGG_RUNTIME_TOPOLOGY_AND_LIFECYCLE.md',
  'DEV-README.md',
  'INSTALL.md',
  'LICENSE',
  'README.md',
  'START-HERE.md',
  'package.json',
]);

export function installPayloadForMode(mode) {
  if (mode === 'convention') return [];
  return INSTALL_PAYLOAD.filter((relative) => mode === 'full' || relative !== 'hooks');
}

export function validateInstallOptions""",
)

replace_once(
    "lib/distribution-contract.mjs",
    """export function agentPathsForMode(contract, mode) {
  return mode === 'full' ? [...(contract.agents.full || [])] : [];
}

export function assertComponentSources""",
    """export function agentPathsForMode(contract, mode) {
  return mode === 'full' ? [...(contract.agents.full || [])] : [];
}

export function hookEventsForMode(packageRoot, contract, mode) {
  if (mode !== 'full') return [];
  const hookPath = join(packageRoot, contract.hooks.full.replace(/^\.\//, ''));
  const hookContract = readJson(hookPath);
  return Object.entries(hookContract.hooks || {})
    .filter(([, entries]) => Array.isArray(entries) && entries.length > 0)
    .map(([event]) => event)
    .sort();
}

export function assertComponentSources""",
)

# ---------------------------------------------------------------------------
# Installer: true skills mode, exact inventory, receipt exactness.
# ---------------------------------------------------------------------------
replace_once(
    "lib/installer.mjs",
    """  agentPathsForMode,
  buildMarketplaceManifest,
  buildPluginManifest,
  loadComponentContract,
  validateInstallOptions,""",
    """  agentPathsForMode,
  buildMarketplaceManifest,
  buildPluginManifest,
  hookEventsForMode,
  installPayloadForMode,
  loadComponentContract,
  skillNamesForMode,
  validateInstallOptions,""",
)

replace_once(
    "lib/installer.mjs",
    """function copyPayload(packageRoot, target, dryRun) {
  const copied = [];
  for (const relative of INSTALL_PAYLOAD) {
    const source = join(packageRoot, relative);
    if (!existsSync(source)) continue;
    copied.push(relative);
    if (dryRun) continue;
    const destination = join(target, relative);
    mkdirSync(dirname(destination), { recursive: true });
    cpSync(source, destination, { recursive: true, force: true, preserveTimestamps: true });
  }
  return copied;
}""",
    """function copyPayload(packageRoot, target, dryRun, mode) {
  const copied = [];
  for (const relative of installPayloadForMode(mode)) {
    const source = join(packageRoot, relative);
    if (!existsSync(source)) continue;
    copied.push(relative);
    if (dryRun) continue;
    const destination = join(target, relative);
    mkdirSync(dirname(destination), { recursive: true });
    cpSync(source, destination, { recursive: true, force: true, preserveTimestamps: true });
  }
  return copied;
}""",
)

regex_once(
    "lib/installer.mjs",
    r"""function inventoryHas\(details, label, candidates\) \{
.*?
\}

function verifyPlugin\(\{ target, mode, manifest \}\) \{
.*?
\}
""",
    """function requireInventoryCount(details, label, expectedCount) {
  const actualCount = inventoryCount(details, label);
  if (actualCount === null) {
    throw new Error(`Claude Code plugin details did not report a ${label} count.`);
  }
  if (actualCount !== expectedCount) {
    throw new Error(
      `Claude Code plugin details reported ${label}(${actualCount}); expected ${label}(${expectedCount}).`,
    );
  }
  return actualCount;
}

function verifyPlugin({ target, mode, manifest }) {
  run('claude', ['plugin', 'validate', target, '--strict'], { passthrough: true });
  const list = run('claude', ['plugin', 'list', '--json']) || '';
  const listJson = parseJsonOrNull(list);
  const record = listJson ? findNamedRecord(listJson, PLUGIN_NAME) : null;
  const installed = record ? true : list.includes(PLUGIN_NAME);
  if (!installed) {
    throw new Error('Claude Code did not report context-grapple-gun as installed after installation.');
  }

  const loadErrors = Array.isArray(record?.errors) ? record.errors : [];
  if (loadErrors.length) {
    throw new Error(`Claude Code lists context-grapple-gun but it failed to load: ${loadErrors.join(' | ')}`);
  }

  const details = run('claude', ['plugin', 'details', QUALIFIED_PLUGIN]) || '';
  if (!details.trim()) {
    throw new Error('Claude Code returned an empty plugin-details inventory.');
  }

  const contract = loadComponentContract(target);
  const expected = {
    skills: skillNamesForMode(contract, mode),
    agents: agentPathsForMode(contract, mode).map((path) => basename(path)).sort(),
    hooks: hookEventsForMode(target, contract, mode),
  };
  const loaded = {
    skills: requireInventoryCount(details, 'Skills', expected.skills.length),
    agents: requireInventoryCount(details, 'Agents', expected.agents.length),
    hooks: requireInventoryCount(details, 'Hooks', expected.hooks.length),
  };

  return {
    details,
    expected: {
      skills: { count: expected.skills.length, ids: expected.skills },
      agents: { count: expected.agents.length, ids: expected.agents },
      hooks: { count: expected.hooks.length, ids: expected.hooks },
    },
    loaded,
  };
}
""",
    flags=re.S,
)

replace_once(
    "lib/installer.mjs",
    """      details_sha256: sha256(verification.details),
      expected_inventory: verification.expected,""",
    """      details_sha256: sha256(verification.details),
      expected_inventory: verification.expected,
      loaded_inventory: verification.loaded,""",
)

replace_once(
    "lib/installer.mjs",
    """  const managedPaths = copyPayload(packageRoot, target, false);""",
    """  const managedPaths = copyPayload(packageRoot, target, false, mode);""",
)

# ---------------------------------------------------------------------------
# Doctor: exact source and loaded inventory; true skills-mode hook absence.
# ---------------------------------------------------------------------------
replace_once(
    "lib/doctor.mjs",
    """import { join, resolve } from 'node:path';
import {
  INSTALL_RECEIPT,
  PLUGIN_NAME,
  QUALIFIED_PLUGIN,
} from './distribution-contract.mjs';""",
    """import { basename, join, resolve } from 'node:path';
import {
  INSTALL_RECEIPT,
  PLUGIN_NAME,
  QUALIFIED_PLUGIN,
  agentPathsForMode,
  hookEventsForMode,
  loadComponentContract,
  skillNamesForMode,
} from './distribution-contract.mjs';""",
)

replace_once(
    "lib/doctor.mjs",
    """function inventoryHas(details, label, candidates) {
  const count = inventoryCount(details, label);
  if (count !== null) return count > 0;
  const normalized = details.toLowerCase();
  return candidates.some((candidate) => normalized.includes(candidate.toLowerCase()));
}""",
    """function sameStringSet(actual, expected) {
  return actual.length === expected.length
    && [...actual].sort().every((value, index) => value === [...expected].sort()[index]);
}""",
)

replace_once(
    "lib/doctor.mjs",
    """  const manifestPath = join(root, '.claude-plugin', 'plugin.json');
  let manifest = null;
  try {
    manifest = readJson(manifestPath);
    add(checks, 'plugin manifest', manifest.name === PLUGIN_NAME, manifestPath);
    add(checks, 'manifest version', manifest.version === packageVersion, manifest.version || 'missing');
    add(checks, 'manifest skills', Array.isArray(manifest.skills) && manifest.skills.length > 0, `${manifest.skills?.length || 0} declared`);
    // Claude Code >= 2.1.220 loads agents/hooks from the standard
    // plugin-root locations, never from manifest fields — check the
    // materialized surfaces, not manifest declarations.
    const agentsDir = join(root, 'agents');
    const agentCount = existsSync(agentsDir)
      ? readdirSync(agentsDir).filter((name) => name.endsWith('.md')).length
      : 0;
    const hooksFile = join(root, 'hooks', 'hooks.json');
    if ((receipt?.mode || 'full') === 'full') {
      add(checks, 'plugin-root agents materialized', agentCount > 0, `${agentCount} agent file(s) in agents/`);
      add(checks, 'standard hooks file present', existsSync(hooksFile), hooksFile);
      add(checks, 'manifest omits inert agents/hooks fields', !manifest.agents && !manifest.hooks,
        'agents+hooks load from plugin-root standard locations on >= 2.1.220');
    } else if (receipt?.mode === 'skills') {
      add(checks, 'skills mode excludes agents', agentCount === 0 && !manifest.agents, `${agentCount} in agents/`);
      add(checks, 'skills mode excludes manifest hooks', !manifest.hooks, String(manifest.hooks || 'absent'));
    }
  } catch (err) {
    add(checks, 'plugin manifest', false, err.message);
  }""",
    """  const manifestPath = join(root, '.claude-plugin', 'plugin.json');
  let manifest = null;
  let expectedInventory = { skills: [], agents: [], hooks: [] };
  try {
    manifest = readJson(manifestPath);
    const mode = receipt?.mode || 'full';
    const contract = loadComponentContract(root);
    expectedInventory = {
      skills: skillNamesForMode(contract, mode),
      agents: agentPathsForMode(contract, mode).map((path) => basename(path)).sort(),
      hooks: hookEventsForMode(root, contract, mode),
    };

    add(checks, 'plugin manifest', manifest.name === PLUGIN_NAME, manifestPath);
    add(checks, 'manifest version', manifest.version === packageVersion, manifest.version || 'missing');

    const manifestSkills = Array.isArray(manifest.skills)
      ? manifest.skills.map((path) => path.split('/').filter(Boolean).at(-1)).sort()
      : [];
    add(
      checks,
      'manifest skill set',
      sameStringSet(manifestSkills, expectedInventory.skills),
      `${manifestSkills.length} declared / ${expectedInventory.skills.length} expected`,
    );

    const agentsDir = join(root, 'agents');
    const materializedAgents = existsSync(agentsDir)
      ? readdirSync(agentsDir).filter((name) => name.endsWith('.md')).sort()
      : [];
    const hooksFile = join(root, 'hooks', 'hooks.json');

    if (mode === 'full') {
      add(
        checks,
        'plugin-root agent set',
        sameStringSet(materializedAgents, expectedInventory.agents),
        `${materializedAgents.length} materialized / ${expectedInventory.agents.length} expected`,
      );
      add(checks, 'standard hooks file present', existsSync(hooksFile), hooksFile);
      add(checks, 'manifest omits inert agents/hooks fields', !manifest.agents && !manifest.hooks,
        'agents+hooks load from plugin-root standard locations on >= 2.1.220');
    } else if (mode === 'skills') {
      add(checks, 'skills mode excludes agents', materializedAgents.length === 0 && !manifest.agents,
        `${materializedAgents.length} materialized`);
      add(checks, 'skills mode excludes root hooks', !existsSync(hooksFile) && !manifest.hooks,
        existsSync(hooksFile) ? hooksFile : 'absent');
    }
  } catch (err) {
    add(checks, 'plugin manifest', false, err.message);
  }""",
)

replace_once(
    "lib/doctor.mjs",
    """    try {
      const details = run('claude', ['plugin', 'details', QUALIFIED_PLUGIN]) || '';
      const expectedSkills = (manifest?.skills || []).map((path) => path.split('/').filter(Boolean).at(-1));
      add(checks, 'loaded skills', inventoryHas(details, 'Skills', expectedSkills), 'plugin details inventory');
      if ((receipt?.mode || 'full') === 'full') {
        add(checks, 'loaded agents', inventoryHas(details, 'Agents', ['mogul', 'ripple-assessor', 'review-execute']), 'plugin details inventory');
        add(checks, 'loaded hooks', inventoryHas(details, 'Hooks', ['SessionStart', 'session-restore-patch', 'hooks.json']), 'plugin details inventory');
      }
    } catch (err) {
      add(checks, 'loaded component inventory', false, err.message);
    }""",
    """    try {
      const details = run('claude', ['plugin', 'details', QUALIFIED_PLUGIN]) || '';
      for (const [label, ids] of Object.entries(expectedInventory)) {
        const display = label[0].toUpperCase() + label.slice(1);
        const actual = inventoryCount(details, display);
        add(
          checks,
          `loaded ${label} exact`,
          actual === ids.length,
          `${actual === null ? 'unreported' : actual} loaded / ${ids.length} expected`,
        );
      }
    } catch (err) {
      add(checks, 'loaded component inventory', false, err.message);
    }""",
)

# ---------------------------------------------------------------------------
# Contract tests.
# ---------------------------------------------------------------------------
replace_once(
    "test/distribution-contract.test.mjs",
    """  buildPluginManifest,
  loadComponentContract,
  skillPathsForMode,""",
    """  buildPluginManifest,
  hookEventsForMode,
  installPayloadForMode,
  loadComponentContract,
  skillPathsForMode,""",
)

replace_once(
    "test/distribution-contract.test.mjs",
    """test('npm package contains the deterministic runtime payload and one release identity', () => {""",
    """test('mode payloads and exact hook contract are truthful', () => {
  const contract = loadComponentContract(ROOT);
  assert.ok(installPayloadForMode('full').includes('hooks'));
  assert.equal(installPayloadForMode('skills').includes('hooks'), false);
  assert.deepEqual(installPayloadForMode('convention'), []);
  assert.equal(hookEventsForMode(ROOT, contract, 'full').length, 8);
  assert.deepEqual(hookEventsForMode(ROOT, contract, 'skills'), []);
});

test('npm package contains the deterministic runtime payload and one release identity', () => {""",
)

replace_once(
    "test/distribution-contract.test.mjs",
    """test('public sync lane never calls the legacy standalone runtime copier', () => {""",
    """test('installer and doctor enforce exact mode inventory', () => {
  const installer = readFileSync(join(ROOT, 'lib', 'installer.mjs'), 'utf-8');
  const doctor = readFileSync(join(ROOT, 'lib', 'doctor.mjs'), 'utf-8');
  assert.match(installer, /requireInventoryCount/);
  assert.match(installer, /copyPayload\\(packageRoot, target, false, mode\\)/);
  assert.match(doctor, /skills mode excludes root hooks/);
  assert.match(doctor, /loaded \\$\\{label\\} exact/);
});

test('public sync lane never calls the legacy standalone runtime copier', () => {""",
)

# ---------------------------------------------------------------------------
# CI: version-delta guard, Node 18/24, current Claude, packed-artifact matrix.
# ---------------------------------------------------------------------------
write(
    ".github/workflows/distribution-contract.yml",
    """name: Distribution contract

on:
  pull_request:
    paths:
      - '.claude-plugin/**'
      - '.github/workflows/distribution-contract.yml'
      - 'bin/**'
      - 'cgg-runtime/agents/**'
      - 'cgg-runtime/config/plugin-components.json'
      - 'cgg-runtime/config/session-learning-protocol.md'
      - 'cgg-runtime/hooks/**'
      - 'cgg-runtime/skills/**'
      - 'hooks/**'
      - 'lib/**'
      - 'package.json'
      - 'package-lock.json'
      - 'test/**'
      - 'README.md'
      - 'START-HERE.md'
      - 'INSTALL.md'
      - 'docs/TERMINOLOGY.md'
      - 'CHANGELOG.md'
  push:
    branches: [main]
    paths:
      - '.claude-plugin/**'
      - '.github/workflows/distribution-contract.yml'
      - 'bin/**'
      - 'cgg-runtime/agents/**'
      - 'cgg-runtime/config/plugin-components.json'
      - 'cgg-runtime/config/session-learning-protocol.md'
      - 'cgg-runtime/hooks/**'
      - 'cgg-runtime/skills/**'
      - 'hooks/**'
      - 'lib/**'
      - 'package.json'
      - 'package-lock.json'
      - 'test/**'
      - 'README.md'
      - 'START-HERE.md'
      - 'INSTALL.md'
      - 'docs/TERMINOLOGY.md'
      - 'CHANGELOG.md'
  workflow_dispatch:

permissions:
  contents: read

jobs:
  release-version-contract:
    if: github.event_name == 'pull_request'
    name: Runtime changes advance the public version
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-node@v4
        with:
          node-version: '24'
      - name: Compare public runtime delta with base version
        env:
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
        run: |
          set -euo pipefail
          git fetch origin "$BASE_SHA" "$HEAD_SHA" --depth=1
          CHANGED="$(git diff --name-only "$BASE_SHA" "$HEAD_SHA")"
          if printf '%s\\n' "$CHANGED" | grep -Eq '^(\\.claude-plugin/|bin/|cgg-runtime/(agents|config|hooks|skills)/|hooks/|lib/)'; then
            BASE_VERSION="$(git show "$BASE_SHA:package.json" | node -e "let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>process.stdout.write(JSON.parse(s).version))")"
            CURRENT_VERSION="$(node -p "require('./package.json').version")"
            test "$BASE_VERSION" != "$CURRENT_VERSION" || {
              echo "Public runtime changed without advancing package.version ($CURRENT_VERSION)." >&2
              exit 1
            }
          fi
          node <<'NODE'
          const fs = require('fs');
          const pkg = require('./package.json');
          const lock = require('./package-lock.json');
          const plugin = require('./.claude-plugin/plugin.json');
          if (pkg.version !== lock.version || pkg.version !== lock.packages[''].version || pkg.version !== plugin.version) {
            throw new Error(`release identity mismatch: package=${pkg.version} lock=${lock.version}/${lock.packages[''].version} plugin=${plugin.version}`);
          }
          NODE

  node-contract:
    name: Node ${{ matrix.node }} and npm package contract
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        node: ['18', '24']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node }}
      - name: Versions
        run: |
          node --version
          npm --version
      - name: Node tests
        run: npm test
      - name: Syntax check
        run: |
          find bin lib test -type f -name '*.mjs' -print0 | xargs -0 -n1 node --check
      - name: npm payload receipt
        run: npm pack --dry-run

  plugin-contract:
    name: Claude Code plugin contract
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '24'
      - name: Install current Claude Code CLI
        run: npm install --global @anthropic-ai/claude-code@latest
      - name: Claude Code version
        run: claude --version
      - name: Strict plugin validation
        run: claude plugin validate . --strict
""",
)

write(
    ".github/workflows/installer-smoke.yml",
    """name: Packed installer lifecycle

on:
  pull_request:
    paths:
      - '.claude-plugin/**'
      - '.github/workflows/installer-smoke.yml'
      - 'bin/**'
      - 'cgg-runtime/agents/**'
      - 'cgg-runtime/config/plugin-components.json'
      - 'cgg-runtime/config/session-learning-protocol.md'
      - 'cgg-runtime/hooks/**'
      - 'cgg-runtime/skills/**'
      - 'hooks/**'
      - 'lib/**'
      - 'package.json'
      - 'package-lock.json'
  workflow_dispatch:

permissions:
  contents: read

jobs:
  installer-smoke:
    name: Packed full scopes, exact skills transition, convention, uninstall
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '24'
      - name: Install current Claude Code CLI
        run: npm install --global @anthropic-ai/claude-code@latest
      - name: Pack and install the exact release artifact
        env:
          CGG_PREFIX: ${{ runner.temp }}/cgg-prefix
        run: |
          set -euo pipefail
          TARBALL="$(npm pack --silent | tail -1)"
          npm install --prefix "$CGG_PREFIX" "$GITHUB_WORKSPACE/$TARBALL"
          test -x "$CGG_PREFIX/node_modules/.bin/cgg"
          echo "CGG_BIN=$CGG_PREFIX/node_modules/.bin/cgg" >> "$GITHUB_ENV"
      - name: Show toolchain versions
        run: |
          node --version
          npm --version
          claude --version
          "$CGG_BIN" --version
      - name: Exercise packed artifact across scopes and modes
        env:
          ROOT: ${{ runner.temp }}/matrix
        run: |
          set -euo pipefail

          init_project() {
            local project="$1"
            mkdir -p "$project"
            git -C "$project" init
            git -C "$project" config user.email "ci@prompted.local"
            git -C "$project" config user.name "CGG CI"
          }

          assert_zone_survives() {
            local project="$1"
            test -f "$project/.ticzone"
            test -f "$project/.ticignore"
            test -d "$project/audit-logs"
            test -f "$project/CLAUDE.md"
          }

          exercise_full_scope() {
            local scope="$1"
            local home="$ROOT/full-$scope/home"
            local project="$ROOT/full-$scope/project"
            local target="$ROOT/full-$scope/target"
            mkdir -p "$home"
            init_project "$project"
            (
              export HOME="$home"
              cd "$project"
              "$CGG_BIN" install --mode full --scope "$scope" --target "$target"
              "$CGG_BIN" doctor --target "$target"
              "$CGG_BIN" install --mode full --scope "$scope" --target "$target"
              "$CGG_BIN" doctor --target "$target"
              "$CGG_BIN" uninstall --scope "$scope" --target "$target" --keep-data
            )
            test ! -e "$target"
            assert_zone_survives "$project"
          }

          exercise_full_scope local
          exercise_full_scope user
          exercise_full_scope project

          home="$ROOT/skills/home"
          project="$ROOT/skills/project"
          target="$ROOT/skills/target"
          mkdir -p "$home"
          init_project "$project"
          (
            export HOME="$home"
            cd "$project"
            "$CGG_BIN" install --mode full --scope local --target "$target"
            "$CGG_BIN" install --mode skills --scope local --target "$target"
            "$CGG_BIN" doctor --target "$target"
            test ! -e "$target/agents"
            test ! -e "$target/hooks"
            "$CGG_BIN" uninstall --scope local --target "$target" --keep-data
          )
          test ! -e "$target"
          assert_zone_survives "$project"

          home="$ROOT/convention/home"
          project="$ROOT/convention/project"
          target="$ROOT/convention/target"
          mkdir -p "$home"
          init_project "$project"
          (
            export HOME="$home"
            cd "$project"
            "$CGG_BIN" install --mode convention --scope local --target "$target"
          )
          test ! -e "$target"
          test -f "$project/CLAUDE.md"
          grep -q 'cgg-session-learning-protocol:v5' "$project/CLAUDE.md"
          test ! -e "$project/.ticzone"
          test ! -e "$project/audit-logs"
""",
)

replace_once(
    ".github/workflows/npm-release.yml",
    """          node-version: '20'""",
    """          node-version: '24'""",
)
replace_once(
    ".github/workflows/npm-release.yml",
    """          ACTUAL_VERSION="$(node -p "require('./package.json').version")"
          test "$ACTUAL_VERSION" = "$EXPECTED_VERSION" || {
            echo "package.json=$ACTUAL_VERSION expected=$EXPECTED_VERSION" >&2
            exit 1
          }""",
    """          ACTUAL_VERSION="$(node -p "require('./package.json').version")"
          LOCK_VERSION="$(node -p "require('./package-lock.json').version")"
          LOCK_ROOT_VERSION="$(node -p "require('./package-lock.json').packages[''].version")"
          PLUGIN_VERSION="$(node -p "require('./.claude-plugin/plugin.json').version")"
          test "$ACTUAL_VERSION" = "$EXPECTED_VERSION" || {
            echo "package.json=$ACTUAL_VERSION expected=$EXPECTED_VERSION" >&2
            exit 1
          }
          test "$ACTUAL_VERSION" = "$LOCK_VERSION" \
            && test "$ACTUAL_VERSION" = "$LOCK_ROOT_VERSION" \
            && test "$ACTUAL_VERSION" = "$PLUGIN_VERSION" || {
              echo "release identity mismatch: package=$ACTUAL_VERSION lock=$LOCK_VERSION/$LOCK_ROOT_VERSION plugin=$PLUGIN_VERSION" >&2
              exit 1
            }""",
)

# ---------------------------------------------------------------------------
# Public documentation: candidate status, true skills semantics, Git source
# evaluation boundary, and dual release/provenance identity.
# ---------------------------------------------------------------------------
replace_once(
    "README.md",
    """## Install

```bash
npx context-grapple-gun@5 install
```

The v5 npm package contains the exact plugin/runtime payload it installs. It no longer clones a moving `main` branch and calls the result a versioned install.

Default behavior:""",
    """## Release standing

CGG v5 is a **release candidate** until the exact npm artifact is published and a registry-origin install receives a clean receipt. The intended public command is:

```bash
npx context-grapple-gun@5 install
```

Do not infer registry availability from the repository version. The currently published 4.x package is legacy and is not the governed v5 distribution path.

The v5 package contract contains the exact plugin/runtime payload it installs. It does not clone a moving `main` branch and call the result a versioned install.

Default behavior:""",
)

replace_once(
    "README.md",
    """The source plugin manifest is the component authority. The marketplace identifies the source; it does not carry a second partial component map. Git installs use the source plugin's guarded semantic release version. npm installs generate a mode-specific manifest stamped with the same package version and preserve that state in `cgg-install-receipt.json`. Distribution CI requires public runtime changes to advance that shared version.""",
    """The source plugin manifest is the component authority. The marketplace identifies the source; it does not carry a second partial component map. The semantic version is the public compatibility identity; a Git commit is exact source provenance. npm installs generate a mode-specific manifest stamped with the package version and preserve the verified inventory in `cgg-install-receipt.json`. Distribution CI requires public runtime changes to advance that shared version.""",
)

replace_once(
    "README.md",
    """The public component set is governed by `cgg-runtime/config/plugin-components.json`. Deprecated surfaces and unrefreshed teaching artifacts do not enter the plugin merely because they exist in the repository.""",
    """The public component set is governed by `cgg-runtime/config/plugin-components.json`. Full mode is admitted only at exact `Skills(17) / Agents(11) / Hooks(8)`. Skills mode is exact `Skills(6) / Agents(0) / Hooks(0)`. Deprecated surfaces and unrefreshed teaching artifacts do not enter the plugin merely because they exist in the repository.""",
)

replace_once(
    "README.md",
    """## Authority boundaries""",
    """## Source evaluation boundary

The raw GitHub repository is a source and validation surface, not a release-equivalent full installation. On current Claude Code, admitted agents are materialized into the plugin-root `agents/` directory by the npm-managed installer. Use the repository to inspect code, run tests, and validate the source manifest; use the published npm artifact for the governed full installation once the release gate opens.

## Authority boundaries""",
)

replace_once(
    "START-HERE.md",
    """## Install

```bash
npx context-grapple-gun@5 install
```

The installer now uses the package you invoked as the runtime source. It creates a durable plugin source under `vendor/context-grapple-gun`, generates the selected mode manifest, bootstraps the project governance zone, validates the plugin strictly, installs it at user scope by default, inspects the loaded component inventory, and writes a receipt.

A successful install means those checks passed. It is no longer a success message printed after cloning a moving branch.""",
    """## Release standing

CGG v5 remains a release candidate until the exact npm artifact is published and passes the same clean lifecycle from the public registry. The intended public command is:

```bash
npx context-grapple-gun@5 install
```

Do not treat that command as available merely because the repository declares `5.0.0`. The currently published 4.x package is legacy.

Once published, the installer uses the package you invoked as the runtime source. It creates a durable plugin source under `vendor/context-grapple-gun`, generates the selected mode manifest, bootstraps the project governance zone, validates the plugin strictly, installs it at user scope by default, verifies exact loaded inventory, and writes a receipt.

A successful install means those checks passed. It is not a success message printed after cloning a moving branch.""",
)

replace_once(
    "START-HERE.md",
    """See [INSTALL.md](INSTALL.md) for direct GitHub installation, target control, reconciliation, and safe uninstall.""",
    """See [INSTALL.md](INSTALL.md) for release status, source evaluation, target control, reconciliation, and safe uninstall.""",
)

replace_once(
    "START-HERE.md",
    """**Does direct GitHub installation differ from npm?**  
Yes. Git installation uses the source manifest and Git commit as version authority. npm installation uses the exact npm package, creates a durable source target, generates a mode-specific versioned manifest, and writes an install receipt.""",
    """**Does the raw GitHub repository equal the npm installation?**  
No. The repository is the source and validation surface. The semantic version names the public compatibility release; the commit identifies exact source provenance. The npm-managed installer materializes the mode-specific runtime, including the admitted root agent set, and writes the install receipt. Do not describe a raw Git checkout as a release-equivalent full install.""",
)

replace_once(
    "INSTALL.md",
    """# Installing Context Grapple Gun v5

CGG has two supported distribution paths:

1. **npm package install** — deterministic, mode-selectable, receipt-bearing.
2. **direct GitHub marketplace install** — source plugin at a Git commit.

They converge on the same plugin component contract but carry different version authority.""",
    """# Installing Context Grapple Gun v5

## Release standing

CGG v5 is a **release candidate** until `context-grapple-gun@5` is published and the exact registry artifact passes the packed lifecycle gate. The currently published 4.x package is legacy and is not the governed v5 distribution path.

There is one release installation path:

1. **npm-managed install** — deterministic, mode-selectable, exact-inventory verified, and receipt-bearing.

The GitHub repository is the source and validation surface. It is not a release-equivalent full installation because current Claude Code loads admitted agents from a plugin-root directory materialized by the npm installer.""",
)

replace_once(
    "INSTALL.md",
    """### Install modes""",
    """### Exact inventory contract

| Mode | Skills | Agents | Hooks |
|---|---:|---:|---:|
| `full` | 17 | 11 | 8 |
| `skills` | 6 | 0 | 0 |
| `convention` | 0 | 0 | 0 |

Installer verification and `doctor` require exact counts. Presence of one component is not completion.

### Install modes""",
)

regex_once(
    "INSTALL.md",
    r"""## Direct GitHub installation
.*?
## Doctor""",
    """## GitHub source evaluation

The repository is suitable for source inspection and contract validation:

```bash
git clone https://github.com/prompted365/context-grapple-gun.git
cd context-grapple-gun
npm test
npm pack --dry-run
claude plugin validate . --strict
```

Do not present `claude plugin marketplace add prompted365/context-grapple-gun` as equivalent to the npm-managed full installation. On current Claude Code, the raw repository does not materialize the admitted root agent set. The semantic version is the public compatibility identity; the Git commit is exact source provenance. Both belong in release receipts, but neither replaces the other.

## Doctor""",
    flags=re.S,
)

replace_once(
    "INSTALL.md",
    """- non-empty admitted skills and, in full mode, agents and hooks;""",
    """- exact mode inventory: full `17/11/8`, skills `6/0/0`;""",
)

replace_once(
    "INSTALL.md",
    """The distribution contract workflow runs on changes to plugin manifests, runtime components, CLI code, package metadata, tests, and public installation docs.""",
    """The distribution contract workflow runs on changes to plugin manifests, runtime components, CLI code, package metadata, tests, and public installation docs. A public runtime delta must advance the version relative to the pull request base.""",
)

replace_once(
    "CHANGELOG.md",
    """- Added a protected, manually dispatched npm publication workflow with version gating, dry-run mode, strict plugin validation, and provenance.""",
    """- Added a protected, manually dispatched npm publication workflow with version gating, dry-run mode, strict plugin validation, and provenance.
- Made skills mode a true zero-agent, zero-hook surface instead of copying the full root hook lifecycle.
- Upgraded installer and doctor completion from nonzero presence checks to exact mode inventory.
- Replaced checkout-origin smoke testing with packed-tarball execution across user, project, and local scopes.
- Classified the raw GitHub repository as source evaluation rather than a release-equivalent full installation.
- Added a base-branch version-advance gate for public runtime changes.""",
)

# Self-delete the one-shot machinery from the final tree.
for relative in [
    "scripts/apply-public-audit-fixes.py",
    ".github/workflows/apply-public-audit-fixes.yml",
]:
    path = ROOT / relative
    if path.exists():
        path.unlink()
