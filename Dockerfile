FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
COPY scripts/test_task_identity.cjs ./scripts/test_task_identity.cjs
RUN TYPESCRIPT_PATH=/build/node_modules/typescript TASK_STORE_PATH=/build/src/stores/tasks.ts node scripts/test_task_identity.cjs && npm run build:prod

FROM python:3.10-slim-bookworm AS wheels
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir setuptools==69.5.1 wheel==0.43.0 Cython==3.0.6 \
    && python -m pip wheel --no-build-isolation --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.10-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=Asia/Shanghai FILM_INDEX_DATA=/data PYTHONPATH=/opt/film-index
WORKDIR /opt/film-index
RUN apt-get update && apt-get install -y --no-install-recommends tzdata ca-certificates curl ffmpeg rclone chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL --retry 3 https://github.com/minio/mc/releases/download/RELEASE.2025-08-13T08-35-41Z/mc.linux-amd64.RELEASE.2025-08-13T08-35-41Z -o /usr/local/bin/mc \
    && echo '01f866e9c5f9b87c2b09116fa5d7c06695b106242d829a8bb32990c00312e891  /usr/local/bin/mc' | sha256sum -c - \
    && chmod +x /usr/local/bin/mc \
    && mkdir -p /app && ln -s /data/media /config && ln -s /data/config /app/config && ln -s /data/log /app/log
COPY requirements.txt ./
COPY --from=wheels /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels
COPY film_index/ ./film_index/
COPY --from=frontend /build/dist/ ./film_index/frontend/dist/
COPY source.zip /opt/film-index/source.zip
LABEL org.opencontainers.image.title="Film Index" \
      org.opencontainers.image.version="3.0.4" \
      org.opencontainers.image.source="https://github.com/dandan658/film-index-hub" \
      org.opencontainers.image.licenses="AGPL-3.0-only"
EXPOSE 5000
HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=6 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=3)"
CMD ["python", "-m", "film_index"]

