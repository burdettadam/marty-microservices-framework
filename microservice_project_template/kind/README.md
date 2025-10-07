# KinD Environment

This directory contains the configuration needed to spin up a disposable Kubernetes cluster for local development.

## Usage

```bash
make kind-up    # create cluster, deploy app + observability
make kind-down  # delete cluster
```

The `cluster-config.yaml` provisions one control-plane node and two workers so you can test scheduling and rollout strategies. Port mappings expose NodePorts `30000` and `32000` if you choose to publish services during local testing.
