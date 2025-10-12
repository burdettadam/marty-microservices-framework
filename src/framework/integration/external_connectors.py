"""
External System Connectors - Compatibility Layer

DEPRECATED: This is a compatibility shim that imports from the decomposed package.
Please import directly from 'framework.integration.external_connectors' package instead.

New import path: from framework.integration.external_connectors import ConnectorType, ...

All components have been migrated to the decomposed package structure.
"""

import warnings

# Import all components from decomposed package for backward compatibility
from framework.integration.external_connectors import (
    ConnectorType,
    DatabaseConnector,
    DataFormat,
    DataTransformation,
    DataTransformationEngine,
    ExternalSystemConfig,
    ExternalSystemConnector,
    ExternalSystemManager,
    FileSystemConnector,
    IntegrationPattern,
    IntegrationRequest,
    IntegrationResponse,
    RESTAPIConnector,
    TransformationType,
    create_external_integration_platform,
)

# Issue deprecation warning
warnings.warn(
    "Importing from framework.integration.external_connectors.py is deprecated. "
    "Please import directly from 'framework.integration.external_connectors' package.",
    DeprecationWarning,
    stacklevel=2
)

# Export all symbols for backward compatibility
__all__ = [
    # From decomposed package
    "ConnectorType",
    "DataFormat",
    "IntegrationPattern",
    "TransformationType",
    "ExternalSystemConfig",
    "IntegrationRequest",
    "IntegrationResponse",
    "DataTransformation",
    "ExternalSystemConnector",
    "DataTransformationEngine",
    "RESTAPIConnector",
    "DatabaseConnector",
    "FileSystemConnector",
    "ExternalSystemManager",
    "create_external_integration_platform",
]
