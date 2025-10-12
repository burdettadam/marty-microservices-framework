#!/usr/bin/env python3
"""
Test script for external connectors package imports
"""

import os
import sys

# Add the project root to the Python path
project_root = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')
sys.path.insert(0, project_root)

try:
    # Test direct module imports
    from src.framework.integration.external_connectors.base import (
        ExternalSystemConnector,
    )
    from src.framework.integration.external_connectors.config import (
        ExternalSystemConfig,
    )
    from src.framework.integration.external_connectors.enums import ConnectorType

    print("✅ All relative imports working correctly!")
    print(f"✅ ConnectorType: {ConnectorType.REST_API}")
    print(f"✅ Available connector types: {list(ConnectorType)}")
    print("✅ ExternalSystemConfig available")
    print("✅ ExternalSystemConnector base class available")

except ImportError as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
