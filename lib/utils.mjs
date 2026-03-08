import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
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
 * On failure, throws with a clean message (no stack trace).
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
    const msg = err.stderr?.trim() || err.message;
    throw new Error(`Command failed: ${cmd}\n${msg}`);
  }
}

/**
 * Check whether a command exists in PATH.
 */
export function checkCommand(cmd) {
  try {
    execSync(`command -v ${cmd}`, { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
}

/**
 * Locate the CGG installation directory by searching common locations.
 * Accepts an optional explicit target path.
 */
export function findCggRoot(targetOverride) {
  const candidates = [
    targetOverride,
    join(process.cwd(), 'vendor', 'context-grapple-gun'),
    join(process.cwd(), '.claude', 'cgg'),
  ].filter(Boolean);

  for (const candidate of candidates) {
    const doctorPath = join(candidate, 'cgg-runtime', 'scripts', 'cgg-doctor.sh');
    if (existsSync(doctorPath)) {
      return candidate;
    }
  }
  return null;
}

/**
 * Read version from package.json.
 */
export function getVersion() {
  const pkgPath = join(dirname(fileURLToPath(import.meta.url)), '..', 'package.json');
  const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'));
  return pkg.version;
}
