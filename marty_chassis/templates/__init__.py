"""
Template system for the Marty Chassis.

This module provides the template engine for generating service scaffolding,
configuration files, and deployment manifests.
"""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, Template

from marty_chassis.exceptions import TemplateError
from marty_chassis.logger import get_logger

logger = get_logger(__name__)


class ServiceTemplate:
    """Represents a service template."""

    def __init__(self, name: str, template_dir: Path, description: str = ""):
        self.name = name
        self.template_dir = template_dir
        self.description = description

    def get_files(self) -> List[Path]:
        """Get all template files."""
        if not self.template_dir.exists():
            return []

        files = []
        for file_path in self.template_dir.rglob("*"):
            if file_path.is_file():
                files.append(file_path.relative_to(self.template_dir))

        return files


class TemplateGenerator:
    """Template generator for creating services from templates."""

    def __init__(self, templates_dir: Optional[Path] = None):
        if templates_dir is None:
            # Use package templates directory
            package_dir = Path(__file__).parent.parent
            templates_dir = package_dir / "templates"

        self.templates_dir = templates_dir
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        logger.info("Template generator initialized", templates_dir=str(templates_dir))

    def get_available_templates(self) -> List[ServiceTemplate]:
        """Get list of available service templates."""
        templates = []

        if not self.templates_dir.exists():
            return templates

        for template_dir in self.templates_dir.iterdir():
            if template_dir.is_dir() and not template_dir.name.startswith("."):
                description = ""
                desc_file = template_dir / "template.json"
                if desc_file.exists():
                    import json

                    try:
                        with open(desc_file) as f:
                            meta = json.load(f)
                            description = meta.get("description", "")
                    except Exception:
                        pass

                templates.append(
                    ServiceTemplate(
                        name=template_dir.name,
                        template_dir=template_dir,
                        description=description,
                    )
                )

        return templates

    def generate_service(
        self,
        service_name: str,
        service_type: str,
        output_dir: str,
        template_data: Dict[str, Any],
        custom_template: Optional[str] = None,
    ) -> None:
        """Generate a service from template."""
        template_name = custom_template or service_type
        template_dir = self.templates_dir / template_name

        if not template_dir.exists():
            raise TemplateError(f"Template '{template_name}' not found")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Generating service from template",
            service_name=service_name,
            template=template_name,
            output_dir=output_dir,
        )

        # Add common template variables
        template_data.update(
            {
                "service_name": service_name,
                "service_type": service_type,
                "python_package": service_name.replace("-", "_"),
            }
        )

        # Process all files in template
        for file_path in template_dir.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith("."):
                relative_path = file_path.relative_to(template_dir)
                self._process_template_file(
                    file_path,
                    output_path / relative_path,
                    template_data,
                )

        logger.info("Service generation completed", service_name=service_name)

    def _process_template_file(
        self,
        template_file: Path,
        output_file: Path,
        template_data: Dict[str, Any],
    ) -> None:
        """Process a single template file."""
        # Create output directory
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Process filename template
        output_filename = self._render_template_string(
            str(output_file.name),
            template_data,
        )
        final_output_file = output_file.parent / output_filename

        try:
            # Read template content
            with open(template_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Check if file should be templated (based on extension or content)
            if self._should_template_file(template_file, content):
                # Render template
                rendered_content = self._render_template_string(content, template_data)

                # Write rendered content
                with open(final_output_file, "w", encoding="utf-8") as f:
                    f.write(rendered_content)

                logger.debug("Templated file created", file=str(final_output_file))
            else:
                # Copy file as-is
                shutil.copy2(template_file, final_output_file)
                logger.debug("File copied", file=str(final_output_file))

        except Exception as e:
            raise TemplateError(f"Failed to process template file {template_file}: {e}")

    def _should_template_file(self, file_path: Path, content: str) -> bool:
        """Determine if a file should be processed as a template."""
        # Template files based on extension
        template_extensions = {
            ".py",
            ".yaml",
            ".yml",
            ".json",
            ".toml",
            ".md",
            ".txt",
            ".sh",
        }

        if file_path.suffix in template_extensions:
            return True

        # Check for Jinja2 syntax in content
        if "{{" in content or "{%" in content:
            return True

        return False

    def _render_template_string(
        self, template_string: str, data: Dict[str, Any]
    ) -> str:
        """Render a template string with data."""
        try:
            template = Template(template_string)
            return template.render(**data)
        except Exception as e:
            raise TemplateError(f"Failed to render template: {e}")

    def generate_file_from_template(
        self,
        template_name: str,
        output_path: Path,
        template_data: Dict[str, Any],
    ) -> None:
        """Generate a single file from template."""
        try:
            template = self.jinja_env.get_template(template_name)
            rendered_content = template.render(**template_data)

            # Create output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write rendered content
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(rendered_content)

            logger.info(
                "File generated from template",
                template=template_name,
                output=str(output_path),
            )

        except Exception as e:
            raise TemplateError(
                f"Failed to generate file from template {template_name}: {e}"
            )


# Create template directories and files
def create_built_in_templates(templates_dir: Path) -> None:
    """Create built-in service templates."""
    templates_dir.mkdir(parents=True, exist_ok=True)

    # FastAPI template
    _create_fastapi_template(templates_dir / "fastapi")

    # gRPC template
    _create_grpc_template(templates_dir / "grpc")

    # Hybrid template
    _create_hybrid_template(templates_dir / "hybrid")


def _create_fastapi_template(template_dir: Path) -> None:
    """Create FastAPI service template."""
    template_dir.mkdir(parents=True, exist_ok=True)

    # Main application file
    main_py = """\"\"\"
{{ service_name }} - FastAPI Service

Generated by Marty Chassis
\"\"\"

from fastapi import FastAPI, Depends
from marty_chassis import create_fastapi_service, ChassisConfig
from marty_chassis.security import get_current_user, require_permission

# Load configuration
config = ChassisConfig.from_env()

# Create FastAPI app with chassis features
app = create_fastapi_service(
    name="{{ service_name }}",
    config=config,
    enable_auth=True,
    enable_metrics=True,
    enable_health_checks=True,
)

@app.get("/")
async def root():
    \"\"\"Root endpoint.\"\"\"
    return {"message": "Hello from {{ service_name }}!", "version": "{{ template_data.get('version', '1.0.0') }}"}

@app.get("/protected")
async def protected_endpoint(current_user=Depends(get_current_user(app.state.security_middleware))):
    \"\"\"Protected endpoint requiring authentication.\"\"\"
    return {"message": f"Hello {current_user.username}!", "user_id": current_user.sub}

@app.get("/admin")
async def admin_endpoint(
    _=Depends(require_permission("admin", app.state.security_middleware))
):
    \"\"\"Admin endpoint requiring admin permission.\"\"\"
    return {"message": "Admin access granted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=config.service.host,
        port=config.service.port,
        reload=config.service.debug,
    )
"""

    with open(template_dir / "main.py", "w") as f:
        f.write(main_py)

    # Configuration file
    config_yaml = """environment: development

service:
  name: {{ service_name }}
  version: 1.0.0
  description: {{ service_name }} microservice
  host: 0.0.0.0
  port: 8080
  debug: true

security:
  jwt_secret_key: "your-secret-key-change-this-in-production"
  jwt_algorithm: HS256
  jwt_expiration_minutes: 30
  enable_cors: true
  cors_origins:
    - "*"

observability:
  service_name: {{ service_name }}
  log_level: INFO
  log_format: json
  enable_metrics: true
  enable_tracing: true

resilience:
  enable_circuit_breaker: true
  circuit_breaker_failure_threshold: 5
  circuit_breaker_recovery_timeout: 60
  retry_attempts: 3
  timeout_seconds: 30
"""

    with open(template_dir / "config.yaml", "w") as f:
        f.write(config_yaml)

    # Add common project configuration
    _create_common_project_files(template_dir)


def _create_grpc_template(template_dir: Path) -> None:
    """Create gRPC service template."""
    template_dir.mkdir(parents=True, exist_ok=True)

    # gRPC service implementation
    main_py = """\"\"\"
{{ service_name }} - gRPC Service

Generated by Marty Chassis
\"\"\"

import asyncio
from marty_chassis import ChassisConfig
from marty_chassis.factories.grpc_factory import create_grpc_service, run_grpc_server

# Load configuration
config = ChassisConfig.from_env()

async def main():
    \"\"\"Main entry point.\"\"\"

    # Create gRPC service
    builder = create_grpc_service(
        service_name="{{ service_name }}",
        config=config,
        enable_auth=True,
        enable_metrics=True,
        enable_reflection=True,
    )

    # TODO: Add your gRPC servicers here
    # builder.add_servicer(YourServicer(), YourServiceStub)

    # Build and run server
    server = builder.build_async_server()
    await run_grpc_server(server)

if __name__ == "__main__":
    asyncio.run(main())
"""

    with open(template_dir / "main.py", "w") as f:
        f.write(main_py)

    # Configuration file
    config_yaml = """environment: development

service:
  name: {{ service_name }}
  version: 1.0.0
  description: {{ service_name }} gRPC microservice
  host: 0.0.0.0
  port: 50051
  debug: true

security:
  jwt_secret_key: "your-secret-key-change-this-in-production"
  jwt_algorithm: HS256
  jwt_expiration_minutes: 30

observability:
  service_name: {{ service_name }}
  log_level: INFO
  log_format: json
  enable_metrics: true
  enable_tracing: true

resilience:
  enable_circuit_breaker: true
  circuit_breaker_failure_threshold: 5
  circuit_breaker_recovery_timeout: 60
  retry_attempts: 3
  timeout_seconds: 30
"""

    with open(template_dir / "config.yaml", "w") as f:
        f.write(config_yaml)

    # Add common project configuration
    _create_common_project_files(template_dir)


def _create_hybrid_template(template_dir: Path) -> None:
    """Create hybrid service template."""
    template_dir.mkdir(parents=True, exist_ok=True)

    # Hybrid service implementation
    main_py = """\"\"\"
{{ service_name }} - Hybrid Service (FastAPI + gRPC)

Generated by Marty Chassis
\"\"\"

import asyncio
from marty_chassis import ChassisConfig
from marty_chassis.factories.hybrid_factory import create_hybrid_service, run_hybrid_service

# Load configuration
config = ChassisConfig.from_env()

async def main():
    \"\"\"Main entry point.\"\"\"

    # Create hybrid service
    builder = create_hybrid_service(
        service_name="{{ service_name }}",
        config=config,
        enable_fastapi=True,
        enable_grpc=True,
        enable_auth=True,
        enable_metrics=True,
    )

    # TODO: Add your gRPC servicers here
    # builder.add_grpc_servicer(YourServicer(), YourServiceStub)

    # Build and run service
    service = builder.build()
    await run_hybrid_service(service)

if __name__ == "__main__":
    asyncio.run(main())
"""

    with open(template_dir / "main.py", "w") as f:
        f.write(main_py)

    # Configuration file
    config_yaml = """environment: development

service:
  name: {{ service_name }}
  version: 1.0.0
  description: {{ service_name }} hybrid microservice
  http_host: 0.0.0.0
  http_port: 8080
  grpc_host: 0.0.0.0
  grpc_port: 50051
  debug: true

security:
  jwt_secret_key: "your-secret-key-change-this-in-production"
  jwt_algorithm: HS256
  jwt_expiration_minutes: 30
  enable_cors: true
  cors_origins:
    - "*"

observability:
  service_name: {{ service_name }}
  log_level: INFO
  log_format: json
  enable_metrics: true
  enable_tracing: true

resilience:
  enable_circuit_breaker: true
  circuit_breaker_failure_threshold: 5
  circuit_breaker_recovery_timeout: 60
  retry_attempts: 3
  timeout_seconds: 30
"""

    with open(template_dir / "config.yaml", "w") as f:
        f.write(config_yaml)

    # Add common project configuration
    _create_common_project_files(template_dir)


def _create_common_project_files(template_dir: Path) -> None:
    """Create common project files like pyproject.toml and Dockerfile."""

    # pyproject.toml file
    pyproject_toml = """[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{{ service_name }}"
version = "0.1.0"
description = "{{ service_name }} microservice built with Marty Chassis"
requires-python = ">=3.10"
dependencies = [
    "marty-chassis[all]",
    "uvicorn[standard]>=0.24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.1.6",
    "mypy>=1.7.0",
]

[tool.hatch.build.targets.wheel]
packages = ["."]

[tool.ruff]
line-length = 88
target-version = "py310"
select = ["E", "F", "I", "B", "UP"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.10"
check_untyped_defs = true
"""

    with open(template_dir / "pyproject.toml", "w") as f:
        f.write(pyproject_toml)

    # Dockerfile
    dockerfile = """FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-cache

COPY . .

EXPOSE 8080

CMD ["uv", "run", "python", "main.py"]
"""

    with open(template_dir / "Dockerfile", "w") as f:
        f.write(dockerfile)
