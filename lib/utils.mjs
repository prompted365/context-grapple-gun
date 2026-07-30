import { execFileSync, execSync } from 'node:child_process';
import {
  existsSync,
  readFileSync,
  writeFileSync,
} from 'node:fs';
import { createHash } from 'node:crypto';
import { homedir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

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
 * Legacy shell execution helper retained for runtime-sync and topology scripts.
 * New distribution code should prefer run() so every argument remains typed.
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
 * Execute one program with a typed argument vector.
 */
export function run(command, args = [], opts = {}) {
  try {
    return execFileSync(command, args, {
      encoding: 'utf-8',
      stdio: opts.passthrough ? 'inherit' : ['ignore', 'pipe', 'pipe'],
      ...opts,
    });
  } catch (err) {
    if (opts.silent) return null;
    const stderr = err.stderr?.toString().trim();
    const stdout = err.stdout?.toString().trim();
    const detail = stderr || stdout || err.message;
    throw new Error(`Command failed: ${command} ${args.join(' ')}\n${detail}`);
  }
}

export function checkCommand(command) {
  const locator = process.platform === 'win32' ? 'where' : 'which';
  try {
    execFileSync(locator, [command], { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

export function getPackageRoot() {
  return resolve(dirname(fileURLToPath(import.meta.url)), '..');
}

export function getVersion() {
  const pkg = readJson(join(getPackageRoot(), 'package.json'));
  return pkg.version;
}

export function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf-8'));
}

export function writeJson(path, value) {
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, 'utf-8');
}

export function sha256(value) {
  const data = Buffer.isBuffer(value) ? value : Buffer.from(String(value));
  return createHash('sha256').update(data).digest('hex');
}

/**
 * Locate the durable npm-managed CGG source directory.
 */
export function findCggRoot(targetOverride, cwd = process.cwd()) {
  const candidates = [
    targetOverride,
    join(cwd, 'vendor', 'context-grapple-gun'),
    join(cwd, '.claude', 'cgg'),
    join(homedir(), '.cgg', 'context-grapple-gun'),
  ].filter(Boolean).map((candidate) => resolve(cwd, candidate));

  for (const candidate of candidates) {
    const doctorPath = join(candidate, 'cgg-runtime', 'scripts', 'cgg-doctor.sh');
    const manifestPath = join(candidate, '.claude-plugin', 'plugin.json');
    if (existsSync(doctorPath) && existsSync(manifestPath)) {
      return candidate;
    }
  }
  return null;
}
