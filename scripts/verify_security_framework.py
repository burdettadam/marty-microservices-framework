#!/usr/bin/env python3
"""
Security Framework Verification Script

This script verifies the security framework structure and components
without requiring external dependencies to be installed.
"""

import os
import sys
from pathlib import Path  # noqa: F401


def check_file_exists(filepath: str, description: str) -> bool:
    """Check if a file exists and report status."""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description}: {filepath} - NOT FOUND")
        return False


def check_directory_structure() -> bool:
    """Verify the security framework directory structure."""
    print("🔍 Checking Security Framework Structure...")
    print("=" * 50)

    # Check main directories
    directories = [
        ("security", "Main security directory"),
        ("security/middleware", "Security middleware directory"),
        ("security/policies", "Security policies directory"),
        ("security/tools", "Security tools directory"),
        ("security/scanners", "Security scanners directory"),
    ]

    all_dirs_exist = True
    for dir_path, description in directories:
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            print(f"✅ {description}: {dir_path}")
        else:
            print(f"❌ {description}: {dir_path} - NOT FOUND")
            all_dirs_exist = False

    return all_dirs_exist


def check_security_files() -> bool:
    """Verify all security framework files exist."""
    print("\n🔍 Checking Security Framework Files...")
    print("=" * 50)

    files_to_check = [
        # Core module files
        ("security/__init__.py", "Security module initialization"),
        ("security/README.md", "Security framework documentation"),
        ("security/requirements.txt", "Security dependencies"),
        # Middleware files
        ("security/middleware/__init__.py", "Middleware module initialization"),
        ("security/middleware/auth_middleware.py", "Authentication middleware"),
        ("security/middleware/rate_limiting.py", "Rate limiting middleware"),
        ("security/middleware/security_headers.py", "Security headers middleware"),
        # Policy files
        ("security/policies/rbac_policies.yaml", "RBAC policies"),
        (
            "security/policies/kubernetes_security_policies.yaml",
            "Kubernetes security policies",
        ),
        # Tool files
        ("security/tools/security_audit.py", "Security audit tool"),
        # Scanner files
        ("security/scanners/security_scan.sh", "Security scanner script"),
    ]

    all_files_exist = True
    for file_path, description in files_to_check:
        if not check_file_exists(file_path, description):
            all_files_exist = False

    return all_files_exist


def check_executable_permissions() -> bool:
    """Check that shell scripts have executable permissions."""
    print("\n🔍 Checking Executable Permissions...")
    print("=" * 50)

    scripts = ["security/scanners/security_scan.sh"]

    all_executable = True
    for script in scripts:
        if os.path.exists(script):
            if os.access(script, os.X_OK):
                print(f"✅ Executable: {script}")
            else:
                print(f"⚠️ Not executable: {script}")
                all_executable = False
        else:
            print(f"❌ Script not found: {script}")
            all_executable = False

    return all_executable


def count_total_files() -> int:
    """Count total files in security framework."""
    print("\n📊 Security Framework Statistics...")
    print("=" * 50)

    if not os.path.exists("security"):
        print("❌ Security directory not found")
        return 0

    total_files = 0
    file_types = {".py": 0, ".yaml": 0, ".yml": 0, ".sh": 0, ".md": 0, ".txt": 0}

    for _root, _dirs, files in os.walk("security"):
        for file in files:
            total_files += 1
            ext = os.path.splitext(file)[1].lower()
            if ext in file_types:
                file_types[ext] += 1
            else:
                if "other" not in file_types:
                    file_types["other"] = 0
                file_types["other"] += 1

    print(f"📁 Total files: {total_files}")
    for ext, count in file_types.items():
        if count > 0:
            print(f"   {ext} files: {count}")

    return total_files


def verify_framework_integration() -> bool:
    """Verify framework integration files are updated."""
    print("\n🔍 Checking Framework Integration...")
    print("=" * 50)

    integration_files = [
        ("README.md", "Main framework README"),
        ("IMPLEMENTATION_STRATEGY.md", "Implementation strategy document"),
        ("PHASE_1_SECURITY_SUMMARY.md", "Phase 1 completion summary"),
    ]

    all_integrated = True
    for file_path, description in integration_files:
        if not check_file_exists(file_path, description):
            all_integrated = False

    return all_integrated


def main() -> int:
    """Main verification function."""
    print("🛡️ Marty Microservices Framework - Security Framework Verification")
    print("=" * 70)
    print()

    # Change to framework directory if needed
    if os.path.basename(os.getcwd()) != "marty-microservices-framework":
        if os.path.exists("marty-microservices-framework"):
            os.chdir("marty-microservices-framework")

    # Run all checks
    checks = [
        ("Directory Structure", check_directory_structure),
        ("Security Files", check_security_files),
        ("Executable Permissions", check_executable_permissions),
        ("Framework Integration", verify_framework_integration),
    ]

    all_passed = True
    results = {}

    for check_name, check_func in checks:
        try:
            result = check_func()
            results[check_name] = result
            if not result:
                all_passed = False
        except Exception as e:  # noqa: BLE001
            print(f"❌ Error during {check_name}: {e}")
            results[check_name] = False
            all_passed = False

    # Count files
    total_files = count_total_files()

    # Final summary
    print("\n🏆 Verification Summary")
    print("=" * 50)

    for check_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{check_name}: {status}")

    print(f"\nTotal Security Framework Files: {total_files}")

    if all_passed:
        print("\n🎉 Security Framework Verification: ✅ ALL CHECKS PASSED")
        print("\n💡 To install dependencies and test imports:")
        print("   pip install -r security/requirements.txt")
        print(
            "   python -c 'from security import AuthenticationMiddleware; print(\"✅ Import successful\")'"
        )
        return 0
    else:
        print("\n⚠️ Security Framework Verification: ❌ SOME CHECKS FAILED")
        print("Please review the failed checks above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
