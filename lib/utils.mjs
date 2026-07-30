import { execSync, spawnSync } from 'node:child_process';
import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from 'node:fs';
import { createHash } from 'node:crypto';
import { homedir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// ANSI color codes
const RESET = '\x1b[0m';
const BOLD = '\x1b[1m';
const RED = '\x1b[31m';
const GREEN = '\x1b[32m';
const YELLOW = '\x1b[33m';
const CYAN = '\x1b[36m';
const DIM = '\x1b[2m';

export function log(msg) {
  console.log(`${GREEN}${BOLD}cgg${RESET} ${msg}`);
}

export function warn(msg) {
  console.log(`${YELLOW}${BOLD}cgg${RESET} ${YELLOW}${msg}${RESET}`);
}

export function error(msg) {
  console.error(`${RED}${BOLD}cgg${RESET} ${RED}${msg}${RESET}`);
}

export function info(msg) {
  console.log(`${DIM}${msg}${RESET}`);
}

export function heading(msg) {
  console.log(`\n${CYAN}${BOLD}${msg}${RESET}`);
}

/**
 * Execute a shell command, returning stdout as a string.
 * Kept for legacy callers that already provide trusted, internally-built
 * command strings. New distribution code should prefer run().
 */
export function exec(cmd, opts = {}) {
  try {
    return execSync(cmd, {
      encoding: 'utf-8',
      stdio: opts.passthrough ? 'inherit' : 'pipe',
      ...opts,
    });
  } catch (err) {
    if (opts.silent) return null;
    const msg = err.stderr?.toString().trim() || err.message;
    throw new Error(`Command failed: ${cmd}\n${msg}`);
  }
}

/**
 * Execute a command without invoking a shell.
 */
export function run(command, args = [], opts = {}) {
  const result = spawnSync(command, args, {
    encoding: 'utf-8',
    cwd: opts.cwd,
    env: opts.env || process.env,
    stdio: opts.passthrough ? 'inherit' : 'pipe',
  });

  if (result.error || result.status !== 0) {
    if (opts.silent) return null;
    const rendered = [command, ...args].join(' ');
    const detail = result.stderr?.trim() || result.stdout?.trim() || result.error?.message || `exit ${result.status}`;
    throw new Error(`Command failed: ${rendered}\n${detail}`);
  }

  return result.stdout || '';
}

export function checkCommand(cmd) {
  const locator = process.platform === 'win32' ? 'where' : 'which';
  const result = spawnSync(locator, [cmd], { stdio: 'ignore' });
  return !result.error && result.status === 0;
}

export function expandHome(input) {
  if (!input) return input;
  if (input === '~') return homedir();
  if (input.startsWith('~/') || input.startsWith('~\\')) {
    return join(homedir(), input.slice(2));
  }
  return input;
}

export function getPackageRoot() {
  return resolve(dirname(fileURLToPath(import.meta.url)), '..');
}

export function getVersion() {
  const pkgPath = join(getPackageRoot(), 'package.json');
  const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'));
  return pkg.version;
}

export function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf-8'));
}

export function writeJson(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, 'utf-8');
}

export function sha256File(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

/**
 * Resolve the governance zone root.
 * Authority order: nearest .ticzone -> git root -> supplied start directory.
 */
export function findZoneRoot(start = process.cwd()) {
  let cursor = resolve(expandHome(start));

  while (true) {
    if (existsSync(join(cursor, '.ticzone'))) return cursor;
    const parent = dirname(cursor);
    if (parent === cursor) break;
    cursor = parent;
  }

  if (checkCommand('git')) {
    const root = run('git', ['-C', resolve(expandHome(start)), 'rev-parse', '--show-toplevel'], { silent: true });
    if (root?.trim()) return resolve(root.trim());
  }

  return resolve(expandHome(start));
}

/**
 * Locate a CGG source/runtime root from explicit and supported managed paths.
 */
export function findCggRoot(targetOverride, opts = {}) {
  const zoneRoot = opts.zoneRoot || findZoneRoot(opts.projectDir || process.cwd());
  const candidates = [
    targetOverride,
    process.env.CGG_HOME,
    join(homedir(), '.cgg', 'context-grapple-gun'),
    join(zoneRoot, '.claude', 'cgg'),
    join(zoneRoot, 'vendor', 'context-grapple-gun'),
    join(process.cwd(), '.claude', 'cgg'),
    join(process.cwd(), 'vendor', 'context-grapple-gun'),
  ].filter(Boolean);

  for (const candidate of candidates) {
    const expanded = resolve(expandHome(candidate));
    const doctorPath = join(expanded, 'cgg-runtime', 'scripts', 'cgg-doctor.sh');
    const manifestPath = join(expanded, '.claude-plugin', 'plugin.json');
    if (existsSync(doctorPath) && existsSync(manifestPath)) return expanded;
  }

  return null;
}
