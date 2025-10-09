#!/usr/bin/env python3
"""
Debug CLI creation issue.
"""

import logging
import tempfile
from pathlib import Path

# Set up debug logging
from typing import Set

logging.basicConfig(level=logging.DEBUG)

from marty_cli import MartyTemplateManager, ProjectConfig


def test_project_creation():
    """Test project creation with debug output."""
    print("🔍 Testing project creation...")

    try:
        # Create temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            print(f"📁 Temp directory: {temp_path}")

            # Initialize template manager
            template_manager = MartyTemplateManager()
            print(f"📋 Framework path: {template_manager.framework_path}")

            # Check available templates
            templates = template_manager.get_available_templates()
            print(f"📋 Available templates: {list(templates.keys())}")

            if "fastapi-service" not in templates:
                print("❌ fastapi-service template not found!")
                return False

            # Create project config
            config = ProjectConfig(
                name="Debug Test Service",
                template="fastapi-service",
                path=str(temp_path / "debug-test-service"),
                author="Debug User",
                email="debug@test.com",
                description="Debug test service",
                skip_prompts=True,
            )

            print(f"⚙️ Project config: {config}")

            # Try to create project
            success = template_manager.create_project(config)
            print(f"✅ Project creation: {'SUCCESS' if success else 'FAILED'}")

            if success:
                project_path = Path(config.path)
                print(
                    f"📁 Project files: {list(project_path.rglob('*'))[:10]}"
                )  # First 10 files

            return success

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_project_creation()
