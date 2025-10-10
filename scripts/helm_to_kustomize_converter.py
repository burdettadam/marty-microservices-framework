#!/usr/bin/env python3
"""
Helm to Kustomize Converter

This tool converts Helm charts to Kustomize manifests for the Marty Microservices Framework.
It analyzes Helm templates and values to generate corresponding Kustomize base and overlay structures.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import click
import yaml


class HelmToKustomizeConverter:
    """Converts Helm charts to Kustomize manifests."""

    def __init__(self, helm_chart_path: str, output_path: str, service_name: str):
        self.helm_chart_path = Path(helm_chart_path)
        self.output_path = Path(output_path)
        self.service_name = service_name
        self.temp_dir = None

    def convert(self, values_files: list[str] | None = None, validate: bool = True) -> bool:
        """
        Convert Helm chart to Kustomize manifests.

        Args:
            values_files: List of values files to use for conversion
            validate: Whether to validate the conversion

        Returns:
            True if conversion successful, False otherwise
        """
        try:
            click.echo(f"Converting Helm chart from {self.helm_chart_path} to {self.output_path}")

            # Create temporary directory for intermediate files
            self.temp_dir = tempfile.mkdtemp()

            # Step 1: Extract Helm templates
            helm_manifests = self._render_helm_templates(values_files or [])

            # Step 2: Parse and categorize manifests
            parsed_manifests = self._parse_manifests(helm_manifests)

            # Step 3: Generate Kustomize base
            self._generate_base_manifests(parsed_manifests)

            # Step 4: Generate overlays for different environments
            self._generate_overlays(values_files or [])

            # Step 5: Validate conversion if requested
            if validate:
                self._validate_conversion()

            click.echo(f"✅ Conversion completed successfully! Output: {self.output_path}")
            return True

        except (subprocess.CalledProcessError, FileNotFoundError, yaml.YAMLError) as e:
            click.echo(f"❌ Conversion failed: {str(e)}", err=True)
            return False
        finally:
            if self.temp_dir:
                shutil.rmtree(self.temp_dir)

    def _render_helm_templates(self, values_files: list[str]) -> str:
        """Render Helm templates to YAML manifests."""
        cmd = ["helm", "template", self.service_name, str(self.helm_chart_path)]

        # Add values files if provided
        for values_file in values_files:
            cmd.extend(["-f", values_file])

        # Add default namespace
        cmd.extend(["--namespace", "default"])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Failed to render Helm templates: {e.stderr}") from e

    def _parse_manifests(self, yaml_content: str) -> dict[str, list[dict]]:
        """Parse YAML manifests and categorize by kind."""
        manifests = {"base": [], "overlays": {}}

        # Split YAML documents
        docs = yaml.safe_load_all(yaml_content)

        for doc in docs:
            if not doc:
                continue

            kind = doc.get("kind", "").lower()

            # Categorize manifests
            if kind in ["deployment", "service", "configmap", "serviceaccount"]:
                manifests["base"].append(doc)
            elif kind in ["hpa", "pdb", "servicemonitor", "podmonitor"]:
                manifests["base"].append(doc)
            elif kind in ["ingress", "networkpolicy"]:
                manifests["base"].append(doc)
            else:
                # Custom resources or environment-specific manifests
                manifests["base"].append(doc)

        return manifests

    def _generate_base_manifests(self, parsed_manifests: dict[str, Any]) -> None:
        """Generate Kustomize base manifests."""
        base_dir = self.output_path / "base"
        base_dir.mkdir(parents=True, exist_ok=True)

        resources = []

        # Group manifests by kind
        manifest_groups = {}
        for manifest in parsed_manifests["base"]:
            kind = manifest["kind"].lower()
            if kind not in manifest_groups:
                manifest_groups[kind] = []
            manifest_groups[kind].append(manifest)

        # Write manifests to separate files
        for kind, manifests in manifest_groups.items():
            filename = f"{kind}.yaml"
            filepath = base_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                for i, manifest in enumerate(manifests):
                    if i > 0:
                        f.write("---\n")
                    # Clean up manifest (remove Helm-specific annotations)
                    cleaned_manifest = self._clean_manifest(manifest)
                    yaml.dump(cleaned_manifest, f, default_flow_style=False)

            resources.append(filename)

        # Generate kustomization.yaml
        kustomization = {
            "apiVersion": "kustomize.config.k8s.io/v1beta1",
            "kind": "Kustomization",
            "resources": sorted(resources)
        }

        with open(base_dir / "kustomization.yaml", "w", encoding="utf-8") as f:
            yaml.dump(kustomization, f, default_flow_style=False)

    def _clean_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]:
        """Clean Helm-specific annotations and labels from manifest."""
        cleaned = manifest.copy()

        # Remove Helm-specific metadata
        if "metadata" in cleaned:
            metadata = cleaned["metadata"]

            # Remove Helm annotations
            if "annotations" in metadata:
                annotations = metadata["annotations"]
                helm_annotations = [k for k in annotations.keys() if k.startswith("meta.helm.sh")]
                for key in helm_annotations:
                    del annotations[key]
                if not annotations:
                    del metadata["annotations"]

            # Clean up labels
            if "labels" in metadata:
                labels = metadata["labels"]
                helm_labels = [k for k in labels.keys() if k.startswith("helm.sh")]
                for key in helm_labels:
                    del labels[key]

        # Replace service name with template placeholder
        cleaned_yaml = yaml.dump(cleaned, default_flow_style=False)
        cleaned_yaml = cleaned_yaml.replace(self.service_name, "microservice-template")

        return yaml.safe_load(cleaned_yaml)

    def _generate_overlays(self, _values_files: list[str]) -> None:
        """Generate Kustomize overlays for different environments."""
        overlays_dir = self.output_path / "overlays"

        # Create environment-specific overlays
        environments = ["dev", "staging", "prod"]

        for env in environments:
            env_dir = overlays_dir / env
            env_dir.mkdir(parents=True, exist_ok=True)

            # Generate namespace.yaml
            namespace_manifest = {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": f"{self.service_name}-{env}",
                    "labels": {
                        "app.kubernetes.io/name": self.service_name,
                        "environment": env
                    }
                }
            }

            with open(env_dir / "namespace.yaml", "w", encoding="utf-8") as f:
                yaml.dump(namespace_manifest, f, default_flow_style=False)

            # Generate patch file for environment-specific changes
            patch_deployment = {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "microservice-template"},
                "spec": {
                    "replicas": 1 if env == "dev" else 2,
                    "template": {
                        "spec": {
                            "containers": [{
                                "name": "microservice-template",
                                "env": [
                                    {"name": "APP_ENVIRONMENT", "value": env}
                                ]
                            }]
                        }
                    }
                }
            }

            with open(env_dir / "patch-deployment.yaml", "w", encoding="utf-8") as f:
                yaml.dump(patch_deployment, f, default_flow_style=False)

            # Generate kustomization.yaml for overlay
            kustomization = {
                "apiVersion": "kustomize.config.k8s.io/v1beta1",
                "kind": "Kustomization",
                "namespace": f"{self.service_name}-{env}",
                "resources": [
                    "namespace.yaml",
                    "../../base"
                ],
                "patches": [
                    {"path": "patch-deployment.yaml"}
                ],
                "configMapGenerator": [{
                    "name": "microservice-template-config",
                    "behavior": "merge",
                    "literals": [
                        f"environment={env}",
                        "otlp_endpoint=http://otel-collector.monitoring:4317"
                    ]
                }]
            }

            with open(env_dir / "kustomization.yaml", "w", encoding="utf-8") as f:
                yaml.dump(kustomization, f, default_flow_style=False)

    def _validate_conversion(self) -> None:
        """Validate that the converted Kustomize manifests work correctly."""
        click.echo("Validating conversion...")

        # Test that kustomize build works
        for env in ["dev", "staging", "prod"]:
            overlay_path = self.output_path / "overlays" / env
            try:
                cmd = ["kustomize", "build", str(overlay_path)]
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                click.echo(f"✅ {env} overlay validation passed")
            except subprocess.CalledProcessError as e:
                raise ValueError(f"Validation failed for {env} overlay: {e.stderr}") from e


@click.command()
@click.option("--helm-chart-path", required=True, help="Path to Helm chart directory")
@click.option("--output-path", required=True, help="Output path for Kustomize manifests")
@click.option("--service-name", required=True, help="Name of the service")
@click.option("--values-file", multiple=True, help="Helm values files to use (can specify multiple)")
@click.option("--validate/--no-validate", default=True, help="Validate conversion output")
def convert_helm_to_kustomize(
    helm_chart_path: str,
    output_path: str,
    service_name: str,
    values_file: tuple[str, ...],
    validate: bool
):
    """Convert Helm charts to Kustomize manifests."""
    converter = HelmToKustomizeConverter(helm_chart_path, output_path, service_name)
    success = converter.convert(list(values_file), validate)

    if not success:
        exit(1)


if __name__ == "__main__":
    convert_helm_to_kustomize()
