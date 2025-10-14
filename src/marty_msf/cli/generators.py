#!/usr/bin/env python3
"""
Service and Plugin generators for MMF CLI

Contains generators for creating services and plugins that integrate with MMF infrastructure.
"""

import re
from pathlib import Path
from typing import Any

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    # Fallback for when Jinja2 is not available
    Environment = None
    FileSystemLoader = None


class ServiceGenerator:
    """Generates comprehensive services using Jinja2 templates."""

    def __init__(self, templates_dir: Path = None, output_dir: Path = None):
        """Initialize the service generator."""
        # Get the root directory of the project (assuming we're in src/marty_msf/cli)
        project_root = Path(__file__).parent.parent.parent.parent
        self.templates_dir = templates_dir or (project_root / "services")
        self.output_dir = output_dir or (project_root / "plugins")

        # Ensure directories exist
        if not self.templates_dir.exists():
            raise ValueError(f"Templates directory not found: {self.templates_dir}")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Jinja2 environment if available
        if Environment and FileSystemLoader:
            self.env = Environment(
                loader=FileSystemLoader(self.templates_dir),
                trim_blocks=True,
                lstrip_blocks=True,
                autoescape=True,
            )
        else:
            self.env = None
            print("⚠️  Jinja2 not available, using fallback generation")

    def generate_service(self, service_type: str, service_name: str, **options: Any) -> bool:
        """
        Generate a new service from templates.

        Args:
            service_type: Type of service (grpc, fastapi, hybrid, minimal, production)
            service_name: Name of the service (e.g., "document-validator")
            **options: Additional template variables including service mesh options

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate service type
            valid_types = ["fastapi", "simple-fastapi", "production", "grpc", "hybrid", "minimal"]
            if service_type not in valid_types:
                print(f"Error: Service type must be one of: {valid_types}")
                return False

            # Validate service name
            if not re.match(r"^[a-z][a-z0-9-]*[a-z0-9]$", service_name):
                print("Error: Service name must be lowercase with hyphens (e.g., document-validator)")
                return False

            # Check if service already exists
            service_package = service_name.replace("-", "_")
            service_dir = self.output_dir / service_package
            if service_dir.exists():
                print(f"Error: Service '{service_name}' already exists at {service_dir}")
                return False

            # Prepare template variables
            template_vars = self._prepare_template_vars(service_name, **options)

            # Use Jinja2 templates if available, otherwise fallback
            if self.env:
                return self._generate_with_jinja2(service_type, template_vars)
            else:
                return self._generate_fallback(service_type, template_vars)

        except Exception as e:
            print(f"Error generating service: {e}")
            return False

    def _prepare_template_vars(self, service_name: str, **options: Any) -> dict[str, Any]:
        """Prepare template variables from service name and options."""
        service_package = service_name.replace("-", "_")
        service_class = self._to_class_name(service_name)

        template_vars = {
            "service_name": service_name,
            "service_package": service_package,
            "service_class": service_class,
            "service_description": options.get(
                "description",
                f"{service_class} service for {service_name} functionality",
            ),
            "author": options.get("author", "Marty Development Team"),
            "grpc_port": options.get("grpc_port", 50051),
            "http_port": options.get("http_port", 8080),
            "service_mesh_enabled": options.get("service_mesh", False),
            "service_mesh_type": options.get("service_mesh_type", "istio"),
            "namespace": options.get("namespace", "microservice-framework"),
            "domain": options.get("domain", "framework.local"),
            "package_name": service_package.replace("_", "."),
            "HTTP_PORT": options.get("http_port", 8080),
            "GRPC_PORT": options.get("grpc_port", 50051),
            "NAMESPACE": options.get("namespace", "microservice-framework"),
            "SERVICE_NAME": service_name,
            "PACKAGE_NAME": service_package.replace("_", "."),
            "DOMAIN": options.get("domain", "framework.local"),
        }

        template_vars.update(options)
        return template_vars

    def _to_class_name(self, service_name: str) -> str:
        """Convert service name to PascalCase class name."""
        parts = re.split(r"[-_]", service_name)
        return "".join(part.capitalize() for part in parts if part)

    def _generate_with_jinja2(self, service_type: str, template_vars: dict[str, Any]) -> bool:
        """Generate service using Jinja2 templates."""
        # Determine template directory
        template_mapping = {
            "fastapi": "fastapi/fastapi-service",
            "simple-fastapi": "fastapi/simple-fastapi-service",
            "production": "fastapi/production-service",
            "grpc": "grpc/grpc_service",
            "hybrid": "hybrid/hybrid_service",
            "minimal": "shared/config-service"
        }

        template_subdir = template_mapping.get(service_type)
        if not template_subdir:
            print(f"Error: Unsupported service type: {service_type}")
            return False

        # Generate service files
        self._generate_from_template_dir(template_subdir, template_vars)

        # Generate additional production-ready components
        if service_type == "production":
            self._generate_production_components(template_vars)

        # Generate Kubernetes manifests (skip for simple templates)
        if service_type not in ["simple-fastapi"]:
            self._generate_k8s_manifests(template_vars)

        print(f"✅ Generated {service_type} service: {template_vars['service_name']}")
        print(f"📁 Location: {self.output_dir / template_vars['service_package']}")

        self._print_getting_started_instructions(service_type, template_vars)
        return True

    def _generate_fallback(self, service_type: str, template_vars: dict[str, Any]) -> bool:
        """Generate service using fallback method (minimal FastAPI service)."""
        print("Using fallback generation (install Jinja2 for full template support)")

        # Create basic directory structure
        service_dir = self.output_dir / template_vars["service_package"]
        service_dir.mkdir(parents=True, exist_ok=True)

        # Generate minimal FastAPI service
        self._generate_minimal_fastapi_service(service_dir, template_vars)

        print(f"✅ Generated minimal {service_type} service: {template_vars['service_name']}")
        print(f"📁 Location: {service_dir}")
        return True

    def _generate_minimal_fastapi_service(self, service_dir: Path, template_vars: dict[str, Any]) -> None:
        """Generate a minimal FastAPI service as fallback."""
        # Create directory structure
        (service_dir / "app").mkdir(exist_ok=True)
        (service_dir / "tests").mkdir(exist_ok=True)

        # Generate main.py
        main_content = f'''"""
Main entry point for {template_vars["service_name"]} service.
"""

import uvicorn
from app import create_app

def main():
    """Main entry point for the service."""
    app = create_app()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port={template_vars["http_port"]},
        log_level="info"
    )

if __name__ == "__main__":
    main()
'''
        (service_dir / "main.py").write_text(main_content)

        # Generate app/__init__.py
        app_init_content = f'''"""
FastAPI application factory for {template_vars["service_name"]} service.
"""

from fastapi import FastAPI

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="{template_vars['service_class']} Service",
        description="{template_vars['service_description']}",
        version="1.0.0"
    )

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {{"status": "healthy", "service": "{template_vars['service_name']}"}}

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {{"message": "Welcome to {template_vars['service_class']} Service"}}

    return app
'''
        (service_dir / "app" / "__init__.py").write_text(app_init_content)

        # Generate requirements.txt
        requirements_content = '''fastapi>=0.104.0
uvicorn[standard]>=0.24.0
'''
        (service_dir / "requirements.txt").write_text(requirements_content)

        # Generate Dockerfile
        dockerfile_content = f'''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE {template_vars["http_port"]}

CMD ["python", "main.py"]
'''
        (service_dir / "Dockerfile").write_text(dockerfile_content)

    def _generate_from_template_dir(self, template_subdir: str, template_vars: dict[str, Any]) -> None:
        """Generate files from a template directory."""
        template_dir = self.templates_dir / template_subdir
        if not template_dir.exists():
            raise ValueError(f"Template directory not found: {template_dir}")

        service_dir = self.output_dir / template_vars["service_package"]
        service_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (service_dir / "app").mkdir(exist_ok=True)
        (service_dir / "tests").mkdir(exist_ok=True)

        # Generate files from templates
        for template_file in template_dir.glob("*.j2"):
            self._generate_file(template_file, template_subdir, service_dir, template_vars)

    def _generate_file(self, template_file: Path, template_subdir: str, service_dir: Path, template_vars: dict[str, Any]) -> None:
        """Generate a single file from template."""
        relative_path = template_file.relative_to(self.templates_dir / template_subdir)

        # File mapping for proper output locations
        file_mapping = {
            "main.py": service_dir / "main.py",
            "config.py": service_dir / "app" / "core" / "config.py",
            "service.py": service_dir / "app" / "services" / f"{template_vars['service_package']}_service.py",
            "routes.py": service_dir / "app" / "api" / "routes.py",
            "Dockerfile": service_dir / "Dockerfile",
            "requirements.txt": service_dir / "requirements.txt",
        }

        template_name = relative_path.with_suffix("").name
        output_path = file_mapping.get(template_name, service_dir / relative_path.with_suffix(""))

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Render template
        template_path = f"{template_subdir}/{relative_path.name}"
        template = self.env.get_template(template_path)
        rendered_content = template.render(**template_vars)

        output_path.write_text(rendered_content, encoding="utf-8")
        print(f"  📝 Generated: {output_path.relative_to(self.output_dir.parent)}")

    def _generate_production_components(self, template_vars: dict[str, Any]) -> None:
        """Generate additional production-ready components."""
        service_dir = self.output_dir / template_vars["service_package"]

        # Create additional directories
        (service_dir / "app" / "models").mkdir(exist_ok=True)
        (service_dir / "app" / "utils").mkdir(exist_ok=True)
        (service_dir / "app" / "middleware").mkdir(exist_ok=True)
        (service_dir / "tests" / "unit").mkdir(exist_ok=True)
        (service_dir / "tests" / "integration").mkdir(exist_ok=True)
        (service_dir / "docs").mkdir(exist_ok=True)

        self._generate_readme(service_dir, template_vars)
        print("  📋 Generated production-ready structure with comprehensive documentation")

    def _generate_readme(self, service_dir: Path, template_vars: dict[str, Any]) -> None:
        """Generate comprehensive README for the service."""
        readme_content = f'''# {template_vars["service_class"]} Service

A production-ready microservice built with the Marty Microservices Framework.

## Quick Start

```bash
# Install dependencies
uv sync

# Run the service
python main.py
```

## API Endpoints

- **Health Check**: `GET /health`
- **API Documentation**: `GET /docs`

## Development

```bash
# Run tests
uv run pytest tests/

# Build Docker image
docker build -t {template_vars["service_name"]}:latest .

# Run container
docker run -p {template_vars["http_port"]}:{template_vars["http_port"]} {template_vars["service_name"]}:latest
```

## Architecture

This service follows the Marty Microservices Framework patterns for production readiness.
'''

        (service_dir / "README.md").write_text(readme_content, encoding="utf-8")

    def _generate_k8s_manifests(self, template_vars: dict[str, Any]) -> None:
        """Generate Kubernetes manifests."""
        service_dir = self.output_dir / template_vars["service_package"]
        k8s_dir = service_dir / "k8s"
        k8s_dir.mkdir(exist_ok=True)

        # Basic deployment manifest
        deployment_content = f'''apiVersion: apps/v1
kind: Deployment
metadata:
  name: {template_vars["service_name"]}
  labels:
    app: {template_vars["service_name"]}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {template_vars["service_name"]}
  template:
    metadata:
      labels:
        app: {template_vars["service_name"]}
    spec:
      containers:
      - name: {template_vars["service_name"]}
        image: {template_vars["service_name"]}:latest
        ports:
        - containerPort: {template_vars["http_port"]}
        env:
        - name: PORT
          value: "{template_vars["http_port"]}"
        livenessProbe:
          httpGet:
            path: /health
            port: {template_vars["http_port"]}
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: {template_vars["http_port"]}
          initialDelaySeconds: 5
          periodSeconds: 5
'''
        (k8s_dir / "deployment.yaml").write_text(deployment_content)

        # Basic service manifest
        service_content = f'''apiVersion: v1
kind: Service
metadata:
  name: {template_vars["service_name"]}-service
  labels:
    app: {template_vars["service_name"]}
spec:
  selector:
    app: {template_vars["service_name"]}
  ports:
  - port: 80
    targetPort: {template_vars["http_port"]}
    protocol: TCP
  type: ClusterIP
'''
        (k8s_dir / "service.yaml").write_text(service_content)

        print(f"  🎛️  Generated Kubernetes manifests in {k8s_dir.relative_to(self.output_dir.parent)}")

    def _print_getting_started_instructions(self, service_type: str, template_vars: dict[str, Any]) -> None:
        """Print getting started instructions based on service type."""
        print("🚀 To get started:")
        print("   1. cd to the service directory")
        print("   2. Install dependencies: uv sync")
        print("   3. Run the service: python main.py")
        print(f"   4. Test health: curl http://localhost:{template_vars['http_port']}/health")
        print(f"   5. View docs: http://localhost:{template_vars['http_port']}/docs")

        if service_type == "production":
            print("   6. Run tests: uv run pytest tests/")
            print("   7. Build for production: docker build -t service:latest .")

    # Legacy compatibility methods
    def generate_plugin(self, name: str) -> bool:
        """Generate a plugin (legacy compatibility)."""
        return self.generate_service("production", name)

    def add_service_to_plugin(self, plugin_name: str, service_name: str) -> bool:
        """Add a new service to existing plugin (legacy compatibility)."""
        print("Note: add_service_to_plugin is deprecated. Use 'marty service init' instead.")
        return False

    def generate_plugin_with_features(self, name: str, features: list = None, services: list = None) -> bool:
        """Generate a plugin with specific features (legacy compatibility)."""
        # Map to service generation for backward compatibility
        return self.generate_service("production", name, features=features or [])


# Legacy alias for backward compatibility
MinimalPluginGenerator = ServiceGenerator
