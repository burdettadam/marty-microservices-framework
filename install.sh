#!/bin/bash

# Marty Microservices Framework - Quick Install Script
# This script downloads and sets up the framework for immediate use

set -e

REPO_URL="https://github.com/burdettadam/Marty"
BRANCH="main"
FRAMEWORK_DIR="marty-microservices-framework"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

echo -e "${BLUE}🚀 Marty Microservices Framework - Quick Install${NC}"
echo "=================================================="

# Check if git is available
if ! command -v git &> /dev/null; then
    print_error "git is not installed. Please install git and try again."
    exit 1
fi

# Check if Python 3.10+ is available
if ! command -v python3 &> /dev/null; then
    print_error "python3 is not installed. Please install Python 3.10+ and try again."
    exit 1
fi

python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
    print_error "Python 3.10+ is required. Found: $python_version"
    exit 1
fi

print_status "Prerequisites check passed"

# Check if framework directory already exists
if [ -d "$FRAMEWORK_DIR" ]; then
    print_warning "Framework directory '$FRAMEWORK_DIR' already exists."
    read -p "Do you want to remove it and reinstall? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$FRAMEWORK_DIR"
        print_status "Removed existing framework directory"
    else
        print_info "Installation cancelled"
        exit 0
    fi
fi

# Clone the repository
print_info "Cloning framework from repository..."
git clone --depth 1 --branch "$BRANCH" "$REPO_URL" temp-marty-repo

# Extract just the templates directory
if [ -d "temp-marty-repo/templates" ]; then
    mv temp-marty-repo/templates "$FRAMEWORK_DIR"
    rm -rf temp-marty-repo
    print_status "Framework extracted successfully"
else
    print_error "Templates directory not found in repository"
    rm -rf temp-marty-repo
    exit 1
fi

# Navigate to framework directory
cd "$FRAMEWORK_DIR"

# Install dependencies
print_info "Installing framework dependencies..."
pip3 install -r requirements.txt

print_status "Dependencies installed"

# Make scripts executable
chmod +x scripts/*.sh scripts/*.py

print_status "Scripts made executable"

# Run framework setup
print_info "Running framework setup and validation..."
python3 scripts/test_framework.py

if [ $? -eq 0 ]; then
    print_status "Framework setup and validation completed successfully"
else
    print_error "Framework validation failed"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 Marty Microservices Framework installed successfully!${NC}"
echo ""
echo "📁 Framework location: ./$FRAMEWORK_DIR"
echo ""
echo "🚀 Quick start commands:"
echo "  cd $FRAMEWORK_DIR"
echo "  make help                                    # Show all available commands"
echo "  make generate-fastapi NAME=my-api           # Generate a REST API service"
echo "  make generate-grpc NAME=my-grpc             # Generate a gRPC service"
echo "  make new-project NAME=my-project            # Create a complete project"
echo ""
echo "📚 Documentation:"
echo "  cat README.md                               # Framework documentation"
echo "  make docs                                   # Show documentation links"
echo "  make examples                               # Show usage examples"
echo ""
echo "Happy building! 🎉"
