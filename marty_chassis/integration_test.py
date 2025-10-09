#!/usr/bin/env python3
"""
Integration test to verify marty_chassis functionality.
Tests key components to ensure the package meets requirements.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

# Add marty_chassis to path
sys.path.insert(0, str(Path(__file__).parent))


def test_basic_imports():
    """Test that all key modules can be imported."""
    print("🧪 Testing basic imports...")

    try:
        # Core factories
        from marty_chassis.factories.fastapi_factory import create_fastapi_service
        from marty_chassis.factories.grpc_factory import create_grpc_service
        from marty_chassis.factories.hybrid_factory import create_hybrid_service

        print("✅ Factory functions imported successfully")

        # Configuration
        from marty_chassis.config import ChassisConfig

        print("✅ Configuration system imported successfully")

        # Security
        from marty_chassis.security import JWTAuth, RBACMiddleware

        print("✅ Security components imported successfully")

        # Health and metrics
        from marty_chassis.health import HealthCheck
        from marty_chassis.metrics import MetricsCollector

        print("✅ Health and metrics imported successfully")

        # Resilience
        from marty_chassis.resilience import CircuitBreaker

        print("✅ Resilience patterns imported successfully")

        # Clients
        from marty_chassis.clients import GRPCClient, HTTPClient

        print("✅ Client libraries imported successfully")

        # Templates and CLI
        from marty_chassis.service_mesh import ManifestGenerator
        from marty_chassis.templates import TemplateGenerator

        print("✅ Templates and service mesh imported successfully")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False


def test_template_generation():
    """Test service template generation."""
    print("\n🧪 Testing service template generation...")

    try:
        from marty_chassis.templates import TemplateGenerator

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            generator = TemplateGenerator()

            # Generate FastAPI service
            generator.generate_service(
                service_name="test-fastapi-svc",
                service_type="fastapi",
                output_dir=output_dir,
                template_data={"version": "1.0.0"},
            )

            service_dir = output_dir / "test-fastapi-svc"

            # Check required files
            required_files = ["main.py", "pyproject.toml", "Dockerfile", "config.yaml"]

            for file_name in required_files:
                file_path = service_dir / file_name
                if file_path.exists():
                    print(f"✅ {file_name} generated")
                else:
                    print(f"❌ {file_name} missing")
                    return False

            # Check pyproject.toml content
            pyproject_content = (service_dir / "pyproject.toml").read_text()
            if (
                "hatchling" in pyproject_content
                and "marty-chassis[all]" in pyproject_content
            ):
                print("✅ pyproject.toml has correct UV/hatchling setup")
            else:
                print("❌ pyproject.toml missing UV/hatchling configuration")
                return False

            # Check Dockerfile uses UV
            dockerfile_content = (service_dir / "Dockerfile").read_text()
            if "uv" in dockerfile_content:
                print("✅ Dockerfile uses UV")
            else:
                print("❌ Dockerfile does not use UV")
                return False

            return True

    except Exception as e:
        print(f"❌ Template generation error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_service_mesh_generation():
    """Test service mesh manifest generation."""
    print("\n🧪 Testing service mesh manifest generation...")

    try:
        from marty_chassis.config import ChassisConfig
        from marty_chassis.service_mesh import ServiceMeshGenerator

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)

            # Create config
            config = ChassisConfig()

            # Generate Istio manifests
            generator = ServiceMeshGenerator("test-service", config)
            istio_dir = output_dir / "istio"
            generator.generate_istio_manifests(istio_dir)

            # Check Istio files
            istio_files = [
                "deployment.yaml",
                "service.yaml",
                "virtualservice.yaml",
                "destinationrule.yaml",
            ]

            for file_name in istio_files:
                if (istio_dir / file_name).exists():
                    print(f"✅ Istio {file_name} generated")
                else:
                    print(f"❌ Istio {file_name} missing")

            # Generate Linkerd manifests
            linkerd_dir = output_dir / "linkerd"
            generator.generate_linkerd_manifests(linkerd_dir)

            # Check Linkerd files
            linkerd_files = ["deployment.yaml", "service.yaml", "serviceprofile.yaml"]

            for file_name in linkerd_files:
                if (linkerd_dir / file_name).exists():
                    print(f"✅ Linkerd {file_name} generated")
                else:
                    print(f"❌ Linkerd {file_name} missing")

            return True

    except Exception as e:
        print(f"❌ Service mesh generation error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_cli_functionality():
    """Test CLI argument parsing."""
    print("\n🧪 Testing CLI functionality...")

    try:
        from click.testing import CliRunner

        from marty_chassis.cli.main import cli

        runner = CliRunner()

        # Test help command
        result = runner.invoke(cli, ["--help"])
        if result.exit_code == 0 and "Marty Chassis" in result.output:
            print("✅ CLI help works")
        else:
            print(f"❌ CLI help failed: {result.output}")
            return False

        return True

    except Exception as e:
        print(f"❌ CLI test error: {e}")
        return False


def main():
    """Run all integration tests."""
    print("🚀 Marty Chassis Integration Tests")
    print("=" * 50)

    tests = [
        test_basic_imports,
        test_template_generation,
        test_service_mesh_generation,
        test_cli_functionality,
    ]

    results = []
    for test in tests:
        results.append(test())

    print("\n📊 Test Results:")
    print("=" * 30)

    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"✅ All {total} tests passed!")
        print("\n🎉 Marty Chassis package is fully functional!")
        return 0
    else:
        print(f"❌ {total - passed} out of {total} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
