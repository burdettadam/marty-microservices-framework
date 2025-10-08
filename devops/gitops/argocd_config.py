"""
ArgoCD Configuration and Management for Marty Microservices Framework

Provides comprehensive ArgoCD integration including:
- Application lifecycle management
- Custom resource definitions
- Sync policies and strategies
- Health checks and monitoring
- Multi-cluster support
- GitOps best practices implementation
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class ArgoCDApplication:
    """ArgoCD Application custom resource definition"""

    name: str
    namespace: str
    project: str = "default"

    # Source configuration
    repo_url: str = ""
    target_revision: str = "HEAD"
    path: str = "."

    # Destination
    destination_server: str = "https://kubernetes.default.svc"
    destination_namespace: str = "default"

    # Sync policy
    auto_sync: bool = False
    auto_prune: bool = False
    self_heal: bool = False

    # Helm configuration
    helm_values_files: List[str] = field(default_factory=list)
    helm_parameters: Dict[str, str] = field(default_factory=dict)
    helm_value_overrides: str = ""

    # Kustomize configuration
    kustomize_images: List[str] = field(default_factory=list)
    kustomize_name_prefix: str = ""
    kustomize_name_suffix: str = ""

    # Sync options
    sync_options: List[str] = field(default_factory=list)
    retry_limit: int = 5
    retry_backoff_duration: str = "5s"
    retry_backoff_factor: int = 2

    # Ignorances
    ignore_differences: List[Dict[str, Any]] = field(default_factory=list)

    def to_yaml(self) -> str:
        """Convert to ArgoCD Application YAML"""

        app_spec = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "finalizers": ["resources-finalizer.argocd.argoproj.io"],
            },
            "spec": {
                "project": self.project,
                "source": {
                    "repoURL": self.repo_url,
                    "targetRevision": self.target_revision,
                    "path": self.path,
                },
                "destination": {
                    "server": self.destination_server,
                    "namespace": self.destination_namespace,
                },
                "syncPolicy": {},
            },
        }

        # Add auto-sync policy
        if self.auto_sync:
            app_spec["spec"]["syncPolicy"]["automated"] = {
                "prune": self.auto_prune,
                "selfHeal": self.self_heal,
            }

        # Add sync options
        if self.sync_options:
            app_spec["spec"]["syncPolicy"]["syncOptions"] = self.sync_options

        # Add retry policy
        app_spec["spec"]["syncPolicy"]["retry"] = {
            "limit": self.retry_limit,
            "backoff": {
                "duration": self.retry_backoff_duration,
                "factor": self.retry_backoff_factor,
            },
        }

        # Add Helm configuration
        if self.helm_values_files or self.helm_parameters or self.helm_value_overrides:
            helm_config = {}

            if self.helm_values_files:
                helm_config["valueFiles"] = self.helm_values_files

            if self.helm_parameters:
                helm_config["parameters"] = [
                    {"name": k, "value": v} for k, v in self.helm_parameters.items()
                ]

            if self.helm_value_overrides:
                helm_config["values"] = self.helm_value_overrides

            app_spec["spec"]["source"]["helm"] = helm_config

        # Add Kustomize configuration
        if (
            self.kustomize_images
            or self.kustomize_name_prefix
            or self.kustomize_name_suffix
        ):
            kustomize_config = {}

            if self.kustomize_images:
                kustomize_config["images"] = self.kustomize_images

            if self.kustomize_name_prefix:
                kustomize_config["namePrefix"] = self.kustomize_name_prefix

            if self.kustomize_name_suffix:
                kustomize_config["nameSuffix"] = self.kustomize_name_suffix

            app_spec["spec"]["source"]["kustomize"] = kustomize_config

        # Add ignore differences
        if self.ignore_differences:
            app_spec["spec"]["ignoreDifferences"] = self.ignore_differences

        return yaml.dump(app_spec, default_flow_style=False)


@dataclass
class ArgoCDProject:
    """ArgoCD Project custom resource definition"""

    name: str
    namespace: str = "argocd"
    description: str = ""

    # Source repositories
    source_repos: List[str] = field(default_factory=list)

    # Destinations
    destinations: List[Dict[str, str]] = field(default_factory=list)

    # Cluster resource whitelist
    cluster_resource_whitelist: List[Dict[str, str]] = field(default_factory=list)

    # Namespace resource whitelist
    namespace_resource_whitelist: List[Dict[str, str]] = field(default_factory=list)

    # Roles
    roles: List[Dict[str, Any]] = field(default_factory=list)

    # Sync windows
    sync_windows: List[Dict[str, Any]] = field(default_factory=list)

    def to_yaml(self) -> str:
        """Convert to ArgoCD Project YAML"""

        project_spec = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "AppProject",
            "metadata": {"name": self.name, "namespace": self.namespace},
            "spec": {
                "description": self.description,
                "sourceRepos": self.source_repos,
                "destinations": self.destinations,
                "clusterResourceWhitelist": self.cluster_resource_whitelist,
                "namespaceResourceWhitelist": self.namespace_resource_whitelist,
                "roles": self.roles,
                "syncWindows": self.sync_windows,
            },
        }

        return yaml.dump(project_spec, default_flow_style=False)


class ArgoCDConfigGenerator:
    """
    Generator for ArgoCD configurations and best practices

    Features:
    - Application and project template generation
    - Multi-environment configurations
    - Security policy templates
    - Monitoring and observability setup
    """

    def __init__(self, output_dir: str = "./argocd-configs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Default configurations
        self.default_sync_options = [
            "CreateNamespace=true",
            "PrunePropagationPolicy=foreground",
            "PruneLast=true",
        ]

        self.common_ignore_differences = [
            {"group": "apps", "kind": "Deployment", "jsonPointers": ["/spec/replicas"]},
            {"group": "", "kind": "Secret", "jsonPointers": ["/data"]},
        ]

    def generate_application_set(
        self,
        app_name: str,
        environments: List[str],
        repo_url: str,
        base_path: str = ".",
    ) -> str:
        """Generate ApplicationSet for multi-environment deployment"""

        app_set = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "ApplicationSet",
            "metadata": {"name": f"{app_name}-environments", "namespace": "argocd"},
            "spec": {
                "generators": [
                    {
                        "list": {
                            "elements": [
                                {
                                    "env": env,
                                    "namespace": f"{app_name}-{env}",
                                    "values": f"environments/{env}/values.yaml",
                                }
                                for env in environments
                            ]
                        }
                    }
                ],
                "template": {
                    "metadata": {
                        "name": "{{env}}-{{values.appName}}",
                        "labels": {"app": app_name, "environment": "{{env}}"},
                    },
                    "spec": {
                        "project": "default",
                        "source": {
                            "repoURL": repo_url,
                            "targetRevision": "HEAD",
                            "path": base_path,
                            "helm": {"valueFiles": ["{{values}}"]},
                        },
                        "destination": {
                            "server": "https://kubernetes.default.svc",
                            "namespace": "{{namespace}}",
                        },
                        "syncPolicy": {
                            "automated": {"prune": True, "selfHeal": True},
                            "syncOptions": self.default_sync_options,
                        },
                    },
                },
            },
        }

        return yaml.dump(app_set, default_flow_style=False)

    def generate_security_project(self) -> str:
        """Generate security-focused ArgoCD project"""

        security_project = ArgoCDProject(
            name="security",
            description="Security and compliance applications",
            source_repos=["*"],  # Restrict in production
            destinations=[
                {"namespace": "security-*", "server": "https://kubernetes.default.svc"},
                {"namespace": "monitoring", "server": "https://kubernetes.default.svc"},
            ],
            cluster_resource_whitelist=[
                {"group": "", "kind": "Namespace"},
                {"group": "rbac.authorization.k8s.io", "kind": "ClusterRole"},
                {"group": "rbac.authorization.k8s.io", "kind": "ClusterRoleBinding"},
                {"group": "apiextensions.k8s.io", "kind": "CustomResourceDefinition"},
            ],
            namespace_resource_whitelist=[
                {"group": "", "kind": "*"},
                {"group": "apps", "kind": "*"},
                {"group": "extensions", "kind": "*"},
                {"group": "networking.k8s.io", "kind": "*"},
            ],
            roles=[
                {
                    "name": "security-admin",
                    "description": "Security administrator role",
                    "policies": [
                        "p, proj:security:security-admin, applications, *, security/*, allow",
                        "p, proj:security:security-admin, repositories, *, *, allow",
                    ],
                    "groups": ["security-team"],
                }
            ],
            sync_windows=[
                {
                    "kind": "allow",
                    "schedule": "0 8 * * 1-5",  # Weekdays 8 AM
                    "duration": "8h",
                    "applications": ["security-*"],
                    "timeZone": "UTC",
                }
            ],
        )

        return security_project.to_yaml()

    def generate_monitoring_setup(self) -> Dict[str, str]:
        """Generate monitoring and observability applications"""

        configurations = {}

        # Prometheus application
        prometheus_app = ArgoCDApplication(
            name="prometheus",
            namespace="argocd",
            repo_url="https://prometheus-community.github.io/helm-charts",
            path=".",
            destination_namespace="monitoring",
            auto_sync=True,
            auto_prune=True,
            self_heal=True,
            helm_values_files=["values-prometheus.yaml"],
            sync_options=self.default_sync_options,
        )

        configurations["prometheus.yaml"] = prometheus_app.to_yaml()

        # Grafana application
        grafana_app = ArgoCDApplication(
            name="grafana",
            namespace="argocd",
            repo_url="https://grafana.github.io/helm-charts",
            path=".",
            destination_namespace="monitoring",
            auto_sync=True,
            auto_prune=True,
            self_heal=True,
            helm_values_files=["values-grafana.yaml"],
            sync_options=self.default_sync_options,
        )

        configurations["grafana.yaml"] = grafana_app.to_yaml()

        # ArgoCD monitoring
        argocd_monitoring = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {"name": "argocd-monitoring", "namespace": "argocd"},
            "spec": {
                "project": "default",
                "source": {
                    "repoURL": "https://github.com/argoproj/argo-cd",
                    "targetRevision": "stable",
                    "path": "manifests/monitoring",
                },
                "destination": {
                    "server": "https://kubernetes.default.svc",
                    "namespace": "argocd",
                },
                "syncPolicy": {"automated": {"prune": True, "selfHeal": True}},
            },
        }

        configurations["argocd-monitoring.yaml"] = yaml.dump(
            argocd_monitoring, default_flow_style=False
        )

        return configurations

    def generate_rbac_config(self) -> str:
        """Generate RBAC configuration for ArgoCD"""

        rbac_config = {
            "policy.default": "role:readonly",
            "policy.csv": """
# Admin users
p, role:admin, applications, *, *, allow
p, role:admin, clusters, *, *, allow
p, role:admin, repositories, *, *, allow
p, role:admin, projects, *, *, allow

# Developer role
p, role:developer, applications, get, */*, allow
p, role:developer, applications, sync, */*, allow
p, role:developer, applications, action/*, */*, allow
p, role:developer, repositories, get, *, allow

# Security team role
p, role:security, applications, *, security/*, allow
p, role:security, repositories, *, *, allow
p, role:security, clusters, get, *, allow

# Operations team role
p, role:operations, applications, *, ops/*, allow
p, role:operations, applications, *, monitoring/*, allow
p, role:operations, clusters, *, *, allow

# Group mappings
g, argocd-admins, role:admin
g, developers, role:developer
g, security-team, role:security
g, ops-team, role:operations
""",
            "scopes": "[groups]",
        }

        return yaml.dump(rbac_config, default_flow_style=False)

    def generate_notification_config(self) -> str:
        """Generate notification configuration"""

        notification_config = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "argocd-notifications-cm", "namespace": "argocd"},
            "data": {
                "service.slack": """
token: $slack-token
apiURL: https://slack.com/api
""",
                "service.email": """
host: smtp.gmail.com
port: 587
from: argocd@company.com
username: $email-username
password: $email-password
""",
                "template.app-deployed": """
email:
  subject: Application {{.app.metadata.name}} is now running new version.
message: |
  Application {{.app.metadata.name}} is now running new version of deployments manifests.
slack:
  attachments: |
    [{
      "title": "{{ .app.metadata.name}}",
      "title_link":"{{.context.argocdUrl}}/applications/{{.app.metadata.name}}",
      "color": "#18be52",
      "fields": [
      {
        "title": "Sync Status",
        "value": "{{.app.status.sync.status}}",
        "short": true
      },
      {
        "title": "Repository",
        "value": "{{.app.spec.source.repoURL}}",
        "short": true
      },
      {
        "title": "Revision",
        "value": "{{.app.status.sync.revision}}",
        "short": true
      }
      {{range $index, $c := .app.status.conditions}}
      {{if not $index}},{{end}}
      {{if $index}},{{end}}
      {
        "title": "{{$c.type}}",
        "value": "{{$c.message}}",
        "short": true
      }
      {{end}}
      ]
    }]
""",
                "template.app-health-degraded": """
email:
  subject: Application {{.app.metadata.name}} has degraded.
message: |
  Application {{.app.metadata.name}} has degraded.
  Application details: {{.context.argocdUrl}}/applications/{{.app.metadata.name}}.
slack:
  attachments: |
    [{
      "title": "{{ .app.metadata.name}}",
      "title_link": "{{.context.argocdUrl}}/applications/{{.app.metadata.name}}",
      "color": "#f4c430",
      "fields": [
      {
        "title": "Health Status",
        "value": "{{.app.status.health.status}}",
        "short": true
      },
      {
        "title": "Repository",
        "value": "{{.app.spec.source.repoURL}}",
        "short": true
      }
      {{range $index, $c := .app.status.conditions}}
      {{if not $index}},{{end}}
      {{if $index}},{{end}}
      {
        "title": "{{$c.type}}",
        "value": "{{$c.message}}",
        "short": true
      }
      {{end}}
      ]
    }]
""",
                "trigger.on-deployed": """
- when: app.status.operationState.phase in ['Succeeded'] and app.status.health.status == 'Healthy'
  send: [app-deployed]
""",
                "trigger.on-health-degraded": """
- when: app.status.health.status == 'Degraded'
  send: [app-health-degraded]
""",
                "trigger.on-sync-failed": """
- when: app.status.operationState.phase in ['Error', 'Failed']
  send: [app-sync-failed]
""",
                "subscriptions": """
# Subscribe to notifications for all applications
- recipients:
  - slack:alerts
  - email:ops-team@company.com
  triggers:
  - on-deployed
  - on-health-degraded
  - on-sync-failed

# Subscribe security team for security applications
- recipients:
  - slack:security-alerts
  - email:security@company.com
  selector: app.metadata.labels.team == 'security'
  triggers:
  - on-deployed
  - on-health-degraded
  - on-sync-failed
""",
            },
        }

        return yaml.dump(notification_config, default_flow_style=False)

    def generate_progressive_delivery_config(self) -> Dict[str, str]:
        """Generate progressive delivery configurations"""

        configurations = {}

        # Argo Rollouts application
        rollouts_app = ArgoCDApplication(
            name="argo-rollouts",
            namespace="argocd",
            repo_url="https://argoproj.github.io/argo-helm",
            path=".",
            destination_namespace="argo-rollouts",
            auto_sync=True,
            auto_prune=True,
            self_heal=True,
            sync_options=self.default_sync_options,
        )

        configurations["argo-rollouts.yaml"] = rollouts_app.to_yaml()

        # Canary rollout example
        canary_rollout = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Rollout",
            "metadata": {"name": "example-rollout", "namespace": "default"},
            "spec": {
                "replicas": 5,
                "strategy": {
                    "canary": {
                        "steps": [
                            {"setWeight": 20},
                            {"pause": {"duration": "1m"}},
                            {"setWeight": 40},
                            {"pause": {"duration": "1m"}},
                            {"setWeight": 60},
                            {"pause": {"duration": "1m"}},
                            {"setWeight": 80},
                            {"pause": {"duration": "1m"}},
                        ],
                        "canaryService": "example-canary",
                        "stableService": "example-stable",
                    }
                },
                "selector": {"matchLabels": {"app": "example"}},
                "template": {
                    "metadata": {"labels": {"app": "example"}},
                    "spec": {
                        "containers": [
                            {
                                "name": "example",
                                "image": "nginx:1.20",
                                "ports": [{"containerPort": 80}],
                            }
                        ]
                    },
                },
            },
        }

        configurations["canary-rollout-example.yaml"] = yaml.dump(
            canary_rollout, default_flow_style=False
        )

        return configurations

    def save_configurations(self, configs: Dict[str, str], subdirectory: str = ""):
        """Save configurations to files"""

        output_path = (
            self.output_dir / subdirectory if subdirectory else self.output_dir
        )
        output_path.mkdir(parents=True, exist_ok=True)

        for filename, content in configs.items():
            file_path = output_path / filename
            file_path.write_text(content)
            print(f"✅ Saved configuration: {file_path}")

    def generate_all_configurations(self):
        """Generate all ArgoCD configurations"""

        print("🔧 Generating ArgoCD configurations...")

        # Generate core configurations
        core_configs = {
            "security-project.yaml": self.generate_security_project(),
            "rbac-config.yaml": self.generate_rbac_config(),
            "notification-config.yaml": self.generate_notification_config(),
        }

        # Generate monitoring configurations
        monitoring_configs = self.generate_monitoring_setup()

        # Generate progressive delivery configurations
        progressive_delivery_configs = self.generate_progressive_delivery_config()

        # Generate application set example
        app_set_config = {
            "multi-env-appset.yaml": self.generate_application_set(
                "example-app",
                ["development", "staging", "production"],
                "https://github.com/example/app-config.git",
            )
        }

        # Save all configurations
        self.save_configurations(core_configs, "core")
        self.save_configurations(monitoring_configs, "monitoring")
        self.save_configurations(progressive_delivery_configs, "progressive-delivery")
        self.save_configurations(app_set_config, "applications")

        print("✅ All ArgoCD configurations generated")


# Example usage
def main():
    """Generate example ArgoCD configurations"""

    print("=== ArgoCD Configuration Generator ===")

    # Initialize generator
    generator = ArgoCDConfigGenerator("./generated-argocd-configs")

    # Generate all configurations
    generator.generate_all_configurations()

    # Example individual application
    example_app = ArgoCDApplication(
        name="microservice-api",
        namespace="argocd",
        repo_url="https://github.com/company/microservice-api-config.git",
        path="manifests",
        destination_namespace="api",
        auto_sync=True,
        auto_prune=True,
        self_heal=True,
        helm_values_files=["values.yaml", "values-production.yaml"],
        helm_parameters={"image.tag": "v1.2.3", "replicaCount": "3"},
        sync_options=[
            "CreateNamespace=true",
            "PrunePropagationPolicy=foreground",
            "PruneLast=true",
            "SkipDryRunOnMissingResource=true",
        ],
        ignore_differences=[
            {"group": "apps", "kind": "Deployment", "jsonPointers": ["/spec/replicas"]}
        ],
    )

    # Save individual application
    app_yaml = example_app.to_yaml()
    app_path = Path("./generated-argocd-configs/applications/microservice-api.yaml")
    app_path.parent.mkdir(parents=True, exist_ok=True)
    app_path.write_text(app_yaml)

    print(f"✅ Generated example application: {app_path}")
    print("\n📁 Generated configurations saved to: ./generated-argocd-configs/")


if __name__ == "__main__":
    main()
