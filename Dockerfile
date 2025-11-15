FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Optional system deps for builds and tooling
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    ca-certificates \
    wget \
  && rm -rf /var/lib/apt/lists/*

# Install project requirements (if provided)
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt || true

# Add runtime dependencies commonly needed for this stack
RUN pip install \
    gunicorn \
    psycopg[binary] \
    django-redis \
    qdrant-client

# Copy application code
COPY . .

EXPOSE 8000

# Default command is set in docker-compose.yml

