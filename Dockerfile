FROM node:24-bookworm-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates python3 make g++ libatomic1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN npm install --global pnpm@11.25.0
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:24-bookworm-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libatomic1 && rm -rf /var/lib/apt/lists/* && groupadd --gid 10001 kakakin && useradd --uid 10001 --gid 10001 --create-home kakakin
WORKDIR /app
COPY --from=build --chown=10001:10001 /app/node_modules ./node_modules
COPY --from=build --chown=10001:10001 /app/dist ./dist
COPY --from=build --chown=10001:10001 /app/drizzle ./drizzle
COPY --from=build --chown=10001:10001 /app/server ./server
COPY --from=build /app/package.json ./package.json
USER 10001:10001
ENV NODE_ENV=production DATA_DIR=/data ACCOUNTS_FILE=/config/accounts.json PORT=18770
EXPOSE 18770
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 CMD node -e "fetch('http://127.0.0.1:18770/healthz').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
CMD ["node","server/gateway.mjs"]
