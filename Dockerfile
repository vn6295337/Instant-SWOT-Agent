# Dockerfile for HF Spaces (Docker SDK)
# Uses pre-built frontend from static/ directory

FROM python:3.11-slim

WORKDIR /app

# Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY a2a/ ./a2a/
COPY data/ ./data/
COPY .env.example ./.env

# Copy pre-built frontend (built locally and committed)
COPY static/ ./static/

# Verify static files exist
RUN ls -la /app/static/ && ls -la /app/static/assets/

# Expose port (HF Spaces uses 7860)
EXPOSE 7860

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Start server (using new consolidated path)
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "7860"]
