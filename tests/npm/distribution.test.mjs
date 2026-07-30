import test from 'node:test';
import assert from 'node:assert/strict';
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import {
  FULL_SKILLS,
  SKILLS_ONLY,
  activatePreparedRuntime,
  appendConventionBlock,
  buildPluginManifest,
  ensureZoneSurfaces,
  install,
  resolveInstallTarget,
} from '../../lib/installer.mjs';
import { authorizeManagedTargetRemoval, removeConventionBlock } from '../../lib/uninstaller.mjs';

const baseManifest = {
  name: 'context-grapple-gun',
  version: '4.0.1',
  skills: ['old'],
  agents: ['./cgg-runtime/agents/mogul.md'],
  hooks: './hooks/hooks.json',
};

test('full manifest exposes curated runtime and excludes held Academy', () => {
  const manifest = buildPluginManifest('full', '5.0.0', baseManifest);
  assert.equal(manifest.version, '5.0.0');
  assert.deepEqual(manifest.skills, FULL_SKILLS);
  assert.equal(manifest.hooks, './hooks/hooks.json');
  assert.ok(manifest.agents.length > 0);
  assert.equal(manifest.skills.some((path) => path.includes('homeskillet-academy')), false);
});

test('skills mode has no hidden hook or agent sovereignty', () => {
  const manifest = buildPluginManifest('skills', '5.0.0', baseManifest);
  assert.deepEqual(manifest.skills, SKILLS_ONLY);
  assert.equal(Object.hasOwn(manifest, 'hooks'), false);
  assert.equal(Object.hasOwn(manifest, 'agents'), false);
});

test('zone bootstrap is idempotent and PRESTIGE remains blocked', () => {
  const zone = mkdtempSync(join(tmpdir(), 'cgg-zone-'));
  const first = ensureZoneSurfaces(zone);
  const second = ensureZoneSurfaces(zone);
  const config = JSON.parse(readFileSync(join(zone, '.ticzone'), 'utf-8'));

  assert.ok(first.length > 0);
  assert.equal(second.length, 0);
  assert.deepEqual(config.bands, ['PRIMITIVE', 'COGNITIVE', 'SOCIAL']);
  assert.equal(config.bands.includes('PRESTIGE'), false);
});

test('convention insertion and removal are marker-bounded and idempotent', () => {
  const zone = mkdtempSync(join(tmpdir(), 'cgg-convention-'));
  const source = mkdtempSync(join(tmpdir(), 'cgg-source-'));
  const protocol = '<!-- CGG:SESSION-LEARNING-PROTOCOL:START -->\n## Session Learning Protocol (CGG)\nbody\n<!-- CGG:SESSION-LEARNING-PROTOCOL:END -->\n';
  writeFileSync(join(source, 'SESSION_LEARNING_PROTOCOL.md'), protocol, 'utf-8');
  writeFileSync(join(zone, 'CLAUDE.md'), '# Existing\n\nUser content.\n', 'utf-8');

  assert.equal(appendConventionBlock(zone, { sourceRoot: source }).changed, true);
  assert.equal(appendConventionBlock(zone, { sourceRoot: source }).changed, false);
  const installed = readFileSync(join(zone, 'CLAUDE.md'), 'utf-8');
  assert.equal((installed.match(/CGG:SESSION-LEARNING-PROTOCOL:START/g) || []).length, 1);
  assert.ok(installed.includes('User content.'));

  assert.equal(removeConventionBlock(zone).changed, true);
  const removed = readFileSync(join(zone, 'CLAUDE.md'), 'utf-8');
  assert.ok(removed.includes('User content.'));
  assert.equal(removed.includes('CGG:SESSION-LEARNING-PROTOCOL:START'), false);
});

test('default managed targets follow runtime scope', () => {
  const zone = '/tmp/example-zone';
  assert.equal(resolveInstallTarget({ scope: 'project', zoneRoot: zone }), join(zone, '.claude', 'cgg'));
  assert.ok(resolveInstallTarget({ scope: 'user', zoneRoot: zone }).endsWith(join('.cgg', 'context-grapple-gun')));
});

test('uninstall removal authority preserves source checkouts and old receipts', () => {
  const packageCopy = mkdtempSync(join(tmpdir(), 'cgg-owned-'));
  const sourceCheckout = mkdtempSync(join(tmpdir(), 'cgg-checkout-'));
  mkdirSync(join(sourceCheckout, '.git'));

  assert.deepEqual(
    authorizeManagedTargetRemoval(packageCopy, {
      package: 'context-grapple-gun',
      managed_target: packageCopy,
      managed_target_kind: 'package_copy',
      removal_authorized: true,
    }),
    { authorized: true, reason: 'receipt-owned package copy' },
  );

  assert.equal(
    authorizeManagedTargetRemoval(sourceCheckout, {
      package: 'context-grapple-gun',
      managed_target: sourceCheckout,
      managed_target_kind: 'package_copy',
      removal_authorized: true,
    }).authorized,
    false,
  );

  assert.equal(
    authorizeManagedTargetRemoval(packageCopy, {
      package: 'context-grapple-gun',
      managed_target: packageCopy,
    }).authorized,
    false,
  );
});

test('atomic activation can restore the previous managed runtime', () => {
  const root = mkdtempSync(join(tmpdir(), 'cgg-atomic-'));
  const target = join(root, 'runtime');
  const candidate = join(root, 'candidate');
  mkdirSync(target, { recursive: true });
  mkdirSync(candidate, { recursive: true });
  writeFileSync(join(target, 'marker.txt'), 'old\n', 'utf-8');
  writeFileSync(join(candidate, 'marker.txt'), 'new\n', 'utf-8');

  const activation = activatePreparedRuntime({ target, candidate, inPlace: false });
  assert.equal(readFileSync(join(target, 'marker.txt'), 'utf-8'), 'new\n');
  activation.rollback();
  assert.equal(readFileSync(join(target, 'marker.txt'), 'utf-8'), 'old\n');
});

test('full install copies a versioned payload, bootstraps the zone, and verifies installed inventory', { skip: process.platform === 'win32' }, () => {
  const source = mkdtempSync(join(tmpdir(), 'cgg-package-'));
  const zone = mkdtempSync(join(tmpdir(), 'cgg-project-'));
  const target = join(zone, '.claude', 'cgg');
  const fakeBin = mkdtempSync(join(tmpdir(), 'cgg-bin-'));
  const logPath = join(fakeBin, 'claude.log');

  for (const path of [
    '.claude-plugin',
    'hooks',
    'cgg-runtime/hooks',
    'cgg-runtime/scripts',
    'cgg-runtime/agents',
  ]) mkdirSync(join(source, path), { recursive: true });
  for (const skill of FULL_SKILLS) mkdirSync(join(source, skill.replace(/^\.\//, '')), { recursive: true });

  const plugin = {
    name: 'context-grapple-gun',
    version: '5.0.0',
    skills: FULL_SKILLS,
    agents: ['./cgg-runtime/agents/mogul.md'],
    hooks: './hooks/hooks.json',
  };
  const marketplace = {
    name: 'cgg',
    plugins: [{ name: 'context-grapple-gun', source: './', version: '5.0.0', strict: true }],
  };
  writeFileSync(join(source, '.claude-plugin', 'plugin.json'), `${JSON.stringify(plugin, null, 2)}\n`);
  writeFileSync(join(source, '.claude-plugin', 'marketplace.json'), `${JSON.stringify(marketplace, null, 2)}\n`);
  writeFileSync(join(source, 'hooks', 'hooks.json'), '{"hooks":{"SessionStart":[]}}\n');
  writeFileSync(join(source, 'cgg-runtime', 'agents', 'mogul.md'), '# Mogul\n');
  writeFileSync(join(source, 'cgg-runtime', 'scripts', 'cgg-doctor.sh'), '#!/bin/sh\nexit 0\n');
  writeFileSync(join(source, 'cgg-runtime', 'hooks', 'boot.py'), '#!/usr/bin/env python3\n');
  for (const skill of FULL_SKILLS) writeFileSync(join(source, skill.replace(/^\.\//, ''), 'SKILL.md'), '---\nname: test\n---\n');
  writeFileSync(join(source, 'SESSION_LEARNING_PROTOCOL.md'), '<!-- CGG:SESSION-LEARNING-PROTOCOL:START -->\n## Session Learning Protocol (CGG)\nbody\n<!-- CGG:SESSION-LEARNING-PROTOCOL:END -->\n');
  for (const file of ['README.md', 'START-HERE.md', 'INSTALL.md', 'LICENSE']) writeFileSync(join(source, file), `${file}\n`);
  writeFileSync(join(source, 'package.json'), '{"name":"context-grapple-gun","version":"5.0.0"}\n');

  const fakeClaude = join(fakeBin, 'claude');
  writeFileSync(fakeClaude, `#!/bin/sh\necho "$(pwd)|$@" >> "$FAKE_CLAUDE_LOG"\ncase "$*" in\n  "--version") echo "2.1.63" ;;\n  "plugin marketplace list --json") echo "[]" ;;\n  "plugin list --json") echo '[{"name":"context-grapple-gun"}]' ;;\n  "plugin details context-grapple-gun@cgg") echo "context-grapple-gun" ;;\n  "plugin update context-grapple-gun@cgg --scope project") exit 1 ;;\n  *) exit 0 ;;\nesac\n`);
  chmodSync(fakeClaude, 0o755);

  const oldPath = process.env.PATH;
  const oldLog = process.env.FAKE_CLAUDE_LOG;
  const oldHome = process.env.HOME;
  process.env.PATH = `${fakeBin}:${oldPath}`;
  process.env.FAKE_CLAUDE_LOG = logPath;
  process.env.HOME = mkdtempSync(join(tmpdir(), 'cgg-home-'));
  try {
    const receipt = install({ mode: 'full', scope: 'project', projectDir: zone, target, sourceRoot: source });
    assert.equal(receipt.version, '5.0.0');
    assert.equal(receipt.mode, 'full');
    assert.equal(receipt.managed_target, target);
    assert.equal(receipt.managed_target_kind, 'package_copy');
    assert.equal(receipt.removal_authorized, true);
    assert.equal(receipt.installed_inventory_verified, true);
    assert.equal(receipt.session_load_state, 'reload_or_next_session_required');
    assert.deepEqual(JSON.parse(readFileSync(join(zone, '.ticzone'), 'utf-8')).bands, ['PRIMITIVE', 'COGNITIVE', 'SOCIAL']);
    assert.equal(JSON.parse(readFileSync(join(target, '.claude-plugin', 'marketplace.json'), 'utf-8')).plugins[0].strict, true);
    const commands = readFileSync(logPath, 'utf-8');
    assert.match(commands, /plugin validate/);
    assert.match(commands, /plugin marketplace add/);
    assert.match(commands, /plugin install/);
    assert.match(commands, /plugin details/);
    for (const line of commands.trim().split('\n')) assert.ok(line.startsWith(`${zone}|`));
  } finally {
    process.env.PATH = oldPath;
    if (oldLog === undefined) delete process.env.FAKE_CLAUDE_LOG;
    else process.env.FAKE_CLAUDE_LOG = oldLog;
    if (oldHome === undefined) delete process.env.HOME;
    else process.env.HOME = oldHome;
  }
});
