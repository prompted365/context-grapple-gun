import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
  INSTALL_RECEIPT,
  PLUGIN_NAME,
  QUALIFIED_PLUGIN,
} from './distribution-contract.mjs';
import {
  checkCommand,
  error,
  findCggRoot,
  heading,
  info,
  log,
  readJson,
  run,
} from './utils.mjs';
import { resolveZoneRoot } from './zone.mjs';

const PROTOCOL_MARKER = '<!-- cgg-session-learning-protocol:v5 -->';
const MANAGED_BY = 'context-grapple-gun-npm';

function add(checks, name, ok, detail) {
  checks.push({ name, ok: Boolean(ok), detail });
}

function parseJsonOrNull(value) {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function visitJson(value, visitor) {
  if (Array.isArray(value)) {
    for (const item of value) visitJson(item, visitor);
    return;
  }
  if (!value || typeof value !== 'object') return;
  visitor(value);
  for (const child of Object.values(value)) visitJson(child, visitor);
}

function findNamedRecord(json, name) {
  let found = null;
  visitJson(json, (record) => {
    if (!found && record.name === name) found = record;
  });
  return found;
}

function inventoryCount(details, label) {
  const patterns = [
    new RegExp(`\\b${label}\\b[^\\d\\n]{0,20}(\\d+)`, 'i'),
    new RegExp(`\\b${label}\\b\\s*[:=-]\\s*(\\d+)`, 'i'),
  ];
  for (const pattern of patterns) {
    const match = details.match(pattern);
    if (match) return Number(match[1]);
  }
  return null;
}

function inventoryHas(details, label, candidates) {
  const count = inventoryCount(details, label);
  if (count !== null) return count > 0;
  const normalized = details.toLowerCase();
  return candidates.some((candidate) => normalized.includes(candidate.toLowerCase()));
}

export function doctor(opts = {}) {
  const cwd = resolve(opts.cwd || process.cwd());
  const zoneRoot = resolve(opts.zoneRoot || resolveZoneRoot(cwd));
  const root = findCggRoot(opts.target, cwd);

  if (!root) {
    const claudePath = join(zoneRoot, 'CLAUDE.md');
    if (existsSync(claudePath) && readFileSync(claudePath, 'utf-8').includes(PROTOCOL_MARKER)) {
      heading('CGG Doctor');
      log('Convention-only installation detected.');
      info(`Zone root: ${zoneRoot}`);
      return { mode: 'convention', zoneRoot, checks: [] };
    }
    throw new Error('CGG runtime target not found. Pass --target or run the npm installer first.');
  }

  const topologyScript = join(root, 'cgg-runtime', 'scripts', 'cgg-doctor.sh');
  if (opts.topologyOnly) {
    if (!existsSync(topologyScript)) throw new Error(`Topology script missing: ${topologyScript}`);
    run('bash', [topologyScript], { passthrough: true, cwd: zoneRoot });
    return { mode: 'topology-only', root, zoneRoot, checks: [] };
  }

  const checks = [];
  const receiptPath = join(root, INSTALL_RECEIPT);
  let receipt = null;
  try {
    receipt = readJson(receiptPath);
    add(checks, 'install receipt owner', receipt.managed_by === MANAGED_BY, receiptPath);
    add(checks, 'install receipt state', receipt.status === 'verified', receipt.status || 'missing');
    add(checks, 'receipt target', resolve(receipt.target || '') === resolve(root), receipt.target || 'missing');
  } catch (err) {
    add(checks, 'install receipt', false, err.message);
  }

  let packageVersion = null;
  try {
    const targetPackage = readJson(join(root, 'package.json'));
    packageVersion = targetPackage.version;
    add(checks, 'target package version', Boolean(packageVersion), packageVersion || 'missing');
    if (receipt) {
      add(
        checks,
        'receipt/package version agreement',
        receipt.package_version === packageVersion,
        `${receipt.package_version || 'missing'} / ${packageVersion || 'missing'}`,
      );
    }
  } catch (err) {
    add(checks, 'target package', false, err.message);
  }

  const manifestPath = join(root, '.claude-plugin', 'plugin.json');
  let manifest = null;
  try {
    manifest = readJson(manifestPath);
    add(checks, 'plugin manifest', manifest.name === PLUGIN_NAME, manifestPath);
    add(checks, 'manifest version', manifest.version === packageVersion, manifest.version || 'missing');
    add(checks, 'manifest skills', Array.isArray(manifest.skills) && manifest.skills.length > 0, `${manifest.skills?.length || 0} declared`);
    if ((receipt?.mode || 'full') === 'full') {
      add(checks, 'manifest agents', Boolean(manifest.agents), String(manifest.agents || 'missing'));
      add(checks, 'manifest hooks', Boolean(manifest.hooks), String(manifest.hooks || 'missing'));
    } else if (receipt?.mode === 'skills') {
      add(checks, 'skills mode excludes agents', !manifest.agents, String(manifest.agents || 'absent'));
      add(checks, 'skills mode excludes hooks', !manifest.hooks, String(manifest.hooks || 'absent'));
    }
  } catch (err) {
    add(checks, 'plugin manifest', false, err.message);
  }

  if (!checkCommand('claude')) {
    add(checks, 'Claude Code CLI', false, 'claude command not found');
  } else {
    try {
      run('claude', ['plugin', 'validate', root, '--strict']);
      add(checks, 'strict plugin validation', true, root);
    } catch (err) {
      add(checks, 'strict plugin validation', false, err.message);
    }

    try {
      const listing = run('claude', ['plugin', 'list', '--json']) || '';
      const listingJson = parseJsonOrNull(listing);
      const record = listingJson ? findNamedRecord(listingJson, PLUGIN_NAME) : null;
      const installed = record ? record.enabled !== false : listing.includes(PLUGIN_NAME);
      add(checks, 'installed/enabled plugin record', installed, QUALIFIED_PLUGIN);
    } catch (err) {
      add(checks, 'installed/enabled plugin record', false, err.message);
    }

    try {
      const details = run('claude', ['plugin', 'details', QUALIFIED_PLUGIN]) || '';
      const expectedSkills = (manifest?.skills || []).map((path) => path.split('/').filter(Boolean).at(-1));
      add(checks, 'loaded skills', inventoryHas(details, 'Skills', expectedSkills), 'plugin details inventory');
      if ((receipt?.mode || 'full') === 'full') {
        add(checks, 'loaded agents', inventoryHas(details, 'Agents', ['mogul', 'ripple-assessor', 'review-execute']), 'plugin details inventory');
        add(checks, 'loaded hooks', inventoryHas(details, 'Hooks', ['SessionStart', 'session-restore-patch', 'hooks.json']), 'plugin details inventory');
      }
    } catch (err) {
      add(checks, 'loaded component inventory', false, err.message);
    }
  }

  const requiredZonePaths = [
    '.ticzone',
    '.ticignore',
    'audit-logs/tics',
    'audit-logs/signals',
    'audit-logs/cprs',
    'audit-logs/conformations',
    'audit-logs/economy',
    'audit-logs/provenance',
    'audit-logs/reviews',
  ];
  for (const relative of requiredZonePaths) {
    add(checks, `zone:${relative}`, existsSync(join(zoneRoot, relative)), join(zoneRoot, relative));
  }

  try {
    const zone = readJson(join(zoneRoot, '.ticzone'));
    add(checks, 'zone bands', Array.isArray(zone.bands), JSON.stringify(zone.bands || null));
    add(checks, 'PRESTIGE blocked', !zone.bands?.includes('PRESTIGE'), JSON.stringify(zone.bands || null));
  } catch (err) {
    add(checks, 'zone configuration', false, err.message);
  }

  const claudePath = join(zoneRoot, 'CLAUDE.md');
  add(
    checks,
    'session learning protocol',
    existsSync(claudePath) && readFileSync(claudePath, 'utf-8').includes(PROTOCOL_MARKER),
    claudePath,
  );

  if (existsSync(topologyScript)) {
    heading('Topology');
    try {
      run('bash', [topologyScript], { passthrough: true, cwd: zoneRoot });
      add(checks, 'topology diagnostic', true, topologyScript);
    } catch (err) {
      add(checks, 'topology diagnostic', false, err.message);
    }
  } else {
    add(checks, 'topology script', false, topologyScript);
  }

  heading('Distribution and installation checks');
  for (const check of checks) {
    const marker = check.ok ? 'PASS' : 'FAIL';
    const writer = check.ok ? log : error;
    writer(`${marker.padEnd(4)} ${check.name}${check.detail ? ` — ${check.detail}` : ''}`);
  }

  const failures = checks.filter((check) => !check.ok);
  if (failures.length) {
    throw new Error(`${failures.length} CGG doctor check(s) failed.`);
  }

  log('All applicable installation checks passed.');
  return { root, zoneRoot, receipt, manifest, checks };
}
