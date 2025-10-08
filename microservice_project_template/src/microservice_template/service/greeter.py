"""Sample gRPC service implementation with analytics capabilities."""

from __future__ import annotations

import io
import json
import time

import grpc
import pandas as pd
import structlog
from microservice_template.config import AppSettings
from microservice_template.observability.metrics import MetricsServer
from microservice_template.proto import greeter_pb2, greeter_pb2_grpc
from microservice_template.service.analytics import AnalyticsService
from opentelemetry import trace


class GreeterService(greeter_pb2_grpc.GreeterServiceServicer):
    """Example business logic demonstrating logging, tracing, and metrics."""

    def __init__(self, settings: AppSettings, metrics: MetricsServer) -> None:
        self._settings = settings
        self._metrics = metrics
        self._logger = structlog.get_logger(__name__)
        self._start_time = time.monotonic()
        self._tracer = trace.get_tracer(__name__)
        self._analytics = AnalyticsService()

    async def SayHello(
        self,
        request: greeter_pb2.HelloRequest,
        context: grpc.aio.ServicerContext,
    ) -> greeter_pb2.HelloResponse:
        start = time.perf_counter()
        with self._tracer.start_as_current_span("SayHello") as span:
            name = request.name or "friend"
            greeting = f"Hello, {name}!"
            span.set_attribute("request.name", name)
            self._logger.info("greeting.generated", name=name, greeting=greeting)

            response = greeter_pb2.HelloResponse(
                message=greeting,
                trace_id=_current_trace_id(span.get_span_context()),
            )

        self._metrics.observe_request(
            "SayHello", grpc.StatusCode.OK.name, time.perf_counter() - start
        )
        return response

    async def HealthCheck(
        self,
        request: greeter_pb2.HealthCheckRequest,
        context: grpc.aio.ServicerContext,
    ) -> greeter_pb2.HealthCheckResponse:
        start = time.perf_counter()
        uptime_seconds = time.monotonic() - self._start_time

        response = greeter_pb2.HealthCheckResponse(
            status="SERVING",
            version=self._settings.version,
            uptime=f"{uptime_seconds:.2f}s",
        )
        self._metrics.observe_request(
            "HealthCheck", grpc.StatusCode.OK.name, time.perf_counter() - start
        )
        return response

    async def GenerateSampleData(
        self,
        request: greeter_pb2.SampleDataRequest,
        context: grpc.aio.ServicerContext,
    ) -> greeter_pb2.SampleDataResponse:
        """Generate sample dataset for analytics demonstration."""
        start = time.perf_counter()
        try:
            with self._tracer.start_as_current_span("GenerateSampleData") as span:
                n_samples = request.n_samples if request.n_samples > 0 else 1000
                seed = request.seed if request.seed > 0 else 42

                span.set_attribute("request.n_samples", n_samples)
                span.set_attribute("request.seed", seed)

                # Generate sample data
                df = self._analytics.generate_sample_data(
                    n_samples=n_samples, seed=seed
                )

                # Convert to CSV string
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue()

                self._logger.info(
                    "analytics.sample_data.generated",
                    n_samples=len(df),
                    columns=list(df.columns),
                )

                response = greeter_pb2.SampleDataResponse(
                    data_csv=csv_data,
                    message=f"Generated {len(df)} samples with {len(df.columns)} columns",
                )

                self._metrics.observe_request(
                    "GenerateSampleData",
                    grpc.StatusCode.OK.name,
                    time.perf_counter() - start,
                )
                return response

        except Exception as e:
            self._logger.error("analytics.sample_data.error", error=str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to generate sample data: {e!s}")
            return greeter_pb2.SampleDataResponse()

    async def AnalyzeCorrelation(
        self,
        request: greeter_pb2.CorrelationRequest,
        context: grpc.aio.ServicerContext,
    ) -> greeter_pb2.AnalysisResponse:
        """Perform correlation analysis on provided dataset."""
        start = time.perf_counter()
        try:
            with self._tracer.start_as_current_span("AnalyzeCorrelation") as span:
                # Parse CSV data
                df = pd.read_csv(io.StringIO(request.data_csv))
                span.set_attribute("dataset.rows", len(df))
                span.set_attribute("dataset.columns", len(df.columns))

                # Perform correlation analysis
                result = self._analytics.correlation_analysis(df)

                response = greeter_pb2.AnalysisResponse(
                    success=result.success,
                    message=result.message,
                    results_json=json.dumps(result.data),
                    plot_base64=result.plot_base64 or "",
                )

                self._metrics.observe_request(
                    "AnalyzeCorrelation",
                    grpc.StatusCode.OK.name,
                    time.perf_counter() - start,
                )
                return response

        except Exception as e:
            self._logger.error("analytics.correlation.error", error=str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Correlation analysis failed: {e!s}")
            return greeter_pb2.AnalysisResponse(success=False, message=str(e))

    async def AnalyzeClustering(
        self,
        request: greeter_pb2.ClusteringRequest,
        context: grpc.aio.ServicerContext,
    ) -> greeter_pb2.AnalysisResponse:
        """Perform clustering analysis on provided dataset."""
        start = time.perf_counter()
        try:
            with self._tracer.start_as_current_span("AnalyzeClustering") as span:
                # Parse CSV data
                df = pd.read_csv(io.StringIO(request.data_csv))
                n_clusters = request.n_clusters if request.n_clusters > 0 else 3

                span.set_attribute("dataset.rows", len(df))
                span.set_attribute("dataset.columns", len(df.columns))
                span.set_attribute("request.n_clusters", n_clusters)

                # Perform clustering analysis
                result = self._analytics.clustering_analysis(df, n_clusters=n_clusters)

                response = greeter_pb2.AnalysisResponse(
                    success=result.success,
                    message=result.message,
                    results_json=json.dumps(result.data),
                    plot_base64=result.plot_base64 or "",
                )

                self._metrics.observe_request(
                    "AnalyzeClustering",
                    grpc.StatusCode.OK.name,
                    time.perf_counter() - start,
                )
                return response

        except Exception as e:
            self._logger.error("analytics.clustering.error", error=str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Clustering analysis failed: {e!s}")
            return greeter_pb2.AnalysisResponse(success=False, message=str(e))

    async def AnalyzeDistribution(
        self,
        request: greeter_pb2.DistributionRequest,
        context: grpc.aio.ServicerContext,
    ) -> greeter_pb2.AnalysisResponse:
        """Perform distribution analysis on provided numeric data."""
        start = time.perf_counter()
        try:
            with self._tracer.start_as_current_span("AnalyzeDistribution") as span:
                values = list(request.values)
                column_name = request.column_name or "values"

                span.set_attribute("data.length", len(values))
                span.set_attribute("request.column_name", column_name)

                # Perform distribution analysis
                result = self._analytics.distribution_analysis(values, column_name)

                response = greeter_pb2.AnalysisResponse(
                    success=result.success,
                    message=result.message,
                    results_json=json.dumps(result.data),
                    plot_base64=result.plot_base64 or "",
                )

                self._metrics.observe_request(
                    "AnalyzeDistribution",
                    grpc.StatusCode.OK.name,
                    time.perf_counter() - start,
                )
                return response

        except Exception as e:
            self._logger.error("analytics.distribution.error", error=str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Distribution analysis failed: {e!s}")
            return greeter_pb2.AnalysisResponse(success=False, message=str(e))


def _current_trace_id(span_context: trace.SpanContext) -> str:
    trace_id_int = span_context.trace_id
    if trace_id_int == 0:
        return ""
    return f"{trace_id_int:032x}"
