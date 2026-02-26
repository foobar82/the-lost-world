#!/usr/bin/env bash
# Start a Cloudflare quick tunnel pointing at the local production server.
# The server must already be running on port 8000 (see deploy.sh).
#
# Usage:
#   ./scripts/tunnel.sh
#
# Cloudflare will print a public *.trycloudflare.com URL to stdout.
# No Cloudflare account or login is required for a quick tunnel.
set -euo pipefail

PORT=8000

echo "=== Starting Cloudflare quick tunnel -> http://localhost:$PORT ==="
exec cloudflared tunnel --url "http://localhost:$PORT"
