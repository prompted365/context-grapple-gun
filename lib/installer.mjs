import {
  chmodSync,
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
  rmSync,
} from 'node:fs';
import { homedir } from 'node:os';
import { basename, dirname, join, resolve, sep } from 'node:path';
import {
  DEFAULT_TARGET,
  INSTALL_PAYLOAD,
  INSTALL_RECEIPT,
  MARKETPLACE_NAME,
  PLUGIN_NAME,
  QUALIFIED_PLUGIN,
  agentPathsForMode,
  buildMarketplaceManifest,
  buildPluginManifest,
  expectedInventoryForMode,
  loadComponentContract,
  payloadPathsForMode,
  readReleaseIdentity,
  validateInstallOptions,
} from './distribution-contract.mjs';
import {
  checkCommand,
  getPackageRoot,
  getVersion,
  heading,
  info,
  log,
  readJson,
  run,
  sha256,
  warn,
  writeJson,
} from './utils.mjs';
import {
  applyConvention,
  bootstrapGovernanceZone,
  resolveZoneRoot,
} from './zone.mjs';

const REQUIRED_PAYLOAD = ['.claude-plugin', 'cgg-runtime', 'hooks', 'package.json'];
const MANAGED_BY = 'context-grapple-gun-npm';

function checkPrerequisites(mode) {
  if (mode === 'convention') return;

  heading('Checking prerequisites...');
  if (!checkCommand('claude')) {
    throw new Error('Claude Code CLI is required. Install it before running full or skills mode.');
  }
  const claudeVersion = run('claude', ['--version'], { silent: true })?.trim() || 'unknown';
  info(`  claude .......... ${claudeVersion}`);

  if (!checkCommand('python3')) {
    throw new Error('Python 3 is required by the CGG runtime hooks and governance scripts.');
  }
  info('  python3 ......... found');
}

function ensurePayload(packageRoot) {
  const missing = REQUIRED_PAYLOAD.filter((relative) => !existsSync(join(packageRoot, relative)));
  if (missing.length) {
    throw new Error(`The npm package is incomplete; missing: ${missing.join(', ')}`);
  }
}

function ensureSafeTarget(packageRoot, target) {
  const source = resolve(packageRoot);
  const destination = resolve(target);
  if (source === destination || source.startsWith(`${destination}${sep}`)) {
    throw new Error(
      `Refusing unsafe --target ${destination}; it contains the running package source ${source}.`,
    );
  }
}

function readReceipt(target) {
  const path = join(target, INSTALL_RECEIPT);
  if (!existsSync(path)) return null;
  try {
    return readJson(path);
  } catch (err) {
    throw new Error(`Install receipt is unreadable at ${path}: ${err.message}`);
  }
}

function isDirectoryEmpty(path) {
  return existsSync(path) && readdirSync(path).length === 0;
}

function prepareTarget(target, dryRun) {
  if (!existsSync(target)) {
    if (!dryRun) mkdirSync(target, { recursive: true });
    return { previousReceipt: null, replacingManagedInstall: false };
  }

  if (isDirectoryEmpty(target)) {
    return { previousReceipt: null, replacingManagedInstall: false };
  }

  const previousReceipt = readReceipt(target);
  if (!previousReceipt || previousReceipt.managed_by !== MANAGED_BY) {
    throw new Error(
      `Refusing to overwrite non-managed target: ${target}\n` +
      'Choose an empty --target, or remove/move the existing directory yourself.',
    );
  }

  const owned = previousReceipt.managed_paths || INSTALL_PAYLOAD;
  if (!dryRun) {
    for (const relative of owned) {
      rmSync(join(target, relative), { recursive: true, force: true });
    }
  }
  return { previousReceipt, replacingManagedInstall: true };
}

function copyPayload(packageRoot, target, dryRun, mode) {
  const copied = [];
  for (const relative of payloadPathsForMode(mode)) {
    const source = join(packageRoot, relative);
    if (!existsSync(source)) continue;
    copied.push(relative);
    if (dryRun) continue;
    const destination = join(target, relative);
    mkdirSync(dirname(destination), { recursive: true });
    cpSync(source, destination, { recursive: true, force: true, preserveTimestamps: true });
  }
  return copied;
}

function makeRuntimeExecutable(target) {
  const roots = [
    join(target, 'hooks'),
    join(target, 'cgg-runtime', 'hooks'),
    join(target, 'cgg-runtime', 'scripts'),
    join(target, 'bin'),
  ];
  const visit = (path) => {
    if (!existsSync(path)) return;
    const entries = readdirSync(path, { withFileTypes: true });
    for (const entry of entries) {
      const child = join(path, entry.name);
      if (entry.isDirectory()) visit(child);
      else if (/\.(?:sh|py|mjs)$/.test(entry.name)) chmodSync(child, 0o755);
    }
  };
  for (const root of roots) visit(root);
}

function materializeAgents({ packageRoot, target, mode, dryRun }) {
  // Claude Code >= 2.1.220 auto-loads agents ONLY from the plugin-root
  // agents/ directory; the manifest "agents" field validates but loads
  // nothing. Materialize only the mode's admitted contract agents.
  const agentsDir = join(target, 'agents');
  const contract = loadComponentContract(packageRoot);
  const agentPaths = agentPathsForMode(contract, mode);
  if (dryRun) return agentPaths.length > 0;
  rmSync(agentsDir, { recursive: true, force: true });
  if (!agentPaths.length) return false;
  mkdirSync(agentsDir, { recursive: true });
  for (const relative of agentPaths) {
    const source = join(packageRoot, relative.replace(/^\.\//, ''));
    cpSync(source, join(agentsDir, basename(relative)), { force: true, preserveTimestamps: true });
  }
  return true;
}

function writeInstalledManifests({ packageRoot, target, mode, version, dryRun }) {
  const plugin = buildPluginManifest({ packageRoot, mode, version });
  const marketplace = buildMarketplaceManifest();
  if (!dryRun) {
    mkdirSync(join(target, '.claude-plugin'), { recursive: true });
    writeJson(join(target, '.claude-plugin', 'plugin.json'), plugin);
    writeJson(join(target, '.claude-plugin', 'marketplace.json'), marketplace);
  }
  return { plugin, marketplace };
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

function collectSourceStrings(record) {
  const strings = [];
  const sourceKeys = new Set(['source', 'path', 'location', 'directory', 'repo', 'repository', 'url']);
  const walk = (value, key = '') => {
    if (typeof value === 'string') {
      if (sourceKeys.has(key)) strings.push(value);
      return;
    }
    if (Array.isArray(value)) {
      for (const item of value) walk(item, key);
      return;
    }
    if (!value || typeof value !== 'object') return;
    for (const [childKey, childValue] of Object.entries(value)) walk(childValue, childKey);
  };
  walk(record);
  return strings;
}

function marketplaceState(target) {
  const raw = run('claude', ['plugin', 'marketplace', 'list', '--json'], { silent: true }) || '';
  if (!raw.trim()) return { exists: false, raw };
  const json = parseJsonOrNull(raw);
  if (!json) {
    const exists = raw.includes(MARKETPLACE_NAME);
    return { exists, raw, sourceKnown: false };
  }
  const record = findNamedRecord(json, MARKETPLACE_NAME);
  if (!record) return { exists: false, raw, json };
  const sources = collectSourceStrings(record);
  const normalizedTarget = resolve(target);
  const matchesTarget = sources.some((source) => {
    const normalized = source.startsWith('file://') ? source.slice('file://'.length) : source;
    return normalized === normalizedTarget || resolve(normalized) === normalizedTarget;
  });
  return {
    exists: true,
    raw,
    json,
    record,
    sources,
    sourceKnown: sources.length > 0,
    matchesTarget,
  };
}

function preflightMarketplace(target) {
  const state = marketplaceState(target);
  if (state.exists && state.sourceKnown && !state.matchesTarget) {
    throw new Error(
      `Marketplace '${MARKETPLACE_NAME}' already points to another source: ${state.sources.join(', ')}\n` +
      `Expected npm-managed source: ${target}\n` +
      `Inspect with: claude plugin marketplace list --json\n` +
      `Rebind only deliberately; marketplace removal may uninstall plugins and affect stored data.`,
    );
  }
  return state;
}

function configureMarketplace(target, preflight = null) {
  const state = preflight || marketplaceState(target);
  if (state.exists) {
    if (!state.sourceKnown) {
      warn(`Marketplace '${MARKETPLACE_NAME}' exists but its source was not machine-readable; updating in place.`);
    }
    run('claude', ['plugin', 'marketplace', 'update', MARKETPLACE_NAME], { passthrough: true });
    return 'updated';
  }
  run('claude', ['plugin', 'marketplace', 'add', target], { passthrough: true });
  return 'added';
}

function pluginInstalled() {
  const raw = run('claude', ['plugin', 'list', '--json'], { silent: true }) || '';
  if (!raw.trim()) return false;
  const json = parseJsonOrNull(raw);
  if (json) return Boolean(findNamedRecord(json, PLUGIN_NAME));
  return raw.includes(PLUGIN_NAME);
}

function installOrUpdatePlugin({ scope, previousReceipt, mode, version }) {
  const priorScope = previousReceipt?.scope;
  const requiresReinstall = Boolean(
    previousReceipt && (
      previousReceipt.package_version !== version ||
      previousReceipt.mode !== mode ||
      priorScope !== scope
    )
  );

  if (priorScope && priorScope !== scope) {
    try {
      run('claude', ['plugin', 'uninstall', QUALIFIED_PLUGIN, '--scope', priorScope, '--keep-data'], { passthrough: true });
    } catch (err) {
      warn(`Prior-scope uninstall did not complete cleanly: ${err.message}`);
    }
  } else if (requiresReinstall && pluginInstalled()) {
    run('claude', ['plugin', 'uninstall', QUALIFIED_PLUGIN, '--scope', scope, '--keep-data'], { passthrough: true });
  }

  if (!requiresReinstall && pluginInstalled()) {
    try {
      run('claude', ['plugin', 'update', QUALIFIED_PLUGIN, '--scope', scope], { passthrough: true });
      return 'updated';
    } catch (err) {
      warn(`Plugin update did not complete; reinstalling while preserving plugin data: ${err.message}`);
      run('claude', ['plugin', 'uninstall', QUALIFIED_PLUGIN, '--scope', scope, '--keep-data'], { passthrough: true });
    }
  }

  run('claude', ['plugin', 'install', QUALIFIED_PLUGIN, '--scope', scope], { passthrough: true });
  return 'installed';
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

function requireInventoryCount(details, label, expected) {
  const loaded = inventoryCount(details, label);
  if (loaded === null) {
    throw new Error(`Claude Code plugin details did not expose a machine-checkable ${label} count.`);
  }
  if (loaded !== expected) {
    throw new Error(`${label} inventory mismatch: expected ${expected}, loaded ${loaded}.`);
  }
  return loaded;
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

  const expected = expectedInventoryForMode(target, mode);
  const loaded = {
    skills: requireInventoryCount(details, 'Skills', expected.skills.expected_count),
    agents: requireInventoryCount(details, 'Agents', expected.agents.expected_count),
    hooks: requireInventoryCount(details, 'Hooks', expected.hooks.expected_count),
  };

  if (manifest.skills.length !== expected.skills.expected_count) {
    throw new Error(
      `Generated manifest/contract mismatch: manifest declares ${manifest.skills.length} skills; ` +
      `contract expects ${expected.skills.expected_count}.`,
    );
  }

  return {
    details,
    inventory: {
      skills: { ...expected.skills, loaded_count: loaded.skills },
      agents: { ...expected.agents, loaded_count: loaded.agents },
      hooks: { ...expected.hooks, loaded_count: loaded.hooks },
    },
  };
}

function writeReceipt({
  target,
  packageVersion,
  releaseIdentity,
  mode,
  scope,
  zoneRoot,
  managedPaths,
  verification,
  marketplaceAction,
  pluginAction,
  status,
}) {
  const receipt = {
    schema_version: 2,
    managed_by: MANAGED_BY,
    package: 'context-grapple-gun',
    package_version: packageVersion,
    release_version: releaseIdentity?.release_version || packageVersion,
    source_commit: releaseIdentity?.source_commit || null,
    plugin: QUALIFIED_PLUGIN,
    mode,
    scope,
    zone_root: zoneRoot,
    target,
    managed_paths: managedPaths,
    status,
    recorded_at: new Date().toISOString(),
  };
  if (marketplaceAction) receipt.marketplace_action = marketplaceAction;
  if (pluginAction) receipt.plugin_action = pluginAction;
  if (verification) {
    receipt.verification = {
      strict_validation: true,
      installed_record: true,
      details_sha256: sha256(verification.details),
      inventory: verification.inventory,
    };
  }
  writeJson(join(target, INSTALL_RECEIPT), receipt);
  return receipt;
}

function printDryRun({ mode, scope, target, zoneRoot, zoneActions }) {
  heading('CGG install plan (dry run)');
  log(`Mode: ${mode}`);
  log(`Plugin scope: ${scope}`);
  log(`Zone root: ${zoneRoot}`);
  if (mode === 'convention') {
    log(`Would append the governed convention to ${join(zoneRoot, 'CLAUDE.md')}`);
  } else {
    log(`Would materialize the package-pinned runtime at ${target}`);
    log(`Would copy ${mode === 'full' ? 'skills + admitted agents + hooks' : 'skills only; zero agents and zero hooks'}`);
    log('Would validate, register, install/update, and inspect the Claude Code plugin');
  }
  for (const action of zoneActions) info(`  ${action.replace('[create]', '[would create]')}`);
}

function printSummary({ mode, scope, target, zoneRoot, version, verification, zoneActions = [] }) {
  heading('Installation verified');
  log(`CGG package: ${version}`);
  log(`Mode: ${mode}`);
  if (mode !== 'convention') log(`Plugin scope: ${scope}`);
  log(`Zone root: ${zoneRoot}`);
  if (mode !== 'convention') log(`Pinned runtime: ${target}`);
  if (verification?.inventory) {
    const { skills, agents, hooks } = verification.inventory;
    log(`Loaded inventory: Skills(${skills.loaded_count}) Agents(${agents.loaded_count}) Hooks(${hooks.loaded_count})`);
  }
  for (const action of zoneActions) info(`  ${action}`);
  info('');
  if (mode !== 'convention') {
    info('Primary commands:');
    info('  /context-grapple-gun:cadence');
    info('  /context-grapple-gun:review');
    info('  /context-grapple-gun:siren');
    info('');
    info('Verify later with:');
    info(`  npx context-grapple-gun@${version} doctor --target "${target}"`);
    info('  # or, after a global npm install: cgg doctor');
  }
}

export function install(opts = {}) {
  const mode = opts.mode || 'full';
  const scope = opts.scope || 'user';
  const dryRun = Boolean(opts.dryRun);
  const cwd = resolve(opts.cwd || process.cwd());
  const packageRoot = resolve(opts.packageRoot || getPackageRoot());
  const version = opts.version || getVersion();
  const releaseIdentity = readReleaseIdentity(packageRoot, version);
  const zoneRoot = resolve(opts.zoneRoot || resolveZoneRoot(cwd));
  const target = resolve(cwd, opts.target || DEFAULT_TARGET);

  validateInstallOptions({ mode, scope });
  ensurePayload(packageRoot);

  const zoneActions = mode === 'convention'
    ? [applyConvention({ zoneRoot, packageRoot, dryRun: true }).action]
    : bootstrapGovernanceZone({ zoneRoot, packageRoot, dryRun: true });

  if (dryRun) {
    printDryRun({ mode, scope, target, zoneRoot, zoneActions });
    return { mode, scope, target, zoneRoot, dryRun: true, zoneActions };
  }

  if (mode === 'convention') {
    const action = applyConvention({ zoneRoot, packageRoot });
    printSummary({ mode, scope, target, zoneRoot, version, zoneActions: [action.action] });
    return { mode, scope, target: null, zoneRoot, version, status: 'verified' };
  }

  checkPrerequisites(mode);
  ensureSafeTarget(packageRoot, target);
  const marketplacePreflight = preflightMarketplace(target);

  heading('Materializing package-pinned CGG runtime...');
  const targetState = prepareTarget(target, false);
  const managedPaths = copyPayload(packageRoot, target, false, mode);
  const manifests = writeInstalledManifests({ packageRoot, target, mode, version, dryRun: false });
  if (materializeAgents({ packageRoot, target, mode, dryRun: false })) {
    managedPaths.push('agents');
  }
  makeRuntimeExecutable(target);
  writeReceipt({
    target,
    packageVersion: version,
    releaseIdentity,
    mode,
    scope,
    zoneRoot,
    managedPaths,
    status: 'prepared',
  });
  log(`${targetState.replacingManagedInstall ? 'Refreshed' : 'Created'} ${target}`);

  heading('Bootstrapping governance zone...');
  const appliedZoneActions = bootstrapGovernanceZone({ zoneRoot, packageRoot });
  mkdirSync(join(homedir(), '.claude', 'grapple-proposals'), { recursive: true });

  heading('Registering Claude Code plugin...');
  run('claude', ['plugin', 'validate', target, '--strict'], { passthrough: true });
  const marketplaceAction = configureMarketplace(target, marketplacePreflight);
  const pluginAction = installOrUpdatePlugin({
    scope,
    previousReceipt: targetState.previousReceipt,
    mode,
    version,
  });

  heading('Verifying exact loaded component inventory...');
  const verification = verifyPlugin({ target, mode, manifest: manifests.plugin });
  const receipt = writeReceipt({
    target,
    packageVersion: version,
    releaseIdentity,
    mode,
    scope,
    zoneRoot,
    managedPaths,
    verification,
    marketplaceAction,
    pluginAction,
    status: 'verified',
  });

  printSummary({
    mode,
    scope,
    target,
    zoneRoot,
    version,
    verification,
    zoneActions: appliedZoneActions,
  });
  return receipt;
}
