#!/usr/bin/env bash
# Bootstrap GoatProject after clone: worktrees, deps, checkpoint verify.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GOAT_ROOT="$ROOT"

PYTHON="${PYTHON:-python3.11}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python3
fi

MODE="${1:-setup}"

echo "GoatProject bootstrap (checkpoint v2 — alchemy-v2)"
echo "GOAT_ROOT=$ROOT"
echo "Using: $PYTHON"
echo ""

ensure_worktree() {
  local dir="$1"
  local branch="$2"
  if [[ -d "$ROOT/$dir" ]] && [[ -e "$ROOT/$dir/.git" ]]; then
    echo "  worktree OK: $dir ($branch)"
    return 0
  fi
  echo "  adding worktree: $dir <- $branch"
  git -C "$ROOT" fetch origin "$branch" 2>/dev/null || git -C "$ROOT" fetch origin
  git -C "$ROOT" worktree add "$ROOT/$dir" "origin/$branch" 2>/dev/null     || git -C "$ROOT" worktree add "$ROOT/$dir" "$branch"
}

install_pkg() {
  local dir="$1"
  echo "  pip install -e $dir"
  (cd "$ROOT/$dir" && "$PYTHON" -m pip install -q -e ".[dev]")
}

case "$MODE" in
  setup|"")
    echo "==> Git worktrees"
    ensure_worktree "GoatProject-data" "data"
    ensure_worktree "GoatProject-modeling" "modeling"
    ensure_worktree "GoatProject-viz" "viz"
    echo ""

    echo "==> Python packages"
    install_pkg "GoatProject-data"
    install_pkg "GoatProject-modeling"
    install_pkg "GoatProject-viz"
    echo ""

    echo "==> Checkpoint verify"
    if "$PYTHON" "$ROOT/scripts/verify_checkpoint.py"; then
      echo ""
      echo "Ready. Open the viz:"
      echo "  ./open.sh"
      echo ""
      echo "Rebuild from raw CSVs (slow):"
      echo "  ./run.sh"
    else
      echo ""
      echo "Checkpoint incomplete. Options:"
      echo "  1) git pull in each worktree if maintainer published artifacts"
      echo "  2) ./run.sh — full rebuild from CSVs"
      exit 1
    fi
    ;;
  worktrees)
    ensure_worktree "GoatProject-data" "data"
    ensure_worktree "GoatProject-modeling" "modeling"
    ensure_worktree "GoatProject-viz" "viz"
    ;;
  deps)
    install_pkg "GoatProject-data"
    install_pkg "GoatProject-modeling"
    install_pkg "GoatProject-viz"
    ;;
  verify)
    "$PYTHON" "$ROOT/scripts/verify_checkpoint.py"
    ;;
  *)
    echo "Usage: ./bootstrap.sh [setup|worktrees|deps|verify]"
    exit 2
    ;;
esac
