FROM node:20-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
ARG VITE_API_BASE_URL=""
ARG VITE_SUPABASE_URL=""
ARG VITE_SUPABASE_ANON_KEY=""
ARG VITE_TURNSTILE_SITE_KEY=""
ARG SUPABASE_URL=""
ARG SUPABASE_ANON_KEY=""
COPY frontend/ .
RUN export VITE_API_BASE_URL="${VITE_API_BASE_URL}" \
    && export VITE_SUPABASE_URL="${VITE_SUPABASE_URL:-$SUPABASE_URL}" \
    && export VITE_SUPABASE_ANON_KEY="${VITE_SUPABASE_ANON_KEY:-$SUPABASE_ANON_KEY}" \
    && export VITE_TURNSTILE_SITE_KEY="${VITE_TURNSTILE_SITE_KEY}" \
    && pnpm build

FROM python:3.13-slim
WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock LICENSE README.md ./
RUN uv sync --no-dev --frozen

COPY src/ src/
COPY --from=frontend-build /build/dist frontend/dist

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r//' /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

RUN mkdir -p .cache/ideago && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f\"http://localhost:{os.getenv('PORT', '8000')}/api/v1/health\")" || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uv", "run", "python", "-m", "ideago"]
