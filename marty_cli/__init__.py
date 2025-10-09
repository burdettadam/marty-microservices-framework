"""
Marty Microservices Framework CLI

A comprehensive command-line interface for scaffolding, managing, and deploying
microservices using the Marty framework. Provides project generation, template
management, dependency handling, and deployment automation.

Features:
- Project scaffolding with multiple templates
- Dependency management and virtual environment setup
- Docker and Kubernetes deployment generation
- Configuration management and validation
- Testing framework integration
- CI/CD pipeline generation
- Service discovery integration
- Monitoring and observability setup

Author: Marty Framework Team
Version: 1.0.0
"""

import asyncio
import builtins
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import jinja2
import requests
import toml
import yaml
from cookiecutter.main import cookiecutter
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

__version__ = "1.0.0"

# Initialize rich console
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("marty-cli")


@dataclass
class TemplateConfig:
    """Template configuration."""

    name: str
    description: str
    path: str
    category: str = "service"
    dependencies: builtins.list[str] = field(default_factory=list)
    post_hooks: builtins.list[str] = field(default_factory=list)
    variables: builtins.dict[str, Any] = field(default_factory=dict)
    python_version: str = "3.11"
    framework_version: str = "1.0.0"


@dataclass
class ProjectConfig:
    """Project configuration."""

    name: str
    template: str
    path: str
    python_version: str = "3.11"
    author: str = ""
    email: str = ""
    description: str = ""
    license: str = "MIT"
    git_repo: str = ""
    docker_enabled: bool = True
    kubernetes_enabled: bool = True
    monitoring_enabled: bool = True
    testing_enabled: bool = True
    ci_cd_enabled: bool = True
    environment: str = "development"
    skip_prompts: bool = False
    variables: builtins.dict[str, Any] = field(default_factory=dict)


class MartyTemplateManager:
    """Manage Marty framework templates."""

    def __init__(self, framework_path: Path | None = None):
        self.framework_path = framework_path or self._find_framework_path()
        self.templates_path = self.framework_path / "templates"
        self.cache_path = Path.home() / ".marty" / "cache"
        self.config_path = Path.home() / ".marty" / "config.toml"

        # Ensure directories exist
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Load configuration
        self.config = self._load_config()

    def _find_framework_path(self) -> Path:
        """Find the Marty framework installation path."""
        # Try to find in current directory structure
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            marty_path = parent / "marty-microservices-framework"
            if marty_path.exists() and (marty_path / "templates").exists():
                return marty_path

        # Try installed package location
        try:
            import marty_msf

            return Path(marty_msf.__file__).parent
        except ImportError:
            pass

        # Default fallback
        return Path(__file__).parent.parent

    def _load_config(self) -> builtins.dict[str, Any]:
        """Load CLI configuration."""
        default_config = {
            "author": "",
            "email": "",
            "default_license": "MIT",
            "default_python_version": "3.11",
            "templates": {},
            "registries": [
                "https://raw.githubusercontent.com/marty-framework/templates/main/registry.json"
            ],
        }

        if self.config_path.exists():
            try:
                return toml.load(self.config_path)
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")
                return default_config

        return default_config

    def save_config(self):
        """Save CLI configuration."""
        try:
            with open(self.config_path, "w") as f:
                toml.dump(self.config, f)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get_available_templates(self) -> builtins.dict[str, TemplateConfig]:
        """Get available templates."""
        templates = {}

        # Local templates
        if self.templates_path.exists():
            for template_dir in self.templates_path.iterdir():
                if template_dir.is_dir() and not template_dir.name.startswith("."):
                    config = self._load_template_config(template_dir)
                    if config:
                        templates[config.name] = config

        return templates

    def _load_template_config(self, template_path: Path) -> TemplateConfig | None:
        """Load template configuration."""
        config_file = template_path / "template.yaml"
        if not config_file.exists():
            # Generate default config
            return TemplateConfig(
                name=template_path.name,
                description=f"Marty {template_path.name.replace('-', ' ').title()} Template",
                path=str(template_path),
                category="service",
            )

        try:
            with open(config_file) as f:
                data = yaml.safe_load(f)
                return TemplateConfig(
                    name=data.get("name", template_path.name),
                    description=data.get("description", ""),
                    path=str(template_path),
                    category=data.get("category", "service"),
                    dependencies=data.get("dependencies", []),
                    post_hooks=data.get("post_hooks", []),
                    variables=data.get("variables", {}),
                    python_version=data.get("python_version", "3.11"),
                    framework_version=data.get("framework_version", "1.0.0"),
                )
        except Exception as e:
            logger.warning(f"Failed to load template config for {template_path}: {e}")
            return None

    def create_project(self, config: ProjectConfig) -> bool:
        """Create a new project from template."""
        try:
            templates = self.get_available_templates()
            if config.template not in templates:
                console.print(
                    f"[red]Error: Template '{config.template}' not found[/red]"
                )
                return False

            template_config = templates[config.template]

            # Prepare template variables
            context = {
                "project_name": config.name,
                "project_slug": config.name.lower().replace(" ", "-").replace("_", "-"),
                "project_description": config.description,
                "author_name": config.author,
                "author_email": config.email,
                "license": config.license,
                "python_version": config.python_version,
                "framework_version": template_config.framework_version,
                "docker_enabled": config.docker_enabled,
                "kubernetes_enabled": config.kubernetes_enabled,
                "monitoring_enabled": config.monitoring_enabled,
                "testing_enabled": config.testing_enabled,
                "ci_cd_enabled": config.ci_cd_enabled,
                "environment": config.environment,
                "git_repo": config.git_repo,
                "creation_date": datetime.now().isoformat(),
                **template_config.variables,
                **config.variables,
            }

            # Create project directory
            project_path = Path(config.path)
            if project_path.exists():
                if not Confirm.ask(f"Directory {project_path} exists. Overwrite?"):
                    return False
                shutil.rmtree(project_path)

            project_path.mkdir(parents=True, exist_ok=True)

            # Copy and process template
            self._process_template(Path(template_config.path), project_path, context)

            # Run post-generation hooks
            self._run_post_hooks(template_config.post_hooks, project_path, context)

            # Initialize virtual environment and dependencies
            if config.python_version:
                self._setup_python_environment(project_path, config.python_version)

            # Initialize git repository
            if config.skip_prompts:
                # In non-interactive mode, initialize git if git_repo is specified or default to True
                should_init_git = config.git_repo or True
            else:
                should_init_git = config.git_repo or Confirm.ask(
                    "Initialize git repository?"
                )

            if should_init_git:
                self._init_git_repo(project_path, config.git_repo)

            console.print(
                f"[green]✓ Project '{config.name}' created successfully at {project_path}[/green]"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            console.print(f"[red]Error creating project: {e}[/red]")
            return False

    def _process_template(
        self, template_path: Path, output_path: Path, context: builtins.dict[str, Any]
    ):
        """Process template files with Jinja2."""
        jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_path)),
            undefined=jinja2.StrictUndefined,
            autoescape=True,
        )

        # Define template filters
        jinja_env.filters["slug"] = (
            lambda x: x.lower().replace(" ", "-").replace("_", "-")
        )
        jinja_env.filters["snake"] = (
            lambda x: x.lower().replace(" ", "_").replace("-", "_")
        )
        jinja_env.filters["pascal"] = lambda x: "".join(
            word.capitalize() for word in x.replace("-", " ").replace("_", " ").split()
        )
        jinja_env.filters["kebab"] = (
            lambda x: x.lower().replace(" ", "-").replace("_", "-")
        )

        for root, dirs, files in os.walk(template_path):
            # Skip hidden directories and template config
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

            root_path = Path(root)
            relative_path = root_path.relative_to(template_path)

            # Process directory names
            processed_relative = self._process_path_template(
                str(relative_path), context
            )
            output_dir = output_path / processed_relative
            output_dir.mkdir(parents=True, exist_ok=True)

            for file in files:
                if file.startswith(".") or file in ["template.yaml", "__pycache__"]:
                    continue

                file_path = root_path / file

                # Process filename
                processed_filename = self._process_path_template(file, context)
                output_file = output_dir / processed_filename

                # Process file content
                try:
                    if file.endswith(
                        (
                            ".py",
                            ".yaml",
                            ".yml",
                            ".toml",
                            ".md",
                            ".txt",
                            ".sh",
                            ".dockerfile",
                            ".env",
                        )
                    ):
                        # Text files - process with Jinja2
                        with open(file_path, encoding="utf-8") as f:
                            content = f.read()

                        template = jinja_env.from_string(content)
                        processed_content = template.render(**context)

                        with open(output_file, "w", encoding="utf-8") as f:
                            f.write(processed_content)
                    else:
                        # Binary files - copy directly
                        shutil.copy2(file_path, output_file)

                except Exception as e:
                    logger.warning(f"Failed to process {file_path}: {e}")
                    # Fallback to direct copy
                    shutil.copy2(file_path, output_file)

    def _process_path_template(
        self, path: str, context: builtins.dict[str, Any]
    ) -> str:
        """Process path templates."""
        try:
            template = jinja2.Template(path)
            return template.render(**context)
        except Exception:
            return path

    def _run_post_hooks(
        self,
        hooks: builtins.list[str],
        project_path: Path,
        context: builtins.dict[str, Any],
    ):
        """Run post-generation hooks."""
        for hook in hooks:
            try:
                # Process hook command with context
                template = jinja2.Template(hook)
                command = template.render(**context)

                console.print(f"[blue]Running post-hook: {command}[/blue]")

                # Parse command safely without shell=True
                import shlex

                command_args = shlex.split(command)

                result = subprocess.run(
                    command_args,
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode != 0:
                    logger.warning(f"Post-hook failed: {command}\n{result.stderr}")
                else:
                    logger.info(f"Post-hook succeeded: {command}")

            except Exception as e:
                logger.warning(f"Failed to run post-hook '{hook}': {e}")

    def _setup_python_environment(self, project_path: Path, python_version: str):
        """Setup Python virtual environment and install dependencies."""
        try:
            console.print(
                f"[blue]Setting up Python {python_version} environment...[/blue]"
            )

            # Create virtual environment
            venv_path = project_path / ".venv"
            subprocess.run(
                [f"python{python_version}", "-m", "venv", str(venv_path)],
                check=True,
                cwd=project_path,
            )

            # Determine pip path
            if sys.platform == "win32":
                pip_path = venv_path / "Scripts" / "pip"
                python_path = venv_path / "Scripts" / "python"
            else:
                pip_path = venv_path / "bin" / "pip"
                python_path = venv_path / "bin" / "python"

            # Upgrade pip
            subprocess.run(
                [str(python_path), "-m", "pip", "install", "--upgrade", "pip"],
                check=True,
            )

            # Install dependencies if requirements.txt exists
            requirements_file = project_path / "requirements.txt"
            if requirements_file.exists():
                console.print("[blue]Installing dependencies...[/blue]")
                subprocess.run(
                    [str(pip_path), "install", "-r", "requirements.txt"],
                    check=True,
                    cwd=project_path,
                )

            # Install development dependencies if requirements-dev.txt exists
            dev_requirements_file = project_path / "requirements-dev.txt"
            if dev_requirements_file.exists():
                console.print("[blue]Installing development dependencies...[/blue]")
                subprocess.run(
                    [str(pip_path), "install", "-r", "requirements-dev.txt"],
                    check=True,
                    cwd=project_path,
                )

            console.print("[green]✓ Python environment setup complete[/green]")

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to setup Python environment: {e}")
        except Exception as e:
            logger.warning(f"Environment setup error: {e}")

    def _init_git_repo(self, project_path: Path, remote_url: str = ""):
        """Initialize git repository."""
        try:
            console.print("[blue]Initializing git repository...[/blue]")

            # Initialize repo
            subprocess.run(["git", "init"], check=True, cwd=project_path)

            # Add files
            subprocess.run(["git", "add", "."], check=True, cwd=project_path)

            # Initial commit
            subprocess.run(
                ["git", "commit", "-m", "Initial commit from Marty CLI"],
                check=True,
                cwd=project_path,
            )

            # Add remote if provided
            if remote_url:
                subprocess.run(
                    ["git", "remote", "add", "origin", remote_url],
                    check=True,
                    cwd=project_path,
                )
                console.print(
                    f"[green]✓ Git repository initialized with remote: {remote_url}[/green]"
                )
            else:
                console.print("[green]✓ Git repository initialized[/green]")

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to initialize git repository: {e}")
        except Exception as e:
            logger.warning(f"Git initialization error: {e}")


class MartyProjectManager:
    """Manage Marty projects and services."""

    def __init__(self):
        self.current_project = self._find_current_project()

    def _find_current_project(self) -> Path | None:
        """Find current Marty project."""
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            if (parent / "marty.toml").exists() or (parent / "pyproject.toml").exists():
                return parent
        return None

    def get_project_info(self) -> builtins.dict[str, Any] | None:
        """Get current project information."""
        if not self.current_project:
            return None

        # Try marty.toml first
        marty_config = self.current_project / "marty.toml"
        if marty_config.exists():
            try:
                return toml.load(marty_config)
            except Exception as e:
                logger.warning(f"Failed to load marty.toml: {e}")

        # Fallback to pyproject.toml
        pyproject_config = self.current_project / "pyproject.toml"
        if pyproject_config.exists():
            try:
                data = toml.load(pyproject_config)
                return data.get("tool", {}).get("marty", {})
            except Exception as e:
                logger.warning(f"Failed to load pyproject.toml: {e}")

        return None

    def build_project(self) -> bool:
        """Build current project."""
        if not self.current_project:
            console.print("[red]Error: Not in a Marty project directory[/red]")
            return False

        try:
            console.print("[blue]Building project...[/blue]")

            # Check for different build systems
            if (self.current_project / "pyproject.toml").exists():
                # Modern Python packaging
                subprocess.run(
                    ["python", "-m", "build"], check=True, cwd=self.current_project
                )
            elif (self.current_project / "setup.py").exists():
                # Legacy setup.py
                subprocess.run(
                    ["python", "setup.py", "sdist", "bdist_wheel"],
                    check=True,
                    cwd=self.current_project,
                )
            elif (self.current_project / "Dockerfile").exists():
                # Docker build
                subprocess.run(
                    [
                        "docker",
                        "build",
                        "-t",
                        f"marty/{self.current_project.name}",
                        ".",
                    ],
                    check=True,
                    cwd=self.current_project,
                )
            else:
                console.print(
                    "[yellow]Warning: No recognized build system found[/yellow]"
                )
                return False

            console.print("[green]✓ Project built successfully[/green]")
            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Build failed: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Build error: {e}[/red]")
            return False

    def test_project(self) -> bool:
        """Run project tests."""
        if not self.current_project:
            console.print("[red]Error: Not in a Marty project directory[/red]")
            return False

        try:
            console.print("[blue]Running tests...[/blue]")

            # Check for test runners
            if (self.current_project / "pytest.ini").exists() or (
                self.current_project / "pyproject.toml"
            ).exists():
                subprocess.run(
                    ["python", "-m", "pytest"], check=True, cwd=self.current_project
                )
            elif (self.current_project / "tests").exists():
                subprocess.run(
                    ["python", "-m", "unittest", "discover", "tests"],
                    check=True,
                    cwd=self.current_project,
                )
            else:
                console.print("[yellow]Warning: No test configuration found[/yellow]")
                return False

            console.print("[green]✓ All tests passed[/green]")
            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Tests failed: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Test error: {e}[/red]")
            return False

    def deploy_project(self, environment: str = "development") -> bool:
        """Deploy project."""
        if not self.current_project:
            console.print("[red]Error: Not in a Marty project directory[/red]")
            return False

        try:
            console.print(f"[blue]Deploying to {environment}...[/blue]")

            # Check for deployment configurations
            k8s_dir = self.current_project / "k8s"
            docker_compose = self.current_project / "docker-compose.yml"

            if k8s_dir.exists():
                # Kubernetes deployment
                subprocess.run(
                    ["kubectl", "apply", "-f", str(k8s_dir)],
                    check=True,
                    cwd=self.current_project,
                )
                console.print("[green]✓ Deployed to Kubernetes[/green]")
            elif docker_compose.exists():
                # Docker Compose deployment
                subprocess.run(
                    ["docker-compose", "up", "-d"], check=True, cwd=self.current_project
                )
                console.print("[green]✓ Deployed with Docker Compose[/green]")
            else:
                console.print(
                    "[yellow]Warning: No deployment configuration found[/yellow]"
                )
                return False

            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Deployment failed: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Deployment error: {e}[/red]")
            return False


# CLI Commands
@click.group()
@click.version_option(version=__version__)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx, verbose):
    """Marty Microservices Framework CLI

    A comprehensive tool for creating, managing, and deploying microservices
    using the Marty framework.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    console.print(
        Panel.fit(
            Text("Marty Microservices Framework CLI", style="bold blue"),
            subtitle=f"Version {__version__}",
        )
    )


@cli.command()
@click.argument("template")
@click.argument("name")
@click.option("--path", "-p", default=".", help="Project path")
@click.option("--author", "-a", help="Author name")
@click.option("--email", "-e", help="Author email")
@click.option("--description", "-d", help="Project description")
@click.option("--license", "-l", default="MIT", help="Project license")
@click.option("--python-version", default="3.11", help="Python version")
@click.option("--git-repo", help="Git repository URL")
@click.option("--no-docker", is_flag=True, help="Disable Docker support")
@click.option("--no-k8s", is_flag=True, help="Disable Kubernetes support")
@click.option("--no-monitoring", is_flag=True, help="Disable monitoring")
@click.option("--no-testing", is_flag=True, help="Disable testing framework")
@click.option("--no-ci-cd", is_flag=True, help="Disable CI/CD pipeline")
@click.option("--environment", default="development", help="Target environment")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.option("--skip-prompts", is_flag=True, help="Skip all interactive prompts")
def new(
    template,
    name,
    path,
    author,
    email,
    description,
    license,
    python_version,
    git_repo,
    no_docker,
    no_k8s,
    no_monitoring,
    no_testing,
    no_ci_cd,
    environment,
    interactive,
    skip_prompts,
):
    """Create a new project from template.

    TEMPLATE: Template name (e.g., fastapi-service, api-gateway-service)
    NAME: Project name
    """

    template_manager = MartyTemplateManager()

    # Interactive mode
    if interactive:
        available_templates = template_manager.get_available_templates()

        console.print("\n[bold]Available Templates:[/bold]")
        table = Table()
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Category", style="yellow")

        for tmpl_name, tmpl_config in available_templates.items():
            table.add_row(tmpl_name, tmpl_config.description, tmpl_config.category)

        console.print(table)

        if template not in available_templates:
            template = Prompt.ask(
                "\nSelect template", choices=list(available_templates.keys())
            )

        if not name:
            name = Prompt.ask("Project name")

        if not author:
            author = Prompt.ask(
                "Author name", default=template_manager.config.get("author", "")
            )

        if not email:
            email = Prompt.ask(
                "Author email", default=template_manager.config.get("email", "")
            )

        if not description:
            description = Prompt.ask(
                "Project description", default=f"A {template} microservice"
            )

    # Use config defaults
    config = template_manager.config
    author = author or config.get("author", "")
    email = email or config.get("email", "")

    # Create project configuration
    project_config = ProjectConfig(
        name=name,
        template=template,
        path=str(Path(path) / name.lower().replace(" ", "-")),
        python_version=python_version,
        author=author,
        email=email,
        description=description or f"A {template} microservice",
        license=license,
        git_repo=git_repo,
        docker_enabled=not no_docker,
        kubernetes_enabled=not no_k8s,
        monitoring_enabled=not no_monitoring,
        testing_enabled=not no_testing,
        ci_cd_enabled=not no_ci_cd,
        environment=environment,
        skip_prompts=skip_prompts,
    )

    # Create project
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Creating project...", total=None)

        success = template_manager.create_project(project_config)

        progress.update(task, completed=True)

    if success:
        console.print(f"\n[green]✓ Project '{name}' created successfully![/green]")
        console.print("\nNext steps:")
        console.print(f"  cd {project_config.path}")
        console.print("  marty run")
    else:
        console.print(f"\n[red]✗ Failed to create project '{name}'[/red]")
        sys.exit(1)


@cli.command()
def templates():
    """List available templates."""
    template_manager = MartyTemplateManager()
    available_templates = template_manager.get_available_templates()

    if not available_templates:
        console.print("[yellow]No templates found[/yellow]")
        return

    console.print("\n[bold]Available Templates:[/bold]")

    # Group by category
    categories = {}
    for tmpl_name, tmpl_config in available_templates.items():
        category = tmpl_config.category
        if category not in categories:
            categories[category] = []
        categories[category].append((tmpl_name, tmpl_config))

    for category, templates in categories.items():
        console.print(f"\n[bold yellow]{category.title()}:[/bold yellow]")

        table = Table()
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Python", style="green")

        for tmpl_name, tmpl_config in templates:
            table.add_row(
                tmpl_name, tmpl_config.description, tmpl_config.python_version
            )

        console.print(table)


@cli.command()
def build():
    """Build current project."""
    project_manager = MartyProjectManager()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Building project...", total=None)

        success = project_manager.build_project()

        progress.update(task, completed=True)

    if not success:
        sys.exit(1)


@cli.command()
def test():
    """Run project tests."""
    project_manager = MartyProjectManager()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running tests...", total=None)

        success = project_manager.test_project()

        progress.update(task, completed=True)

    if not success:
        sys.exit(1)


@cli.command()
@click.option("--environment", "-e", default="development", help="Target environment")
def deploy(environment):
    """Deploy current project."""
    project_manager = MartyProjectManager()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Deploying to {environment}...", total=None)

        success = project_manager.deploy_project(environment)

        progress.update(task, completed=True)

    if not success:
        sys.exit(1)


@cli.command()
def run():
    """Run current project in development mode."""
    project_manager = MartyProjectManager()

    if not project_manager.current_project:
        console.print("[red]Error: Not in a Marty project directory[/red]")
        sys.exit(1)

    try:
        console.print("[blue]Starting development server...[/blue]")

        # Check for different run configurations
        if (project_manager.current_project / "main.py").exists():
            subprocess.run(
                ["python", "main.py"], cwd=project_manager.current_project, check=False
            )
        elif (project_manager.current_project / "app.py").exists():
            subprocess.run(
                ["python", "app.py"], cwd=project_manager.current_project, check=False
            )
        elif (project_manager.current_project / "uvicorn").exists():
            subprocess.run(
                ["uvicorn", "main:app", "--reload"],
                cwd=project_manager.current_project,
                check=False,
            )
        else:
            console.print(
                "[yellow]Warning: No recognized run configuration found[/yellow]"
            )
            console.print("Try running: python main.py")

    except KeyboardInterrupt:
        console.print("\n[yellow]Development server stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]Run error: {e}[/red]")
        sys.exit(1)


@cli.command()
def info():
    """Show current project information."""
    project_manager = MartyProjectManager()

    if not project_manager.current_project:
        console.print("[red]Error: Not in a Marty project directory[/red]")
        return

    project_info = project_manager.get_project_info()

    console.print("\n[bold]Project Information:[/bold]")
    console.print(f"Path: {project_manager.current_project}")

    if project_info:
        console.print(f"Name: {project_info.get('name', 'Unknown')}")
        console.print(f"Version: {project_info.get('version', 'Unknown')}")
        console.print(f"Description: {project_info.get('description', 'None')}")
        console.print(f"Template: {project_info.get('template', 'Unknown')}")
    else:
        console.print("No Marty configuration found")


@cli.command()
@click.option("--author", help="Default author name")
@click.option("--email", help="Default author email")
@click.option("--license", help="Default license")
@click.option("--python-version", help="Default Python version")
def config(author, email, license, python_version):
    """Configure CLI defaults."""
    template_manager = MartyTemplateManager()

    if author:
        template_manager.config["author"] = author
    if email:
        template_manager.config["email"] = email
    if license:
        template_manager.config["default_license"] = license
    if python_version:
        template_manager.config["default_python_version"] = python_version

    template_manager.save_config()

    console.print("[green]✓ Configuration updated[/green]")

    # Show current config
    console.print("\n[bold]Current Configuration:[/bold]")
    config_data = template_manager.config
    console.print(f"Author: {config_data.get('author', 'Not set')}")
    console.print(f"Email: {config_data.get('email', 'Not set')}")
    console.print(f"Default License: {config_data.get('default_license', 'MIT')}")
    console.print(
        f"Default Python Version: {config_data.get('default_python_version', '3.11')}"
    )


if __name__ == "__main__":
    cli()
