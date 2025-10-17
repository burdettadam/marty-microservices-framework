#!/bin/bash
set -euo pipefail

# Production Service Mesh Deployment Script
# Supports both Istio and Linkerd with enterprise features

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default configuration
MESH_TYPE="${MESH_TYPE:-istio}"
CLUSTER_NAME="${CLUSTER_NAME:-marty-primary}"
NETWORK_NAME="${NETWORK_NAME:-marty-network}"
ENABLE_MULTICLUSTER="${ENABLE_MULTICLUSTER:-false}"
ENABLE_OBSERVABILITY="${ENABLE_OBSERVABILITY:-true}"
NAMESPACE="${NAMESPACE:-microservice-framework}"
DRY_RUN="${DRY_RUN:-false}"

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

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

# Print usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy production-ready service mesh with enterprise features.

OPTIONS:
    -m, --mesh-type TYPE        Service mesh type: istio|linkerd (default: istio)
    -c, --cluster-name NAME     Cluster name for multi-cluster setup (default: marty-primary)
    -n, --network-name NAME     Network name for multi-cluster setup (default: marty-network)
    -N, --namespace NAME        Target namespace (default: microservice-framework)
    --enable-multicluster       Enable multi-cluster configuration
    --enable-observability      Enable observability integration (default: true)
    --dry-run                   Show what would be done without applying
    -h, --help                  Show this help message

EXAMPLES:
    # Deploy Istio with all features
    $0 --mesh-type istio --enable-multicluster --enable-observability

    # Deploy Linkerd in dry-run mode
    $0 --mesh-type linkerd --dry-run

    # Deploy to specific cluster and network
    $0 --cluster-name prod-west --network-name prod-network

ENVIRONMENT VARIABLES:
    KUBECONFIG              Path to kubeconfig file
    REMOTE_CLUSTER_ENDPOINT Remote cluster endpoint for multi-cluster
    REMOTE_CLUSTER_KUBECONFIG_BASE64 Base64 encoded remote cluster kubeconfig
EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -m|--mesh-type)
                MESH_TYPE="$2"
                shift 2
                ;;
            -c|--cluster-name)
                CLUSTER_NAME="$2"
                shift 2
                ;;
            -n|--network-name)
                NETWORK_NAME="$2"
                shift 2
                ;;
            -N|--namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            --enable-multicluster)
                ENABLE_MULTICLUSTER="true"
                shift
                ;;
            --enable-observability)
                ENABLE_OBSERVABILITY="true"
                shift
                ;;
            --dry-run)
                DRY_RUN="true"
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
}

# Validate prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi

    # Check cluster connectivity
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        log_info "Please check your KUBECONFIG and cluster connectivity"
        exit 1
    fi

    # Check mesh-specific tools
    case "$MESH_TYPE" in
        istio)
            if ! command -v istioctl &> /dev/null; then
                log_warning "istioctl not found, will attempt to install"
            fi
            ;;
        linkerd)
            if ! command -v linkerd &> /dev/null; then
                log_warning "linkerd CLI not found, will attempt to install"
            fi
            ;;
        *)
            log_error "Unsupported mesh type: $MESH_TYPE"
            log_info "Supported types: istio, linkerd"
            exit 1
            ;;
    esac

    # Validate multi-cluster settings
    if [[ "$ENABLE_MULTICLUSTER" == "true" ]]; then
        if [[ -z "${REMOTE_CLUSTER_ENDPOINT:-}" ]]; then
            log_warning "REMOTE_CLUSTER_ENDPOINT not set, multi-cluster features may not work"
        fi
        if [[ -z "${REMOTE_CLUSTER_KUBECONFIG_BASE64:-}" ]]; then
            log_warning "REMOTE_CLUSTER_KUBECONFIG_BASE64 not set, multi-cluster features may not work"
        fi
    fi

    log_success "Prerequisites check completed"
}

# Install mesh CLI tools
install_mesh_cli() {
    case "$MESH_TYPE" in
        istio)
            if ! command -v istioctl &> /dev/null; then
                log_info "Installing istioctl..."
                curl -L https://istio.io/downloadIstio | sh -
                export PATH="$PWD/istio-*/bin:$PATH"
            fi
            ;;
        linkerd)
            if ! command -v linkerd &> /dev/null; then
                log_info "Installing linkerd CLI..."
                curl -sL https://run.linkerd.io/install | sh
                export PATH=$HOME/.linkerd2/bin:$PATH
            fi
            ;;
    esac
}

# Apply Kubernetes manifests with optional dry-run
apply_manifest() {
    local manifest_file="$1"
    local description="$2"

    if [[ ! -f "$manifest_file" ]]; then
        log_error "Manifest file not found: $manifest_file"
        return 1
    fi

    log_info "Applying $description..."

    # Substitute environment variables
    local temp_file=$(mktemp)
    envsubst < "$manifest_file" > "$temp_file"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would apply $manifest_file"
        kubectl apply --dry-run=client -f "$temp_file"
    else
        kubectl apply -f "$temp_file"
    fi

    rm -f "$temp_file"
}

# Wait for deployment to be ready
wait_for_deployment() {
    local namespace="$1"
    local deployment="$2"
    local timeout="${3:-300s}"

    log_info "Waiting for deployment $deployment in namespace $namespace..."

    if [[ "$DRY_RUN" == "false" ]]; then
        kubectl wait --for=condition=Available \
            deployment/"$deployment" \
            -n "$namespace" \
            --timeout="$timeout"
    fi
}

# Deploy Istio service mesh
deploy_istio() {
    log_info "Deploying Istio service mesh..."

    # Install Istio control plane
    local production_config="$PROJECT_ROOT/ops/service-mesh/production/istio-production.yaml"
    apply_manifest "$production_config" "Istio production configuration"

    wait_for_deployment "istio-system" "istiod" "600s"

    # Apply security policies
    local security_config="$PROJECT_ROOT/ops/service-mesh/production/istio-security.yaml"
    apply_manifest "$security_config" "Istio security policies"

    # Apply traffic management
    local traffic_config="$PROJECT_ROOT/ops/service-mesh/production/istio-traffic-management.yaml"
    apply_manifest "$traffic_config" "Istio traffic management"

    # Apply gateway configuration
    local gateway_config="$PROJECT_ROOT/ops/service-mesh/production/istio-gateways.yaml"
    apply_manifest "$gateway_config" "Istio gateway configuration"

    # Multi-cluster configuration
    if [[ "$ENABLE_MULTICLUSTER" == "true" ]]; then
        local multicluster_config="$PROJECT_ROOT/ops/service-mesh/production/istio-cross-cluster.yaml"
        apply_manifest "$multicluster_config" "Istio multi-cluster configuration"
    fi

    log_success "Istio deployment completed"
}

# Deploy Linkerd service mesh
deploy_linkerd() {
    log_info "Deploying Linkerd service mesh..."

    # Check pre-installation requirements
    if [[ "$DRY_RUN" == "false" ]]; then
        linkerd check --pre
    fi

    # Install Linkerd CRDs and control plane
    if [[ "$DRY_RUN" == "false" ]]; then
        linkerd install --crds | kubectl apply -f -
        linkerd install | kubectl apply -f -
    else
        log_info "DRY RUN: Would install Linkerd CRDs and control plane"
    fi

    wait_for_deployment "linkerd" "linkerd-controller" "600s"

    # Apply production configuration
    local production_config="$PROJECT_ROOT/ops/service-mesh/production/linkerd-production.yaml"
    apply_manifest "$production_config" "Linkerd production configuration"

    # Apply security policies
    local security_config="$PROJECT_ROOT/ops/service-mesh/production/linkerd-security.yaml"
    apply_manifest "$security_config" "Linkerd security policies"

    # Apply traffic management
    local traffic_config="$PROJECT_ROOT/ops/service-mesh/production/linkerd-traffic-management.yaml"
    apply_manifest "$traffic_config" "Linkerd traffic management"

    # Install observability extension
    if [[ "$ENABLE_OBSERVABILITY" == "true" && "$DRY_RUN" == "false" ]]; then
        linkerd viz install | kubectl apply -f -
        wait_for_deployment "linkerd-viz" "web" "300s"

        # Install Jaeger extension
        linkerd jaeger install | kubectl apply -f -
        wait_for_deployment "linkerd-jaeger" "jaeger" "300s"
    fi

    log_success "Linkerd deployment completed"
}

# Enable namespace injection
enable_namespace_injection() {
    log_info "Enabling service mesh injection for namespace: $NAMESPACE"

    # Create namespace if it doesn't exist
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

    case "$MESH_TYPE" in
        istio)
            kubectl label namespace "$NAMESPACE" istio-injection=enabled --overwrite
            ;;
        linkerd)
            kubectl annotate namespace "$NAMESPACE" linkerd.io/inject=enabled --overwrite
            ;;
    esac

    log_success "Namespace injection enabled for $NAMESPACE"
}

# Verify deployment
verify_deployment() {
    log_info "Verifying service mesh deployment..."

    case "$MESH_TYPE" in
        istio)
            if [[ "$DRY_RUN" == "false" ]]; then
                istioctl verify-install
                istioctl proxy-status
            else
                log_info "DRY RUN: Would verify Istio installation"
            fi
            ;;
        linkerd)
            if [[ "$DRY_RUN" == "false" ]]; then
                linkerd check
                linkerd check --proxy
            else
                log_info "DRY RUN: Would verify Linkerd installation"
            fi
            ;;
    esac

    log_success "Service mesh verification completed"
}

# Generate deployment summary
generate_summary() {
    log_info "Generating deployment summary..."

    cat << EOF

========================================
SERVICE MESH DEPLOYMENT SUMMARY
========================================

Mesh Type:           $MESH_TYPE
Cluster Name:        $CLUSTER_NAME
Network Name:        $NETWORK_NAME
Target Namespace:    $NAMESPACE
Multi-cluster:       $ENABLE_MULTICLUSTER
Observability:       $ENABLE_OBSERVABILITY
Dry Run:            $DRY_RUN

Features Deployed:
✓ Production control plane
✓ Comprehensive security policies (mTLS, authorization)
✓ Advanced traffic management (circuit breakers, retries, rate limiting)
✓ Gateway configuration (ingress/egress)
$([ "$ENABLE_MULTICLUSTER" == "true" ] && echo "✓ Multi-cluster communication")
$([ "$ENABLE_OBSERVABILITY" == "true" ] && echo "✓ Observability integration")

Next Steps:
1. Deploy your applications to the '$NAMESPACE' namespace
2. Verify sidecar injection: kubectl get pods -n $NAMESPACE
3. Test mTLS: kubectl exec -n $NAMESPACE <pod> -- curl -k https://<service>
4. Monitor traffic: Access observability dashboards
$([ "$MESH_TYPE" == "istio" ] && echo "5. Istio dashboard: istioctl dashboard kiali")
$([ "$MESH_TYPE" == "linkerd" ] && echo "5. Linkerd dashboard: linkerd viz dashboard")

Documentation: $PROJECT_ROOT/docs/service-mesh/

EOF

    log_success "Deployment summary generated"
}

# Main execution
main() {
    log_info "Starting production service mesh deployment..."
    log_info "Mesh Type: $MESH_TYPE | Cluster: $CLUSTER_NAME | Namespace: $NAMESPACE"

    parse_args "$@"
    check_prerequisites
    install_mesh_cli

    # Deploy the selected service mesh
    case "$MESH_TYPE" in
        istio)
            deploy_istio
            ;;
        linkerd)
            deploy_linkerd
            ;;
    esac

    enable_namespace_injection
    verify_deployment
    generate_summary

    log_success "Service mesh deployment completed successfully!"
}

# Handle script interruption
trap 'log_error "Script interrupted"; exit 1' INT TERM

# Execute main function with all arguments
main "$@"
