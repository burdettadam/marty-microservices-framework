#!/usr/bin/env python3
"""
Service Generator for Marty Microservices Framework

This script generates new microservices from templates using DRY patterns.
Supports FastAPI, gRPC, hybrid, and minimal service architectures.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("Error: Jinja2 is required for template generation.")
    print("Install it with: uv add jinja2 or uv sync")
    sys.exit(1)


class ServiceGenerator:
    """Generator for Marty services using DRY templates."""

    def __init__(self, templates_dir: Path, output_dir: Path) -> None:
        """
        Initialize the service generator.

        Args:
            templates_dir: Directory containing service templates
            output_dir: Directory where generated services will be created
        """
        self.templates_dir = templates_dir
        self.output_dir = output_dir

        # Ensure directories exist
        if not templates_dir.exists():
            raise ValueError(f"Templates directory not found: {templates_dir}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=True,
        )

    def generate_service(self, service_type: str, service_name: str, **options: Any) -> None:
        """
        Generate a new service from templates.

        Args:
            service_type: Type of service (grpc, fastapi, hybrid, minimal)
            service_name: Name of the service (e.g., "document-validator")
            **options: Additional template variables including service mesh options
        """
        # Validate service type
        valid_types = ["grpc", "fastapi", "hybrid", "minimal"]
        if service_type not in valid_types:
            raise ValueError(f"Service type must be one of: {valid_types}")

        # Prepare template variables
        template_vars = self._prepare_template_vars(service_name, **options)

        # Determine template directory
        if service_type == "grpc":
            template_subdir = "service/grpc_service"
        elif service_type == "fastapi":
            template_subdir = "service/fastapi_service"
        elif service_type == "hybrid":
            template_subdir = "service/hybrid_service"
        else:  # minimal
            template_subdir = "service/minimal_service"

        # Generate service files
        self._generate_from_template_dir(template_subdir, template_vars)

        # Generate Kubernetes manifests
        self._generate_k8s_manifests(template_vars)

        print(f"✅ Generated {service_type} service: {service_name}")
        print(f"📁 Location: {self.output_dir / template_vars['service_package']}")
        print("🚀 To get started:")
        print("   1. Review and customize the generated configuration")
        print("   2. Add any new dependencies with: uv add <package-name>")
        print("   3. Implement your business logic in the service class")
        print("   4. Add your API endpoints or gRPC methods")
        print(f"   5. Run tests: uv run pytest src/{template_vars['service_package']}/tests/")
        print(
            f"   6. Build Docker image: docker build -f src/{template_vars['service_package']}/Dockerfile ."
        )

        # Add service mesh deployment instructions
        if template_vars.get("service_mesh_enabled", False):
            print("🕸️  Service Mesh Configuration:")
            print("   7. Deploy with service mesh: kubectl apply -k k8s/overlays/service-mesh/")
            print("   8. Apply service mesh policies: kubectl apply -f k8s/service-mesh/")
            print(
                f"   9. Verify mesh injection: kubectl get pods -n {template_vars.get('namespace', 'default')} -o wide"
            )

    def _prepare_template_vars(self, service_name: str, **options: Any) -> dict[str, Any]:
        """
        Prepare template variables from service name and options.

        Args:
            service_name: Service name (e.g., "document-validator")
            **options: Additional options

        Returns:
            Dictionary of template variables
        """
        # Convert service name to different formats
        service_package = service_name.replace("-", "_")
        service_class = self._to_class_name(service_name)

        # Default template variables
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
            # Service mesh options
            "service_mesh_enabled": options.get("service_mesh", False),
            "service_mesh_type": options.get("service_mesh_type", "istio"),
            "namespace": options.get("namespace", "microservice-framework"),
            "domain": options.get("domain", "framework.local"),
            "package_name": service_package.replace("_", "."),
            # Kubernetes options
            "HTTP_PORT": options.get("http_port", 8080),
            "GRPC_PORT": options.get("grpc_port", 50051),
            "NAMESPACE": options.get("namespace", "microservice-framework"),
            "SERVICE_NAME": service_name,
            "PACKAGE_NAME": service_package.replace("_", "."),
            "DOMAIN": options.get("domain", "framework.local"),
        }

        # Add any additional options
        template_vars.update(options)

        return template_vars

    def _to_class_name(self, service_name: str) -> str:
        """
        Convert service name to PascalCase class name.

        Args:
            service_name: Service name (e.g., "document-validator")

        Returns:
            PascalCase class name (e.g., "DocumentValidator")
        """
        # Split on hyphens and underscores, capitalize each part
        parts = re.split(r"[-_]", service_name)
        return "".join(part.capitalize() for part in parts if part)

    def _generate_from_template_dir(
        self, template_subdir: str, template_vars: dict[str, Any]
    ) -> None:
        """
        Generate files from a template directory.

        Args:
            template_subdir: Subdirectory containing templates
            template_vars: Variables for template rendering
        """
        template_dir = self.templates_dir / template_subdir
        if not template_dir.exists():
            raise ValueError(f"Template directory not found: {template_dir}")

        # Create output directory structure
        service_dir = self.output_dir / template_vars["service_package"]
        service_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (service_dir / "app").mkdir(exist_ok=True)
        (service_dir / "app" / "api").mkdir(exist_ok=True)
        (service_dir / "app" / "core").mkdir(exist_ok=True)
        (service_dir / "app" / "services").mkdir(exist_ok=True)
        (service_dir / "tests").mkdir(exist_ok=True)

        # Generate files from templates
        for template_file in template_dir.glob("*.j2"):
            self._generate_file(template_file, template_subdir, service_dir, template_vars)

    def _generate_file(
        self,
        template_file: Path,
        template_subdir: str,
        service_dir: Path,
        template_vars: dict[str, Any],
    ) -> None:
        """
        Generate a single file from template.

        Args:
            template_file: Path to template file
            template_subdir: Template subdirectory
            service_dir: Output service directory
            template_vars: Template variables
        """
        # Determine output file path
        relative_path = template_file.relative_to(self.templates_dir / template_subdir)
        output_file = service_dir / relative_path.with_suffix("")

        # Map template files to output locations
        file_mapping = {
            "main.py": service_dir / "main.py",
            "config.py": service_dir / "app" / "core" / "config.py",
            "service.py": service_dir
            / "app"
            / "services"
            / f"{template_vars['service_package']}_service.py",
            "grpc_service.py": service_dir / "app" / "services" / "grpc_service.py",
            "routes.py": service_dir / "app" / "api" / "routes.py",
            "middleware.py": service_dir / "app" / "core" / "middleware.py",
            "error_handlers.py": service_dir / "app" / "core" / "error_handlers.py",
            "test_service.py": service_dir
            / "tests"
            / f"test_{template_vars['service_package']}_service.py",
            "Dockerfile": service_dir / "Dockerfile",
            "service.proto": service_dir / f"{template_vars['service_package']}.proto",
        }

        # Get actual output path
        output_path = file_mapping.get(relative_path.name, output_file)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Render template
        template_path = f"{template_subdir}/{relative_path.name}"
        template = self.env.get_template(template_path)
        rendered_content = template.render(**template_vars)

        # Write output file
        output_path.write_text(rendered_content, encoding="utf-8")
        print(f"  📝 Generated: {output_path.relative_to(self.output_dir.parent)}")

    def _generate_k8s_manifests(self, template_vars: dict[str, Any]) -> None:
        """
        Generate Kubernetes manifests with service mesh configurations.

        Args:
            template_vars: Template variables including service mesh options
        """
        service_dir = self.output_dir / template_vars["service_package"]
        k8s_dir = service_dir / "k8s"

        # Create k8s directory structure
        k8s_dir.mkdir(exist_ok=True)
        (k8s_dir / "base").mkdir(exist_ok=True)
        (k8s_dir / "overlays").mkdir(exist_ok=True)
        (k8s_dir / "service-mesh").mkdir(exist_ok=True)

        # Copy base Kubernetes templates
        template_k8s_dir = self.templates_dir / "microservice_project_template" / "k8s"
        if template_k8s_dir.exists():
            self._copy_and_render_k8s_templates(template_k8s_dir, k8s_dir, template_vars)

        print(
            f"  🎛️  Generated Kubernetes manifests in {k8s_dir.relative_to(self.output_dir.parent)}"
        )

    def _copy_and_render_k8s_templates(
        self, source_dir: Path, target_dir: Path, template_vars: dict[str, Any]
    ) -> None:
        """
        Copy and render Kubernetes template files.

        Args:
            source_dir: Source template directory
            target_dir: Target output directory
            template_vars: Variables for template rendering
        """
        for item in source_dir.rglob("*"):
            if item.is_file() and not item.name.startswith("."):
                # Calculate relative path
                rel_path = item.relative_to(source_dir)
                target_path = target_dir / rel_path

                # Ensure target directory exists
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Read and render template if it's a YAML file
                if item.suffix in [".yaml", ".yml"]:
                    content = item.read_text(encoding="utf-8")

                    # Simple template variable substitution
                    for key, value in template_vars.items():
                        content = content.replace(f"{{{{{key.upper()}}}}}", str(value))
                        content = content.replace(f"{{{{{key}}}}}", str(value))

                    # Replace template-specific placeholders
                    content = content.replace(
                        "microservice-template", template_vars["service_name"]
                    )
                    content = content.replace(
                        "microservice_template", template_vars["service_package"]
                    )

                    target_path.write_text(content, encoding="utf-8")
                else:
                    # Copy non-template files as-is
                    target_path.write_bytes(item.read_bytes())

                print(f"    📄 Generated K8s: {target_path.relative_to(target_dir.parent)}")


def main() -> None:
    """Main entry point for service generation."""
    parser = argparse.ArgumentParser(
        description="Generate new Marty services using DRY templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s grpc document-validator
  %(prog)s fastapi user-management --http-port 8080
  %(prog)s hybrid payment-processor --grpc-port 50052 --http-port 8082
  %(prog)s grpc certificate-checker --description "Certificate validation service"
  %(prog)s fastapi order-service --service-mesh --service-mesh-type istio
  %(prog)s hybrid user-service --service-mesh --namespace production --domain api.company.com

Service Types:
  grpc      - gRPC-only service with protocol buffers
  fastapi   - HTTP REST API service with FastAPI
  hybrid    - Combined gRPC and FastAPI service
  minimal   - Minimal service with base configuration only

Service Mesh:
  --service-mesh          - Enable service mesh configurations (Istio/Linkerd)
  --service-mesh-type     - Choose between 'istio' or 'linkerd' (default: istio)
  --namespace            - Kubernetes namespace for deployment
  --domain               - Service domain for external access
        """,
    )

    parser.add_argument(
        "service_type",
        choices=["grpc", "fastapi", "hybrid", "minimal"],
        help="Type of service to generate",
    )

    parser.add_argument("service_name", help="Name of the service (e.g., document-validator)")

    parser.add_argument("--description", help="Service description")

    parser.add_argument(
        "--author",
        default="Marty Development Team",
        help="Author name (default: Marty Development Team)",
    )

    parser.add_argument("--grpc-port", type=int, default=50051, help="gRPC port (default: 50051)")

    parser.add_argument(
        "--http-port",
        type=int,
        default=8080,
        help="HTTP port for FastAPI services (default: 8080)",
    )

    parser.add_argument("--output-dir", type=Path, help="Output directory (default: ./src)")

    # Service mesh options
    parser.add_argument(
        "--service-mesh", action="store_true", help="Enable service mesh configuration"
    )

    parser.add_argument(
        "--service-mesh-type",
        choices=["istio", "linkerd"],
        default="istio",
        help="Service mesh type (default: istio)",
    )

    parser.add_argument(
        "--namespace",
        default="microservice-framework",
        help="Kubernetes namespace (default: microservice-framework)",
    )

    parser.add_argument(
        "--domain",
        default="framework.local",
        help="Service domain (default: framework.local)",
    )

    args = parser.parse_args()

    # Determine directories
    script_dir = Path(__file__).parent
    templates_root = script_dir.parent
    templates_dir = templates_root
    output_dir = args.output_dir or (Path.cwd() / "src")

    # Validate inputs
    if not (templates_dir / "service").exists():
        print(f"Error: Service templates directory not found: {templates_dir / 'service'}")
        sys.exit(1)

    # Validate service name
    if not re.match(r"^[a-z][a-z0-9-]*[a-z0-9]$", args.service_name):
        print("Error: Service name must be lowercase with hyphens (e.g., document-validator)")
        sys.exit(1)

    # Check if service already exists
    service_package = args.service_name.replace("-", "_")
    if (output_dir / service_package).exists():
        response = input(f"Service '{service_package}' already exists. Overwrite? (y/N): ")
        if response.lower() != "y":
            print("Generation cancelled.")
            sys.exit(0)

    try:
        # Create generator and generate service
        generator = ServiceGenerator(templates_dir, output_dir)
        generator.generate_service(
            service_type=args.service_type,
            service_name=args.service_name,
            description=args.description,
            author=args.author,
            grpc_port=args.grpc_port,
            http_port=args.http_port,
            # Service mesh options
            service_mesh=args.service_mesh,
            service_mesh_type=args.service_mesh_type,
            namespace=args.namespace,
            domain=args.domain,
        )

    except Exception as e:
        print(f"Error generating service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
