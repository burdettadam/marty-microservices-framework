# PetStore Authorization Policy (Oso Polar format)

# Basic pet access rules
allow(actor, "GET", resource) if {
    resource.type == "pet" and
    resource.visibility == "public"
}

allow(actor, "GET", resource) if {
    resource.type == "pet" and
    actor.has_role("user")
}

allow(actor, action, resource) if {
    resource.type == "pet" and
    action in ["POST", "PUT", "DELETE"] and
    actor.has_role("admin")
}

# Order access rules
allow(actor, action, resource) if {
    resource.type == "order" and
    action in ["GET", "POST"] and
    actor.has_role("user")
}

allow(actor, action, resource) if {
    resource.type == "order" and
    (resource.owner_id == actor.id or actor.has_role("admin"))
}

# Admin access rules
allow(actor, action, resource) if {
    resource.path.startswith("/api/v1/admin/") and
    actor.has_role("admin")
}

# Service-to-service access
allow(actor, action, resource) if {
    resource.path.startswith("/api/v1/internal/") and
    actor.type == "service"
}

# Test endpoints
allow(actor, "GET", resource) if {
    resource.path.startswith("/api/v1/test/") and
    actor.has_role("user")
}

# Helper rules
has_permission(actor, action, resource) if {
    allow(actor, action, resource)
}
