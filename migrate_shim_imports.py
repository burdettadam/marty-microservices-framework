#!/usr/bin/env python3
"""
Back-Compat Shim Migration Tool

This script helps migrate import statements from back-compatibility shim files
to the new decomposed package structure. It can:

1. Detect files using shim imports
2. Automatically update import statements
3. Verify the updates work correctly
4. Generate migration reports

Usage:
    python migrate_shim_imports.py --scan          # Scan for shim usage
    python migrate_shim_imports.py --migrate       # Migrate imports
    python migrate_shim_imports.py --verify        # Verify migrations
"""

import argparse
import ast
import re
from pathlib import Path

# Shim migration mappings
SHIM_MIGRATIONS = {
    # external_connectors.py shim
    "src.framework.integration.external_connectors": {
        "target": "src.framework.integration.external_connectors",
        "description": "External connectors decomposed package",
        "exports": [
            "ConnectorType",
            "DatabaseConnector",
            "DataFormat",
            "DataTransformation",
            "DataTransformationEngine",
            "ExternalSystemConfig",
            "ExternalSystemConnector",
            "ExternalSystemManager",
            "FileSystemConnector",
            "IntegrationPattern",
            "IntegrationRequest",
            "IntegrationResponse",
            "RESTAPIConnector",
            "TransformationType",
            "create_external_integration_platform",
        ],
    },
    # strategies.py shim
    "src.framework.deployment.strategies": {
        "target": "src.framework.deployment.strategies",
        "description": "Deployment strategies decomposed package",
        "exports": [
            "Deployment",
            "DeploymentEvent",
            "DeploymentOrchestrator",
            "DeploymentPhase",
            "DeploymentStatus",
            "DeploymentStrategy",
            "DeploymentTarget",
            "DeploymentValidation",
            "EnvironmentType",
            "FeatureFlag",
            "FeatureFlagManager",
            "FeatureFlagType",
            "InfrastructureManager",
            "RollbackConfiguration",
            "RollbackManager",
            "ServiceVersion",
            "TrafficManager",
            "TrafficSplit",
            "ValidationManager",
            "ValidationResult",
            "ValidationRunResult",
            "create_deployment_orchestrator",
        ],
    },
}


class ShimMigrationTool:
    """Tool for migrating shim imports to decomposed packages."""

    def __init__(self, root_path: Path):
        self.root_path = Path(root_path)
        self.scan_results: dict[str, list[dict]] = {}

    def scan_for_shim_usage(self) -> dict[str, list[dict]]:
        """Scan for files using shim imports."""
        results = {}

        for shim_module, _config in SHIM_MIGRATIONS.items():
            results[shim_module] = []

            # Find Python files that import from the shim
            for py_file in self.root_path.rglob("*.py"):
                try:
                    with open(py_file, encoding="utf-8") as f:
                        content = f.read()

                    imports = self._find_shim_imports(content, shim_module)
                    if imports:
                        results[shim_module].append({"file": str(py_file), "imports": imports})

                except Exception as e:
                    print(f"Warning: Could not scan {py_file}: {e}")

        self.scan_results = results
        return results

    def _find_shim_imports(self, content: str, shim_module: str) -> list[dict]:
        """Find import statements for a specific shim module."""
        imports = []

        # Pattern for "from X import Y" statements
        from_pattern = rf"from\s+{re.escape(shim_module)}\s+import\s+(.+)"

        # Pattern for "import X" statements
        import_pattern = rf"import\s+{re.escape(shim_module)}(?:\s+as\s+\w+)?"

        for line_num, line in enumerate(content.split("\n"), 1):
            line = line.strip()

            # Check for "from ... import ..." pattern
            from_match = re.search(from_pattern, line)
            if from_match:
                imported_items = from_match.group(1)
                imports.append(
                    {
                        "line": line_num,
                        "type": "from_import",
                        "original": line,
                        "imported_items": imported_items,
                    }
                )

            # Check for "import ..." pattern
            import_match = re.search(import_pattern, line)
            if import_match:
                imports.append({"line": line_num, "type": "import", "original": line})

        return imports

    def migrate_file(self, file_path: Path, dry_run: bool = True) -> tuple[bool, str]:
        """Migrate shim imports in a single file."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            changes_made = False

            for shim_module, config in SHIM_MIGRATIONS.items():
                target_module = config["target"]

                # Replace "from shim import X" with "from package import X"
                from_pattern = rf"from\s+{re.escape(shim_module)}\s+import"
                from_replacement = f"from {target_module} import"

                new_content = re.sub(from_pattern, from_replacement, content)
                if new_content != content:
                    content = new_content
                    changes_made = True

                # Replace "import shim" with "import package"
                import_pattern = rf"import\s+{re.escape(shim_module)}(?=\s|$)"
                import_replacement = f"import {target_module}"

                new_content = re.sub(import_pattern, import_replacement, content)
                if new_content != content:
                    content = new_content
                    changes_made = True

            if changes_made and not dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)

            return changes_made, content if changes_made else ""

        except Exception as e:
            return False, f"Error processing {file_path}: {e}"

    def migrate_all(self, dry_run: bool = True) -> dict[str, any]:
        """Migrate all files with shim imports."""
        if not self.scan_results:
            self.scan_for_shim_usage()

        results = {"files_processed": 0, "files_changed": 0, "errors": [], "changes": []}

        for shim_module, file_list in self.scan_results.items():
            for file_info in file_list:
                file_path = Path(file_info["file"])
                results["files_processed"] += 1

                changed, content_or_error = self.migrate_file(file_path, dry_run)

                if changed:
                    results["files_changed"] += 1
                    results["changes"].append(
                        {
                            "file": str(file_path),
                            "shim": shim_module,
                            "target": SHIM_MIGRATIONS[shim_module]["target"],
                        }
                    )
                elif "Error" in content_or_error:
                    results["errors"].append(content_or_error)

        return results

    def verify_migrations(self) -> dict[str, any]:
        """Verify that migrated files can still be imported/parsed."""
        results = {"files_checked": 0, "syntax_errors": [], "import_errors": []}

        if not self.scan_results:
            self.scan_for_shim_usage()

        for _shim_module, file_list in self.scan_results.items():
            for file_info in file_list:
                file_path = Path(file_info["file"])
                results["files_checked"] += 1

                # Check syntax
                try:
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()
                    ast.parse(content)
                except SyntaxError as e:
                    results["syntax_errors"].append({"file": str(file_path), "error": str(e)})

        return results

    def generate_report(self) -> str:
        """Generate a migration report."""
        if not self.scan_results:
            self.scan_for_shim_usage()

        report = ["# Shim Import Migration Report", ""]

        total_files = sum(len(files) for files in self.scan_results.values())
        report.append(f"**Total files using shims**: {total_files}")
        report.append("")

        for shim_module, file_list in self.scan_results.items():
            if not file_list:
                continue

            config = SHIM_MIGRATIONS[shim_module]
            report.append(f"## {shim_module}")
            report.append(f"**Target**: `{config['target']}`")
            report.append(f"**Description**: {config['description']}")
            report.append(f"**Files affected**: {len(file_list)}")
            report.append("")

            for file_info in file_list:
                report.append(f"- `{file_info['file']}`")
                for import_info in file_info["imports"]:
                    report.append(f"  - Line {import_info['line']}: `{import_info['original']}`")

            report.append("")

        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Migrate shim imports to decomposed packages")
    parser.add_argument(
        "--root", default=".", help="Root directory to scan (default: current directory)"
    )
    parser.add_argument("--scan", action="store_true", help="Scan for shim usage")
    parser.add_argument(
        "--migrate", action="store_true", help="Migrate imports (dry run by default)"
    )
    parser.add_argument("--verify", action="store_true", help="Verify migrated files")
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (not dry run)")
    parser.add_argument("--report", action="store_true", help="Generate migration report")

    args = parser.parse_args()

    tool = ShimMigrationTool(Path(args.root))

    if args.scan or not any([args.migrate, args.verify, args.report]):
        print("🔍 Scanning for shim usage...")
        results = tool.scan_for_shim_usage()

        total_files = sum(len(files) for files in results.values())
        print(f"Found {total_files} files using shim imports:")

        for shim, file_list in results.items():
            if file_list:
                print(f"\n📁 {shim}: {len(file_list)} files")
                for file_info in file_list[:5]:  # Show first 5 files
                    print(f"  - {file_info['file']}")
                if len(file_list) > 5:
                    print(f"  ... and {len(file_list) - 5} more")

    if args.migrate:
        print(f"\n🔄 {'Migrating' if args.apply else 'Simulating migration of'} shim imports...")
        results = tool.migrate_all(dry_run=not args.apply)

        print(f"Processed: {results['files_processed']} files")
        print(f"Changed: {results['files_changed']} files")

        if results["errors"]:
            print(f"Errors: {len(results['errors'])}")
            for error in results["errors"][:3]:
                print(f"  - {error}")

        if not args.apply:
            print("\n⚠️  This was a dry run. Use --apply to actually make changes.")

    if args.verify:
        print("\n✅ Verifying migrated files...")
        results = tool.verify_migrations()

        print(f"Checked: {results['files_checked']} files")
        if results["syntax_errors"]:
            print(f"Syntax errors: {len(results['syntax_errors'])}")
            for error in results["syntax_errors"]:
                print(f"  - {error['file']}: {error['error']}")
        else:
            print("No syntax errors found!")

    if args.report:
        print("\n📋 Generating migration report...")
        report = tool.generate_report()

        report_file = Path("shim_migration_report.md")
        with open(report_file, "w") as f:
            f.write(report)
        print(f"Report saved to: {report_file}")


if __name__ == "__main__":
    main()
