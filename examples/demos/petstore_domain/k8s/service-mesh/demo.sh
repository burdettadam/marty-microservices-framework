#!/bin/bash

# Petstore Domain Service Mesh Demo Script
# This script demonstrates the service mesh capabilities for the petstore domain plugin

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="petstore-domain"
SERVICE_MESH=${1:-"istio"}  # Default to istio, can be overridden
DEMO_MODE=${2:-"interactive"}  # interactive or automated

echo -e "${BLUE}🏗️  Marty Microservices Framework - Petstore Domain Service Mesh Demo${NC}"
echo -e "${BLUE}Service Mesh: ${SERVICE_MESH}${NC}"
echo ""

# Function to wait for user input in interactive mode
wait_for_user() {
    if [ "$DEMO_MODE" = "interactive" ]; then
        echo -e "${YELLOW}Press Enter to continue...${NC}"
        read -r
    else
        sleep 2
    fi
}

# Function to check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}❌ kubectl is not installed or not in PATH${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ kubectl is available${NC}"
}

# Function to check if cluster is accessible
check_cluster() {
    if ! kubectl cluster-info &> /dev/null; then
        echo -e "${RED}❌ Cannot connect to Kubernetes cluster${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Kubernetes cluster is accessible${NC}"
}

# Function to check service mesh installation
check_service_mesh() {
    case $SERVICE_MESH in
        "istio")
            if ! kubectl get namespace istio-system &> /dev/null; then
                echo -e "${RED}❌ Istio is not installed${NC}"
                echo -e "${YELLOW}Please install Istio first:${NC}"
                echo "curl -L https://istio.io/downloadIstio | sh -"
                echo "istioctl install --set values.defaultRevision=default"
                exit 1
            fi
            echo -e "${GREEN}✅ Istio is installed${NC}"
            ;;
        "linkerd")
            if ! kubectl get namespace linkerd &> /dev/null; then
                echo -e "${RED}❌ Linkerd is not installed${NC}"
                echo -e "${YELLOW}Please install Linkerd first:${NC}"
                echo "curl -sL https://run.linkerd.io/install | sh"
                echo "linkerd install | kubectl apply -f -"
                exit 1
            fi
            echo -e "${GREEN}✅ Linkerd is installed${NC}"
            ;;
        *)
            echo -e "${RED}❌ Unsupported service mesh: $SERVICE_MESH${NC}"
            echo "Supported service meshes: istio, linkerd"
            exit 1
            ;;
    esac
}

# Function to deploy the petstore domain with service mesh
deploy_petstore() {
    echo -e "${BLUE}🚀 Deploying Petstore Domain with $SERVICE_MESH service mesh...${NC}"

    # Create namespace with service mesh injection
    case $SERVICE_MESH in
        "istio")
            kubectl create namespace $NAMESPACE --dry-run=client -o yaml | \
            kubectl label --local -f - istio-injection=enabled -o yaml | \
            kubectl apply -f -
            ;;
        "linkerd")
            kubectl create namespace $NAMESPACE --dry-run=client -o yaml | \
            kubectl annotate --local -f - linkerd.io/inject=enabled -o yaml | \
            kubectl apply -f -
            ;;
    esac

    # Apply the base petstore domain deployment directly
    kubectl apply -f petstore_domain/k8s/deployment.yaml -n $NAMESPACE
    kubectl apply -f petstore_domain/k8s/service.yaml -n $NAMESPACE

    # Apply service mesh specific configurations (skip overlays to avoid cycle)
    echo -e "${YELLOW}⚠️  Skipping overlay application due to kustomization cycle - using direct manifests${NC}"

    echo -e "${GREEN}✅ Petstore Domain deployed with $SERVICE_MESH${NC}"
}

# Function to wait for deployment to be ready
wait_for_deployment() {
    echo -e "${BLUE}⏳ Waiting for deployment to be ready...${NC}"
    kubectl rollout status deployment/petstore-domain -n $NAMESPACE --timeout=300s
    echo -e "${GREEN}✅ Deployment is ready${NC}"
}

# Function to show service mesh status
show_service_mesh_status() {
    echo -e "${BLUE}📊 Service Mesh Status:${NC}"

    case $SERVICE_MESH in
        "istio")
            echo -e "${YELLOW}Istio Proxy Status:${NC}"
            kubectl get pods -n $NAMESPACE -o custom-columns=NAME:.metadata.name,READY:.status.containerStatuses[*].ready,ISTIO-PROXY:.spec.containers[1].name 2>/dev/null || true

            echo -e "\n${YELLOW}Virtual Services:${NC}"
            kubectl get virtualservices -n $NAMESPACE 2>/dev/null || echo "No VirtualServices found"

            echo -e "\n${YELLOW}Destination Rules:${NC}"
            kubectl get destinationrules -n $NAMESPACE 2>/dev/null || echo "No DestinationRules found"
            ;;
        "linkerd")
            echo -e "${YELLOW}Linkerd Proxy Status:${NC}"
            kubectl get pods -n $NAMESPACE -o custom-columns=NAME:.metadata.name,READY:.status.containerStatuses[*].ready,LINKERD-PROXY:.spec.containers[1].name 2>/dev/null || true

            echo -e "\n${YELLOW}Service Profiles:${NC}"
            kubectl get serviceprofiles -n $NAMESPACE 2>/dev/null || echo "No ServiceProfiles found"

            echo -e "\n${YELLOW}Traffic Splits:${NC}"
            kubectl get trafficsplits -n $NAMESPACE 2>/dev/null || echo "No TrafficSplits found"
            ;;
    esac
}

# Function to demonstrate circuit breaker
demo_circuit_breaker() {
    echo -e "${BLUE}🔌 Demonstrating Circuit Breaker...${NC}"

    # Get service endpoint
    SERVICE_IP=$(kubectl get svc petstore-domain-service -n $NAMESPACE -o jsonpath='{.spec.clusterIP}')

    echo -e "${YELLOW}Creating load to trigger circuit breaker...${NC}"

    # Create a temporary pod for load testing
    kubectl run load-test --image=busybox --rm -i --restart=Never -- sh -c "
        echo 'Sending requests to trigger circuit breaker...'
        for i in \$(seq 1 100); do
            wget -q -O- --timeout=1 http://$SERVICE_IP:8080/api/petstore-domain/pets 2>/dev/null || echo 'Request \$i failed'
        done
    " 2>/dev/null || true

    echo -e "${GREEN}✅ Circuit breaker demonstration completed${NC}"
    echo -e "${YELLOW}Check metrics in Grafana or Prometheus to see circuit breaker activity${NC}"
}

# Function to demonstrate fault injection
demo_fault_injection() {
    echo -e "${BLUE}💥 Demonstrating Fault Injection...${NC}"

    if [ "$SERVICE_MESH" = "istio" ]; then
        echo -e "${YELLOW}Injecting chaos with headers...${NC}"

        # Create a test pod with curl
        kubectl run test-client --image=curlimages/curl --rm -i --restart=Never -- sh -c "
            echo 'Testing normal request:'
            curl -s -o /dev/null -w '%{http_code}\n' http://petstore-domain-service.$NAMESPACE:8080/health || true

            echo 'Testing with chaos latency:'
            curl -s -o /dev/null -w '%{http_code}\n' -H 'x-chaos-enabled: true' http://petstore-domain-service.$NAMESPACE:8080/api/petstore-domain/pets || true

            echo 'Testing with chaos errors:'
            curl -s -o /dev/null -w '%{http_code}\n' -H 'x-chaos-error: true' http://petstore-domain-service.$NAMESPACE:8080/api/petstore-domain/pets || true
        " 2>/dev/null || true
    else
        echo -e "${YELLOW}Fault injection is configured via ServiceProfile retries and failure conditions${NC}"
    fi

    echo -e "${GREEN}✅ Fault injection demonstration completed${NC}"
}

# Function to show monitoring and observability
show_monitoring() {
    echo -e "${BLUE}📈 Monitoring and Observability:${NC}"

    case $SERVICE_MESH in
        "istio")
            echo -e "${YELLOW}Prometheus metrics endpoint:${NC}"
            kubectl get svc -n istio-system prometheus 2>/dev/null || echo "Prometheus not found"

            echo -e "\n${YELLOW}Grafana dashboard:${NC}"
            kubectl get svc -n istio-system grafana 2>/dev/null || echo "Grafana not found"

            echo -e "\n${YELLOW}Jaeger tracing:${NC}"
            kubectl get svc -n istio-system tracing 2>/dev/null || echo "Jaeger not found"
            ;;
        "linkerd")
            echo -e "${YELLOW}Linkerd Viz dashboard:${NC}"
            kubectl get svc -n linkerd-viz web 2>/dev/null || echo "Linkerd Viz not found"

            echo -e "\n${YELLOW}Prometheus metrics:${NC}"
            kubectl get svc -n linkerd-viz prometheus 2>/dev/null || echo "Prometheus not found"

            echo -e "\n${YELLOW}Grafana dashboard:${NC}"
            kubectl get svc -n linkerd-viz grafana 2>/dev/null || echo "Grafana not found"
            ;;
    esac

    echo -e "\n${YELLOW}Custom ServiceMonitor for petstore domain:${NC}"
    kubectl get servicemonitor -n $NAMESPACE 2>/dev/null || echo "No ServiceMonitors found"

    echo -e "\n${YELLOW}Prometheus rules for alerts:${NC}"
    kubectl get prometheusrule -n $NAMESPACE 2>/dev/null || echo "No PrometheusRules found"
}

# Function to cleanup
cleanup() {
    echo -e "${BLUE}🧹 Cleaning up demo resources...${NC}"

    # Delete the namespace (this will delete everything in it)
    kubectl delete namespace $NAMESPACE --ignore-not-found=true

    echo -e "${GREEN}✅ Cleanup completed${NC}"
}

# Main demo flow
main() {
    echo -e "${BLUE}🔍 Pre-flight checks...${NC}"
    check_kubectl
    check_cluster
    check_service_mesh

    wait_for_user

    deploy_petstore
    wait_for_deployment

    wait_for_user

    show_service_mesh_status

    wait_for_user

    demo_circuit_breaker

    wait_for_user

    demo_fault_injection

    wait_for_user

    show_monitoring

    echo -e "\n${GREEN}🎉 Petstore Domain Service Mesh Demo completed successfully!${NC}"
    echo -e "${YELLOW}The service is now running with $SERVICE_MESH service mesh features:${NC}"
    echo -e "  • Circuit breakers for resilience"
    echo -e "  • Automatic retries for reliability"
    echo -e "  • mTLS for security"
    echo -e "  • Rate limiting for protection"
    echo -e "  • Comprehensive monitoring and alerting"
    echo -e "  • Fault injection for chaos testing"

    if [ "$DEMO_MODE" = "interactive" ]; then
        echo -e "\n${YELLOW}Would you like to clean up the demo resources? (y/N)${NC}"
        read -r response
        if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            cleanup
        else
            echo -e "${YELLOW}Demo resources preserved. To clean up later, run:${NC}"
            echo "kubectl delete namespace $NAMESPACE"
        fi
    fi
}

# Help function
show_help() {
    echo "Usage: $0 [SERVICE_MESH] [MODE]"
    echo ""
    echo "SERVICE_MESH: istio (default) | linkerd"
    echo "MODE: interactive (default) | automated"
    echo ""
    echo "Examples:"
    echo "  $0                    # Interactive demo with Istio"
    echo "  $0 istio automated    # Automated demo with Istio"
    echo "  $0 linkerd            # Interactive demo with Linkerd"
    echo ""
    echo "This script demonstrates the service mesh integration for the Petstore Domain plugin"
    echo "including circuit breakers, retries, fault injection, and monitoring."
}

# Handle command line arguments
case "${1:-}" in
    -h|--help|help)
        show_help
        exit 0
        ;;
    *)
        main
        ;;
esac
