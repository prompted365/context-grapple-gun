import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { readJson } from './utils.mjs';

export const PLUGIN_NAME = 'context-grapple-gun';
export const MARKETPLACE_NAME = 'cgg';
export const QUALIFIED_PLUGIN = `${PLUGIN_NAME}@${MARKETPLACE_NAME}`;
export const DEFAULT_TARGET = 'vendor/context-grapple-gun';
export const INSTALL_RECEIPT = 'cgg-install-receipt.json';
export const VALID_MODES = Object.freeze(['full', 'skills', 'convention']);
export const VALID_SCOPES = Object.freeze(['user', 'project', 'local']);

export const INSTALL_PAYLOAD = Object.freeze([
  '.claude-plugin',
  'assets',
  'bin',
  'cgg-runtime',
  'docs',
  'hooks',
  'lib',
  'ARCHITECTURE.md',
  'AUTHORING_CONVENTION.md',
  'CHANGELOG.md',
  'CGG_RUNTIME_TOPOLOGY_AND_LIFECYCLE.md',
  'DEV-README.md',
  'INSTALL.md',
  'LICENSE',
  'README.md',
  'START-HERE.md',
  'package.json',
]);

export function validateInstallOptions({ mode, scope }) {
  if (!VALID_MODES.includes(mode)) {
    throw new Error(`Invalid install mode: ${mode}. Expected one of: ${VALID_MODES.join(', ')}`);
  }
  if (!VALID_SCOPES.includes(scope)) {
    throw new Error(`Invalid plugin scope: ${scope}. Expected one of: ${VALID_SCOPES.join(', ')}`);
  }
}

export function loadComponentContract(packageRoot) {
  const path = join(packageRoot, 'cgg-runtime', 'config', 'plugin-components.json');
  const contract = readJson(path);
  if (contract.schema_version !== 1) {
    throw new Error(`Unsupported plugin component contract: ${contract.schema_version}`);
  }
  return contract;
}

export function skillNamesForMode(contract, mode) {
  if (mode === 'convention') return [];
  const names = [
    ...(contract.skill_sets.core || []),
    ...(contract.skill_sets.compatibility || []),
  ];
  if (mode === 'full') names.push(...(contract.skill_sets.full || []));
  return [...new Set(names)];
}

export function skillPathsForMode(contract, mode) {
  return skillNamesForMode(contract, mode).map(
    (name) => `./cgg-runtime/skills/${name}/`,
  );
}

export function assertComponentSources(packageRoot, contract, mode) {
  const missing = [];
  for (const name of skillNamesForMode(contract, mode)) {
    const path = join(packageRoot, 'cgg-runtime', 'skills', name, 'SKILL.md');
    if (!existsSync(path)) missing.push(`skill:${name}`);
  }
  if (mode === 'full') {
    const agentPath = join(packageRoot, contract.agents.full.replace(/^\.\//, ''));
    const hookPath = join(packageRoot, contract.hooks.full.replace(/^\.\//, ''));
    if (!existsSync(agentPath)) missing.push(`agents:${contract.agents.full}`);
    if (!existsSync(hookPath)) missing.push(`hooks:${contract.hooks.full}`);
  }
  if (missing.length) {
    throw new Error(`Distribution contract references missing components: ${missing.join(', ')}`);
  }
}

export function buildPluginManifest({ packageRoot, mode, version }) {
  const contract = loadComponentContract(packageRoot);
  assertComponentSources(packageRoot, contract, mode);

  const manifest = {
    $schema: 'https://json.schemastore.org/claude-code-plugin-manifest.json',
    name: PLUGIN_NAME,
    displayName: 'Context Grapple Gun',
    version,
    description: 'Portable governance lifecycle for Claude Code. Captures lessons as CogPRs, preserves session continuity, routes proposals through human-gated review, and tracks recurring friction through the signal manifold.',
    author: {
      name: 'Prompted LLC',
      email: 'breyden@prompted.community',
    },
    repository: 'https://github.com/prompted365/context-grapple-gun',
    homepage: 'https://github.com/prompted365/context-grapple-gun#readme',
    license: 'MIT',
    keywords: ['governance', 'learning', 'autonomy', 'cogpr', 'signals'],
    skills: skillPathsForMode(contract, mode),
  };

  if (mode === 'full') {
    manifest.agents = contract.agents.full;
    manifest.hooks = contract.hooks.full;
  }

  return manifest;
}

export function buildMarketplaceManifest() {
  return {
    name: MARKETPLACE_NAME,
    owner: {
      name: 'Prompted LLC',
      email: 'breyden@prompted.community',
    },
    metadata: {
      description: 'Context Grapple Gun — file-based governance lifecycle for persistent AI sessions',
    },
    plugins: [
      {
        name: PLUGIN_NAME,
        source: './',
        description: 'Portable governance lifecycle for Claude Code: CogPR capture, scoped promotion, signal routing, and receipt-bearing continuity.',
      },
    ],
  };
}
