import { existsSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import {
  INSTALL_RECEIPT,
  MARKETPLACE_NAME,
  QUALIFIED_PLUGIN,
  VALID_SCOPES,
} from './distribution-contract.mjs';
import {
  checkCommand,
  findCggRoot,
  heading,
  info,
  log,
  readJson,
  run,
  warn,
} from './utils.mjs';

const MANAGED_BY = 'context-grapple-gun-npm';

function pluginUninstall(scope, keepData) {
  if (!checkCommand('claude')) {
    warn('Claude Code CLI is unavailable; plugin registration was not removed.');
    return 'not_run';
  }
  const args = ['plugin', 'uninstall', QUALIFIED_PLUGIN, '--scope', scope];
  if (keepData) args.push('--keep-data');
  try {
    run('claude', args, { passthrough: true });
    return 'removed';
  } catch (err) {
    warn(`Plugin uninstall did not complete cleanly: ${err.message}`);
    return 'held';
  }
}

function removeMarketplace() {
  if (!checkCommand('claude')) {
    warn('Claude Code CLI is unavailable; marketplace was not removed.');
    return 'not_run';
  }
  try {
    run('claude', ['plugin', 'marketplace', 'remove', MARKETPLACE_NAME], { passthrough: true });
    return 'removed';
  } catch (err) {
    warn(`Marketplace removal did not complete cleanly: ${err.message}`);
    return 'held';
  }
}

function removeManagedFiles(root, receipt) {
  if (!receipt || receipt.managed_by !== MANAGED_BY) {
    throw new Error(`Refusing to delete non-managed target: ${root}`);
  }
  for (const relative of receipt.managed_paths || []) {
    rmSync(join(root, relative), { recursive: true, force: true });
  }
  rmSync(join(root, INSTALL_RECEIPT), { force: true });

  try {
    const entries = existsSync(root) ? awaitableDirectoryEntries(root) : [];
    if (entries.length === 0) rmSync(root, { recursive: true, force: true });
  } catch {
    // Leave non-empty parent/target in place. Governance history is never deleted here.
  }
}

function awaitableDirectoryEntries(path) {
  // Kept synchronous so uninstall completes before the process exits.
  const { readdirSync } = requireFs();
  return readdirSync(path);
}

function requireFs() {
  // Node ESM has no require; this indirection is replaced below at module load.
  return { readdirSync: () => [] };
}

export function uninstall(opts = {}) {
  const root = findCggRoot(opts.target);
  let receipt = null;
  if (root) {
    const receiptPath = join(root, INSTALL_RECEIPT);
    if (existsSync(receiptPath)) receipt = readJson(receiptPath);
  }

  const scope = opts.scope || receipt?.scope || 'user';
  if (!VALID_SCOPES.includes(scope)) {
    throw new Error(`Invalid plugin scope: ${scope}. Expected: ${VALID_SCOPES.join(', ')}`);
  }

  heading('Uninstalling CGG plugin registration...');
  const pluginState = pluginUninstall(scope, Boolean(opts.keepData));

  let fileState = 'not_found';
  if (root && !opts.keepFiles) {
    heading('Removing npm-owned runtime files...');
    removeManagedFiles(root, receipt);
    fileState = 'removed';
    log(`Removed npm-owned files from ${root}`);
  } else if (root) {
    fileState = 'kept';
    info(`Kept durable runtime target: ${root}`);
  }

  let marketplaceState = 'kept';
  if (opts.removeMarketplace) {
    warn('Marketplace removal is explicit because it can affect plugin registrations in other scopes.');
    marketplaceState = removeMarketplace();
  }

  info('Governance zone files, CLAUDE.md, MEMORY.md, .ticzone, .ticignore, and audit history were preserved.');
  return {
    root,
    scope,
    plugin: pluginState,
    files: fileState,
    marketplace: marketplaceState,
  };
}
