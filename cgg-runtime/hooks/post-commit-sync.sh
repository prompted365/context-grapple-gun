#!/usr/bin/env bash
# post-commit-sync.sh — CGG PostToolUse hook
#
# Fires after Bash tool invocations. Resolves whether a commit actually LANDED,
# and in WHICH repo, by observing the repo itself (reflog / HEAD), never by
# matching the tool command's text. If that commit touched CGG runtime files,
# materialises THAT COMMIT'S tree and syncs the installed runtime from it.
#
# Registered as: PostToolUse hook with matcher "Bash"
# Input: JSON on stdin with agent_id / agent_type. The tool command TEXT is not read
#        at all — reading it is the defect this hook was cured of.
# Output: stdout message (shown to user if non-empty)
#
# TIC-808 CURE (ruled /review 804 round 3, released /review 807 round 2):
#   1. resolves WHICH repo the commit landed in  — observe-the-repo, below
#   2. syncs only when THAT commit touched the runtime — diff-tree of THAT sha
#   3. syncs from the COMMITTED tree, never the working tree — git archive snapshot
#   4. recognises the `-C` form — by never reading the command text at all
# The defect cured: the old fast exit was a bare substring test for the two-word
# commit phrase over ANY agent's Bash command TEXT, and the runtime then synced
# the WORKING TREE against the CGG repo's own HEAD whichever repo (if any) was
# committed to. Witnessed live at tic 807: a sibling seat's command text, no
# commit anywhere, installed an uncommitted edit.
#   witness: audit-logs/governance/sync-hook-witnesses/post-commit-sync-hook-live-witness-tic807.txt
# DOES-NOT-SATISFY RIDER (travels verbatim): this ruling does NOT identify the command text that carried the substring, does NOT audit past syncs for unverified installs, does NOT change what the sync manifest covers, and does NOT touch any other hook's commit matching.

set -euo pipefail

# Read tool input from stdin
INPUT=$(cat)

# Wire cutter — emergency kill switch
[ -f ~/.claude/wire-cutter.sh ] && source ~/.claude/wire-cutter.sh && wire_check sync

# How recent a landed commit must be to belong to the tool call that just
# finished. A long-running command that commits early still lands inside it.
# Both error directions are benign: a stale window costs a missed auto-sync
# (the explicit sync still covers it); a generous window costs at most a
# redundant sync of the SAME committed bytes, which is idempotent.
COMMIT_WINDOW="${CGG_SYNC_COMMIT_WINDOW_SECONDS:-300}"

# Optional resolution trace — proves, per run, which roots this hook resolved.
# OFF by default; no output unless CGG_SYNC_HOOK_DEBUG is set to a non-empty value.
debug() {
    [ -n "${CGG_SYNC_HOOK_DEBUG:-}" ] && echo "[post-commit-sync:debug] $*"
    return 0
}

# ============================================================================
# Path resolution — use environment variables, not dirname "$0" relative paths.
# This hook is installed at ~/.claude/hooks/ which is OUTSIDE the plugin tree.
# dirname-relative navigation only works inside the plugin directory.
# ============================================================================

# Zone root: use CLAUDE_PROJECT_DIR, fall back to .ticzone walk
resolve_zone_root() {
    local dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
    while [ "$dir" != "/" ]; do
        [ -f "$dir/.ticzone" ] && echo "$dir" && return 0
        dir=$(dirname "$dir")
    done
    echo "${CLAUDE_PROJECT_DIR:-$(pwd)}"
}
ZONE_ROOT=$(resolve_zone_root)

# Plugin root: use CLAUDE_PLUGIN_ROOT, fall back to known locations
CGG_ROOT="${CLAUDE_PLUGIN_ROOT:-}"
if [ -z "$CGG_ROOT" ] || [ ! -d "$CGG_ROOT" ]; then
    for candidate in \
        "$ZONE_ROOT/vendor/context-grapple-gun" \
        "$ZONE_ROOT/canonical_developer/context-grapple-gun" \
        "$HOME/.claude/cgg"; do
        [ -d "$candidate" ] && CGG_ROOT="$candidate" && break
    done
fi

# ============================================================================
# FOLDER-SEED LEG (tic 812, Architect-directed in-session) — a SECOND repo of
# record, handled BEFORE the CGG resolution below can exit. The decision lives
# in that repo's own tool (tools/seed_sync.py update --from-hook): did a commit
# LAND there inside the window (its own reflog, never command text); read from
# the COMMITTED tree (git archive); applied ONLY to user-lane children whose own
# config says autoupdate: true. For every other child sync does not apply.
# Fast exit with no subprocess beyond stat: an untouched reflog means no commit.
# Fail-soft by construction: an absent repo or tool, a non-zero exit, or any
# error costs a missed seed update and nothing else. This leg never changes
# this hook's exit status and never touches the CGG leg below.
# DOES-NOT-SATISFY RIDER: this leg does NOT admit the folder seed, its terms or
# its soils as doctrine; it does NOT install a child (install is an explicit
# act in that tool); and it does NOT cure the root/merge-commit predicate gap.
# ============================================================================
SEED_REPO="$ZONE_ROOT/canonical_developer/folder-seed"
SEED_REFLOG="$SEED_REPO/.git/logs/HEAD"
if [ -f "$SEED_REFLOG" ] && [ -f "$SEED_REPO/tools/seed_sync.py" ]; then
    SEED_MTIME=$(stat -f %m "$SEED_REFLOG" 2>/dev/null || stat -c %Y "$SEED_REFLOG" 2>/dev/null || echo 0)
    if [ "$SEED_MTIME" -gt 0 ] && [ $(( $(date +%s) - SEED_MTIME )) -le "$COMMIT_WINDOW" ]; then
        SEED_OUT=$(FOLDER_SEED_SYNC_WINDOW_SECONDS="$COMMIT_WINDOW" python3 "$SEED_REPO/tools/seed_sync.py" update --from-hook 2>&1) \
            || debug "folder-seed leg returned non-zero"
        if [ -n "${SEED_OUT:-}" ]; then echo "[folder-seed sync] $SEED_OUT"; fi
    fi
fi

# ============================================================================
# WHICH REPO — resolved from the repos themselves, not from the command text.
#
# The runtime lives in exactly one repo of record:
#   - CGG carries its own .git  -> the CGG repo owns cgg-runtime/
#   - otherwise                 -> the federation repo owns
#                                  canonical_developer/context-grapple-gun/cgg-runtime/
# A commit in any OTHER repo is not this hook's business, and is now invisible
# to it: the repo of record's own HEAD is what gets probed.
# ============================================================================

COMMIT_REPO=""
RUNTIME_PREFIX=""        # path prefix of the runtime inside that repo
SNAPSHOT_SUBDIR=""       # where the plugin root sits inside the snapshot

if [ -n "$CGG_ROOT" ] && [ -e "$CGG_ROOT/.git" ]; then
    COMMIT_REPO="$CGG_ROOT"
    RUNTIME_PREFIX="cgg-runtime"
    SNAPSHOT_SUBDIR="."
elif [ -n "$ZONE_ROOT" ] && [ -e "$ZONE_ROOT/.git" ]; then
    COMMIT_REPO="$ZONE_ROOT"
    RUNTIME_PREFIX="canonical_developer/context-grapple-gun/cgg-runtime"
    SNAPSHOT_SUBDIR="canonical_developer/context-grapple-gun"
else
    debug "no repo of record (CGG_ROOT=$CGG_ROOT ZONE_ROOT=$ZONE_ROOT)"
    exit 0
fi

# ---------------------------------------------------------------------------
# Fast exit #1 (no subprocess): the repo of record's ref log has not been
# touched inside the window, so no ref moved, so no commit landed. Any commit
# appends to logs/HEAD, so this cannot skip one while reflogs are enabled.
# When logs/HEAD is absent (reflogs disabled) the filter is SKIPPED, not
# treated as a negative — the committer-date probe below still fires.
# ---------------------------------------------------------------------------
NOW=$(date +%s)
REFLOG_FILE=""
if [ -d "$COMMIT_REPO/.git" ]; then
    REFLOG_FILE="$COMMIT_REPO/.git/logs/HEAD"
else
    # worktree / submodule layout: .git is a file — ask git where the log lives
    REFLOG_FILE=$(git -C "$COMMIT_REPO" rev-parse --git-path logs/HEAD 2>/dev/null || true)
    case "$REFLOG_FILE" in
        /*) ;;
        "") ;;
        *) REFLOG_FILE="$COMMIT_REPO/$REFLOG_FILE" ;;
    esac
fi

if [ -n "$REFLOG_FILE" ] && [ -f "$REFLOG_FILE" ]; then
    REFLOG_MTIME=$(stat -f %m "$REFLOG_FILE" 2>/dev/null || stat -c %Y "$REFLOG_FILE" 2>/dev/null || echo 0)
    if [ "$REFLOG_MTIME" -gt 0 ] && [ $((NOW - REFLOG_MTIME)) -gt "$COMMIT_WINDOW" ]; then
        debug "no ref moved in ${COMMIT_WINDOW}s (repo=$COMMIT_REPO)"
        exit 0
    fi
fi

# ---------------------------------------------------------------------------
# DID A COMMIT LAND — the reflog is the git-native record of "HEAD moved, by
# WHICH action, WHEN". Only the actions `git commit` itself writes are accepted:
#   commit:  commit (amend):  commit (initial):  commit (merge):  commit (cherry-pick):
# DECLINED (named, not silently dropped): checkout:, reset:, merge <x>:, pull:,
# rebase*, clone: — they move HEAD without a commit being authored here.
# FALLBACK (documented conditional): a repo with reflogs disabled has no such
# record; the committer date of HEAD is used instead, which answers "was this
# commit created just now" without answering "by which action".
# ---------------------------------------------------------------------------
COMMIT_SHA=""
COMMIT_WHEN=""
LANDED_VIA=""

REFLOG_LINE=$(git -C "$COMMIT_REPO" log -g -1 --date=unix --format='%H%x09%gd%x09%gs' HEAD 2>/dev/null || true)
if [ -n "$REFLOG_LINE" ]; then
    RL_SHA="${REFLOG_LINE%%	*}"
    RL_REST="${REFLOG_LINE#*	}"
    RL_SELECTOR="${RL_REST%%	*}"
    RL_SUBJECT="${RL_REST#*	}"
    RL_STAMP="${RL_SELECTOR#*\{}"
    RL_STAMP="${RL_STAMP%\}}"
    RL_ACTION="${RL_SUBJECT%%:*}"
    case "$RL_ACTION" in
        commit|"commit ("*)
            COMMIT_SHA="$RL_SHA"
            COMMIT_WHEN="$RL_STAMP"
            LANDED_VIA="reflog:$RL_ACTION"
            ;;
        *)
            debug "last ref move was not a commit (action=$RL_ACTION repo=$COMMIT_REPO)"
            exit 0
            ;;
    esac
else
    FALLBACK_LINE=$(git -C "$COMMIT_REPO" log -1 --format='%H%x09%ct' HEAD 2>/dev/null || true)
    if [ -z "$FALLBACK_LINE" ]; then
        debug "no commit reachable in $COMMIT_REPO"
        exit 0
    fi
    COMMIT_SHA="${FALLBACK_LINE%%	*}"
    COMMIT_WHEN="${FALLBACK_LINE#*	}"
    LANDED_VIA="committer-date(no-reflog)"
fi

case "$COMMIT_WHEN" in
    ''|*[!0-9]*)
        debug "unreadable commit timestamp ($COMMIT_WHEN) — declining to sync"
        exit 0
        ;;
esac

if [ $((NOW - COMMIT_WHEN)) -gt "$COMMIT_WINDOW" ] || [ $((NOW - COMMIT_WHEN)) -lt -"$COMMIT_WINDOW" ]; then
    debug "commit $COMMIT_SHA is outside the ${COMMIT_WINDOW}s window (age $((NOW - COMMIT_WHEN))s)"
    exit 0
fi

# ---------------------------------------------------------------------------
# DID THAT COMMIT TOUCH THE RUNTIME — diff-tree of THAT sha, in THAT repo.
# (Not of the repo's current HEAD, and not of some other repo's HEAD.)
# ---------------------------------------------------------------------------
CHANGED_FILES=$(git -C "$COMMIT_REPO" diff-tree --no-commit-id --name-only -r "$COMMIT_SHA" 2>/dev/null || true)
if ! echo "$CHANGED_FILES" | grep -q "$RUNTIME_PREFIX/"; then
    debug "commit $COMMIT_SHA did not touch $RUNTIME_PREFIX/"
    exit 0
fi

# Scripts directory: plugin-root-anchored, then global install fallback
SCRIPT_DIR=""
for candidate in \
    "${CGG_ROOT:+$CGG_ROOT/cgg-runtime/scripts}" \
    "$HOME/.claude/cgg-runtime/scripts"; do
    [ -n "$candidate" ] && [ -d "$candidate" ] && SCRIPT_DIR="$candidate" && break
done

# Fast exit: no scripts directory found
[ -z "$SCRIPT_DIR" ] && exit 0

# ---------------------------------------------------------------------------
# THE COMMITTED TREE — materialised with `git archive`, which reads the object
# database and never the working tree, and writes nothing into the repo.
# The snapshot is what gets installed; uncommitted edits on disk cannot reach
# the installed runtime through this hook any more.
# ---------------------------------------------------------------------------
SNAPSHOT=$(mktemp -d "${TMPDIR:-/tmp}/cgg-sync-committed-XXXXXX")
cleanup_snapshot() { [ -n "${SNAPSHOT:-}" ] && rm -rf "$SNAPSHOT"; }
trap cleanup_snapshot EXIT

if ! git -C "$COMMIT_REPO" archive --format=tar "$COMMIT_SHA" -- "$RUNTIME_PREFIX" 2>/dev/null \
     | tar -x -C "$SNAPSHOT" 2>/dev/null; then
    echo "[post-commit-sync] could not materialise the committed tree for $COMMIT_SHA — no sync"
    exit 0
fi

SNAPSHOT_ROOT="$SNAPSHOT"
[ "$SNAPSHOT_SUBDIR" != "." ] && SNAPSHOT_ROOT="$SNAPSHOT/$SNAPSHOT_SUBDIR"
if [ ! -d "$SNAPSHOT_ROOT/cgg-runtime" ]; then
    echo "[post-commit-sync] committed tree for $COMMIT_SHA carries no cgg-runtime/ — no sync"
    exit 0
fi

# The snapshot carries the repo's HEAD IDENTITY (branch, or detached), mirrored
# into an identity-only gitdir: HEAD + the one ref, no object database and no
# link to the real repo. runtime-sync.py's branch-residence guard reads the
# resident branch from the plugin root it is given, so without this the
# snapshot would report "not a git repo" and the guard would pass by default —
# the non-main residence hazard (borns-tic673) would go dark behind this cure.
# The guard's DECISION stays in runtime-sync.py; this only carries the identity.
HEAD_BRANCH=$(git -C "$COMMIT_REPO" symbolic-ref --quiet --short HEAD 2>/dev/null || true)
mkdir -p "$SNAPSHOT_ROOT/.git/objects"
printf '[core]\n\trepositoryformatversion = 0\n\tbare = false\n' > "$SNAPSHOT_ROOT/.git/config"
if [ -n "$HEAD_BRANCH" ]; then
    mkdir -p "$SNAPSHOT_ROOT/.git/refs/heads/$(dirname "$HEAD_BRANCH")"
    printf 'ref: refs/heads/%s\n' "$HEAD_BRANCH" > "$SNAPSHOT_ROOT/.git/HEAD"
    printf '%s\n' "$COMMIT_SHA" > "$SNAPSHOT_ROOT/.git/refs/heads/$HEAD_BRANCH"
else
    mkdir -p "$SNAPSHOT_ROOT/.git/refs/heads"
    printf '%s\n' "$COMMIT_SHA" > "$SNAPSHOT_ROOT/.git/HEAD"
fi

debug "repo=$COMMIT_REPO sha=$COMMIT_SHA via=$LANDED_VIA branch=${HEAD_BRANCH:-DETACHED}"
debug "ZONE_ROOT=$ZONE_ROOT CGG_ROOT=$CGG_ROOT SCRIPT_DIR=$SCRIPT_DIR"
debug "SNAPSHOT_ROOT=$SNAPSHOT_ROOT HOME=$HOME INSTALL_ROOT=$HOME/.claude"

# Extract agent identity (Claude Code 2.1.69+) — threaded to runtime-sync.py
# via CLI args so the cgg-sync-log entry knows which agent context fired
# the underlying commit. Federation KI: bounded-delegation default
# masking — capture identity at the audit boundary. Both fields are optional
# in the payload and resolve to "" when the harness does not send them.
AGENT_IDENT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('agent_id') or '')
    print(data.get('agent_type') or '')
except Exception:
    print('')
    print('')
" 2>/dev/null || printf '\n\n')
AGENT_ID=$(echo "$AGENT_IDENT" | sed -n 1p)
AGENT_TYPE=$(echo "$AGENT_IDENT" | sed -n 2p)

# ============================================================================
# MANIFEST CHANGE DETECTION
# If sync-manifest.json was in this commit, the surface map itself changed.
# Both runtime-sync.py and posttool-sync-weigh.sh consume this file —
# flag it prominently so the installed copy gets updated.
# The installed copy is taken from the COMMITTED tree, same as every other
# surface — a working-tree manifest is exactly the class of bytes this cure
# keeps out of the installation.
# ============================================================================

MANIFEST_CHANGED=false
if echo "$CHANGED_FILES" | grep -q 'sync-manifest.json'; then
    MANIFEST_CHANGED=true
    echo "[post-commit-sync] sync-manifest.json CHANGED in this commit"
    echo "  The weigh manifest defines which files count toward runtime parity."
    echo "  Both runtime-sync.py and posttool-sync-weigh.sh read from it."
    echo "  Installed copy at ~/.claude/cgg-runtime/sync-manifest.json needs update."

    # Auto-sync the manifest itself, from the committed tree
    CANONICAL_MANIFEST="$SNAPSHOT_ROOT/cgg-runtime/sync-manifest.json"
    INSTALLED_MANIFEST="$HOME/.claude/cgg-runtime/sync-manifest.json"
    if [ -f "$CANONICAL_MANIFEST" ]; then
        mkdir -p "$(dirname "$INSTALLED_MANIFEST")"
        cp "$CANONICAL_MANIFEST" "$INSTALLED_MANIFEST"
        echo "  → manifest synced to installed location"
    fi
fi

# Run auto-sync against the COMMITTED tree. agent_id/agent_type passed through
# so write_sync_log can stamp them into the cgg-sync-log entry.
if [ -f "$SCRIPT_DIR/runtime-sync.py" ]; then
    RESULT=$(python3 "$SCRIPT_DIR/runtime-sync.py" auto-sync \
        --project-dir "$ZONE_ROOT" \
        --plugin-root "$SNAPSHOT_ROOT" \
        --commit "$COMMIT_SHA" \
        --agent-id "$AGENT_ID" \
        --agent-type "$AGENT_TYPE" 2>&1) || true
    if [ -n "$RESULT" ]; then
        echo "$RESULT"
    fi
fi

# ============================================================================
# CANONICAL PARENT AWARENESS
# If this commit is inside canonical_developer/ (a federation sub-estate),
# the parent canonical/ repo now has dirty state from this commit's sync
# effects. Flag it so the session knows to commit up.
# ============================================================================

if [ -n "$ZONE_ROOT" ] && [ -f "$ZONE_ROOT/.federation-root" ]; then
    # We're in the federation repo — check if canonical_developer changes
    # created drift that the parent should be aware of
    PARENT_DIRTY=$(cd "$ZONE_ROOT" && git status --porcelain canonical_developer/ 2>/dev/null | head -1)
    if [ -n "$PARENT_DIRTY" ]; then
        SURFACE_COUNT=$(cd "$ZONE_ROOT" && git status --porcelain canonical_developer/ 2>/dev/null | wc -l | tr -d ' ')
        echo "[post-commit-sync] canonical parent has ${SURFACE_COUNT} uncommitted change(s) from this commit's sync"
        if [ "$MANIFEST_CHANGED" = true ]; then
            echo "  ⚠ manifest changed — weighed surface definitions may have shifted"
        fi
    fi
fi
