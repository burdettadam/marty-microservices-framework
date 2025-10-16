# Production Dockerfile for PetstoreDomain Service
# Multi-stage build for optimal image size and security

# Build stage
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create and set work directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.local/bin:$PATH"

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy Python dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Copy enhanced configurations and database files
COPY config/enhanced_config.yaml /app/config/
COPY db/ /app/db/

# Set additional environment variables for enhanced features
ENV CONFIG_FILE=/app/config/enhanced_config.yaml \
    KAFKA_BROKERS=kafka:9092 \
    REDIS_URL=redis://redis:6379 \
    DATABASE_URL=postgresql://petstore_user:demo_password@postgres:5432/petstore \
    JAEGER_ENDPOINT=http://jaeger:14268/api/traces \
    PROMETHEUS_GATEWAY=http://prometheus:9090

# Create necessary directories
RUN mkdir -p logs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check - updated for enhanced petstore endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/petstore-domain/health || exit 1

# Expose port
EXPOSE 8080

# Set default command - using simple service
CMD ["python", "-m", "uvicorn", "simple_main:app", "--host", "0.0.0.0", "--port", "8080"]

# Production optimizations:
# - Multi-stage build reduces image size
# - Non-root user for security
# - Health check for container orchestration
# - Proper Python optimizations
# - Runtime dependency optimization

# Build commands:
# docker build -t petstore-domain:latest .
# docker run -p 8080:8080 petstore-domain:latest
