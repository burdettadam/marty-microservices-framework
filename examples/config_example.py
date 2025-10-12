"""
Comprehensive example demonstrating the enterprise configuration framework.

This example shows:
- Environment-based configuration management
- Service-specific configuration
- Configuration validation
- Environment variable expansion
- Multi-environment support
"""

import logging
import os

from framework.config import DatabaseConfigSection, Environment, create_service_config

# Configure logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demonstrate_basic_configuration():
    """Demonstrate basic configuration usage."""
    print("=== Basic Configuration Demo ===\n")

    # 1. Create service configuration for development
    print("1. Creating user service configuration for development...")
    config = create_service_config("user_service", Environment.DEVELOPMENT)

    print(f"   ✓ Service: {config.service_name}")
    print(f"   ✓ Environment: {config.environment.value}")

    # 2. Access database configuration
    print("\n2. Accessing database configuration...")
    try:
        db_config = config.database
        print(f"   ✓ Database: {db_config.database}")
        print(f"   ✓ Host: {db_config.host}")
        print(f"   ✓ Port: {db_config.port}")
        print(f"   ✓ Pool size: {db_config.pool_size}")
        print(f"   ✓ Connection URL: {db_config.connection_url}")
    except Exception as e:
        print(f"   ❌ Database config error: {e}")

    # 3. Access security configuration
    print("\n3. Accessing security configuration...")
    security_config = config.security
    print(f"   ✓ TLS enabled: {security_config.tls.enabled}")
    print(f"   ✓ mTLS enabled: {security_config.tls.mtls}")
    print(f"   ✓ Auth required: {security_config.auth.required}")
    print(f"   ✓ JWT enabled: {security_config.auth.jwt_enabled}")

    # 4. Access logging configuration
    print("\n4. Accessing logging configuration...")
    logging_config = config.logging
    print(f"   ✓ Log level: {logging_config.level}")
    print(f"   ✓ Handlers: {', '.join(logging_config.handlers)}")
    print(f"   ✓ Log file: {logging_config.file}")

    # 5. Access monitoring configuration
    print("\n5. Accessing monitoring configuration...")
    monitoring_config = config.monitoring
    print(f"   ✓ Monitoring enabled: {monitoring_config.enabled}")
    print(f"   ✓ Metrics port: {monitoring_config.metrics_port}")
    print(f"   ✓ Prometheus enabled: {monitoring_config.prometheus_enabled}")
    print(f"   ✓ Service name: {monitoring_config.service_name}")

    # 6. Get custom configuration values
    print("\n6. Accessing custom configuration values...")
    max_connections = config.get("services.user_service.max_connections", 100)
    request_timeout = config.get("services.user_service.request_timeout", 30)
    print(f"   ✓ Max connections: {max_connections}")
    print(f"   ✓ Request timeout: {request_timeout}")

    print("\n=== Basic configuration demo completed! ===")


def demonstrate_environment_differences():
    """Demonstrate configuration differences across environments."""
    print("\n=== Environment Configuration Differences ===\n")

    environments = [
        Environment.DEVELOPMENT,
        Environment.TESTING,
        Environment.PRODUCTION,
    ]

    for env in environments:
        print(f"--- {env.value.upper()} Environment ---")

        try:
            config = create_service_config("payment_service", env)

            # Security settings
            security = config.security
            print(f"TLS enabled: {security.tls.enabled}")
            print(f"Auth required: {security.auth.required}")
            print(f"Authorization enabled: {security.authz.enabled}")

            # Monitoring settings
            monitoring = config.monitoring
            print(f"Tracing enabled: {monitoring.tracing_enabled}")

            # Service-specific settings
            service_config = config.get_service_config()
            if service_config:
                max_amount = service_config.get("max_transaction_amount", "Not configured")
                print(f"Max transaction amount: {max_amount}")
                fraud_check = service_config.get("fraud_check_enabled", "Not configured")
                print(f"Fraud check enabled: {fraud_check}")

            print()

        except Exception as e:
            print(f"❌ Error loading {env.value} config: {e}\n")


def demonstrate_environment_variables():
    """Demonstrate environment variable expansion."""
    print("=== Environment Variable Expansion Demo ===\n")

    # Set some test environment variables
    os.environ["TEST_DB_PASSWORD"] = "secret_password_123"
    os.environ["TEST_JWT_SECRET"] = "jwt_secret_for_testing"
    os.environ["TEST_SERVICE_PORT"] = "8080"

    print("1. Set test environment variables:")
    print("   TEST_DB_PASSWORD=secret_password_123")
    print("   TEST_JWT_SECRET=jwt_secret_for_testing")
    print("   TEST_SERVICE_PORT=8080")

    try:
        # Create a test configuration that uses environment variables
        config = create_service_config("user_service", Environment.DEVELOPMENT)

        print("\n2. Configuration with environment variables:")

        # Try to access expanded values
        jwt_secret = config.get("security.auth.jwt.secret", "Not set")
        print(
            f"   JWT secret: {jwt_secret[:10]}..."
            if len(jwt_secret) > 10
            else f"   JWT secret: {jwt_secret}"
        )

        # Get any environment-expanded values from the raw config
        raw_config = config.to_dict()
        print(f"   Raw config keys: {list(raw_config.keys())}")

    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Clean up environment variables
    for var in ["TEST_DB_PASSWORD", "TEST_JWT_SECRET", "TEST_SERVICE_PORT"]:
        os.environ.pop(var, None)

    print("\n3. Cleaned up test environment variables")


def demonstrate_validation():
    """Demonstrate configuration validation."""
    print("\n=== Configuration Validation Demo ===\n")

    print("1. Testing valid configuration...")
    try:
        config = create_service_config("user_service", Environment.DEVELOPMENT)

        # Validate each section
        db_config = config.database
        db_config.validate()
        print("   ✓ Database configuration is valid")

        security_config = config.security
        security_config.validate()
        print("   ✓ Security configuration is valid")

        logging_config = config.logging
        logging_config.validate()
        print("   ✓ Logging configuration is valid")

        monitoring_config = config.monitoring
        monitoring_config.validate()
        print("   ✓ Monitoring configuration is valid")

    except Exception as e:
        print(f"   ❌ Validation error: {e}")

    print("\n2. Testing invalid configuration...")
    try:
        # Create an invalid database config
        invalid_db_config = DatabaseConfigSection(
            host="localhost",
            port=-1,  # Invalid port
            database="",  # Empty database name
            username="",  # Empty username
            password="",  # Empty password
        )
        invalid_db_config.validate()
        print("   ❌ Should have failed validation")

    except Exception as e:
        print(f"   ✓ Correctly caught validation error: {e}")


def demonstrate_service_specific_config():
    """Demonstrate service-specific configuration."""
    print("\n=== Service-Specific Configuration Demo ===\n")

    services = ["user_service", "payment_service"]

    for service_name in services:
        print(f"--- {service_name.upper()} ---")

        try:
            config = create_service_config(service_name, Environment.DEVELOPMENT)

            # Get service-specific configuration
            service_config = config.get_service_config()

            if service_config:
                print("Service-specific configuration found:")
                for key, value in service_config.items():
                    if isinstance(value, dict):
                        print(f"  {key}: {list(value.keys())}")
                    else:
                        print(f"  {key}: {value}")
            else:
                print("No service-specific configuration found")

            print()

        except Exception as e:
            print(f"❌ Error loading {service_name} config: {e}\n")


def demonstrate_configuration_export():
    """Demonstrate configuration export and inspection."""
    print("=== Configuration Export Demo ===\n")

    try:
        config = create_service_config("user_service", Environment.DEVELOPMENT)

        print("1. Exporting configuration to dictionary...")
        config_dict = config.to_dict()

        print(f"   ✓ Top-level keys: {list(config_dict.keys())}")

        # Show database configuration
        if "database" in config_dict:
            db_config = config_dict["database"]
            if isinstance(db_config, dict) and "user_service" in db_config:
                user_db = db_config["user_service"]
                print(f"   ✓ User service database: {user_db.get('database', 'N/A')}")

        # Show security configuration
        if "security" in config_dict:
            security_config = config_dict["security"]
            if isinstance(security_config, dict):
                auth_config = security_config.get("auth", {})
                print(f"   ✓ Auth required: {auth_config.get('required', 'N/A')}")

        print("\n2. Configuration summary:")
        print(f"   Service: {config.service_name}")
        print(f"   Environment: {config.environment.value}")
        print(f"   Total configuration keys: {len(config_dict)}")

    except Exception as e:
        print(f"   ❌ Export error: {e}")


def run_comprehensive_demo():
    """Run the comprehensive configuration demo."""
    print("🔧 Enterprise Configuration Framework Demo")
    print("=" * 50)

    # Run all demonstration functions
    demonstrate_basic_configuration()
    demonstrate_environment_differences()
    demonstrate_environment_variables()
    demonstrate_validation()
    demonstrate_service_specific_config()
    demonstrate_configuration_export()

    print("\n🎉 Configuration framework demo completed successfully!")
    print("\nKey Features Demonstrated:")
    print("✅ Environment-based configuration management")
    print("✅ Service-specific configuration isolation")
    print("✅ Configuration validation and error handling")
    print("✅ Environment variable expansion")
    print("✅ Multi-environment support")
    print("✅ Structured configuration sections")
    print("✅ Configuration export and inspection")


if __name__ == "__main__":
    run_comprehensive_demo()
