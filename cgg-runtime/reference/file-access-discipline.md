# File-Access Discipline (Chunked Read Around Target)

**Federation-wide doctrinal-lane mandate (tic 208).** Applies to every CGG agent
that reads, audits, or mutates large governance files (CLAUDE.md, MEMORY.md,
queue.jsonl, audit-logs/**/*.jsonl, etc.).

Never read an entire CLAUDE.md, MEMORY.md, or other large governance file just
to find an insert/edit/audit target. Always:

1. **Get the file length first**: `wc -l <file>` (or `Read` with `limit: 1` and
   inspect size metadata) — establishes the bound before any window read.
2. **Locate the target region**: `grep -n` for the section header, the closest
   existing provenance comment, or the file-end marker. Capture the target line
   number.
3. **Read a chunk that surrounds the target**: use `Read` with `offset` and
   `limit` parameters to read only the window
   `[target_line - N, target_line + N]` (typical N=20). For append-at-end
   inserts, read the last ~30 lines via `offset: total_lines - 30`.
4. **Edit precisely within the chunk**: when mutating, use `Edit` with the
   narrow chunk's content as `old_string` so the match anchors against the
   local context, not the whole file.
5. **Never load the entire file into context** unless the file is genuinely
   small (<200 lines). Doctrinal-lane files (canonical/CLAUDE.md ~400 lines and
   growing; domain CLAUDE.md files 300-1000+ lines; MEMORY.md often >2000
   lines) require this discipline every single time, not just when the file is
   "large enough to notice."

## Rationale

Read-entire-file at every governance operation saturates context with material
irrelevant to the operation, displaces other governance state from window, and
inflates the agent's effective context cost on a per-operation basis. The
chunked-read mandate matches the operation's actual scope — appending or
modifying one bullet, reading one section, auditing one chain — to the file
access scope.

Originally inscribed at review-execute (tic 207); generalized to all
doctrinal-lane agents at tic 208; externalized to this reference doc at tic 221
to remove ~16x duplication across the agent corpus while preserving the
mandate's load-bearing presence.

## Lineage

- **Origin**: review-execute spec (tic 207) — model haiku could not fit
  queue.jsonl (~50KB, 435+ lines) and silently truncated reads, falling back
  to append-only behavior.
- **Generalization**: all 16 agents touching doctrinal-lane files (tic 208).
- **Externalization**: this reference doc (tic 221) replaces verbatim
  duplication in agent prompt bodies with a one-line pointer; the doctrine
  text is canonical here.

Agents reference this doc via:

```markdown
## File-Access Discipline

See `cgg-runtime/reference/file-access-discipline.md` — federation-wide
chunked-read mandate for doctrinal-lane files. Applies to every read or edit
of CLAUDE.md, MEMORY.md, queue.jsonl, and any audit-logs surface >200 lines.
```
