# All-in-One Cloud Dockerfile for Hugging Face Spaces (16GB RAM Free), Render, Railway & Koyeb
FROM ghcr.io/astral-sh/uv:0.11.4 AS uv
FROM python:3.12-slim

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    MLFLOW_DISABLE_AGENT_HINT=1 \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    NODE_ENV=production \
    PORT=7860

# Install system dependencies + Node.js 22 LTS
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    libgomp1 \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python ML & API dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --python /usr/local/bin/python

# Install Node.js frontend dependencies
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
RUN npm ci

# Copy full application source
COPY packages packages
COPY services services
COPY scripts scripts
COPY configs configs
COPY alembic.ini ./
COPY apps/web apps/web

# Finalize Python workspace & build Next.js production bundle
RUN uv sync --frozen --no-dev --python /usr/local/bin/python \
    && npm run build --workspace apps/web \
    && chmod +x scripts/start-cloud.sh

ENV PATH="/app/.venv/bin:$PATH"

# Create non-root user (UID 1000 required by Hugging Face Spaces)
RUN useradd -m -u 1000 atlasrec \
    && mkdir -p artifacts data/research docs/evidence \
    && chown -R atlasrec:atlasrec /app

USER atlasrec
EXPOSE 7860

CMD ["bash", "scripts/start-cloud.sh"]
