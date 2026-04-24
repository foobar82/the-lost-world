#!/usr/bin/env bash
# scripts/rollback.sh — roll back the most recent pipeline release.
#
# Usage:
#   bash scripts/rollback.sh            # interactive (shows diff, asks confirmation)
#   bash scripts/rollback.sh --yes      # skip confirmation prompt
#   bash scripts/rollback.sh --dry-run  # preview what would be done, no changes
#
# What it does:
#   1. Finds the most recent "Merge agent/..." commit on the current branch.
#   2. Shows the commit info and files that would be reverted.
#   3. (Unless --dry-run) asks for confirmation.
#   4. Creates a revert commit with:  git revert -m 1 <hash>
#   5. Resets matching feedback rows from 'done' → 'pending' in SQLite.
#   6. Re-runs scripts/deploy.sh to rebuild the frontend and restart the server.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ── parse arguments ────────────────────────────────────────────────────────
DRY_RUN=false
YES=false

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --yes|-y)  YES=true ;;
        --help|-h)
            sed -n '2,13p' "$0" | sed 's/^# *//'
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            echo "Usage: bash scripts/rollback.sh [--dry-run] [--yes]" >&2
            exit 1
            ;;
    esac
done

# ── find the most recent agent merge commit ────────────────────────────────
MERGE_COMMIT=$(
    git -C "$REPO_ROOT" log \
        --merges \
        --format="%H %s" \
    | grep ' Merge agent/' \
    | head -1 \
    | awk '{print $1}'
)

if [ -z "$MERGE_COMMIT" ]; then
    echo "error: no agent merge commits found on this branch." >&2
    exit 1
fi

COMMIT_MSG=$(git -C "$REPO_ROOT" log -1 --format="%s" "$MERGE_COMMIT")
COMMIT_DATE=$(git -C "$REPO_ROOT" log -1 --format="%ai" "$MERGE_COMMIT")
COMMIT_SHORT="${MERGE_COMMIT:0:12}"

# Files changed by the merge (diff between the two parents: mainline vs. merge result)
FILES_CHANGED=$(git -C "$REPO_ROOT" diff --name-only "${MERGE_COMMIT}^1" "$MERGE_COMMIT" 2>/dev/null || true)

# ── print summary ──────────────────────────────────────────────────────────
echo ""
echo "Most recent pipeline release:"
echo "  Commit : $COMMIT_SHORT"
echo "  Date   : $COMMIT_DATE"
echo "  Message: $COMMIT_MSG"
echo ""

if [ -n "$FILES_CHANGED" ]; then
    echo "Files that will be reverted:"
    echo "$FILES_CHANGED" | sed 's/^/  /'
else
    echo "  (no file diff available)"
fi
echo ""

if $DRY_RUN; then
    echo "--- DRY RUN: no changes will be made ---"
    echo ""
    # Still run the Python DB preview so the user can see what refs would reset.
    cd "$REPO_ROOT"
    if [ -z "${VIRTUAL_ENV:-}" ] && [ -f backend/venv/bin/activate ]; then
        # shellcheck disable=SC1091
        source backend/venv/bin/activate
    fi
    python -m pipeline.rollback "$MERGE_COMMIT" \
        --repo-path "$REPO_ROOT" \
        --dry-run || true
    echo ""
    echo "Dry run complete. Re-run without --dry-run to apply."
    exit 0
fi

# ── confirmation prompt (skipped with --yes) ────────────────────────────────
if ! $YES; then
    printf "Proceed with rollback? [y/N] "
    read -r CONFIRM
    case "$CONFIRM" in
        [yY]|[yY][eE][sS]) ;;
        *)
            echo "Rollback cancelled."
            exit 0
            ;;
    esac
fi

# ── safety: working directory must be clean ────────────────────────────────
if [ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]; then
    echo ""
    echo "error: working directory is not clean." >&2
    echo "Please commit or stash your changes before rolling back." >&2
    exit 1
fi

# ── 1. revert the merge commit ─────────────────────────────────────────────
echo ""
echo "=== Reverting merge commit $COMMIT_SHORT ==="
git -C "$REPO_ROOT" revert -m 1 --no-edit "$MERGE_COMMIT"
echo "Revert commit created."

# ── 2. reset feedback statuses ─────────────────────────────────────────────
echo ""
echo "=== Resetting feedback statuses ==="
cd "$REPO_ROOT"
if [ -z "${VIRTUAL_ENV:-}" ] && [ -f backend/venv/bin/activate ]; then
    # shellcheck disable=SC1091
    source backend/venv/bin/activate
fi
python -m pipeline.rollback "$MERGE_COMMIT" --repo-path "$REPO_ROOT" || {
    echo "warning: feedback status reset had issues (see above). Continuing." >&2
}

# ── 3. redeploy ────────────────────────────────────────────────────────────
echo ""
echo "=== Redeploying ==="
"$REPO_ROOT/scripts/deploy.sh"

echo ""
echo "=== Rollback complete ==="
echo "  Reverted commit : $COMMIT_SHORT  ($COMMIT_MSG)"
echo "  Run 'git log --oneline -5' to verify the revert commit."
