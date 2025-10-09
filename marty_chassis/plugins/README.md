# Marty Chassis Plugin Architecture

A comprehensive plugin architecture that provides extensibility for the Marty microservices framework through well-defined interfaces and extension points.

## Overview

The plugin architecture enables developers to extend the framework functionality without modifying the core codebase. It supports:

- **Dynamic Plugin Loading**: Load plugins from directories or Python entry points
- **Lifecycle Management**: Full plugin lifecycle with proper initialization and cleanup
- **Extension Points**: Well-defined hooks for extending framework behavior
- **Plugin Isolation**: Sandboxing to ensure plugins don't interfere with each other
- **Service Integration**: Seamless integration with service registry, middleware, and events
- **Hot Reloading**: Add or remove plugins without restarting the service

## Plugin Types

### 1. Base Plugin (IPlugin)
All plugins must implement the `IPlugin` interface:

```python
from marty_chassis.plugins import IPlugin, plugin, PluginMetadata

@plugin(
    name="my-plugin",
    version="1.0.0",
    description="My awesome plugin",
    author="Your Name"
)
class MyPlugin(IPlugin):
    async def initialize(self, context):
        self.logger = context.logger
        # Plugin initialization logic

    async def start(self):
        # Start plugin operations
        pass

    async def stop(self):
        # Stop plugin operations
        pass
```

### 2. Service Plugin (IServicePlugin)
For plugins that interact with service registry:

```python
from marty_chassis.plugins import IServicePlugin, plugin

@plugin(name="service-discovery", version="1.0.0")
class ServiceDiscoveryPlugin(IServicePlugin):
    async def on_service_register(self, service_info):
        # Called when a service is registered
        pass

    async def on_service_unregister(self, service_info):
        # Called when a service is unregistered
        pass

    async def on_service_discovery(self, query):
        # Called during service discovery
        return []  # Return matching services
```

### 3. Middleware Plugin (IMiddlewarePlugin)
For request/response processing:

```python
from marty_chassis.plugins import IMiddlewarePlugin, plugin

@plugin(name="request-tracing", version="1.0.0")
class TracingPlugin(IMiddlewarePlugin):
    async def process_request(self, request, call_next):
        # Add correlation ID
        correlation_id = str(uuid.uuid4())
        request.headers['X-Correlation-ID'] = correlation_id

        # Process request
        response = await call_next(request)

        # Add to response
        response.headers['X-Correlation-ID'] = correlation_id
        return response

    def get_middleware_priority(self):
        return 10  # Lower = higher priority
```

### 4. Event Handler Plugin (IEventHandlerPlugin)
For event-driven functionality:

```python
from marty_chassis.plugins import IEventHandlerPlugin, plugin

@plugin(name="audit-logger", version="1.0.0")
class AuditPlugin(IEventHandlerPlugin):
    def get_event_subscriptions(self):
        return {
            "user.login": "handle_login",
            "user.logout": "handle_logout",
            "service.error": "handle_error"
        }

    async def handle_event(self, event_type, event_data):
        # Route to specific handlers
        pass

    async def handle_login(self, event_data):
        # Handle login events
        self.logger.info(f"User login: {event_data}")
```

### 5. Health Plugin (IHealthPlugin)
For custom health checks:

```python
from marty_chassis.plugins import IHealthPlugin, plugin

@plugin(name="database-health", version="1.0.0")
class DatabaseHealthPlugin(IHealthPlugin):
    async def check_health(self):
        # Check database connectivity
        return {
            "healthy": True,
            "database": "postgresql",
            "connections": 5
        }

    def get_health_check_interval(self):
        return 30  # Check every 30 seconds
```

### 6. Metrics Plugin (IMetricsPlugin)
For custom metrics collection:

```python
from marty_chassis.plugins import IMetricsPlugin, plugin

@plugin(name="custom-metrics", version="1.0.0")
class MetricsPlugin(IMetricsPlugin):
    async def collect_metrics(self):
        return {
            "custom_counter": 42,
            "response_time": 0.125,
            "active_users": 100
        }

    def get_metric_definitions(self):
        return {
            "custom_counter": {
                "type": "counter",
                "description": "Custom counter metric"
            }
        }
```

## Extension Points

Extension points provide hooks for plugins to extend framework behavior:

### Predefined Extension Points

- `service.pre_register` - Modify service info before registration
- `service.post_register` - Notification after service registration
- `middleware.pre_request` - Process request before main handler
- `middleware.post_response` - Process response after main handler
- `config.load` - Provide additional configuration sources
- `health.check` - Provide health check results
- `metrics.collect` - Provide custom metrics

### Using Extension Points

```python
# In your plugin
async def initialize(self, context):
    # Register extension point handler
    context.extension_points.register_handler(
        "service.pre_register",
        self.enhance_service_info,
        priority=10
    )

async def enhance_service_info(self, service_info):
    # Modify service info
    service_info["enhanced"] = True
    return service_info
```

## Plugin Configuration

Configure plugins in your application configuration:

```yaml
# config.yaml
plugins:
  directories:
    - "./plugins"
    - "./custom_plugins"

  # Plugin-specific configuration
  jwt-authentication:
    jwt_secret: "your-secret-key"
    jwt_algorithm: "HS256"
    token_expiry: 3600

  request-tracing:
    correlation_header: "X-Correlation-ID"
    timing_header: "X-Processing-Time"

  custom-metrics:
    collection_interval: 30
    export_format: "prometheus"
```

## Creating Plugin-Enabled Services

### Basic Usage

```python
from marty_chassis.plugins import create_plugin_enabled_fastapi_service

# Create service with automatic plugin loading
app = await create_plugin_enabled_fastapi_service(
    name="my-service",
    plugin_directories=["./plugins", "./custom_plugins"]
)
```

### Advanced Usage

```python
from marty_chassis import ChassisConfig
from marty_chassis.plugins import PluginEnabledServiceFactory

# Create configuration
config = ChassisConfig.from_file("config.yaml")

# Create factory
factory = PluginEnabledServiceFactory(config)

# Create service with plugins
app = await factory.create_fastapi_service_with_plugins(
    name="my-service",
    plugin_directories=["./plugins"],
    enable_auth=True,
    enable_metrics=True
)

# Access plugin manager
plugin_manager = factory.get_plugin_manager()
```

## Plugin Discovery

The framework supports multiple plugin discovery mechanisms:

### 1. Directory-based Discovery
Place plugin files in specified directories:
```
plugins/
├── authentication_plugin.py
├── metrics_plugin.py
└── custom_middleware/
    ├── __init__.py
    └── middleware.py
```

### 2. Entry Points Discovery
Register plugins as Python entry points in `setup.py`:

```python
setup(
    name="my-plugins",
    entry_points={
        "marty.plugins": [
            "auth = my_plugins.auth:AuthPlugin",
            "metrics = my_plugins.metrics:MetricsPlugin",
        ]
    }
)
```

## Plugin Management API

Plugin-enabled services automatically expose management endpoints:

### Plugin Status
```http
GET /plugins/status
```
Returns status of all loaded plugins.

### Plugin Health
```http
GET /plugins/{plugin_name}/health
```
Returns health status of a specific plugin.

### Plugin Metrics
```http
GET /plugins/metrics
```
Returns metrics from all metrics plugins.

### Plugin Reload
```http
POST /plugins/{plugin_name}/reload
```
Reload a specific plugin (development use).

### Extension Points
```http
GET /extension-points
```
Returns information about registered extension points.

## Best Practices

### 1. Plugin Design
- Keep plugins focused on a single responsibility
- Use proper error handling and logging
- Implement health checks for monitoring
- Follow semantic versioning

### 2. Configuration
- Use plugin-specific configuration sections
- Provide sensible defaults
- Validate configuration during initialization

### 3. Error Handling
- Don't let plugin errors crash the application
- Log errors clearly with plugin context
- Provide graceful degradation

### 4. Performance
- Minimize plugin initialization time
- Use async operations where appropriate
- Be mindful of middleware performance impact

### 5. Testing
- Write unit tests for plugin functionality
- Test plugin integration with the framework
- Use plugin isolation for testing

## Example Plugins

The framework includes several example plugins:

- **JWT Authentication Plugin**: Demonstrates service hooks and security
- **Request Tracing Plugin**: Shows middleware implementation
- **Custom Metrics Plugin**: Illustrates metrics collection
- **Consul Service Discovery**: Service registry integration
- **Structured Logging Plugin**: Event handling and log enhancement

## Troubleshooting

### Plugin Not Loading
1. Check plugin directory paths
2. Verify plugin file syntax
3. Check plugin metadata and decorators
4. Review plugin manager logs

### Plugin Errors
1. Check plugin health endpoints
2. Review plugin-specific logs
3. Verify plugin dependencies
4. Check configuration

### Performance Issues
1. Review middleware priority order
2. Check plugin resource usage
3. Monitor plugin metrics
4. Use plugin isolation settings

## Security Considerations

### Plugin Isolation
- Plugins run in isolated environments by default
- Module import restrictions prevent dangerous operations
- Resource limits can be configured per plugin

### Plugin Validation
- Only load plugins from trusted sources
- Review plugin code before deployment
- Use plugin signing in production environments

### Configuration Security
- Store sensitive configuration securely
- Use environment variables for secrets
- Implement proper access controls

## Advanced Topics

### Custom Extension Points
```python
from marty_chassis.plugins import ExtensionPoint, ExtensionPointType

# Define custom extension point
custom_ep = ExtensionPoint(
    name="data.transform",
    type=ExtensionPointType.FILTER,
    description="Transform data before processing",
    parameters={"data": "Dict[str, Any]"},
    return_type="Dict[str, Any]"
)

# Register extension point
extension_manager.register_extension_point(custom_ep)
```

### Plugin Dependencies
```python
@plugin(
    name="dependent-plugin",
    version="1.0.0",
    dependencies=["jwt-authentication", "metrics-collector"]
)
class DependentPlugin(IPlugin):
    pass
```

### Plugin Communication
```python
# Use event bus for plugin communication
await context.event_bus.publish(
    "custom.event",
    {"data": "value"},
    source=self.plugin_metadata.name
)
```

This plugin architecture provides a powerful and flexible foundation for extending the Marty microservices framework while maintaining security, performance, and maintainability.
