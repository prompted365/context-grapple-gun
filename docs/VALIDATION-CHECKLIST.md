# CGG Validation Checklist

Post-change QA runbook. Run these after modifying scan behavior, zone handling, install flow, skill definitions, hook logic, or documentation.

All commands assume you are at the CGG repo root (`vendor/context-grapple-gun/` or wherever the repo is checked out).

---

## Presentation QA (First-Contact Clarity)

### P1. First-contact docs use only current command names

First-contact surfaces (README.md top section, START-HERE.md, INSTALL.md main paths) should use `/cadence`, `/review`, `/siren` — not deprecated names.

```bash
# Check for deprecated command names in first-contact surfaces
grep -n "cadence-downbeat\|cadence-syncopate\|/grapple\|/init-gun\|/init-cogpr" \
  README.md START-HERE.md INSTALL.md | grep -v "backward\|deprecated\|redirect"
```

Hits here (outside backward-compatibility sections) indicate presentation drift.

### P2. Core terms are aliased on first use

README.md should define core terms with neutral aliases near the top:

```bash
# Should find aliased definitions for these terms:
grep -n "CogPR\|tic-zone\|siren\|warrant\|conformation\|abstraction ladder" README.md | head -20
```

Check that each term has a neutral systems equivalent in parentheses or a table on first mention.

### P3. README top section answers core questions

Verify the README top section (before first Mermaid diagram) addresses:
- What CGG is
- What problem it solves
- The three commands
- The five mechanisms
- The lexical ceiling / scope boundary
- Read paths by intent

```bash
# Quick structural check — these sections should exist near the top
grep -n "## Read this first\|## 90-second\|## What CGG is not\|## Core terms\|## Skeptic\|## The lexical ceiling" README.md
```

### P4. Academy chapter names are consistent across surfaces

Three files must agree on chapter titles and sequence:

```bash
# Compare chapter tables
grep -A 5 "Taylor Family\|Adjunct\|Zookeeper\|Bridge Inspector\|Graduation" \
  academy/README.md academy/course.json cgg-runtime/skills/homeskillet-academy/SKILL.md
```

Any title drift between these files breaks the Academy's coherence.

### P5. Scope boundary is stated clearly and early

README and ARCHITECTURE should explain CGG's lexical ceiling without external doc dependencies:

```bash
# Check for scope boundary framing
grep -n "lexical ceiling\|out of scope\|scope boundary" README.md ARCHITECTURE.md
```

The boundary should be framed as a deliberate design decision, not a roadmap promise.

### P6. Links between doc ladder resolve

All cross-doc links should resolve:

```bash
# Check for broken markdown links
for f in README.md START-HERE.md INSTALL.md DEV-README.md ARCHITECTURE.md academy/README.md; do
  echo "=== $f ==="
  grep -oP '\[.*?\]\(\K[^)]+' "$f" | while read link; do
    if [[ "$link" != http* ]] && [[ ! -e "$link" ]] && [[ ! -e "${f%/*}/$link" ]]; then
      echo "  BROKEN: $link"
    fi
  done
done
```

### P7. Three-audience fidelity

Docs should preserve access for operators, technical evaluators, AND narrative-first learners:

```bash
# Academy should appear as legitimate entry path, not afterthought
grep -n "academy\|Academy\|story\|stories\|narrative" README.md START-HERE.md INSTALL.md
```

The Academy should be mentioned as a core onboarding path, not just technical reference.

---

## Checks

### 1. CogPR count accuracy (ticignore filtering)

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

Create a test CogPR block in an ignored directory, verify it is excluded from counts.

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
| Skill rename or deprecation | 2, 5, P1 |
| Proposals path | 3 |
| Double-time behavior | 6 |
| `.ticzone` schema | 7 |
| Install bootstrap prompt | 2, P1 |
| Hook shell logic | 9 |
| Any doc edit | 6, 8, P1-P7 |
| New skill added | 2, 5 |
| First-contact doc changes | P1, P2, P3, P5, P6 |
| Academy changes | P4, P7 |
| Terminology changes | P2, P4 |
