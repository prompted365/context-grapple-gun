import {
  existsSync,
  lstatSync,
  readdirSync,
  readFileSync,
} from 'node:fs';
import { join, relative, resolve } from 'node:path';
import {
  INSTALL_PAYLOAD,
  INSTALL_RECEIPT,
} from './distribution-contract.mjs';
import {
  error,
  findCggRoot,
  getPackageRoot,
  getVersion,
  heading,
  info,
  log,
  readJson,
  sha256,
  warn,
} from './utils.mjs';

const VALID_SUBCOMMANDS = ['check', 'diff', 'sync'];
const GENERATED_DIFFERENCES = new Set([
  '.claude-plugin/plugin.json',
  INSTALL_RECEIPT,
]);

function collectFiles(base, path = base, output = new Map()) {
  if (!existsSync(path)) return output;
  const stat = lstatSync(path);
  if (stat.isFile()) {
    const rel = relative(base, path).replaceAll('\\', '/');
    if (!GENERATED_DIFFERENCES.has(rel)) output.set(rel, sha256(readFileSync(path)));
    return output;
  }
  for (const entry of readdirSync(path)) {
    if (entry === '.git' || entry === 'node_modules') continue;
    collectFiles(base, join(path, entry), output);
  }
  return output;
}

function payloadFiles(root) {
  const output = new Map();
  for (const item of INSTALL_PAYLOAD) {
    const path = join(root, item);
    if (!existsSync(path)) continue;
    if (lstatSync(path).isFile()) {
      const rel = item.replaceAll('\\', '/');
      if (!GENERATED_DIFFERENCES.has(rel)) output.set(rel, sha256(readFileSync(path)));
    } else {
      const nested = collectFiles(root, path);
      for (const [name, hash] of nested) output.set(name, hash);
    }
  }
  return output;
}

function comparePayload(packageRoot, target) {
  const source = payloadFiles(packageRoot);
  const installed = payloadFiles(target);
  const rows = [];
  const all = new Set([...source.keys(), ...installed.keys()]);
  for (const path of [...all].sort()) {
    const sourceHash = source.get(path) || null;
    const installedHash = installed.get(path) || null;
    let status = 'synced';
    if (!sourceHash) status = 'extra_installed';
    else if (!installedHash) status = 'missing_installed';
    else if (sourceHash !== installedHash) status = 'drifted';
    rows.push({ path, status, sourceHash, installedHash });
  }
  return rows;
}

function numericVersion(version) {
  const match = String(version || '').match(/^(\d+)\.(\d+)\.(\d+)/);
  return match ? match.slice(1).map(Number) : null;
}

function compareVersions(a, b) {
  const left = numericVersion(a);
  const right = numericVersion(b);
  if (!left || !right) return null;
  for (let i = 0; i < 3; i += 1) {
    if (left[i] < right[i]) return -1;
    if (left[i] > right[i]) return 1;
  }
  return 0;
}

function loadTarget(targetOverride) {
  const root = findCggRoot(targetOverride);
  if (!root) throw new Error('CGG package target not found. Run: cgg install');
  const receiptPath = join(root, INSTALL_RECEIPT);
  if (!existsSync(receiptPath)) {
    throw new Error(`CGG npm install receipt not found: ${receiptPath}`);
  }
  return { root, receipt: readJson(receiptPath) };
}

function printDiff(rows) {
  const changed = rows.filter((row) => row.status !== 'synced');
  if (!changed.length) {
    log('Package payload and durable target are byte-identical.');
    return changed;
  }
  for (const row of changed) {
    const writer = row.status === 'extra_installed' ? warn : error;
    writer(`${row.status.padEnd(18)} ${row.path}`);
  }
  return changed;
}

export async function sync(subcommand = 'check', opts = {}) {
  if (!VALID_SUBCOMMANDS.includes(subcommand)) {
    throw new Error(`Unknown sync subcommand: ${subcommand}. Expected: ${VALID_SUBCOMMANDS.join(', ')}`);
  }

  const packageRoot = resolve(opts.packageRoot || getPackageRoot());
  const packageVersion = getVersion();
  const { root, receipt } = loadTarget(opts.target);
  const rows = comparePayload(packageRoot, root);

  heading('CGG v5 package reconciliation');
  log(`CLI package: ${packageVersion}`);
  log(`Installed target: ${root}`);
  log(`Receipt package: ${receipt.package_version || 'unknown'}`);

  if (subcommand === 'diff') {
    const changed = printDiff(rows);
    if (changed.length) process.exitCode = 1;
    return { root, receipt, rows };
  }

  if (subcommand === 'check') {
    const changed = printDiff(rows);
    const versionState = compareVersions(packageVersion, receipt.package_version);
    if (versionState === -1) {
      error('The running CLI is older than the installed target; refusing to treat it as reconciliation authority.');
      process.exitCode = 1;
    } else if (versionState === 1) {
      warn('A newer CLI package is available to reconcile this target. Run: cgg sync sync');
      process.exitCode = 1;
    } else if (packageVersion !== receipt.package_version) {
      warn('Package versions differ and could not be ordered safely.');
      process.exitCode = 1;
    }
    return { root, receipt, rows, changed };
  }

  const ordering = compareVersions(packageVersion, receipt.package_version);
  if (ordering === -1) {
    throw new Error(
      `Refusing to downgrade target ${receipt.package_version} with older CLI ${packageVersion}.\n` +
      `Run npx context-grapple-gun@${receipt.package_version} sync sync, or install a newer intended version explicitly.`,
    );
  }

  info('Reconciliation is a governed reinstall, not a raw copy into ~/.claude.');
  const { install } = await import('./installer.mjs');
  return install({
    mode: receipt.mode,
    scope: receipt.scope,
    target: root,
    zoneRoot: receipt.zone_root,
  });
}
