#!/usr/bin/env python3
"""
Quick test to verify the UV adoption for marty_chassis
"""

import sys
from pathlib import Path

# Add the marty_chassis directory to Python path
chassis_dir = Path(__file__).parent
sys.path.insert(0, str(chassis_dir))

try:
    from marty_chassis.templates import TemplateGenerator

    # Test in /tmp
    output_dir = Path("/tmp")
    service_name = "test-uv-service"

    # Remove if exists
    service_dir = output_dir / service_name
    if service_dir.exists():
        import shutil

        shutil.rmtree(service_dir)

    # Generate service
    gen = TemplateGenerator()
    gen.generate_service(
        service_name=service_name, service_type="fastapi", output_dir=output_dir
    )

    print(f"✅ Service generated at: {service_dir}")

    # Check files
    pyproject = service_dir / "pyproject.toml"
    dockerfile = service_dir / "Dockerfile"

    if pyproject.exists():
        content = pyproject.read_text()
        print("✅ pyproject.toml created")
        if "hatchling" in content:
            print("✅ Uses hatchling build system")
        if "marty-chassis[all]" in content:
            print("✅ Correct dependencies")

    if dockerfile.exists():
        content = dockerfile.read_text()
        print("✅ Dockerfile created")
        if "uv" in content:
            print("✅ Dockerfile uses UV")

    print(f"\n📁 Files created in {service_dir}:")
    for f in service_dir.rglob("*"):
        if f.is_file():
            print(f"  - {f.name}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
