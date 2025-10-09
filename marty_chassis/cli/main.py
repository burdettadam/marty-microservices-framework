"""
CLI tool for the Marty Chassis.

This module provides the command-line interface for scaffolding new services,
generating configurations, and managing chassis-based projects.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import click
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from marty_chassis.config import ChassisConfig, Environment
from marty_chassis.service_mesh import ManifestGenerator
from marty_chassis.templates import ServiceTemplate, TemplateGenerator

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="marty-chassis")
def cli():
    """Marty Chassis - Enterprise Microservices Framework CLI"""
    pass


@cli.command()
@click.argument("service_name")
@click.option(
    "--type",
    "service_type",
    type=click.Choice(["fastapi", "grpc", "hybrid"]),
    default="fastapi",
    help="Type of service to create",
)
@click.option(
    "--output-dir", "-o", default=".", help="Output directory for the new service"
)
@click.option("--template", "-t", help="Custom template to use")
@click.option("--no-docker", is_flag=True, help="Skip Docker configuration")
@click.option("--no-k8s", is_flag=True, help="Skip Kubernetes manifests")
@click.option(
    "--service-mesh",
    type=click.Choice(["none", "istio", "linkerd"]),
    default="istio",
    help="Service mesh to generate manifests for",
)
@click.option("--no-tests", is_flag=True, help="Skip test files")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
def new_service(
    service_name: str,
    service_type: str,
    output_dir: str,
    template: Optional[str],
    no_docker: bool,
    no_k8s: bool,
    service_mesh: str,
    no_tests: bool,
    interactive: bool,
):
    """Create a new microservice from template."""
    console.print(
        f"[bold green]Creating new {service_type} service: {service_name}[/bold green]"
    )

    # Interactive mode
    if interactive:
        service_type = Prompt.ask(
            "Service type", choices=["fastapi", "grpc", "hybrid"], default=service_type
        )

        if not no_docker:
            no_docker = not Confirm.ask("Include Docker configuration?", default=True)

        if not no_k8s:
            no_k8s = not Confirm.ask("Include Kubernetes manifests?", default=True)

        if not no_k8s:
            service_mesh = Prompt.ask(
                "Service mesh",
                choices=["none", "istio", "linkerd"],
                default=service_mesh,
            )

        if not no_tests:
            no_tests = not Confirm.ask("Include test files?", default=True)

    # Validate service name
    if not service_name.replace("-", "").replace("_", "").isalnum():
        console.print(
            "[red]Error: Service name must be alphanumeric (hyphens and underscores allowed)[/red]"
        )
        sys.exit(1)

    # Create output directory
    service_dir = Path(output_dir) / service_name
    if service_dir.exists():
        if not Confirm.ask(f"Directory {service_dir} already exists. Continue?"):
            sys.exit(0)

    try:
        # Generate service from template
        generator = TemplateGenerator()

        template_data = {
            "service_name": service_name,
            "service_type": service_type,
            "include_docker": not no_docker,
            "include_k8s": not no_k8s,
            "include_tests": not no_tests,
            "python_package": service_name.replace("-", "_"),
        }

        generator.generate_service(
            service_name=service_name,
            service_type=service_type,
            output_dir=str(service_dir),
            template_data=template_data,
            custom_template=template,
        )

        # Generate Kubernetes and service mesh manifests
        if not no_k8s:
            manifest_generator = ManifestGenerator(service_name)
            manifest_dir = service_dir / "k8s"

            console.print(f"[blue]Generating {service_mesh} manifests...[/blue]")
            manifest_generator.generate_all_manifests(
                output_dir=manifest_dir,
                service_mesh=service_mesh,
                include_monitoring=True,
            )
            console.print(
                f"[green]✓[/green] {service_mesh.title()} manifests generated in {manifest_dir}"
            )

        console.print(
            f"[green]✓[/green] Service '{service_name}' created successfully!"
        )
        console.print(f"[blue]Location:[/blue] {service_dir.absolute()}")

        # Show next steps
        console.print("\n[bold yellow]Next steps:[/bold yellow]")
        console.print(f"1. cd {service_name}")
        console.print("2. uv sync --extra dev")
        console.print("3. marty-chassis run")

    except Exception as e:
        console.print(f"[red]Error creating service: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--config-file", "-c", help="Configuration file path")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", type=int, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload (development only)")
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    help="Log level",
)
def run(
    config_file: Optional[str],
    host: str,
    port: Optional[int],
    reload: bool,
    log_level: Optional[str],
):
    """Run a chassis-based service."""
    try:
        # Load configuration
        if config_file:
            config = ChassisConfig.from_yaml(config_file)
        else:
            config = ChassisConfig.from_env()

        # Override with CLI options
        if port:
            config.service.port = port
        if host != "0.0.0.0":
            config.service.host = host
        if log_level:
            config.observability.log_level = log_level

        console.print(f"[green]Starting service: {config.service.name}[/green]")
        console.print(f"[blue]Host:[/blue] {config.service.host}")
        console.print(f"[blue]Port:[/blue] {config.service.port}")
        console.print(f"[blue]Environment:[/blue] {config.environment}")

        # Try to import and run the service
        try:
            import uvicorn
            from main import app  # Assumes the service has a main.py with app

            uvicorn.run(
                app,
                host=config.service.host,
                port=config.service.port,
                reload=reload,
                log_level=log_level.lower() if log_level else "info",
            )
        except ImportError:
            console.print(
                "[red]Error: Could not find service application. Make sure you're in a service directory with main.py[/red]"
            )
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Error running service: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option(
    "--environment",
    "-e",
    type=click.Choice(["development", "testing", "staging", "production"]),
    default="development",
    help="Environment to generate config for",
)
@click.option("--output", "-o", default="config.yaml", help="Output file path")
@click.option("--service-name", required=True, help="Service name")
def init_config(environment: str, output: str, service_name: str):
    """Initialize a new configuration file."""
    try:
        # Create default configuration
        config = ChassisConfig(
            environment=Environment(environment),
            service=ChassisConfig.model_fields["service"].default_factory()(
                name=service_name,
                version="1.0.0",
                description=f"{service_name} microservice",
            ),
        )

        # Save to file
        config.to_yaml(output)

        console.print(f"[green]✓[/green] Configuration file created: {output}")
        console.print(f"[blue]Environment:[/blue] {environment}")
        console.print(f"[blue]Service:[/blue] {service_name}")

    except Exception as e:
        console.print(f"[red]Error creating configuration: {e}[/red]")
        sys.exit(1)


@cli.command()
def list_templates():
    """List available service templates."""
    console.print("[bold green]Available Service Templates[/bold green]\n")

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Description")

    templates = [
        (
            "fastapi",
            "REST API",
            "FastAPI-based REST service with authentication and metrics",
        ),
        ("grpc", "gRPC", "gRPC service with reflection and middleware"),
        ("hybrid", "REST + gRPC", "Combined FastAPI and gRPC service"),
        ("minimal", "Minimal", "Minimal service template"),
        ("database", "Database", "Service with database integration"),
        ("event-driven", "Events", "Event-driven service with message queues"),
    ]

    for name, type_name, description in templates:
        table.add_row(name, type_name, description)

    console.print(table)


@cli.command()
@click.argument("service_dir", default=".")
def validate(service_dir: str):
    """Validate a chassis-based service."""
    service_path = Path(service_dir)

    console.print(f"[blue]Validating service in: {service_path.absolute()}[/blue]\n")

    checks = [
        ("Configuration file", lambda: (service_path / "config.yaml").exists()),
        ("Main application", lambda: (service_path / "main.py").exists()),
        (
            "Requirements file",
            lambda: (service_path / "requirements.txt").exists()
            or (service_path / "pyproject.toml").exists(),
        ),
        ("Tests directory", lambda: (service_path / "tests").is_dir()),
        ("Docker configuration", lambda: (service_path / "Dockerfile").exists()),
    ]

    all_passed = True

    for check_name, check_func in checks:
        try:
            passed = check_func()
            status = "[green]✓[/green]" if passed else "[red]✗[/red]"
            console.print(f"{status} {check_name}")
            if not passed:
                all_passed = False
        except Exception:
            console.print(f"[red]✗[/red] {check_name} (error during check)")
            all_passed = False

    if all_passed:
        console.print("\n[green]All validation checks passed![/green]")
    else:
        console.print(
            "\n[yellow]Some validation checks failed. See above for details.[/yellow]"
        )


@cli.command()
def version():
    """Show version information."""
    console.print("[bold blue]Marty Chassis[/bold blue]")
    console.print("Version: 0.1.0")
    console.print("Enterprise Microservices Framework")


def main():
    """Main CLI entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Unexpected error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
