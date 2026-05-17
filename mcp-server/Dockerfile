FROM python:3.12-slim

WORKDIR /app

# Install system deps: build tools for chromadb/sentence-transformers, curl for HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Layer cache: copy requirements first so pip install only reruns when requirements change
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Set persist dir so the seed script knows where to put the db
ENV CHROMADB_PERSIST_DIR=/app/data/chroma_db

# Run the seeding script during build so the data is baked into the image
RUN python data/seed_runbooks.py

# Create non-root user for security (never run as root in production)
# IMPORTANT: Chown the /app directory so the appuser can read/write if necessary
RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /app
USER appuser

# Runtime defaults (overridden by Cloud Run env vars, except CHROMADB_PERSIST_DIR)
ENV PORT=8080
ENV ENV=production

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
