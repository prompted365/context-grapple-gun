#!/usr/bin/env node

import { parseArgs } from '../lib/cli-args.mjs';
import { error, getVersion, info } from '../lib/utils.mjs';

const HELP = `
Context Grapple Gun — receipt-bearing governance continuity for Claude Code

Usage:
  cgg install [options]       Install or reconcile the package-pinned CGG runtime
  cgg doctor [options]        Verify package, plugin inventory, zone, and topology
  cgg sync [subcommand]       Compare/reconcile npm package and durable target
  cgg uninstall [options]     Remove plugin registration and npm-owned runtime files
  cgg --version               Print CLI package version
  cgg --help                  Show this help

Install options:
  --mode <mode>               full | skills | convention (default: full)
  --target <path>             Durable plugin source (default: vendor/context-grapple-gun)
  --scope <scope>             user | project | local (default: user)
  --dry-run                   Show the install plan without writing

Doctor options:
  --target <path>             Explicit npm-managed runtime target
  --topology-only             Run only the read-only topology diagnostic

Sync subcommands:
  check                       Compare running package to durable target (default)
  diff                        List missing, extra, or drifted npm-owned files
  sync                        Reconcile through the governed installer (never raw-copy to ~/.claude)

Uninstall options:
  --target <path>             Explicit npm-managed runtime target
  --scope <scope>             user | project | local (default: receipt, then user)
  --keep-files                Keep the durable npm runtime target
  --keep-data                 Preserve Claude plugin data when unregistering
  --remove-marketplace        Also remove marketplace cgg (explicit; may affect other scopes)

Examples:
  npx context-grapple-gun@5 install
  npx context-grapple-gun@5 install --mode skills --scope local
  npx context-grapple-gun@5 doctor
  cgg sync diff
`;

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
        dryRun: Boolean(flags['dry-run']),
      });
      break;
    }

    case 'doctor': {
      const { doctor } = await import('../lib/doctor.mjs');
      doctor({
        target: flags.target,
        topologyOnly: Boolean(flags['topology-only']),
      });
      break;
    }

    case 'sync': {
      const { sync } = await import('../lib/sync.mjs');
      await sync(positional[0] || 'check', { target: flags.target });
      break;
    }

    case 'uninstall': {
      const { uninstall } = await import('../lib/uninstaller.mjs');
      uninstall({
        target: flags.target,
        scope: flags.scope,
        keepFiles: Boolean(flags['keep-files']),
        keepData: Boolean(flags['keep-data']),
        removeMarketplace: Boolean(flags['remove-marketplace']),
      });
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
