import { join } from 'node:path';
import { existsSync } from 'node:fs';
import { exec, findCggRoot, checkCommand, log, error, info } from './utils.mjs';

const VALID_SUBCOMMANDS = ['check', 'diff', 'sync'];

/**
 * Run runtime-sync.py with the given subcommand.
 */
export function sync(subcommand, opts = {}) {
  if (!subcommand) subcommand = 'check';

  if (!VALID_SUBCOMMANDS.includes(subcommand)) {
    error(`Unknown sync subcommand: ${subcommand}`);
    info(`Valid subcommands: ${VALID_SUBCOMMANDS.join(', ')}`);
    process.exit(1);
  }

  if (!checkCommand('python3')) {
    error('python3 is required for sync commands.');
    info('Install Python 3 and retry.');
    process.exit(1);
  }

  const root = findCggRoot(opts.target);

  if (!root) {
    error('CGG installation not found.');
    info('Run: cgg install');
    process.exit(1);
  }

  const scriptPath = join(root, 'cgg-runtime', 'scripts', 'runtime-sync.py');

  if (!existsSync(scriptPath)) {
    error(`Sync script not found at ${scriptPath}`);
    info('Your CGG installation may be incomplete. Try: cgg install');
    process.exit(1);
  }

  log(`Running sync ${subcommand} from ${root}`);

  try {
    exec(`python3 "${scriptPath}" ${subcommand}`, { passthrough: true, cwd: root });
  } catch (err) {
    error(err.message);
    process.exit(1);
  }
}
