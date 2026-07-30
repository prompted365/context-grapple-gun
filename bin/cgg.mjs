#!/usr/bin/env node

import { getVersion, error, info } from '../lib/utils.mjs';

const HELP = `
Context Grapple Gun — authority-preserving continuity for Claude Code

Usage:
  cgg install [options]      Install a versioned CGG runtime and register the plugin
  cgg doctor [options]       Verify package, plugin, zone, and loaded-runtime state
  cgg sync [subcommand]      Runtime sync (check | diff | sync)
  cgg uninstall [options]    Remove managed runtime/plugin surfaces; preserve governance data
  cgg --version              Print version
  cgg --help                 Show this help

Install options:
  --mode <mode>              full | skills | convention (default: full)
  --scope <scope>            user | project (default: user)
  --target <path>            Override the managed runtime target
  --project-dir <path>       Project/zone discovery start (default: cwd)
  --dry-run                  Print the exact mutation plan without writing

Doctor options:
  --scope <scope>            user | project (default: user)
  --target <path>            Override the expected managed runtime target
  --project-dir <path>       Project/zone discovery start (default: cwd)
  --json                     Emit a machine-readable report

Uninstall options:
  --scope <scope>            user | project (default: user)
  --target <path>            Override the managed runtime target
  --project-dir <path>       Project/zone discovery start (default: cwd)
  --keep-runtime             Unregister the plugin but keep managed runtime bytes
  --remove-convention        Remove only the marker-bounded CGG protocol block
  --dry-run                  Print what would be removed

Examples:
  npx context-grapple-gun install
  cgg install --mode skills --scope project
  cgg install --mode convention
  cgg doctor
  cgg sync diff
  cgg uninstall --dry-run
`;

function parseArgs(argv) {
  const args = argv.slice(2);
  const command = args[0] && !args[0].startsWith('-') ? args[0] : null;
  const positional = [];
  const flags = {};

  for (let i = command ? 1 : 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--help' || arg === '-h') flags.help = true;
    else if (arg === '--version' || arg === '-v') flags.version = true;
    else if (arg.startsWith('--')) {
      const key = arg.slice(2);
      const next = args[i + 1];
      if (next && !next.startsWith('-')) {
        flags[key] = next;
        i++;
      } else flags[key] = true;
    } else positional.push(arg);
  }

  return { command, positional, flags };
}

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
        scope: flags.scope || 'user',
        projectDir: flags['project-dir'],
        dryRun: Boolean(flags['dry-run']),
      });
      break;
    }

    case 'doctor': {
      const { doctor } = await import('../lib/doctor.mjs');
      doctor({
        target: flags.target,
        scope: flags.scope || 'user',
        projectDir: flags['project-dir'],
        json: Boolean(flags.json),
      });
      break;
    }

    case 'sync': {
      const { sync } = await import('../lib/sync.mjs');
      sync(positional[0], { target: flags.target });
      break;
    }

    case 'uninstall': {
      const { uninstall } = await import('../lib/uninstaller.mjs');
      uninstall({
        target: flags.target,
        scope: flags.scope || 'user',
        projectDir: flags['project-dir'],
        dryRun: Boolean(flags['dry-run']),
        keepRuntime: Boolean(flags['keep-runtime']),
        removeConvention: Boolean(flags['remove-convention']),
      });
      break;
    }

    default:
      error(`Unknown command: ${command}`);
      info('Run: cgg --help');
      process.exitCode = 1;
  }
}

main().catch((err) => {
  error(err.message);
  process.exitCode = 1;
});
