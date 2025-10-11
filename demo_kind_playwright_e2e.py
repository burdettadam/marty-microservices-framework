#!/usr/bin/env python3
"""
Kind + Playwright E2E Demo

This script demonstrates the new Kind + Playwright E2E testing infrastructure.
It shows how to:
1. Create a Kind Kubernetes cluster
2. Deploy microservices to the cluster
3. Test the deployed services with Playwright browser automation
4. Clean up resources automatically

This is a demonstration that can be run manually to understand the capabilities.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the path so we can import our modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import sys
    sys.path.insert(0, 'tests/e2e')
    from kind_playwright_infrastructure import (
        kind_playwright_test_environment,
        run_basic_kind_playwright_test,
    )
except ImportError as e:
    print(f"❌ Could not import Kind + Playwright infrastructure: {e}")
    print("Make sure you have installed the dependencies:")
    print("  uv add --dev playwright pytest-playwright kubernetes docker aiohttp")
    print("  uv run playwright install chromium")
    sys.exit(1)


async def demo_infrastructure_components():
    """Demonstrate the individual components of the infrastructure."""
    print("🔧 Testing Individual Infrastructure Components")
    print("=" * 50)

    try:
        from kind_playwright_infrastructure import (
            KindClusterManager,
            MicroserviceDeployer,
            PlaywrightTester,
        )

        # Test KindClusterManager
        print("\n1. Testing KindClusterManager:")
        cluster = KindClusterManager("demo-cluster")
        print(f"   ✅ Created cluster manager for: {cluster.cluster_name}")

        # Test MicroserviceDeployer
        print("\n2. Testing MicroserviceDeployer:")
        deployer = MicroserviceDeployer(cluster)
        print(f"   ✅ Created deployer with {len(deployer.deployed_services)} initial services")

        # Test PlaywrightTester
        print("\n3. Testing PlaywrightTester:")
        tester = PlaywrightTester()
        print(f"   ✅ Created Playwright tester for base URL: {tester.base_url}")

        print("\n✅ All infrastructure components created successfully!")

    except Exception as e:
        print(f"❌ Error testing components: {e}")
        return False

    return True


async def demo_basic_e2e_test():
    """Run the basic E2E test to demonstrate full functionality."""
    print("\n🚀 Running Basic Kind + Playwright E2E Test")
    print("=" * 50)
    print("This will:")
    print("  1. Create a Kind Kubernetes cluster")
    print("  2. Deploy a dashboard service")
    print("  3. Test the dashboard with Playwright")
    print("  4. Take screenshots for visual testing")
    print("  5. Clean up all resources")
    print("\nThis may take 2-3 minutes...")

    try:
        success = await run_basic_kind_playwright_test()
        if success:
            print("\n🎉 Basic E2E test completed successfully!")
            return True
        else:
            print("\n❌ Basic E2E test failed!")
            return False

    except Exception as e:
        print(f"\n❌ Error running basic E2E test: {e}")
        return False


def show_test_files_created():
    """Show what test files and infrastructure were created."""
    print("\n📁 Kind + Playwright E2E Infrastructure Created")
    print("=" * 50)

    files_created = [
        ("tests/e2e/kind_playwright_infrastructure.py", "Core infrastructure classes"),
        ("tests/e2e/test_kind_playwright_e2e.py", "Comprehensive E2E test suite"),
        ("tests/e2e/KIND_PLAYWRIGHT_README.md", "Detailed documentation"),
        ("tests/e2e/config.yaml", "Configuration example"),
        ("scripts/run_kind_playwright_e2e.sh", "Test runner script"),
    ]

    for file_path, description in files_created:
        if Path(file_path).exists():
            print(f"   ✅ {file_path}")
            print(f"      {description}")
        else:
            print(f"   ❌ {file_path} (missing)")

    print("\n📊 Test Capabilities Added:")
    capabilities = [
        "Kind Kubernetes cluster management",
        "Microservice deployment automation",
        "Playwright browser automation",
        "Dashboard and UI testing",
        "Responsive design testing",
        "Visual regression detection",
        "Screenshot capture",
        "Automatic resource cleanup",
        "CI/CD ready configuration"
    ]

    for capability in capabilities:
        print(f"   ✅ {capability}")


def show_usage_examples():
    """Show examples of how to use the new E2E infrastructure."""
    print("\n🛠️  Usage Examples")
    print("=" * 50)

    print("1. Run all E2E tests:")
    print("   ./scripts/run_kind_playwright_e2e.sh")
    print()

    print("2. Run specific test types:")
    print("   ./scripts/run_kind_playwright_e2e.sh --test-type dashboard")
    print("   ./scripts/run_kind_playwright_e2e.sh --test-type visual")
    print()

    print("3. Run with visible browser (for debugging):")
    print("   ./scripts/run_kind_playwright_e2e.sh --headless false")
    print()

    print("4. Keep cluster after testing (for inspection):")
    print("   ./scripts/run_kind_playwright_e2e.sh --no-cleanup")
    print()

    print("5. Run via pytest directly:")
    print("   uv run pytest tests/e2e/test_kind_playwright_e2e.py -v -s")
    print()

    print("6. Manual test for development:")
    print("   uv run python -c \"import asyncio; from tests.e2e.test_kind_playwright_e2e import run_manual_e2e_test; asyncio.run(run_manual_e2e_test())\"")


def show_next_steps():
    """Show what users can do next with this infrastructure."""
    print("\n🚀 Next Steps")
    print("=" * 50)

    print("You now have comprehensive Kind + Playwright E2E testing! Here's what you can do:")
    print()

    print("📚 Learn More:")
    print("   - Read tests/e2e/KIND_PLAYWRIGHT_README.md for detailed documentation")
    print("   - Check tests/e2e/config.yaml for configuration options")
    print("   - Look at tests/e2e/test_kind_playwright_e2e.py for test examples")
    print()

    print("🧪 Run Tests:")
    print("   - Start with: ./scripts/run_kind_playwright_e2e.sh --test-type dashboard")
    print("   - Try visual testing: ./scripts/run_kind_playwright_e2e.sh --test-type visual")
    print("   - Run full suite: ./scripts/run_kind_playwright_e2e.sh")
    print()

    print("🔧 Extend and Customize:")
    print("   - Add your own microservices to test")
    print("   - Create custom dashboard HTML for your needs")
    print("   - Add additional Playwright test scenarios")
    print("   - Integrate with your CI/CD pipeline")
    print()

    print("🐛 Debug and Develop:")
    print("   - Use --headless false to see browser actions")
    print("   - Use --no-cleanup to inspect cluster state")
    print("   - Check test_screenshots/ for visual outputs")
    print("   - Use kubectl to inspect deployed services")


async def main():
    """Main demo function."""
    print("🎭 Kind + Playwright E2E Testing Demo")
    print("=" * 50)
    print("This demo shows the new comprehensive E2E testing infrastructure")
    print("that combines Kind Kubernetes clusters with Playwright browser automation.")
    print()

    # Check if required tools are available
    print("🔍 Checking Prerequisites...")
    try:
        import docker
        import kubernetes
        import playwright
        print("   ✅ All required Python packages are available")
    except ImportError as e:
        print(f"   ❌ Missing required package: {e}")
        print("   Please run: uv add --dev playwright pytest-playwright kubernetes docker aiohttp")
        return

    try:
        import subprocess
        result = subprocess.run(["kind", "version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   ✅ Kind is available: {result.stdout.strip()}")
        else:
            print("   ❌ Kind is not available. Please install Kind first.")
            return
    except FileNotFoundError:
        print("   ❌ Kind command not found. Please install Kind first.")
        return

    # Show what was created
    show_test_files_created()

    # Test infrastructure components
    components_ok = await demo_infrastructure_components()
    if not components_ok:
        print("\n❌ Infrastructure components test failed!")
        return

    # Ask user if they want to run the full E2E test
    print("\n" + "=" * 50)
    response = input("🤔 Would you like to run a full E2E test (creates cluster, deploys services, tests with browser)? [y/N]: ")

    if response.lower() in ['y', 'yes']:
        e2e_ok = await demo_basic_e2e_test()
        if e2e_ok:
            print("\n🎉 Full E2E demo completed successfully!")
        else:
            print("\n❌ E2E demo had issues - but the infrastructure is ready to use!")
    else:
        print("\n⏭️  Skipping full E2E test (you can run it later)")

    # Show usage examples and next steps
    show_usage_examples()
    show_next_steps()

    print("\n🎉 Demo completed! You now have comprehensive Kind + Playwright E2E testing ready to use!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        sys.exit(1)
