#!/bin/bash

# Cleanup script for the microservices framework

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CLUSTER_NAME="microservices-framework"

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

cleanup_cluster() {
    print_status "Cleaning up microservices framework..."

    if kind get clusters | grep -q "^$CLUSTER_NAME$"; then
        print_status "Deleting Kind cluster: $CLUSTER_NAME"
        kind delete cluster --name "$CLUSTER_NAME"
        print_success "Cluster deleted successfully"
    else
        print_warning "Cluster $CLUSTER_NAME does not exist"
    fi
}

cleanup_port_forwards() {
    print_status "Cleaning up port forwards..."

    # Kill any existing port forwards
    pkill -f "kubectl port-forward" || true

    print_success "Port forwards cleaned up"
}

cleanup_docker_images() {
    if [ "$1" = "--docker" ]; then
        print_status "Cleaning up Docker images..."

        # Remove unused Docker images
        docker image prune -f || true

        print_success "Docker images cleaned up"
    fi
}

main() {
    print_status "Starting cleanup process..."

    cleanup_port_forwards
    cleanup_cluster
    cleanup_docker_images "$1"

    print_success "Cleanup completed successfully!"
}

# Handle script arguments
case "${1:-}" in
    --docker)
        main --docker
        ;;
    --help)
        echo "Usage: $0 [options]"
        echo "Options:"
        echo "  --docker    Also clean up Docker images"
        echo "  --help      Show this help message"
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
