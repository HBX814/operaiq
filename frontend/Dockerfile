# Stage 1: Install dependencies
FROM node:22-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json package-lock.json* ./
# Use npm ci for reproducible installs
RUN npm ci

# Stage 2: Build the application
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_MCP_SERVER_URL
ARG NEXT_PUBLIC_AGENTS_WS_URL
ARG NEXT_PUBLIC_AGENT_WS_URL
ENV NEXT_PUBLIC_MCP_SERVER_URL=$NEXT_PUBLIC_MCP_SERVER_URL
ENV NEXT_PUBLIC_AGENTS_WS_URL=$NEXT_PUBLIC_AGENTS_WS_URL
ENV NEXT_PUBLIC_AGENT_WS_URL=$NEXT_PUBLIC_AGENT_WS_URL

RUN npm run build

# Stage 3: Production runner (minimal image)
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Create non-root user
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# Copy built standalone output and static assets
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:3000/ | grep -q "OperaIQ" || exit 1

CMD ["node", "server.js"]
