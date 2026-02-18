# Multi-stage build for production-ready container
FROM python:3.11-slim as builder

# Set build arguments
ARG BUILDPLATFORM
ARG TARGETPLATFORM
ARG TARGETARCH

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml README.md ./
COPY src/ src/

# Install the package and dependencies
RUN pip install --no-cache-dir -e .[security]

# Production stage
FROM python:3.11-slim as production

# Create non-root user for security
RUN groupadd -r mcp && useradd -r -g mcp -s /bin/false mcp

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/src /app/src

# Set up proper Python path
ENV PYTHONPATH="/app/src:$PYTHONPATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Security and performance settings
ENV FINOS_MCP_LOG_LEVEL=INFO
ENV FINOS_MCP_HTTP_TIMEOUT=30
ENV FINOS_MCP_ENABLE_CACHE=true
ENV FINOS_MCP_CACHE_MAX_SIZE=1000
ENV FINOS_MCP_CACHE_TTL_SECONDS=3600

# Health check
COPY --from=builder /app/src/finos_mcp /usr/local/lib/python3.11/site-packages/finos_mcp
RUN python -c "import finos_mcp; print('Package import successful')"

# Change ownership to non-root user
RUN chown -R mcp:mcp /app
USER mcp

# Expose port (MCP servers typically use stdio, but for health checks)
EXPOSE 8080

# Health check command
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import finos_mcp; print('Health check passed')" || exit 1

# Default command
CMD ["finos-mcp"]

# Labels for better container management
LABEL org.opencontainers.image.title="FINOS AI Governance MCP Server"
LABEL org.opencontainers.image.description="Model Context Protocol server for FINOS AI Governance Framework"
LABEL org.opencontainers.image.source="https://github.com/<OWNER>/<REPO>"
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.vendor="FINOS"
