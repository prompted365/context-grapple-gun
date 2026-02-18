# CogPR — Cognitive Pull Request Conventions (Claude Desktop)

Add this to your Claude Desktop Project's custom instructions.

---

## Session Learning Protocol

When you discover something during a session that constitutes a durable lesson — a friction point resolved, a non-obvious behavior confirmed, a workflow correction, or an architectural insight — **capture it locally**.

### Capture Rules

1. **Write at your operational level.** Write the lesson to the nearest existing CLAUDE.md up the tree from where you're working. If working at project root, write to that file. If in a subsystem, write to that subsystem's CLAUDE.md. If no subsystem CLAUDE.md exists, write to MEMORY.md.

2. **Match the existing format.** Use the heading style, bullet format, and tone already present in the target file.

3. **Flag Cognitive Pull Requests (CPRs).** If the lesson might apply beyond the current file's scope, add a CPR flag immediately after the lesson:

```html
<!-- --agnostic-candidate
  lesson: "one-line lesson summary"
  source_date: "YYYY-MM-DD"
  recommended_scopes:
    - "path/to/broader/CLAUDE.md"
  rationale: "why this is broader than local"
  review_hints: "what to check when evaluating"
  status: "pending"
-->
```

Valid status values: `pending` | `promoted` | `rejected`.

4. **Protected files — NEVER touch autonomously:**
   - `~/.claude/CLAUDE.md` (global root)
   - Any file tagged `[GLOBAL_INVARIANT]`

### Reviewing CPR Flags

When the user says "review my CPR flags", "grapple", or "review pending lessons":

1. Search all CLAUDE.md and MEMORY.md files for `<!-- --agnostic-candidate -->` blocks with `status: "pending"`
2. For each pending CPR:
   - Read the lesson text and source context
   - Read each recommended target scope file
   - Check for overlap, conflict, or gaps
   - Assess: PROMOTE (write to target), SKIP (mark rejected), or MODIFY (adjust then promote)
3. Present your assessment and wait for approval before making any changes
4. For approved promotions:
   - Write the lesson to the target file in its existing format
   - Update the source CPR flag status to `promoted` or `rejected`
5. Never auto-promote — always get explicit approval first
