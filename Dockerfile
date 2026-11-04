FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.18 /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
# Bake the embedding model (~220 MB) into the image: no download at runtime, works offline.
ENV MODEL_CACHE_DIR=/opt/models
RUN /app/.venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', cache_dir='/opt/models')"
COPY alembic.ini ./
COPY migrations ./migrations
COPY trend_radar ./trend_radar
COPY dbt ./dbt

RUN useradd --system --no-create-home app && chown -R app /opt/models
USER app
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1
CMD ["sh", "-c", "alembic upgrade head && python -m trend_radar.scheduler"]
