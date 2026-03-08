import { existsSync, mkdirSync } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { exec, checkCommand, log, warn, error, info, heading } from './utils.mjs';

const REPO_URL = 'https://github.com/prompted365/context-grapple-gun.git';
const DEFAULT_TARGET = 'vendor/context-grapple-gun';
const MARKETPLACE_NAME = 'cgg';
const PLUGIN_NAME = 'context-grapple-gun';

/**
 * Verify that required tools are available.
 */
function checkPrerequisites() {
  heading('Checking prerequisites...');
  let ok = true;

  if (!checkCommand('git')) {
    error('git is not installed. Install it from https://git-scm.com');
    ok = false;
  } else {
    info('  git ............. found');
  }

  if (!checkCommand('claude')) {
    error('claude CLI is not installed. Install from https://claude.ai/code');
    ok = false;
  } else {
    const version = exec('claude --version', { silent: true })?.trim() || 'unknown';
    info(`  claude .......... ${version}`);
  }

  if (!checkCommand('python3')) {
    warn('python3 not found. Sync commands will be unavailable.');
  } else {
    info('  python3 ........ found');
  }

  if (!ok) {
    throw new Error('Missing required prerequisites. Install them and retry.');
  }
}

/**
 * Clone or update the CGG repository.
 */
function cloneRepo(target) {
  heading('Installing CGG runtime...');
  const absTarget = resolve(target);

  if (existsSync(join(absTarget, '.git'))) {
    log(`Updating existing installation at ${absTarget}`);
    exec(`git -C "${absTarget}" pull --ff-only`, { passthrough: true });
  } else {
    const parent = dirname(absTarget);
    if (!existsSync(parent)) {
      mkdirSync(parent, { recursive: true });
    }
    log(`Cloning to ${absTarget}`);
    exec(`git clone "${REPO_URL}" "${absTarget}"`, { passthrough: true });
  }

  return absTarget;
}

/**
 * Register CGG as a Claude Code plugin via its self-hosting marketplace.
 */
function pluginInstall(target, scope) {
  heading('Registering CGG plugin...');
  const absTarget = resolve(target);

  // Step 1: Add CGG's self-hosting marketplace
  log(`Adding marketplace from ${absTarget}`);
  try {
    exec(`claude plugin marketplace add "${absTarget}"`, { passthrough: true });
  } catch (e) {
    // Marketplace may already exist — try updating instead
    warn('Marketplace may already exist, attempting update...');
    try {
      exec(`claude plugin marketplace update ${MARKETPLACE_NAME}`, { passthrough: true });
    } catch {
      // Ignore update failures — marketplace might have just been added
    }
  }

  // Step 2: Install the plugin from the marketplace
  const scopeFlag = scope === 'user' ? '--scope user' : '--scope project';
  log(`Installing plugin: ${PLUGIN_NAME}@${MARKETPLACE_NAME} ${scopeFlag}`);
  exec(`claude plugin install ${PLUGIN_NAME}@${MARKETPLACE_NAME} ${scopeFlag}`, { passthrough: true });
}

/**
 * Print post-install summary.
 */
function printSummary(target, scope) {
  heading('Installation complete');
  log(`CGG installed at: ${resolve(target)}`);
  log(`Plugin scope: ${scope}`);
  info('');
  info('Next steps:');
  info('  cgg doctor          Run diagnostic checks');
  info('  cgg sync check      Check runtime sync status');
  info('');
  info('Primary commands (namespaced as /context-grapple-gun:*):');
  info('  /context-grapple-gun:cadence     — end of session');
  info('  /context-grapple-gun:review      — review proposed lessons');
  info('  /context-grapple-gun:siren       — check signal manifold');
  info('');
  info('CGG governance surfaces are now active in your Claude Code sessions.');
}

/**
 * Main install orchestration.
 */
export function install(opts = {}) {
  const target = opts.target || DEFAULT_TARGET;
  const scope = opts.scope || 'project';
  const mode = opts.mode || 'full';

  try {
    checkPrerequisites();

    if (mode === 'convention') {
      log('Convention-only mode: no clone needed. Add convention-block.md to your CLAUDE.md.');
      return;
    }

    const absTarget = cloneRepo(target);
    pluginInstall(absTarget, scope);
    printSummary(target, scope);
  } catch (err) {
    error(err.message);
    process.exit(1);
  }
}
