"""
MMF Demo: Custom Analytics Plugin
Demonstrates the MMF plugin architecture with real-time transaction analytics
"""
import json
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


# MMF Plugin Interface
class MMFPlugin(ABC):
    """Base class for all MMF plugins"""

    @abstractmethod
    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the plugin with configuration"""
        pass

    @abstractmethod
    def process_event(self, event: dict[str, Any]) -> None:
        """Process an incoming event"""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get plugin name"""
        pass

    @abstractmethod
    def get_version(self) -> str:
        """Get plugin version"""
        pass

@dataclass
class TransactionMetrics:
    """Transaction performance metrics"""
    total_transactions: int = 0
    successful_transactions: int = 0
    failed_transactions: int = 0
    avg_processing_time: float = 0.0
    max_processing_time: float = 0.0
    min_processing_time: float = float('inf')
    bottleneck_services: dict[str, float] = None
    error_patterns: dict[str, int] = None

    def __post_init__(self):
        if self.bottleneck_services is None:
            self.bottleneck_services = {}
        if self.error_patterns is None:
            self.error_patterns = {}

class TransactionAnalyticsPlugin(MMFPlugin):
    """
    Custom plugin that analyzes transaction flows across services
    Demonstrates:
    - Real-time analytics
    - Performance bottleneck detection
    - Error pattern analysis
    - Business intelligence
    """

    def __init__(self):
        self.config = {}
        self.transaction_data = {}  # correlation_id -> transaction info
        self.service_metrics = {}   # service_name -> metrics
        self.processing_times = []  # List of all processing times
        self.error_patterns = {}    # error_type -> count
        self.bottlenecks = {}       # service -> avg_response_time

    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the analytics plugin"""
        self.config = config
        self.performance_threshold = config.get('performance_threshold_ms', 1000)
        self.error_threshold = config.get('error_threshold_percent', 5)

        print(f"🔌 {self.get_name()} v{self.get_version()} initialized")
        print(f"   Performance threshold: {self.performance_threshold}ms")
        print(f"   Error threshold: {self.error_threshold}%")

    def get_name(self) -> str:
        return "Transaction Analytics Plugin"

    def get_version(self) -> str:
        return "1.0.0"

    def process_event(self, event: dict[str, Any]) -> None:
        """Process transaction events and update analytics"""
        try:
            event_type = event.get('event')
            correlation_id = event.get('correlation_id')
            service_name = self._extract_service_name(event)

            if not correlation_id:
                return

            # Initialize transaction tracking
            if correlation_id not in self.transaction_data:
                self.transaction_data[correlation_id] = {
                    'started_at': datetime.utcnow(),
                    'services_involved': set(),
                    'events': [],
                    'status': 'in_progress',
                    'total_processing_time': 0.0,
                    'service_times': {}
                }

            transaction = self.transaction_data[correlation_id]
            transaction['events'].append(event)
            transaction['services_involved'].add(service_name)

            # Process different event types
            if 'processing_time_ms' in event:
                processing_time = event['processing_time_ms']
                transaction['service_times'][service_name] = processing_time
                self._update_service_metrics(service_name, processing_time)

            if 'failed' in event_type or 'error' in event_type:
                transaction['status'] = 'failed'
                self._track_error(event)
            elif 'completed' in event_type:
                if transaction['status'] != 'failed':
                    transaction['status'] = 'completed'
                self._finalize_transaction(correlation_id, transaction)

        except Exception as e:
            print(f"Error processing event in analytics plugin: {e}")

    def _extract_service_name(self, event: dict[str, Any]) -> str:
        """Extract service name from event"""
        # Look for service indicators in the event
        if 'order' in str(event).lower():
            return 'order-service'
        elif 'payment' in str(event).lower():
            return 'payment-service'
        elif 'inventory' in str(event).lower():
            return 'inventory-service'
        else:
            return 'unknown-service'

    def _update_service_metrics(self, service_name: str, processing_time: float) -> None:
        """Update metrics for a specific service"""
        if service_name not in self.service_metrics:
            self.service_metrics[service_name] = {
                'total_requests': 0,
                'total_time': 0.0,
                'max_time': 0.0,
                'min_time': float('inf'),
                'times': []
            }

        metrics = self.service_metrics[service_name]
        metrics['total_requests'] += 1
        metrics['total_time'] += processing_time
        metrics['max_time'] = max(metrics['max_time'], processing_time)
        metrics['min_time'] = min(metrics['min_time'], processing_time)
        metrics['times'].append(processing_time)

        # Keep only last 100 times for memory efficiency
        if len(metrics['times']) > 100:
            metrics['times'] = metrics['times'][-100:]

    def _track_error(self, event: dict[str, Any]) -> None:
        """Track error patterns"""
        error_type = event.get('error', 'unknown_error')
        self.error_patterns[error_type] = self.error_patterns.get(error_type, 0) + 1

    def _finalize_transaction(self, correlation_id: str, transaction: dict) -> None:
        """Finalize transaction analysis"""
        total_time = sum(transaction['service_times'].values())
        transaction['total_processing_time'] = total_time
        self.processing_times.append(total_time)

        # Keep only last 1000 processing times
        if len(self.processing_times) > 1000:
            self.processing_times = self.processing_times[-1000:]

    def generate_performance_report(self) -> dict[str, Any]:
        """Generate comprehensive performance analysis report"""
        report = {
            'report_generated_at': datetime.utcnow().isoformat(),
            'summary': self._generate_summary(),
            'service_performance': self._analyze_service_performance(),
            'bottleneck_analysis': self._identify_bottlenecks(),
            'error_analysis': self._analyze_errors(),
            'recommendations': self._generate_recommendations()
        }

        return report

    def _generate_summary(self) -> dict[str, Any]:
        """Generate transaction summary"""
        total_transactions = len(self.transaction_data)
        completed = sum(1 for t in self.transaction_data.values() if t['status'] == 'completed')
        failed = sum(1 for t in self.transaction_data.values() if t['status'] == 'failed')

        avg_time = statistics.mean(self.processing_times) if self.processing_times else 0
        max_time = max(self.processing_times) if self.processing_times else 0
        min_time = min(self.processing_times) if self.processing_times else 0

        return {
            'total_transactions': total_transactions,
            'successful_transactions': completed,
            'failed_transactions': failed,
            'success_rate_percent': (completed / total_transactions * 100) if total_transactions > 0 else 0,
            'average_processing_time_ms': round(avg_time, 2),
            'max_processing_time_ms': round(max_time, 2),
            'min_processing_time_ms': round(min_time, 2)
        }

    def _analyze_service_performance(self) -> dict[str, Any]:
        """Analyze performance of each service"""
        service_analysis = {}

        for service_name, metrics in self.service_metrics.items():
            if metrics['total_requests'] > 0:
                avg_time = metrics['total_time'] / metrics['total_requests']

                analysis = {
                    'total_requests': metrics['total_requests'],
                    'average_response_time_ms': round(avg_time, 2),
                    'max_response_time_ms': round(metrics['max_time'], 2),
                    'min_response_time_ms': round(metrics['min_time'], 2),
                    'performance_status': 'healthy' if avg_time < self.performance_threshold else 'slow',
                    'p95_response_time_ms': round(self._calculate_percentile(metrics['times'], 95), 2) if metrics['times'] else 0,
                    'p99_response_time_ms': round(self._calculate_percentile(metrics['times'], 99), 2) if metrics['times'] else 0
                }

                service_analysis[service_name] = analysis

        return service_analysis

    def _identify_bottlenecks(self) -> dict[str, Any]:
        """Identify performance bottlenecks"""
        bottlenecks = []

        for service_name, metrics in self.service_metrics.items():
            if metrics['total_requests'] > 0:
                avg_time = metrics['total_time'] / metrics['total_requests']

                if avg_time > self.performance_threshold:
                    bottlenecks.append({
                        'service': service_name,
                        'average_response_time_ms': round(avg_time, 2),
                        'severity': 'high' if avg_time > self.performance_threshold * 2 else 'medium',
                        'impact': f"{avg_time - self.performance_threshold:.0f}ms over threshold"
                    })

        # Sort by response time (worst first)
        bottlenecks.sort(key=lambda x: x['average_response_time_ms'], reverse=True)

        return {
            'bottlenecks_found': len(bottlenecks),
            'critical_services': bottlenecks
        }

    def _analyze_errors(self) -> dict[str, Any]:
        """Analyze error patterns"""
        total_transactions = len(self.transaction_data)
        total_errors = sum(self.error_patterns.values())

        error_rate = (total_errors / total_transactions * 100) if total_transactions > 0 else 0

        # Sort errors by frequency
        sorted_errors = sorted(self.error_patterns.items(), key=lambda x: x[1], reverse=True)

        return {
            'total_errors': total_errors,
            'error_rate_percent': round(error_rate, 2),
            'error_threshold_exceeded': error_rate > self.error_threshold,
            'common_errors': [{'error_type': error, 'count': count} for error, count in sorted_errors[:5]]
        }

    def _generate_recommendations(self) -> list[str]:
        """Generate performance improvement recommendations"""
        recommendations = []

        # Analyze service performance
        for service_name, metrics in self.service_metrics.items():
            if metrics['total_requests'] > 0:
                avg_time = metrics['total_time'] / metrics['total_requests']

                if avg_time > self.performance_threshold * 2:
                    recommendations.append(f"🚨 CRITICAL: {service_name} is severely slow (avg: {avg_time:.0f}ms). Consider scaling or optimization.")
                elif avg_time > self.performance_threshold:
                    recommendations.append(f"⚠️  WARNING: {service_name} is slow (avg: {avg_time:.0f}ms). Monitor for potential issues.")

        # Analyze error rates
        total_transactions = len(self.transaction_data)
        total_errors = sum(self.error_patterns.values())
        error_rate = (total_errors / total_transactions * 100) if total_transactions > 0 else 0

        if error_rate > self.error_threshold:
            recommendations.append(f"🔴 High error rate detected: {error_rate:.1f}%. Investigate error patterns and root causes.")

        # General recommendations
        if len(recommendations) == 0:
            recommendations.append("✅ All services are performing within acceptable thresholds.")

        return recommendations

    def _calculate_percentile(self, values: list[float], percentile: int) -> float:
        """Calculate percentile from list of values"""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = (percentile / 100) * (len(sorted_values) - 1)

        if index.is_integer():
            return sorted_values[int(index)]
        else:
            lower = sorted_values[int(index)]
            upper = sorted_values[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))

# Plugin Registry (demonstrates plugin management)
class PluginRegistry:
    """Manages MMF plugins"""

    def __init__(self):
        self.plugins: dict[str, MMFPlugin] = {}

    def register_plugin(self, plugin: MMFPlugin, config: dict[str, Any] = None) -> None:
        """Register and initialize a plugin"""
        plugin.initialize(config or {})
        self.plugins[plugin.get_name()] = plugin
        print(f"✅ Plugin registered: {plugin.get_name()} v{plugin.get_version()}")

    def process_event(self, event: dict[str, Any]) -> None:
        """Send event to all registered plugins"""
        for plugin in self.plugins.values():
            try:
                plugin.process_event(event)
            except Exception as e:
                print(f"Error in plugin {plugin.get_name()}: {e}")

    def get_plugin(self, name: str) -> MMFPlugin:
        """Get plugin by name"""
        return self.plugins.get(name)

    def list_plugins(self) -> list[str]:
        """List all registered plugins"""
        return list(self.plugins.keys())

# Example usage
if __name__ == "__main__":
    # Demo the plugin system
    registry = PluginRegistry()

    # Create and register analytics plugin
    analytics_plugin = TransactionAnalyticsPlugin()
    registry.register_plugin(analytics_plugin, {
        'performance_threshold_ms': 800,
        'error_threshold_percent': 3
    })

    # Simulate some transaction events
    sample_events = [
        {
            'event': 'order_creation_started',
            'correlation_id': 'TXN-001',
            'timestamp': datetime.utcnow().isoformat()
        },
        {
            'event': 'payment_processing_completed',
            'correlation_id': 'TXN-001',
            'processing_time_ms': 1200,
            'timestamp': datetime.utcnow().isoformat()
        },
        {
            'event': 'inventory_reservation_completed',
            'correlation_id': 'TXN-001',
            'processing_time_ms': 300,
            'timestamp': datetime.utcnow().isoformat()
        },
        {
            'event': 'order_creation_completed',
            'correlation_id': 'TXN-001',
            'processing_time_ms': 150,
            'timestamp': datetime.utcnow().isoformat()
        }
    ]

    # Process events through plugin system
    for event in sample_events:
        registry.process_event(event)

    # Generate analytics report
    report = analytics_plugin.generate_performance_report()
    print("\n📊 Performance Analysis Report:")
    print(json.dumps(report, indent=2))
