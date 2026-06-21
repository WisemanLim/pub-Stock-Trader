FROM node:22-alpine AS base
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate

FROM base AS build
# BFF_URL is used by next.config.ts rewrites() at build time (server-side proxy)
ARG BFF_URL=http://bff:3002
ENV BFF_URL=$BFF_URL
# NEXT_PUBLIC_* vars are baked into the browser bundle at build time — must be ARG here
ARG NEXT_PUBLIC_BFF_URL=/bff
ENV NEXT_PUBLIC_BFF_URL=$NEXT_PUBLIC_BFF_URL
ARG NEXT_PUBLIC_RISK_ENGINE_URL=/bff
ENV NEXT_PUBLIC_RISK_ENGINE_URL=$NEXT_PUBLIC_RISK_ENGINE_URL
WORKDIR /app
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/dashboard/package.json ./apps/dashboard/
COPY packages/shared/package.json ./packages/shared/
RUN pnpm install --frozen-lockfile
COPY apps/dashboard ./apps/dashboard
COPY packages/shared ./packages/shared
RUN pnpm --filter @stock-trader/dashboard build

FROM node:22-alpine
WORKDIR /app
# standalone output includes traced node_modules — no pnpm needed at runtime
COPY --from=build /app/apps/dashboard/.next/standalone ./
COPY --from=build /app/apps/dashboard/.next/static ./apps/dashboard/.next/static
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0
CMD ["node", "apps/dashboard/server.js"]
