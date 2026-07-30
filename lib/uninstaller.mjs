import {
  existsSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { join } from 'node:path';
import {
  checkCommand,
  findZoneRoot,
  heading,
  info,
  log,
  readJson,
  run,
  warn,
} from './utils.mjs';
import {
  MARKETPLACE_NAME,
  PLUGIN_ID,
  PLUGIN_NAME,
  resolveInstallTarget,
} from './installer.mjs';

const PROTOCOL_PATTERN = /\n?<!-- CGG:SESSION-LEARNING-PROTOCOL:START -->[\s\S]*?<!-- CGG:SESSION-LEARNING-PROTOCOL:END -->\n?/m;

export function removeConventionBlock(zoneRoot, opts = {}) {
  const path = join(zoneRoot, 'CLAUDE.md');
  if (!existsSync(path)) return { changed: false, path };
  const current = readFileSync(path, 'utf-8');
  if (!PROTOCOL_PATTERN.test(current)) return { changed: false, path };
  if (!opts.dryRun) {
    const next = current.replace(PROTOCOL_PATTERN, '\n').replace(/\n{3,}/g, '\n\n').trimEnd();
    writeFileSync(path, `${next}\n`, 'utf-8');
  }
  return { changed: true, path };
}

function removePluginRegistration(scope, dryRun) {
  if (!checkCommand('claude')) {
    warn('claude CLI not found; plugin and marketplace registration were not changed.');
    return;
  }

  if (dryRun) {
    info(`[would uninstall] ${PLUGIN_ID} --scope ${scope} --keep-data`);
    info(`[would remove marketplace] ${MARKETPLACE_NAME}`);
    return;
  }

  run('claude', ['plugin', 'uninstall', PLUGIN_ID, '--scope', scope, '--keep-data'], { silent: true });
  run('claude', ['plugin', 'marketplace', 'remove', MARKETPLACE_NAME], { silent: true });
}

export function uninstall(opts = {}) {
  const scope = opts.scope || 'user';
  if (!['user', 'project'].includes(scope)) {
    throw new Error(`Unknown uninstall scope: ${scope}. Use user or project.`);
  }

  const zoneRoot = findZoneRoot(opts.projectDir || process.cwd());
  const target = resolveInstallTarget({ scope, zoneRoot, target: opts.target });
  const dryRun = Boolean(opts.dryRun);
  const keepRuntime = Boolean(opts.keepRuntime);

  heading('CGG uninstall');
  info(`  scope ............ ${scope}`);
  info(`  zone root ........ ${zoneRoot}`);
  info(`  managed target ... ${target}`);
  info('  zone history ..... preserved');

  removePluginRegistration(scope, dryRun);

  if (!keepRuntime && existsSync(target)) {
    const receiptPath = join(target, '.cgg-install.json');
    if (!existsSync(receiptPath)) {
      warn(`Preserving ${target}: no CGG install receipt proves ownership.`);
    } else {
      const receipt = readJson(receiptPath);
      if (receipt.package !== PLUGIN_NAME || receipt.managed_target !== target) {
        warn(`Preserving ${target}: install receipt does not authorize removal.`);
      } else if (dryRun) {
        info(`[would remove managed runtime] ${target}`);
      } else {
        rmSync(target, { recursive: true, force: true });
        log(`Removed managed runtime ${target}`);
      }
    }
  } else if (keepRuntime) {
    info(`[kept managed runtime] ${target}`);
  }

  if (opts.removeConvention) {
    const result = removeConventionBlock(zoneRoot, { dryRun });
    info(`${dryRun && result.changed ? '[would remove]' : result.changed ? '[removed]' : '[not present]'} ${result.path}`);
  }

  info('Preserved: .ticzone, .ticignore, audit-logs/, MEMORY.md, and user-authored CLAUDE.md content.');
  return { scope, zoneRoot, target, dryRun, keepRuntime };
}
