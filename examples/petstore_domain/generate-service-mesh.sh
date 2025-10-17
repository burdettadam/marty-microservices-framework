#!/bin/bash
# Example: Generate Petstore Service Mesh Deployment
# This demonstrates how the framework generates deployment scripts

# Example project configuration
PROJECT_NAME="petstore"
PROJECT_DOMAIN="api.petstore.com"
OUTPUT_DIR="/tmp/petstore-service-mesh-example"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Source the framework library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_LIB_PATH="$SCRIPT_DIR/../src/marty_msf/framework/service_mesh/service_mesh_lib.sh"

if [[ -f "$FRAMEWORK_LIB_PATH" ]]; then
    source "$FRAMEWORK_LIB_PATH"
else
    echo "ERROR: Framework library not found at $FRAMEWORK_LIB_PATH"
    exit 1
fi

echo "=== Generating Petstore Service Mesh Deployment ==="
echo "Project: $PROJECT_NAME"
echo "Domain: $PROJECT_DOMAIN"
echo "Output: $OUTPUT_DIR"
echo

# Generate deployment script and plugin template
msf_generate_deployment_script "$PROJECT_NAME" "$OUTPUT_DIR" "$PROJECT_DOMAIN"
msf_generate_plugin_template "$OUTPUT_DIR"

echo
echo "=== Generated Files ==="
find "$OUTPUT_DIR" -type f -exec ls -la {} \;

echo
echo "=== Generated Deployment Script Preview ==="
head -50 "$OUTPUT_DIR/deploy-service-mesh.sh"

echo
echo "=== Generated Plugin Template Preview ==="
head -30 "$OUTPUT_DIR/plugins/service-mesh-extensions.sh"

echo
echo "=== Usage ==="
echo "1. Copy the generated files to your petstore project"
echo "2. Customize plugins/service-mesh-extensions.sh for your specific needs"
echo "3. Add your K8s manifests to k8s/service-mesh/"
echo "4. Run: ./deploy-service-mesh.sh"
echo
echo "Generated files are in: $OUTPUT_DIR"
