"""
Infrastructure as Code (IaC) Framework for Marty Microservices Framework

Provides comprehensive Infrastructure as Code capabilities including:
- Terraform integration and management
- Pulumi support for cloud-agnostic provisioning
- State management and backend configuration
- Resource lifecycle automation
- Multi-cloud provider support
- Infrastructure validation and drift detection
- Cost optimization and resource tagging
"""

import asyncio
import builtins
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, dict, list, tuple

import yaml

# External dependencies
try:
    import boto3

    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

try:
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.resource import ResourceManagementClient

    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

try:
    from google.cloud import resource_manager

    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False


class CloudProvider(Enum):
    """Supported cloud providers"""

    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    DIGITAL_OCEAN = "digital_ocean"
    KUBERNETES = "kubernetes"
    LOCAL = "local"


class IaCTool(Enum):
    """Infrastructure as Code tools"""

    TERRAFORM = "terraform"
    PULUMI = "pulumi"
    CDK = "cdk"
    CLOUDFORMATION = "cloudformation"
    ARM = "arm"
    DEPLOYMENT_MANAGER = "deployment_manager"


class ResourceType(Enum):
    """Infrastructure resource types"""

    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    SECURITY = "security"
    MONITORING = "monitoring"
    CONTAINER = "container"
    SERVERLESS = "serverless"


class OperationStatus(Enum):
    """Infrastructure operation status"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


@dataclass
class InfrastructureResource:
    """Infrastructure resource definition"""

    name: str
    resource_type: ResourceType
    provider: CloudProvider

    # Resource configuration
    configuration: builtins.dict[str, Any] = field(default_factory=dict)

    # Dependencies
    depends_on: builtins.list[str] = field(default_factory=list)

    # Tags and metadata
    tags: builtins.dict[str, str] = field(default_factory=dict)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    # Lifecycle
    prevent_destroy: bool = False
    create_before_destroy: bool = False

    # State
    resource_id: str | None = None
    status: str = "not_created"
    created_at: datetime | None = None
    last_modified: datetime | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "resource_type": self.resource_type.value,
            "provider": self.provider.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_modified": self.last_modified.isoformat()
            if self.last_modified
            else None,
        }


@dataclass
class InfrastructureStack:
    """Infrastructure stack definition"""

    name: str
    description: str
    provider: CloudProvider
    tool: IaCTool

    # Resources
    resources: builtins.list[InfrastructureResource] = field(default_factory=list)

    # Configuration
    variables: builtins.dict[str, Any] = field(default_factory=dict)
    outputs: builtins.dict[str, Any] = field(default_factory=dict)

    # Backend configuration
    backend_config: builtins.dict[str, Any] = field(default_factory=dict)

    # State management
    state_location: str = ""
    state_lock: bool = True

    # Deployment configuration
    workspace: str = "default"
    environment: str = "development"
    region: str = "us-east-1"

    # Metadata
    version: str = "1.0.0"
    tags: builtins.dict[str, str] = field(default_factory=dict)

    # Lifecycle
    created_at: datetime | None = None
    last_deployed: datetime | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "provider": self.provider.value,
            "tool": self.tool.value,
            "resources": [resource.to_dict() for resource in self.resources],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_deployed": self.last_deployed.isoformat()
            if self.last_deployed
            else None,
        }


@dataclass
class InfrastructureOperation:
    """Infrastructure operation tracking"""

    operation_id: str
    stack_name: str
    operation_type: str  # plan, apply, destroy, refresh
    started_at: datetime

    # Configuration
    dry_run: bool = False
    auto_approve: bool = False

    # Status
    status: OperationStatus = OperationStatus.PENDING
    progress_percentage: int = 0

    # Results
    resources_to_create: int = 0
    resources_to_update: int = 0
    resources_to_destroy: int = 0

    # Execution details
    plan_output: str = ""
    apply_output: str = ""
    error_message: str | None = None

    # Timing
    completed_at: datetime | None = None
    duration: float | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }


class IaCProviderBase(ABC):
    """
    Base class for Infrastructure as Code providers

    Defines the interface that all IaC providers must implement
    """

    def __init__(self, tool: IaCTool, provider: CloudProvider):
        self.tool = tool
        self.provider = provider
        self.stacks: builtins.dict[str, InfrastructureStack] = {}
        self.operations: builtins.dict[str, InfrastructureOperation] = {}

    @abstractmethod
    async def initialize_stack(self, stack: InfrastructureStack) -> bool:
        """Initialize infrastructure stack"""

    @abstractmethod
    async def plan_stack(self, stack_name: str) -> InfrastructureOperation:
        """Generate infrastructure plan"""

    @abstractmethod
    async def apply_stack(
        self, stack_name: str, auto_approve: bool = False
    ) -> InfrastructureOperation:
        """Apply infrastructure changes"""

    @abstractmethod
    async def destroy_stack(
        self, stack_name: str, auto_approve: bool = False
    ) -> InfrastructureOperation:
        """Destroy infrastructure stack"""

    @abstractmethod
    async def get_stack_state(self, stack_name: str) -> builtins.dict[str, Any]:
        """Get current stack state"""

    @abstractmethod
    async def validate_configuration(self, stack_name: str) -> builtins.dict[str, Any]:
        """Validate infrastructure configuration"""


class TerraformProvider(IaCProviderBase):
    """
    Terraform Infrastructure as Code provider

    Features:
    - Terraform CLI integration
    - State management and locking
    - Multi-workspace support
    - Plan and apply operations
    - Resource drift detection
    """

    def __init__(self, provider: CloudProvider):
        super().__init__(IaCTool.TERRAFORM, provider)
        self.terraform_binary = "terraform"
        self.working_directory = "/tmp/terraform"

        # Ensure working directory exists
        os.makedirs(self.working_directory, exist_ok=True)

    async def initialize_stack(self, stack: InfrastructureStack) -> bool:
        """Initialize Terraform stack"""

        try:
            print(f"🏗️ Initializing Terraform stack: {stack.name}")

            # Create stack directory
            stack_dir = os.path.join(self.working_directory, stack.name)
            os.makedirs(stack_dir, exist_ok=True)

            # Generate Terraform configuration
            await self._generate_terraform_config(stack, stack_dir)

            # Initialize Terraform
            init_result = await self._run_terraform_command(
                ["init"], working_dir=stack_dir
            )

            if init_result["returncode"] != 0:
                print(f"❌ Terraform init failed: {init_result['stderr']}")
                return False

            # Create workspace if specified
            if stack.workspace != "default":
                workspace_result = await self._run_terraform_command(
                    ["workspace", "new", stack.workspace], working_dir=stack_dir
                )

                # Workspace might already exist, check if we can select it
                if workspace_result["returncode"] != 0:
                    select_result = await self._run_terraform_command(
                        ["workspace", "select", stack.workspace], working_dir=stack_dir
                    )

                    if select_result["returncode"] != 0:
                        print(
                            f"⚠️ Could not create or select workspace: {stack.workspace}"
                        )

            stack.created_at = datetime.now()
            self.stacks[stack.name] = stack

            print(f"✅ Terraform stack initialized: {stack.name}")
            return True

        except Exception as e:
            print(f"❌ Failed to initialize Terraform stack {stack.name}: {e}")
            return False

    async def plan_stack(self, stack_name: str) -> InfrastructureOperation:
        """Generate Terraform plan"""

        if stack_name not in self.stacks:
            raise ValueError(f"Stack {stack_name} not found")

        stack = self.stacks[stack_name]

        # Create operation
        operation = InfrastructureOperation(
            operation_id=f"plan_{stack_name}_{int(datetime.now().timestamp())}",
            stack_name=stack_name,
            operation_type="plan",
            started_at=datetime.now(),
            dry_run=True,
        )

        self.operations[operation.operation_id] = operation

        try:
            print(f"📋 Planning Terraform stack: {stack_name}")
            operation.status = OperationStatus.RUNNING

            stack_dir = os.path.join(self.working_directory, stack_name)

            # Run terraform plan
            plan_result = await self._run_terraform_command(
                ["plan", "-detailed-exitcode", "-out=tfplan"], working_dir=stack_dir
            )

            operation.plan_output = plan_result["stdout"]

            # Parse plan output
            await self._parse_plan_output(operation, plan_result["stdout"])

            if plan_result["returncode"] == 0:
                # No changes
                operation.status = OperationStatus.SUCCEEDED
                print(f"📋 No changes required for {stack_name}")
            elif plan_result["returncode"] == 2:
                # Changes detected
                operation.status = OperationStatus.SUCCEEDED
                print(
                    f"📋 Plan completed for {stack_name}: "
                    f"{operation.resources_to_create} to create, "
                    f"{operation.resources_to_update} to update, "
                    f"{operation.resources_to_destroy} to destroy"
                )
            else:
                # Error
                operation.status = OperationStatus.FAILED
                operation.error_message = plan_result["stderr"]
                print(f"❌ Plan failed for {stack_name}: {plan_result['stderr']}")

        except Exception as e:
            operation.status = OperationStatus.FAILED
            operation.error_message = str(e)
            print(f"❌ Plan error for {stack_name}: {e}")

        finally:
            operation.completed_at = datetime.now()
            operation.duration = (
                operation.completed_at - operation.started_at
            ).total_seconds()

        return operation

    async def apply_stack(
        self, stack_name: str, auto_approve: bool = False
    ) -> InfrastructureOperation:
        """Apply Terraform changes"""

        if stack_name not in self.stacks:
            raise ValueError(f"Stack {stack_name} not found")

        stack = self.stacks[stack_name]

        # Create operation
        operation = InfrastructureOperation(
            operation_id=f"apply_{stack_name}_{int(datetime.now().timestamp())}",
            stack_name=stack_name,
            operation_type="apply",
            started_at=datetime.now(),
            auto_approve=auto_approve,
        )

        self.operations[operation.operation_id] = operation

        try:
            print(f"🚀 Applying Terraform stack: {stack_name}")
            operation.status = OperationStatus.RUNNING

            stack_dir = os.path.join(self.working_directory, stack_name)

            # Build apply command
            apply_cmd = ["apply"]
            if auto_approve:
                apply_cmd.append("-auto-approve")

            # Check if we have a saved plan
            plan_file = os.path.join(stack_dir, "tfplan")
            if os.path.exists(plan_file):
                apply_cmd.append("tfplan")

            # Run terraform apply
            apply_result = await self._run_terraform_command(
                apply_cmd, working_dir=stack_dir
            )

            operation.apply_output = apply_result["stdout"]

            if apply_result["returncode"] == 0:
                operation.status = OperationStatus.SUCCEEDED
                stack.last_deployed = datetime.now()
                print(f"✅ Apply completed for {stack_name}")

                # Update resource states
                await self._update_resource_states(stack)
            else:
                operation.status = OperationStatus.FAILED
                operation.error_message = apply_result["stderr"]
                print(f"❌ Apply failed for {stack_name}: {apply_result['stderr']}")

        except Exception as e:
            operation.status = OperationStatus.FAILED
            operation.error_message = str(e)
            print(f"❌ Apply error for {stack_name}: {e}")

        finally:
            operation.completed_at = datetime.now()
            operation.duration = (
                operation.completed_at - operation.started_at
            ).total_seconds()

        return operation

    async def destroy_stack(
        self, stack_name: str, auto_approve: bool = False
    ) -> InfrastructureOperation:
        """Destroy Terraform stack"""

        if stack_name not in self.stacks:
            raise ValueError(f"Stack {stack_name} not found")

        # Create operation
        operation = InfrastructureOperation(
            operation_id=f"destroy_{stack_name}_{int(datetime.now().timestamp())}",
            stack_name=stack_name,
            operation_type="destroy",
            started_at=datetime.now(),
            auto_approve=auto_approve,
        )

        self.operations[operation.operation_id] = operation

        try:
            print(f"💥 Destroying Terraform stack: {stack_name}")
            operation.status = OperationStatus.RUNNING

            stack_dir = os.path.join(self.working_directory, stack_name)

            # Build destroy command
            destroy_cmd = ["destroy"]
            if auto_approve:
                destroy_cmd.append("-auto-approve")

            # Run terraform destroy
            destroy_result = await self._run_terraform_command(
                destroy_cmd, working_dir=stack_dir
            )

            if destroy_result["returncode"] == 0:
                operation.status = OperationStatus.SUCCEEDED
                print(f"✅ Destroy completed for {stack_name}")

                # Clean up stack directory
                shutil.rmtree(stack_dir, ignore_errors=True)

                # Remove from stacks
                if stack_name in self.stacks:
                    del self.stacks[stack_name]
            else:
                operation.status = OperationStatus.FAILED
                operation.error_message = destroy_result["stderr"]
                print(f"❌ Destroy failed for {stack_name}: {destroy_result['stderr']}")

        except Exception as e:
            operation.status = OperationStatus.FAILED
            operation.error_message = str(e)
            print(f"❌ Destroy error for {stack_name}: {e}")

        finally:
            operation.completed_at = datetime.now()
            operation.duration = (
                operation.completed_at - operation.started_at
            ).total_seconds()

        return operation

    async def get_stack_state(self, stack_name: str) -> builtins.dict[str, Any]:
        """Get current Terraform state"""

        if stack_name not in self.stacks:
            return {}

        try:
            stack_dir = os.path.join(self.working_directory, stack_name)

            # Run terraform show
            show_result = await self._run_terraform_command(
                ["show", "-json"], working_dir=stack_dir
            )

            if show_result["returncode"] == 0:
                state_data = json.loads(show_result["stdout"])
                return state_data
            print(
                f"⚠️ Could not retrieve state for {stack_name}: {show_result['stderr']}"
            )
            return {}

        except Exception as e:
            print(f"❌ Error getting state for {stack_name}: {e}")
            return {}

    async def validate_configuration(self, stack_name: str) -> builtins.dict[str, Any]:
        """Validate Terraform configuration"""

        validation_result = {"valid": False, "errors": [], "warnings": []}

        try:
            if stack_name not in self.stacks:
                validation_result["errors"].append(f"Stack {stack_name} not found")
                return validation_result

            stack_dir = os.path.join(self.working_directory, stack_name)

            # Run terraform validate
            validate_result = await self._run_terraform_command(
                ["validate", "-json"], working_dir=stack_dir
            )

            if validate_result["returncode"] == 0:
                validation_result["valid"] = True
                print(f"✅ Configuration valid for {stack_name}")
            else:
                # Parse validation errors
                try:
                    error_data = json.loads(validate_result["stdout"])
                    if "diagnostics" in error_data:
                        for diagnostic in error_data["diagnostics"]:
                            if diagnostic["severity"] == "error":
                                validation_result["errors"].append(
                                    diagnostic["summary"]
                                )
                            else:
                                validation_result["warnings"].append(
                                    diagnostic["summary"]
                                )
                except:
                    validation_result["errors"].append(validate_result["stderr"])

                print(f"❌ Configuration invalid for {stack_name}")

        except Exception as e:
            validation_result["errors"].append(str(e))

        return validation_result

    async def _generate_terraform_config(
        self, stack: InfrastructureStack, stack_dir: str
    ):
        """Generate Terraform configuration files"""

        # Main configuration file
        main_tf = {
            "terraform": {
                "required_providers": self._get_required_providers(stack.provider)
            }
        }

        # Add backend configuration
        if stack.backend_config:
            main_tf["terraform"]["backend"] = stack.backend_config

        # Provider configuration
        provider_config = self._get_provider_config(stack.provider, stack.region)
        if provider_config:
            main_tf["provider"] = provider_config

        # Variables
        if stack.variables:
            variables_tf = {}
            for var_name, var_config in stack.variables.items():
                variables_tf[f'variable "{var_name}"'] = var_config

            with open(os.path.join(stack_dir, "variables.tf"), "w") as f:
                self._write_tf_config(f, variables_tf)

        # Resources
        resources_tf = {}
        for resource in stack.resources:
            resource_config = self._convert_resource_to_terraform(resource)
            resources_tf.update(resource_config)

        # Outputs
        if stack.outputs:
            outputs_tf = {}
            for output_name, output_config in stack.outputs.items():
                outputs_tf[f'output "{output_name}"'] = output_config

            with open(os.path.join(stack_dir, "outputs.tf"), "w") as f:
                self._write_tf_config(f, outputs_tf)

        # Write main configuration
        with open(os.path.join(stack_dir, "main.tf"), "w") as f:
            self._write_tf_config(f, {**main_tf, **resources_tf})

    def _get_required_providers(
        self, provider: CloudProvider
    ) -> builtins.dict[str, Any]:
        """Get required Terraform providers"""

        providers = {}

        if provider == CloudProvider.AWS:
            providers["aws"] = {"source": "hashicorp/aws", "version": "~> 5.0"}
        elif provider == CloudProvider.AZURE:
            providers["azurerm"] = {"source": "hashicorp/azurerm", "version": "~> 3.0"}
        elif provider == CloudProvider.GCP:
            providers["google"] = {"source": "hashicorp/google", "version": "~> 4.0"}
        elif provider == CloudProvider.KUBERNETES:
            providers["kubernetes"] = {
                "source": "hashicorp/kubernetes",
                "version": "~> 2.0",
            }

        return providers

    def _get_provider_config(
        self, provider: CloudProvider, region: str
    ) -> builtins.dict[str, Any]:
        """Get provider configuration"""

        if provider == CloudProvider.AWS:
            return {"aws": {"region": region}}
        if provider == CloudProvider.AZURE:
            return {"azurerm": {"features": {}}}
        if provider == CloudProvider.GCP:
            return {"google": {"region": region}}

        return {}

    def _convert_resource_to_terraform(
        self, resource: InfrastructureResource
    ) -> builtins.dict[str, Any]:
        """Convert infrastructure resource to Terraform configuration"""

        # Get provider prefix
        provider_prefix = {
            CloudProvider.AWS: "aws",
            CloudProvider.AZURE: "azurerm",
            CloudProvider.GCP: "google",
            CloudProvider.KUBERNETES: "kubernetes",
        }.get(resource.provider, "local")

        # Get resource type mapping
        resource_type_map = {
            ResourceType.COMPUTE: f"{provider_prefix}_instance",
            ResourceType.STORAGE: f"{provider_prefix}_storage_bucket",
            ResourceType.NETWORK: f"{provider_prefix}_vpc",
            ResourceType.DATABASE: f"{provider_prefix}_db_instance",
            ResourceType.SECURITY: f"{provider_prefix}_security_group",
        }

        tf_resource_type = resource_type_map.get(
            resource.resource_type, f"{provider_prefix}_resource"
        )

        # Build resource configuration
        resource_config = resource.configuration.copy()

        # Add tags
        if resource.tags:
            if (
                resource.provider == CloudProvider.AWS
                or resource.provider == CloudProvider.AZURE
            ):
                resource_config["tags"] = resource.tags
            elif resource.provider == CloudProvider.GCP:
                resource_config["labels"] = resource.tags

        # Add lifecycle configuration
        lifecycle = {}
        if resource.prevent_destroy:
            lifecycle["prevent_destroy"] = True
        if resource.create_before_destroy:
            lifecycle["create_before_destroy"] = True

        if lifecycle:
            resource_config["lifecycle"] = lifecycle

        # Add dependencies
        if resource.depends_on:
            resource_config["depends_on"] = [
                f"{tf_resource_type}.{dep}" for dep in resource.depends_on
            ]

        return {f'resource "{tf_resource_type}" "{resource.name}"': resource_config}

    def _write_tf_config(self, file_handle, config: builtins.dict[str, Any]):
        """Write Terraform configuration to file"""

        # This is a simplified HCL writer
        # In production, would use a proper HCL library

        def write_value(value, indent=0):
            spaces = "  " * indent

            if isinstance(value, dict):
                file_handle.write("{\n")
                for k, v in value.items():
                    file_handle.write(f"{spaces}  {k} = ")
                    write_value(v, indent + 1)
                    file_handle.write("\n")
                file_handle.write(f"{spaces}}}")
            elif isinstance(value, list):
                file_handle.write("[\n")
                for item in value:
                    file_handle.write(f"{spaces}  ")
                    write_value(item, indent + 1)
                    file_handle.write(",\n")
                file_handle.write(f"{spaces}]")
            elif isinstance(value, str):
                file_handle.write(f'"{value}"')
            elif isinstance(value, bool):
                file_handle.write("true" if value else "false")
            else:
                file_handle.write(str(value))

        for key, value in config.items():
            if key.startswith(
                ("resource", "variable", "output", "terraform", "provider")
            ):
                file_handle.write(f"{key} ")
                write_value(value)
                file_handle.write("\n\n")
            else:
                file_handle.write(f"{key} = ")
                write_value(value)
                file_handle.write("\n")

    async def _run_terraform_command(
        self, args: builtins.list[str], working_dir: str
    ) -> builtins.dict[str, Any]:
        """Run Terraform command"""

        try:
            # Build full command
            cmd = [self.terraform_binary] + args

            # Run command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            return {
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8"),
                "stderr": stderr.decode("utf-8"),
            }

        except Exception as e:
            return {"returncode": -1, "stdout": "", "stderr": str(e)}

    async def _parse_plan_output(
        self, operation: InfrastructureOperation, plan_output: str
    ):
        """Parse Terraform plan output"""

        # Simple parsing - in production would use structured JSON output
        lines = plan_output.split("\n")

        for line in lines:
            if "Plan:" in line:
                # Extract numbers from plan summary
                parts = line.split()
                for i, part in enumerate(parts):
                    if "add" in part and i > 0:
                        try:
                            operation.resources_to_create = int(parts[i - 1])
                        except:
                            pass
                    elif "change" in part and i > 0:
                        try:
                            operation.resources_to_update = int(parts[i - 1])
                        except:
                            pass
                    elif "destroy" in part and i > 0:
                        try:
                            operation.resources_to_destroy = int(parts[i - 1])
                        except:
                            pass

    async def _update_resource_states(self, stack: InfrastructureStack):
        """Update resource states after successful apply"""

        for resource in stack.resources:
            resource.status = "created"
            resource.last_modified = datetime.now()
            if not resource.created_at:
                resource.created_at = datetime.now()


class PulumiProvider(IaCProviderBase):
    """
    Pulumi Infrastructure as Code provider

    Features:
    - Pulumi CLI integration
    - Multi-language support
    - Stack management
    - State backends
    """

    def __init__(self, provider: CloudProvider):
        super().__init__(IaCTool.PULUMI, provider)
        self.pulumi_binary = "pulumi"
        self.working_directory = "/tmp/pulumi"

        os.makedirs(self.working_directory, exist_ok=True)

    async def initialize_stack(self, stack: InfrastructureStack) -> bool:
        """Initialize Pulumi stack"""

        try:
            print(f"🏗️ Initializing Pulumi stack: {stack.name}")

            # Create stack directory
            stack_dir = os.path.join(self.working_directory, stack.name)
            os.makedirs(stack_dir, exist_ok=True)

            # Generate Pulumi program
            await self._generate_pulumi_program(stack, stack_dir)

            # Initialize Pulumi project
            init_result = await self._run_pulumi_command(
                ["stack", "init", stack.name], working_dir=stack_dir
            )

            if (
                init_result["returncode"] != 0
                and "already exists" not in init_result["stderr"]
            ):
                print(f"❌ Pulumi stack init failed: {init_result['stderr']}")
                return False

            stack.created_at = datetime.now()
            self.stacks[stack.name] = stack

            print(f"✅ Pulumi stack initialized: {stack.name}")
            return True

        except Exception as e:
            print(f"❌ Failed to initialize Pulumi stack {stack.name}: {e}")
            return False

    async def plan_stack(self, stack_name: str) -> InfrastructureOperation:
        """Generate Pulumi preview"""

        if stack_name not in self.stacks:
            raise ValueError(f"Stack {stack_name} not found")

        # Create operation
        operation = InfrastructureOperation(
            operation_id=f"preview_{stack_name}_{int(datetime.now().timestamp())}",
            stack_name=stack_name,
            operation_type="preview",
            started_at=datetime.now(),
            dry_run=True,
        )

        self.operations[operation.operation_id] = operation

        try:
            print(f"📋 Previewing Pulumi stack: {stack_name}")
            operation.status = OperationStatus.RUNNING

            stack_dir = os.path.join(self.working_directory, stack_name)

            # Run pulumi preview
            preview_result = await self._run_pulumi_command(
                ["preview", "--json"], working_dir=stack_dir
            )

            operation.plan_output = preview_result["stdout"]

            if preview_result["returncode"] == 0:
                operation.status = OperationStatus.SUCCEEDED
                print(f"📋 Preview completed for {stack_name}")
            else:
                operation.status = OperationStatus.FAILED
                operation.error_message = preview_result["stderr"]
                print(f"❌ Preview failed for {stack_name}: {preview_result['stderr']}")

        except Exception as e:
            operation.status = OperationStatus.FAILED
            operation.error_message = str(e)
            print(f"❌ Preview error for {stack_name}: {e}")

        finally:
            operation.completed_at = datetime.now()
            operation.duration = (
                operation.completed_at - operation.started_at
            ).total_seconds()

        return operation

    async def apply_stack(
        self, stack_name: str, auto_approve: bool = False
    ) -> InfrastructureOperation:
        """Apply Pulumi stack"""

        if stack_name not in self.stacks:
            raise ValueError(f"Stack {stack_name} not found")

        # Create operation
        operation = InfrastructureOperation(
            operation_id=f"up_{stack_name}_{int(datetime.now().timestamp())}",
            stack_name=stack_name,
            operation_type="up",
            started_at=datetime.now(),
            auto_approve=auto_approve,
        )

        self.operations[operation.operation_id] = operation

        try:
            print(f"🚀 Updating Pulumi stack: {stack_name}")
            operation.status = OperationStatus.RUNNING

            stack_dir = os.path.join(self.working_directory, stack_name)

            # Build up command
            up_cmd = ["up", "--json"]
            if auto_approve:
                up_cmd.append("--yes")

            # Run pulumi up
            up_result = await self._run_pulumi_command(up_cmd, working_dir=stack_dir)

            operation.apply_output = up_result["stdout"]

            if up_result["returncode"] == 0:
                operation.status = OperationStatus.SUCCEEDED
                self.stacks[stack_name].last_deployed = datetime.now()
                print(f"✅ Update completed for {stack_name}")
            else:
                operation.status = OperationStatus.FAILED
                operation.error_message = up_result["stderr"]
                print(f"❌ Update failed for {stack_name}: {up_result['stderr']}")

        except Exception as e:
            operation.status = OperationStatus.FAILED
            operation.error_message = str(e)
            print(f"❌ Update error for {stack_name}: {e}")

        finally:
            operation.completed_at = datetime.now()
            operation.duration = (
                operation.completed_at - operation.started_at
            ).total_seconds()

        return operation

    async def destroy_stack(
        self, stack_name: str, auto_approve: bool = False
    ) -> InfrastructureOperation:
        """Destroy Pulumi stack"""

        if stack_name not in self.stacks:
            raise ValueError(f"Stack {stack_name} not found")

        # Create operation
        operation = InfrastructureOperation(
            operation_id=f"destroy_{stack_name}_{int(datetime.now().timestamp())}",
            stack_name=stack_name,
            operation_type="destroy",
            started_at=datetime.now(),
            auto_approve=auto_approve,
        )

        self.operations[operation.operation_id] = operation

        try:
            print(f"💥 Destroying Pulumi stack: {stack_name}")
            operation.status = OperationStatus.RUNNING

            stack_dir = os.path.join(self.working_directory, stack_name)

            # Build destroy command
            destroy_cmd = ["destroy", "--json"]
            if auto_approve:
                destroy_cmd.append("--yes")

            # Run pulumi destroy
            destroy_result = await self._run_pulumi_command(
                destroy_cmd, working_dir=stack_dir
            )

            if destroy_result["returncode"] == 0:
                operation.status = OperationStatus.SUCCEEDED
                print(f"✅ Destroy completed for {stack_name}")

                # Remove stack
                await self._run_pulumi_command(
                    ["stack", "rm", stack_name, "--yes"], working_dir=stack_dir
                )

                # Clean up
                shutil.rmtree(stack_dir, ignore_errors=True)
                if stack_name in self.stacks:
                    del self.stacks[stack_name]
            else:
                operation.status = OperationStatus.FAILED
                operation.error_message = destroy_result["stderr"]
                print(f"❌ Destroy failed for {stack_name}: {destroy_result['stderr']}")

        except Exception as e:
            operation.status = OperationStatus.FAILED
            operation.error_message = str(e)
            print(f"❌ Destroy error for {stack_name}: {e}")

        finally:
            operation.completed_at = datetime.now()
            operation.duration = (
                operation.completed_at - operation.started_at
            ).total_seconds()

        return operation

    async def get_stack_state(self, stack_name: str) -> builtins.dict[str, Any]:
        """Get current Pulumi stack state"""

        if stack_name not in self.stacks:
            return {}

        try:
            stack_dir = os.path.join(self.working_directory, stack_name)

            # Run pulumi stack export
            export_result = await self._run_pulumi_command(
                ["stack", "export"], working_dir=stack_dir
            )

            if export_result["returncode"] == 0:
                state_data = json.loads(export_result["stdout"])
                return state_data
            print(
                f"⚠️ Could not retrieve state for {stack_name}: {export_result['stderr']}"
            )
            return {}

        except Exception as e:
            print(f"❌ Error getting state for {stack_name}: {e}")
            return {}

    async def validate_configuration(self, stack_name: str) -> builtins.dict[str, Any]:
        """Validate Pulumi configuration"""

        validation_result = {"valid": True, "errors": [], "warnings": []}

        try:
            if stack_name not in self.stacks:
                validation_result["valid"] = False
                validation_result["errors"].append(f"Stack {stack_name} not found")
                return validation_result

            # Pulumi doesn't have a separate validate command
            # We can check if preview works without errors
            preview_op = await self.plan_stack(stack_name)

            if preview_op.status == OperationStatus.SUCCEEDED:
                validation_result["valid"] = True
                print(f"✅ Configuration valid for {stack_name}")
            else:
                validation_result["valid"] = False
                validation_result["errors"].append(
                    preview_op.error_message or "Preview failed"
                )
                print(f"❌ Configuration invalid for {stack_name}")

        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(str(e))

        return validation_result

    async def _generate_pulumi_program(
        self, stack: InfrastructureStack, stack_dir: str
    ):
        """Generate Pulumi program"""

        # Create Pulumi.yaml
        pulumi_yaml = {
            "name": stack.name,
            "runtime": "python",
            "description": stack.description,
        }

        with open(os.path.join(stack_dir, "Pulumi.yaml"), "w") as f:
            yaml.dump(pulumi_yaml, f)

        # Create requirements.txt
        requirements = ["pulumi>=3.0.0,<4.0.0"]

        if stack.provider == CloudProvider.AWS:
            requirements.append("pulumi-aws>=5.0.0,<6.0.0")
        elif stack.provider == CloudProvider.AZURE:
            requirements.append("pulumi-azure-native>=1.0.0,<2.0.0")
        elif stack.provider == CloudProvider.GCP:
            requirements.append("pulumi-gcp>=6.0.0,<7.0.0")
        elif stack.provider == CloudProvider.KUBERNETES:
            requirements.append("pulumi-kubernetes>=3.0.0,<4.0.0")

        with open(os.path.join(stack_dir, "requirements.txt"), "w") as f:
            f.write("\n".join(requirements))

        # Create __main__.py
        main_py = self._generate_python_program(stack)

        with open(os.path.join(stack_dir, "__main__.py"), "w") as f:
            f.write(main_py)

    def _generate_python_program(self, stack: InfrastructureStack) -> str:
        """Generate Pulumi Python program"""

        # This is a simplified program generator
        # In production, would have more sophisticated resource mapping

        imports = ["import pulumi"]

        if stack.provider == CloudProvider.AWS:
            imports.append("import pulumi_aws as aws")
        elif stack.provider == CloudProvider.AZURE:
            imports.append("import pulumi_azure_native as azure")
        elif stack.provider == CloudProvider.GCP:
            imports.append("import pulumi_gcp as gcp")
        elif stack.provider == CloudProvider.KUBERNETES:
            imports.append("import pulumi_kubernetes as k8s")

        program = "\n".join(imports) + "\n\n"

        # Add configuration
        if stack.variables:
            program += "# Configuration\n"
            for var_name in stack.variables.keys():
                program += f'{var_name} = pulumi.Config().get("{var_name}")\n'
            program += "\n"

        # Add resources
        if stack.resources:
            program += "# Resources\n"
            for resource in stack.resources:
                resource_code = self._generate_resource_code(resource, stack.provider)
                program += resource_code + "\n"

        # Add outputs
        if stack.outputs:
            program += "# Outputs\n"
            for output_name, output_config in stack.outputs.items():
                value = output_config.get("value", f"{output_name}_value")
                program += f'pulumi.export("{output_name}", {value})\n'

        return program

    def _generate_resource_code(
        self, resource: InfrastructureResource, provider: CloudProvider
    ) -> str:
        """Generate Pulumi resource code"""

        # Simplified resource code generation
        provider_map = {
            CloudProvider.AWS: "aws",
            CloudProvider.AZURE: "azure",
            CloudProvider.GCP: "gcp",
            CloudProvider.KUBERNETES: "k8s",
        }

        provider_prefix = provider_map.get(provider, "local")

        # Map resource types to Pulumi resources
        resource_type_map = {
            ResourceType.COMPUTE: f"{provider_prefix}.ec2.Instance",
            ResourceType.STORAGE: f"{provider_prefix}.s3.Bucket",
            ResourceType.NETWORK: f"{provider_prefix}.ec2.Vpc",
            ResourceType.DATABASE: f"{provider_prefix}.rds.Instance",
        }

        pulumi_resource_type = resource_type_map.get(
            resource.resource_type, f"{provider_prefix}.Resource"
        )

        # Build arguments
        args = []
        for key, value in resource.configuration.items():
            if isinstance(value, str):
                args.append(f'    {key}="{value}"')
            else:
                args.append(f"    {key}={value}")

        # Add tags
        if resource.tags:
            tags_str = ", ".join([f'"{k}": "{v}"' for k, v in resource.tags.items()])
            args.append(f"    tags={{{tags_str}}}")

        args_str = ",\n".join(args)

        return f"""{resource.name} = {pulumi_resource_type}(
    "{resource.name}",
{args_str}
)"""

    async def _run_pulumi_command(
        self, args: builtins.list[str], working_dir: str
    ) -> builtins.dict[str, Any]:
        """Run Pulumi command"""

        try:
            # Build full command
            cmd = [self.pulumi_binary] + args

            # Run command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            return {
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8"),
                "stderr": stderr.decode("utf-8"),
            }

        except Exception as e:
            return {"returncode": -1, "stdout": "", "stderr": str(e)}


class InfrastructureOrchestrator:
    """
    Infrastructure orchestration and management

    Features:
    - Multi-tool support (Terraform, Pulumi)
    - Stack lifecycle management
    - Drift detection and remediation
    - Cost optimization
    - Resource tagging and governance
    """

    def __init__(self):
        # IaC providers
        self.providers: builtins.dict[
            builtins.tuple[IaCTool, CloudProvider], IaCProviderBase
        ] = {}

        # Stack registry
        self.stacks: builtins.dict[str, InfrastructureStack] = {}
        self.operations: builtins.dict[str, InfrastructureOperation] = {}

        # Configuration
        self.default_tags = {
            "ManagedBy": "Marty-Framework",
            "Environment": "unknown",
            "Owner": "DevOps",
            "CreatedAt": datetime.now().strftime("%Y-%m-%d"),
        }

    def register_provider(self, tool: IaCTool, provider: CloudProvider):
        """Register Infrastructure as Code provider"""

        if tool == IaCTool.TERRAFORM:
            iac_provider = TerraformProvider(provider)
        elif tool == IaCTool.PULUMI:
            iac_provider = PulumiProvider(provider)
        else:
            raise ValueError(f"Unsupported IaC tool: {tool.value}")

        self.providers[(tool, provider)] = iac_provider
        print(f"📋 Registered {tool.value} provider for {provider.value}")

    async def deploy_stack(
        self,
        stack: InfrastructureStack,
        auto_approve: bool = False,
        validate_first: bool = True,
    ) -> InfrastructureOperation:
        """Deploy infrastructure stack"""

        # Get provider
        provider_key = (stack.tool, stack.provider)
        if provider_key not in self.providers:
            self.register_provider(stack.tool, stack.provider)

        iac_provider = self.providers[provider_key]

        try:
            print(f"🚀 Deploying stack: {stack.name}")

            # Add default tags
            for resource in stack.resources:
                resource.tags = {**self.default_tags, **resource.tags}
                resource.tags["StackName"] = stack.name
                resource.tags["Environment"] = stack.environment

            # Initialize stack if not already done
            if stack.name not in iac_provider.stacks:
                init_success = await iac_provider.initialize_stack(stack)
                if not init_success:
                    raise Exception(f"Failed to initialize stack {stack.name}")

            # Validate configuration
            if validate_first:
                validation = await iac_provider.validate_configuration(stack.name)
                if not validation["valid"]:
                    raise Exception(
                        f"Configuration validation failed: {validation['errors']}"
                    )

            # Generate plan
            plan_operation = await iac_provider.plan_stack(stack.name)
            if plan_operation.status != OperationStatus.SUCCEEDED:
                raise Exception(f"Planning failed: {plan_operation.error_message}")

            # Apply changes
            apply_operation = await iac_provider.apply_stack(stack.name, auto_approve)

            # Store in registry
            self.stacks[stack.name] = stack
            self.operations[apply_operation.operation_id] = apply_operation

            return apply_operation

        except Exception as e:
            print(f"❌ Failed to deploy stack {stack.name}: {e}")
            # Create failed operation
            failed_operation = InfrastructureOperation(
                operation_id=f"failed_{stack.name}_{int(datetime.now().timestamp())}",
                stack_name=stack.name,
                operation_type="apply",
                started_at=datetime.now(),
                status=OperationStatus.FAILED,
                error_message=str(e),
                completed_at=datetime.now(),
            )
            self.operations[failed_operation.operation_id] = failed_operation
            return failed_operation

    async def destroy_stack(
        self, stack_name: str, auto_approve: bool = False
    ) -> InfrastructureOperation:
        """Destroy infrastructure stack"""

        if stack_name not in self.stacks:
            raise ValueError(f"Stack {stack_name} not found")

        stack = self.stacks[stack_name]
        provider_key = (stack.tool, stack.provider)

        if provider_key not in self.providers:
            raise ValueError(
                f"Provider not available for {stack.tool.value}/{stack.provider.value}"
            )

        iac_provider = self.providers[provider_key]

        # Destroy stack
        destroy_operation = await iac_provider.destroy_stack(stack_name, auto_approve)

        # Remove from registry if successful
        if destroy_operation.status == OperationStatus.SUCCEEDED:
            del self.stacks[stack_name]

        self.operations[destroy_operation.operation_id] = destroy_operation
        return destroy_operation

    async def detect_drift(self, stack_name: str) -> builtins.dict[str, Any]:
        """Detect infrastructure drift"""

        if stack_name not in self.stacks:
            raise ValueError(f"Stack {stack_name} not found")

        stack = self.stacks[stack_name]
        provider_key = (stack.tool, stack.provider)

        if provider_key not in self.providers:
            raise ValueError("Provider not available")

        iac_provider = self.providers[provider_key]

        try:
            print(f"🔍 Detecting drift for stack: {stack_name}")

            # Get current state
            current_state = await iac_provider.get_stack_state(stack_name)

            # Generate plan to see changes
            plan_operation = await iac_provider.plan_stack(stack_name)

            drift_detected = (
                plan_operation.resources_to_create > 0
                or plan_operation.resources_to_update > 0
                or plan_operation.resources_to_destroy > 0
            )

            drift_result = {
                "stack_name": stack_name,
                "drift_detected": drift_detected,
                "resources_to_create": plan_operation.resources_to_create,
                "resources_to_update": plan_operation.resources_to_update,
                "resources_to_destroy": plan_operation.resources_to_destroy,
                "plan_output": plan_operation.plan_output,
                "detected_at": datetime.now().isoformat(),
            }

            if drift_detected:
                print(f"⚠️ Drift detected for {stack_name}")
            else:
                print(f"✅ No drift detected for {stack_name}")

            return drift_result

        except Exception as e:
            print(f"❌ Error detecting drift for {stack_name}: {e}")
            return {
                "stack_name": stack_name,
                "error": str(e),
                "detected_at": datetime.now().isoformat(),
            }

    def get_stack_status(self, stack_name: str) -> builtins.dict[str, Any] | None:
        """Get stack status and information"""

        if stack_name not in self.stacks:
            return None

        stack = self.stacks[stack_name]

        # Get recent operations
        stack_operations = [
            op for op in self.operations.values() if op.stack_name == stack_name
        ]

        stack_operations.sort(key=lambda x: x.started_at, reverse=True)

        return {
            "stack": stack.to_dict(),
            "recent_operations": [op.to_dict() for op in stack_operations[:5]],
            "total_resources": len(stack.resources),
            "resource_types": list(set(r.resource_type.value for r in stack.resources)),
        }

    def list_stacks(self) -> builtins.list[builtins.dict[str, Any]]:
        """List all registered stacks"""

        return [
            {
                "name": name,
                "provider": stack.provider.value,
                "tool": stack.tool.value,
                "environment": stack.environment,
                "resource_count": len(stack.resources),
                "last_deployed": stack.last_deployed.isoformat()
                if stack.last_deployed
                else None,
            }
            for name, stack in self.stacks.items()
        ]

    async def generate_cost_report(
        self, stack_name: str | None = None
    ) -> builtins.dict[str, Any]:
        """Generate cost analysis report"""

        # Mock cost analysis - in production would integrate with cloud billing APIs
        cost_report = {
            "generated_at": datetime.now().isoformat(),
            "currency": "USD",
            "total_estimated_monthly_cost": 0.0,
            "stacks": {},
        }

        stacks_to_analyze = [stack_name] if stack_name else list(self.stacks.keys())

        for name in stacks_to_analyze:
            if name not in self.stacks:
                continue

            stack = self.stacks[name]

            # Mock cost calculation
            stack_cost = 0.0
            resource_costs = {}

            for resource in stack.resources:
                # Simplified cost estimation
                if resource.resource_type == ResourceType.COMPUTE:
                    cost = 50.0  # $50/month for compute
                elif resource.resource_type == ResourceType.DATABASE:
                    cost = 100.0  # $100/month for database
                elif resource.resource_type == ResourceType.STORAGE:
                    cost = 10.0  # $10/month for storage
                else:
                    cost = 20.0  # $20/month for other resources

                resource_costs[resource.name] = cost
                stack_cost += cost

            cost_report["stacks"][name] = {
                "monthly_cost": stack_cost,
                "resource_costs": resource_costs,
                "resource_count": len(stack.resources),
            }

            cost_report["total_estimated_monthly_cost"] += stack_cost

        return cost_report


# Example usage and demo
async def main():
    """Example usage of Infrastructure as Code framework"""

    print("=== Infrastructure as Code Demo ===")

    # Initialize orchestrator
    orchestrator = InfrastructureOrchestrator()

    # Create infrastructure resources
    vpc_resource = InfrastructureResource(
        name="main_vpc",
        resource_type=ResourceType.NETWORK,
        provider=CloudProvider.AWS,
        configuration={
            "cidr_block": "10.0.0.0/16",
            "enable_dns_hostnames": True,
            "enable_dns_support": True,
        },
        tags={"Name": "Main VPC", "Purpose": "Microservices"},
    )

    security_group_resource = InfrastructureResource(
        name="web_sg",
        resource_type=ResourceType.SECURITY,
        provider=CloudProvider.AWS,
        configuration={
            "name": "web-security-group",
            "description": "Security group for web servers",
            "vpc_id": "${aws_vpc.main_vpc.id}",
            "ingress": [
                {
                    "from_port": 80,
                    "to_port": 80,
                    "protocol": "tcp",
                    "cidr_blocks": ["0.0.0.0/0"],
                },
                {
                    "from_port": 443,
                    "to_port": 443,
                    "protocol": "tcp",
                    "cidr_blocks": ["0.0.0.0/0"],
                },
            ],
        },
        depends_on=["main_vpc"],
        tags={"Name": "Web Security Group"},
    )

    # Create infrastructure stack
    web_stack = InfrastructureStack(
        name="web-infrastructure",
        description="Web application infrastructure",
        provider=CloudProvider.AWS,
        tool=IaCTool.TERRAFORM,
        resources=[vpc_resource, security_group_resource],
        variables={
            "environment": {
                "description": "Environment name",
                "type": "string",
                "default": "development",
            },
            "instance_type": {
                "description": "EC2 instance type",
                "type": "string",
                "default": "t3.micro",
            },
        },
        outputs={
            "vpc_id": {"description": "VPC ID", "value": "${aws_vpc.main_vpc.id}"},
            "security_group_id": {
                "description": "Security Group ID",
                "value": "${aws_security_group.web_sg.id}",
            },
        },
        environment="development",
        region="us-east-1",
    )

    # Deploy stack
    print("\n🚀 Deploying infrastructure stack")
    deploy_operation = await orchestrator.deploy_stack(
        web_stack, auto_approve=True, validate_first=True
    )

    print(f"Deployment result: {deploy_operation.status.value}")
    if deploy_operation.error_message:
        print(f"Error: {deploy_operation.error_message}")

    # Check stack status
    print("\n📊 Stack Status")
    stack_status = orchestrator.get_stack_status("web-infrastructure")
    if stack_status:
        print(f"Stack: {stack_status['stack']['name']}")
        print(f"Provider: {stack_status['stack']['provider']}")
        print(f"Tool: {stack_status['stack']['tool']}")
        print(f"Resources: {stack_status['total_resources']}")
        print(f"Resource types: {stack_status['resource_types']}")

    # Detect drift
    print("\n🔍 Detecting drift")
    drift_result = await orchestrator.detect_drift("web-infrastructure")
    print(f"Drift detected: {drift_result.get('drift_detected', False)}")

    # Generate cost report
    print("\n💰 Cost Analysis")
    cost_report = await orchestrator.generate_cost_report()
    print(
        f"Total estimated monthly cost: ${cost_report['total_estimated_monthly_cost']:.2f}"
    )

    for stack_name, stack_cost in cost_report["stacks"].items():
        print(f"  {stack_name}: ${stack_cost['monthly_cost']:.2f}/month")

    # List all stacks
    print("\n📋 All Stacks")
    all_stacks = orchestrator.list_stacks()
    for stack_info in all_stacks:
        print(
            f"  {stack_info['name']} ({stack_info['tool']}/{stack_info['provider']}) - {stack_info['resource_count']} resources"
        )


if __name__ == "__main__":
    asyncio.run(main())
