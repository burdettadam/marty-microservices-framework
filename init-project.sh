#!/bin/bash

# Marty Microservices Framework - Project Initialization Script
# This script sets up the framework as a standalone git project

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Initializing Marty Microservices Framework as Standalone Project${NC}"
echo "=================================================================="

# Function to print status
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if we're already in a git repository
if [ -d ".git" ]; then
    print_status "Git repository already initialized"
else
    echo "🔧 Initializing git repository..."
    git init
    git branch -m main
    print_status "Git repository initialized with main branch"
fi

# Check if .gitignore exists
if [ ! -f ".gitignore" ]; then
    print_error ".gitignore not found - this script should be run from the framework root"
    exit 1
fi

# Install pre-commit if not available
if ! command -v pre-commit &> /dev/null; then
    echo "📦 Installing pre-commit..."
    pip install pre-commit
    print_status "Pre-commit installed"
fi

# Install pre-commit hooks
echo "🔧 Installing pre-commit hooks..."
pre-commit install
print_status "Pre-commit hooks installed"

# Install framework dependencies
echo "📦 Installing framework dependencies..."
pip install -r requirements.txt
if [ -f "requirements-dev.txt" ]; then
    pip install -r requirements-dev.txt
fi
print_status "Dependencies installed"

# Run framework setup
if [ -f "scripts/setup_framework.sh" ]; then
    echo "🔧 Running framework setup..."
    bash scripts/setup_framework.sh
    print_status "Framework setup completed"
fi

# Run tests to verify everything works
echo "🧪 Running framework validation..."
python3 scripts/test_framework.py
if [ $? -eq 0 ]; then
    print_status "Framework validation passed"
else
    print_error "Framework validation failed"
    exit 1
fi

# Run type checking
echo "🔍 Running type checking..."
python3 -m mypy scripts/ --config-file mypy.ini
if [ $? -eq 0 ]; then
    print_status "Type checking passed"
else
    print_warning "Type checking found issues (see output above)"
fi

# Run pre-commit to validate everything
echo "🔧 Running pre-commit validation..."
pre-commit run --all-files
if [ $? -eq 0 ]; then
    print_status "Pre-commit hooks passed"
else
    print_warning "Pre-commit hooks found and fixed issues"
fi

# Make initial commit if no commits exist
if [ -z "$(git log --oneline 2>/dev/null)" ]; then
    echo "📝 Creating initial commit..."
    git add .
    git commit -m "feat: initialize Marty Microservices Framework

- Add comprehensive service templates (FastAPI, gRPC, hybrid, auth, database, caching, message queue)
- Implement service generation with DRY patterns
- Add template validation and framework testing
- Configure MyPy type checking for enhanced code quality
- Setup pre-commit hooks for automated quality checks
- Include complete project template for microservices
- Add comprehensive documentation and examples

Framework ready for standalone development and distribution."
    print_status "Initial commit created"
fi

echo ""
echo -e "${GREEN}🎉 Marty Microservices Framework initialized successfully!${NC}"
echo ""
echo "📖 Next Steps:"
echo "  1. Generate a service:"
echo "     python3 scripts/generate_service.py fastapi my-service"
echo ""
echo "  2. Create a new project:"
echo "     cp -r microservice_project_template my-new-project"
echo "     cd my-new-project && uv sync --extra dev"
echo ""
echo "  3. Validate framework:"
echo "     make test-all"
echo ""
echo "  4. Setup remote repository:"
echo "     git remote add origin <your-repository-url>"
echo "     git push -u origin main"
echo ""
echo "📚 Documentation: README.md"
echo "🛠️ Available commands: make help"
