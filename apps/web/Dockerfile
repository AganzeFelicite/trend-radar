FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENV API_URL=http://api:8000 NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Standalone output: server.js plus only the node_modules it needs.
FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000 API_URL=http://api:8000 NEXT_TELEMETRY_DISABLED=1
COPY --from=build --chown=node /app/.next/standalone ./
COPY --from=build --chown=node /app/.next/static ./.next/static
USER node
CMD ["node", "server.js"]
