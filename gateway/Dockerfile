FROM --platform=$BUILDPLATFORM node:22.23.2-alpine3.24@sha256:b6f26b36c8ff49624cfdac716b8ea1138d606df02586a77d364bb5536a634f85 AS deps

RUN --mount=type=cache,target=/root/.npm,sharing=locked npm install --global npm@10.9.10 --ignore-scripts --no-fund && test "$(npm --version)" = "10.9.10"

WORKDIR /workspace

COPY gateway/package.json gateway/package-lock.json ./gateway/
COPY shared/secret-provider-node ./shared/secret-provider-node

WORKDIR /workspace/gateway
RUN --mount=type=cache,target=/root/.npm,sharing=locked npm ci

FROM --platform=$BUILDPLATFORM node:22.23.2-alpine3.24@sha256:b6f26b36c8ff49624cfdac716b8ea1138d606df02586a77d364bb5536a634f85 AS builder

RUN --mount=type=cache,target=/root/.npm,sharing=locked npm install --global npm@10.9.10 --ignore-scripts --no-fund && test "$(npm --version)" = "10.9.10"

WORKDIR /workspace
COPY --from=deps /workspace/gateway/node_modules ./gateway/node_modules
COPY gateway ./gateway
COPY schemas/v1/protos ./protos
COPY shared/secret-provider-node ./shared/secret-provider-node

WORKDIR /workspace/gateway
RUN npm run build

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

COPY --from=builder /workspace/gateway/package.json ./package.json
COPY --from=builder /workspace/gateway/node_modules ./node_modules
COPY --from=builder /workspace/gateway/dist ./dist
COPY --from=builder /workspace/protos ./protos
COPY --from=builder /workspace/protos /protos
COPY --from=builder /workspace/shared/secret-provider-node /shared/secret-provider-node

EXPOSE 8080

CMD ["node", "dist/server.js"]
