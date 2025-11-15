"""
Workspace provisioning orchestrator.

This module handles the complete lifecycle of workspace provisioning,
from initial creation to deployment and configuration.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any

from sqlalchemy.orm import Session

from .. import models


class ProvisioningError(Exception):
    """Raised when workspace provisioning fails."""
    pass


class WorkspaceOrchestrator:
    """
    Orchestrates workspace provisioning.

    Currently supports Docker-based local provisioning.
    Can be extended to support DigitalOcean, AWS, bare metal, etc.
    """

    def __init__(self, db: Session):
        self.db = db
        self.workspace_template_dir = Path(__file__).parent.parent.parent.parent / "workspace"
        self.deployments_dir = Path("/tmp/adim_deployments")  # Change to persistent location in production
        self.deployments_dir.mkdir(exist_ok=True)

    def provision_workspace(self, workspace: models.Workspace) -> Dict[str, Any]:
        """
        Provision a new workspace instance.

        Args:
            workspace: Workspace model instance

        Returns:
            Dictionary with provisioning details

        Raises:
            ProvisioningError: If provisioning fails
        """
        try:
            self._log(workspace, "info", f"Starting provisioning for workspace {workspace.workspace_id}")

            if workspace.deployment_type == "cloud":
                return self._provision_docker_workspace(workspace)
            elif workspace.deployment_type == "bare_metal":
                return self._register_bare_metal(workspace)
            else:
                raise ProvisioningError(f"Unknown deployment type: {workspace.deployment_type}")

        except Exception as e:
            self._log(workspace, "error", f"Provisioning failed: {str(e)}")
            workspace.mark_failed()
            self.db.commit()
            raise ProvisioningError(f"Failed to provision workspace: {str(e)}")

    def _provision_docker_workspace(self, workspace: models.Workspace) -> Dict[str, Any]:
        """
        Provision workspace using Docker containers.

        Creates isolated Docker environment with:
        - PostgreSQL database
        - Redis cache
        - Qdrant vector DB
        - Django application
        """
        workspace_dir = self.deployments_dir / workspace.workspace_id

        # 1. Create workspace directory
        self._log(workspace, "info", "Creating workspace directory structure")
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir)
        workspace_dir.mkdir(parents=True)

        # 2. Copy workspace template
        self._log(workspace, "info", "Copying workspace template")
        self._copy_workspace_template(workspace_dir)

        # 3. Generate configuration
        self._log(workspace, "info", "Generating workspace configuration")
        ports = workspace.get_port_allocation()
        env_config = self._generate_env_config(workspace, ports)
        self._write_env_file(workspace_dir, env_config)

        # 4. Generate docker-compose.yml with unique ports
        self._log(workspace, "info", "Generating Docker Compose configuration")
        self._generate_docker_compose(workspace_dir, workspace, ports)

        # 5. Start Docker containers
        self._log(workspace, "info", "Starting Docker containers")
        self._start_docker_containers(workspace_dir, workspace)

        # 6. Run migrations
        self._log(workspace, "info", "Running database migrations")
        self._run_migrations(workspace_dir, workspace)

        # 7. Update workspace metadata
        instance_url = f"http://localhost:{ports['daphne']}"
        workspace.instance_url = instance_url
        workspace.ip_address = "127.0.0.1"
        workspace.mark_provisioned()

        self._log(
            workspace,
            "info",
            f"Workspace provisioned successfully at {instance_url}",
            data={"ports": ports}
        )

        self.db.commit()

        return {
            "workspace_id": workspace.workspace_id,
            "instance_url": instance_url,
            "ports": ports,
            "status": "active"
        }

    def _register_bare_metal(self, workspace: models.Workspace) -> Dict[str, Any]:
        """
        Register a bare metal workspace instance.

        This is for user-managed installations where they run the
        installation script on their own server.
        """
        self._log(workspace, "info", "Registering bare metal workspace")

        # For bare metal, we just mark it as provisioning
        # User will provide the instance_url when they complete installation
        workspace.status = "pending_registration"
        self.db.commit()

        return {
            "workspace_id": workspace.workspace_id,
            "status": "pending_registration",
            "message": "Workspace registered. Please complete installation using the provided script."
        }

    def _copy_workspace_template(self, target_dir: Path) -> None:
        """Copy workspace template to target directory."""
        if not self.workspace_template_dir.exists():
            raise ProvisioningError(f"Workspace template not found at {self.workspace_template_dir}")

        # Copy all files except .env and __pycache__
        for item in self.workspace_template_dir.iterdir():
            if item.name in ['.env', '__pycache__', '.git', 'venv', '.venv']:
                continue

            target = target_dir / item.name
            if item.is_dir():
                shutil.copytree(item, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            else:
                shutil.copy2(item, target)

    def _generate_env_config(self, workspace: models.Workspace, ports: Dict[str, int]) -> Dict[str, str]:
        """Generate environment configuration for workspace."""
        import secrets
        from cryptography.fernet import Fernet

        return {
            # Django Core
            "SECRET_KEY": secrets.token_urlsafe(50),
            "DEBUG": "0",
            "ALLOWED_HOSTS": f"localhost,127.0.0.1",

            # Deployment
            "DEPLOYMENT_TYPE": "local",
            "GATE_ID": workspace.workspace_id,
            "CUSTOMER_ID": workspace.workspace_id,

            # Database
            "POSTGRES_DB": f"adim_{workspace.workspace_id}",
            "POSTGRES_USER": f"adim_{workspace.workspace_id}",
            "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
            "POSTGRES_HOST": "db",
            "POSTGRES_PORT": "5432",

            # Redis
            "REDIS_PASSWORD": secrets.token_urlsafe(32),

            # Qdrant
            "QDRANT_API_KEY": secrets.token_urlsafe(32),

            # Encryption
            "ENCRYPTION_KEY": Fernet.generate_key().decode(),

            # Ports (for reference, Docker handles mapping)
            "WEB_PORT": str(ports['daphne']),
        }

    def _write_env_file(self, workspace_dir: Path, config: Dict[str, str]) -> None:
        """Write .env file for workspace."""
        env_file = workspace_dir / ".env"
        with open(env_file, 'w') as f:
            f.write("# Auto-generated workspace configuration\n")
            f.write(f"# Generated: {models.datetime.now(models.timezone.utc).isoformat()}\n\n")
            for key, value in config.items():
                f.write(f"{key}={value}\n")

    def _generate_docker_compose(self, workspace_dir: Path, workspace: models.Workspace, ports: Dict[str, int]) -> None:
        """Generate docker-compose.yml with unique ports for this workspace."""
        compose_content = f"""version: "3.9"

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ${{POSTGRES_DB}}
      POSTGRES_USER: ${{POSTGRES_USER}}
      POSTGRES_PASSWORD: ${{POSTGRES_PASSWORD}}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 5s
      timeout: 3s
      retries: 15
    networks:
      - internal
    security_opt:
      - no-new-privileges:true
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    environment:
      REDIS_PASSWORD: ${{REDIS_PASSWORD}}
    command: >-
      sh -c "exec redis-server --save '' --appendonly no --requirepass \\"$${{REDIS_PASSWORD}}\\""
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "$$REDIS_PASSWORD", "ping"]
      interval: 5s
      timeout: 3s
      retries: 15
    networks:
      - internal
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    tmpfs:
      - /data
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:latest
    environment:
      QDRANT__SERVICE__API_KEY: ${{QDRANT_API_KEY}}
    expose:
      - "6333"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test:
        - "CMD-SHELL"
        - >-
          wget -qO- --header "api-key: $$QDRANT__SERVICE__API_KEY"
          http://localhost:6333/readyz | grep -q 'ready'
      interval: 5s
      timeout: 3s
      retries: 25
    networks:
      - internal
    security_opt:
      - no-new-privileges:true
    restart: unless-stopped

  web:
    build: .
    init: true
    environment:
      DJANGO_SETTINGS_MODULE: ${{DJANGO_SETTINGS_MODULE:-project.settings}}
      DJANGO_SECRET_KEY: ${{SECRET_KEY}}
      POSTGRES_DB: ${{POSTGRES_DB}}
      POSTGRES_USER: ${{POSTGRES_USER}}
      POSTGRES_PASSWORD: ${{POSTGRES_PASSWORD}}
      POSTGRES_HOST: db
      POSTGRES_PORT: "5432"
      REDIS_URL: redis://:${{REDIS_PASSWORD}}@redis:6379/0
      QDRANT_HOST: qdrant
      QDRANT_PORT: "6333"
      QDRANT_API_KEY: ${{QDRANT_API_KEY}}
      GUNICORN_BIND: 0.0.0.0:8000
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_started
    ports:
      - "{ports['daphne']}:8000"
    networks:
      - internal
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    tmpfs:
      - /tmp
    restart: unless-stopped

volumes:
  pgdata:
  qdrant_data:

networks:
  internal:
    driver: bridge
"""

        compose_file = workspace_dir / "docker-compose.yml"
        with open(compose_file, 'w') as f:
            f.write(compose_content)

    def _start_docker_containers(self, workspace_dir: Path, workspace: models.Workspace) -> None:
        """Start Docker containers for workspace."""
        try:
            result = subprocess.run(
                ["docker", "compose", "up", "--build", "-d"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout for building
            )

            if result.returncode != 0:
                raise ProvisioningError(f"Docker compose failed: {result.stderr}")

            self._log(workspace, "info", "Docker containers started successfully")

        except subprocess.TimeoutExpired:
            raise ProvisioningError("Docker compose timed out after 10 minutes")
        except FileNotFoundError:
            raise ProvisioningError("Docker not found. Please install Docker.")

    def _run_migrations(self, workspace_dir: Path, workspace: models.Workspace) -> None:
        """Run Django migrations in the workspace container."""
        try:
            # Wait a bit for containers to be fully ready
            import time
            time.sleep(5)

            result = subprocess.run(
                ["docker", "compose", "exec", "-T", "web", "python", "manage.py", "migrate", "--noinput"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                self._log(workspace, "warning", f"Migrations output: {result.stderr}")
                # Don't fail on migration errors - workspace might still be usable
            else:
                self._log(workspace, "info", "Database migrations completed")

        except subprocess.TimeoutExpired:
            self._log(workspace, "warning", "Migration command timed out")
        except Exception as e:
            self._log(workspace, "warning", f"Migration failed: {str(e)}")

    def stop_workspace(self, workspace: models.Workspace) -> None:
        """Stop and remove workspace containers."""
        workspace_dir = self.deployments_dir / workspace.workspace_id

        if not workspace_dir.exists():
            self._log(workspace, "warning", "Workspace directory not found, nothing to stop")
            return

        try:
            self._log(workspace, "info", "Stopping workspace containers")

            subprocess.run(
                ["docker", "compose", "down", "-v"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            self._log(workspace, "info", "Workspace containers stopped")
            workspace.mark_decommissioned()
            self.db.commit()

        except Exception as e:
            self._log(workspace, "error", f"Failed to stop workspace: {str(e)}")
            raise ProvisioningError(f"Failed to stop workspace: {str(e)}")

    def _log(
        self,
        workspace: models.Workspace,
        level: str,
        message: str,
        data: Dict[str, Any] | None = None
    ) -> None:
        """Add provisioning log entry."""
        log = models.ProvisioningLog(
            workspace=workspace,
            level=level,
            message=message,
            data=data or {}
        )
        self.db.add(log)
        self.db.flush()  # Flush to DB but don't commit yet
