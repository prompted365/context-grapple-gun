#!/usr/bin/env node

import { getVersion, error, info } from '../lib/utils.mjs';

const HELP = `
Context Grapple Gun — governed autonomy substrate for Claude Code

Usage:
  cgg install [options]    Clone CGG and register as Claude Code plugin
  cgg doctor [options]     Run diagnostic checks on CGG installation
  cgg sync [subcommand]    Runtime sync (check | diff | sync)
  cgg uninstall            Clean removal of CGG
  cgg --version            Print version
  cgg --help               Show this help

Install options:
  --mode <mode>            Install mode: full | skills | convention (default: full)
  --target <path>          Target directory (default: vendor/context-grapple-gun)
  --scope <scope>          Plugin scope: user | project (default: project)

Sync subcommands:
  check                    Check sync status (default)
  diff                     Show differences
  sync                     Synchronize runtime

Examples:
  npx context-grapple-gun install
  cgg install --scope user --target ~/.cgg
  cgg doctor
  cgg sync diff
`;

// --- Argument parsing (zero deps) ---

function parseArgs(argv) {
  const args = argv.slice(2);
  const command = args[0] && !args[0].startsWith('-') ? args[0] : null;
  const positional = [];
  const flags = {};

  for (let i = command ? 1 : 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--help' || arg === '-h') {
      flags.help = true;
    } else if (arg === '--version' || arg === '-v') {
      flags.version = true;
    } else if (arg.startsWith('--')) {
      const key = arg.slice(2);
      const next = args[i + 1];
      if (next && !next.startsWith('-')) {
        flags[key] = next;
        i++;
      } else {
        flags[key] = true;
      }
    } else {
      positional.push(arg);
    }
  }

  return { command, positional, flags };
}

// --- Main dispatch ---

async function main() {
  const { command, positional, flags } = parseArgs(process.argv);

  if (flags.version) {
    console.log(getVersion());
    return;
  }

  if (flags.help || !command) {
    console.log(HELP.trim());
    return;
  }

  switch (command) {
    case 'install': {
      const { install } = await import('../lib/installer.mjs');
      install({
        mode: flags.mode || 'full',
        target: flags.target,
        scope: flags.scope || 'project',
      });
      break;
    }

    case 'doctor': {
      const { doctor } = await import('../lib/doctor.mjs');
      doctor({ target: flags.target });
      break;
    }

    case 'sync': {
      const { sync } = await import('../lib/sync.mjs');
      sync(positional[0], { target: flags.target });
      break;
    }

    case 'uninstall': {
      error('Uninstall not yet wired. Run cgg-uninstall.py manually:');
      info('  python3 <cgg-root>/cgg-runtime/scripts/cgg-uninstall.py');
      process.exit(1);
      break;
    }

    default:
      error(`Unknown command: ${command}`);
      info('Run: cgg --help');
      process.exit(1);
  }
}

main().catch((err) => {
  error(err.message);
  process.exit(1);
});
