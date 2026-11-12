# Един образ за Render: Vue панелът се сглобява и FastAPI го сервира заедно с API-то.
# (За собствен VPS вижте docker-compose.yml – там панелът е зад Caddy.)
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 KK_STATIC_DIR=/app/static
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir .
COPY backend/scripts ./scripts
COPY --from=web /web/dist ./static

RUN useradd --create-home --uid 1000 klimaklas && chown klimaklas /app
USER klimaklas

# Render подава порта в $PORT.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
