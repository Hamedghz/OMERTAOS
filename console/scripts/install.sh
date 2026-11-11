#!/bin/sh
set -eu

if [ -z "${DATABASE_URL:-}" ]; then
  echo "[install] DATABASE_URL is not set"
  exit 1
fi

echo "[install] Applying database migrations..."
node ./scripts/with-auditable-esbuild.mjs ./node_modules/.bin/prisma migrate deploy

echo "[install] Bootstrapping console admin user..."
node ./scripts/with-auditable-esbuild.mjs node ./scripts/dist/bootstrap-admin.js

echo "[install] Quickstart install completed."
