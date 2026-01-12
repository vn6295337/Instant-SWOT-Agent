# Dockerfile for HF Spaces (Docker SDK)
# Multi-stage build: Node.js for frontend, Python for backend

# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

# Copy package files first for better caching
COPY frontend/package.json frontend/package-lock.json ./

# Install dependencies
RUN npm ci

# Copy frontend source code
COPY frontend/ ./

# Build the frontend
RUN npm run build

# Stage 2: Python backend with built frontend
FROM python:3.11-slim

WORKDIR /app

# Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY a2a/ ./a2a/
COPY data/ ./data/
# Note: Don't copy .env file - HF Spaces injects secrets as environment variables

# Copy built frontend from stage 1 (vite outputs to ../static which is /static in container)
COPY --from=frontend-builder /static ./static/

# Verify static files exist
RUN ls -la /app/static/ && ls -la /app/static/assets/

# Expose port (HF Spaces uses 7860)
EXPOSE 7860

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Start server
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "7860"]
