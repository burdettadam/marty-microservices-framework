#!/bin/bash
# Enhanced Petstore Kind Deployment Script
# Deploys the complete MMF stack locally using Kind

set -e

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

# Configuration
CLUSTER_NAME="petstore-demo"
NAMESPACE="petstore"
REGISTRY_PORT="5001"

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if Kind is installed
    if ! command -v kind &> /dev/null; then
        log_error "Kind is not installed. Please install Kind first: https://kind.sigs.k8s.io/docs/user/quick-start/"
        exit 1
    fi

    # Check if Docker is running
    if ! docker info &> /dev/null; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi

    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed. Please install kubectl first."
        exit 1
    fi

    log_success "All prerequisites are satisfied"
}

# Create Kind cluster with registry
create_cluster() {
    log_info "Creating Kind cluster with local registry..."

    # Create registry container unless it already exists
    if [ "$(docker inspect -f '{{.State.Running}}' "${CLUSTER_NAME}-registry" 2>/dev/null || true)" != 'true' ]; then
        docker run \
            -d --restart=always -p "127.0.0.1:${REGISTRY_PORT}:5000" --name "${CLUSTER_NAME}-registry" \
            registry:2
    fi

    # Create Kind cluster config
    cat <<EOF > kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ${CLUSTER_NAME}
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
  - containerPort: 8080
    hostPort: 8080
    protocol: TCP
  - containerPort: 3000
    hostPort: 3000
    protocol: TCP
  - containerPort: 9090
    hostPort: 9090
    protocol: TCP
  - containerPort: 16686
    hostPort: 16686
    protocol: TCP
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:${REGISTRY_PORT}"]
    endpoint = ["http://${CLUSTER_NAME}-registry:5000"]
EOF

    # Create cluster if it doesn't exist
    if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
        kind create cluster --config=kind-config.yaml
        log_success "Kind cluster created"
    else
        log_info "Kind cluster already exists"
    fi

    # Connect the registry to the cluster network if not already connected
    if [ "$(docker inspect -f='{{json .NetworkSettings.Networks.kind}}' "${CLUSTER_NAME}-registry")" = 'null' ]; then
        docker network connect "kind" "${CLUSTER_NAME}-registry"
    fi

    # Document the local registry
    kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REGISTRY_PORT}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

    rm kind-config.yaml
    log_success "Local registry connected to cluster"
}

# Build and push Docker images
build_and_push_images() {
    log_info "Building and pushing Docker images..."

    # Build petstore domain image
    log_info "Building petstore domain image..."
    docker build -t localhost:${REGISTRY_PORT}/petstore-domain:latest .
    docker push localhost:${REGISTRY_PORT}/petstore-domain:latest

    log_success "Images built and pushed to local registry"
}

# Install monitoring stack
install_monitoring() {
    log_info "Installing monitoring stack..."

    # Install Prometheus
    kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: prometheus
        image: prom/prometheus:latest
        ports:
        - containerPort: 9090
        volumeMounts:
        - name: config
          mountPath: /etc/prometheus
        command:
        - /bin/prometheus
        - --config.file=/etc/prometheus/prometheus.yml
        - --storage.tsdb.path=/prometheus
        - --web.console.libraries=/etc/prometheus/console_libraries
        - --web.console.templates=/etc/prometheus/consoles
        - --web.enable-lifecycle
      volumes:
      - name: config
        configMap:
          name: prometheus-config
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
  namespace: monitoring
spec:
  selector:
    app: prometheus
  ports:
  - port: 9090
    targetPort: 9090
    nodePort: 30090
  type: NodePort
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: monitoring
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
    scrape_configs:
    - job_name: 'petstore-domain'
      kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
          - petstore
      relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: keep
        regex: petstore-domain
      - source_labels: [__meta_kubernetes_pod_ip]
        target_label: __address__
        replacement: \${1}:8080
EOF

    # Install Grafana
    kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      containers:
      - name: grafana
        image: grafana/grafana:latest
        ports:
        - containerPort: 3000
        env:
        - name: GF_SECURITY_ADMIN_PASSWORD
          value: admin
---
apiVersion: v1
kind: Service
metadata:
  name: grafana
  namespace: monitoring
spec:
  selector:
    app: grafana
  ports:
  - port: 3000
    targetPort: 3000
    nodePort: 30030
  type: NodePort
EOF

    # Install Jaeger
    kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jaeger
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: jaeger
  template:
    metadata:
      labels:
        app: jaeger
    spec:
      containers:
      - name: jaeger
        image: jaegertracing/all-in-one:latest
        ports:
        - containerPort: 16686
        - containerPort: 14268
        env:
        - name: COLLECTOR_ZIPKIN_HOST_PORT
          value: ":9411"
---
apiVersion: v1
kind: Service
metadata:
  name: jaeger
  namespace: monitoring
spec:
  selector:
    app: jaeger
  ports:
  - name: ui
    port: 16686
    targetPort: 16686
    nodePort: 30686
  - name: collector
    port: 14268
    targetPort: 14268
  type: NodePort
EOF

    log_success "Monitoring stack installed"
}

# Install Kafka
install_kafka() {
    log_info "Installing Kafka..."

    # Install Zookeeper
    kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: zookeeper
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: zookeeper
  template:
    metadata:
      labels:
        app: zookeeper
    spec:
      containers:
      - name: zookeeper
        image: confluentinc/cp-zookeeper:latest
        ports:
        - containerPort: 2181
        env:
        - name: ZOOKEEPER_CLIENT_PORT
          value: "2181"
        - name: ZOOKEEPER_TICK_TIME
          value: "2000"
---
apiVersion: v1
kind: Service
metadata:
  name: zookeeper
  namespace: ${NAMESPACE}
spec:
  selector:
    app: zookeeper
  ports:
  - port: 2181
    targetPort: 2181
EOF

    # Install Kafka
    kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kafka
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: kafka
  template:
    metadata:
      labels:
        app: kafka
    spec:
      containers:
      - name: kafka
        image: confluentinc/cp-kafka:latest
        ports:
        - containerPort: 9092
        env:
        - name: KAFKA_BROKER_ID
          value: "1"
        - name: KAFKA_ZOOKEEPER_CONNECT
          value: "zookeeper:2181"
        - name: KAFKA_ADVERTISED_LISTENERS
          value: "PLAINTEXT://kafka:9092"
        - name: KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR
          value: "1"
        - name: KAFKA_AUTO_CREATE_TOPICS_ENABLE
          value: "true"
---
apiVersion: v1
kind: Service
metadata:
  name: kafka
  namespace: ${NAMESPACE}
spec:
  selector:
    app: kafka
  ports:
  - port: 9092
    targetPort: 9092
EOF

    log_success "Kafka installed"
}

# Install Redis
install_redis() {
    log_info "Installing Redis..."

    # Create namespace first
    kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

    kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        command:
        - redis-server
        - --appendonly
        - "yes"
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: ${NAMESPACE}
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
EOF

    log_success "Redis installed"
}

# Install PostgreSQL
install_postgres() {
    log_info "Installing PostgreSQL..."

    kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: petstore
        - name: POSTGRES_USER
          value: petstore_user
        - name: POSTGRES_PASSWORD
          value: demo_password
        volumeMounts:
        - name: init-sql
          mountPath: /docker-entrypoint-initdb.d
      volumes:
      - name: init-sql
        configMap:
          name: postgres-init
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: ${NAMESPACE}
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
EOF

    # Create init SQL ConfigMap
    kubectl create configmap postgres-init --from-file=init.sql=db/init.sql -n ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

    log_success "PostgreSQL installed"
}

# Deploy petstore application
deploy_petstore() {
    log_info "Deploying petstore application..."

    # Create enhanced configuration ConfigMap
    kubectl create configmap petstore-config \
        --from-file=config/enhanced_config.yaml \
        -n ${NAMESPACE} \
        --dry-run=client -o yaml | kubectl apply -f -

    # Deploy petstore domain
    kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: petstore-domain
  namespace: ${NAMESPACE}
  labels:
    app: petstore-domain
spec:
  replicas: 2
  selector:
    matchLabels:
      app: petstore-domain
  template:
    metadata:
      labels:
        app: petstore-domain
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: petstore-domain
        image: localhost:${REGISTRY_PORT}/petstore-domain:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8080
          name: http
        env:
        - name: CONFIG_FILE
          value: /app/config/enhanced_config.yaml
        - name: KAFKA_BROKERS
          value: kafka:9092
        - name: REDIS_URL
          value: redis://redis:6379
        - name: DATABASE_URL
          value: postgresql://petstore_user:demo_password@postgres:5432/petstore
        - name: JAEGER_ENDPOINT
          value: http://jaeger.monitoring:14268/api/traces
        - name: PROMETHEUS_GATEWAY
          value: http://prometheus.monitoring:9090
        volumeMounts:
        - name: config
          mountPath: /app/config
        livenessProbe:
          httpGet:
            path: /petstore-domain/health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /petstore-domain/health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: config
        configMap:
          name: petstore-config
---
apiVersion: v1
kind: Service
metadata:
  name: petstore-domain
  namespace: ${NAMESPACE}
  labels:
    app: petstore-domain
spec:
  selector:
    app: petstore-domain
  ports:
  - port: 8080
    targetPort: 8080
    nodePort: 30080
    name: http
  type: NodePort
EOF

    log_success "Petstore application deployed"
}

# Wait for deployments to be ready
wait_for_deployments() {
    log_info "Waiting for deployments to be ready..."

    # Wait for infrastructure
    kubectl wait --for=condition=available --timeout=300s deployment/redis -n ${NAMESPACE}
    kubectl wait --for=condition=available --timeout=300s deployment/postgres -n ${NAMESPACE}
    kubectl wait --for=condition=available --timeout=300s deployment/kafka -n ${NAMESPACE}

    # Wait for monitoring
    kubectl wait --for=condition=available --timeout=300s deployment/prometheus -n monitoring
    kubectl wait --for=condition=available --timeout=300s deployment/grafana -n monitoring
    kubectl wait --for=condition=available --timeout=300s deployment/jaeger -n monitoring

    # Wait for petstore
    kubectl wait --for=condition=available --timeout=300s deployment/petstore-domain -n ${NAMESPACE}

    log_success "All deployments are ready"
}

# Show access information
show_access_info() {
    echo
    log_info "=== Access Information ==="
    echo
    echo "🌐 Petstore API:         http://localhost:30080/petstore-domain"
    echo "📊 Grafana Dashboard:    http://localhost:30030 (admin/admin)"
    echo "📈 Prometheus:           http://localhost:30090"
    echo "🔍 Jaeger Tracing:       http://localhost:30686"
    echo
    echo "🔧 Kubectl Commands:"
    echo "  kubectl get pods -n ${NAMESPACE}"
    echo "  kubectl logs -f deployment/petstore-domain -n ${NAMESPACE}"
    echo "  kubectl port-forward svc/petstore-domain 8080:8080 -n ${NAMESPACE}"
    echo
    echo "🧪 Test the API:"
    echo "  curl http://localhost:30080/petstore-domain/health"
    echo "  curl http://localhost:30080/petstore-domain/pets/browse"
    echo
}

# Clean up function
cleanup() {
    log_info "Cleaning up resources..."
    kind delete cluster --name ${CLUSTER_NAME}
    docker rm -f ${CLUSTER_NAME}-registry 2>/dev/null || true
    log_success "Cleanup completed"
}

# Main deployment function
main() {
    case "${1:-deploy}" in
        "deploy")
            check_prerequisites
            create_cluster
            build_and_push_images

            # Create namespace first
            kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
            kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

            install_redis
            install_postgres
            install_kafka
            install_monitoring
            deploy_petstore
            wait_for_deployments
            show_access_info
            ;;
        "cleanup")
            cleanup
            ;;
        "status")
            kubectl get all -n ${NAMESPACE}
            kubectl get all -n monitoring
            ;;
        *)
            echo "Usage: $0 [deploy|cleanup|status]"
            echo "  deploy  - Deploy the complete petstore stack"
            echo "  cleanup - Clean up the Kind cluster"
            echo "  status  - Show deployment status"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
