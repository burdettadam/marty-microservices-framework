#!/usr/bin/env bash

# Kind + Playwright E2E Test Runner
# Comprehensive script for running Kind + Playwright end-to-end tests

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
HEADLESS=${HEADLESS:-true}
CLEANUP=${CLEANUP:-true}
TEST_TYPE=${TEST_TYPE:-all}
CLUSTER_NAME=${CLUSTER_NAME:-e2e-test-$(date +%s)}

# Functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Kind + Playwright E2E Test Runner${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

check_prerequisites() {
    print_info "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! docker ps &> /dev/null; then
        print_error "Docker is not running. Please start Docker."
        exit 1
    fi
    print_status "Docker is running"

    # Check Kind
    if ! command -v kind &> /dev/null; then
        print_error "Kind is not installed. Please install Kind first."
        echo "Install with: brew install kind (macOS) or see https://kind.sigs.k8s.io/"
        exit 1
    fi
    print_status "Kind is available"

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_warning "kubectl not found. Some debugging features may not work."
    else
        print_status "kubectl is available"
    fi

    # Check uv/Python environment
    if ! command -v uv &> /dev/null; then
        print_error "uv is not installed. Please install uv first."
        exit 1
    fi
    print_status "uv is available"

    # Check if Playwright is installed
    if ! uv run python -c "import playwright" &> /dev/null; then
        print_warning "Playwright may not be installed. Installing dependencies..."
        uv sync --group dev
        uv run playwright install chromium
    fi
    print_status "Python dependencies are ready"

    echo ""
}

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    --test-type TYPE     Type of test to run (all|complete|dashboard|scaling|visual|unit) [default: all]
    --cluster-name NAME  Name for the Kind cluster [default: e2e-test-TIMESTAMP]
    --headless BOOL      Run browser in headless mode (true|false) [default: true]
    --no-cleanup         Don't clean up cluster after tests [default: cleanup enabled]
    --help              Show this help message

Test Types:
    all        - Run all E2E tests (default)
    complete   - Run complete microservices deployment test
    dashboard  - Run dashboard functionality test only
    scaling    - Run service scaling and monitoring test
    visual     - Run visual regression detection test
    unit       - Run unit tests for infrastructure components
    manual     - Run manual test with detailed output

Examples:
    $0                                    # Run all tests with defaults
    $0 --test-type dashboard             # Run only dashboard tests
    $0 --headless false --no-cleanup     # Run with visible browser, keep cluster
    $0 --test-type complete --cluster-name my-test  # Run complete test with custom cluster name

Environment Variables:
    HEADLESS     - Set to 'false' to run browser in non-headless mode
    CLEANUP      - Set to 'false' to keep cluster after tests
    TEST_TYPE    - Set test type (same as --test-type)
    CLUSTER_NAME - Set cluster name (same as --cluster-name)

EOF
}

run_tests() {
    local test_type="$1"
    local cluster_name="$2"
    local headless="$3"
    local cleanup="$4"

    print_info "Running $test_type tests with cluster: $cluster_name"
    print_info "Headless mode: $headless, Cleanup: $cleanup"
    echo ""

    # Set environment variables
    export HEADLESS="$headless"
    export CLEANUP="$cleanup"
    export CLUSTER_NAME="$cluster_name"

    case "$test_type" in
        "all")
            print_info "Running all E2E tests..."
            uv run pytest tests/e2e/test_kind_playwright_e2e.py -v -s --tb=short
            ;;
        "complete")
            print_info "Running complete microservices deployment test..."
            uv run pytest tests/e2e/test_kind_playwright_e2e.py::TestKindPlaywrightE2E::test_complete_microservices_deployment_and_ui_testing -v -s
            ;;
        "dashboard")
            print_info "Running dashboard functionality test..."
            uv run pytest tests/e2e/test_kind_playwright_e2e.py::TestKindPlaywrightE2E::test_dashboard_functionality_only -v -s
            ;;
        "scaling")
            print_info "Running service scaling and monitoring test..."
            uv run pytest tests/e2e/test_kind_playwright_e2e.py::TestKindPlaywrightE2E::test_service_scaling_and_monitoring -v -s
            ;;
        "visual")
            print_info "Running visual regression detection test..."
            uv run pytest tests/e2e/test_kind_playwright_e2e.py::TestKindPlaywrightE2E::test_visual_regression_detection -v -s
            ;;
        "unit")
            print_info "Running infrastructure unit tests..."
            uv run pytest tests/e2e/test_kind_playwright_e2e.py::TestKindClusterManagement -v -s
            uv run pytest tests/e2e/test_kind_playwright_e2e.py::TestPlaywrightIntegration -v -s
            ;;
        "manual")
            print_info "Running manual test with detailed output..."
            uv run python -c "
import asyncio
from tests.e2e.test_kind_playwright_e2e import run_manual_e2e_test
result = asyncio.run(run_manual_e2e_test())
exit(0 if result else 1)
"
            ;;
        *)
            print_error "Unknown test type: $test_type"
            show_usage
            exit 1
            ;;
    esac
}

cleanup_resources() {
    print_info "Cleaning up any remaining resources..."

    # Clean up any test clusters
    for cluster in $(kind get clusters 2>/dev/null | grep -E "e2e-test|test-cluster" || true); do
        print_info "Cleaning up cluster: $cluster"
        kind delete cluster --name "$cluster" || true
    done

    # Clean up any test containers
    docker ps -a --filter "label=io.x-k8s.kind.cluster" --format "{{.Names}}" | while read -r container; do
        if [[ "$container" =~ (e2e-test|test-cluster) ]]; then
            print_info "Cleaning up container: $container"
            docker rm -f "$container" || true
        fi
    done

    print_status "Cleanup completed"
}

show_test_results() {
    echo ""
    print_header
    print_info "Test execution completed!"

    # Show screenshots if any were taken
    if [ -d "tests/e2e/test_screenshots" ] && [ "$(ls -A tests/e2e/test_screenshots 2>/dev/null)" ]; then
        print_status "Screenshots captured:"
        ls -la tests/e2e/test_screenshots/ | tail -n +2
        echo ""
    fi

    # Show any cluster logs if debugging
    if [ -d "tests/e2e/cluster_logs" ] && [ "$(ls -A tests/e2e/cluster_logs 2>/dev/null)" ]; then
        print_info "Cluster logs available in: tests/e2e/cluster_logs/"
    fi

    # Show next steps
    print_info "Next steps:"
    echo "  - View screenshots in tests/e2e/test_screenshots/"
    echo "  - Check test results above for any failures"
    echo "  - Run with --headless false to see browser actions"
    echo "  - Use --no-cleanup to inspect cluster after tests"
    echo ""
}

main() {
    local test_type="$TEST_TYPE"
    local cluster_name="$CLUSTER_NAME"
    local headless="$HEADLESS"
    local cleanup="$CLEANUP"

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --test-type)
                test_type="$2"
                shift 2
                ;;
            --cluster-name)
                cluster_name="$2"
                shift 2
                ;;
            --headless)
                headless="$2"
                shift 2
                ;;
            --no-cleanup)
                cleanup="false"
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # Trap cleanup on exit
    trap cleanup_resources EXIT

    print_header
    check_prerequisites

    # Run the tests
    if run_tests "$test_type" "$cluster_name" "$headless" "$cleanup"; then
        print_status "All tests completed successfully!"
        exit_code=0
    else
        print_error "Some tests failed!"
        exit_code=1
    fi

    show_test_results
    exit $exit_code
}

# Only run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
