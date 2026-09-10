# Single-container sandbox image (portal + API + demo data). For the IT team's sandbox server.
FROM node:20-bookworm AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY web ./
COPY shared ../shared
RUN VITE_BASE_PATH=/building-violations/ npm run build

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libcairo2 fonts-noto-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./
COPY shared ../shared
COPY --from=web /app/web/dist ../web/dist
ENV DEMO_MODE=1 SERVE_SPA=1 DJANGO_DEBUG=0 DJANGO_ALLOWED_HOSTS=* MEDIA_ROOT=/data/media PYTHONUNBUFFERED=1
VOLUME ["/data"]
EXPOSE 8000
CMD sh -c "python manage.py migrate -v 0 && (python manage.py seed_demo --with-cases || true) && gunicorn config.wsgi:application -b 0.0.0.0:8000 -w 3 --timeout 180"
