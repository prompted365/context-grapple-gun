import {
  existsSync,
  readdirSync,
  rmSync,
} from 'node:fs';
import { join, resolve } from 'node:path';
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

export function uninstall(opts = {}) {
  const cwd = resolve(opts.cwd || process.cwd());
  const root = findCggRoot(opts.target, cwd);
  const receiptPath = root ? join(root, INSTALL_RECEIPT) : null;
  const receipt = receiptPath && existsSync(receiptPath) ? readJson(receiptPath) : null;
  const scope = opts.scope || receipt?.scope || 'user';

  if (!VALID_SCOPES.includes(scope)) {
    throw new Error(`Invalid plugin scope: ${scope}. Expected: ${VALID_SCOPES.join(', ')}`);
  }

  heading('Removing CGG plugin registration...');
  if (checkCommand('claude')) {
    const args = ['plugin', 'uninstall', QUALIFIED_PLUGIN, '--scope', scope];
    if (opts.keepData) args.push('--keep-data');
    try {
      run('claude', args, { passthrough: true });
    } catch (err) {
      warn(`Plugin uninstall did not complete cleanly: ${err.message}`);
    }

    if (opts.removeMarketplace) {
      run('claude', ['plugin', 'marketplace', 'remove', MARKETPLACE_NAME], { passthrough: true });
    }
  } else {
    warn('Claude Code CLI is not available; plugin registration was not changed.');
  }

  if (opts.keepFiles) {
    info(`Pinned runtime retained at ${root || '(not found)'}.`);
  } else if (!root) {
    warn('No npm-managed CGG runtime target was found; no files were removed.');
  } else if (!receipt || receipt.managed_by !== MANAGED_BY) {
    warn(`Refusing to delete non-managed target: ${root}`);
  } else {
    heading('Removing npm-managed runtime payload...');
    for (const relative of receipt.managed_paths || []) {
      rmSync(join(root, relative), { recursive: true, force: true });
    }
    rmSync(receiptPath, { force: true });
    if (readdirSync(root).length === 0) rmSync(root, { recursive: true, force: true });
    log(`Removed npm-managed runtime from ${root}`);
  }

  info('');
  info('Project governance history was preserved: .ticzone, .ticignore, audit-logs/, and CLAUDE.md were not deleted.');
  if (!opts.removeMarketplace) {
    info(`Marketplace '${MARKETPLACE_NAME}' was retained. Add --remove-marketplace only when no other CGG scope depends on it.`);
  }
}
