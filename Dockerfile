# Use official lightweight Python runtime
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    PORT=8080

WORKDIR /app

# Install system dependencies (FFmpeg for audio processing and curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root system user for least-privilege security
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application directories (backend includes seed_catalog.json)
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY data/ ./data/

# Create application data directories and assign permissions to non-root user
RUN mkdir -p /app/data/uploads /app/data/chunks && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose Cloud Run default container port
EXPOSE 8080

# Health check probe for container orchestrators (Cloud Run / K8s / Docker)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8080}/health || exit 1

# Launch production server with proper signal forwarding
CMD ["sh", "-c", "exec uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8080} --timeout-keep-alive 65"]
