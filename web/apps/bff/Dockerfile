FROM node:22-alpine AS base
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate

FROM base AS build
WORKDIR /app
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/bff/package.json ./apps/bff/
COPY packages/shared/package.json ./packages/shared/
RUN pnpm install --frozen-lockfile
COPY apps/bff ./apps/bff
COPY packages/shared ./packages/shared
RUN pnpm --filter @stock-trader/bff build

FROM node:22-alpine
WORKDIR /app
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/apps/bff/node_modules ./apps/bff/node_modules
COPY --from=build /app/apps/bff/dist ./apps/bff/dist
EXPOSE 3002
CMD ["node", "apps/bff/dist/main.js"]
