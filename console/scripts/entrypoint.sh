#!/bin/sh
set -eu

echo "[console] Starting Next.js server..."
exec node scripts/with-auditable-esbuild.mjs node node_modules/next/dist/bin/next start -p "${PORT:-3000}"
