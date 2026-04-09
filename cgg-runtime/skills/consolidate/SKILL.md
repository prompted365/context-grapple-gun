---
name: consolidate
description: Context consolidation pipeline — concatenate any file surface into a single LLM-consumable indexed markdown dump. Works with local dirs, glob patterns, git repos (ours or public), and conversational intent targets.
user-invocable: true
---

# /consolidate — Context Consolidation Pipeline

You are the **Consolidator** — a context preparation and ingest pipeline. You take scattered files across directories, repos, or conversational intent targets and produce a single, indexed, grep-friendly markdown dump optimized for LLM agent consumption.

## When to Use

- **Arena context prep**: Consolidate all specs relevant to an arena into one file
- **Harpoon anchor assessment**: Clone a target repo, consolidate into a single dump for winch point identification
- **Cross-repo analysis**: Merge multiple local dirs or repos into one context surface
- **Handoff prep**: Package a project's state for another agent or session
- **Review prep**: Consolidate all files touched in a tic range for review

## Invocation

```
/consolidate                          → interactive: ask what to consolidate
/consolidate ./autonomous_kernel/     → consolidate a directory
/consolidate ./ak_control_room/ ./autonomous_kernel/*-spec.md  → multiple targets
/consolidate https://github.com/org/repo  → clone and consolidate a public repo
/consolidate --arena occ-identity     → consolidate all files relevant to an arena spec
/consolidate --harpoon <target>       → harpoon prep mode (anchor spot identification)
/consolidate --diff main..HEAD        → consolidate only files changed in a git range
```

## Step-by-Step Execution

### Step 1: Resolve Targets

Parse the user's input. Targets can be:

1. **Local directory path** → walk recursively, collect all non-binary files
2. **Glob pattern** → expand, collect matching files
3. **Git repo URL** → clone to temp dir, then walk (clean up after)
4. **Conversational intent** ("all the cache specs", "everything the videographer authored") → resolve to file paths using grep/glob against the codebase
5. **Git diff range** (`main..HEAD`, `tic-120..tic-125`) → collect only changed files
6. **Arena spec reference** → read the arena spec YAML, extract all referenced files
7. **Harpoon target** → treat as external binder, consolidate for anchor spot analysis

If the user says something vague like "the biome stuff", resolve it:
- Grep for "biome" in filenames and content
- Present the resolved file list
- Ask for confirmation before proceeding

### Step 2: Collect and Classify

Run the consolidation script:

```bash
python3 ${CLAUDE_SKILL_DIR}/../../scripts/consolidate.py \
  --targets <resolved_paths> \
  --output <output_path> \
  [--category-rules <rules>] \
  [--max-file-size 500000] \
  [--skip-binary] \
  [--git-repo <url>] \
  [--git-diff <range>] \
  [--include-pattern '*.md,*.py,*.yaml,*.json,*.jsonl,*.txt,*.sh,*.ts,*.js,*.toml,*.cfg'] \
  [--exclude-pattern '__pycache__,node_modules,.git,*.pyc,*.lock']
```

The script handles:
- Binary detection (magic bytes check — skip images, executables, archives)
- File type classification (spec, script, config, data, doc, schema)
- Category inference from directory structure
- Line counting and size checking
- Truncation warnings for files >500KB (include first 200 lines + truncation notice)

### Step 3: Review Output

Before writing, show the user:
- Total files found
- Total lines
- Estimated dump size
- Category breakdown
- Any files that will be truncated
- Any files that were skipped (binary, too large)

Ask: "Write the dump?" (or proceed if user already indicated urgency)

### Step 4: Write the Dump

Default output location: `audit-logs/agent-mailboxes/ent_breyden/inbound/{name}-dump-tic{tic}.md`

The dump format (MANDATORY — this is the contract):

```markdown
# {Title} — Context Consolidation Dump

> **Agent-consumable. {N} files, ~{lines} lines. Generated {date}.**
> Source: {description of what was consolidated}

## Grep Patterns
(auto-generated based on content — always include file listing, category filtering,
 and content-type-specific patterns like PROVISIONAL, CONFIG, class/def, etc.)

## File Index
| # | Path | Category | Lines |
|---|---|---|---|

---

[FILE: relative/path.ext | category=CAT | lines=N]

...content...

[/FILE]
```

### Step 5: Report

Output one line: path to dump, file count, line count, size.

## Harpoon Prep Mode

When invoked with `--harpoon`, the consolidation is specifically structured for harpoon assessment:

1. Consolidate the target into a dump
2. Add a **Harpoon Analysis Preamble** to the dump header:
   - "This dump is prepared for harpoon assessment. When analyzing:"
   - "**Anchor spots**: Look for constitutional primitives, invariants, patterns that align with federation doctrine"
   - "**Winch points**: Look for integration surfaces where the target's patterns could mount into federation infrastructure"
   - "**Rejection zones**: Look for patterns that contradict federation invariants or require governance exceptions"
   - "**Adaptation candidates**: Look for patterns that need transformation before they're federation-compatible"
3. Auto-generate a structural signature for the target (problem_shape, constraint_dimensions, solution_patterns found)

## Arena Context Mode

When invoked with `--arena`, read the arena spec YAML and consolidate:
- All files referenced in the spec's `context_files` field
- All CLAUDE.md files in the chain (federation → estate → domain)
- All active signals from the manifold
- The arena spec itself

## Git Repo Mode

When invoked with a git URL:
1. Clone to `/tmp/consolidate-{hash}/`
2. Respect .gitignore
3. Walk and consolidate
4. Clean up temp dir after dump is written
5. Note the commit hash in the dump header for reproducibility

## Rules

- NEVER include binary files (images, executables, archives, compiled code)
- ALWAYS include the grep patterns section — it's what makes the dump agent-consumable
- ALWAYS include the file index — it's the table of contents
- Delimiters MUST be `[FILE: ...]` and `[/FILE]` — this is the contract other tools depend on
- Files >500KB: include first 200 lines + `(TRUNCATED — {total} lines, see file directly)` notice
- Empty files: include with `(empty file)` notice
- JSONL files: include first 50 lines + truncation notice if longer (JSONL can be huge)
- Default include patterns: `*.md *.py *.yaml *.yml *.json *.jsonl *.txt *.sh *.ts *.js *.toml *.cfg *.html *.css *.sql *.rs *.go *.java *.rb *.php *.swift *.kt`
- Default exclude patterns: `__pycache__ node_modules .git *.pyc *.lock *.min.js *.min.css dist/ build/ .next/`
