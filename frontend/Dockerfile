# syntax=docker/dockerfile:1

FROM node:18-alpine AS deps
WORKDIR /app

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build
RUN npm prune --omit=dev

FROM node:18-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=deps /app/package.json ./
COPY --from=deps /app/next.config.js ./
COPY --from=deps /app/public ./public
COPY --from=deps /app/.next ./.next
COPY --from=deps /app/node_modules ./node_modules

EXPOSE 3000

CMD ["npm", "run", "start"]
