# Marty CLI

The Marty CLI provides powerful command-line tools for creating, managing, and deploying microservices using the Marty Microservices Framework.

## Quick Usage

```bash
# Generate a FastAPI service
make generate TYPE=fastapi NAME=my-api

# Generate a gRPC service
make generate TYPE=grpc NAME=my-grpc-service

# Create a complete project
make new NAME=my-awesome-project
```

## Full Documentation

For complete CLI documentation, including all commands, options, and examples, see:

**[📚 Complete CLI Guide](docs/guides/CLI_README.md)**

## Common Commands

| Command | Description |
|---------|-------------|
| `make generate` | Generate a new service with specified type and name |
| `make new` | Create a complete project structure |
| `make dev` | Setup development environment |
| `make test` | Run all tests |
| `make help` | Show all available commands |

For detailed usage and advanced features, please refer to the [full CLI documentation](docs/guides/CLI_README.md).
