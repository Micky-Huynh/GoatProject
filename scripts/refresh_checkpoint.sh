#!/usr/bin/env bash
# Maintainer: rebuild pipeline and print commit checklist for checkpoint branches.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export GOAT_ROOT="$ROOT"

PYTHON="${PYTHON:-python3.11}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python3
fi

echo "==> Full pipeline rebuild"
"$ROOT/run.sh"

echo ""
echo "==> Verify checkpoint"
"$PYTHON" "$ROOT/scripts/verify_checkpoint.py"

echo ""
echo "==> Commit checklist (run inside each worktree)"
cat <<'EOF'
GoatProject-data (branch data):
  git add processed/ src/ tests/
  git commit -m "checkpoint: processed parquet + pipeline v2"

GoatProject-modeling (branch modeling):
  git add output/ src/ tests/
  git commit -m "checkpoint: modeling outputs + alchemy cache v2"

GoatProject-viz (branch viz):
  git add output/ src/ tests/
  git commit -m "checkpoint: viz HTML + alchemy lab"

main:
  git add checkpoint.yaml bootstrap.sh open.sh scripts/ config/ README.md run.sh
  git commit -m "checkpoint: bootstrap scripts and config for clone-and-run"
EOF

echo ""
echo "After pushing all branches, fresh clones can: git clone && ./bootstrap.sh && ./open.sh"
