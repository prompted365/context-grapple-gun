import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
  INSTALL_RECEIPT,
  PLUGIN_NAME,
  QUALIFIED_PLUGIN,
  expectedInventoryForMode,
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
  // Claude Code >= 2.1.220 plugin-list records carry only a qualified
  // "id" ("name@marketplace") and no "name" field.
  let found = null;
  visitJson(json, (record) => {
    if (found) return;
    if (record.name === name) {
      found = record;
      return;
    }
    if (typeof record.id === 'string'
        && (record.id === name || record.id.startsWith(`${name}@`))) {
      found = record;
    }
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

function inventoryDetail(label, loaded, expected) {
  return `${label} loaded=${loaded === null ? 'unreadable' : loaded} expected=${expected}`;
}

function receiptInventoryMatches(receipt, expected, loaded) {
  const actual = receipt?.verification?.inventory;
  if (!actual) return false;
  for (const key of ['skills', 'agents', 'hooks']) {
    if (actual[key]?.expected_count !== expected[key].expected_count) return false;
    if (actual[key]?.loaded_count !== loaded[key]) return false;
    if (JSON.stringify(actual[key]?.expected_ids || []) !== JSON.stringify(expected[key].expected_ids)) return false;
  }
  return true;
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
    add(checks, 'install receipt schema', receipt.schema_version >= 2, String(receipt.schema_version || 'missing'));
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
        receipt.package_version === packageVersion && receipt.release_version === packageVersion,
        `${receipt.package_version || 'missing'} / ${receipt.release_version || 'missing'} / ${packageVersion || 'missing'}`,
      );
    }
  } catch (err) {
    add(checks, 'target package', false, err.message);
  }

  const mode = receipt?.mode || 'full';
  let expectedInventory = null;
  try {
    expectedInventory = expectedInventoryForMode(root, mode);
    add(
      checks,
      'inventory contract readable',
      true,
      `Skills(${expectedInventory.skills.expected_count}) Agents(${expectedInventory.agents.expected_count}) Hooks(${expectedInventory.hooks.expected_count})`,
    );
  } catch (err) {
    add(checks, 'inventory contract readable', false, err.message);
  }

  const manifestPath = join(root, '.claude-plugin', 'plugin.json');
  let manifest = null;
  try {
    manifest = readJson(manifestPath);
    add(checks, 'plugin manifest', manifest.name === PLUGIN_NAME, manifestPath);
    add(checks, 'manifest version', manifest.version === packageVersion, manifest.version || 'missing');
    add(
      checks,
      'manifest skills exact',
      Array.isArray(manifest.skills)
        && expectedInventory
        && manifest.skills.length === expectedInventory.skills.expected_count,
      `${manifest.skills?.length || 0} declared / ${expectedInventory?.skills.expected_count ?? 'unknown'} expected`,
    );

    const agentsDir = join(root, 'agents');
    const agentCount = existsSync(agentsDir)
      ? readdirSync(agentsDir).filter((name) => name.endsWith('.md')).length
      : 0;
    const hooksFile = join(root, 'hooks', 'hooks.json');
    if (mode === 'full') {
      add(
        checks,
        'plugin-root agents materialized exactly',
        expectedInventory && agentCount === expectedInventory.agents.expected_count,
        `${agentCount} agent file(s) / ${expectedInventory?.agents.expected_count ?? 'unknown'} expected`,
      );
      add(checks, 'standard hooks file present', existsSync(hooksFile), hooksFile);
      add(
        checks,
        'manifest omits inert agents/hooks fields',
        !manifest.agents && !manifest.hooks,
        'agents+hooks load from standard plugin-root locations on Claude Code >= 2.1.220',
      );
    } else if (mode === 'skills') {
      add(checks, 'skills mode excludes plugin-root agents', agentCount === 0 && !manifest.agents, `${agentCount} in agents/`);
      add(checks, 'skills mode excludes standard hooks file', !existsSync(hooksFile) && !manifest.hooks, hooksFile);
    }
  } catch (err) {
    add(checks, 'plugin manifest', false, err.message);
  }

  let loadedInventory = null;
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
      const loadErrors = Array.isArray(record?.errors) ? record.errors : [];
      const installed = record
        ? record.enabled !== false && loadErrors.length === 0
        : listing.includes(PLUGIN_NAME);
      const detail = loadErrors.length
        ? `${QUALIFIED_PLUGIN} listed but failed to load: ${loadErrors.join(' | ')}`
        : QUALIFIED_PLUGIN;
      add(checks, 'installed/enabled plugin record', installed, detail);
    } catch (err) {
      add(checks, 'installed/enabled plugin record', false, err.message);
    }

    try {
      const details = run('claude', ['plugin', 'details', QUALIFIED_PLUGIN]) || '';
      loadedInventory = {
        skills: inventoryCount(details, 'Skills'),
        agents: inventoryCount(details, 'Agents'),
        hooks: inventoryCount(details, 'Hooks'),
      };
      for (const key of ['skills', 'agents', 'hooks']) {
        const expected = expectedInventory?.[key]?.expected_count;
        add(
          checks,
          `loaded ${key} exact`,
          Number.isInteger(loadedInventory[key]) && loadedInventory[key] === expected,
          inventoryDetail(key, loadedInventory[key], expected ?? 'unknown'),
        );
      }
      if (receipt && expectedInventory) {
        add(
          checks,
          'receipt inventory exact',
          receiptInventoryMatches(receipt, expectedInventory, loadedInventory),
          'receipt expected_ids and expected/loaded counts agree with live inventory',
        );
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
  return { root, zoneRoot, receipt, manifest, expectedInventory, loadedInventory, checks };
}
