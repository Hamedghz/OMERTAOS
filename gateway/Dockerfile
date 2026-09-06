FROM --platform=$BUILDPLATFORM node:22.23.2-alpine3.24@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS deps

WORKDIR /workspace

COPY gateway/package.json gateway/package-lock.json ./gateway/
COPY shared/secret-provider-node ./shared/secret-provider-node

WORKDIR /workspace/gateway
RUN --mount=type=cache,target=/root/.npm,sharing=locked npm ci

FROM --platform=$BUILDPLATFORM node:22.23.2-alpine3.24@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS builder

WORKDIR /workspace
COPY --from=deps /workspace/gateway/node_modules ./gateway/node_modules
COPY gateway ./gateway
COPY schemas/v1/protos ./protos
COPY shared/secret-provider-node ./shared/secret-provider-node

WORKDIR /workspace/gateway
RUN npm run build

FROM node:22.23.2-alpine3.24@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS runner

WORKDIR /app
ENV NODE_ENV=production

RUN apk add --no-cache curl

COPY --from=builder /workspace/gateway/package.json ./package.json
COPY --from=builder /workspace/gateway/node_modules ./node_modules
COPY --from=builder /workspace/gateway/dist ./dist
COPY --from=builder /workspace/protos ./protos
COPY --from=builder /workspace/protos /protos
COPY --from=builder /workspace/shared/secret-provider-node /shared/secret-provider-node

EXPOSE 8080

CMD ["node", "dist/server.js"]
