#!/usr/bin/env bash
# Run the full GOAT pipeline: data → modeling → viz
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GOAT_ROOT="$ROOT"

PYTHON="${PYTHON:-python3.11}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  PYTHON=python3
fi

echo "GOAT_ROOT=$GOAT_ROOT"
echo "Using: $PYTHON"
echo "Tip: after clone use ./bootstrap.sh (not ./run.sh) unless rebuilding from CSVs."
echo ""
echo "==> Data pipeline"
(cd "$ROOT/GoatProject-data" && "$PYTHON" -m goat_data.run_pipeline)

echo ""
echo "==> Rankings"
(cd "$ROOT/GoatProject-modeling" && "$PYTHON" -m goat_model.run_ranking)

echo ""
echo "==> Analysis (PCA, similarity)"
(cd "$ROOT/GoatProject-modeling" && "$PYTHON" -m goat_model.run_analysis)

echo ""
echo "==> Alchemy cache"
(cd "$ROOT/GoatProject-modeling" && PYTHONPATH=src "$PYTHON" -m goat_model.run_alchemy)

echo ""
echo "==> Visualization"
(cd "$ROOT/GoatProject-viz" && "$PYTHON" -m goat_viz.run_viz)

INDEX="$ROOT/GoatProject-viz/output/index.html"
echo ""
echo "Done. Open:"
echo "  file://$INDEX"
