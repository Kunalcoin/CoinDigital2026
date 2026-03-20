#!/usr/bin/env bash
# Deliver one release to Apple Music via Merlin Bridge (SFTP .itmsp.zip).
# Requires: Django env (.env), MERLIN_BRIDGE_* vars, AWS/S3 for assets, release approved.
#
# Usage:
#   ./deliver_apple_music_bridge.sh --upc 8905285305999
#   ./deliver_apple_music_bridge.sh 36917                    # release id
#   ./deliver_apple_music_bridge.sh --upc 8905285305999 --metadata-only
#
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if command -v python3 &>/dev/null; then
  PYTHON=python3
elif command -v python &>/dev/null; then
  PYTHON=python
else
  echo "Error: python3 (or python) not found." >&2
  exit 1
fi

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 --upc <UPC> | $0 <release_id> [--metadata-only]" >&2
  echo "Examples:" >&2
  echo "  $0 --upc 8905285305999" >&2
  echo "  $0 36917" >&2
  echo "  $0 --upc 8905285305999 --metadata-only" >&2
  exit 1
fi

exec "$PYTHON" manage.py deliver_apple_music "$@"
