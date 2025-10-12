#!/usr/bin/env python3
"""Script to fix unused import (F401) errors by removing them."""

import re
import subprocess


def get_f401_errors():
    """Get all F401 errors from ruff."""
    try:
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "--select", "F401", "."],
            capture_output=True,
            text=True,
            cwd="/Users/adamburdett/Github/work/Marty/marty-microservices-framework",
        )
        return result.stdout
    except Exception as e:
        print(f"Error running ruff: {e}")
        return ""


def parse_f401_errors(output):
    """Parse F401 errors to extract file paths and unused imports."""
    errors = []
    lines = output.split("\n")

    for line in lines:
        if "F401" in line and "imported but unused" in line:
            # Extract file path and import name
            if "-->" in line:
                parts = line.split("-->")
                if len(parts) >= 2:
                    file_path = parts[1].strip().split(":")[0]
                    # Extract import name from the error message
                    import_match = re.search(r"F401 `([^`]+)` imported but unused", line)
                    if import_match:
                        import_name = import_match.group(1)
                        errors.append((file_path, import_name))

    return errors


def remove_unused_import(file_path, import_name):
    """Remove unused import from file."""
    try:
        with open(file_path) as f:
            content = f.read()

        lines = content.split("\n")
        new_lines = []

        for line in lines:
            # Skip lines that import the unused import
            if f"import {import_name}" in line and line.strip().startswith(("import ", "from ")):
                # Check if it's a single import or multiple imports
                if "," in line:
                    # Multiple imports - remove just this one
                    import_parts = re.split(r",\s*", line)
                    filtered_parts = [part for part in import_parts if import_name not in part]
                    if len(filtered_parts) > 0:
                        new_lines.append(",".join(filtered_parts))
                else:
                    # Single import - skip the line entirely
                    continue
            else:
                new_lines.append(line)

        new_content = "\n".join(new_lines)

        # Only write if content changed
        if new_content != content:
            with open(file_path, "w") as f:
                f.write(new_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function to fix all F401 errors."""
    print("Getting F401 errors...")
    output = get_f401_errors()

    if not output:
        print("No F401 errors found or error running ruff.")
        return

    errors = parse_f401_errors(output)
    print(f"Found {len(errors)} F401 errors to fix...")

    fixed_files = set()
    for file_path, import_name in errors:
        if remove_unused_import(file_path, import_name):
            fixed_files.add(file_path)

    print(f"Fixed unused imports in {len(fixed_files)} files")

    # Run a final check
    print("Running final ruff check...")
    result = subprocess.run(
        ["uv", "run", "ruff", "check", "--select", "F401", "."],
        cwd="/Users/adamburdett/Github/work/Marty/marty-microservices-framework",
    )

    if result.returncode == 0:
        print("✅ All F401 errors fixed!")
    else:
        print("⚠️  Some F401 errors remain - may need manual intervention")


if __name__ == "__main__":
    main()
