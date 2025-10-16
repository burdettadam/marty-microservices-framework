#!/bin/bash
# Enhanced Petstore Demo Script
# Demonstrates all MMF capabilities in action

set -e

echo "🚀 Enhanced Petstore Domain - MMF Capabilities Demo"
echo "=================================================="

# Configuration
BASE_URL="http://localhost:8080"
PETSTORE_API="$BASE_URL/petstore-domain"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if services are running
check_services() {
    log_info "Checking service health..."

    if curl -s "$PETSTORE_API/health" > /dev/null; then
        log_success "Petstore service is running"
    else
        log_error "Petstore service is not running. Please start with: docker-compose -f docker-compose.enhanced.yml up -d"
        exit 1
    fi

    # Check monitoring services
    local services=(
        "http://localhost:3000:Grafana"
        "http://localhost:9090:Prometheus"
        "http://localhost:16686:Jaeger"
        "http://localhost:8081:Kafka UI"
    )

    for service in "${services[@]}"; do
        IFS=':' read -r url name <<< "$service"
        if curl -s "$url" > /dev/null; then
            log_success "$name is running"
        else
            log_warning "$name is not accessible at $url"
        fi
    done
}

# Demo 1: Basic API functionality
demo_basic_api() {
    echo
    log_info "=== Demo 1: Basic API Functionality ==="

    log_info "Getting service health..."
    curl -s "$PETSTORE_API/health" | jq '.'

    log_info "Browsing pets..."
    curl -s "$PETSTORE_API/pets/browse?category=dog" | jq '.pets[0]'

    log_success "Basic API functionality verified"
}

# Demo 2: Event-driven saga workflow
demo_saga_workflow() {
    echo
    log_info "=== Demo 2: Event-Driven Saga Workflow ==="

    log_info "Creating order to trigger saga..."
    ORDER_RESPONSE=$(curl -s -X POST "$PETSTORE_API/orders" \
        -H "Content-Type: application/json" \
        -d '{
            "customer_id": "customer-001",
            "pet_id": "golden-retriever-001",
            "special_instructions": "Include training guide"
        }')

    echo "$ORDER_RESPONSE" | jq '.'

    ORDER_ID=$(echo "$ORDER_RESPONSE" | jq -r '.data.order.order_id')
    CORRELATION_ID=$(echo "$ORDER_RESPONSE" | jq -r '.correlation_id')

    log_info "Order created: $ORDER_ID (Correlation: $CORRELATION_ID)"

    log_info "Tracking order status..."
    curl -s "$PETSTORE_API/orders/$ORDER_ID/status" | jq '.data.workflow_steps'

    log_success "Saga workflow demonstrated"
}

# Demo 3: Observability features
demo_observability() {
    echo
    log_info "=== Demo 3: Observability Features ==="

    log_info "Generating correlated requests..."
    CORRELATION_ID="demo-$(date +%s)"

    for i in {1..5}; do
        curl -s -H "X-Correlation-ID: $CORRELATION_ID" \
            "$PETSTORE_API/pets/browse?category=cat" > /dev/null
        echo -n "."
    done
    echo

    log_info "Correlation ID used: $CORRELATION_ID"
    log_info "Check Jaeger traces at: http://localhost:16686"
    log_info "Check Grafana dashboards at: http://localhost:3000"

    log_success "Observability features demonstrated"
}

# Demo 4: Resilience patterns
demo_resilience() {
    echo
    log_info "=== Demo 4: Resilience Patterns ==="

    log_info "Testing circuit breaker behavior..."

    # Simulate high load to potentially trigger circuit breaker
    log_info "Generating load..."
    for i in {1..20}; do
        curl -s "$PETSTORE_API/pets/browse" > /dev/null &
    done
    wait

    log_info "Checking service status..."
    curl -s "$PETSTORE_API/status" | jq '.data.mmf_status'

    log_success "Resilience patterns demonstrated"
}

# Demo 5: Security features
demo_security() {
    echo
    log_info "=== Demo 5: Security Features ==="

    log_info "Testing rate limiting..."

    # Generate requests to test rate limiting
    for i in {1..10}; do
        RESPONSE=$(curl -s -w "%{http_code}" "$PETSTORE_API/pets/browse" -o /dev/null)
        if [ "$RESPONSE" != "200" ]; then
            log_warning "Rate limit triggered (HTTP $RESPONSE)"
            break
        fi
        echo -n "."
    done
    echo

    log_info "Testing authenticated endpoints..."
    curl -s "$PETSTORE_API/admin/config" | jq '.data.feature_flags // .message'

    log_success "Security features demonstrated"
}

# Demo 6: Feature flags and configuration
demo_feature_flags() {
    echo
    log_info "=== Demo 6: Feature Flags & Configuration ==="

    log_info "Current configuration..."
    curl -s "$PETSTORE_API/admin/config" | jq '.data.feature_flags'

    log_info "Testing feature-flag driven behavior..."

    # Test with personalization off
    curl -s "$PETSTORE_API/pets/browse" | jq 'has("personalized")'

    log_success "Feature flags and configuration demonstrated"
}

# Demo 7: Data integration
demo_data_integration() {
    echo
    log_info "=== Demo 7: Data Integration ==="

    log_info "Testing cached responses..."

    # First request (cache miss)
    time curl -s "$PETSTORE_API/pets/browse" > /dev/null

    # Second request (cache hit)
    time curl -s "$PETSTORE_API/pets/browse" > /dev/null

    log_info "Check Redis at: redis-cli -h localhost -p 6379 keys '*'"
    log_info "Check PostgreSQL at: psql -h localhost -p 5432 -U petstore_user -d petstore"

    log_success "Data integration demonstrated"
}

# Performance test
run_performance_test() {
    echo
    log_info "=== Performance Test ==="

    log_info "Running load test..."

    # Generate concurrent load
    for i in {1..50}; do
        curl -s "$PETSTORE_API/pets/browse" > /dev/null &
    done

    wait

    log_info "Check metrics at: http://localhost:9090/graph"
    log_info "Query: rate(petstore_requests_total[1m])"

    log_success "Performance test completed"
}

# Show monitoring URLs
show_monitoring_urls() {
    echo
    log_info "=== Monitoring & Observability URLs ==="
    echo
    echo "📊 Grafana Dashboard:    http://localhost:3000 (admin/admin)"
    echo "📈 Prometheus Metrics:   http://localhost:9090"
    echo "🔍 Jaeger Tracing:       http://localhost:16686"
    echo "📨 Kafka UI:             http://localhost:8081"
    echo "💾 Redis Insight:        redis-cli -h localhost -p 6379"
    echo "🗄️  PostgreSQL:           psql -h localhost -p 5432 -U petstore_user -d petstore"
    echo
    echo "🌐 API Documentation:    http://localhost:8080/docs"
    echo "📋 Service Health:       http://localhost:8080/petstore-domain/health"
    echo "⚙️  Admin Config:         http://localhost:8080/petstore-domain/admin/config"
}

# Main demo execution
main() {
    echo "Starting Enhanced Petstore MMF Demo..."
    echo

    check_services

    # Run demos based on arguments
    if [ $# -eq 0 ]; then
        # Run all demos
        demo_basic_api
        demo_saga_workflow
        demo_observability
        demo_resilience
        demo_security
        demo_feature_flags
        demo_data_integration
        run_performance_test
    else
        # Run specific demos
        for demo in "$@"; do
            case $demo in
                "basic")      demo_basic_api ;;
                "saga")       demo_saga_workflow ;;
                "observ")     demo_observability ;;
                "resilience") demo_resilience ;;
                "security")   demo_security ;;
                "flags")      demo_feature_flags ;;
                "data")       demo_data_integration ;;
                "perf")       run_performance_test ;;
                *)            log_error "Unknown demo: $demo" ;;
            esac
        done
    fi

    show_monitoring_urls

    echo
    log_success "🎉 Enhanced Petstore MMF Demo completed!"
    echo
    echo "Next steps:"
    echo "1. Explore the monitoring dashboards"
    echo "2. Check the correlation IDs in traces"
    echo "3. Review the database audit trails"
    echo "4. Test feature flag changes"
    echo "5. Examine the saga orchestration logs"
}

# Script usage
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    echo "Enhanced Petstore MMF Demo Script"
    echo
    echo "Usage: $0 [demo1] [demo2] ..."
    echo
    echo "Available demos:"
    echo "  basic      - Basic API functionality"
    echo "  saga       - Event-driven saga workflow"
    echo "  observ     - Observability features"
    echo "  resilience - Resilience patterns"
    echo "  security   - Security features"
    echo "  flags      - Feature flags & configuration"
    echo "  data       - Data integration"
    echo "  perf       - Performance test"
    echo
    echo "Examples:"
    echo "  $0                    # Run all demos"
    echo "  $0 basic saga         # Run specific demos"
    echo "  $0 observ perf        # Run observability and performance"
    echo
    exit 0
fi

# Run the main demo
main "$@"
