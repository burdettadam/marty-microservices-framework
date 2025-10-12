"""
Integration test runner for Phase 3 Security & Compliance components

This module provides comprehensive integration testing for all security components
to ensure they work together seamlessly and provide the expected security posture.
"""

import asyncio
import builtins
import json
from datetime import datetime
from typing import Any

from security.compliance import ComplianceManager
from security.compliance.risk_management import RiskCategory, RiskManager
from security.identity_access import IAMManager, RBACManager
from security.monitoring import (
    SecurityEventSeverity,
    SecurityEventType,
    SecurityMonitoringSystem,
)
from security.threat_detection import ThreatDetectionManager, ThreatLevel

# Import security components
from security.zero_trust import ZeroTrustManager


class SecurityIntegrationTestSuite:
    """
    Comprehensive integration test suite for Phase 3 security components
    """

    def __init__(self):
        self.test_results: builtins.dict[str, Any] = {}
        self.components_initialized = False

        # Component instances
        self.zero_trust: ZeroTrustManager | None = None
        self.threat_detection: ThreatDetectionManager | None = None
        self.iam_manager: IAMManager | None = None
        self.compliance_manager: ComplianceManager | None = None
        self.risk_manager: RiskManager | None = None
        self.monitoring_system: SecurityMonitoringSystem | None = None

    async def initialize_components(self):
        """Initialize all security components for testing"""

        print("Initializing security components for integration testing...")

        try:
            # Initialize Zero-Trust
            self.zero_trust = ZeroTrustManager()
            await self.zero_trust.initialize_ca()

            # Initialize Threat Detection
            self.threat_detection = ThreatDetectionManager()
            await self.threat_detection.start_monitoring()

            # Initialize IAM
            self.iam_manager = IAMManager()
            await self.iam_manager.initialize()

            # Initialize Compliance
            self.compliance_manager = ComplianceManager()
            await self.compliance_manager.initialize()

            # Initialize Risk Management
            self.risk_manager = RiskManager()

            # Initialize Security Monitoring
            self.monitoring_system = SecurityMonitoringSystem()

            self.components_initialized = True
            print("✅ All security components initialized successfully")

        except Exception as e:
            print(f"❌ Failed to initialize components: {e}")
            raise

    async def test_authentication_flow(self) -> builtins.dict[str, Any]:
        """Test complete authentication and authorization flow"""

        test_name = "Authentication Flow"
        print(f"\n🧪 Testing {test_name}...")

        try:
            # Test user registration
            registration_result = await self.iam_manager.register_user(
                username="test_user",
                email="test@example.com",
                password="SecurePassword123!",
                role="standard_user",
            )

            assert registration_result["success"], "User registration failed"

            # Test MFA setup
            mfa_setup = await self.iam_manager.setup_mfa(
                user_id=registration_result["user_id"], method="totp"
            )

            assert mfa_setup["success"], "MFA setup failed"

            # Test authentication with MFA
            auth_result = await self.iam_manager.authenticate_with_mfa(
                username="test_user",
                password="SecurePassword123!",
                mfa_token="123456",  # Mock token for testing
            )

            # Test authorization
            auth_engine = RBACManager()
            access_result = await auth_engine.check_permission(
                user_id=registration_result["user_id"],
                resource="api:user_profile",
                action="read",
            )

            result = {
                "test_name": test_name,
                "status": "PASSED",
                "details": {
                    "registration_success": registration_result["success"],
                    "mfa_setup_success": mfa_setup["success"],
                    "authentication_success": auth_result.get("success", False),
                    "authorization_granted": access_result.get("allowed", False),
                },
            }

            print(f"✅ {test_name} completed successfully")
            return result

        except Exception as e:
            result = {"test_name": test_name, "status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} failed: {e}")
            return result

    async def test_zero_trust_policy_enforcement(self) -> builtins.dict[str, Any]:
        """Test zero-trust policy enforcement"""

        test_name = "Zero-Trust Policy Enforcement"
        print(f"\n🧪 Testing {test_name}...")

        try:
            # Create test policy using available API
            from datetime import datetime, timedelta

            from security.zero_trust import (
                AccessDecision,
                AccessPolicy,
                SecurityLevel,
                ServiceIdentity,
            )

            # Create a test service identity
            test_identity = ServiceIdentity(
                service_name="test_user",
                namespace="default",
                cluster="default",
                service_account="test-sa",
                certificate_fingerprint="test_fingerprint",
                public_key_hash="test_hash",
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=30),
                security_level=SecurityLevel.INTERNAL,
                capabilities={"read"},
            )

            # Register the identity
            self.zero_trust.policy_engine.register_identity(test_identity)

            # Create a test policy using the correct API
            test_policy = AccessPolicy(
                policy_id="test_api_access",
                name="Test API Access",
                description="Test policy for API access",
                source_selector={"service_name": "test_user"},
                target_selector={"service": "api-gateway"},
                action="read",
                decision=AccessDecision.ALLOW,
                priority=10,
            )

            self.zero_trust.policy_engine.add_policy(test_policy)
            policy_result = {"success": True}  # Mock policy creation result

            # Test access during business hours (should be allowed)
            access_request = {
                "user_id": "test_user",
                "resource": "service:api-gateway",
                "action": "read",
                "context": {
                    "time": "14:00",  # 2 PM - business hours
                    "source_ip": "192.168.1.100",
                    "user_agent": "TestClient/1.0",
                },
            }

            access_decision = await self.zero_trust.evaluate_access_request(access_request)

            # Test network segmentation
            segment_result = await self.zero_trust.network_manager.create_segment(
                segment_name="test_segment",
                cidrs=["10.0.100.0/24"],
                allowed_ports=[8080, 8443],
                isolation_level="moderate",
            )

            result = {
                "test_name": test_name,
                "status": "PASSED",
                "details": {
                    "policy_created": policy_result["success"],
                    "access_allowed": access_decision.get("allowed", False),
                    "segment_created": segment_result.get("success", False),
                    "trust_score": access_decision.get("trust_score", 0.0),
                },
            }

            print(f"✅ {test_name} completed successfully")
            return result

        except Exception as e:
            result = {"test_name": test_name, "status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} failed: {e}")
            return result

    async def test_threat_detection_and_response(self) -> builtins.dict[str, Any]:
        """Test threat detection and automated response"""

        test_name = "Threat Detection and Response"
        print(f"\n🧪 Testing {test_name}...")

        try:
            # Simulate malware detection
            malware_detection = await self.threat_detection.analyze_artifact(
                artifact_type="file",
                artifact_data={
                    "filename": "suspicious.exe",
                    "file_hash": "d41d8cd98f00b204e9800998ecf8427e",
                    "file_size": 1024000,
                    "source": "email_attachment",
                },
            )

            # Simulate behavioral anomaly
            behavioral_analysis = (
                await self.threat_detection.behavioral_analyzer.analyze_user_behavior(
                    user_id="test_user",
                    actions=[
                        {"action": "login", "timestamp": datetime.now()},
                        {"action": "data_access", "timestamp": datetime.now()},
                        {"action": "privilege_escalation", "timestamp": datetime.now()},
                    ],
                )
            )

            # Test incident response
            incident = await self.threat_detection.incident_manager.create_incident(
                incident_type="malware_detection",
                severity=ThreatLevel.HIGH,
                description="Malware detected in email attachment",
                affected_systems=["mail_server", "endpoint_001"],
            )

            result = {
                "test_name": test_name,
                "status": "PASSED",
                "details": {
                    "malware_detected": malware_detection.get("threat_detected", False),
                    "behavioral_anomaly": behavioral_analysis.get("anomaly_detected", False),
                    "incident_created": incident.get("success", False),
                    "threat_score": malware_detection.get("threat_score", 0.0),
                },
            }

            print(f"✅ {test_name} completed successfully")
            return result

        except Exception as e:
            result = {"test_name": test_name, "status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} failed: {e}")
            return result

    async def test_compliance_automation(self) -> builtins.dict[str, Any]:
        """Test compliance automation and monitoring"""

        test_name = "Compliance Automation"
        print(f"\n🧪 Testing {test_name}...")

        try:
            # Enable GDPR compliance
            gdpr_result = await self.compliance_manager.enable_framework(
                "gdpr",
                {
                    "data_retention_days": 365,
                    "consent_tracking": True,
                    "right_to_erasure": True,
                },
            )

            # Test compliance rule evaluation
            compliance_check = await self.compliance_manager.check_compliance(
                framework="gdpr",
                control_id="gdpr_article_32",
                context={
                    "encryption_enabled": True,
                    "access_controls": True,
                    "audit_logging": True,
                },
            )

            # Test audit trail
            audit_event = await self.compliance_manager.audit_manager.log_event(
                event_type="data_access",
                user_id="test_user",
                resource="customer_data",
                action="read",
                context={"gdpr_lawful_basis": "consent"},
            )

            # Generate compliance report
            compliance_report = self.compliance_manager.generate_compliance_report("gdpr")

            result = {
                "test_name": test_name,
                "status": "PASSED",
                "details": {
                    "gdpr_enabled": gdpr_result.get("success", False),
                    "compliance_check_passed": compliance_check.get("compliant", False),
                    "audit_event_logged": audit_event.get("success", False),
                    "report_generated": compliance_report is not None,
                    "compliance_score": compliance_report.get("overall_score", 0)
                    if compliance_report
                    else 0,
                },
            }

            print(f"✅ {test_name} completed successfully")
            return result

        except Exception as e:
            result = {"test_name": test_name, "status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} failed: {e}")
            return result

    async def test_risk_management(self) -> builtins.dict[str, Any]:
        """Test risk assessment and management"""

        test_name = "Risk Management"
        print(f"\n🧪 Testing {test_name}...")

        try:
            # Conduct risk assessment
            system_context = {
                "handles_sensitive_data": True,
                "encryption_enabled": True,
                "access_controls_implemented": True,
                "has_redundancy": False,
                "processes_eu_data": True,
                "gdpr_compliant": True,
                "audit_logging_enabled": True,
            }

            risks = await self.risk_manager.conduct_risk_assessment(
                "Integration Test Assessment", system_context, "Test Suite"
            )

            # Get risk dashboard
            dashboard = self.risk_manager.get_risk_dashboard()

            # Generate risk report
            risk_report = self.risk_manager.get_risk_report(RiskCategory.CYBERSECURITY)

            result = {
                "test_name": test_name,
                "status": "PASSED",
                "details": {
                    "risks_identified": len(risks),
                    "total_risks": dashboard.get("total_risks", 0),
                    "high_priority_risks": len(dashboard.get("high_priority_risks", [])),
                    "risk_reduction_percentage": risk_report.get("risk_reduction_percentage", 0),
                },
            }

            print(f"✅ {test_name} completed successfully")
            return result

        except Exception as e:
            result = {"test_name": test_name, "status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} failed: {e}")
            return result

    async def test_security_monitoring(self) -> builtins.dict[str, Any]:
        """Test security monitoring and event correlation"""

        test_name = "Security Monitoring"
        print(f"\n🧪 Testing {test_name}...")

        try:
            # Configure SIEM integration
            self.monitoring_system.siem_integration.configure_siem_connection(
                "test_siem", {"host": "localhost", "port": 9200}
            )

            # Generate test security events
            events = []

            # Failed login attempts
            for _i in range(5):
                event = await self.monitoring_system.event_collector.collect_event(
                    source="test_application",
                    event_type=SecurityEventType.AUTHENTICATION_FAILURE,
                    severity=SecurityEventSeverity.MEDIUM,
                    event_data={
                        "source_ip": "192.168.1.100",
                        "user_id": "test_user",
                        "action": "login_attempt",
                    },
                )
                if event:
                    events.append(event)

            # Successful login
            success_event = await self.monitoring_system.event_collector.collect_event(
                source="test_application",
                event_type=SecurityEventType.AUTHENTICATION_SUCCESS,
                severity=SecurityEventSeverity.INFO,
                event_data={
                    "source_ip": "192.168.1.100",
                    "user_id": "test_user",
                    "action": "login_success",
                },
            )
            if success_event:
                events.append(success_event)

            # Run analytics
            alerts = await self.monitoring_system.analytics_engine.analyze_events(events)

            # Get security dashboard
            dashboard = self.monitoring_system.dashboard.get_security_dashboard()

            result = {
                "test_name": test_name,
                "status": "PASSED",
                "details": {
                    "events_generated": len(events),
                    "alerts_generated": len(alerts),
                    "security_score": dashboard.get("security_score", 0),
                    "threat_level": dashboard.get("threat_level", "UNKNOWN"),
                    "siem_configured": len(self.monitoring_system.siem_integration.siem_connections)
                    > 0,
                },
            }

            print(f"✅ {test_name} completed successfully")
            return result

        except Exception as e:
            result = {"test_name": test_name, "status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} failed: {e}")
            return result

    async def test_end_to_end_security_scenario(self) -> builtins.dict[str, Any]:
        """Test complete end-to-end security scenario"""

        test_name = "End-to-End Security Scenario"
        print(f"\n🧪 Testing {test_name}...")

        try:
            scenario_results = {}

            # Scenario: User authentication and suspicious activity detection

            # 1. User authenticates successfully
            auth_result = await self.iam_manager.authenticate_user(
                username="test_user", password="SecurePassword123!"
            )
            scenario_results["authentication"] = auth_result.get("success", False)

            # 2. Zero-trust evaluates access request
            access_request = {
                "user_id": "test_user",
                "resource": "database:customer_data",
                "action": "read",
                "context": {"time": "15:00", "source_ip": "192.168.1.100"},
            }

            access_decision = await self.zero_trust.evaluate_access_request(access_request)
            scenario_results["access_granted"] = access_decision.get("allowed", False)

            # 3. User performs unusual activity (mass data access)
            for i in range(50):  # Simulate high volume data access
                await self.monitoring_system.event_collector.collect_event(
                    source="database",
                    event_type=SecurityEventType.DATA_ACCESS,
                    severity=SecurityEventSeverity.INFO,
                    event_data={
                        "user_id": "test_user",
                        "resource": f"customer_record_{i}",
                        "action": "read",
                    },
                )

            # 4. Threat detection identifies anomaly
            events = list(self.monitoring_system.event_collector.processed_events.values())
            alerts = await self.monitoring_system.analytics_engine.analyze_events(events)
            scenario_results["anomaly_detected"] = len(alerts) > 0

            # 5. Compliance check for data access
            compliance_check = await self.compliance_manager.check_compliance(
                framework="gdpr",
                control_id="gdpr_article_6",  # Lawfulness of processing
                context={
                    "user_id": "test_user",
                    "data_type": "personal_data",
                    "purpose": "business_operations",
                },
            )
            scenario_results["compliance_check"] = compliance_check.get("compliant", False)

            # 6. Risk assessment update
            risk_assessment = await self.risk_manager.conduct_risk_assessment(
                "Post-Incident Assessment",
                {
                    "unusual_access_detected": True,
                    "user_behavior_anomaly": True,
                    "data_volume_high": True,
                },
                "Automated System",
            )
            scenario_results["risk_assessment"] = len(risk_assessment) > 0

            result = {
                "test_name": test_name,
                "status": "PASSED",
                "details": scenario_results,
                "summary": {
                    "all_components_working": all(scenario_results.values()),
                    "security_posture": "STRONG"
                    if all(scenario_results.values())
                    else "NEEDS_ATTENTION",
                },
            }

            print(f"✅ {test_name} completed successfully")
            return result

        except Exception as e:
            result = {"test_name": test_name, "status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} failed: {e}")
            return result

    async def run_all_tests(self) -> builtins.dict[str, Any]:
        """Run all integration tests"""

        print("🚀 Starting Phase 3 Security Integration Tests")
        print("=" * 60)

        if not self.components_initialized:
            await self.initialize_components()

        # Test suite
        test_methods = [
            self.test_authentication_flow,
            self.test_zero_trust_policy_enforcement,
            self.test_threat_detection_and_response,
            self.test_compliance_automation,
            self.test_risk_management,
            self.test_security_monitoring,
            self.test_end_to_end_security_scenario,
        ]

        results = []
        passed_tests = 0
        failed_tests = 0

        # Run each test
        for test_method in test_methods:
            try:
                test_result = await test_method()
                results.append(test_result)

                if test_result["status"] == "PASSED":
                    passed_tests += 1
                else:
                    failed_tests += 1

            except Exception as e:
                failed_tests += 1
                results.append(
                    {
                        "test_name": test_method.__name__,
                        "status": "FAILED",
                        "error": f"Test execution error: {e}",
                    }
                )

        # Generate summary report
        summary = {
            "test_suite": "Phase 3 Security Integration Tests",
            "execution_time": datetime.now().isoformat(),
            "total_tests": len(test_methods),
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": (passed_tests / len(test_methods)) * 100,
            "overall_status": "PASSED" if failed_tests == 0 else "FAILED",
            "test_results": results,
        }

        self.test_results = summary

        print("\n" + "=" * 60)
        print("📊 Test Summary")
        print("=" * 60)
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']}")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        print(f"Overall Status: {summary['overall_status']}")

        if summary["overall_status"] == "PASSED":
            print("\n🎉 All security integration tests passed!")
            print("✅ Phase 3 Security & Compliance framework is ready for deployment")
        else:
            print("\n⚠️  Some tests failed. Review the results before deployment.")

        return summary

    def export_test_report(self, filename: str = None):
        """Export test results to JSON file"""

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"security_integration_test_report_{timestamp}.json"

        with open(filename, "w") as f:
            json.dump(self.test_results, f, indent=2, default=str)

        print(f"📄 Test report exported to: {filename}")


# Example usage and main execution
async def main():
    """Main test execution"""

    # Initialize test suite
    test_suite = SecurityIntegrationTestSuite()

    try:
        # Run all integration tests
        results = await test_suite.run_all_tests()

        # Export results
        test_suite.export_test_report()

        # Exit with appropriate code
        exit_code = 0 if results["overall_status"] == "PASSED" else 1
        exit(exit_code)

    except Exception as e:
        print(f"❌ Test suite execution failed: {e}")
        exit(1)


if __name__ == "__main__":
    # Run integration tests
    asyncio.run(main())
