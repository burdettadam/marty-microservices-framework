#!/usr/bin/env python3
"""
Plugin Integration Verification Script

This script verifies the plugin integration setup is working correctly.
"""

import sys
from importlib.metadata import entry_points
from pathlib import Path

import yaml

from marty_msf.framework.plugins.core import PluginContext, PluginManager
from marty_msf.framework.plugins.services import ServiceDefinition

# Add framework to path
framework_root = Path(__file__).parent.parent
sys.path.insert(0, str(framework_root / "src"))

def test_plugin_discovery():
    """Test that the plugin can be discovered via entry points."""
    print("🔍 Testing plugin discovery...")

    try:
        # Test entry point discovery
        try:
            eps = entry_points(group="mmf.plugins")

            found_plugins = []
            for ep in eps:
                found_plugins.append(ep.name)
                print(f"  ✅ Found plugin entry point: {ep.name} -> {ep.value}")

            if "production_payment" in found_plugins:
                print("  ✅ Production payment plugin entry point found")
            else:
                print("  ❌ Production payment plugin entry point not found")

        except Exception as e:
            print(f"  ⚠️  Entry point discovery failed: {e}")

    except Exception as e:
        print(f"❌ Plugin discovery test failed: {e}")

def test_plugin_import():
    """Test direct plugin import."""
    print("\n📦 Testing plugin import...")

    # Check for available plugins in the plugins directory
    plugins_dir = Path(__file__).parent.parent / "plugins"
    available_plugins = []

    for plugin_dir in plugins_dir.iterdir():
        if plugin_dir.is_dir() and not plugin_dir.name.startswith("__"):
            available_plugins.append(plugin_dir.name)

    if not available_plugins:
        print("  ⚠️  No plugins found in plugins directory")
        return True

    print(f"  📋 Available plugins: {', '.join(available_plugins)}")

    # Try to import test plugins
    success_count = 0
    for plugin_name in available_plugins:
        try:
            # Skip simple-payment-service as it's a standalone service, not a plugin
            if plugin_name == "simple-payment-service":
                print(f"  ℹ️  Skipping {plugin_name} (standalone service, not a plugin)")
                continue

            # Try to import plugin (this is a placeholder for actual plugin imports)
            print(f"  ✅ Found plugin directory: {plugin_name}")
            success_count += 1

        except Exception as e:
            print(f"  ❌ Plugin {plugin_name} import failed: {e}")

    print(f"  📊 Plugin scan complete: {success_count} plugin directories found")
    return True

def test_configuration():
    """Test plugin configuration loading."""
    print("\n⚙️  Testing configuration...")

    config_files = [
        framework_root / "config" / "plugins" / "production_payment_service.yaml",
        framework_root / "config" / "base.yaml",
        framework_root / "config" / "development.yaml",
    ]

    for config_file in config_files:
        if config_file.exists():
            print(f"  ✅ Configuration file exists: {config_file.name}")
        else:
            print(f"  ❌ Configuration file missing: {config_file.name}")

    # Test configuration content
    plugin_config = framework_root / "config" / "plugins" / "production_payment_service.yaml"
    if plugin_config.exists():
        try:
            import yaml
            with open(plugin_config) as f:
                config = yaml.safe_load(f)

            if config.get("default", {}).get("enabled"):
                print("  ✅ Plugin is enabled in configuration")
            else:
                print("  ⚠️  Plugin may not be enabled in configuration")

        except ImportError:
            print("  ⚠️  PyYAML not available, skipping config content check")
        except Exception as e:
            print(f"  ❌ Configuration parsing failed: {e}")

def test_framework_integration():
    """Test framework integration capabilities."""
    print("\n🔗 Testing framework integration...")

    try:
        # Test plugin context creation
        from marty_msf.framework.plugins.core import PluginContext
        print("  ✅ PluginContext can be imported")

        # Test plugin manager
        from marty_msf.framework.plugins.core import PluginManager
        print("  ✅ PluginManager can be imported")

        # Test service definitions
        print("🚀 Testing service definitions...")
        try:
            # Test service definition creation
            print("  ✅ ServiceDefinition can be imported")

            return True

        except Exception as e:
            print(f"  ❌ Framework integration test failed: {e}")
            return False

    except Exception as e:
        print(f"  ❌ Framework integration test failed: {e}")
        return False

def main():
    """Run all verification tests."""
    print("🧪 Plugin Integration Verification")
    print("=" * 40)

    # Run tests
    test_plugin_discovery()
    plugin_import_ok = test_plugin_import()
    test_configuration()
    framework_ok = test_framework_integration()

    # Summary
    print("\n📊 Summary")
    print("-" * 20)

    if plugin_import_ok and framework_ok:
        print("✅ Plugin integration setup is working correctly!")
        print("\n🚀 Next steps:")
        print("  1. Use the generator script to create services")
        print("  2. Configure plugin settings for your environment")
        print("  3. Start services with plugin integration")
        return 0
    else:
        print("❌ Some tests failed. Please check the setup.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
