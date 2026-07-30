import { existsSync } from 'node:fs';
import { join } from 'node:path';
import {
  checkCommand,
  findCggRoot,
  findZoneRoot,
  getVersion,
  heading,
  info,
  readJson,
  run,
} from './utils.mjs';
import {
  FULL_SKILLS,
  PLUGIN_ID,
  PLUGIN_NAME,
  resolveInstallTarget,
} from './installer.mjs';

function checkPath(root, relative) {
  return existsSync(join(root, relative.replace(/^\.\//, '')));
}

function renderCheck(check) {
  const status = check.ok ? 'PASS' : check.required ? 'FAIL' : 'WARN';
  const marker = check.ok ? '✓' : check.required ? '✗' : '!';
  info(`  [${status}] ${marker} ${check.id}: ${check.detail}`);
}

export function inspectInstallation(opts = {}) {
  const scope = opts.scope || 'user';
  const zoneRoot = findZoneRoot(opts.projectDir || process.cwd());
  const expectedTarget = resolveInstallTarget({ scope, zoneRoot, target: opts.target });
  const root = findCggRoot(expectedTarget, { zoneRoot, projectDir: opts.projectDir });
  const checks = [];
  const add = (id, ok, detail, required = true) => checks.push({ id, ok: Boolean(ok), detail, required });

  add('managed runtime', Boolean(root), root || `not found at ${expectedTarget}`);
  if (!root) return { ok: false, scope, zoneRoot, target: expectedTarget, root: null, checks };

  const receiptPath = join(root, '.cgg-install.json');
  let receipt = null;
  if (existsSync(receiptPath)) {
    try {
      receipt = readJson(receiptPath);
      add('install receipt', receipt.package === PLUGIN_NAME, `${receipt.version || 'unknown'} / ${receipt.mode || 'unknown'} / ${receipt.scope || 'unknown'}`);
      add('receipt target', receipt.managed_target === root, receipt.managed_target || 'missing');
    } catch (err) {
      add('install receipt', false, err.message);
    }
  } else {
    add('install receipt', false, 'missing (manual/source-checkout install)', false);
  }

  const pluginPath = join(root, '.claude-plugin', 'plugin.json');
  const marketplacePath = join(root, '.claude-plugin', 'marketplace.json');
  add('plugin manifest', existsSync(pluginPath), pluginPath);
  add('marketplace manifest', existsSync(marketplacePath), marketplacePath);

  if (existsSync(pluginPath)) {
    try {
      const plugin = readJson(pluginPath);
      add('version identity', plugin.version === getVersion(), `plugin=${plugin.version || 'missing'} cli=${getVersion()}`);
      const skills = Array.isArray(plugin.skills) ? plugin.skills : plugin.skills ? [plugin.skills] : [];
      for (const required of FULL_SKILLS.slice(0, 3)) {
        add(`core skill ${required}`, skills.includes(required) && checkPath(root, required), required);
      }
      if (receipt?.mode === 'full' || !receipt) {
        add('full hook declaration', plugin.hooks === './hooks/hooks.json' && checkPath(root, './hooks/hooks.json'), plugin.hooks || 'missing');
        add('full agent declaration', Array.isArray(plugin.agents) && plugin.agents.length > 0, `${plugin.agents?.length || 0} agents`);
      }
      if (receipt?.mode === 'skills') {
        add('skills-only boundary', !plugin.hooks && !plugin.agents, 'no hooks or agents declared');
      }
    } catch (err) {
      add('plugin manifest parse', false, err.message);
    }
  }

  if (existsSync(marketplacePath)) {
    try {
      const marketplace = readJson(marketplacePath);
      const entry = marketplace.plugins?.find((item) => item.name === PLUGIN_NAME);
      add('strict marketplace authority', entry?.strict === true, `strict=${entry?.strict}`);
      add('marketplace version identity', entry?.version === getVersion(), `marketplace=${entry?.version || 'missing'} cli=${getVersion()}`);
      add('single component authority', !entry?.agents && !entry?.hooks && !entry?.skills, 'components live in plugin.json');
    } catch (err) {
      add('marketplace manifest parse', false, err.message);
    }
  }

  add('zone config', existsSync(join(zoneRoot, '.ticzone')), join(zoneRoot, '.ticzone'));
  add('zone exclusions', existsSync(join(zoneRoot, '.ticignore')), join(zoneRoot, '.ticignore'));
  add('audit root', existsSync(join(zoneRoot, 'audit-logs')), join(zoneRoot, 'audit-logs'));

  if (checkCommand('claude')) {
    const validated = run('claude', ['plugin', 'validate', root, '--strict'], { silent: true });
    add('Claude plugin validation', validated !== null, validated === null ? 'failed' : 'strict validation passed');
    const listing = run('claude', ['plugin', 'list', '--json'], { silent: true });
    add('loaded plugin inventory', Boolean(listing?.includes(PLUGIN_NAME)), listing ? PLUGIN_ID : 'plugin list unavailable');
    const details = run('claude', ['plugin', 'details', PLUGIN_ID], { silent: true });
    add('loaded component details', details !== null, details === null ? 'details unavailable' : 'loaded');
  } else {
    add('Claude CLI', false, 'claude command not found');
  }

  const ok = checks.every((check) => check.ok || !check.required);
  return { ok, scope, zoneRoot, target: expectedTarget, root, receipt, checks };
}

export function doctor(opts = {}) {
  const report = inspectInstallation(opts);

  if (opts.json) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    heading('CGG Doctor — distribution and topology');
    info(`  expected target: ${report.target}`);
    info(`  resolved root:   ${report.root || '(none)'}`);
    info(`  zone root:       ${report.zoneRoot}`);
    for (const check of report.checks) renderCheck(check);

    if (report.root && checkCommand('bash')) {
      const topology = join(report.root, 'cgg-runtime', 'scripts', 'cgg-doctor.sh');
      if (existsSync(topology)) {
        heading('Topology');
        run('bash', [topology], { cwd: report.zoneRoot, passthrough: true });
      }
    }
  }

  if (!report.ok) throw new Error('CGG doctor found blocking installation defects.');
  return report;
}
