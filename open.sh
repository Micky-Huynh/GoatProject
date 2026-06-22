#!/usr/bin/env bash
# Open the built visualization bundle in the default browser.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INDEX="$ROOT/GoatProject-viz/output/index.html"
ALCHEMY="$ROOT/GoatProject-viz/output/alchemy.html"

if [[ ! -f "$INDEX" ]]; then
  echo "Missing $INDEX — run ./bootstrap.sh first (or ./run.sh to rebuild)." >&2
  exit 1
fi

TARGET="${1:-index}"
case "$TARGET" in
  index) FILE="$INDEX" ;;
  3d|embed) FILE="$ROOT/GoatProject-viz/output/embed_3d.html" ;;
  alchemy|lab) FILE="$ALCHEMY" ;;
  *)
    echo "Usage: ./open.sh [index|3d|alchemy]" >&2
    exit 2
    ;;
esac

if [[ ! -f "$FILE" ]]; then
  echo "Missing $FILE — run ./bootstrap.sh or ./run.sh." >&2
  exit 1
fi

echo "Opening file://$FILE"
if command -v open >/dev/null 2>&1; then
  open "$FILE"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$FILE"
else
  echo "Open this URL in your browser: file://$FILE"
fi
