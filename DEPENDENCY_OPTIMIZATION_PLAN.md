# Dependency and Linting Configuration Optimization Plan

## Current Issues

### Core Dependencies (pyproject.toml:27)
The current dependency list includes 20+ core dependencies, some of which are only used in specific features:

**Always Required (Core):**
- fastapi>=0.104.0
- uvicorn[standard]>=0.24.0
- pydantic>=2.5.0
- python-multipart>=0.0.6
- click>=8.1.0
- rich>=13.8.0
- jinja2>=3.1.0
- toml>=0.10.2
- pyyaml>=6.0.0
- aiohttp>=3.13.0
- aiofiles>=24.1.0
- pydantic-settings>=2.11.0

**Feature-Specific (Should be optional):**
- cookiecutter>=2.5.0 (CLI only - used in marty_cli)
- aiokafka>=0.12.0 (messaging features)
- kafka-python>=2.2.15 (messaging features)
- grpcio>=1.75.1 (gRPC features)
- grpcio-tools>=1.75.1 (gRPC features)
- grpcio-reflection>=1.59.0 (gRPC features)
- docker>=7.1.0 (testing features)
- psutil>=7.1.0 (monitoring features)
- sqlalchemy>=2.0.44 (database features)

### Ruff Ignore Rules (pyproject.toml:166)
Currently ignoring several important rules that should be addressed:

```toml
ignore = [
    "E501",  # line-too-long
    "C901",  # complex-structure
    "I001",  # unsorted-imports
    "E402",  # module-import-not-at-top-of-file
    "B904",  # raise-without-from-inside-except
    "B027",  # empty-method-without-abstract-decorator
    "B024",  # abstract-base-class-without-abstract-method
]
```

## Proposed Optimization

### 1. Restructure Dependencies

#### Move to Core Dependencies (12 dependencies)
```toml
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.5.0",
    "python-multipart>=0.0.6",
    "click>=8.1.0",
    "rich>=13.8.0",
    "jinja2>=3.1.0",
    "toml>=0.10.2",
    "pyyaml>=6.0.0",
    "aiohttp>=3.13.0",
    "aiofiles>=24.1.0",
    "pydantic-settings>=2.11.0",
]
```

#### Move to Optional Dependencies
```toml
[project.optional-dependencies]
# CLI and code generation
cli = [
    "cookiecutter>=2.5.0",
    "gitpython>=3.1.40",
]

# Messaging and event streaming
messaging = [
    "aiokafka>=0.12.0",
    "kafka-python>=2.2.15",
]

# gRPC support
grpc = [
    "grpcio>=1.75.1",
    "grpcio-tools>=1.75.1",
    "grpcio-reflection>=1.59.0",
]

# Database integration
database = [
    "sqlalchemy>=2.0.44",
]

# Testing and development
testing = [
    "docker>=7.1.0",
]

# Monitoring and metrics
monitoring = [
    "psutil>=7.1.0",
]

# Security features
security = [
    "bandit[toml]>=1.8.0",
    "defusedxml>=0.7.1",
    "pyjwt>=2.10.1",
    "cryptography>=46.0.2",
    "bcrypt>=5.0.0",
    "passlib>=1.7.4",
]

# Complete installation (all features)
all = [
    "marty-microservices-framework[cli,messaging,grpc,database,testing,monitoring,security]"
]
```

### 2. Gradual Ruff Rules Re-enabling

After module decomposition is complete, gradually re-enable rules:

#### Phase 1: Auto-fixable rules
```toml
# Remove from ignore list (can be auto-fixed):
# "I001",  # unsorted-imports
# "E402",  # module-import-not-at-top-of-file
```

#### Phase 2: After decomposition
```toml
# Remove from ignore list (decomposition helps):
# "C901",  # complex-structure (smaller modules)
# "E501",  # line-too-long (smaller modules)
```

#### Phase 3: Exception handling improvements
```toml
# Remove from ignore list (dedicated effort):
# "B904",  # raise-without-from-inside-except
# "B027",  # empty-method-without-abstract-decorator
# "B024",  # abstract-base-class-without-abstract-method
```

### 3. Usage Impact

#### Before (Current)
```bash
pip install marty-microservices-framework
# Installs 20+ dependencies regardless of usage
```

#### After (Optimized)
```bash
# Basic framework
pip install marty-microservices-framework

# With messaging features
pip install marty-microservices-framework[messaging]

# With all features
pip install marty-microservices-framework[all]

# Development with testing
pip install marty-microservices-framework[testing,cli]
```

### 4. Code Changes Required

#### Update Import Patterns
Components that use optional dependencies should handle missing imports gracefully:

```python
# Before
from aiokafka import AIOKafkaProducer

# After
try:
    from aiokafka import AIOKafkaProducer
except ImportError:
    raise ImportError(
        "Kafka support requires 'aiokafka'. "
        "Install with: pip install marty-microservices-framework[messaging]"
    )
```

#### Create Feature Detection Utilities
```python
# src/framework/utils/features.py
def has_kafka_support() -> bool:
    """Check if Kafka dependencies are available."""
    try:
        import aiokafka
        return True
    except ImportError:
        return False

def has_grpc_support() -> bool:
    """Check if gRPC dependencies are available."""
    try:
        import grpcio
        return True
    except ImportError:
        return False
```

### 5. Benefits

#### Installation Performance
- **Faster installs:** Core framework installs ~60% fewer dependencies
- **Smaller images:** Docker images only include needed dependencies
- **Reduced conflicts:** Fewer dependency version conflicts

#### Development Experience
- **Clear dependencies:** Explicit about what features require what dependencies
- **Easier debugging:** Missing features have clear error messages
- **Better testing:** Can test with minimal dependency sets

#### Code Quality
- **Progressive improvement:** Ruff rules enabled gradually
- **Focused fixes:** Rules re-enabled as structural issues are resolved
- **Maintained standards:** Quality doesn't regress

### 6. Implementation Steps

1. ✅ **Audit current dependencies:** Identify feature-specific vs core dependencies
2. **Create optional dependency groups:** Move feature-specific deps to optional
3. **Update import handling:** Add graceful error handling for missing optional deps
4. **Create feature detection:** Add utility functions to check feature availability
5. **Update documentation:** Reflect new installation patterns
6. **Test installations:** Verify core and optional dependency combinations work
7. **Re-enable Ruff rules:** Start with auto-fixable rules
8. **Progressive quality improvement:** Address remaining lint issues

### 7. Estimated Impact

#### Dependency Reduction
- **Core dependencies:** From 20+ to 12 (40% reduction)
- **Optional features:** 8 focused feature groups
- **Install time:** Estimated 40-60% faster for core framework

#### Code Quality
- **Lint rules:** Gradually reduce ignored rules from 7 to 0
- **Maintainability:** Better separation of concerns
- **Reliability:** More explicit about feature requirements

## Next Steps

This optimization should be done after the module decomposition is complete, as the smaller, more focused modules will make it easier to re-enable the lint rules and identify which dependencies are truly needed.
