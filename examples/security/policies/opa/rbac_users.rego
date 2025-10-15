package authz.rbac

import future.keywords.if
import future.keywords.in

# Default deny
default allow = false

# Admin users have full access
allow if {
    "admin" in input.principal.roles
}

# Super admin users have unrestricted access
allow if {
    "super_admin" in input.principal.roles
}

# Managers can read and modify user data
allow if {
    input.action in ["GET", "PUT", "PATCH"]
    startswith(input.resource, "/api/v1/users/")
    "manager" in input.principal.roles
}

# Regular users can read user information
allow if {
    input.action == "GET"
    startswith(input.resource, "/api/v1/users/")
    "user" in input.principal.roles
}

# Users can manage their own profile
allow if {
    input.resource == "/api/v1/users/profile"
    input.principal.type == "user"
    input.principal.user_id == input.environment.target_user_id
}

# Service accounts can access user API for integration
allow if {
    startswith(input.resource, "/api/v1/users/")
    input.action in ["GET", "POST", "PUT"]
    input.principal.type == "service"
    input.principal.service_name in [
        "user-service",
        "notification-service",
        "analytics-service"
    ]
}

# Special permissions for user creation
allow if {
    input.action == "POST"
    input.resource == "/api/v1/users"
    "admin" in input.principal.roles
}

# Bulk operations restricted to admins
allow if {
    input.action == "POST"
    input.resource == "/api/v1/users/bulk"
    "admin" in input.principal.roles
}

# User deletion requires super admin
allow if {
    input.action == "DELETE"
    startswith(input.resource, "/api/v1/users/")
    "super_admin" in input.principal.roles
}
