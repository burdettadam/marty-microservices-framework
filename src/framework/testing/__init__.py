"""
Advanced Testing Framework for Marty Microservices Framework.

This package provides comprehensive testing capabilities for enterprise microservices
including contract testing, chaos engineering, performance testing, integration testing,
and test automation.

Key Components:
- Core testing framework with test execution and reporting
- Contract testing for consumer-driven contracts and API validation
- Chaos engineering for resilience testing
- Performance testing with load, stress, and spike testing
- Integration testing for service-to-service, database, and message queue testing
- Test automation with discovery, scheduling, and CI/CD integration

Example Usage:
    from marty.framework.testing import (
        TestSuite, TestExecutor, TestConfiguration,
        ContractBuilder, ChaosExperimentBuilder,
        create_load_test, IntegrationTestEnvironment,
        TestOrchestrator, setup_basic_test_automation
    )

    # Create and execute a basic test suite
    suite = TestSuite("Example Tests", "Example test suite")

    config = TestConfiguration(
        parallel_execution=True,
        max_workers=4,
        generate_reports=True
    )

    executor = TestExecutor(config)
    results = await executor.execute_suite(suite)

    # Create a contract test
    contract = (ContractBuilder("consumer", "provider")
                .interaction("Get user")
                .with_request("GET", "/users/123")
                .will_respond_with(200, body={"id": 123, "name": "John"})
                .build())

    # Create a chaos experiment
    experiment = (ChaosExperimentBuilder("Service Kill Test")
                  .chaos_type(ChaosType.SERVICE_KILL)
                  .target("user-service")
                  .duration(60)
                  .build())

    # Create a performance test
    load_test = create_load_test(
        name="API Load Test",
        url="http://localhost:8080/api/users",
        users=50,
        duration=120,
        criteria={"max_response_time": 1.0, "min_requests_per_second": 100}
    )

    # Setup test automation
    orchestrator = setup_basic_test_automation(
        base_dirs=["./tests"],
        environments=["development", "testing", "staging"]
    )
"""

# Chaos engineering
from .chaos_engineering import (
    ChaosAction,
    ChaosActionFactory,
    ChaosExperiment,
    ChaosExperimentBuilder,
    ChaosManager,
    ChaosParameters,
    ChaosScope,
    ChaosTarget,
    ChaosTestCase,
    ChaosType,
    ExperimentPhase,
    SteadyStateHypothesis,
    SteadyStateProbe,
    create_cpu_stress_experiment,
    create_memory_stress_experiment,
    create_network_delay_experiment,
    create_service_kill_experiment,
)

# Contract testing
from .contract_testing import (
    Contract,
    ContractBuilder,
    ContractInteraction,
    ContractManager,
    ContractRepository,
    ContractRequest,
    ContractResponse,
    ContractTestCase,
    ContractType,
    ContractValidator,
    InteractionBuilder,
    VerificationLevel,
    pact_contract,
    verify_contracts_for_provider,
)

# Core testing framework
from .core import (
    TestCase,
    TestConfiguration,
    TestDataManager,
    TestExecutor,
    TestMetrics,
    TestReporter,
    TestResult,
    TestSeverity,
    TestStatus,
    TestSuite,
    TestType,
    test_case,
    test_context,
)

# Integration testing
from .integration_testing import (
    DatabaseConfig,
    DatabaseIntegrationHelper,
    DatabaseIntegrationTestCase,
    IntegrationTestEnvironment,
    IntegrationTestManager,
    IntegrationType,
    MessageQueueConfig,
    MessageQueueIntegrationHelper,
    MessageQueueIntegrationTestCase,
    ServiceEndpoint,
    ServiceToServiceTestCase,
    TestEnvironment,
    TestScenario,
    create_api_integration_scenario,
    create_database_crud_scenario,
    create_message_flow_scenario,
)

# Performance testing
from .performance_testing import (
    LoadConfiguration,
    LoadGenerator,
    LoadPattern,
    MetricsCollector,
    PerformanceMetrics,
    PerformanceReportGenerator,
    PerformanceTestCase,
    PerformanceTestType,
    RequestSpec,
    ResponseMetric,
    create_load_test,
    create_spike_test,
    create_stress_test,
)

# Test automation
from .test_automation import (
    ContinuousTestingEngine,
    TestDiscovery,
    TestDiscoveryConfig,
    TestDiscoveryStrategy,
    TestEnvironmentType,
    TestExecutionPlan,
    TestOrchestrator,
    TestRun,
    TestScheduleConfig,
    TestScheduler,
    TestScheduleType,
    create_ci_cd_execution_plan,
    create_standard_discovery_config,
    setup_basic_test_automation,
)

__all__ = [
    # Core testing framework
    "TestType",
    "TestStatus",
    "TestSeverity",
    "TestMetrics",
    "TestResult",
    "TestCase",
    "TestSuite",
    "TestConfiguration",
    "TestDataManager",
    "TestReporter",
    "TestExecutor",
    "test_case",
    "test_context",
    # Contract testing
    "ContractType",
    "VerificationLevel",
    "ContractRequest",
    "ContractResponse",
    "ContractInteraction",
    "Contract",
    "ContractBuilder",
    "InteractionBuilder",
    "ContractValidator",
    "ContractRepository",
    "ContractTestCase",
    "ContractManager",
    "pact_contract",
    "verify_contracts_for_provider",
    # Chaos engineering
    "ChaosType",
    "ChaosScope",
    "ExperimentPhase",
    "ChaosTarget",
    "ChaosParameters",
    "SteadyStateHypothesis",
    "ChaosExperiment",
    "ChaosAction",
    "ChaosActionFactory",
    "SteadyStateProbe",
    "ChaosTestCase",
    "ChaosExperimentBuilder",
    "ChaosManager",
    "create_network_delay_experiment",
    "create_service_kill_experiment",
    "create_cpu_stress_experiment",
    "create_memory_stress_experiment",
    # Performance testing
    "PerformanceTestType",
    "LoadPattern",
    "RequestSpec",
    "LoadConfiguration",
    "ResponseMetric",
    "PerformanceMetrics",
    "MetricsCollector",
    "LoadGenerator",
    "PerformanceTestCase",
    "PerformanceReportGenerator",
    "create_load_test",
    "create_stress_test",
    "create_spike_test",
    # Integration testing
    "IntegrationType",
    "TestEnvironment",
    "ServiceEndpoint",
    "DatabaseConfig",
    "MessageQueueConfig",
    "TestScenario",
    "IntegrationTestEnvironment",
    "DatabaseIntegrationHelper",
    "MessageQueueIntegrationHelper",
    "ServiceToServiceTestCase",
    "DatabaseIntegrationTestCase",
    "MessageQueueIntegrationTestCase",
    "IntegrationTestManager",
    "create_api_integration_scenario",
    "create_database_crud_scenario",
    "create_message_flow_scenario",
    # Test automation
    "TestDiscoveryStrategy",
    "TestScheduleType",
    "TestEnvironmentType",
    "TestDiscoveryConfig",
    "TestScheduleConfig",
    "TestExecutionPlan",
    "TestRun",
    "TestDiscovery",
    "TestScheduler",
    "ContinuousTestingEngine",
    "TestOrchestrator",
    "create_standard_discovery_config",
    "create_ci_cd_execution_plan",
    "setup_basic_test_automation",
]

# Version information
__version__ = "1.0.0"
__author__ = "Marty Microservices Framework Team"
__description__ = "Advanced Testing Framework for Enterprise Microservices"


def get_version():
    """Get the version of the testing framework."""
    return __version__


def get_framework_info():
    """Get comprehensive framework information."""
    return {
        "name": "Marty Advanced Testing Framework",
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "components": {
            "core": "Core testing framework with execution and reporting",
            "contract_testing": "Consumer-driven contract testing and API validation",
            "chaos_engineering": "Resilience testing with fault injection",
            "performance_testing": "Load, stress, and performance testing capabilities",
            "integration_testing": "Service, database, and message queue integration testing",
            "test_automation": "Test discovery, scheduling, and CI/CD integration",
        },
        "supported_test_types": [t.value for t in TestType],
        "supported_contract_types": [t.value for t in ContractType],
        "supported_chaos_types": [t.value for t in ChaosType],
        "supported_performance_types": [t.value for t in PerformanceTestType],
        "supported_integration_types": [t.value for t in IntegrationType],
    }


# Example usage and quick start helpers
class QuickStart:
    """Quick start helper for common testing scenarios."""

    @staticmethod
    def create_basic_test_suite(name: str, description: str = "") -> TestSuite:
        """Create a basic test suite with common configuration."""
        return TestSuite(name, description)

    @staticmethod
    def create_basic_executor(parallel: bool = True, workers: int = 4) -> TestExecutor:
        """Create a basic test executor with common configuration."""
        config = TestConfiguration(
            parallel_execution=parallel,
            max_workers=workers,
            generate_reports=True,
            report_formats=["json", "html"],
        )
        return TestExecutor(config)

    @staticmethod
    def create_contract_verification_test(
        consumer: str, provider: str, provider_url: str
    ) -> ContractTestCase:
        """Create a basic contract verification test."""
        manager = ContractManager()
        return manager.verify_contract(consumer, provider, provider_url)

    @staticmethod
    def create_simple_chaos_test(
        service_name: str, chaos_type: str = "service_kill"
    ) -> ChaosTestCase:
        """Create a simple chaos engineering test."""
        chaos_type_enum = ChaosType(chaos_type)

        if chaos_type_enum == ChaosType.SERVICE_KILL:
            experiment = create_service_kill_experiment(service_name)
        elif chaos_type_enum == ChaosType.NETWORK_DELAY:
            experiment = create_network_delay_experiment(service_name)
        elif chaos_type_enum == ChaosType.RESOURCE_EXHAUSTION:
            experiment = create_cpu_stress_experiment(service_name)
        else:
            raise ValueError(f"Unsupported chaos type: {chaos_type}")

        return ChaosTestCase(experiment)

    @staticmethod
    def create_api_load_test(
        url: str, users: int = 10, duration: int = 60
    ) -> PerformanceTestCase:
        """Create a simple API load test."""
        return create_load_test(
            name=f"Load Test - {url}",
            url=url,
            users=users,
            duration=duration,
            criteria={
                "max_response_time": 2.0,
                "max_error_rate": 0.05,
                "min_requests_per_second": users * 0.8,
            },
        )

    @staticmethod
    def setup_integration_environment(
        services: List[Dict[str, str]]
    ) -> IntegrationTestEnvironment:
        """Setup a basic integration test environment."""
        env = IntegrationTestEnvironment()

        for service in services:
            endpoint = ServiceEndpoint(
                name=service["name"],
                url=service["url"],
                health_check_path=service.get("health_path", "/health"),
            )
            env.add_service(endpoint)

        return env

    @staticmethod
    def setup_automated_testing(
        test_dirs: List[str], environments: List[str] = None
    ) -> TestOrchestrator:
        """Setup automated testing with reasonable defaults."""
        environments = environments or ["development", "testing"]
        return setup_basic_test_automation(test_dirs, environments)


# Make QuickStart available at package level
quick_start = QuickStart()
