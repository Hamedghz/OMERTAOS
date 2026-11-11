# Stage 1: install dependencies with pnpm
FROM node:22.23.2-alpine3.24@sha256:b6f26b36c8ff49624cfdac716b8ea1138d606df02586a77d364bb5536a634f85 AS deps

RUN --mount=type=cache,target=/root/.npm,sharing=locked npm install --global npm@10.9.10 --ignore-scripts --no-fund && test "$(npm --version)" = "10.9.10"

WORKDIR /workspace

# Enable pnpm via corepack so the image uses the same package manager version
RUN corepack enable && corepack prepare pnpm@11.13.1 --activate

# Copy the console manifest and the local workspace packages it depends on
COPY console/package.json console/pnpm-lock.yaml console/pnpm-workspace.yaml ./console/
COPY console/scripts/with-auditable-esbuild.mjs ./console/scripts/with-auditable-esbuild.mjs
COPY scripts/verify_esbuild_artifact.mjs scripts/esbuild-linux-x64-artifact.json ./scripts/
COPY --from=omerta_esbuild --chmod=0555 /esbuild /opt/omerta-tools/esbuild
COPY --from=omerta_esbuild /omerta-esbuild-linux-x64-0.28.2-omerta.1.tgz ./artifacts/tooling/esbuild/omerta-esbuild-linux-x64-0.28.2-omerta.1.tgz
COPY shared/secret-provider-node ./shared/secret-provider-node
COPY packages/ui-core ./packages/ui-core

WORKDIR /workspace/console
ENV OMERTA_ESBUILD_BINARY=/opt/omerta-tools/esbuild

RUN --mount=type=cache,id=omerta-console-pnpm-v11,target=/pnpm/store,sharing=locked \
    pnpm config set store-dir /pnpm/store \
    && node scripts/with-auditable-esbuild.mjs pnpm install --frozen-lockfile --prefer-offline --network-concurrency=2 --child-concurrency=2 \
        --fetch-retries=1 --fetch-timeout=120000

# Stage 2: build (Next.js + Prisma generate)
FROM node:22.23.2-alpine3.24@sha256:b6f26b36c8ff49624cfdac716b8ea1138d606df02586a77d364bb5536a634f85 AS builder

RUN --mount=type=cache,target=/root/.npm,sharing=locked npm install --global npm@10.9.10 --ignore-scripts --no-fund && test "$(npm --version)" = "10.9.10"

WORKDIR /workspace
RUN corepack enable && corepack prepare pnpm@11.13.1 --activate

# Reuse installed dependencies from deps stage
COPY --from=deps /workspace/console/node_modules ./console/node_modules
COPY --from=deps /workspace/scripts ./scripts
COPY --from=deps /workspace/artifacts/tooling/esbuild ./artifacts/tooling/esbuild
COPY --from=deps /opt/omerta-tools /opt/omerta-tools
ENV OMERTA_ESBUILD_BINARY=/opt/omerta-tools/esbuild

# Copy full source and shared packages required for build-time steps
COPY console/. ./console
COPY shared/secret-provider-node ./shared/secret-provider-node
COPY packages/ui-core ./packages/ui-core

WORKDIR /workspace/console

# Ensure the public directory exists so the runtime stage can copy it even when
# the application does not ship static assets. This avoids COPY failures on CI
# when the folder is absent from the source tree.
RUN mkdir -p public

# Provide Prisma with a safe build-time DATABASE_URL so it can emit the client without
# talking to a live database. Runtime deployments still override DATABASE_URL via their
# own environment configuration (docker-compose, k8s secrets, etc.).
ARG PRISMA_DATABASE_URL="postgresql://placeholder:placeholder@localhost:5432/placeholder?schema=public"
ENV DATABASE_URL=${PRISMA_DATABASE_URL}

RUN pnpm prisma:generate
# Next subtracts one from this value when choosing build workers.
RUN CIRCLE_NODE_TOTAL=2 pnpm build
RUN node scripts/with-auditable-esbuild.mjs pnpm exec tsc --project scripts/tsconfig.json

# Stage 3: runtime image
FROM node:22.23.2-alpine3.24@sha256:b6f26b36c8ff49624cfdac716b8ea1138d606df02586a77d364bb5536a634f85 AS runner

RUN --mount=type=cache,target=/root/.npm,sharing=locked npm install --global npm@10.9.10 --ignore-scripts --no-fund && test "$(npm --version)" = "10.9.10"

WORKDIR /app
ENV NODE_ENV=production

ARG ALPINE_MIRROR=cdn
RUN case "$ALPINE_MIRROR" in \
      cdn) ;; \
      kernel) sed -i 's|^https://dl-cdn\.alpinelinux\.org/alpine/|https://mirrors.edge.kernel.org/alpine/|' /etc/apk/repositories ;; \
      *) echo "Unsupported ALPINE_MIRROR; expected cdn or kernel" >&2; exit 1 ;; \
    esac \
    && apk add --no-cache curl

# Create non-root user for running the app
RUN addgroup -g 1001 -S nodejs \
  && adduser -S nextjs -u 1001

# Copy only the files required at runtime
COPY --from=builder /workspace/console/public ./public
COPY --from=builder /workspace/console/.next ./.next
COPY --from=builder /workspace/console/node_modules ./node_modules
COPY --from=builder /workspace/console/package.json ./package.json
COPY --from=builder /workspace/console/next.config.mjs ./next.config.mjs
COPY --from=builder /workspace/console/prisma ./prisma
COPY --from=builder /workspace/console/scripts ./scripts
COPY --from=builder /workspace/scripts /scripts
COPY --from=builder /opt/omerta-tools /opt/omerta-tools
ENV OMERTA_ESBUILD_BINARY=/opt/omerta-tools/esbuild

USER nextjs

EXPOSE 3000

COPY console/scripts/entrypoint.sh ./entrypoint.sh

CMD ["sh", "entrypoint.sh"]
