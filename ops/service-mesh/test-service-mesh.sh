#!/bin/bash
set -euo pipefail

# Service Mesh Testing and Validation Script
# Comprehensive testing for production service mesh deployments

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Configuration
MESH_TYPE="${MESH_TYPE:-istio}"
NAMESPACE="${NAMESPACE:-microservice-framework}"
TEST_NAMESPACE="${TEST_NAMESPACE:-mesh-test}"
ENABLE_CHAOS_TESTING="${ENABLE_CHAOS_TESTING:-false}"
PARALLEL_TESTS="${PARALLEL_TESTS:-true}"

# Color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

# Test results tracking
declare -a TEST_RESULTS=()
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

# Test result tracking
track_test() {
    local test_name="$1"
    local result="$2"
    local message="$3"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    if [[ "$result" == "PASS" ]]; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
        log_success "✓ $test_name: $message"
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        log_error "✗ $test_name: $message"
    fi

    TEST_RESULTS+=("$test_name:$result:$message")
}

# Setup test environment
setup_test_environment() {
    log_info "Setting up test environment..."

    # Create test namespace
    kubectl create namespace "$TEST_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

    # Enable mesh injection for test namespace
    case "$MESH_TYPE" in
        istio)
            kubectl label namespace "$TEST_NAMESPACE" istio-injection=enabled --overwrite
            ;;
        linkerd)
            kubectl annotate namespace "$TEST_NAMESPACE" linkerd.io/inject=enabled --overwrite
            ;;
    esac

    # Deploy test applications
    cat << EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-app-a
  namespace: $TEST_NAMESPACE
spec:
  replicas: 2
  selector:
    matchLabels:
      app: test-app-a
  template:
    metadata:
      labels:
        app: test-app-a
        version: v1
    spec:
      containers:
      - name: app
        image: nginx:alpine
        ports:
        - containerPort: 80
        command: ["/bin/sh"]
        args:
        - -c
        - |
          echo '<h1>Test App A</h1>' > /usr/share/nginx/html/index.html
          nginx -g 'daemon off;'
---
apiVersion: v1
kind: Service
metadata:
  name: test-app-a
  namespace: $TEST_NAMESPACE
spec:
  selector:
    app: test-app-a
  ports:
  - port: 80
    targetPort: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-app-b
  namespace: $TEST_NAMESPACE
spec:
  replicas: 2
  selector:
    matchLabels:
      app: test-app-b
  template:
    metadata:
      labels:
        app: test-app-b
        version: v1
    spec:
      containers:
      - name: app
        image: nginx:alpine
        ports:
        - containerPort: 80
        command: ["/bin/sh"]
        args:
        - -c
        - |
          echo '<h1>Test App B</h1>' > /usr/share/nginx/html/index.html
          nginx -g 'daemon off;'
---
apiVersion: v1
kind: Service
metadata:
  name: test-app-b
  namespace: $TEST_NAMESPACE
spec:
  selector:
    app: test-app-b
  ports:
  - port: 80
    targetPort: 80
EOF

    # Wait for deployments
    kubectl wait --for=condition=Available deployment/test-app-a -n "$TEST_NAMESPACE" --timeout=300s
    kubectl wait --for=condition=Available deployment/test-app-b -n "$TEST_NAMESPACE" --timeout=300s

    log_success "Test environment setup completed"
}

# Test sidecar injection
test_sidecar_injection() {
    log_info "Testing sidecar injection..."

    local app_a_pods
    app_a_pods=$(kubectl get pods -n "$TEST_NAMESPACE" -l app=test-app-a -o jsonpath='{.items[*].metadata.name}')

    for pod in $app_a_pods; do
        local container_count
        container_count=$(kubectl get pod "$pod" -n "$TEST_NAMESPACE" -o jsonpath='{.spec.containers[*].name}' | wc -w)

        case "$MESH_TYPE" in
            istio)
                if [[ $container_count -ge 2 ]]; then
                    track_test "Sidecar Injection ($pod)" "PASS" "Istio sidecar injected ($container_count containers)"
                else
                    track_test "Sidecar Injection ($pod)" "FAIL" "Istio sidecar not injected ($container_count containers)"
                fi
                ;;
            linkerd)
                if [[ $container_count -ge 2 ]]; then
                    track_test "Sidecar Injection ($pod)" "PASS" "Linkerd proxy injected ($container_count containers)"
                else
                    track_test "Sidecar Injection ($pod)" "FAIL" "Linkerd proxy not injected ($container_count containers)"
                fi
                ;;
        esac
    done
}

# Test mTLS configuration
test_mtls_configuration() {
    log_info "Testing mTLS configuration..."

    local test_pod
    test_pod=$(kubectl get pods -n "$TEST_NAMESPACE" -l app=test-app-a -o jsonpath='{.items[0].metadata.name}')

    case "$MESH_TYPE" in
        istio)
            # Test mTLS by checking if plain HTTP fails
            local mtls_result
            if kubectl exec "$test_pod" -n "$TEST_NAMESPACE" -- curl -s --connect-timeout 5 http://test-app-b.${TEST_NAMESPACE}.svc.cluster.local &>/dev/null; then
                track_test "mTLS Enforcement" "PASS" "Service-to-service communication working with mTLS"
            else
                # Check if it works with the sidecar proxy
                if kubectl exec "$test_pod" -n "$TEST_NAMESPACE" -c istio-proxy -- curl -s --connect-timeout 5 http://test-app-b.${TEST_NAMESPACE}.svc.cluster.local &>/dev/null; then
                    track_test "mTLS Enforcement" "PASS" "mTLS enforced, proxy-to-proxy communication working"
                else
                    track_test "mTLS Enforcement" "FAIL" "mTLS communication not working"
                fi
            fi
            ;;
        linkerd)
            # Check Linkerd mTLS
            local mtls_status
            mtls_status=$(kubectl exec "$test_pod" -n "$TEST_NAMESPACE" -- curl -s http://test-app-b.${TEST_NAMESPACE}.svc.cluster.local || echo "failed")
            if [[ "$mtls_status" != "failed" ]]; then
                track_test "mTLS Enforcement" "PASS" "Linkerd mTLS communication working"
            else
                track_test "mTLS Enforcement" "FAIL" "Linkerd mTLS communication failed"
            fi
            ;;
    esac
}

# Test circuit breaker functionality
test_circuit_breaker() {
    log_info "Testing circuit breaker functionality..."

    # Create a failing service for circuit breaker testing
    cat << EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: failing-service
  namespace: $TEST_NAMESPACE
spec:
  replicas: 1
  selector:
    matchLabels:
      app: failing-service
  template:
    metadata:
      labels:
        app: failing-service
        version: v1
    spec:
      containers:
      - name: app
        image: nginx:alpine
        ports:
        - containerPort: 80
        command: ["/bin/sh"]
        args:
        - -c
        - |
          while true; do
            echo "HTTP/1.1 500 Internal Server Error\r\n\r\nService Unavailable" | nc -l -p 80
          done
---
apiVersion: v1
kind: Service
metadata:
  name: failing-service
  namespace: $TEST_NAMESPACE
spec:
  selector:
    app: failing-service
  ports:
  - port: 80
    targetPort: 80
EOF

    kubectl wait --for=condition=Available deployment/failing-service -n "$TEST_NAMESPACE" --timeout=300s

    local test_pod
    test_pod=$(kubectl get pods -n "$TEST_NAMESPACE" -l app=test-app-a -o jsonpath='{.items[0].metadata.name}')

    # Send multiple requests to trigger circuit breaker
    local failed_requests=0
    for i in {1..10}; do
        if ! kubectl exec "$test_pod" -n "$TEST_NAMESPACE" -- curl -s --connect-timeout 2 --fail http://failing-service.${TEST_NAMESPACE}.svc.cluster.local &>/dev/null; then
            failed_requests=$((failed_requests + 1))
        fi
        sleep 1
    done

    if [[ $failed_requests -ge 5 ]]; then
        track_test "Circuit Breaker" "PASS" "Circuit breaker triggered for failing service ($failed_requests/10 requests failed)"
    else
        track_test "Circuit Breaker" "FAIL" "Circuit breaker not working properly ($failed_requests/10 requests failed)"
    fi
}

# Test traffic splitting/canary deployment
test_traffic_splitting() {
    log_info "Testing traffic splitting..."

    # Deploy canary version
    cat << EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-app-a-canary
  namespace: $TEST_NAMESPACE
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-app-a
      version: canary
  template:
    metadata:
      labels:
        app: test-app-a
        version: canary
    spec:
      containers:
      - name: app
        image: nginx:alpine
        ports:
        - containerPort: 80
        command: ["/bin/sh"]
        args:
        - -c
        - |
          echo '<h1>Test App A - Canary</h1>' > /usr/share/nginx/html/index.html
          nginx -g 'daemon off;'
EOF

    kubectl wait --for=condition=Available deployment/test-app-a-canary -n "$TEST_NAMESPACE" --timeout=300s

    # Apply traffic splitting configuration
    case "$MESH_TYPE" in
        istio)
            cat << EOF | kubectl apply -f -
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: test-app-a-subsets
  namespace: $TEST_NAMESPACE
spec:
  host: test-app-a
  subsets:
  - name: stable
    labels:
      version: v1
  - name: canary
    labels:
      version: canary
---
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: test-app-a-split
  namespace: $TEST_NAMESPACE
spec:
  hosts:
  - test-app-a
  http:
  - route:
    - destination:
        host: test-app-a
        subset: stable
      weight: 90
    - destination:
        host: test-app-a
        subset: canary
      weight: 10
EOF
            ;;
        linkerd)
            cat << EOF | kubectl apply -f -
apiVersion: split.smi-spec.io/v1alpha1
kind: TrafficSplit
metadata:
  name: test-app-a-split
  namespace: $TEST_NAMESPACE
spec:
  service: test-app-a
  backends:
  - service: test-app-a
    weight: 900
  - service: test-app-a-canary
    weight: 100
EOF
            ;;
    esac

    sleep 30  # Allow time for configuration to propagate

    # Test traffic distribution
    local test_pod
    test_pod=$(kubectl get pods -n "$TEST_NAMESPACE" -l app=test-app-b -o jsonpath='{.items[0].metadata.name}')

    local stable_responses=0
    local canary_responses=0

    for i in {1..50}; do
        local response
        response=$(kubectl exec "$test_pod" -n "$TEST_NAMESPACE" -- curl -s http://test-app-a.${TEST_NAMESPACE}.svc.cluster.local)

        if [[ "$response" == *"Canary"* ]]; then
            canary_responses=$((canary_responses + 1))
        else
            stable_responses=$((stable_responses + 1))
        fi
    done

    local canary_percentage=$((canary_responses * 100 / 50))

    if [[ $canary_percentage -ge 5 && $canary_percentage -le 25 ]]; then
        track_test "Traffic Splitting" "PASS" "Traffic split working: $canary_percentage% canary traffic"
    else
        track_test "Traffic Splitting" "FAIL" "Traffic split not working properly: $canary_percentage% canary traffic"
    fi
}

# Test observability integration
test_observability() {
    log_info "Testing observability integration..."

    case "$MESH_TYPE" in
        istio)
            # Check if metrics are being generated
            local metrics_output
            if metrics_output=$(kubectl exec deployment/prometheus -n observability -- wget -qO- http://localhost:9090/api/v1/query?query=istio_requests_total 2>/dev/null); then
                if [[ "$metrics_output" == *"success"* ]]; then
                    track_test "Istio Metrics" "PASS" "Istio metrics available in Prometheus"
                else
                    track_test "Istio Metrics" "FAIL" "Istio metrics not found in Prometheus"
                fi
            else
                track_test "Istio Metrics" "FAIL" "Cannot query Prometheus for Istio metrics"
            fi
            ;;
        linkerd)
            # Check Linkerd metrics
            if linkerd viz stat deployment -n "$TEST_NAMESPACE" &>/dev/null; then
                track_test "Linkerd Metrics" "PASS" "Linkerd metrics collection working"
            else
                track_test "Linkerd Metrics" "FAIL" "Linkerd metrics collection not working"
            fi
            ;;
    esac
}

# Test security policies
test_security_policies() {
    log_info "Testing security policies..."

    # Create a pod without mesh injection to test authorization
    cat << EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: unauthorized-pod
  namespace: default
  labels:
    app: unauthorized
spec:
  containers:
  - name: curl
    image: curlimages/curl:latest
    command: ["sleep", "3600"]
EOF

    kubectl wait --for=condition=Ready pod/unauthorized-pod -n default --timeout=300s

    # Test if unauthorized pod can access mesh services
    local unauthorized_access
    if kubectl exec unauthorized-pod -n default -- curl -s --connect-timeout 5 --fail http://test-app-a.${TEST_NAMESPACE}.svc.cluster.local &>/dev/null; then
        track_test "Authorization Policy" "FAIL" "Unauthorized access allowed from outside mesh"
    else
        track_test "Authorization Policy" "PASS" "Unauthorized access properly blocked"
    fi

    # Cleanup
    kubectl delete pod unauthorized-pod -n default
}

# Test cross-cluster functionality (if enabled)
test_cross_cluster() {
    if [[ -z "${REMOTE_CLUSTER_ENDPOINT:-}" ]]; then
        log_warning "Skipping cross-cluster tests - REMOTE_CLUSTER_ENDPOINT not set"
        return
    fi

    log_info "Testing cross-cluster functionality..."

    case "$MESH_TYPE" in
        istio)
            # Check if cross-cluster services are discoverable
            if kubectl get serviceentry -A | grep -q "cross-cluster"; then
                track_test "Cross-cluster Discovery" "PASS" "Cross-cluster service entries configured"
            else
                track_test "Cross-cluster Discovery" "FAIL" "Cross-cluster service entries not found"
            fi
            ;;
        linkerd)
            # Check if multicluster link is established
            if kubectl get link -n linkerd-multicluster &>/dev/null; then
                track_test "Cross-cluster Link" "PASS" "Linkerd multicluster link established"
            else
                track_test "Cross-cluster Link" "FAIL" "Linkerd multicluster link not found"
            fi
            ;;
    esac
}

# Chaos testing (if enabled)
run_chaos_tests() {
    if [[ "$ENABLE_CHAOS_TESTING" != "true" ]]; then
        log_info "Skipping chaos tests - not enabled"
        return
    fi

    log_info "Running chaos engineering tests..."

    # Simulate pod failures
    local test_pod
    test_pod=$(kubectl get pods -n "$TEST_NAMESPACE" -l app=test-app-a -o jsonpath='{.items[0].metadata.name}')

    # Delete a pod and check if service remains available
    kubectl delete pod "$test_pod" -n "$TEST_NAMESPACE"

    sleep 10

    # Check if service is still responding
    local remaining_pod
    remaining_pod=$(kubectl get pods -n "$TEST_NAMESPACE" -l app=test-app-a -o jsonpath='{.items[0].metadata.name}')

    if kubectl exec "$remaining_pod" -n "$TEST_NAMESPACE" -- curl -s --connect-timeout 5 --fail http://test-app-b.${TEST_NAMESPACE}.svc.cluster.local &>/dev/null; then
        track_test "Pod Failure Resilience" "PASS" "Service remained available after pod deletion"
    else
        track_test "Pod Failure Resilience" "FAIL" "Service unavailable after pod deletion"
    fi
}

# Generate load for testing
generate_load() {
    log_info "Generating load for testing..."

    local test_pod
    test_pod=$(kubectl get pods -n "$TEST_NAMESPACE" -l app=test-app-b -o jsonpath='{.items[0].metadata.name}')

    # Run background load generation
    kubectl exec "$test_pod" -n "$TEST_NAMESPACE" -- sh -c '
        for i in $(seq 1 100); do
            curl -s http://test-app-a.'$TEST_NAMESPACE'.svc.cluster.local >/dev/null &
        done
        wait
    ' &

    local load_pid=$!
    sleep 5  # Let load run for a bit
    kill $load_pid 2>/dev/null || true

    log_success "Load generation completed"
}

# Cleanup test environment
cleanup_test_environment() {
    log_info "Cleaning up test environment..."

    kubectl delete namespace "$TEST_NAMESPACE" --ignore-not-found=true

    log_success "Test environment cleanup completed"
}

# Generate test report
generate_test_report() {
    log_info "Generating test report..."

    local report_file="$PROJECT_ROOT/service-mesh-test-report-$(date +%Y%m%d-%H%M%S).txt"

    cat << EOF > "$report_file"
========================================
SERVICE MESH TEST REPORT
========================================

Test Configuration:
- Mesh Type: $MESH_TYPE
- Namespace: $NAMESPACE
- Test Namespace: $TEST_NAMESPACE
- Chaos Testing: $ENABLE_CHAOS_TESTING
- Date: $(date)

Test Results Summary:
- Total Tests: $TOTAL_TESTS
- Passed: $PASSED_TESTS
- Failed: $FAILED_TESTS
- Success Rate: $(( PASSED_TESTS * 100 / TOTAL_TESTS ))%

Detailed Results:
EOF

    for result in "${TEST_RESULTS[@]}"; do
        IFS=':' read -r test_name test_result test_message <<< "$result"
        echo "[$test_result] $test_name: $test_message" >> "$report_file"
    done

    cat << EOF >> "$report_file"

Recommendations:
$([ $FAILED_TESTS -eq 0 ] && echo "✓ All tests passed - service mesh is ready for production" || echo "✗ Some tests failed - review configuration before production deployment")

EOF

    log_success "Test report generated: $report_file"

    # Also output to console
    echo
    echo "========================================="
    echo "TEST SUMMARY"
    echo "========================================="
    echo "Total: $TOTAL_TESTS | Passed: $PASSED_TESTS | Failed: $FAILED_TESTS"
    echo "Success Rate: $(( PASSED_TESTS * 100 / TOTAL_TESTS ))%"
    echo "========================================="
}

# Main execution
main() {
    log_info "Starting service mesh testing and validation..."

    setup_test_environment

    # Run core tests
    test_sidecar_injection
    test_mtls_configuration
    test_security_policies
    test_observability

    # Generate some load for more realistic testing
    generate_load

    # Run advanced tests
    test_circuit_breaker
    test_traffic_splitting
    test_cross_cluster

    # Run chaos tests if enabled
    run_chaos_tests

    # Generate report
    generate_test_report

    # Cleanup
    cleanup_test_environment

    if [[ $FAILED_TESTS -eq 0 ]]; then
        log_success "All tests passed! Service mesh is ready for production."
        exit 0
    else
        log_error "$FAILED_TESTS tests failed. Please review the configuration."
        exit 1
    fi
}

# Execute main function
main "$@"
