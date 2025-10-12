# End-to-End Testing Suite for Marty Framework

This comprehensive end-to-end testing suite demonstrates the full capabilities of the Marty microservices framework, including performance analysis, bottleneck detection, timeout monitoring, auditability, and visual testing.

## Overview

The E2E test suite includes:

### 🔍 **Bottleneck Analysis** (`test_bottleneck_analysis.py`)
- Uses example plugins to generate realistic workload
- Analyzes performance bottlenecks under different load levels
- Measures CPU, memory, and response time metrics
- Identifies services with performance degradation
- Generates actionable optimization recommendations

### ⏱️ **Timeout Detection** (`test_timeout_detection.py`)
- Tests services under increased workload leading to timeouts
- Demonstrates circuit breaker functionality and state transitions
- Monitors timeout patterns and service resilience
- Validates automatic recovery mechanisms
- Provides insights on service protection strategies

### 📋 **Auditability** (`test_auditability.py`)
- Comprehensive error logging and event tracking
- Audit trail functionality for compliance and debugging
- Structured logging for observability across services
- Event correlation and traceability validation
- Compliance checking and gap analysis

### 🎭 **Visual Testing** (`test_playwright_visual.py`)
- Automated testing of monitoring dashboards using Playwright
- Visual regression testing and screenshot comparison
- Responsive design validation across devices
- Interactive element testing and accessibility validation
- UI performance and usability analysis

### 📈 **Performance Reporting** (`performance_reporting.py`)
- Generates comprehensive reports with visual charts
- Performance trend analysis and bottleneck visualization
- Executive summaries with actionable insights
- HTML reports with interactive dashboards
- Cross-cutting analysis and recommendations

## Quick Start

### Prerequisites

Install additional testing dependencies:

```bash
# Install the testing dependencies
pip install -e ".[dev]"

# Install Playwright browsers (required for visual testing)
playwright install chromium
```

### Running Tests

#### Run All E2E Tests (Recommended)
```bash
# Run the comprehensive master test
pytest tests/e2e/test_master_e2e.py -v -s
```

#### Run Individual Test Categories
```bash
# Bottleneck analysis only
pytest tests/e2e/test_bottleneck_analysis.py -v -s

# Timeout detection only
pytest tests/e2e/test_timeout_detection.py -v -s

# Auditability testing only
pytest tests/e2e/test_auditability.py -v -s

# Visual testing only (requires display)
pytest tests/e2e/test_playwright_visual.py -v -s
```

## Test Results and Reports

After running tests, you'll find comprehensive reports in:

```
test_reports/
├── master_e2e_report/
│   ├── master_e2e_summary.json           # Overall test summary
│   ├── comprehensive_performance_report.json  # Detailed analysis
│   ├── performance_report.html           # Interactive HTML report
│   ├── bottleneck_analysis_report.json   # Bottleneck details
│   ├── timeout_detection_report.json     # Timeout analysis
│   ├── auditability_report.json         # Audit compliance
│   ├── visual_testing_report.json       # UI test results
│   ├── charts/                          # Performance charts
│   │   ├── summary_dashboard.png        # Overall dashboard
│   │   ├── bottleneck_cpu_memory_trends.png
│   │   ├── timeout_progression.png
│   │   ├── audit_overview.png
│   │   └── visual_testing_scorecard.png
│   └── screenshots/                     # Playwright screenshots
│       ├── dashboard_initial_load.png
│       ├── dashboard_mobile.png
│       └── dashboard_desktop.png
```

## Example Plugins Used

The tests demonstrate the framework using these example plugins:

- **SimulationServicePlugin**: Generates realistic workload with configurable delays and error rates
- **DataProcessingPipelinePlugin**: Multi-stage processing with retries and detailed tracking
- **PerformanceMonitorPlugin**: System monitoring with alerting capabilities
- **CircuitBreakerPlugin**: Fault tolerance and service protection

## Key Features Demonstrated

### 🚀 **Framework Capabilities**
- Plugin architecture with lifecycle management
- Service registry and discovery patterns
- Event bus for cross-service communication
- Comprehensive observability and monitoring
- Circuit breaker and resilience patterns

### 📊 **Performance Analysis**
- Real-time bottleneck detection
- Resource usage monitoring (CPU, memory)
- Response time analysis and trending
- Load testing with increasing complexity
- Performance correlation analysis

### 🔒 **Observability & Compliance**
- Structured logging with correlation IDs
- Audit trail generation and validation
- Error tracking and pattern analysis
- Compliance checking and reporting
- Event correlation across services

### 🎯 **Visual Validation**
- Dashboard functionality testing
- Responsive design validation
- Interactive element verification
- Accessibility compliance checking
- Visual regression detection

## Test Configuration

### Environment Variables
```bash
# Optional: Customize test behavior
export E2E_TEST_DURATION=30          # Test duration in seconds
export E2E_LOAD_LEVELS="1,3,5,8"     # Load levels to test
export E2E_TIMEOUT_THRESHOLD=5.0     # Timeout threshold in seconds
export E2E_VISUAL_HEADLESS=true      # Run browser in headless mode
```

### Plugin Configuration
Tests automatically configure plugins with appropriate settings:
- **Error rates**: 5-30% depending on test phase
- **Complexity multipliers**: 1x to 6x for load testing
- **Background tasks**: Scaled with load levels
- **Circuit breaker thresholds**: Tuned for test scenarios

## Understanding Test Results

### Health Scores
- **90-100%**: Excellent - System performing optimally
- **70-89%**: Good - Minor optimizations recommended
- **50-69%**: Needs Attention - Performance issues detected
- **<50%**: Critical - Immediate action required

### Bottleneck Types
- **CPU**: High processor utilization under load
- **Memory**: Memory usage approaching limits
- **Response Time**: Slow service response times
- **Error Rate**: High failure rates in operations

### Timeout Patterns
- **Baseline**: Normal operation timeouts
- **Moderate Load**: Increased timeout frequency
- **High Load**: Significant timeout clustering
- **Stress Test**: Circuit breaker activation

### Audit Quality Metrics
- **Completeness**: Percentage of events with full context
- **Traceability**: Correlation chain completeness
- **Compliance**: Regulatory requirement adherence

## Troubleshooting

### Common Issues

**Tests fail with import errors:**
```bash
# Ensure framework modules are properly imported
python -c "from src.framework.plugins import PluginManager; print('Framework plugins available')"
```

**Playwright tests fail:**
```bash
# Install browser dependencies
playwright install-deps
playwright install chromium
```

**Performance tests show no bottlenecks:**
```bash
# Increase load levels or test duration
export E2E_LOAD_LEVELS="5,10,15,20"
export E2E_TEST_DURATION=60
```

**Charts not generating:**
```bash
# Ensure matplotlib backend is available
python -c "import matplotlib.pyplot as plt; plt.figure()"
```

### Debug Mode
```bash
# Run with verbose output and debug logging
pytest tests/e2e/test_master_e2e.py -v -s --log-cli-level=DEBUG
```

## Integration with CI/CD

### GitHub Actions Example
```yaml
name: E2E Performance Tests
on: [push, pull_request]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
          playwright install chromium

      - name: Run E2E tests
        run: |
          export E2E_VISUAL_HEADLESS=true
          pytest tests/e2e/test_master_e2e.py -v

      - name: Upload reports
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: e2e-reports
          path: test_reports/
```

## Contributing

When adding new E2E tests:

1. **Follow the pattern**: Use existing tests as templates
2. **Add fixtures**: Create reusable test fixtures in `conftest.py`
3. **Generate reports**: Include comprehensive reporting
4. **Update master test**: Add new tests to the master runner
5. **Document thoroughly**: Update this README with new capabilities

## Performance Benchmarks

Expected performance for reference system (4 CPU, 8GB RAM):

- **Bottleneck Analysis**: ~2-3 minutes for 4 load levels
- **Timeout Detection**: ~3-4 minutes for 4 test phases
- **Auditability**: ~2-3 minutes for 4 scenarios
- **Visual Testing**: ~1-2 minutes for all viewports
- **Report Generation**: ~30-60 seconds for all charts

Total test suite runtime: **8-12 minutes**

## Support

For issues with the E2E test suite:

1. Check the troubleshooting section above
2. Review generated logs in `test_reports/`
3. Run individual tests to isolate issues
4. Check plugin configuration and dependencies

The E2E test suite provides comprehensive validation of the Marty framework's performance, reliability, and observability capabilities.
