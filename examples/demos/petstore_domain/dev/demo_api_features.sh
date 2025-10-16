#!/bin/bash

# Petstore Domain API Documentation and Contract Testing Demo
# This script demonstrates the new API documentation and contract testing capabilities
# of the Marty Microservices Framework using the petstore domain plugin.

set -e

echo "🐾 Petstore Domain API Documentation & Contract Testing Demo"
echo "============================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}📋 Step 1: Setup and Prerequisites${NC}"
echo "Checking prerequisites..."

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "❌ uv is required but not installed. Please install uv first."
    exit 1
fi

# Check if the main framework is available
if [ ! -f "../../src/marty_msf/cli/__init__.py" ]; then
    echo "❌ Marty framework not found. Please run from the petstore plugin directory."
    exit 1
fi

echo "✅ Prerequisites check passed"
echo ""

echo -e "${BLUE}📋 Step 2: Generate API Documentation${NC}"
echo "Generating comprehensive API documentation for the petstore service..."

# Create docs directory if it doesn't exist
mkdir -p docs/api

# Run the documentation generation
echo "Running: marty api docs for petstore service..."
cd ../..
uv run python -m src.marty_msf.cli api docs \
    -s ./plugins/petstore_domain/app \
    -o ./plugins/petstore_domain/docs/api \
    --theme redoc \
    --include-examples \
    --generate-postman

echo "✅ API documentation generated"
echo ""

cd plugins/petstore_domain

echo -e "${BLUE}📋 Step 3: Register API Versions${NC}"
echo "Registering API versions for tracking and deprecation management..."

# Register current stable version
cd ../..
uv run python -m src.marty_msf.cli api register-version \
    -s petstore-domain \
    -v 2.0.0 \
    --status active \
    -m "https://docs.petstore.example.com/migration/v2.0"

# Register deprecated version
uv run python -m src.marty_msf.cli api register-version \
    -s petstore-domain \
    -v 1.0.0 \
    --status deprecated \
    -d 2024-12-31 \
    -m "https://docs.petstore.example.com/migration/v1-to-v2"

# Register beta version
uv run python -m src.marty_msf.cli api register-version \
    -s petstore-domain \
    -v 2.1.0-beta \
    --status active \
    -m "https://docs.petstore.example.com/migration/v2.1-beta"

echo "✅ API versions registered"
echo ""

echo -e "${BLUE}📋 Step 4: List API Versions${NC}"
echo "Displaying registered API versions..."

uv run python -m src.marty_msf.cli api list-versions -s petstore-domain

echo ""

cd plugins/petstore_domain

echo -e "${BLUE}📋 Step 5: Create Consumer-Driven Contracts${NC}"
echo "Creating comprehensive contracts for different consumers..."

# Create contracts directory
mkdir -p contracts/{rest,internal,integration}

# Create a sample contract for web frontend
echo "Creating web frontend contract..."
cd ../..
uv run python -m src.marty_msf.cli api create-contract \
    -c web-frontend \
    -p petstore-domain \
    -v 2.0.0 \
    --type rest \
    -o ./plugins/petstore_domain/contracts

# Create a sample contract for mobile app
echo "Creating mobile app contract..."
uv run python -m src.marty_msf.cli api create-contract \
    -c mobile-app \
    -p petstore-domain \
    -v 2.0.0 \
    --type rest \
    -o ./plugins/petstore_domain/contracts

# Create a sample internal service contract
echo "Creating order service contract..."
uv run python -m src.marty_msf.cli api create-contract \
    -c order-service \
    -p petstore-domain \
    -v 2.0.0 \
    --type rest \
    -o ./plugins/petstore_domain/contracts

echo "✅ Consumer contracts created"
echo ""

cd plugins/petstore_domain

echo -e "${BLUE}📋 Step 6: List Available Contracts${NC}"
echo "Displaying all available contracts..."

cd ../..
uv run python -m src.marty_msf.cli api list-contracts \
    --contracts-dir ./plugins/petstore_domain/contracts

echo ""

cd plugins/petstore_domain

echo -e "${BLUE}📋 Step 7: Generate Contract Documentation${NC}"
echo "Creating human-readable documentation from contracts..."

cd ../..
uv run python -m src.marty_msf.cli api generate-contract-docs \
    --contracts-dir ./plugins/petstore_domain/contracts \
    --docs-dir ./plugins/petstore_domain/docs/contracts \
    --format html

echo "✅ Contract documentation generated"
echo ""

cd plugins/petstore_domain

echo -e "${BLUE}📋 Step 8: Setup Demonstration Files${NC}"
echo "Creating demonstration configuration files..."

# Create API documentation config
cat > api-docs-config.yaml << 'EOF'
# Petstore API Documentation Configuration
output_dir: "./docs/api"
theme: "redoc"
include_examples: true
generate_postman: true
generate_grpc_docs: false
generate_unified_docs: false

service_metadata:
  title: "Petstore Domain API"
  version: "2.0.0"
  description: |
    Comprehensive petstore domain service demonstrating enterprise-grade
    microservice patterns with the Marty Microservices Framework.

  contact:
    name: "Petstore API Team"
    email: "api-support@petstore.example.com"
    url: "https://docs.petstore.example.com"

  servers:
    - url: "https://api.petstore.example.com"
      description: "Production server"
    - url: "https://staging-api.petstore.example.com"
      description: "Staging server"
    - url: "http://localhost:8000"
      description: "Development server"
EOF

# Create contract monitoring config
cat > contract-monitor-config.yaml << 'EOF'
# Contract Monitoring Configuration
contracts_dir: "./contracts"
interval: 300  # 5 minutes
webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

providers:
  - name: "petstore-domain"
    rest_url: "http://localhost:8000"

consumers:
  - "web-frontend"
  - "mobile-app"
  - "order-service"

verification_level: "strict"
EOF

echo "✅ Configuration files created"
echo ""

echo -e "${BLUE}📋 Step 9: Create Usage Examples${NC}"
echo "Creating practical usage examples..."

# Create a comprehensive usage guide
cat > docs/API_DOCUMENTATION_USAGE.md << 'EOF'
# Petstore API Documentation & Contract Testing Usage Guide

This guide demonstrates how to use the new API documentation and contract testing features with the petstore domain service.

## 🚀 Quick Start

### Generate API Documentation
```bash
# Generate comprehensive documentation
marty api docs -s ./app -o ./docs/api --theme redoc --include-examples

# Generate with custom configuration
marty api docs -s ./app -c ./api-docs-config.yaml
```

### Manage API Versions
```bash
# Register a new version
marty api register-version -s petstore-domain -v 2.1.0

# Mark version as deprecated
marty api register-version -s petstore-domain -v 1.0.0 --status deprecated -d 2024-12-31

# List all versions
marty api list-versions -s petstore-domain
```

### Create and Test Contracts
```bash
# Create interactive contract
marty api create-contract -c web-frontend -p petstore-domain --interactive

# Test contracts against running service
marty api test-contracts -p petstore-domain -u http://localhost:8000

# Monitor contract compliance
marty api monitor-contracts -c ./contract-monitor-config.yaml
```

## 📋 Contract Examples

### Web Frontend Contract
The web frontend requires:
- GET /petstore-domain/pets with pagination
- POST /petstore-domain/pets for creating pets
- PUT /petstore-domain/pets/{id} for updates
- Proper error handling for 404/400 responses

### Mobile App Contract
The mobile app needs:
- Optimized responses with thumbnails
- Different pagination (scroll-based)
- Mobile-specific authentication
- Simplified data structures

### Internal Service Contracts
Order service integration requires:
- Pet availability checking
- Reservation capabilities
- Stock management
- Service-to-service authentication

## 🔧 Advanced Usage

### Custom Documentation Themes
- `redoc`: Modern, clean design
- `swagger-ui`: Interactive exploration
- `stoplight`: Advanced documentation features

### Contract Testing Levels
- `strict`: Full request/response validation
- `permissive`: Schema validation only
- `schema_only`: Structure validation

### Monitoring Integration
- Slack webhooks for failures
- CI/CD pipeline integration
- Continuous compliance checking

## 📊 Integration with CI/CD

```yaml
# .github/workflows/api-contracts.yml
name: API Contract Testing
on: [push, pull_request]

jobs:
  contract-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Test Contracts
        run: |
          marty api test-contracts -p petstore-domain -u ${{ env.API_URL }} --output-format junit
      - name: Upload Results
        uses: actions/upload-artifact@v2
        with:
          name: contract-test-results
          path: contract-test-results.xml
```

## 🎯 Best Practices

1. **Version Contracts**: Always specify API version in contracts
2. **Realistic Data**: Use production-like test data
3. **Error Scenarios**: Include error cases in contracts
4. **Regular Updates**: Keep contracts synchronized with API changes
5. **Documentation**: Maintain clear contract documentation

## 🔗 Links

- [API Documentation](./docs/api/index.html)
- [Contract Documentation](./docs/contracts/index.html)
- [Petstore Service README](./README.md)
EOF

echo "✅ Usage examples created"
echo ""

echo -e "${YELLOW}📋 Step 10: Demonstration Summary${NC}"
echo "================================================================="
echo ""
echo "🎉 Petstore API Documentation & Contract Testing Demo Complete!"
echo ""
echo "What was demonstrated:"
echo "✅ Comprehensive API documentation generation"
echo "✅ API version registration and management"
echo "✅ Consumer-driven contract creation"
echo "✅ Contract documentation generation"
echo "✅ Configuration management"
echo "✅ Usage examples and best practices"
echo ""
echo "Generated Files:"
echo "📁 docs/api/ - Interactive API documentation"
echo "📁 docs/contracts/ - Contract documentation"
echo "📁 contracts/ - Consumer-driven contracts"
echo "📄 api-docs-config.yaml - Documentation configuration"
echo "📄 contract-monitor-config.yaml - Monitoring configuration"
echo "📄 docs/API_DOCUMENTATION_USAGE.md - Usage guide"
echo ""
echo "Next Steps:"
echo "1. Start the petstore service: python main.py"
echo "2. Open API docs: open docs/api/index.html"
echo "3. Test contracts: marty api test-contracts -p petstore-domain -u http://localhost:8000"
echo "4. Monitor compliance: marty api monitor-contracts -c contract-monitor-config.yaml"
echo ""
echo -e "${GREEN}🚀 Ready for production use!${NC}"
