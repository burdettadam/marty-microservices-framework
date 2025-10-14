"""
Enhanced MMF Store Demo - Configuration Management Example

This service demonstrates comprehensive configuration management patterns:
- Environment-based configuration (dev, prod, test)
- Service-specific configuration sections
- Configuration validation
- Environment variable expansion
- Multi-environment support

This incorporates functionality from config_example.py
"""

import logging
import os
from dataclasses import dataclass

# Mock framework imports (these would be real in production)
try:
    from marty_msf.framework.config import (
        DatabaseConfigSection,
        Environment,
        create_service_config,
    )
except ImportError:
    # Fallback implementations for demo purposes
    class Environment:
        DEVELOPMENT = "development"
        PRODUCTION = "production"
        TESTING = "testing"

    @dataclass
    class DatabaseConfigSection:
        host: str = "localhost"
        port: int = 5432
        name: str = "store_db"
        user: str = "store_user"
        password: str = "store_pass"

    def create_service_config(service_name: str, environment: str):
        return {
            "service_name": service_name,
            "environment": environment,
            "database": DatabaseConfigSection(),
            "api_timeout": 30.0,
            "max_connections": 100,
            "enable_tracing": True
        }

logger = logging.getLogger(__name__)

class StoreConfigManager:
    """Configuration manager for the store demo services"""

    def __init__(self, service_name: str, environment: str | None = None):
        self.service_name = service_name
        self.environment = environment or os.getenv("ENVIRONMENT", Environment.DEVELOPMENT)
        self.config = self._load_config()

    def _load_config(self):
        """Load configuration based on service and environment"""
        logger.info(f"Loading configuration for {self.service_name} in {self.environment}")

        config = create_service_config(self.service_name, self.environment)

        # Environment-specific overrides
        if self.environment == Environment.PRODUCTION:
            config["api_timeout"] = 60.0
            config["max_connections"] = 200
            config["database"].host = os.getenv("DB_HOST", "prod-db.example.com")
        elif self.environment == Environment.TESTING:
            config["api_timeout"] = 10.0
            config["max_connections"] = 10
            config["database"].host = os.getenv("DB_HOST", "test-db.example.com")

        return config

    def get_database_config(self) -> DatabaseConfigSection:
        """Get database configuration"""
        return self.config["database"]

    def get_api_timeout(self) -> float:
        """Get API timeout configuration"""
        return self.config["api_timeout"]

    def get_max_connections(self) -> int:
        """Get maximum connections configuration"""
        return self.config["max_connections"]

    def is_tracing_enabled(self) -> bool:
        """Check if distributed tracing is enabled"""
        return self.config.get("enable_tracing", False)

def demonstrate_store_configuration():
    """Demonstrate configuration management in store demo"""
    print("=== Store Demo Configuration Management ===\n")

    # Configuration for different services
    services = ["order-service", "payment-service", "inventory-service"]

    for service in services:
        print(f"🔧 Configuring {service}...")
        config_mgr = StoreConfigManager(service)

        print(f"   Environment: {config_mgr.environment}")
        print(f"   API Timeout: {config_mgr.get_api_timeout()}s")
        print(f"   Max Connections: {config_mgr.get_max_connections()}")
        print(f"   Tracing Enabled: {config_mgr.is_tracing_enabled()}")

        db_config = config_mgr.get_database_config()
        print(f"   Database: {db_config.host}:{db_config.port}/{db_config.name}")
        print()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demonstrate_store_configuration()
