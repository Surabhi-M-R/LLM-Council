# ============================================================
# LLM Council Backend — Docker Image for AWS App Runner / ECS
# ============================================================
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python dependency management
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy dependency files first (for Docker layer caching)
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv sync --no-dev

# Copy application code
COPY backend/ ./backend/
COPY main.py ./
COPY .env.production .env

# Create data directory for local JSON fallback
RUN mkdir -p data/conversations

# Expose the API port
EXPOSE 8001

# Health check for App Runner / ECS
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"

# Run the FastAPI server
CMD ["uv", "run", "python", "-m", "backend.main"]
