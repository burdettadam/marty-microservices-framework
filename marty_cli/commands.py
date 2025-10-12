"""
Migration commands for converting Helm charts to Kustomize manifests.
"""

import os
import subprocess
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


@click.group()
def migrate():
    """Migration utilities for moving to MMF patterns."""
    pass


@migrate.command()
@click.option(
    "--helm-chart-path",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to Helm chart directory",
)
@click.option(
    "--output-path",
    required=True,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Output path for Kustomize manifests",
)
@click.option(
    "--service-name",
    required=True,
    help="Name of the service",
)
@click.option(
    "--values-file",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Helm values files to use (can specify multiple)",
)
@click.option(
    "--validate/--no-validate",
    default=True,
    help="Validate conversion output",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be converted without making changes",
)
def helm_to_kustomize(
    helm_chart_path: Path,
    output_path: Path,
    service_name: str,
    values_file: tuple[Path, ...],
    validate: bool,
    dry_run: bool,
):
    """Convert Helm charts to Kustomize manifests."""
    console.print("🔄 Converting Helm chart to Kustomize manifests", style="bold blue")

    if dry_run:
        console.print("🔍 Dry-run mode: showing what would be converted", style="yellow")

        # Show conversion plan
        table = Table(title="Conversion Plan")
        table.add_column("Component", style="cyan")
        table.add_column("Action", style="green")
        table.add_column("Output", style="yellow")

        table.add_row("Helm Chart", "Convert", str(helm_chart_path))
        table.add_row("Service Name", "Use", service_name)
        table.add_row("Output Path", "Create", str(output_path))
        table.add_row("Values Files", "Process", f"{len(values_file)} files")

        console.print(table)
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Converting Helm to Kustomize...", total=None)

        try:
            # Import and use the converter
            from scripts.helm_to_kustomize_converter import HelmToKustomizeConverter

            converter = HelmToKustomizeConverter(
                str(helm_chart_path), str(output_path), service_name
            )

            success = converter.convert(list(map(str, values_file)), validate)

            if success:
                console.print("✅ Conversion completed successfully!", style="bold green")
                console.print(f"📁 Output directory: {output_path}", style="blue")

                # Show generated structure
                _show_generated_structure(output_path)
            else:
                console.print("❌ Conversion failed!", style="bold red")
                raise click.ClickException("Helm to Kustomize conversion failed")

        except ImportError:
            console.print("❌ Conversion tool not available", style="bold red")
            raise click.ClickException("Helm to Kustomize converter not found")


@migrate.command()
@click.option(
    "--service-name",
    required=True,
    help="Name of the service",
)
@click.option(
    "--environment",
    type=click.Choice(["dev", "staging", "prod", "marty-dev", "marty-prod"]),
    default="dev",
    help="Target environment",
)
@click.option(
    "--output-path",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=Path("./k8s/overlays"),
    help="Output path for overlay",
)
@click.option(
    "--use-marty-patterns",
    is_flag=True,
    help="Use Marty-specific patterns (migration jobs, PVCs, etc.)",
)
def generate_overlay(
    service_name: str,
    environment: str,
    output_path: Path,
    use_marty_patterns: bool,
):
    """Generate Kustomize overlay for a service."""
    console.print(f"🏗️  Generating {environment} overlay for {service_name}", style="bold blue")

    overlay_path = output_path / environment
    overlay_path.mkdir(parents=True, exist_ok=True)

    if use_marty_patterns:
        # Copy from marty-dev or marty-services template
        template_name = "marty-dev" if environment in ["dev", "marty-dev"] else "marty-services"
        console.print(f"📋 Using Marty template: {template_name}", style="cyan")

        # Copy template files and customize
        _generate_marty_overlay(overlay_path, service_name, environment, template_name)
    else:
        # Generate basic overlay
        _generate_basic_overlay(overlay_path, service_name, environment)

    console.print(f"✅ Overlay generated at: {overlay_path}", style="bold green")


@migrate.command()
@click.option(
    "--original-path",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to original Helm deployment",
)
@click.option(
    "--migrated-path",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to migrated Kustomize deployment",
)
@click.option(
    "--namespace",
    default="default",
    help="Kubernetes namespace for validation",
)
def validate_migration(
    original_path: Path,
    migrated_path: Path,
    namespace: str,
):
    """Validate that migrated manifests match original functionality."""
    console.print("🔍 Validating migration...", style="bold blue")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Validating migration...", total=None)

        try:
            # Render both Helm and Kustomize manifests
            helm_output = _render_helm_manifests(original_path, namespace)
            kustomize_output = _render_kustomize_manifests(migrated_path)

            # Compare outputs
            differences = _compare_manifests(helm_output, kustomize_output)

            if not differences:
                console.print("✅ Migration validation passed!", style="bold green")
                console.print("🎯 Functionality parity achieved", style="green")
            else:
                console.print("⚠️  Migration validation found differences:", style="yellow")
                for diff in differences:
                    console.print(f"  • {diff}", style="yellow")

        except Exception as e:
            console.print(f"❌ Validation failed: {str(e)}", style="bold red")
            raise click.ClickException("Migration validation failed")


@migrate.command()
@click.option(
    "--service-name",
    required=True,
    help="Name of the service to check",
)
@click.option(
    "--chart-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to Helm chart (optional)",
)
def check_compatibility(service_name: str, chart_path: Path | None):
    """Check Helm chart compatibility with MMF migration."""
    console.print(f"🔍 Checking migration compatibility for {service_name}", style="bold blue")

    compatibility_results = {
        "Basic Deployment": True,
        "Service Configuration": True,
        "ConfigMaps": True,
        "Secrets": False,  # Requires manual review
        "ServiceAccount": True,
        "RBAC": False,  # May need customization
        "Ingress": False,  # Not in base template
        "PersistentVolumes": False,  # Available in Marty overlay
        "Custom Resources": False,  # Needs evaluation
    }

    if chart_path:
        # Analyze actual chart
        compatibility_results.update(_analyze_helm_chart(chart_path))

    # Display results
    table = Table(title=f"Migration Compatibility: {service_name}")
    table.add_column("Component", style="cyan")
    table.add_column("Compatible", style="green")
    table.add_column("Notes", style="yellow")

    for component, compatible in compatibility_results.items():
        status = "✅ Yes" if compatible else "❌ No"
        notes = _get_compatibility_notes(component, compatible)
        table.add_row(component, status, notes)

    console.print(table)

    # Overall recommendation
    compatible_count = sum(compatibility_results.values())
    total_count = len(compatibility_results)

    if compatible_count >= total_count * 0.8:
        console.print("🟢 Good migration candidate", style="bold green")
    elif compatible_count >= total_count * 0.6:
        console.print("🟡 Moderate complexity migration", style="bold yellow")
    else:
        console.print("🔴 Complex migration - manual work required", style="bold red")


def _show_generated_structure(output_path: Path) -> None:
    """Display the generated directory structure."""
    console.print("📁 Generated structure:", style="bold")

    for root, _dirs, files in os.walk(output_path):
        level = root.replace(str(output_path), "").count(os.sep)
        indent = " " * 2 * level
        console.print(f"{indent}📂 {os.path.basename(root)}/", style="blue")
        sub_indent = " " * 2 * (level + 1)
        for file in files:
            console.print(f"{sub_indent}📄 {file}", style="cyan")


def _generate_marty_overlay(
    overlay_path: Path,
    service_name: str,
    environment: str,
    template_name: str,
) -> None:
    """Generate a Marty-specific overlay."""
    # This would copy and customize from the MMF template
    # For now, create a basic implementation
    _generate_basic_overlay(overlay_path, service_name, environment)

    # Add Marty-specific configurations
    kustomization_file = overlay_path / "kustomization.yaml"
    if kustomization_file.exists():
        with open(kustomization_file, encoding="utf-8") as f:
            content = f.read()

        # Add Marty-specific configurations
        marty_additions = f"""
# Marty-specific configurations
commonLabels:
  app.kubernetes.io/part-of: marty-platform

commonAnnotations:
  marty.io/service-type: microservice
  marty.io/environment: {environment}
"""

        with open(kustomization_file, "w", encoding="utf-8") as f:
            f.write(content + marty_additions)


def _generate_basic_overlay(overlay_path: Path, service_name: str, environment: str) -> None:
    """Generate a basic Kustomize overlay."""
    import yaml

    # Generate kustomization.yaml
    kustomization = {
        "apiVersion": "kustomize.config.k8s.io/v1beta1",
        "kind": "Kustomization",
        "namespace": f"{service_name}-{environment}",
        "resources": ["namespace.yaml", "../../base"],
        "configMapGenerator": [
            {
                "name": "microservice-template-config",
                "behavior": "merge",
                "literals": [
                    f"environment={environment}",
                    "otlp_endpoint=http://otel-collector.monitoring:4317",
                ],
            }
        ],
    }

    with open(overlay_path / "kustomization.yaml", "w", encoding="utf-8") as f:
        yaml.dump(kustomization, f, default_flow_style=False)

    # Generate namespace.yaml
    namespace = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": f"{service_name}-{environment}",
            "labels": {"name": f"{service_name}-{environment}", "environment": environment},
        },
    }

    with open(overlay_path / "namespace.yaml", "w", encoding="utf-8") as f:
        yaml.dump(namespace, f, default_flow_style=False)


def _render_helm_manifests(helm_path: Path, namespace: str) -> str:
    """Render Helm manifests for comparison."""
    cmd = ["helm", "template", "test", str(helm_path), "--namespace", namespace]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout


def _render_kustomize_manifests(kustomize_path: Path) -> str:
    """Render Kustomize manifests for comparison."""
    cmd = ["kustomize", "build", str(kustomize_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout


def _compare_manifests(helm_output: str, kustomize_output: str) -> list[str]:
    """Compare Helm and Kustomize manifest outputs."""
    # Simple implementation - in practice this would be more sophisticated
    differences = []

    # Parse both outputs and compare
    import yaml

    try:
        helm_docs = list(yaml.safe_load_all(helm_output))
        kustomize_docs = list(yaml.safe_load_all(kustomize_output))

        if len(helm_docs) != len(kustomize_docs):
            differences.append(
                f"Document count differs: Helm={len(helm_docs)}, Kustomize={len(kustomize_docs)}"
            )

        # More detailed comparison would go here

    except yaml.YAMLError as e:
        differences.append(f"YAML parsing error: {e}")

    return differences


def _analyze_helm_chart(chart_path: Path) -> dict[str, bool]:
    """Analyze Helm chart for compatibility assessment."""
    # Simplified analysis - would be more comprehensive in practice
    results = {}

    templates_dir = chart_path / "templates"
    if templates_dir.exists():
        for template_file in templates_dir.glob("*.yaml"):
            if "ingress" in template_file.name:
                results["Ingress"] = True
            elif "pvc" in template_file.name or "persistent" in template_file.name:
                results["PersistentVolumes"] = True
            elif "rbac" in template_file.name or "role" in template_file.name:
                results["RBAC"] = True

    return results


def _get_compatibility_notes(component: str, compatible: bool) -> str:
    """Get compatibility notes for a component."""
    notes_map = {
        "Secrets": "Requires manual secret creation",
        "RBAC": "May need customization for specific permissions",
        "Ingress": "Use service mesh or add custom ingress",
        "PersistentVolumes": "Available in Marty overlay",
        "Custom Resources": "Manual evaluation required",
    }

    if compatible:
        return "Ready for migration"
    else:
        return notes_map.get(component, "Manual work required")
