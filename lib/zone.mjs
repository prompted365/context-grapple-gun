import {
  appendFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { checkCommand, run, writeJson } from './utils.mjs';

const PROTOCOL_MARKER = '<!-- cgg-session-learning-protocol:v5 -->';

export function resolveZoneRoot(startDir = process.cwd()) {
  const origin = resolve(startDir);
  let cursor = origin;
  while (true) {
    if (existsSync(join(cursor, '.ticzone'))) return cursor;
    const parent = dirname(cursor);
    if (parent === cursor) break;
    cursor = parent;
  }

  if (checkCommand('git')) {
    const gitRoot = run('git', ['-C', origin, 'rev-parse', '--show-toplevel'], { silent: true });
    if (gitRoot?.trim()) return resolve(gitRoot.trim());
  }
  return origin;
}

export function defaultTiczone(zoneRoot) {
  return {
    name: `${basename(zoneRoot)}-zone`,
    tz: 'UTC',
    include: ['.'],
    bands: ['PRIMITIVE', 'COGNITIVE', 'SOCIAL'],
    muffling_per_hop: 5,
    signal_governance: {
      hearing_threshold: 40,
      decay_rate_per_tic: 2,
      warrant_eligible_kinds: ['BEACON', 'TENSION'],
      primitive_audibility_mode: 'threshold_floor',
      zombie_guard_mode: 'clamp_and_warn',
    },
  };
}

export function defaultTicignore() {
  return `# Common build and dependency surfaces\nnode_modules/\ndist/\ntarget/\n.git/\n__pycache__/\n*.pyc\n\n# Vendor/upstream runtime is not the project's governance surface\nvendor/\n\n# Installed skill templates contain examples, not live CogPRs\n.claude/skills/\n\n# Stage artifacts are learning-eligible but do not emit tics/signals/warrants\nstage/\n`;
}

export function applyConvention({ zoneRoot, packageRoot, dryRun = false }) {
  const claudePath = join(zoneRoot, 'CLAUDE.md');
  const protocolPath = join(packageRoot, 'cgg-runtime', 'config', 'session-learning-protocol.md');
  const protocol = readFileSync(protocolPath, 'utf-8').trim();
  const existing = existsSync(claudePath) ? readFileSync(claudePath, 'utf-8') : '';

  if (existing.includes(PROTOCOL_MARKER)) {
    return { changed: false, path: claudePath, action: '[exists] convention block' };
  }
  if (!dryRun) {
    const prefix = existing.trim() ? '\n\n' : `# ${basename(zoneRoot)}\n\n`;
    appendFileSync(claudePath, `${prefix}${protocol}\n`, 'utf-8');
  }
  return { changed: true, path: claudePath, action: '[created] convention block' };
}

export function bootstrapGovernanceZone({
  zoneRoot,
  packageRoot,
  dryRun = false,
  includeConvention = true,
}) {
  const actions = [];
  const ticzonePath = join(zoneRoot, '.ticzone');
  const ticignorePath = join(zoneRoot, '.ticignore');

  if (!existsSync(ticzonePath)) {
    actions.push('[create] .ticzone');
    if (!dryRun) writeJson(ticzonePath, defaultTiczone(zoneRoot));
  } else {
    actions.push('[exists] .ticzone');
  }

  if (!existsSync(ticignorePath)) {
    actions.push('[create] .ticignore');
    if (!dryRun) writeFileSync(ticignorePath, defaultTicignore(), 'utf-8');
  } else {
    actions.push('[exists] .ticignore');
  }

  const auditDirs = [
    'audit-logs/tics',
    'audit-logs/signals',
    'audit-logs/cprs',
    'audit-logs/conformations',
    'audit-logs/economy',
    'audit-logs/provenance',
    'audit-logs/reviews',
  ];
  for (const relative of auditDirs) {
    const path = join(zoneRoot, relative);
    if (!existsSync(path)) {
      actions.push(`[create] ${relative}/`);
      if (!dryRun) mkdirSync(path, { recursive: true });
    } else {
      actions.push(`[exists] ${relative}/`);
    }
  }

  if (includeConvention) {
    const result = applyConvention({ zoneRoot, packageRoot, dryRun });
    actions.push(result.action);
  }

  return actions;
}
