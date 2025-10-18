package authz

import rego.v1

# Default deny
default allow := false

# Allow admin users to do anything
allow if {
    input.principal.roles[_] == "admin"
}

# Allow users to access their own resources
allow if {
    input.principal.id == input.resource_owner
    input.action in ["read", "update"]
}

# Allow read access to public resources
allow if {
    input.resource_type == "public"
    input.action == "read"
}

# Service-to-service communication
allow if {
    input.principal.type == "service"
    input.principal.service_name
    input.action in ["read", "write"]
    valid_service_access
}

valid_service_access if {
    # Define service access rules here
    input.principal.service_name in ["user-service", "order-service", "payment-service"]
}

# Role-based access for specific resources
allow if {
    some role in input.principal.roles
    role_permissions[role][input.resource_type][_] == input.action
}

role_permissions := {
    "user": {
        "profile": ["read", "update"],
        "orders": ["read", "create"]
    },
    "moderator": {
        "profile": ["read", "update"],
        "orders": ["read", "create", "update"],
        "reports": ["read", "create"]
    },
    "admin": {
        "profile": ["read", "update", "delete"],
        "orders": ["read", "create", "update", "delete"],
        "reports": ["read", "create", "update", "delete"],
        "users": ["read", "create", "update", "delete"]
    }
}

# Audit decision information
decision_info := {
    "allowed": allow,
    "policy_id": "marty_authz_v1",
    "timestamp": time.now_ns(),
    "principal": input.principal,
    "resource": input.resource,
    "action": input.action
}
