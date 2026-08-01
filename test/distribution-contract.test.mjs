import assert from 'node:assert/strict';
import test from 'node:test';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, existsSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  buildPluginManifest,
  expectedInventoryForMode,
  loadComponentContract,
  payloadPathsForMode,
  skillPathsForMode,
} from '../lib/distribution-contract.mjs';
import {
  applyConvention,
  bootstrapGovernanceZone,
} from '../lib/zone.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

function read(path) {
  return JSON.parse(readFileSync(join(ROOT, path), 'utf-8'));
}

let packedFileCache;
function packedFiles() {
  if (packedFileCache) return packedFileCache;
  const cache = mkdtempSync(join(tmpdir(), 'cgg-npm-pack-cache-'));
  const receipt = JSON.parse(execFileSync(
    'npm',
    ['--cache', cache, 'pack', '--dry-run', '--json'],
    { cwd: ROOT, encoding: 'utf-8' },
  ))[0];
  packedFileCache = new Set(receipt.files.map((file) => file.path));
  return packedFileCache;
}

function markdownLinks(path) {
  const text = readFileSync(path, 'utf-8');
  return [...text.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)].map((match) => match[1]);
}

function assertCheckoutCredentialsDisabled(workflow) {
  const lines = workflow.split('\n');
  const checkoutSteps = lines
    .map((line, index) => ({ line, index }))
    .filter(({ line }) => /^\s*- uses: actions\/checkout@/.test(line));
  assert.ok(checkoutSteps.length > 0);
  for (const { line, index } of checkoutSteps) {
    const indentation = line.indexOf('-');
    let end = lines.length;
    for (let candidate = index + 1; candidate < lines.length; candidate += 1) {
      if (lines[candidate].startsWith(`${' '.repeat(indentation)}- `)) {
        end = candidate;
        break;
      }
    }
    assert.match(
      lines.slice(index, end).join('\n'),
      /persist-credentials: false/,
      `checkout at line ${index + 1} must disable persisted credentials`,
    );
  }
}

test('source plugin manifest is the single complete component authority', () => {
  const sourcePlugin = read('.claude-plugin/plugin.json');
  const marketplace = read('.claude-plugin/marketplace.json');
  const contract = loadComponentContract(ROOT);
  const pkg = read('package.json');

  assert.equal(sourcePlugin.version, pkg.version);
  assert.deepEqual([...sourcePlugin.skills].sort(), [...skillPathsForMode(contract, 'full')].sort());
  assert.equal(sourcePlugin.agents, undefined);
  assert.equal(sourcePlugin.hooks, undefined);
  const entry = marketplace.plugins.find((plugin) => plugin.name === sourcePlugin.name);
  assert.ok(entry);
  assert.equal(entry.source, './');
  assert.equal(entry.strict, undefined);
  assert.equal(entry.version, undefined);
  assert.equal(entry.skills, undefined);
  assert.equal(entry.agents, undefined);
  assert.equal(entry.hooks, undefined);
});

test('component contract references real source components', () => {
  const contract = loadComponentContract(ROOT);
  const allSkills = [
    ...contract.skill_sets.core,
    ...contract.skill_sets.compatibility,
    ...contract.skill_sets.full,
  ];
  for (const name of allSkills) {
    assert.ok(existsSync(join(ROOT, 'cgg-runtime', 'skills', name, 'SKILL.md')), name);
  }
  for (const relative of contract.agents.full) {
    assert.ok(existsSync(join(ROOT, relative.replace(/^\.\//, ''))), relative);
  }
  assert.ok(existsSync(join(ROOT, contract.hooks.full.replace(/^\.\//, ''))));
});

test('mode manifests have distinct, truthful skill surfaces', () => {
  const full = buildPluginManifest({ packageRoot: ROOT, mode: 'full', version: '5.0.0' });
  const skills = buildPluginManifest({ packageRoot: ROOT, mode: 'skills', version: '5.0.0' });

  assert.ok(full.skills.length > skills.skills.length);
  assert.equal(full.agents, undefined);
  assert.equal(full.hooks, undefined);
  assert.equal(skills.agents, undefined);
  assert.equal(skills.hooks, undefined);
  assert.ok(skills.skills.some((path) => path.includes('/cadence/')));
  assert.ok(skills.skills.some((path) => path.includes('/review/')));
  assert.ok(skills.skills.some((path) => path.includes('/siren/')));
});

test('mode payloads make skills a true zero-agent zero-hook install', () => {
  const full = payloadPathsForMode('full');
  const skills = payloadPathsForMode('skills');
  assert.ok(full.includes('hooks'));
  assert.equal(skills.includes('hooks'), false);
});

test('public inventory contract is exact for full and skills modes', () => {
  const full = expectedInventoryForMode(ROOT, 'full');
  const skills = expectedInventoryForMode(ROOT, 'skills');

  assert.deepEqual(
    [full.skills.expected_count, full.agents.expected_count, full.hooks.expected_count],
    [17, 11, 8],
  );
  assert.deepEqual(
    [skills.skills.expected_count, skills.agents.expected_count, skills.hooks.expected_count],
    [6, 0, 0],
  );
  assert.equal(full.skills.expected_ids.length, 17);
  assert.equal(full.agents.expected_ids.length, 11);
  assert.equal(full.hooks.expected_ids.length, 8);
});

test('npm package contains the deterministic runtime payload and one release identity', () => {
  const pkg = read('package.json');
  const lock = read('package-lock.json');
  const plugin = read('.claude-plugin/plugin.json');
  const release = read('release-status.json');

  assert.equal(pkg.version, '5.0.0');
  assert.equal(lock.version, pkg.version);
  assert.equal(lock.packages[''].version, pkg.version);
  assert.equal(plugin.version, pkg.version);
  assert.equal(release.version, pkg.version);
  assert.ok(['release-candidate', 'published'].includes(release.status));
  for (const required of ['.claude-plugin/', 'cgg-runtime/', 'hooks/', 'lib/', 'docs/', 'release-status.json']) {
    assert.ok(pkg.files.includes(required), required);
  }
  assert.equal(pkg.publishConfig.access, 'public');
  assert.equal(pkg.publishConfig.provenance, true);
  assert.ok(existsSync(join(ROOT, '.github', 'workflows', 'npm-release.yml')));
  const runtimeNpmIgnore = readFileSync(join(ROOT, 'cgg-runtime', '.npmignore'), 'utf-8');
  assert.match(runtimeNpmIgnore, /__pycache__/);
  assert.match(runtimeNpmIgnore, /\*\.pyc/);
});

test('zone bootstrap is idempotent and never activates PRESTIGE', () => {
  const zoneRoot = mkdtempSync(join(tmpdir(), 'cgg-zone-'));
  const first = bootstrapGovernanceZone({ zoneRoot, packageRoot: ROOT });
  const second = bootstrapGovernanceZone({ zoneRoot, packageRoot: ROOT });
  const zone = JSON.parse(readFileSync(join(zoneRoot, '.ticzone'), 'utf-8'));
  const claude = readFileSync(join(zoneRoot, 'CLAUDE.md'), 'utf-8');

  assert.ok(first.some((entry) => entry.includes('[create] .ticzone')));
  assert.ok(second.some((entry) => entry.includes('[exists] .ticzone')));
  assert.equal(zone.bands.includes('PRESTIGE'), false);
  assert.equal((claude.match(/cgg-session-learning-protocol:v5/g) || []).length, 2);
});

test('zone bootstrap refuses PRESTIGE and competing legacy convention', () => {
  const prestigeRoot = mkdtempSync(join(tmpdir(), 'cgg-prestige-'));
  writeFileSync(join(prestigeRoot, '.ticzone'), JSON.stringify({ bands: ['COGNITIVE', 'PRESTIGE'] }), 'utf-8');
  assert.throws(
    () => bootstrapGovernanceZone({ zoneRoot: prestigeRoot, packageRoot: ROOT, dryRun: true }),
    /PRESTIGE/,
  );

  const legacyRoot = mkdtempSync(join(tmpdir(), 'cgg-legacy-protocol-'));
  writeFileSync(join(legacyRoot, 'CLAUDE.md'), '## Session Learning Protocol (CGG)\nlegacy\n', 'utf-8');
  assert.throws(
    () => bootstrapGovernanceZone({ zoneRoot: legacyRoot, packageRoot: ROOT, dryRun: true }),
    /competing protocol/,
  );
});

test('convention-only mode mutates only CLAUDE.md', () => {
  const zoneRoot = mkdtempSync(join(tmpdir(), 'cgg-convention-'));
  const result = applyConvention({ zoneRoot, packageRoot: ROOT });
  assert.equal(result.changed, true);
  assert.ok(existsSync(join(zoneRoot, 'CLAUDE.md')));
  assert.equal(existsSync(join(zoneRoot, '.ticzone')), false);
  assert.equal(existsSync(join(zoneRoot, 'audit-logs')), false);
});

test('CLI help exposes implemented modes, scopes, uninstall, and dry-run', () => {
  const output = execFileSync(process.execPath, [join(ROOT, 'bin', 'cgg.mjs'), '--help'], { encoding: 'utf-8' });
  for (const expected of ['full | skills | convention', 'user | project | local', '--dry-run', '--remove-marketplace']) {
    assert.match(output, new RegExp(expected.replace(/[|]/g, '\\|')));
  }
});

test('public Markdown routes resolve locally', () => {
  for (const relative of ['README.md', 'START-HERE.md', 'INSTALL.md']) {
    const path = join(ROOT, relative);
    for (const link of markdownLinks(path)) {
      if (/^(?:https?:|mailto:|#)/.test(link)) continue;
      const clean = link.split('#')[0];
      assert.ok(existsSync(resolve(dirname(path), clean)), `${relative} -> ${link}`);
    }
  }
});

test('direct Git is explicitly classified as non-equivalent to npm-managed full mode', () => {
  const install = readFileSync(join(ROOT, 'INSTALL.md'), 'utf-8');
  assert.match(install, /source-evaluation path/i);
  assert.match(install, /not equivalent to the npm-managed full install/i);
});

test('public sync lane is mode-aware, tracks materialized agents, and fails on drift', () => {
  const syncSource = readFileSync(join(ROOT, 'lib', 'sync.mjs'), 'utf-8');
  assert.doesNotMatch(syncSource, /runtime-sync\.py/);
  assert.match(syncSource, /payloadPathsForMode\(mode\)/);
  assert.match(syncSource, /agentPathsForMode\(contract, mode\)/);
  assert.match(syncSource, /if \(changed\.length\) process\.exitCode = 1;/);
  assert.match(syncSource, /governed reinstall/);
  assert.match(syncSource, /Refusing to downgrade/);
});

test('full hook authority includes the whole declared lifecycle', () => {
  const hooks = read('hooks/hooks.json').hooks;
  for (const event of ['SessionStart', 'SubagentStart', 'PreCompact', 'PostCompact', 'Stop', 'SessionEnd', 'UserPromptSubmit', 'PostToolUse']) {
    assert.ok(Array.isArray(hooks[event]) && hooks[event].length > 0, event);
  }
});

test('installer smoke executes the packed artifact and all plugin scopes', () => {
  const workflow = readFileSync(join(ROOT, '.github', 'workflows', 'installer-smoke.yml'), 'utf-8');
  assert.match(workflow, /'cgg-runtime\/\*\*'/);
  assertCheckoutCredentialsDisabled(workflow);
  assert.match(workflow, /npm pack --json/);
  for (const scope of ['user', 'project', 'local']) {
    assert.match(workflow, new RegExp(`--scope ${scope}`));
  }
  assert.match(workflow, /--mode skills/);
  assert.match(workflow, /--mode convention/);
  assert.match(workflow, /sync check/);
  assert.match(workflow, /expected sync check to fail/);
});

test('distribution CI freezes published runtime while allowing candidate completion', () => {
  const workflow = readFileSync(join(ROOT, '.github', 'workflows', 'distribution-contract.yml'), 'utf-8');
  assert.match(workflow, /'cgg-runtime\/\*\*'/);
  assert.match(workflow, /^\s+cgg-runtime \\$/m);
  for (const payload of ['assets', 'docs', 'README.md', 'package-lock.json']) {
    assert.match(workflow, new RegExp(`^\\s+${payload.replace('.', '\\.')}`, 'm'));
  }
  assert.match(workflow, /Verify published runtime immutability/);
  assert.match(workflow, /BASE_VERSION/);
  assert.match(workflow, /BASE_STATUS/);
  assert.match(workflow, /CURRENT_VERSION/);
  assert.match(workflow, /BASE_STATUS.*published/s);
  assertCheckoutCredentialsDisabled(workflow);
});

test('third-surface correction contract is packaged and wired to review plus hydration', () => {
  const packaged = packedFiles();
  for (const relative of [
    'cgg-runtime/contracts/record-correction-authorization-v1.schema.json',
    'cgg-runtime/contracts/record-correction-v1.schema.json',
    'cgg-runtime/migrations/record-correction-tic658.json',
    'cgg-runtime/scripts/effective-record.py',
    'cgg-runtime/scripts/lib/effective_record.py',
    'cgg-runtime/scripts/test_effective_record.py',
  ]) {
    assert.ok(existsSync(join(ROOT, relative)), relative);
    assert.ok(packaged.has(relative), `packed artifact missing ${relative}`);
  }
  assert.equal([...packaged].some((path) => /__pycache__|\.py[co]$|\.pytest_cache/.test(path)), false);
  const authorizationSchema = JSON.parse(readFileSync(
    join(ROOT, 'cgg-runtime/contracts/record-correction-authorization-v1.schema.json'),
    'utf-8',
  ));
  const migration = JSON.parse(readFileSync(
    join(ROOT, 'cgg-runtime/migrations/record-correction-tic658.json'),
    'utf-8',
  ));
  assert.ok(authorizationSchema.required.includes('canonical_append_surface'));
  assert.equal(
    migration.canonical_authorization_receipt.canonical_append_surface,
    migration.provenance.surface,
  );
  const review = readFileSync(join(ROOT, 'cgg-runtime/skills/review/SKILL.md'), 'utf-8');
  const session = readFileSync(join(ROOT, 'cgg-runtime/hooks/session-restore.sh'), 'utf-8');
  const hydration = readFileSync(join(ROOT, 'cgg-runtime/skills/tactical-hydration/SKILL.md'), 'utf-8');
  assert.match(review, /^python3 [^\n]*effective-record\.py[^\n]*review-gate$/m);
  assert.match(review, /check-index/);
  assert.match(session, /hydration-gate --format hook/);
  assert.match(session, /EFFECTIVE_RECORD_HYDRATION_BLOCKED/);
  assert.match(session, /EFFECTIVE_RECORD_RC" -eq 3.*EFFECTIVE_RECORD_HYDRATION_BLOCKED=1/s);
  assert.match(session, /HANDOFF_MSG=""[\s\S]*CGG_MSG="\$\{CGG_MSG:\+\$CGG_MSG \}\$HANDOFF_MSG"/);
  assert.match(session, /command -v python3/);
  assert.doesNotMatch(hydration, /There is no `rtch\.py` runner yet/);
  assert.match(hydration, /^\s*runner_script: [^\n]*rtch\.py[^\n]*operational[^\n]*$/m);
});

test('npm publication is tokenless OIDC and transitions status only after registry proof', () => {
  const workflow = readFileSync(join(ROOT, '.github', 'workflows', 'npm-release.yml'), 'utf-8');
  assert.match(workflow, /id-token: write/);
  assert.match(workflow, /environment: npm-publish/);
  assert.match(workflow, /npm@11\.5\.1/);
  assert.doesNotMatch(workflow, /npm@\^11\.5\.1/);
  assert.match(workflow, /publication-admission-commit/);
  assert.match(workflow, /issue #16 is/);
  assert.match(workflow, /author_association/);
  assert.match(workflow, /trustedAssociations/);
  assert.match(workflow, /--paginate --slurp/);
  assert.match(workflow, /single trusted issue comment/);
  assert.match(workflow, /Registry already carries the exact artifact; entering receipt-only recovery/);
  assert.match(workflow, /publication_needed=false/);
  assert.match(workflow, /E404/);
  assert.match(workflow, /refusing to classify the version as absent/);
  assert.doesNotMatch(workflow, /npm view[^\n]*\|\| true/);
  assert.match(workflow, /git rebase origin\/main/);
  assert.match(workflow, /git rebase --abort/);
  assert.match(workflow, /main advanced during receipt write; retrying/);
  assert.match(workflow, /Transient Python cache entered tarball/);
  assert.match(workflow, /npm audit signatures --json/);
  assert.match(workflow, /https:\/\/slsa\.dev\/provenance\/v1/);
  assert.match(workflow, /registry_attestations/);
  assert.match(workflow, /Release receipt surfaces disagree/);
  assert.match(workflow, /PACKED_PATHS/);
  assert.match(workflow, /ref: \$\{\{ inputs\.expected_commit \}\}/);
  assert.doesNotMatch(workflow, /npm publish[^\n]*inputs\.dist_tag/);
  assert.match(workflow, /DIST_TAG: \$\{\{ inputs\.dist_tag \}\}[\s\S]*npm publish "\$TARBALL" --tag "\$DIST_TAG"/);
  assert.doesNotMatch(workflow, /NPM_TOKEN/);
  const manifestStart = workflow.indexOf('Write exact source receipt into the package workspace');
  const manifestEnd = workflow.indexOf('Test distribution contract');
  assert.ok(manifestStart >= 0, 'candidate manifest step must exist');
  assert.ok(manifestEnd > manifestStart, 'distribution test must follow candidate manifest creation');
  const deterministicManifest = workflow.slice(manifestStart, manifestEnd);
  assert.doesNotMatch(deterministicManifest, /new Date/);
  assert.doesNotMatch(deterministicManifest, /workflow_run/);
  const publishAt = workflow.indexOf('npm publish');
  const verifyAt = workflow.indexOf('Verify registry receipt');
  const transitionAt = workflow.indexOf('Transition public release status after registry verification');
  assert.ok(publishAt >= 0 && publishAt < verifyAt && verifyAt < transitionAt);
});

test('Academy is excluded pending its governed refresh', () => {
  const contract = loadComponentContract(ROOT);
  const academy = contract.excluded_skills.find((entry) => entry.name === 'homeskillet-academy');
  assert.ok(academy);
  assert.match(academy.reason, /issue #17/);
  assert.equal(skillPathsForMode(contract, 'full').some((path) => path.includes('homeskillet-academy')), false);
});

test('init-governance no longer activates PRESTIGE in its zone template', () => {
  const skill = readFileSync(join(ROOT, 'cgg-runtime', 'skills', 'init-governance', 'SKILL.md'), 'utf-8');
  assert.doesNotMatch(skill, /"bands": \["PRIMITIVE", "COGNITIVE", "SOCIAL", "PRESTIGE"\]/);
  assert.match(skill, /(?:governance-blocked.*PRESTIGE|PRESTIGE.*governance-blocked)/s);
});
