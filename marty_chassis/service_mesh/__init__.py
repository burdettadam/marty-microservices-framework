"""
Service mesh integration for the Marty Chassis.

This module provides generators for Istio and Linkerd service mesh
configurations, including VirtualServices, DestinationRules, and policies.
"""

from pathlib import Path
from typing import Any, Optional, dict, list

import yaml
from marty_chassis.config import ChassisConfig
from marty_chassis.exceptions import TemplateError
from marty_chassis.logger import get_logger

logger = get_logger(__name__)


class ServiceMeshGenerator:
    """Generator for service mesh configurations."""

    def __init__(self, service_name: str, config: ChassisConfig | None = None):
        self.service_name = service_name
        self.config = config or ChassisConfig.from_env()
        logger.info("Service mesh generator initialized", service_name=service_name)

    def generate_istio_manifests(self, output_dir: Path) -> None:
        """Generate Istio service mesh manifests."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate Deployment
        deployment = self._generate_kubernetes_deployment()
        self._write_yaml(deployment, output_dir / "deployment.yaml")

        # Generate Service
        service = self._generate_kubernetes_service()
        self._write_yaml(service, output_dir / "service.yaml")

        # Generate VirtualService
        virtual_service = self._generate_istio_virtual_service()
        self._write_yaml(virtual_service, output_dir / "virtualservice.yaml")

        # Generate DestinationRule
        destination_rule = self._generate_istio_destination_rule()
        self._write_yaml(destination_rule, output_dir / "destinationrule.yaml")

        # Generate ServiceEntry (if needed)
        if self.config.environment.value == "production":
            service_entry = self._generate_istio_service_entry()
            self._write_yaml(service_entry, output_dir / "serviceentry.yaml")

        # Generate AuthorizationPolicy
        auth_policy = self._generate_istio_authorization_policy()
        self._write_yaml(auth_policy, output_dir / "authorizationpolicy.yaml")

        logger.info("Istio manifests generated", output_dir=str(output_dir))

    def generate_linkerd_manifests(self, output_dir: Path) -> None:
        """Generate Linkerd service mesh manifests."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate Deployment with Linkerd annotations
        deployment = self._generate_kubernetes_deployment(linkerd=True)
        self._write_yaml(deployment, output_dir / "deployment.yaml")

        # Generate Service
        service = self._generate_kubernetes_service()
        self._write_yaml(service, output_dir / "service.yaml")

        # Generate TrafficSplit
        traffic_split = self._generate_linkerd_traffic_split()
        self._write_yaml(traffic_split, output_dir / "trafficsplit.yaml")

        # Generate ServiceProfile
        service_profile = self._generate_linkerd_service_profile()
        self._write_yaml(service_profile, output_dir / "serviceprofile.yaml")

        logger.info("Linkerd manifests generated", output_dir=str(output_dir))

    def _generate_kubernetes_deployment(self, linkerd: bool = False) -> dict[str, Any]:
        """Generate Kubernetes Deployment manifest."""
        annotations = {}
        if linkerd:
            annotations["linkerd.io/inject"] = "enabled"

        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": self.service_name,
                "labels": {
                    "app": self.service_name,
                    "version": self.config.service.version,
                },
            },
            "spec": {
                "replicas": 3 if self.config.environment.value == "production" else 1,
                "selector": {
                    "matchLabels": {
                        "app": self.service_name,
                    },
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": self.service_name,
                            "version": self.config.service.version,
                        },
                        "annotations": annotations,
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": self.service_name,
                                "image": f"{self.service_name}:latest",
                                "ports": [
                                    {
                                        "containerPort": self.config.service.port,
                                        "name": "http",
                                    },
                                    {
                                        "containerPort": 8000,
                                        "name": "metrics",
                                    },
                                ],
                                "env": [
                                    {
                                        "name": "CHASSIS_ENVIRONMENT",
                                        "value": self.config.environment.value,
                                    },
                                    {
                                        "name": "CHASSIS_SERVICE__HOST",
                                        "value": "0.0.0.0",
                                    },
                                    {
                                        "name": "CHASSIS_SERVICE__PORT",
                                        "value": str(self.config.service.port),
                                    },
                                ],
                                "livenessProbe": {
                                    "httpGet": {
                                        "path": "/health/live",
                                        "port": "http",
                                    },
                                    "initialDelaySeconds": 30,
                                    "periodSeconds": 10,
                                },
                                "readinessProbe": {
                                    "httpGet": {
                                        "path": "/health/ready",
                                        "port": "http",
                                    },
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 5,
                                },
                                "resources": {
                                    "requests": {
                                        "cpu": "100m",
                                        "memory": "128Mi",
                                    },
                                    "limits": {
                                        "cpu": "500m",
                                        "memory": "512Mi",
                                    },
                                },
                            },
                        ],
                    },
                },
            },
        }

    def _generate_kubernetes_service(self) -> dict[str, Any]:
        """Generate Kubernetes Service manifest."""
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": self.service_name,
                "labels": {
                    "app": self.service_name,
                },
            },
            "spec": {
                "selector": {
                    "app": self.service_name,
                },
                "ports": [
                    {
                        "port": 80,
                        "targetPort": "http",
                        "name": "http",
                    },
                    {
                        "port": 8000,
                        "targetPort": "metrics",
                        "name": "metrics",
                    },
                ],
                "type": "ClusterIP",
            },
        }

    def _generate_istio_virtual_service(self) -> dict[str, Any]:
        """Generate Istio VirtualService manifest."""
        return {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "VirtualService",
            "metadata": {
                "name": self.service_name,
            },
            "spec": {
                "hosts": [self.service_name],
                "http": [
                    {
                        "match": [
                            {
                                "uri": {
                                    "prefix": "/",
                                },
                            },
                        ],
                        "route": [
                            {
                                "destination": {
                                    "host": self.service_name,
                                    "subset": "v1",
                                },
                                "weight": 100,
                            },
                        ],
                        "fault": {
                            "delay": {
                                "percentage": {
                                    "value": 0.1,
                                },
                                "fixedDelay": "5s",
                            },
                        }
                        if self.config.environment.value == "testing"
                        else None,
                        "timeout": "30s",
                        "retries": {
                            "attempts": 3,
                            "perTryTimeout": "10s",
                        },
                    },
                ],
            },
        }

    def _generate_istio_destination_rule(self) -> dict[str, Any]:
        """Generate Istio DestinationRule manifest."""
        return {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "DestinationRule",
            "metadata": {
                "name": self.service_name,
            },
            "spec": {
                "host": self.service_name,
                "trafficPolicy": {
                    "connectionPool": {
                        "tcp": {
                            "maxConnections": 100,
                        },
                        "http": {
                            "http1MaxPendingRequests": 10,
                            "maxRequestsPerConnection": 2,
                        },
                    },
                    "loadBalancer": {
                        "simple": "LEAST_CONN",
                    },
                    "outlierDetection": {
                        "consecutiveErrors": 3,
                        "interval": "30s",
                        "baseEjectionTime": "30s",
                    },
                },
                "subsets": [
                    {
                        "name": "v1",
                        "labels": {
                            "version": self.config.service.version,
                        },
                    },
                ],
            },
        }

    def _generate_istio_service_entry(self) -> dict[str, Any]:
        """Generate Istio ServiceEntry for external services."""
        return {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "ServiceEntry",
            "metadata": {
                "name": f"{self.service_name}-external",
            },
            "spec": {
                "hosts": [
                    "api.external-service.com",
                ],
                "ports": [
                    {
                        "number": 443,
                        "name": "https",
                        "protocol": "HTTPS",
                    },
                ],
                "location": "MESH_EXTERNAL",
                "resolution": "DNS",
            },
        }

    def _generate_istio_authorization_policy(self) -> dict[str, Any]:
        """Generate Istio AuthorizationPolicy manifest."""
        return {
            "apiVersion": "security.istio.io/v1beta1",
            "kind": "AuthorizationPolicy",
            "metadata": {
                "name": self.service_name,
            },
            "spec": {
                "selector": {
                    "matchLabels": {
                        "app": self.service_name,
                    },
                },
                "rules": [
                    {
                        "from": [
                            {
                                "source": {
                                    "principals": [
                                        "cluster.local/ns/default/sa/default",
                                    ],
                                },
                            },
                        ],
                        "to": [
                            {
                                "operation": {
                                    "methods": ["GET", "POST"],
                                },
                            },
                        ],
                    },
                ],
            },
        }

    def _generate_linkerd_traffic_split(self) -> dict[str, Any]:
        """Generate Linkerd TrafficSplit manifest."""
        return {
            "apiVersion": "split.smi-spec.io/v1alpha1",
            "kind": "TrafficSplit",
            "metadata": {
                "name": self.service_name,
            },
            "spec": {
                "service": self.service_name,
                "backends": [
                    {
                        "service": f"{self.service_name}-v1",
                        "weight": 100,
                    },
                ],
            },
        }

    def _generate_linkerd_service_profile(self) -> dict[str, Any]:
        """Generate Linkerd ServiceProfile manifest."""
        return {
            "apiVersion": "linkerd.io/v1alpha2",
            "kind": "ServiceProfile",
            "metadata": {
                "name": self.service_name,
            },
            "spec": {
                "routes": [
                    {
                        "name": "health",
                        "condition": {
                            "pathRegex": "/health.*",
                        },
                        "responseClasses": [
                            {
                                "condition": {
                                    "status": {
                                        "min": 200,
                                        "max": 299,
                                    },
                                },
                                "isSuccess": True,
                            },
                        ],
                    },
                    {
                        "name": "api",
                        "condition": {
                            "pathRegex": "/.*",
                        },
                        "timeout": "30s",
                        "retryBudget": {
                            "retryRatio": 0.2,
                            "minRetriesPerSecond": 10,
                            "ttl": "10s",
                        },
                    },
                ],
            },
        }

    def _write_yaml(self, data: dict[str, Any], file_path: Path) -> None:
        """Write YAML data to file."""
        try:
            with open(file_path, "w") as f:
                yaml.dump(data, f, default_flow_style=False, indent=2)
            logger.debug("YAML manifest written", file=str(file_path))
        except Exception as e:
            raise TemplateError(f"Failed to write YAML file {file_path}: {e}")


class ManifestGenerator:
    """High-level manifest generator."""

    def __init__(self, service_name: str, config: ChassisConfig | None = None):
        self.service_name = service_name
        self.config = config or ChassisConfig.from_env()
        self.mesh_generator = ServiceMeshGenerator(service_name, config)

    def generate_all_manifests(
        self,
        output_dir: Path,
        service_mesh: str = "istio",
        include_monitoring: bool = True,
    ) -> None:
        """Generate all Kubernetes and service mesh manifests."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate service mesh manifests
        if service_mesh.lower() == "istio":
            self.mesh_generator.generate_istio_manifests(output_dir / "istio")
        elif service_mesh.lower() == "linkerd":
            self.mesh_generator.generate_linkerd_manifests(output_dir / "linkerd")
        else:
            # Just generate basic Kubernetes manifests
            deployment = self.mesh_generator._generate_kubernetes_deployment()
            service = self.mesh_generator._generate_kubernetes_service()

            self.mesh_generator._write_yaml(deployment, output_dir / "deployment.yaml")
            self.mesh_generator._write_yaml(service, output_dir / "service.yaml")

        # Generate monitoring manifests
        if include_monitoring:
            self._generate_monitoring_manifests(output_dir / "monitoring")

        logger.info(
            "All manifests generated",
            service_name=self.service_name,
            service_mesh=service_mesh,
            output_dir=str(output_dir),
        )

    def _generate_monitoring_manifests(self, output_dir: Path) -> None:
        """Generate monitoring-related manifests."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # ServiceMonitor for Prometheus
        service_monitor = {
            "apiVersion": "monitoring.coreos.com/v1",
            "kind": "ServiceMonitor",
            "metadata": {
                "name": self.service_name,
                "labels": {
                    "app": self.service_name,
                },
            },
            "spec": {
                "selector": {
                    "matchLabels": {
                        "app": self.service_name,
                    },
                },
                "endpoints": [
                    {
                        "port": "metrics",
                        "path": "/metrics",
                        "interval": "30s",
                    },
                ],
            },
        }

        self.mesh_generator._write_yaml(
            service_monitor, output_dir / "servicemonitor.yaml"
        )

        # PrometheusRule for alerting
        prometheus_rule = {
            "apiVersion": "monitoring.coreos.com/v1",
            "kind": "PrometheusRule",
            "metadata": {
                "name": self.service_name,
                "labels": {
                    "app": self.service_name,
                },
            },
            "spec": {
                "groups": [
                    {
                        "name": f"{self.service_name}.rules",
                        "rules": [
                            {
                                "alert": f"{self.service_name}Down",
                                "expr": f'up{{job="{self.service_name}"}} == 0',
                                "for": "1m",
                                "labels": {
                                    "severity": "critical",
                                },
                                "annotations": {
                                    "summary": f"{self.service_name} is down",
                                    "description": f"{self.service_name} has been down for more than 1 minute.",
                                },
                            },
                            {
                                "alert": f"{self.service_name}HighErrorRate",
                                "expr": f'rate(http_requests_total{{job="{self.service_name}",status_code=~"5.."}}[5m]) > 0.1',
                                "for": "5m",
                                "labels": {
                                    "severity": "warning",
                                },
                                "annotations": {
                                    "summary": f"{self.service_name} high error rate",
                                    "description": f"{self.service_name} error rate is above 10% for 5 minutes.",
                                },
                            },
                        ],
                    },
                ],
            },
        }

        self.mesh_generator._write_yaml(
            prometheus_rule, output_dir / "prometheusrule.yaml"
        )
