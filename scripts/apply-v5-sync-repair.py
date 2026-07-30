#!/usr/bin/env python3
"""One-time branch migration for the v5 receipt/tree sync contract.

This script is intentionally deleted by the workflow that executes it.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if old not in text:
        raise SystemExit(f"expected migration anchor missing in {path}: {old[:100]!r}")
    write(path, text.replace(old, new, 1))


HASH_BLOCK = r'''
function portablePath(path) {
  return path.split(sep).join('/');
}

function defaultTreeExclude(relativePath) {
  const normalized = portablePath(relativePath);
  const parts = normalized.split('/');
  const base = parts.at(-1);
  return (
    parts.includes('.git') ||
    parts.includes('node_modules') ||
    parts.includes('__pycache__') ||
    base === '.cgg-install.json' ||
    base === '.DS_Store' ||
    base?.endsWith('.pyc') ||
    base?.startsWith('.cgg-stage-') ||
    base?.includes('.cgg-backup-')
  );
}

/**
 * Return deterministic signatures for every authority-bearing file in a tree.
 * Generated caches and the mutable install receipt are excluded deliberately.
 */
export function treeSignatures(root, opts = {}) {
  const absoluteRoot = resolve(root);
  const exclude = opts.exclude || defaultTreeExclude;
  const signatures = new Map();

  if (!existsSync(absoluteRoot)) return signatures;

  function walk(path) {
    const entries = readdirSync(path, { withFileTypes: true })
      .sort((a, b) => a.name.localeCompare(b.name));

    for (const entry of entries) {
      const absolute = join(path, entry.name);
      const rel = portablePath(relative(absoluteRoot, absolute));
      if (exclude(rel)) continue;

      const stat = lstatSync(absolute);
      if (stat.isDirectory()) {
        walk(absolute);
      } else if (stat.isSymbolicLink()) {
        signatures.set(rel, {
          type: 'symlink',
          target: readlinkSync(absolute),
          executable: false,
        });
      } else if (stat.isFile()) {
        signatures.set(rel, {
          type: 'file',
          sha256: sha256File(absolute),
          executable: Boolean(stat.mode & 0o111),
        });
      }
    }
  }

  walk(absoluteRoot);
  return signatures;
}

export function hashTree(root, opts = {}) {
  const hash = createHash('sha256');
  for (const [path, signature] of treeSignatures(root, opts)) {
    hash.update(path);
    hash.update('\0');
    hash.update(JSON.stringify(signature));
    hash.update('\0');
  }
  return hash.digest('hex');
}

export function diffTrees(expectedRoot, actualRoot, opts = {}) {
  const expected = treeSignatures(expectedRoot, opts);
  const actual = treeSignatures(actualRoot, opts);
  const missing = [];
  const extra = [];
  const changed = [];

  for (const [path, signature] of expected) {
    if (!actual.has(path)) missing.push(path);
    else if (JSON.stringify(signature) !== JSON.stringify(actual.get(path))) changed.push(path);
  }
  for (const path of actual.keys()) {
    if (!expected.has(path)) extra.push(path);
  }

  return {
    missing: missing.sort(),
    extra: extra.sort(),
    changed: changed.sort(),
    clean: missing.length === 0 && extra.length === 0 && changed.length === 0,
  };
}

'''

SYNC_CONTENT = r'''import { existsSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import {
  diffTrees,
  findZoneRoot,
  getPackageRoot,
  getVersion,
  hashTree,
  heading,
  info,
  log,
  readJson,
  warn,
} from './utils.mjs';
import {
  PLUGIN_NAME,
  install,
  preparePackagedRuntime,
  resolveInstallTarget,
} from './installer.mjs';

const VALID = new Set(['check', 'diff', 'sync']);

function printPaths(label, paths, limit = 200) {
  if (!paths.length) return;
  info(`  ${label} (${paths.length})`);
  for (const path of paths.slice(0, limit)) info(`    - ${path}`);
  if (paths.length > limit) info(`    ... ${paths.length - limit} more`);
}

export function inspectSyncState(opts = {}) {
  const scope = opts.scope || 'user';
  const zoneRoot = findZoneRoot(opts.projectDir || process.cwd());
  const target = resolveInstallTarget({ scope, zoneRoot, target: opts.target });
  const receiptPath = join(target, '.cgg-install.json');

  if (!existsSync(receiptPath)) {
    throw new Error(`No v5 install receipt found at ${receiptPath}. Run cgg install first.`);
  }

  const receipt = readJson(receiptPath);
  if (receipt.package !== PLUGIN_NAME || receipt.managed_target !== target) {
    throw new Error('Install receipt does not authorize this target as a CGG managed runtime.');
  }
  if (receipt.managed_target_kind === 'source_checkout') {
    throw new Error('cgg sync does not rewrite a git source checkout. Use git status/diff and run the local installer deliberately.');
  }

  const prepared = preparePackagedRuntime(target, {
    sourceRoot: opts.sourceRoot || getPackageRoot(),
    mode: receipt.mode,
    version: getVersion(),
    forceRuntimeOverwrite: true,
  });

  try {
    const expectedHash = hashTree(prepared.candidate);
    const actualHash = hashTree(target);
    const receiptHash = receipt.hashes?.runtime_tree_sha256 || null;
    const diff = diffTrees(prepared.candidate, target);
    const localDrift = !receiptHash || receiptHash !== actualHash;
    const packageDrift = expectedHash !== actualHash || receipt.version !== getVersion();

    return {
      scope,
      zoneRoot,
      target,
      receipt,
      packageVersion: getVersion(),
      installedVersion: receipt.version,
      receiptHash,
      actualHash,
      expectedHash,
      localDrift,
      packageDrift,
      inSync: !localDrift && !packageDrift,
      diff,
    };
  } finally {
    if (!prepared.inPlace && existsSync(prepared.candidate)) {
      rmSync(prepared.candidate, { recursive: true, force: true });
    }
  }
}

function printState(state) {
  heading('CGG runtime sync');
  info(`  package version ... ${state.packageVersion}`);
  info(`  installed version . ${state.installedVersion}`);
  info(`  target ............ ${state.target}`);
  info(`  zone .............. ${state.zoneRoot}`);
  info(`  receipt integrity . ${state.localDrift ? 'DRIFTED OR UNPROVEN' : 'clean'}`);
  info(`  package parity .... ${state.packageDrift ? 'update/diff present' : 'clean'}`);
}

export function sync(subcommand = 'check', opts = {}) {
  const action = subcommand || 'check';
  if (!VALID.has(action)) {
    throw new Error(`Unknown sync subcommand: ${action}. Use check, diff, or sync.`);
  }

  const state = inspectSyncState(opts);
  printState(state);

  if (action === 'diff') {
    printPaths('missing from installed runtime', state.diff.missing);
    printPaths('extra in installed runtime', state.diff.extra);
    printPaths('changed', state.diff.changed);
    if (state.diff.clean) info('  file diff ........ clean');
    if (state.localDrift) warn('Installed bytes no longer match the last install receipt. Review before overwriting.');
    return state;
  }

  if (action === 'check') {
    if (!state.inSync) {
      throw new Error(
        state.localDrift
          ? 'CGG runtime has local drift or an unproven legacy receipt. Run cgg sync diff.'
          : 'CGG runtime differs from the current package. Run cgg sync diff, then cgg sync sync.',
      );
    }
    log('Managed runtime matches both its receipt and the current package.');
    return state;
  }

  if (state.inSync) {
    log('Managed runtime is already synchronized.');
    return state;
  }
  if (state.localDrift && !opts.force) {
    throw new Error(
      'Refusing to overwrite locally drifted managed runtime. Run cgg sync diff and re-run cgg sync sync --force only after review.',
    );
  }

  return install({
    mode: state.receipt.mode,
    scope: state.receipt.scope || state.scope,
    projectDir: state.receipt.zone_root || state.zoneRoot,
    target: state.target,
    replaceMarketplace: Boolean(opts.replaceMarketplace),
    forceRuntimeOverwrite: Boolean(opts.force),
  });
}
'''

# utils.mjs
replace_once(
    "lib/utils.mjs",
    "  existsSync,\n  mkdirSync,\n  readFileSync,\n  writeFileSync,\n} from 'node:fs';",
    "  existsSync,\n  lstatSync,\n  mkdirSync,\n  readFileSync,\n  readdirSync,\n  readlinkSync,\n  writeFileSync,\n} from 'node:fs';",
)
replace_once(
    "lib/utils.mjs",
    "import { dirname, join, resolve } from 'node:path';",
    "import { dirname, join, relative, resolve, sep } from 'node:path';",
)
replace_once(
    "lib/utils.mjs",
    "/**\n * Resolve the governance zone root.",
    HASH_BLOCK + "/**\n * Resolve the governance zone root.",
)

# installer.mjs
replace_once("lib/installer.mjs", "  getVersion,\n  heading,", "  getVersion,\n  hashTree,\n  heading,")
replace_once(
    "lib/installer.mjs",
    """  if (existsSync(absTarget)) {
    const entries = readdirSync(absTarget);
    const managed = existsSync(join(absTarget, '.cgg-install.json'));
    if (entries.length && !managed) {
      throw new Error(`Refusing to overwrite non-managed directory: ${absTarget}`);
    }
  }
""",
    """  if (existsSync(absTarget)) {
    const entries = readdirSync(absTarget);
    const receiptPath = join(absTarget, '.cgg-install.json');
    const managed = existsSync(receiptPath);
    if (entries.length && !managed) {
      throw new Error(`Refusing to overwrite non-managed directory: ${absTarget}`);
    }
    if (entries.length && managed && !opts.forceRuntimeOverwrite) {
      const receipt = readJson(receiptPath);
      const expected = receipt.hashes?.runtime_tree_sha256;
      if (!expected) {
        throw new Error(
          `Managed runtime ${absTarget} has no tree-integrity receipt. ` +
          'Run cgg sync diff, then re-run with --force-runtime-overwrite only after reviewing local changes.',
        );
      }
      const actual = hashTree(absTarget);
      if (actual !== expected) {
        throw new Error(
          `Managed runtime ${absTarget} has local drift. ` +
          'Run cgg sync diff; use --force-runtime-overwrite only to authorize replacing those changes.',
        );
      }
    }
  }
""",
)
replace_once(
    "lib/installer.mjs",
    "      hooks_manifest_sha256: existsSync(hooksManifest) ? sha256File(hooksManifest) : null,\n",
    "      hooks_manifest_sha256: existsSync(hooksManifest) ? sha256File(hooksManifest) : null,\n      runtime_tree_sha256: hashTree(target),\n",
)
replace_once(
    "lib/installer.mjs",
    "function printPlan({ mode, scope, zoneRoot, target, replaceMarketplace }) {",
    "function printPlan({ mode, scope, zoneRoot, target, replaceMarketplace, forceRuntimeOverwrite }) {",
)
replace_once(
    "lib/installer.mjs",
    "  info(`  marketplace ...... ${replaceMarketplace ? 'replacement explicitly authorized' : 'preserve unless source matches'}`);\n",
    "  info(`  marketplace ...... ${replaceMarketplace ? 'replacement explicitly authorized' : 'preserve unless source matches'}`);\n  info(`  runtime drift .... ${forceRuntimeOverwrite ? 'overwrite explicitly authorized' : 'preserve / hold on local drift'}`);\n",
)
replace_once(
    "lib/installer.mjs",
    "  const replaceMarketplace = Boolean(opts.replaceMarketplace);\n\n  printPlan({ mode, scope, zoneRoot, target, replaceMarketplace });",
    "  const replaceMarketplace = Boolean(opts.replaceMarketplace);\n  const forceRuntimeOverwrite = Boolean(opts.forceRuntimeOverwrite);\n\n  printPlan({ mode, scope, zoneRoot, target, replaceMarketplace, forceRuntimeOverwrite });",
)
replace_once(
    "lib/installer.mjs",
    "    info(`[would stage and atomically activate] ${sourceRoot} -> ${target}`);\n",
    "    info(`[would stage and atomically activate] ${sourceRoot} -> ${target}`);\n    if (forceRuntimeOverwrite) info('[would replace] locally drifted managed runtime if present');\n",
)
replace_once(
    "lib/installer.mjs",
    "  const prepared = preparePackagedRuntime(target, { sourceRoot, mode, version: getVersion() });",
    """  const prepared = preparePackagedRuntime(target, {
    sourceRoot,
    mode,
    version: getVersion(),
    forceRuntimeOverwrite,
  });""",
)

# doctor.mjs
replace_once("lib/doctor.mjs", "  getVersion,\n  heading,", "  getVersion,\n  hashTree,\n  heading,")
replace_once(
    "lib/doctor.mjs",
    """  } else {
    add('install receipt', false, 'missing (manual/source-checkout install)', false);
  }

  const pluginPath = join(root, '.claude-plugin', 'plugin.json');
""",
    """  } else {
    add('install receipt', false, 'missing (manual/source-checkout install)', false);
  }

  if (receipt?.hashes?.runtime_tree_sha256) {
    const currentTreeHash = hashTree(root);
    add(
      'runtime tree integrity',
      currentTreeHash === receipt.hashes.runtime_tree_sha256,
      currentTreeHash === receipt.hashes.runtime_tree_sha256 ? 'matches install receipt' : 'local drift detected',
    );
  } else if (receipt) {
    add('runtime tree integrity', false, 'receipt predates tree-integrity hashing', false);
  }

  const pluginPath = join(root, '.claude-plugin', 'plugin.json');
""",
)

# sync.mjs
write("lib/sync.mjs", SYNC_CONTENT)

# bin/cgg.mjs
replace_once(
    "bin/cgg.mjs",
    "  --replace-marketplace      Explicitly replace a cgg marketplace with a different source\n",
    "  --replace-marketplace      Explicitly replace a cgg marketplace with a different source\n  --force-runtime-overwrite  Replace locally drifted receipt-owned runtime bytes\n",
)
replace_once(
    "bin/cgg.mjs",
    "Doctor options:\n",
    "Sync options:\n  --scope <scope>            user | project (default: user)\n  --target <path>            Override the managed runtime target\n  --project-dir <path>       Project/zone discovery start (default: cwd)\n  --force                    Authorize replacing reviewed local runtime drift\n  --replace-marketplace      Explicitly replace a different cgg marketplace source\n\nDoctor options:\n",
)
replace_once(
    "bin/cgg.mjs",
    "        replaceMarketplace: Boolean(flags['replace-marketplace']),\n",
    "        replaceMarketplace: Boolean(flags['replace-marketplace']),\n        forceRuntimeOverwrite: Boolean(flags['force-runtime-overwrite']),\n",
)
replace_once(
    "bin/cgg.mjs",
    "      sync(positional[0], { target: flags.target });\n",
    """      sync(positional[0], {
        target: flags.target,
        scope: flags.scope || 'user',
        projectDir: flags['project-dir'],
        force: Boolean(flags.force),
        replaceMarketplace: Boolean(flags['replace-marketplace']),
      });
""",
)

# tests
replace_once(
    "tests/npm/distribution.test.mjs",
    "import { authorizeManagedTargetRemoval, removeConventionBlock } from '../../lib/uninstaller.mjs';\n",
    "import { authorizeManagedTargetRemoval, removeConventionBlock } from '../../lib/uninstaller.mjs';\nimport { inspectSyncState } from '../../lib/sync.mjs';\n",
)
replace_once(
    "tests/npm/distribution.test.mjs",
    "    assert.equal(receipt.session_load_state, 'reload_or_next_session_required');\n",
    "    assert.equal(receipt.session_load_state, 'reload_or_next_session_required');\n    assert.ok(receipt.hashes.runtime_tree_sha256);\n",
)
replace_once(
    "tests/npm/distribution.test.mjs",
    """    const commands = readFileSync(logPath, 'utf-8');
    assert.match(commands, /plugin validate/);
""",
    """    const synchronized = inspectSyncState({
      scope: 'project',
      projectDir: zone,
      target,
      sourceRoot: source,
    });
    assert.equal(synchronized.inSync, true);

    writeFileSync(join(target, 'README.md'), 'locally changed\\n', 'utf-8');
    const drifted = inspectSyncState({
      scope: 'project',
      projectDir: zone,
      target,
      sourceRoot: source,
    });
    assert.equal(drifted.localDrift, true);
    assert.throws(
      () => install({ mode: 'full', scope: 'project', projectDir: zone, target, sourceRoot: source }),
      /local drift/,
    );

    const commands = readFileSync(logPath, 'utf-8');
    assert.match(commands, /plugin validate/);
""",
)

# CI real-runtime sync checks.
replace_once(
    ".github/workflows/distribution-contract.yml",
    "          test -f \"$TARGET/.cgg-install.json\"\n\n          node \"$GITHUB_WORKSPACE/bin/cgg.mjs\" uninstall",
    "          test -f \"$TARGET/.cgg-install.json\"\n          node \"$GITHUB_WORKSPACE/bin/cgg.mjs\" sync check --scope project --project-dir \"$PROJECT\" --target \"$TARGET\"\n\n          node \"$GITHUB_WORKSPACE/bin/cgg.mjs\" uninstall",
)
replace_once(
    ".github/workflows/distribution-contract.yml",
    "          node -e \"const r=require(process.argv[1]); if(!r.ok) process.exit(1); if(r.receipt.mode!=='skills') process.exit(2);\" \"$PROJECT/doctor.json\"\n\n          node \"$GITHUB_WORKSPACE/bin/cgg.mjs\" uninstall",
    "          node -e \"const r=require(process.argv[1]); if(!r.ok) process.exit(1); if(r.receipt.mode!=='skills') process.exit(2);\" \"$PROJECT/doctor.json\"\n          node \"$GITHUB_WORKSPACE/bin/cgg.mjs\" sync check --scope user --project-dir \"$PROJECT\"\n\n          node \"$GITHUB_WORKSPACE/bin/cgg.mjs\" uninstall",
)

# Public docs: define sync as receipt/package parity, not legacy direct-copy sync.
replace_once(
    "INSTALL.md",
    """Runtime drift commands remain available:

```bash
cgg sync check
cgg sync diff
cgg sync sync
```
""",
    """Runtime sync is receipt- and package-mediated:

```bash
cgg sync check       # receipt integrity + current package parity
cgg sync diff        # list missing, extra, and changed authority-bearing files
cgg sync sync        # install the current package when receipt integrity is clean
cgg sync sync --force  # only after reviewing and authorizing local drift replacement
```

`cgg sync` does not use the pre-v5 direct-copy manifest. It stages the current package, compares deterministic tree signatures, and routes repair back through the transactional installer.
""",
)
replace_once(
    "README.md",
    "- makes `cgg doctor` check package, plugin, zone, and installed-runtime truth;\n",
    "- makes `cgg doctor` check package, plugin, zone, installed-runtime truth, and receipt tree integrity;\n- makes `cgg sync` compare the installed tree against both its receipt and the current package before repair;\n",
)
replace_once(
    "START-HERE.md",
    "A topology script returning successfully is not, by itself, proof that installation succeeded.\n",
    "A topology script returning successfully is not, by itself, proof that installation succeeded. Use `cgg sync check` to verify that managed runtime bytes still match both their install receipt and the current package.\n",
)

# Remove the one-time migration surfaces from the resulting commit.
(ROOT / "scripts/apply-v5-sync-repair.py").unlink()
(ROOT / ".github/workflows/apply-v5-sync-repair.yml").unlink()
