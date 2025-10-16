# Petstore Domain Service Mesh Integration

This document provides comprehensive guidance on using the service mesh integration with the Petstore Domain plugin in the Marty Microservices Framework (MMF).

## Overview

The Petstore Domain plugin demonstrates how to integrate service mesh capabilities into MMF services, providing:

- **Circuit breakers** for resilience and fault tolerance
- **Automatic retries** for improved reliability
- **mTLS encryption** for zero-trust security
- **Rate limiting** for protection against overload
- **Fault injection** for chaos engineering and testing
- **Comprehensive monitoring** with metrics, alerts, and dashboards
- **Traffic management** with canary deployments and A/B testing

## Service Mesh Support

The integration supports both **Istio** and **Linkerd** service meshes:

### Istio Integration
- Uses VirtualService and DestinationRule for traffic management
- Implements EnvoyFilter for rate limiting
- Provides PeerAuthentication and AuthorizationPolicy for security
- Supports fault injection with delay and abort configurations

### Linkerd Integration
- Uses ServiceProfile for retry and circuit breaker configuration
- Implements SMI specs (TrafficSplit, HTTPRouteGroup, TrafficTarget)
- Provides Server and ServerAuthorization for security policies
- Includes NetworkPolicy for additional network security

## Quick Start

### Prerequisites

1. **Kubernetes cluster** with kubectl access
2. **Service mesh installed** (Istio or Linkerd)
3. **MMF CLI** with service mesh commands available

### Installation

1. **Install the service mesh** (if not already installed):

   For Istio:
   ```bash
   curl -L https://istio.io/downloadIstio | sh -
   istioctl install --set values.defaultRevision=default
   ```

   For Linkerd:
   ```bash
   curl -sL https://run.linkerd.io/install | sh
   linkerd install | kubectl apply -f -
   linkerd viz install | kubectl apply -f -
   ```

2. **Deploy with MMF CLI**:
   ```bash
   # Generate and apply Istio overlay
   marty service-mesh generate-overlay --service petstore-domain --mesh istio --output ./overlays/istio
   kubectl apply -k ./overlays/istio

   # Or generate and apply Linkerd overlay
   marty service-mesh generate-overlay --service petstore-domain --mesh linkerd --output ./overlays/linkerd
   kubectl apply -k ./overlays/linkerd
   ```

3. **Run the demo**:
   ```bash
   cd plugins/petstore_domain/k8s/service-mesh/
   ./demo.sh istio  # or ./demo.sh linkerd
   ```

## Configuration Guide

### Directory Structure

```
plugins/petstore_domain/k8s/
├── kustomization.yaml                    # Base Kustomize configuration
├── overlays/
│   ├── service-mesh-istio/              # Istio-specific overlay
│   │   ├── kustomization.yaml           # Istio overlay configuration
│   │   ├── namespace.yaml               # Namespace with Istio injection
│   │   └── deployment-patch.yaml        # Istio deployment patches
│   └── service-mesh-linkerd/            # Linkerd-specific overlay
│       ├── kustomization.yaml           # Linkerd overlay configuration
│       ├── namespace.yaml               # Namespace with Linkerd injection
│       └── deployment-patch.yaml        # Linkerd deployment patches
└── service-mesh/
    ├── istio-policies.yaml              # Istio policies and configurations
    ├── linkerd-policies.yaml            # Linkerd policies and configurations
    ├── monitoring.yaml                  # Monitoring and observability
    ├── demo.sh                          # Interactive demonstration script
    └── README.md                        # This documentation
```

### Customizing Service Mesh Policies

#### Circuit Breaker Configuration

**Istio - DestinationRule:**
```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: petstore-domain-circuit-breaker
spec:
  host: petstore-domain-service.petstore-domain.svc.cluster.local
  trafficPolicy:
    outlierDetection:
      consecutiveGatewayErrors: 3      # Trigger after 3 errors
      consecutive5xxErrors: 5          # Or 5 server errors
      interval: 30s                    # Check every 30 seconds
      baseEjectionTime: 30s            # Eject for 30 seconds
      maxEjectionPercent: 50           # Maximum 50% of endpoints
```

**Linkerd - ServiceProfile:**
```yaml
apiVersion: linkerd.io/v1alpha2
kind: ServiceProfile
metadata:
  name: petstore-domain-service.petstore-domain.svc.cluster.local
spec:
  routes:
  - name: api
    retryBudget:
      retryRatio: 0.2                  # Retry 20% of requests
      minRetriesPerSecond: 5           # Minimum 5 retries per second
      ttl: 10s                         # TTL for retry budget
```

#### Rate Limiting Configuration

**Istio - EnvoyFilter:**
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: petstore-domain-rate-limit
spec:
  configPatches:
  - patch:
      value:
        typed_config:
          value:
            token_bucket:
              max_tokens: 200          # Maximum 200 tokens
              tokens_per_fill: 100     # Refill 100 tokens
              fill_interval: 60s       # Every 60 seconds
```

**Linkerd - Uses external rate limiting or application-level controls**

#### Security Configuration

**mTLS Enforcement (Istio):**
```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: petstore-domain-mtls
spec:
  mtls:
    mode: STRICT                       # Enforce strict mTLS
```

**mTLS Enforcement (Linkerd):**
```yaml
apiVersion: policy.linkerd.io/v1beta1
kind: ServerAuthorization
metadata:
  name: petstore-domain-server-authz
spec:
  requiredAuthentication:
    policy: required                   # Require mTLS authentication
```

### Monitoring and Observability

#### Metrics Collection

The configuration includes:

- **ServiceMonitor** for Prometheus scraping
- **Custom dashboards** for Grafana
- **Alerting rules** for critical conditions
- **Distributed tracing** integration

#### Key Metrics

- **Request rate**: `istio_request_total` (Istio) / `request_total` (Linkerd)
- **Error rate**: `istio_request_total{response_code=~"5.*"}`
- **Latency**: `istio_request_duration_milliseconds`
- **Circuit breaker status**: `envoy_cluster_circuit_breakers_default_cx_open`

#### Alerts

Configured alerts include:
- High error rate (>5% for 2 minutes)
- High latency (P99 >1000ms for 5 minutes)
- Circuit breaker open
- Low success rate (<95% for 5 minutes)

## Testing and Validation

### Automated Testing

Use the provided demo script for comprehensive testing:

```bash
# Interactive testing
./demo.sh istio interactive

# Automated testing
./demo.sh linkerd automated
```

### Manual Testing

1. **Circuit Breaker Testing**:
   ```bash
   # Generate load to trigger circuit breaker
   kubectl run load-test --image=busybox --rm -i --restart=Never -- \
     sh -c "for i in \$(seq 1 100); do wget -q -O- --timeout=1 http://petstore-domain-service.petstore-domain:8080/api/petstore-domain/pets; done"
   ```

2. **Fault Injection Testing** (Istio):
   ```bash
   # Test with chaos headers
   kubectl run test-client --image=curlimages/curl --rm -i --restart=Never -- \
     curl -H "x-chaos-enabled: true" http://petstore-domain-service.petstore-domain:8080/api/petstore-domain/pets
   ```

3. **Security Testing**:
   ```bash
   # Verify mTLS is enforced
   kubectl exec -it test-pod -- curl http://petstore-domain-service.petstore-domain:8080/health
   ```

### Verification Commands

```bash
# Check service mesh injection
kubectl get pods -n petstore-domain -o jsonpath='{.items[*].spec.containers[*].name}'

# Verify policies are applied
kubectl get destinationrules,virtualservices -n petstore-domain  # Istio
kubectl get serviceprofiles,trafficsplits -n petstore-domain     # Linkerd

# Check monitoring
kubectl get servicemonitor,prometheusrule -n petstore-domain
```

## Troubleshooting

### Common Issues

1. **Service mesh not injecting sidecars**:
   - Verify namespace labels: `istio-injection=enabled` or `linkerd.io/inject=enabled`
   - Check service mesh control plane status

2. **Policies not taking effect**:
   - Verify policy syntax and labels
   - Check service mesh configuration

3. **Monitoring not working**:
   - Verify ServiceMonitor selector matches service labels
   - Check Prometheus configuration

### Debug Commands

```bash
# Check Istio configuration
istioctl proxy-config cluster petstore-domain-pod-name -n petstore-domain
istioctl analyze -n petstore-domain

# Check Linkerd configuration
linkerd check --proxy -n petstore-domain
linkerd viz stat -n petstore-domain

# Check logs
kubectl logs -n petstore-domain deployment/petstore-domain -c istio-proxy  # Istio
kubectl logs -n petstore-domain deployment/petstore-domain -c linkerd-proxy  # Linkerd
```

## Advanced Configuration

### Canary Deployments

**Istio TrafficSplit:**
```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: petstore-domain-canary
spec:
  http:
  - match:
    - headers:
        canary:
          exact: "true"
    route:
    - destination:
        host: petstore-domain-service
        subset: v2
      weight: 100
  - route:
    - destination:
        host: petstore-domain-service
        subset: v1
      weight: 90
    - destination:
        host: petstore-domain-service
        subset: v2
      weight: 10
```

**Linkerd TrafficSplit:**
```yaml
apiVersion: split.smi-spec.io/v1alpha1
kind: TrafficSplit
metadata:
  name: petstore-domain-canary
spec:
  service: petstore-domain-service
  backends:
  - service: petstore-domain-service-v1
    weight: 90
  - service: petstore-domain-service-v2
    weight: 10
```

### Multi-Cluster Configuration

For multi-cluster deployments, refer to the main service mesh documentation in `ops/service-mesh/`.

## Integration with MMF CLI

The MMF CLI provides commands for service mesh management:

```bash
# Generate service mesh overlays
marty service-mesh generate-overlay --service petstore-domain --mesh istio

# Apply policies
marty service-mesh apply-policies --service petstore-domain --mesh istio

# Validate configuration
marty service-mesh validate --service petstore-domain

# Get status
marty service-mesh status --service petstore-domain
```

## Best Practices

1. **Start with permissive mode** and gradually tighten security
2. **Monitor circuit breaker metrics** to tune thresholds
3. **Test fault injection** in non-production environments first
4. **Use namespace isolation** for different environments
5. **Regular security audits** of mTLS and authorization policies
6. **Implement gradual rollouts** for policy changes
7. **Monitor resource usage** of service mesh sidecars

## Contributing

To extend or modify the service mesh integration:

1. Update policies in `istio-policies.yaml` or `linkerd-policies.yaml`
2. Modify overlays in the respective directories
3. Update monitoring configurations as needed
4. Test with the demo script
5. Update this documentation

## Support

For issues or questions:
- Check the troubleshooting section above
- Review MMF documentation in `docs/`
- File issues in the MMF repository
- Refer to Istio/Linkerd official documentation

---

This integration demonstrates the power of service mesh with MMF, providing enterprise-grade reliability, security, and observability for microservices.
