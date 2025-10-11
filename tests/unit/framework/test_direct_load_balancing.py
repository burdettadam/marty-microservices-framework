"""Direct load balancing strategy tests - bypassing import issues."""

import asyncio
from unittest.mock import AsyncMock

import pytest


def test_direct_import_load_balancing():
    """Test direct import of load balancing without going through __init__.py"""
    try:
        from src.framework.discovery.load_balancing import (
            LoadBalancingStrategy,
            RoundRobinLoadBalancer,
            WeightedLoadBalancer,
        )
        assert LoadBalancingStrategy is not None
        assert RoundRobinLoadBalancer is not None
        assert WeightedLoadBalancer is not None
        print("Successfully imported load balancing classes directly")
    except Exception as e:
        pytest.fail(f"Could not import load balancing classes directly: {e}")


def test_direct_import_service_instance():
    """Test direct import of ServiceInstance"""
    try:
        from src.framework.discovery.core import ServiceInstance

        # Test basic instantiation
        instance = ServiceInstance(
            service_name="test-service",
            host="localhost",
            port=8080
        )
        assert instance.service_name == "test-service"
        assert instance.host == "localhost"
        assert instance.port == 8080
        print("Successfully created ServiceInstance directly")
    except Exception as e:
        pytest.fail(f"Could not import/create ServiceInstance directly: {e}")


@pytest.mark.asyncio
async def test_round_robin_basic_functionality():
    """Test basic round robin load balancing functionality."""
    try:
        from src.framework.discovery.core import ServiceInstance
        from src.framework.discovery.load_balancing import RoundRobinLoadBalancer

        # Create balancer
        balancer = RoundRobinLoadBalancer()

        # Create test service instances
        instances = [
            ServiceInstance(service_name="test-service", host="host1", port=8080),
            ServiceInstance(service_name="test-service", host="host2", port=8080),
            ServiceInstance(service_name="test-service", host="host3", port=8080),
        ]

        # Test selection
        selected1 = await balancer.select_instance(instances)
        selected2 = await balancer.select_instance(instances)
        selected3 = await balancer.select_instance(instances)
        selected4 = await balancer.select_instance(instances)  # Should wrap around

        # Verify round robin behavior
        assert selected1 is not None
        assert selected2 is not None
        assert selected3 is not None
        assert selected4 is not None

        # Should cycle through instances
        hosts = [selected1.host, selected2.host, selected3.host, selected4.host]
        assert "host1" in hosts
        assert "host2" in hosts
        assert "host3" in hosts

        print(f"Round robin selection order: {hosts}")

    except Exception as e:
        pytest.fail(f"Round robin test failed: {e}")


@pytest.mark.asyncio
async def test_weighted_basic_functionality():
    """Test basic weighted load balancing functionality."""
    try:
        from src.framework.discovery.core import ServiceInstance
        from src.framework.discovery.load_balancing import WeightedLoadBalancer

        # Create balancer
        balancer = WeightedLoadBalancer()

        # Create test service instances with weights
        instances = [
            ServiceInstance(service_name="test-service", host="host1", port=8080),
            ServiceInstance(service_name="test-service", host="host2", port=8080),
        ]

        # Set weights if supported (check if method exists)
        if hasattr(instances[0], 'weight'):
            instances[0].weight = 3
            instances[1].weight = 1

        # Test selection
        selected = await balancer.select_instance(instances)
        assert selected is not None
        assert selected.host in ["host1", "host2"]

        print(f"Weighted selection: {selected.host}")

    except Exception as e:
        pytest.fail(f"Weighted load balancer test failed: {e}")
