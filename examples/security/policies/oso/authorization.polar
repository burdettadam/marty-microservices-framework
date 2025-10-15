# User Management Authorization
allow(actor, action, resource) if {
    # Admin users have full access
    actor.has_role("admin")
}

allow(actor, action, resource) if {
    # Managers can read and modify users
    actor.has_role("manager") and
    action in ["read", "update"] and
    resource.type == "user"
}

allow(actor, action, resource) if {
    # Users can read user information
    actor.has_role("user") and
    action == "read" and
    resource.type == "user"
}

allow(actor, action, resource) if {
    # Users can manage their own profile
    actor.has_role("user") and
    resource.type == "user_profile" and
    resource.owner == actor.id
}

allow(actor, action, resource) if {
    # Service accounts for integration
    actor.type == "service" and
    actor.service_name in ["user-service", "notification-service"] and
    resource.type == "user" and
    action in ["read", "create", "update"]
}

# Financial Operations Authorization
allow(actor, action, resource) if {
    # High-value transactions require senior approval
    actor.has_role("finance_manager") and
    action == "approve" and
    resource.type == "transaction" and
    resource.amount > 10000 and
    current_time().hour >= 9 and
    current_time().hour <= 17
}

allow(actor, action, resource) if {
    # Regional access control
    actor.has_role("finance_user") and
    action in ["read", "update"] and
    resource.type == "transaction" and
    actor.region == resource.region
}

allow(actor, action, resource) if {
    # Time-based access for reports
    actor.has_role("analyst") and
    action == "read" and
    resource.type == "financial_report" and
    current_time().hour >= 9 and
    current_time().hour <= 17 and
    current_time().weekday in [1, 2, 3, 4, 5]
}

allow(actor, action, resource) if {
    # MFA required for sensitive operations
    actor.mfa_verified and
    (current_time() - actor.mfa_timestamp) < 300 and
    action in ["create", "update", "delete"] and
    resource.sensitivity == "high"
}

# Emergency Override
allow(actor, action, resource) if {
    actor.has_role("emergency_admin") and
    actor.emergency_mode and
    get_incident_status() == "active"
}

# Helper rules for attribute-based decisions
has_permission(actor, action, resource) if {
    allow(actor, action, resource)
}

# IP-based restrictions
allow(actor, action, resource) if {
    actor.has_role("system_admin") and
    resource.type == "admin_panel" and
    actor.source_ip in ["10.0.0.0/8", "192.168.1.0/24"]
}

# Department-based data isolation
allow(actor, action, resource) if {
    actor.department == resource.department and
    action in ["read", "update"] and
    resource.type == "department_data"
}

# Risk-based transaction approval
allow(actor, action, resource) if {
    actor.has_role("finance_user") and
    action == "create" and
    resource.type == "transaction" and
    resource.amount <= 1000 and
    resource.risk_score < 0.3
}
