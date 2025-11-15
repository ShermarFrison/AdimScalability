# AdimScalability

This project is a Django application that can be run either in Docker (via `docker-compose.yml`) or directly on your machine. Gunicorn is now the default production-grade WSGI HTTP server used for serving the app.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create a `.env` file (or export environment variables) that mirrors the values used in `docker-compose.yml` for database credentials, Redis, Qdrant, etc.

## Running with Gunicorn

Once dependencies and environment variables are ready, run database migrations and start Gunicorn:

```bash
python manage.py migrate
gunicorn ${DJANGO_WSGI_MODULE:-project.wsgi:application} --bind 0.0.0.0:8000
```

If you need to target a different settings module (for example `project.settings.production`), set `DJANGO_WSGI_MODULE` before launching Gunicorn (e.g., `DJANGO_WSGI_MODULE=project.wsgi:application`).

## Docker deployment

Build and run using Docker Compose (or `docker build` / `docker run`). The container entrypoint automatically runs migrations and then launches Gunicorn using the same `DJANGO_WSGI_MODULE` environment variable.

```bash
docker compose up --build web
```

Override `GUNICORN_BIND` or `GUNICORN_EXTRA_ARGS` in the environment to customize the bind address or Gunicorn flags when running in Docker.
