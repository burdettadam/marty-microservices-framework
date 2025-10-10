#!/bin/bash

# Plugin System Test Runner
# Comprehensive test execution script for the MMF plugin system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}Plugin System Test Runner${NC}"
echo "========================================"
echo "Project Root: $PROJECT_ROOT"
echo "Test Directory: $SCRIPT_DIR"
echo ""

# Function to print status
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [[ ! -f "$PROJECT_ROOT/pyproject.toml" ]]; then
    print_error "pyproject.toml not found in project root. Please run from the correct directory."
    exit 1
fi

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    print_error "uv is not installed. Please install it first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  or visit: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# Create virtual environment with uv if it doesn't exist
if [[ ! -d "$PROJECT_ROOT/.venv" ]]; then
    print_warning "Virtual environment not found. Creating one with uv..."
    cd "$PROJECT_ROOT"
    uv venv
    print_success "Virtual environment created with uv"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
cd "$PROJECT_ROOT"
source .venv/bin/activate
print_status "Virtual environment activated"

# Install test dependencies with uv
print_status "Installing test dependencies with uv..."
cd "$SCRIPT_DIR"
uv pip install -r requirements-test.txt
print_success "Test dependencies installed"

# Set Python path
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"
print_status "Python path configured"

# Function to run tests with different configurations
run_test_suite() {
    local test_type="$1"
    local test_args="$2"

    print_status "Running $test_type tests..."

    if pytest $test_args; then
        print_success "$test_type tests passed"
        return 0
    else
        print_error "$test_type tests failed"
        return 1
    fi
}

# Parse command line arguments
TEST_TYPES=()
VERBOSE=false
COVERAGE=true
SPECIFIC_TEST=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --unit)
            TEST_TYPES+=("unit")
            shift
            ;;
        --integration)
            TEST_TYPES+=("integration")
            shift
            ;;
        --performance)
            TEST_TYPES+=("performance")
            shift
            ;;
        --security)
            TEST_TYPES+=("security")
            shift
            ;;
        --all)
            TEST_TYPES=("unit" "integration" "performance" "security")
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --no-coverage)
            COVERAGE=false
            shift
            ;;
        --test)
            SPECIFIC_TEST="$2"
            shift 2
            ;;
        --help|-h)
            echo "Plugin System Test Runner"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --unit          Run unit tests only"
            echo "  --integration   Run integration tests only"
            echo "  --performance   Run performance tests only"
            echo "  --security      Run security tests only"
            echo "  --all           Run all test suites (default)"
            echo "  --verbose, -v   Enable verbose output"
            echo "  --no-coverage   Disable coverage reporting"
            echo "  --test <name>   Run specific test"
            echo "  --help, -h      Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Run all tests"
            echo "  $0 --unit --verbose  # Run unit tests with verbose output"
            echo "  $0 --test test_core  # Run specific test file"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Default to all tests if none specified
if [[ ${#TEST_TYPES[@]} -eq 0 ]]; then
    TEST_TYPES=("unit" "integration")
fi

# Build base pytest command
PYTEST_CMD="pytest"

if [[ "$VERBOSE" == "true" ]]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

if [[ "$COVERAGE" == "true" ]]; then
    PYTEST_CMD="$PYTEST_CMD --cov=src/framework/plugins --cov=src/plugins --cov-report=term-missing --cov-report=html"
fi

# Add specific test if provided
if [[ -n "$SPECIFIC_TEST" ]]; then
    PYTEST_CMD="$PYTEST_CMD -k $SPECIFIC_TEST"
fi

# Run linting first
print_status "Running code quality checks..."

# Check if mypy is available
if command -v mypy &> /dev/null; then
    print_status "Running mypy type checking..."
    if mypy "$PROJECT_ROOT/src" --config-file="$SCRIPT_DIR/pyproject.toml"; then
        print_success "Type checking passed"
    else
        print_warning "Type checking found issues (continuing with tests)"
    fi
else
    print_warning "mypy not available, skipping type checking"
fi

# Check if black is available
if command -v black &> /dev/null; then
    print_status "Checking code formatting..."
    if black --check "$PROJECT_ROOT/src" --config="$SCRIPT_DIR/pyproject.toml"; then
        print_success "Code formatting check passed"
    else
        print_warning "Code formatting issues found (continuing with tests)"
    fi
else
    print_warning "black not available, skipping format checking"
fi

# Run test suites
FAILED_TESTS=()

for test_type in "${TEST_TYPES[@]}"; do
    case $test_type in
        unit)
            if ! run_test_suite "Unit" "$PYTEST_CMD -m unit"; then
                FAILED_TESTS+=("unit")
            fi
            ;;
        integration)
            if ! run_test_suite "Integration" "$PYTEST_CMD -m integration"; then
                FAILED_TESTS+=("integration")
            fi
            ;;
        performance)
            if ! run_test_suite "Performance" "$PYTEST_CMD -m performance"; then
                FAILED_TESTS+=("performance")
            fi
            ;;
        security)
            if ! run_test_suite "Security" "$PYTEST_CMD -m security"; then
                FAILED_TESTS+=("security")
            fi
            ;;
    esac
done

# If no specific test types were requested or specific test was given, run all tests
if [[ -n "$SPECIFIC_TEST" ]] || [[ ${#TEST_TYPES[@]} -eq 0 ]]; then
    if ! run_test_suite "All" "$PYTEST_CMD"; then
        FAILED_TESTS+=("all")
    fi
fi

# Generate test report summary
echo ""
echo "========================================"
echo -e "${BLUE}Test Execution Summary${NC}"
echo "========================================"

if [[ ${#FAILED_TESTS[@]} -eq 0 ]]; then
    print_success "All tests passed successfully!"

    if [[ "$COVERAGE" == "true" ]]; then
        print_status "Coverage report generated in htmlcov/"
    fi

    echo ""
    print_success "Plugin system is ready for deployment!"
    exit 0
else
    print_error "Some tests failed:"
    for failed_test in "${FAILED_TESTS[@]}"; do
        echo "  - $failed_test"
    done

    echo ""
    print_error "Please review and fix the failing tests before deployment"
    exit 1
fi
