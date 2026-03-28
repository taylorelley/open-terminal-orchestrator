# Stage 1: Build frontend
FROM node:20-alpine AS frontend

WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.ts tsconfig.json tsconfig.app.json tsconfig.node.json ./
COPY tailwind.config.js postcss.config.js eslint.config.js ./
COPY src/ src/

ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY

RUN npm run build


# Stage 2: Python backend + built frontend
FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/ backend/
RUN pip install --no-cache-dir ./backend

COPY --from=frontend /build/dist /app/dist

ENV FRONTEND_DIST_PATH=/app/dist

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -sf http://localhost:8080/health || exit 1

ENTRYPOINT ["shellguard"]
