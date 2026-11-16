# Stage 1: Build & Dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY core/ core/
COPY app/ app/
COPY cli.py ./

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Stage 2: Final Minimal Runtime
FROM python:3.12-slim AS runner

WORKDIR /app

# Install runtime system libraries and create non-root user
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1001 appgroup \
    && useradd -u 1001 -g appgroup -m -s /bin/bash appuser

# Copy installed site-packages and console binaries from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source code and configurations
COPY --chown=appuser:appgroup . /app

# Ensure writable directories for logs and local database
RUN mkdir -p /app/logs /app/results/reports /app/data && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8501 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app/Home.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
