# ── 1. Deps + build ───────────────────────────────────────────
FROM node:20-alpine AS builder

# pnpm via corepack (pas de npm install -g)
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile=false

COPY . .
RUN pnpm build

# ── 2. Runtime nginx ──────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]


# ── Variante dev (hot reload) ─────────────────────────────────
FROM node:20-alpine AS dev

RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

WORKDIR /app
ENV CHOKIDAR_USEPOLLING=true

COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile=false

COPY . .

EXPOSE 5173
CMD ["pnpm", "dev"]
