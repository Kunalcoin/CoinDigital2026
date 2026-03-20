#!/bin/bash
# Deliver the listed UPCs to all stores via Sonosuite API.
# Tracks and poster must already be added in Sonosuite UI.
# Set SONOSUITE_* in .env or coin.env. Run from RoyaltyWebsite directory.

set -e
cd "$(dirname "$0")"

if [ -f coin.env ]; then
  set -a
  source coin.env
  set +a
fi
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

UPCs=(
  8905285299670
  8905285299687
  8905285299717
  8905285299694
  8905285299700
  8904228552193
  0886449362165
  8905285299724
  8905285299731
  8905285299748
)

echo "Delivering ${#UPCs[@]} UPCs via Sonosuite API (all stores)..."
python3 manage.py sonosuite_deliver "${UPCs[@]}"
