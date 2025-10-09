"""
Metrics collection service for gathering system and service metrics.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import AsyncSessionLocal, Service, ServiceMetrics

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Service for collecting and storing metrics from services."""

    def __init__(self):
        self.settings = get_settings()
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.http_client: Optional[httpx.AsyncClient] = None

    async def start(self):
        """Start the metrics collection service."""
        if self.running:
            return

        self.running = True
        self.http_client = httpx.AsyncClient(timeout=10.0)

        # Start collection task
        self.task = asyncio.create_task(self._collection_loop())
        logger.info("Metrics collection service started")

    async def stop(self):
        """Stop the metrics collection service."""
        if not self.running:
            return

        self.running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        if self.http_client:
            await self.http_client.aclose()

        logger.info("Metrics collection service stopped")

    async def collect_service_metrics(self, service_name: str) -> Dict:
        """Collect metrics from a specific service."""
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Service).where(Service.name == service_name)
                result = await session.execute(stmt)
                service = result.scalar_one_or_none()

                if not service:
                    return {}

                metrics_url = f"http://{service.address}:{service.port}/metrics"

                try:
                    if self.http_client:
                        response = await self.http_client.get(metrics_url)
                        if response.status_code == 200:
                            # Parse Prometheus metrics format
                            metrics = self._parse_prometheus_metrics(response.text)

                            # Store metrics in database
                            await self._store_metrics(service_name, metrics)

                            return metrics

                except Exception as exc:
                    logger.error(
                        f"Failed to collect metrics from {service_name}: {exc}"
                    )

        except Exception as exc:
            logger.error(f"Failed to get service info for {service_name}: {exc}")

        return {}

    async def get_service_metrics(
        self, service_name: str, metric_name: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """Get stored metrics for a service."""
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(ServiceMetrics).where(
                    ServiceMetrics.service_name == service_name
                )

                if metric_name:
                    stmt = stmt.where(ServiceMetrics.metric_name == metric_name)

                stmt = stmt.order_by(ServiceMetrics.timestamp.desc()).limit(limit)

                result = await session.execute(stmt)
                metrics = result.scalars().all()

                return [
                    {
                        "service_name": metric.service_name,
                        "metric_name": metric.metric_name,
                        "metric_value": metric.metric_value,
                        "metric_type": metric.metric_type,
                        "labels": metric.labels,
                        "timestamp": metric.timestamp.isoformat(),
                    }
                    for metric in metrics
                ]

        except Exception as exc:
            logger.error(f"Failed to get metrics for {service_name}: {exc}")
            return []

    async def _collection_loop(self):
        """Main metrics collection loop."""
        while self.running:
            try:
                await self._collect_all_metrics()
                await asyncio.sleep(self.settings.metrics_collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in metrics collection loop: {exc}")
                await asyncio.sleep(5)

    async def _collect_all_metrics(self):
        """Collect metrics from all registered services."""
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Service)
                result = await session.execute(stmt)
                services = result.scalars().all()

                for service in services:
                    try:
                        await self.collect_service_metrics(str(service.name))
                    except Exception as exc:
                        logger.error(
                            f"Failed to collect metrics from {service.name}: {exc}"
                        )

        except Exception as exc:
            logger.error(f"Failed to get services for metrics collection: {exc}")

    def _parse_prometheus_metrics(self, metrics_text: str) -> Dict:
        """Parse Prometheus metrics format."""
        metrics = {}

        for line in metrics_text.split("\n"):
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            try:
                # Simple parsing - split by space
                parts = line.split(" ")
                if len(parts) >= 2:
                    metric_name_with_labels = parts[0]
                    metric_value = parts[1]

                    # Extract metric name and labels
                    if "{" in metric_name_with_labels:
                        metric_name = metric_name_with_labels.split("{")[0]
                        labels_part = metric_name_with_labels.split("{")[1].rstrip("}")
                        labels = self._parse_labels(labels_part)
                    else:
                        metric_name = metric_name_with_labels
                        labels = {}

                    if metric_name not in metrics:
                        metrics[metric_name] = []

                    metrics[metric_name].append(
                        {
                            "value": metric_value,
                            "labels": labels,
                        }
                    )

            except Exception as exc:
                logger.debug(f"Failed to parse metric line '{line}': {exc}")

        return metrics

    def _parse_labels(self, labels_text: str) -> Dict:
        """Parse Prometheus labels format."""
        labels = {}

        # Simple label parsing
        for label_pair in labels_text.split(","):
            label_pair = label_pair.strip()
            if "=" in label_pair:
                key, value = label_pair.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"')
                labels[key] = value

        return labels

    async def _store_metrics(self, service_name: str, metrics: Dict):
        """Store metrics in database."""
        try:
            async with AsyncSessionLocal() as session:
                for metric_name, metric_values in metrics.items():
                    for metric_data in metric_values:
                        db_metric = ServiceMetrics(
                            service_name=service_name,
                            metric_name=metric_name,
                            metric_value=metric_data["value"],
                            metric_type="gauge",  # Default type
                            labels=metric_data["labels"],
                            timestamp=datetime.utcnow(),
                        )
                        session.add(db_metric)

                await session.commit()

        except Exception as exc:
            logger.error(f"Failed to store metrics for {service_name}: {exc}")
