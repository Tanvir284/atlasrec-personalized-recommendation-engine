FROM ghcr.io/astral-sh/uv:0.11.4@sha256:5164bf84e7b4e2e08ce0b4c66b4a8c996a286e6959f72ac5c6e0a3c80e8cb04a AS uv
FROM python:3.12.13-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy MLFLOW_DISABLE_AGENT_HINT=1 UV_CONCURRENT_DOWNLOADS=4 UV_HTTP_TIMEOUT=120
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project --python /usr/local/bin/python
COPY packages packages
COPY services services
COPY scripts scripts
COPY configs configs
COPY alembic.ini ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --python /usr/local/bin/python
ENV PATH="/app/.venv/bin:$PATH" OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 GIT_PYTHON_REFRESH=quiet
RUN useradd --create-home atlasrec && mkdir -p artifacts data docs/evidence && chown -R atlasrec:atlasrec artifacts data docs
USER atlasrec
CMD ["uvicorn","atlasrec_api.main:app","--host","0.0.0.0","--port","8000","--workers","1"]
