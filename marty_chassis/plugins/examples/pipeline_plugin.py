"""
Data Processing Pipeline Plugin Example.

This plugin demonstrates a data processing pipeline with stages,
timers, error handling, and detailed observability.
"""

import asyncio
import random
import time
from enum import Enum
from typing import Any

from ..decorators import plugin
from ..interfaces import IServicePlugin, PluginContext, PluginMetadata


class ProcessingStage(str, Enum):
    """Data processing pipeline stages."""

    INGESTION = "ingestion"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    ENRICHMENT = "enrichment"
    STORAGE = "storage"


class ProcessingStatus(str, Enum):
    """Processing status values."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@plugin(
    name="data-processing-pipeline",
    version="1.0.0",
    description="Data processing pipeline with stages, timers, and observability",
    author="Marty Team",
    provides=["data-processing", "pipeline", "etl"],
)
class DataProcessingPipelinePlugin(IServicePlugin):
    """
    Data processing pipeline plugin for demonstration.

    This plugin demonstrates:
    - Multi-stage data processing pipeline
    - Stage-specific timers and error rates
    - Retry logic with exponential backoff
    - Detailed observability and metrics
    - Batch and real-time processing modes
    """

    def __init__(self):
        super().__init__()

        # Configuration
        self.batch_size = 10
        self.max_retries = 3
        self.retry_delay_base = 1.0  # Base delay for exponential backoff
        self.processing_enabled = True

        # Stage configurations (stage -> {duration_range, error_rate})
        self.stage_configs = {
            ProcessingStage.INGESTION: {
                "duration_range": [0.1, 0.5],
                "error_rate": 0.05,
            },
            ProcessingStage.VALIDATION: {
                "duration_range": [0.2, 0.8],
                "error_rate": 0.10,
            },
            ProcessingStage.TRANSFORMATION: {
                "duration_range": [0.5, 2.0],
                "error_rate": 0.08,
            },
            ProcessingStage.ENRICHMENT: {
                "duration_range": [0.3, 1.5],
                "error_rate": 0.12,
            },
            ProcessingStage.STORAGE: {"duration_range": [0.2, 1.0], "error_rate": 0.06},
        }

        # Metrics
        self.pipeline_metrics = {
            "total_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "stage_metrics": {
                stage.value: {
                    "processed": 0,
                    "failed": 0,
                    "total_duration": 0.0,
                    "retry_count": 0,
                }
                for stage in ProcessingStage
            },
        }

        # Active jobs tracking
        self.active_jobs: dict[str, dict[str, Any]] = {}

        # Background processor task
        self._processor_task: asyncio.Task | None = None
        self._job_queue: asyncio.Queue = asyncio.Queue()

    async def initialize(self, context: PluginContext) -> None:
        """Initialize the data processing pipeline plugin."""
        await super().initialize(context)

        # Get configuration
        self.batch_size = context.get_config("batch_size", 10)
        self.max_retries = context.get_config("max_retries", 3)
        self.retry_delay_base = context.get_config("retry_delay_base", 1.0)
        self.processing_enabled = context.get_config("processing_enabled", True)

        # Update stage configurations from config
        config_stages = context.get_config("stage_configs", {})
        for stage_name, config in config_stages.items():
            if stage_name in [s.value for s in ProcessingStage]:
                self.stage_configs[ProcessingStage(stage_name)].update(config)

        # Register processing service
        if context.service_registry:
            context.service_registry.register_service(
                "data-processing",
                {
                    "type": "pipeline",
                    "plugin": self.plugin_metadata.name,
                    "methods": ["submit_job", "get_job_status", "get_pipeline_metrics"],
                    "stages": [stage.value for stage in ProcessingStage],
                    "tags": ["data-processing", "pipeline", "etl"],
                },
            )

        self.logger.info("Data processing pipeline initialized")

    async def start(self) -> None:
        """Start the data processing pipeline."""
        await super().start()

        if self.processing_enabled:
            # Start background processor
            self._processor_task = asyncio.create_task(self._background_processor())

        # Publish plugin started event
        if self.context and self.context.event_bus:
            await self.context.event_bus.publish(
                "pipeline.started",
                {
                    "plugin": self.plugin_metadata.name,
                    "batch_size": self.batch_size,
                    "max_retries": self.max_retries,
                    "stages": [stage.value for stage in ProcessingStage],
                },
                source=self.plugin_metadata.name,
            )

        self.logger.info("Data processing pipeline started")

    async def stop(self) -> None:
        """Stop the data processing pipeline."""
        await super().stop()

        # Stop background processor
        if self._processor_task and not self._processor_task.done():
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Data processing pipeline stopped")

    @property
    def plugin_metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return self._plugin_metadata

    async def submit_job(self, job_data: dict[str, Any], priority: int = 0) -> str:
        """
        Submit a job for processing through the pipeline.

        Args:
            job_data: Data to be processed
            priority: Job priority (higher = more priority)

        Returns:
            Job ID for tracking
        """
        job_id = f"job-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"

        job = {
            "id": job_id,
            "data": job_data,
            "priority": priority,
            "status": ProcessingStatus.PENDING,
            "submitted_at": time.time(),
            "current_stage": None,
            "completed_stages": [],
            "retry_count": 0,
            "stage_durations": {},
            "errors": [],
        }

        self.active_jobs[job_id] = job
        self.pipeline_metrics["total_jobs"] += 1

        # Add to processing queue
        await self._job_queue.put(job)

        # Publish job submitted event
        if self.context and self.context.event_bus:
            await self.context.event_bus.publish(
                "pipeline.job.submitted",
                {
                    "job_id": job_id,
                    "priority": priority,
                    "data_size": len(str(job_data)),
                },
                source=self.plugin_metadata.name,
            )

        self.logger.info(f"Job submitted: {job_id}")
        return job_id

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get status of a specific job."""
        job = self.active_jobs.get(job_id)
        if not job:
            return None

        return {
            "id": job["id"],
            "status": job["status"],
            "current_stage": job["current_stage"],
            "completed_stages": job["completed_stages"],
            "retry_count": job["retry_count"],
            "stage_durations": job["stage_durations"],
            "total_duration": time.time() - job["submitted_at"]
            if job["status"] == ProcessingStatus.IN_PROGRESS
            else None,
            "errors": job["errors"][-3:],  # Last 3 errors
        }

    async def get_pipeline_metrics(self) -> dict[str, Any]:
        """Get comprehensive pipeline metrics."""
        total_jobs = self.pipeline_metrics["total_jobs"]

        metrics = {
            "overview": {
                "total_jobs": total_jobs,
                "completed_jobs": self.pipeline_metrics["completed_jobs"],
                "failed_jobs": self.pipeline_metrics["failed_jobs"],
                "active_jobs": len(
                    [
                        j
                        for j in self.active_jobs.values()
                        if j["status"] == ProcessingStatus.IN_PROGRESS
                    ]
                ),
                "success_rate": (self.pipeline_metrics["completed_jobs"] / total_jobs)
                if total_jobs > 0
                else 0,
            },
            "stage_metrics": {},
        }

        # Calculate stage metrics
        for stage, stage_data in self.pipeline_metrics["stage_metrics"].items():
            processed = stage_data["processed"]
            avg_duration = (
                (stage_data["total_duration"] / processed) if processed > 0 else 0
            )
            error_rate = (stage_data["failed"] / processed) if processed > 0 else 0

            metrics["stage_metrics"][stage] = {
                "processed": processed,
                "failed": stage_data["failed"],
                "average_duration": avg_duration,
                "error_rate": error_rate,
                "total_retries": stage_data["retry_count"],
            }

        return metrics

    async def _background_processor(self) -> None:
        """Background task that processes jobs from the queue."""
        while True:
            try:
                # Get job from queue (with timeout to allow cancellation)
                try:
                    job = await asyncio.wait_for(self._job_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Process the job
                await self._process_job(job)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in background processor: {e}")

    async def _process_job(self, job: dict[str, Any]) -> None:
        """Process a single job through the pipeline."""
        job_id = job["id"]
        job["status"] = ProcessingStatus.IN_PROGRESS

        self.logger.info(f"Starting job processing: {job_id}")

        try:
            # Process through each stage
            for stage in ProcessingStage:
                if stage.value in job["completed_stages"]:
                    continue  # Skip already completed stages (in case of retry)

                job["current_stage"] = stage.value

                # Process stage with retry logic
                success = await self._process_stage(job, stage)

                if success:
                    job["completed_stages"].append(stage.value)
                else:
                    # Stage failed, handle retry or failure
                    if job["retry_count"] < self.max_retries:
                        job["retry_count"] += 1
                        job["status"] = ProcessingStatus.RETRYING

                        # Exponential backoff delay
                        delay = self.retry_delay_base * (2 ** (job["retry_count"] - 1))
                        await asyncio.sleep(delay)

                        # Re-queue for retry
                        await self._job_queue.put(job)
                        return
                    else:
                        # Max retries exceeded
                        job["status"] = ProcessingStatus.FAILED
                        self.pipeline_metrics["failed_jobs"] += 1

                        # Publish job failed event
                        if self.context and self.context.event_bus:
                            await self.context.event_bus.publish(
                                "pipeline.job.failed",
                                {
                                    "job_id": job_id,
                                    "failed_stage": stage.value,
                                    "retry_count": job["retry_count"],
                                    "errors": job["errors"][-1]
                                    if job["errors"]
                                    else None,
                                },
                                source=self.plugin_metadata.name,
                            )

                        self.logger.error(
                            f"Job failed after {job['retry_count']} retries: {job_id}"
                        )
                        return

            # All stages completed successfully
            job["status"] = ProcessingStatus.COMPLETED
            job["current_stage"] = None
            self.pipeline_metrics["completed_jobs"] += 1

            # Publish job completed event
            if self.context and self.context.event_bus:
                total_duration = sum(job["stage_durations"].values())
                await self.context.event_bus.publish(
                    "pipeline.job.completed",
                    {
                        "job_id": job_id,
                        "total_duration": total_duration,
                        "stage_durations": job["stage_durations"],
                        "retry_count": job["retry_count"],
                    },
                    source=self.plugin_metadata.name,
                )

            self.logger.info(f"Job completed successfully: {job_id}")

        except Exception as e:
            job["status"] = ProcessingStatus.FAILED
            job["errors"].append(str(e))
            self.pipeline_metrics["failed_jobs"] += 1
            self.logger.error(f"Unexpected error processing job {job_id}: {e}")

    async def _process_stage(self, job: dict[str, Any], stage: ProcessingStage) -> bool:
        """
        Process a single stage of the pipeline.

        Returns:
            True if stage completed successfully, False if failed
        """
        stage_config = self.stage_configs[stage]
        stage_name = stage.value
        job_id = job["id"]

        # Simulate stage processing time
        duration_range = stage_config["duration_range"]
        duration = random.uniform(duration_range[0], duration_range[1])

        start_time = time.time()

        self.logger.debug(
            f"Processing stage {stage_name} for job {job_id} (estimated {duration:.2f}s)"
        )

        # Publish stage started event
        if self.context and self.context.event_bus:
            await self.context.event_bus.publish(
                "pipeline.stage.started",
                {"job_id": job_id, "stage": stage_name, "estimated_duration": duration},
                source=self.plugin_metadata.name,
            )

        try:
            # Simulate work
            await asyncio.sleep(duration)

            # Random error based on stage error rate
            if random.random() < stage_config["error_rate"]:
                error_msg = f"Stage {stage_name} failed randomly"
                raise Exception(error_msg)

            # Stage completed successfully
            actual_duration = time.time() - start_time
            job["stage_durations"][stage_name] = actual_duration

            # Update metrics
            stage_metrics = self.pipeline_metrics["stage_metrics"][stage_name]
            stage_metrics["processed"] += 1
            stage_metrics["total_duration"] += actual_duration

            # Publish stage completed event
            if self.context and self.context.event_bus:
                await self.context.event_bus.publish(
                    "pipeline.stage.completed",
                    {
                        "job_id": job_id,
                        "stage": stage_name,
                        "duration": actual_duration,
                    },
                    source=self.plugin_metadata.name,
                )

            self.logger.debug(
                f"Stage {stage_name} completed for job {job_id} in {actual_duration:.2f}s"
            )
            return True

        except Exception as e:
            actual_duration = time.time() - start_time
            error_msg = str(e)

            # Update metrics
            stage_metrics = self.pipeline_metrics["stage_metrics"][stage_name]
            stage_metrics["failed"] += 1
            if job["retry_count"] > 0:
                stage_metrics["retry_count"] += 1

            # Add error to job
            job["errors"].append(f"Stage {stage_name}: {error_msg}")

            # Publish stage failed event
            if self.context and self.context.event_bus:
                await self.context.event_bus.publish(
                    "pipeline.stage.failed",
                    {
                        "job_id": job_id,
                        "stage": stage_name,
                        "duration": actual_duration,
                        "error": error_msg,
                        "retry_count": job["retry_count"],
                    },
                    source=self.plugin_metadata.name,
                )

            self.logger.warning(
                f"Stage {stage_name} failed for job {job_id}: {error_msg}"
            )
            return False

    async def on_service_register(self, service_info: dict[str, Any]) -> None:
        """Called when a service is being registered."""
        self.logger.debug(f"Service registered: {service_info.get('name', 'unknown')}")

    async def on_service_unregister(self, service_info: dict[str, Any]) -> None:
        """Called when a service is being unregistered."""
        self.logger.debug(
            f"Service unregistered: {service_info.get('name', 'unknown')}"
        )

    async def health_check(self) -> dict[str, Any]:
        """Perform health check with pipeline status."""
        health = await super().health_check()

        # Get pipeline metrics
        metrics = await self.get_pipeline_metrics()

        # Add pipeline-specific health information
        health["details"] = {
            "processing_enabled": self.processing_enabled,
            "background_processor_running": self._processor_task
            and not self._processor_task.done(),
            "queue_size": self._job_queue.qsize(),
            "active_jobs": metrics["overview"]["active_jobs"],
            "success_rate": metrics["overview"]["success_rate"],
            "total_jobs": metrics["overview"]["total_jobs"],
        }

        # Health status based on success rate and active processing
        if metrics["overview"]["total_jobs"] > 5:  # Only evaluate after some jobs
            health["healthy"] = metrics["overview"][
                "success_rate"
            ] > 0.7 and (  # >70% success rate
                self._processor_task and not self._processor_task.done()
            )  # Processor running

        return health
