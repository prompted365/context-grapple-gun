# Commit History Navigation

CGG's live history is the Git commit graph. This page is a navigation aid, not an alternate source of truth.

## Current inspection commands

```bash
git log --oneline --decorate --graph --all
git log --first-parent --oneline main
git show --stat <sha>
git show <sha> -- <path>
git log -S'<exact term>' --all -- <path>
git log -G'<regex>' --all -- <path>
```

## Read a change lawfully

For any claim derived from history, retain:

1. the exact commit SHA;
2. the path and line or diff hunk;
3. whether the commit is on current `main`;
4. any later correction or superseding commit;
5. the current loaded/runtime state when behavior is the question.

A commit message is evidence of intended change. It is not proof that the installed or loaded runtime contains the change.

## Historical cheatsheet

The previous static cheatsheet is preserved under `deprecated-docs/docs/COMMIT-HISTORY-CHEATSHEET.md`. It is useful as historical context but is not maintained as current authority.
