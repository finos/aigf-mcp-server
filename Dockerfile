FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install package into a dedicated virtualenv for a smaller runtime image.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && \
    pip install .

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    FINOS_MCP_MCP_TRANSPORT=http \
    FINOS_MCP_MCP_HOST=0.0.0.0 \
    FINOS_MCP_MCP_PORT=8000 \
    FINOS_MCP_LOG_LEVEL=INFO \
    FINOS_MCP_ENABLE_CACHE=true \
    FINOS_MCP_CACHE_MAX_SIZE=1000 \
    FINOS_MCP_CACHE_TTL_SECONDS=3600

WORKDIR /app

RUN groupadd --system app && \
    useradd --system --gid app --home-dir /app --create-home app

COPY --from=builder /opt/venv /opt/venv
RUN mkdir -p /app/.cache/discovery && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "import finos_mcp; print('ok')" || exit 1

CMD ["finos-mcp"]
