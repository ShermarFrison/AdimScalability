# AdimScalability

This repository is now a monolithic home for two distinct services:

- `workspace/` – the Django-based single-tenant workspace application (Gunicorn, PostgreSQL, Redis, Qdrant). This is the code that ultimately runs inside each customer instance.
- `meta_platform/` – the FastAPI-powered meta platform that manages meta users, workspace metadata, OTP issuance, and provisioning logs.

Both services share the same repository but run independently.

## Workspace service (Django)

All Django assets (project code, Dockerfile, entrypoint, requirements, etc.) live under `workspace/`.

```bash
cd workspace
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Environment variables should be stored in `workspace/.env` (see `workspace/docker-compose.yml` for required values). Once dependencies and env vars are configured:

```bash
python manage.py migrate
gunicorn ${DJANGO_WSGI_MODULE:-project.wsgi:application} --bind 0.0.0.0:8000
```

Docker assets also live inside `workspace/`:

```bash
cd workspace
docker compose up --build web
```

The Dockerfile and compose project behave the same way as before (run migrations via `entrypoint.sh`, then start Gunicorn), just namespaced inside the `workspace/` directory.

## Meta Platform (FastAPI)

The FastAPI service is responsible for user registration, workspace CRUD, OTP management, and the public `/api/otps/validate/` endpoint that client apps consume.

```bash
cd meta_platform
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Set `META_PLATFORM_DATABASE_URL` to point at your PostgreSQL instance (defaults to `postgresql+psycopg://meta_platform:meta_platform@localhost:5432/meta_platform`). Then run the API with Uvicorn:

```bash
uvicorn meta_platform.main:app --reload --host 0.0.0.0 --port 9000
```

The API surface mirrors the documented endpoints in `API_DOCUMENTATION.md` (register, `/api/workspaces/`, `/api/otps/validate/`, etc.) but is now implemented in FastAPI/SQLAlchemy instead of Django REST Framework.

## Repository layout

```
AdimScalability/
├── meta_platform/         # FastAPI meta platform (PostgreSQL + SQLAlchemy)
│   ├── app/
│   └── requirements.txt
├── workspace/             # Django workspace service + Docker assets
│   ├── manage.py
│   ├── project/
│   ├── meta_auth/
│   ├── workspaces/
│   ├── provisioning/
│   ├── Dockerfile
│   └── docker-compose.yml
├── API_DOCUMENTATION.md
├── deploy-pipeline.txt
└── … (docs, keys, etc.)
```

Use this README as the source of truth for where to run each service going forward.
