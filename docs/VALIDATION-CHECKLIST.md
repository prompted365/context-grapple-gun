# CGG Validation Checklist

Post-change QA runbook. Run these after modifying scan behavior, zone handling, install flow, skill definitions, or hook logic.

All commands assume you are at the CGG repo root (`vendor/context-grapple-gun/` or wherever the repo is checked out).

---

## Checks

### 1. CPR count accuracy (ticignore filtering)

Raw count should be >= filtered count. If equal, `.ticignore` isn't excluding anything (may be expected).

```bash
# Raw count (no exclusions)
RAW=$(grep -r "agnostic-candidate" . --include="*.md" | grep -c "pending")
# Filtered: exclude vendor/, node_modules/, .claude/skills/
FILTERED=$(grep -r "agnostic-candidate" . --include="*.md" \
  --exclude-dir=vendor --exclude-dir=node_modules --exclude-dir=.claude \
  | grep -c "pending")
echo "Raw: $RAW, Filtered: $FILTERED"
```

### 2. Install file copy matrix vs reality

Listed files in INSTALL.md must match actual `cgg-runtime/` contents.

```bash
echo "=== Hooks ==="
ls cgg-runtime/hooks/
echo "=== Agents ==="
ls cgg-runtime/agents/
echo "=== Primary Skills ==="
ls cgg-runtime/skills/cadence/ cgg-runtime/skills/review/ cgg-runtime/skills/siren/
echo "=== Deprecated Skills ==="
ls cgg-runtime/skills/cadence-downbeat/ cgg-runtime/skills/cadence-syncopate/ \
   cgg-runtime/skills/grapple/ cgg-runtime/skills/init-gun/ cgg-runtime/skills/init-cogpr/
```

Cross-reference output against INSTALL.md Mode A file list and [LOCKSTEP-INVARIANTS.md](LOCKSTEP-INVARIANTS.md) invariant #6.

### 3. Proposals path consistency

Every file referencing the proposals path must use the same value.

```bash
grep -rn "grapple-proposals" . --include="*.md" --include="*.sh"
```

Expected path everywhere: `~/.claude/grapple-proposals/latest.md`

### 4. `.ticignore` behavior

Create a test CPR block in an ignored directory, verify it is excluded from counts.

```bash
# In a project using CGG:
mkdir -p vendor/test-ignore
cat > vendor/test-ignore/CLAUDE.md << 'EOF'
<!-- --agnostic-candidate
  lesson: "test block"
  status: "pending"
-->
EOF
# Run the hook's count logic — this block should NOT be counted
# (vendor/ is in default exclusions)
# Clean up after:
rm -rf vendor/test-ignore
```

### 5. Deprecated skills are redirect-only

Each deprecated skill should contain only a redirect message. No duplicate logic.

```bash
for f in cgg-runtime/skills/cadence-downbeat/SKILL.md \
         cgg-runtime/skills/cadence-syncopate/SKILL.md \
         cgg-runtime/skills/grapple/SKILL.md \
         cgg-runtime/skills/init-gun/SKILL.md \
         cgg-runtime/skills/init-cogpr/SKILL.md; do
  LINES=$(wc -l < "$f")
  echo "$f: $LINES lines"
done
```

Redirect-only skills should be short (under 40 lines). If a deprecated skill has grown, it likely has duplicated logic.

### 6. Double-time description consistency

All 5 locations describing double-time semantics should say the same thing.

```bash
grep -rn "double-time\|syncopate" . --include="*.md" | grep -i "skip\|compact\|no signal\|no conformation"
```

Cross-reference against [LOCKSTEP-INVARIANTS.md](LOCKSTEP-INVARIANTS.md) invariant #5.

### 7. `.ticzone` format matches implementation

The JSONC format documented in README.md should match what `/siren conformation` actually reads.

```bash
# Check README documents these fields:
grep -A 10 "ticzone" README.md | head -15
# Compare with conformation code:
grep -A 5 "ticzone" cgg-runtime/skills/siren/SKILL.md
```

Expected fields: `name`, `tz`, `lat`, `lon`, `include`, `bands`, `muffling_per_hop`.

### 8. No external repo URL dependencies

Docs should not reference external repos as dependencies (attribution in maintainers section is fine).

```bash
grep -rn "github.com\|gitlab.com\|bitbucket.org" . --include="*.md" \
  | grep -v "LICENSE\|maintainer\|author\|CONTRIBUTING\|assets/"
```

Any hits outside attribution/license sections should be reviewed — CGG is standalone.

### 9. Shell hook syntax check

Both hooks must parse without errors.

```bash
bash -n cgg-runtime/hooks/cgg-gate.sh && echo "cgg-gate.sh: OK" || echo "cgg-gate.sh: FAIL"
bash -n cgg-runtime/hooks/session-restore-patch.sh && echo "session-restore-patch.sh: OK" || echo "session-restore-patch.sh: FAIL"
```

---

## Quick-Reference Matrix

When you change something in CGG, which checks apply?

| Change Area | Required Checks |
|-------------|----------------|
| Zone scan logic (find/glob targets) | 1, 4 |
| `.ticignore` handling | 1, 4 |
| Skill rename or deprecation | 2, 5 |
| Proposals path | 3 |
| Double-time behavior | 6 |
| `.ticzone` schema | 7 |
| Install bootstrap prompt | 2 |
| Hook shell logic | 9 |
| Any doc edit | 6, 8 |
| New skill added | 2, 5 |
