#!/usr/bin/env python3
"""
Code Quality Checker for Marty Microservices Framework

Checks for:
- Cyclomatic complexity using radon
- File length limits
- Function length limits
- Provides actionable feedback for improvements
"""

import ast
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except (OSError, ValueError) as e:
        return 1, "", str(e)


def check_cyclomatic_complexity(src_dir: str = "src/framework/") -> bool:
    """Check cyclomatic complexity using radon."""
    print("🔍 Checking cyclomatic complexity with radon...")

    # Try to install radon if not available
    exit_code, _, _ = run_command(["radon", "--version"])
    if exit_code != 0:
        print("Installing radon...")
        install_code, _, install_err = run_command(["uv", "add", "--dev", "radon"])
        if install_code != 0:
            print(f"❌ Failed to install radon: {install_err}")
            return False

    # Check for functions with complexity > 10 (grade C and above)
    cmd = ["uv", "run", "radon", "cc", "--min=C", src_dir, "--show-complexity", "--no-assert"]
    exit_code, stdout, _ = run_command(cmd)

    if stdout.strip():
        print("❌ Found functions with high complexity (>10):")
        print(stdout)
        print()
        print("💡 Consider refactoring these functions to reduce complexity:")
        print("   - Break down into smaller functions")
        print("   - Use early returns to reduce nesting")
        print("   - Extract complex conditions into variables")
        print("   - Consider using strategy pattern for complex conditionals")
        return False

    print("✅ Cyclomatic complexity check passed")
    return True


def check_file_lengths(src_dir: str = "src/framework/", max_lines: int = 500) -> bool:
    """Check for files that are too long."""
    print(f"🔍 Checking file lengths (max {max_lines} lines)...")

    long_files = []
    src_path = Path(src_dir)

    if not src_path.exists():
        print(f"⚠️  Source directory {src_dir} not found")
        return True

    for py_file in src_path.rglob("*.py"):
        # Skip certain directories
        if any(part in str(py_file) for part in ["__pycache__", "templates", "examples", "tests"]):
            continue

        try:
            with open(py_file, encoding="utf-8") as f:
                line_count = sum(1 for _ in f)

            if line_count > max_lines:
                long_files.append(f"{py_file} has {line_count} lines")
        except (OSError, UnicodeDecodeError):
            continue

    if long_files:
        print(f"⚠️  Found long files (>{max_lines} lines):")
        for file_info in long_files:
            print(f"   {file_info}")
        print()
        print("💡 Consider breaking these files into smaller modules:")
        print("   - Extract related classes/functions into separate modules")
        print("   - Use composition over inheritance")
        print("   - Create utility modules for common functionality")
        # Don't fail on long files, just warn
    else:
        print("✅ File length check passed")

    return True


def check_function_lengths(src_dir: str = "src/framework/", max_lines: int = 50) -> bool:
    """Check for functions that are too long."""
    print(f"🔍 Checking function lengths (max {max_lines} lines)...")

    long_functions = []
    src_path = Path(src_dir)

    if not src_path.exists():
        print(f"⚠️  Source directory {src_dir} not found")
        return True

    for py_file in src_path.rglob("*.py"):
        # Skip certain directories
        if any(part in str(py_file) for part in ["__pycache__", "templates", "examples", "tests"]):
            continue

        try:
            with open(py_file, encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content, filename=str(py_file))

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    if hasattr(node, "end_lineno") and node.end_lineno:
                        length = node.end_lineno - node.lineno + 1
                        if length > max_lines:
                            long_functions.append(
                                f"{py_file}:{node.lineno} - {node.name}() has {length} lines"
                            )
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue

    if long_functions:
        print(f"⚠️  Found long functions (>{max_lines} lines):")
        for func_info in long_functions:
            print(f"   {func_info}")
        print()
        print("💡 Consider breaking these functions into smaller ones:")
        print("   - Extract helper functions")
        print("   - Use early returns to reduce nesting")
        print("   - Consider the single responsibility principle")
        # Don't fail on long functions, just warn
    else:
        print("✅ Function length check passed")

    return True


def main():
    """Main function to run all code quality checks."""
    print("🚀 Running code quality checks...")

    all_passed = True

    # Run all checks
    if not check_cyclomatic_complexity():
        all_passed = False

    if not check_file_lengths():
        all_passed = False

    if not check_function_lengths():
        all_passed = False

    if all_passed:
        print("\n✅ All code quality checks passed!")
        return 0
    else:
        print("\n❌ Some code quality checks failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
