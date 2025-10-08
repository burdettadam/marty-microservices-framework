#!/bin/bash

# Validation script for the microservices framework
# Tests that all components are working correctly

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CLUSTER_NAME="microservices-framework"
FAILED_TESTS=0
TOTAL_TESTS=0

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

test_passed() {
    ((TOTAL_TESTS++))
    print_success "✓ $1"
}

test_failed() {
    ((TOTAL_TESTS++))
    ((FAILED_TESTS++))
    print_error "✗ $1"
}

check_cluster() {
    print_status "Checking Kind cluster..."

    if kind get clusters | grep -q "^$CLUSTER_NAME$"; then
        test_passed "Kind cluster '$CLUSTER_NAME' exists"
    else
        test_failed "Kind cluster '$CLUSTER_NAME' not found"
        return 1
    fi

    # Check cluster connectivity
    if kubectl cluster-info --context "kind-$CLUSTER_NAME" &>/dev/null; then
        test_passed "Cluster connectivity working"
    else
        test_failed "Cannot connect to cluster"
        return 1
    fi
}

check_namespaces() {
    print_status "Checking required namespaces..."

    local namespaces=("observability" "microservice-framework" "istio-system")

    for ns in "${namespaces[@]}"; do
        if kubectl get namespace "$ns" &>/dev/null; then
            test_passed "Namespace '$ns' exists"
        else
            test_failed "Namespace '$ns' not found"
        fi
    done
}

check_observability() {
    print_status "Checking observability stack..."

    # Check Prometheus
    if kubectl get deployment prometheus -n observability &>/dev/null; then
        if kubectl wait --for=condition=Available deployment/prometheus -n observability --timeout=30s &>/dev/null; then
            test_passed "Prometheus is running"
        else
            test_failed "Prometheus is not ready"
        fi
    else
        test_failed "Prometheus deployment not found"
    fi

    # Check Grafana
    if kubectl get deployment grafana -n observability &>/dev/null; then
        if kubectl wait --for=condition=Available deployment/grafana -n observability --timeout=30s &>/dev/null; then
            test_passed "Grafana is running"
        else
            test_failed "Grafana is not ready"
        fi
    else
        test_failed "Grafana deployment not found"
    fi

    # Check Kafka
    if kubectl get deployment kafka -n observability &>/dev/null; then
        if kubectl wait --for=condition=Available deployment/kafka -n observability --timeout=30s &>/dev/null; then
            test_passed "Kafka is running"
        else
            test_failed "Kafka is not ready"
        fi
    else
        test_failed "Kafka deployment not found"
    fi
}

check_service_mesh() {
    print_status "Checking service mesh..."

    # Check Istio
    if kubectl get namespace istio-system &>/dev/null; then
        if kubectl get deployment istiod -n istio-system &>/dev/null; then
            if kubectl wait --for=condition=Available deployment/istiod -n istio-system --timeout=30s &>/dev/null; then
                test_passed "Istio control plane is running"
            else
                test_failed "Istio control plane is not ready"
            fi
        else
            test_failed "Istio control plane not found"
        fi
    fi

    # Check Linkerd
    if kubectl get namespace linkerd &>/dev/null; then
        if kubectl get deployment linkerd-controller -n linkerd &>/dev/null; then
            if kubectl wait --for=condition=Available deployment/linkerd-controller -n linkerd --timeout=30s &>/dev/null; then
                test_passed "Linkerd control plane is running"
            else
                test_failed "Linkerd control plane is not ready"
            fi
        else
            test_failed "Linkerd control plane not found"
        fi
    fi
}

check_sample_services() {
    print_status "Checking sample services..."

    if kubectl get deployment sample-api -n microservice-framework &>/dev/null; then
        if kubectl wait --for=condition=Available deployment/sample-api -n microservice-framework --timeout=30s &>/dev/null; then
            test_passed "Sample API service is running"
        else
            test_failed "Sample API service is not ready"
        fi
    else
        test_failed "Sample API service not found"
    fi
}

check_metrics() {
    print_status "Checking metrics collection..."

    # Port forward Prometheus temporarily
    kubectl port-forward -n observability svc/prometheus 9090:9090 &
    local pf_pid=$!
    sleep 5

    # Check if Prometheus is collecting metrics
    if curl -s "http://localhost:9090/api/v1/query?query=up" | grep -q "success"; then
        test_passed "Prometheus metrics collection working"
    else
        test_failed "Prometheus metrics collection not working"
    fi

    # Kill the port forward
    kill $pf_pid 2>/dev/null || true
    wait $pf_pid 2>/dev/null || true
}

check_ingress() {
    print_status "Checking ingress controller..."

    if kubectl get namespace ingress-nginx &>/dev/null; then
        if kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=30s &>/dev/null; then
            test_passed "Ingress controller is running"
        else
            test_failed "Ingress controller is not ready"
        fi
    else
        test_failed "Ingress controller namespace not found"
    fi
}

run_connectivity_tests() {
    print_status "Running connectivity tests..."

    # Test internal service communication
    if kubectl run test-pod --image=curlimages/curl:latest --rm -i --restart=Never --command -- curl -s -o /dev/null -w "%{http_code}" http://sample-api.microservice-framework.svc.cluster.local &>/dev/null; then
        test_passed "Internal service communication working"
    else
        test_failed "Internal service communication failed"
    fi
}

display_results() {
    echo
    print_status "Validation Results:"
    echo "==================="
    echo "Total tests: $TOTAL_TESTS"
    echo "Passed: $((TOTAL_TESTS - FAILED_TESTS))"
    echo "Failed: $FAILED_TESTS"
    echo

    if [ $FAILED_TESTS -eq 0 ]; then
        print_success "All tests passed! 🎉"
        print_status "Your microservices framework is ready to use."
    else
        print_error "Some tests failed. Please check the output above."
        print_status "You may need to wait longer for components to start or check the logs."
        return 1
    fi
}

main() {
    print_status "Starting validation of microservices framework..."
    echo

    check_cluster || exit 1
    check_namespaces
    check_observability
    check_service_mesh
    check_sample_services
    check_ingress
    check_metrics
    run_connectivity_tests

    display_results
}

# Handle script arguments
case "${1:-}" in
    --help)
        echo "Usage: $0"
        echo "Validates that the microservices framework is working correctly."
        exit 0
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown option: $1"
        exit 1
        ;;
esac
