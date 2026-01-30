# Stage 1: Build frontend
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy Python package files
COPY pyproject.toml ./
COPY wsb_tracker/ ./wsb_tracker/

# Install Python dependencies
RUN pip install --no-cache-dir -e ".[api,ticker-info]"

# Copy frontend build
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Create data directory for SQLite database
RUN mkdir -p /data

# Environment variables
ENV WSB_DB_PATH=/data/wsb_tracker.db
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/stats')" || exit 1

# Run the API server
CMD ["uvicorn", "wsb_tracker.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
