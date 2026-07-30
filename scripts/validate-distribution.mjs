#!/usr/bin/env node

import { existsSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const failures = [];
const notes = [];

function fail(message) {
  failures.push(message);
}

function note(message) {
  notes.push(message);
}

function readJson(relative) {
  const path = join(root, relative);
  if (!existsSync(path)) {
    fail(`missing ${relative}`);
    return {};
  }
  try {
    return JSON.parse(readFileSync(path, 'utf-8'));
  } catch (err) {
    fail(`${relative} is not valid JSON: ${err.message}`);
    return {};
  }
}

function relativePathFromPluginPath(path) {
  return path.replace(/^\.\//, '').replace(/\/$/, '');
}

function validateComponentPath(path, type) {
  const relative = relativePathFromPluginPath(path);
  const absolute = join(root, relative);
  if (!existsSync(absolute)) {
    fail(`${type} path does not exist: ${path}`);
    return;
  }
  if (type === 'skill') {
    const skillFile = statSync(absolute).isDirectory() ? join(absolute, 'SKILL.md') : absolute;
    if (!existsSync(skillFile)) fail(`skill path has no SKILL.md: ${path}`);
  }
}

function validateMarkdownLinks(relative) {
  const path = join(root, relative);
  if (!existsSync(path)) return;
  const text = readFileSync(path, 'utf-8');
  const links = [...text.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)].map((match) => match[1]);
  for (const link of links) {
    if (/^(https?:|mailto:|#)/.test(link)) continue;
    const withoutAnchor = link.split('#')[0];
    if (!withoutAnchor) continue;
    const resolved = resolve(dirname(path), withoutAnchor);
    if (!existsSync(resolved)) fail(`${relative} contains broken local link: ${link}`);
  }
}

const pkg = readJson('package.json');
const lock = readJson('package-lock.json');
const plugin = readJson('.claude-plugin/plugin.json');
const marketplace = readJson('.claude-plugin/marketplace.json');
const hooks = readJson('hooks/hooks.json');
const entry = marketplace.plugins?.find((item) => item.name === 'context-grapple-gun');

const versions = [pkg.version, lock.version, plugin.version, entry?.version];
if (new Set(versions).size !== 1 || versions.some((value) => !value)) {
  fail(`version identity mismatch: package=${pkg.version} lock=${lock.version} plugin=${plugin.version} marketplace=${entry?.version}`);
}

if (entry?.strict !== true) fail('marketplace entry must set strict=true');
for (const field of ['skills', 'agents', 'hooks']) {
  if (entry && Object.hasOwn(entry, field)) fail(`marketplace entry must not declare ${field}; plugin.json is the single component authority`);
}
if (entry?.source !== './') fail('marketplace plugin source must be ./');

const packageFiles = new Set(pkg.files || []);
for (const required of ['bin/', 'lib/', '.claude-plugin/', 'hooks/', 'cgg-runtime/', 'SESSION_LEARNING_PROTOCOL.md']) {
  if (!packageFiles.has(required)) fail(`npm files[] does not include ${required}`);
}

if (!Array.isArray(plugin.skills) || plugin.skills.length < 3) fail('plugin.json must declare the curated skill set');
if (!Array.isArray(plugin.agents) || plugin.agents.length < 1) fail('plugin.json must declare the curated agent set');
if (plugin.hooks !== './hooks/hooks.json') fail('plugin.json hooks must point to ./hooks/hooks.json');

for (const path of plugin.skills || []) validateComponentPath(path, 'skill');
for (const path of plugin.agents || []) validateComponentPath(path, 'agent');
if (plugin.hooks) validateComponentPath(plugin.hooks, 'hooks');

if ((plugin.skills || []).some((path) => path.includes('homeskillet-academy'))) {
  fail('Homeskillet Academy is currentness-held under issue #13 and must remain outside the v5 public plugin manifest');
}
if ((plugin.skills || []).some((path) => path.includes('deprec_'))) {
  fail('deprecated skill trees must not be publicly admitted through plugin.json');
}
for (const held of ['homeskillet-academy', 'init-governance']) {
  if ((plugin.skills || []).some((path) => path.includes(held))) {
    fail(`${held} is currentness-held and must remain outside the v5 public plugin manifest`);
  }
}

for (const event of ['SessionStart', 'SubagentStart', 'PreCompact', 'PostCompact', 'Stop', 'SessionEnd', 'UserPromptSubmit', 'PostToolUse']) {
  if (!hooks.hooks?.[event]) fail(`hooks/hooks.json is missing lifecycle event ${event}`);
}

const protocol = join(root, 'SESSION_LEARNING_PROTOCOL.md');
if (!existsSync(protocol)) fail('missing SESSION_LEARNING_PROTOCOL.md');
else {
  const text = readFileSync(protocol, 'utf-8');
  if (!text.includes('CGG:SESSION-LEARNING-PROTOCOL:START') || !text.includes('CGG:SESSION-LEARNING-PROTOCOL:END')) {
    fail('SESSION_LEARNING_PROTOCOL.md must carry marker-bounded mutation authority');
  }
}

for (const doc of ['README.md', 'START-HERE.md', 'INSTALL.md']) validateMarkdownLinks(doc);

if (!pkg.scripts?.['test:distribution']) fail('package.json must expose test:distribution');
if (!pkg.scripts?.prepack) fail('package.json must validate before npm packing');

note(`validated CGG distribution ${pkg.version || '(unknown)'}`);
note(`${plugin.skills?.length || 0} skills, ${plugin.agents?.length || 0} agents, ${Object.keys(hooks.hooks || {}).length} hook events`);

for (const message of notes) console.log(`PASS ${message}`);
if (failures.length) {
  for (const message of failures) console.error(`FAIL ${message}`);
  process.exit(1);
}
console.log('PASS distribution contract admitted');
