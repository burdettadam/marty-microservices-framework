package authz.abac

import future.keywords.if
import future.keywords.in

# Default deny
default allow = false

# Financial operations with attribute-based access control

# High-value transactions require senior approval during business hours
allow if {
    input.action == "POST"
    startswith(input.resource, "/api/v1/transactions/")
    input.principal.roles[_] in ["finance_manager", "cfo"]
    input.environment.transaction_amount > 10000
    business_hours
}

# Regional access control - users can only access data from their region
allow if {
    input.action in ["GET", "PUT"]
    startswith(input.resource, "/api/v1/transactions/")
    input.principal.roles[_] in ["finance_user", "accountant"]
    input.principal.region == input.environment.resource_region
}

# Time-based access for sensitive financial reports
allow if {
    input.action == "GET"
    startswith(input.resource, "/api/v1/reports/financial/")
    input.principal.roles[_] in ["analyst", "auditor", "finance_manager"]
    business_hours
    weekday
}

# IP-based restrictions for administrative access
allow if {
    startswith(input.resource, "/api/v1/admin/")
    input.principal.roles[_] in ["admin", "system_admin"]
    trusted_network
}

# MFA required for sensitive operations
allow if {
    startswith(input.resource, "/api/v1/sensitive/")
    input.action in ["POST", "PUT", "DELETE"]
    input.principal.mfa_verified == true
    input.principal.mfa_age < 300  # MFA must be within 5 minutes
}

# Department-based data isolation
allow if {
    startswith(input.resource, "/api/v1/data/")
    input.action in ["GET", "POST", "PUT"]
    input.principal.department == input.environment.resource_department
}

# Emergency override with incident verification
allow if {
    input.principal.roles[_] == "emergency_admin"
    input.principal.emergency_mode == true
    input.environment.incident_active == true
}

# Read-only access for auditors to all financial data
allow if {
    input.action == "GET"
    startswith(input.resource, "/api/v1/")
    input.principal.roles[_] == "auditor"
    business_hours
}

# Helper functions

business_hours if {
    hour := time.clock(time.now_ns())[0]
    hour >= 9
    hour <= 17
}

weekday if {
    day := time.weekday(time.now_ns())
    day in [1, 2, 3, 4, 5]  # Monday to Friday
}

trusted_network if {
    net.cidr_contains("10.0.0.0/8", input.environment.source_ip)
}

trusted_network if {
    net.cidr_contains("192.168.1.0/24", input.environment.source_ip)
}

# Risk-based access control
high_risk_transaction if {
    input.environment.transaction_amount > 50000
}

high_risk_transaction if {
    input.environment.transaction_country in ["high_risk_countries"]
}

# Allow low-risk transactions with standard approval
allow if {
    input.action == "POST"
    startswith(input.resource, "/api/v1/transactions/")
    input.principal.roles[_] in ["finance_user", "accountant"]
    not high_risk_transaction
    input.environment.transaction_amount <= 1000
}
