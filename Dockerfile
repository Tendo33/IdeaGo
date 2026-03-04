FROM node:20-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.13-slim
WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --no-dev --frozen

COPY src/ src/
COPY --from=frontend-build /build/dist frontend/dist

RUN mkdir -p .cache/ideago && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f\"http://localhost:{os.getenv('PORT', '8000')}/api/v1/health\")" || exit 1

CMD ["uv", "run", "python", "-m", "ideago"]
