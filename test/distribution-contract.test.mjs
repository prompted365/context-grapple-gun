import assert from 'node:assert/strict';
import test from 'node:test';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, existsSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  buildPluginManifest,
  expectedInventoryForMode,
  loadComponentContract,
  payloadPathsForMode,
  skillPathsForMode,
} from '../lib/distribution-contract.mjs';
import {
  applyConvention,
  bootstrapGovernanceZone,
} from '../lib/zone.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

function read(path) {
  return JSON.parse(readFileSync(join(ROOT, path), 'utf-8'));
}

function markdownLinks(path) {
  const text = readFileSync(path, 'utf-8');
  return [...text.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)].map((match) => match[1]);
}

test('source plugin manifest is the single complete component authority', () => {
  const sourcePlugin = read('.claude-plugin/plugin.json');
  const marketplace = read('.claude-plugin/marketplace.json');
  const contract = loadComponentContract(ROOT);
  const pkg = read('package.json');

  assert.equal(sourcePlugin.version, pkg.version);
  assert.deepEqual([...sourcePlugin.skills].sort(), [...skillPathsForMode(contract, 'full')].sort());
  assert.equal(sourcePlugin.agents, undefined);
  assert.equal(sourcePlugin.hooks, undefined);
  const entry = marketplace.plugins.find((plugin) => plugin.name === sourcePlugin.name);
  assert.ok(entry);
  assert.equal(entry.source, './');
  assert.equal(entry.strict, undefined);
  assert.equal(entry.version, undefined);
  assert.equal(entry.skills, undefined);
  assert.equal(entry.agents, undefined);
  assert.equal(entry.hooks, undefined);
});

test('component contract references real source components', () => {
  const contract = loadComponentContract(ROOT);
  const allSkills = [
    ...contract.skill_sets.core,
    ...contract.skill_sets.compatibility,
    ...contract.skill_sets.full,
  ];
  for (const name of allSkills) {
    assert.ok(existsSync(join(ROOT, 'cgg-runtime', 'skills', name, 'SKILL.md')), name);
  }
  for (const relative of contract.agents.full) {
    assert.ok(existsSync(join(ROOT, relative.replace(/^\.\//, ''))), relative);
  }
  assert.ok(existsSync(join(ROOT, contract.hooks.full.replace(/^\.\//, ''))));
});

test('mode manifests have distinct, truthful skill surfaces', () => {
  const full = buildPluginManifest({ packageRoot: ROOT, mode: 'full', version: '5.0.0' });
  const skills = buildPluginManifest({ packageRoot: ROOT, mode: 'skills', version: '5.0.0' });

  assert.ok(full.skills.length > skills.skills.length);
  assert.equal(full.agents, undefined);
  assert.equal(full.hooks, undefined);
  assert.equal(skills.agents, undefined);
  assert.equal(skills.hooks, undefined);
  assert.ok(skills.skills.some((path) => path.includes('/cadence/')));
  assert.ok(skills.skills.some((path) => path.includes('/review/')));
  assert.ok(skills.skills.some((path) => path.includes('/siren/')));
});

test('mode payloads make skills a true zero-agent zero-hook install', () => {
  const full = payloadPathsForMode('full');
  const skills = payloadPathsForMode('skills');
  assert.ok(full.includes('hooks'));
  assert.equal(skills.includes('hooks'), false);
});

test('public inventory contract is exact for full and skills modes', () => {
  const full = expectedInventoryForMode(ROOT, 'full');
  const skills = expectedInventoryForMode(ROOT, 'skills');

  assert.deepEqual(
    [full.skills.expected_count, full.agents.expected_count, full.hooks.expected_count],
    [17, 11, 8],
  );
  assert.deepEqual(
    [skills.skills.expected_count, skills.agents.expected_count, skills.hooks.expected_count],
    [6, 0, 0],
  );
  assert.equal(full.skills.expected_ids.length, 17);
  assert.equal(full.agents.expected_ids.length, 11);
  assert.equal(full.hooks.expected_ids.length, 8);
});

test('npm package contains the deterministic runtime payload and one release identity', () => {
  const pkg = read('package.json');
  const lock = read('package-lock.json');
  const plugin = read('.claude-plugin/plugin.json');
  const release = read('release-status.json');

  assert.equal(pkg.version, '5.0.0');
  assert.equal(lock.version, pkg.version);
  assert.equal(lock.packages[''].version, pkg.version);
  assert.equal(plugin.version, pkg.version);
  assert.equal(release.version, pkg.version);
  assert.ok(['release-candidate', 'published'].includes(release.status));
  for (const required of ['.claude-plugin/', 'cgg-runtime/', 'hooks/', 'lib/', 'docs/', 'release-status.json']) {
    assert.ok(pkg.files.includes(required), required);
  }
  assert.equal(pkg.publishConfig.access, 'public');
  assert.equal(pkg.publishConfig.provenance, true);
  assert.ok(existsSync(join(ROOT, '.github', 'workflows', 'npm-release.yml')));
});

test('zone bootstrap is idempotent and never activates PRESTIGE', () => {
  const zoneRoot = mkdtempSync(join(tmpdir(), 'cgg-zone-'));
  const first = bootstrapGovernanceZone({ zoneRoot, packageRoot: ROOT });
  const second = bootstrapGovernanceZone({ zoneRoot, packageRoot: ROOT });
  const zone = JSON.parse(readFileSync(join(zoneRoot, '.ticzone'), 'utf-8'));
  const claude = readFileSync(join(zoneRoot, 'CLAUDE.md'), 'utf-8');

  assert.ok(first.some((entry) => entry.includes('[create] .ticzone')));
  assert.ok(second.some((entry) => entry.includes('[exists] .ticzone')));
  assert.equal(zone.bands.includes('PRESTIGE'), false);
  assert.equal((claude.match(/cgg-session-learning-protocol:v5/g) || []).length, 2);
});

test('zone bootstrap refuses PRESTIGE and competing legacy convention', () => {
  const prestigeRoot = mkdtempSync(join(tmpdir(), 'cgg-prestige-'));
  writeFileSync(join(prestigeRoot, '.ticzone'), JSON.stringify({ bands: ['COGNITIVE', 'PRESTIGE'] }), 'utf-8');
  assert.throws(
    () => bootstrapGovernanceZone({ zoneRoot: prestigeRoot, packageRoot: ROOT, dryRun: true }),
    /PRESTIGE/,
  );

  const legacyRoot = mkdtempSync(join(tmpdir(), 'cgg-legacy-protocol-'));
  writeFileSync(join(legacyRoot, 'CLAUDE.md'), '## Session Learning Protocol (CGG)\nlegacy\n', 'utf-8');
  assert.throws(
    () => bootstrapGovernanceZone({ zoneRoot: legacyRoot, packageRoot: ROOT, dryRun: true }),
    /competing protocol/,
  );
});

test('convention-only mode mutates only CLAUDE.md', () => {
  const zoneRoot = mkdtempSync(join(tmpdir(), 'cgg-convention-'));
  const result = applyConvention({ zoneRoot, packageRoot: ROOT });
  assert.equal(result.changed, true);
  assert.ok(existsSync(join(zoneRoot, 'CLAUDE.md')));
  assert.equal(existsSync(join(zoneRoot, '.ticzone')), false);
  assert.equal(existsSync(join(zoneRoot, 'audit-logs')), false);
});

test('CLI help exposes implemented modes, scopes, uninstall, and dry-run', () => {
  const output = execFileSync(process.execPath, [join(ROOT, 'bin', 'cgg.mjs'), '--help'], { encoding: 'utf-8' });
  for (const expected of ['full | skills | convention', 'user | project | local', '--dry-run', '--remove-marketplace']) {
    assert.match(output, new RegExp(expected.replace(/[|]/g, '\\|')));
  }
});

test('public Markdown routes resolve locally', () => {
  for (const relative of ['README.md', 'START-HERE.md', 'INSTALL.md']) {
    const path = join(ROOT, relative);
    for (const link of markdownLinks(path)) {
      if (/^(?:https?:|mailto:|#)/.test(link)) continue;
      const clean = link.split('#')[0];
      assert.ok(existsSync(resolve(dirname(path), clean)), `${relative} -> ${link}`);
    }
  }
});

test('direct Git is explicitly classified as non-equivalent to npm-managed full mode', () => {
  const install = readFileSync(join(ROOT, 'INSTALL.md'), 'utf-8');
  assert.match(install, /source-evaluation path/i);
  assert.match(install, /not equivalent to the npm-managed full install/i);
});

test('public sync lane is mode-aware, tracks materialized agents, and fails on drift', () => {
  const syncSource = readFileSync(join(ROOT, 'lib', 'sync.mjs'), 'utf-8');
  assert.doesNotMatch(syncSource, /runtime-sync\.py/);
  assert.match(syncSource, /payloadPathsForMode\(mode\)/);
  assert.match(syncSource, /agentPathsForMode\(contract, mode\)/);
  assert.match(syncSource, /if \(changed\.length\) process\.exitCode = 1;/);
  assert.match(syncSource, /governed reinstall/);
  assert.match(syncSource, /Refusing to downgrade/);
});

test('full hook authority includes the whole declared lifecycle', () => {
  const hooks = read('hooks/hooks.json').hooks;
  for (const event of ['SessionStart', 'SubagentStart', 'PreCompact', 'PostCompact', 'Stop', 'SessionEnd', 'UserPromptSubmit', 'PostToolUse']) {
    assert.ok(Array.isArray(hooks[event]) && hooks[event].length > 0, event);
  }
});

test('installer smoke executes the packed artifact and all plugin scopes', () => {
  const workflow = readFileSync(join(ROOT, '.github', 'workflows', 'installer-smoke.yml'), 'utf-8');
  assert.match(workflow, /npm pack --json/);
  for (const scope of ['user', 'project', 'local']) {
    assert.match(workflow, new RegExp(`--scope ${scope}`));
  }
  assert.match(workflow, /--mode skills/);
  assert.match(workflow, /--mode convention/);
  assert.match(workflow, /sync check/);
  assert.match(workflow, /expected sync check to fail/);
});

test('distribution CI gates runtime changes on a version advance', () => {
  const workflow = readFileSync(join(ROOT, '.github', 'workflows', 'distribution-contract.yml'), 'utf-8');
  assert.match(workflow, /Verify public runtime version advance/);
  assert.match(workflow, /BASE_VERSION/);
  assert.match(workflow, /CURRENT_VERSION/);
});

test('Academy is excluded pending its governed refresh', () => {
  const contract = loadComponentContract(ROOT);
  const academy = contract.excluded_skills.find((entry) => entry.name === 'homeskillet-academy');
  assert.ok(academy);
  assert.match(academy.reason, /issue #17/);
  assert.equal(skillPathsForMode(contract, 'full').some((path) => path.includes('homeskillet-academy')), false);
});

test('init-governance no longer activates PRESTIGE in its zone template', () => {
  const skill = readFileSync(join(ROOT, 'cgg-runtime', 'skills', 'init-governance', 'SKILL.md'), 'utf-8');
  assert.doesNotMatch(skill, /"bands": \["PRIMITIVE", "COGNITIVE", "SOCIAL", "PRESTIGE"\]/);
  assert.match(skill, /(?:governance-blocked.*PRESTIGE|PRESTIGE.*governance-blocked)/s);
});
