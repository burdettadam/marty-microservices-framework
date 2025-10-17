"""
Service Mesh Framework Module
Provides Python integration for service mesh deployment capabilities
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ServiceMeshManager:
    """
    Manager for service mesh deployment and configuration
    """

    def __init__(self, project_path: str | None = None):
        self.project_path = project_path
        self.lib_path = Path(__file__).parent / "service_mesh_lib.sh"
        self.production_manifests_path = Path(__file__).parent.parent.parent.parent.parent / "ops" / "service-mesh" / "production"

    def generate_deployment_script(
        self,
        project_name: str,
        output_dir: str,
        domain: str = "example.com",
        mesh_type: str = "istio"
    ) -> dict[str, str]:
        """
        Generate a deployment script for the project

        Args:
            project_name: Name of the project
            output_dir: Output directory for the deployment script
            domain: Domain name for the project
            mesh_type: Type of service mesh (istio/linkerd)

        Returns:
            Dictionary with generated file paths
        """
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # Create k8s/service-mesh directory
            k8s_path = output_path / "k8s" / "service-mesh"
            k8s_path.mkdir(parents=True, exist_ok=True)

            # Copy production manifests
            if self.production_manifests_path.exists():
                for manifest_file in self.production_manifests_path.glob("*.yaml"):
                    shutil.copy2(manifest_file, k8s_path)
                logger.info(f"Copied production manifests to {k8s_path}")
            else:
                logger.warning(f"Production manifests not found at {self.production_manifests_path}")

            # Generate deployment script using bash library
            script_path = output_path / "deploy-service-mesh.sh"

            env = os.environ.copy()
            env.update({
                "PROJECT_NAME": project_name,
                "PROJECT_DOMAIN": domain,
                "MESH_TYPE": mesh_type
            })

            # Call the bash function to generate the script
            cmd = [
                "bash", "-c", f"""
                source '{self.lib_path}'
                msf_generate_deployment_script '{project_name}' '{output_path}' '{domain}'
                msf_generate_plugin_template '{output_path}'
                """
            ]

            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"Failed to generate deployment script: {result.stderr}")

            # Make script executable
            script_path.chmod(0o755)

            generated_files = {
                "deployment_script": str(script_path),
                "plugin_template": str(output_path / "plugins" / "service-mesh-extensions.sh"),
                "manifests_dir": str(k8s_path)
            }

            logger.info(f"Generated service mesh deployment files for {project_name}")
            return generated_files

        except Exception as e:
            logger.error(f"Failed to generate deployment script: {e}")
            raise

    def validate_service_mesh_config(self, config: dict) -> tuple[bool, list[str]]:
        """
        Validate service mesh configuration

        Args:
            config: Service mesh configuration dictionary

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Required fields
        required_fields = ["mesh_type", "cluster_name", "namespace"]
        for field in required_fields:
            if field not in config or not config[field]:
                errors.append(f"Missing required field: {field}")

        # Validate mesh type
        if "mesh_type" in config and config["mesh_type"] not in ["istio", "linkerd"]:
            errors.append(f"Invalid mesh_type: {config['mesh_type']}. Must be 'istio' or 'linkerd'")

        # Validate cluster name format
        if "cluster_name" in config:
            cluster_name = config["cluster_name"]
            if not cluster_name.replace("-", "").replace("_", "").isalnum():
                errors.append(f"Invalid cluster_name format: {cluster_name}")

        # Validate namespace format
        if "namespace" in config:
            namespace = config["namespace"]
            if not namespace.replace("-", "").isalnum():
                errors.append(f"Invalid namespace format: {namespace}")

        # Validate domain if provided
        if "domain" in config and config["domain"]:
            domain = config["domain"]
            if not all(part.replace("-", "").isalnum() for part in domain.split(".")):
                errors.append(f"Invalid domain format: {domain}")

        return len(errors) == 0, errors

    def deploy_service_mesh(
        self,
        project_dir: str,
        mesh_type: str = "istio",
        namespace: str | None = None,
        dry_run: bool = False,
        **kwargs
    ) -> dict[str, Any]:
        """
        Deploy service mesh using the generated deployment script

        Args:
            project_dir: Project directory containing deployment script
            mesh_type: Type of service mesh
            namespace: Target namespace
            dry_run: Whether to perform a dry run
            **kwargs: Additional arguments for deployment

        Returns:
            Dictionary with deployment results
        """
        try:
            project_path = Path(project_dir)
            script_path = project_path / "deploy-service-mesh.sh"

            if not script_path.exists():
                raise FileNotFoundError(f"Deployment script not found: {script_path}")

            # Build command arguments
            cmd = [str(script_path)]
            cmd.extend(["--mesh-type", mesh_type])

            if namespace:
                cmd.extend(["--namespace", namespace])

            if dry_run:
                cmd.append("--dry-run")

            # Add additional arguments
            for key, value in kwargs.items():
                if key.startswith("enable_") and value:
                    cmd.append(f"--{key.replace('_', '-')}")
                elif value and key in ["cluster_name", "domain"]:
                    cmd.extend([f"--{key.replace('_', '-')}", str(value)])

            # Execute deployment
            logger.info(f"Executing service mesh deployment: {' '.join(cmd)}")

            env = os.environ.copy()
            env.update({
                "MARTY_MSF_PATH": str(Path(__file__).parent.parent.parent.parent)
            })

            result = subprocess.run(cmd, cwd=project_dir, env=env, capture_output=True, text=True)

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "command": " ".join(cmd)
            }

        except Exception as e:
            logger.error(f"Failed to deploy service mesh: {e}")
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": "",
                "return_code": -1,
                "command": ""
            }

    def get_deployment_status(self, namespace: str = "istio-system") -> dict[str, Any]:
        """
        Get the status of service mesh deployment

        Args:
            namespace: Namespace to check (istio-system or linkerd)

        Returns:
            Dictionary with deployment status information
        """
        try:
            # Check if kubectl is available
            result = subprocess.run(["kubectl", "cluster-info"], capture_output=True, text=True)
            if result.returncode != 0:
                return {"connected": False, "error": "Cannot connect to cluster"}

            # Check namespace exists
            result = subprocess.run(
                ["kubectl", "get", "namespace", namespace],
                capture_output=True, text=True
            )

            if result.returncode != 0:
                return {"namespace_exists": False, "namespace": namespace}

            # Check deployments in namespace
            result = subprocess.run(
                ["kubectl", "get", "deployments", "-n", namespace, "-o", "json"],
                capture_output=True, text=True
            )

            if result.returncode == 0:
                import json
                deployments = json.loads(result.stdout)
                deployment_status = {}

                for deployment in deployments.get("items", []):
                    name = deployment["metadata"]["name"]
                    status = deployment.get("status", {})
                    deployment_status[name] = {
                        "ready_replicas": status.get("readyReplicas", 0),
                        "replicas": status.get("replicas", 0),
                        "available": status.get("availableReplicas", 0) == status.get("replicas", 0)
                    }

                return {
                    "connected": True,
                    "namespace_exists": True,
                    "namespace": namespace,
                    "deployments": deployment_status
                }

            return {"connected": True, "namespace_exists": True, "namespace": namespace, "deployments": {}}

        except Exception as e:
            logger.error(f"Failed to get deployment status: {e}")
            return {"error": str(e)}

    def cleanup_service_mesh(self, namespace: str, mesh_type: str = "istio") -> dict[str, Any]:
        """
        Clean up service mesh deployment

        Args:
            namespace: Namespace to clean up
            mesh_type: Type of service mesh to clean up

        Returns:
            Dictionary with cleanup results
        """
        try:
            commands = []

            if mesh_type == "istio":
                commands = [
                    ["kubectl", "delete", "namespace", "istio-system", "--ignore-not-found"],
                    ["kubectl", "delete", "namespace", namespace, "--ignore-not-found"]
                ]
            elif mesh_type == "linkerd":
                commands = [
                    ["kubectl", "delete", "namespace", "linkerd", "--ignore-not-found"],
                    ["kubectl", "delete", "namespace", "linkerd-viz", "--ignore-not-found"],
                    ["kubectl", "delete", "namespace", namespace, "--ignore-not-found"]
                ]

            results = []
            for cmd in commands:
                result = subprocess.run(cmd, capture_output=True, text=True)
                results.append({
                    "command": " ".join(cmd),
                    "success": result.returncode == 0,
                    "output": result.stdout if result.returncode == 0 else result.stderr
                })

            return {"cleanup_results": results, "success": all(r["success"] for r in results)}

        except Exception as e:
            logger.error(f"Failed to cleanup service mesh: {e}")
            return {"error": str(e), "success": False}


def create_service_mesh_manager(project_path: str | None = None) -> ServiceMeshManager:
    """
    Factory function to create a ServiceMeshManager instance

    Args:
        project_path: Path to the project directory

    Returns:
        ServiceMeshManager instance
    """
    return ServiceMeshManager(project_path)
