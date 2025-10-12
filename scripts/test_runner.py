#!/usr/bin/env python3
"""
Test runner for Marty CLI with validation reports.
"""

import json
import subprocess
import sys
import time
from pathlib import Path


def run_tests():
    """Run the CLI test suite."""
    print("🧪 Running Marty CLI Test Suite...")
    print("=" * 50)

    # Set up test environment
    framework_path = Path(__file__).parent
    test_file = framework_path / "tests" / "test_cli.py"

    if not test_file.exists():
        print("❌ Test file not found!")
        return False

    # Run pytest with detailed output
    cmd = [
        "uv",
        "run",
        "pytest",
        str(test_file),
        "-v",
        "--tb=short",
        "--no-header",
        "--json-report",
        "--json-report-file=test_results.json",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=framework_path, check=False
        )

        print(f"Exit code: {result.returncode}")
        print("\nSTDOUT:")
        print(result.stdout)

        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)

        # Try to load test results
        results_file = framework_path / "test_results.json"
        if results_file.exists():
            try:
                with open(results_file, encoding="utf-8") as f:
                    results = json.load(f)

                print("\n📊 Test Summary:")
                print(f"  Total: {results.get('summary', {}).get('total', 0)}")
                print(f"  Passed: {results.get('summary', {}).get('passed', 0)}")
                print(f"  Failed: {results.get('summary', {}).get('failed', 0)}")
                print(f"  Skipped: {results.get('summary', {}).get('skipped', 0)}")

                if results.get("summary", {}).get("failed", 0) > 0:
                    print("\n❌ Failed Tests:")
                    for test in results.get("tests", []):
                        if test.get("outcome") == "failed":
                            print(f"  - {test.get('nodeid')}")
                            if test.get("call", {}).get("longrepr"):
                                print(f"    Error: {test['call']['longrepr']}")

            except (OSError, json.JSONDecodeError) as e:
                print(f"Could not parse test results: {e}")

        return result.returncode == 0

    except FileNotFoundError:
        print(
            "❌ uv or pytest not found. Please install with: uv add --dev pytest pytest-json-report"
        )
        return False
    except (subprocess.SubprocessError, OSError) as e:
        print(f"❌ Error running tests: {e}")
        return False


def validate_cli_installation():
    """Validate that the CLI can be installed and imported."""
    print("\n🔍 Validating CLI Installation...")
    print("-" * 30)

    try:
        # Test import
        from marty_cli import cli  # MartyTemplateManager, MartyProjectManager

        print("✅ CLI modules import successfully")

        # Test Click CLI
        from click.testing import CliRunner

        runner = CliRunner()

        result = runner.invoke(cli, ["--version"])
        if result.exit_code == 0:
            print("✅ CLI version command works")
            print(f"   Version output: {result.output.strip()}")
        else:
            print("❌ CLI version command failed")
            return False

        result = runner.invoke(cli, ["--help"])
        if result.exit_code == 0:
            print("✅ CLI help command works")
        else:
            print("❌ CLI help command failed")
            return False

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except (AttributeError, TypeError) as e:
        print(f"❌ Validation error: {e}")
        return False


def test_template_discovery():
    """Test template discovery functionality."""
    print("\n🔍 Testing Template Discovery...")
    print("-" * 30)

    try:
        framework_path = Path(__file__).parent
        templates_path = framework_path / "templates"

        if not templates_path.exists():
            print("❌ Templates directory not found")
            return False

        template_dirs = [d for d in templates_path.iterdir() if d.is_dir()]
        print(f"📁 Found {len(template_dirs)} template directories:")

        valid_templates = 0
        for template_dir in template_dirs:
            template_yaml = template_dir / "template.yaml"
            if template_yaml.exists():
                print(f"  ✅ {template_dir.name} (has template.yaml)")
                valid_templates += 1
            else:
                print(f"  ⚠️  {template_dir.name} (missing template.yaml)")

        print(f"\n📊 Valid templates: {valid_templates}/{len(template_dirs)}")
        return valid_templates > 0

    except OSError as e:
        print(f"❌ Template discovery error: {e}")
        return False


def main():
    """Main test runner."""
    print("🚀 Marty CLI Test & Validation Suite")
    print("=" * 50)

    start_time = time.time()

    # Run all validations
    validations = [
        ("CLI Installation", validate_cli_installation),
        ("Template Discovery", test_template_discovery),
        ("Unit Tests", run_tests),
    ]

    results = {}
    for name, func in validations:
        print(f"\n🔄 Running {name}...")
        results[name] = func()

    # Summary
    end_time = time.time()
    duration = end_time - start_time

    print("\n" + "=" * 50)
    print("📊 FINAL RESULTS")
    print("=" * 50)

    passed = sum(results.values())
    total = len(results)

    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {name}")

    print(f"\nOverall: {passed}/{total} validations passed")
    print(f"Duration: {duration:.2f} seconds")

    if passed == total:
        print("\n🎉 All validations passed! CLI is ready for use.")
        return 0
    print(f"\n⚠️  {total - passed} validation(s) failed. Please review and fix issues.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
