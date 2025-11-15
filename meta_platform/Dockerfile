FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /code

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /code/meta_platform/requirements.txt

RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /code/meta_platform/requirements.txt \
    && pip install --no-cache-dir 'pydantic[email]'

# Copy application code
COPY . /code/meta_platform/

# Create runtime user
RUN addgroup --system app \
    && adduser --system --ingroup app app \
    && chown -R app:app /code

USER app

EXPOSE 9000

CMD ["uvicorn", "meta_platform.main:app", "--host", "0.0.0.0", "--port", "9000"]
