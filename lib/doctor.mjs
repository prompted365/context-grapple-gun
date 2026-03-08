import { join } from 'node:path';
import { existsSync } from 'node:fs';
import { exec, findCggRoot, log, error, info } from './utils.mjs';

/**
 * Run cgg-doctor.sh diagnostic from the CGG installation.
 */
export function doctor(opts = {}) {
  const root = findCggRoot(opts.target);

  if (!root) {
    error('CGG installation not found.');
    info('');
    info('Searched:');
    info('  ./vendor/context-grapple-gun');
    info('  ./.claude/cgg');
    if (opts.target) info(`  ${opts.target}`);
    info('');
    info('Run: cgg install');
    process.exit(1);
  }

  const scriptPath = join(root, 'cgg-runtime', 'scripts', 'cgg-doctor.sh');

  if (!existsSync(scriptPath)) {
    error(`Doctor script not found at ${scriptPath}`);
    info('Your CGG installation may be incomplete. Try: cgg install');
    process.exit(1);
  }

  log(`Running diagnostics from ${root}`);

  try {
    exec(`bash "${scriptPath}"`, { passthrough: true, cwd: root });
  } catch (err) {
    error(err.message);
    process.exit(1);
  }
}
