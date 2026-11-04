FROM node:26.13.0-alpine3.24@sha256:c6ad9e9c1d80f6eb607c26b4b0a132ff7a2344fad1c78ea3baa2a7d4c8de6d94 AS dependencies
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
COPY apps/dashboard/package.json ./apps/dashboard/package.json
RUN npm ci

FROM dependencies AS builder
COPY apps/dashboard ./apps/dashboard
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:26.13.0-alpine3.24@sha256:c6ad9e9c1d80f6eb607c26b4b0a132ff7a2344fad1c78ea3baa2a7d4c8de6d94 AS runtime
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
COPY --from=builder --chown=node:node /app/apps/dashboard/.next/standalone ./
COPY --from=builder --chown=node:node /app/apps/dashboard/.next/static ./apps/dashboard/.next/static
USER 1000:1000
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=12 CMD ["node", "-e", "fetch('http://127.0.0.1:3000').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
CMD ["node", "apps/dashboard/server.js"]
