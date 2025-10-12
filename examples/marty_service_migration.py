"""
Example of migrating a Marty service to use the unified MMF configuration system.

This demonstrates how to update a Marty service to use the consolidated
configuration while maintaining backward compatibility.
"""

import sys
from pathlib import Path

# Add framework to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from framework.marty_config_adapter import create_unified_config
except ImportError:
    # Fallback imports for development
    sys.path.append(str(Path(__file__).parent.parent / "src"))
    print("Using fallback imports")


class UnifiedMartyService:
    """
    Example service showing how to use the unified configuration system.

    This service can work with both legacy Marty config files and new MMF config.
    """

    def __init__(self, service_name: str, environment: str = "development"):
        self.service_name = service_name
        self.environment = environment

        # Use unified config that works with both systems
        self.config = self._load_unified_config()

    def _load_unified_config(self):
        """Load configuration using the unified system."""
        try:
            # Try the unified config adapter first
            return create_unified_config(
                service_name=self.service_name,
                environment=self.environment,
                config_path=Path("config"),
            )
        except Exception as e:
            print(f"Failed to load unified config: {e}")
            # Fallback to basic MMF config
            try:
                from framework.config import Environment as MMFEnvironment
                from framework.config import ServiceConfig

                return ServiceConfig(
                    service_name=self.service_name,
                    environment=MMFEnvironment(self.environment),
                    config_path=Path("config"),
                )
            except Exception as e2:
                print(f"Failed to load MMF config: {e2}")
                return None

    def get_database_config(self):
        """Get database configuration."""
        if self.config:
            try:
                return self.config.database
            except Exception as e:
                print(f"Error getting database config: {e}")
        return None

    def get_security_config(self):
        """Get security configuration."""
        if self.config:
            try:
                return self.config.security
            except Exception as e:
                print(f"Error getting security config: {e}")
        return None

    def get_cryptographic_config(self):
        """Get cryptographic configuration (Marty-specific)."""
        if self.config:
            try:
                return self.config.cryptographic
            except Exception as e:
                print(f"Error getting cryptographic config: {e}")
        return None

    def get_trust_store_config(self):
        """Get trust store configuration (Marty-specific)."""
        if self.config:
            try:
                return self.config.trust_store
            except Exception as e:
                print(f"Error getting trust store config: {e}")
        return None

    def get_service_discovery_config(self):
        """Get service discovery configuration."""
        if self.config:
            try:
                return self.config.service_discovery
            except Exception as e:
                print(f"Error getting service discovery config: {e}")
        return None

    def print_config_summary(self):
        """Print a summary of the loaded configuration."""
        print(f"\\n=== Configuration Summary for {self.service_name} ===")
        print(f"Environment: {self.environment}")

        if not self.config:
            print("No configuration loaded!")
            return

        # Database config
        db_config = self.get_database_config()
        if db_config:
            print(
                f"Database: {getattr(db_config, 'host', 'unknown')}:{getattr(db_config, 'port', 'unknown')}"
            )
            print(f"Database name: {getattr(db_config, 'database', 'unknown')}")

        # Security config
        security_config = self.get_security_config()
        if security_config:
            print(f"TLS enabled: {getattr(security_config.tls, 'enabled', 'unknown')}")
            print(f"mTLS enabled: {getattr(security_config.tls, 'mtls', 'unknown')}")

        # Service discovery
        discovery_config = self.get_service_discovery_config()
        if discovery_config:
            print(f"Service hosts: {getattr(discovery_config, 'hosts', {})}")
            print(f"Service ports: {getattr(discovery_config, 'ports', {})}")

        # Marty-specific configs
        crypto_config = self.get_cryptographic_config()
        if crypto_config:
            print(f"Signing algorithm: {getattr(crypto_config.signing, 'algorithm', 'unknown')}")
            print(f"Vault URL: {getattr(crypto_config.vault, 'url', 'not configured')}")

        trust_config = self.get_trust_store_config()
        if trust_config:
            print(
                f"Certificate store: {getattr(trust_config.trust_anchor, 'certificate_store_path', 'unknown')}"
            )
            print(f"PKD service: {getattr(trust_config.pkd, 'service_url', 'not configured')}")


def main():
    """Example usage of the unified configuration system."""
    print("=== Marty Service Configuration Migration Example ===")

    # Example services that could be migrated
    services = ["document_signer", "trust_anchor", "csca_service", "pkd_service"]

    for service_name in services:
        print(f"\\n--- Testing {service_name} ---")
        service = UnifiedMartyService(service_name, "development")
        service.print_config_summary()


if __name__ == "__main__":
    main()
