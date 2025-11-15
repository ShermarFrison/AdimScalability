# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django 5.2.8 application with a multi-service architecture designed for scalability. The stack includes:
- **PostgreSQL** (database)
- **Redis** (caching)
- **Qdrant** (vector database)
- **Gunicorn** (production WSGI server)

## Development Commands

### Local Development Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Running the Application

**Local (with Gunicorn):**
```bash
python manage.py migrate
gunicorn project.wsgi:application --bind 0.0.0.0:8000
```

**Docker (recommended):**
```bash
docker compose up --build web
```

**Run individual services:**
```bash
docker compose up db redis qdrant  # Infrastructure only
```

### Django Management
```bash
python manage.py migrate           # Run migrations
python manage.py makemigrations    # Create new migrations
python manage.py createsuperuser   # Create admin user
python manage.py shell             # Django shell
```

## Architecture

### Service Dependencies
The application follows a strict dependency chain enforced by Docker healthchecks:
1. **db** (PostgreSQL) - Must be healthy before web starts
2. **redis** - Must be healthy before web starts
3. **qdrant** - Must be healthy before web starts
4. **web** - Django app served via Gunicorn

All services communicate over an **internal bridge network** with no external internet access for security.

### Environment Configuration
The application uses environment variables for configuration. Key variables:

**Database:**
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `POSTGRES_HOST`, `POSTGRES_PORT`

**Django:**
- `DJANGO_SETTINGS_MODULE` (default: `project.settings`)
- `DJANGO_WSGI_MODULE` (default: `project.wsgi:application`)
- `DJANGO_SECRET_KEY` (required in production)
- `DEBUG` (set to `0`, `false`, or `False` for production)
- `ALLOWED_HOSTS` (comma-separated)

**Services:**
- `REDIS_URL` (format: `redis://:password@host:port/db`)
- `REDIS_PASSWORD` (required)
- `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_API_KEY`

**Gunicorn:**
- `GUNICORN_BIND` (default: `0.0.0.0:8000`)
- `GUNICORN_EXTRA_ARGS` (additional Gunicorn flags)

### Docker Security Features
The deployment uses hardened Docker security:
- Non-root user (`app:app`) in the web container
- `security_opt: no-new-privileges:true` on all services
- `cap_drop: ALL` on redis and web
- Internal-only network (no external access)
- tmpfs mounts for ephemeral data
- Minimal Alpine-based images where possible

### Entry Point Behavior
`entrypoint.sh` automatically:
1. Runs database migrations (`python manage.py migrate --noinput`)
2. Starts Gunicorn with configured WSGI module and bind address

## Code Structure

- `project/` - Django project configuration
  - `settings.py` - Main settings (uses environment variables)
  - `wsgi.py` - WSGI application entry point
  - `urls.py` - URL routing
- `manage.py` - Django management script
- `requirements.txt` - Core Python dependencies
- `Dockerfile` - Installs additional dependencies (psycopg, django-redis, qdrant-client)

### Database
PostgreSQL is the primary database (configured in `settings.py:52-61`). The app uses Django's ORM with automatic connection pooling.

### Caching
Redis caching is optional - the app falls back to `LocMemCache` if `REDIS_URL` is not set (see `settings.py:64-78`).

### Qdrant Integration
Qdrant vector database is available at the host/port specified in environment variables. Client configuration should use `QDRANT_API_KEY` for authentication.

## Adding New Dependencies

**Python packages:**
1. Add to `requirements.txt` for base dependencies
2. Or add to `Dockerfile` RUN pip install line for service-specific deps (e.g., database drivers, clients)
3. Rebuild: `docker compose build web`

## Production Considerations

- Set `DEBUG=0` in production
- Use a strong `DJANGO_SECRET_KEY`
- Configure `ALLOWED_HOSTS` to match your domain(s)
- Review and set strong passwords for `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `QDRANT_API_KEY`
- Consider adding volume mounts for static files
- The current docker-compose network is internal-only; add a reverse proxy (nginx/traefik) for external access
