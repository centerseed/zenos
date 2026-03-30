"""Per-request context variables for ZenOS infrastructure layer."""
from contextvars import ContextVar

# Current partner ID for per-request Firestore collection routing.
# Set by ApiKeyMiddleware in the interface layer; read by repositories.
current_partner_id: ContextVar[str] = ContextVar("current_partner_id", default="")
current_partner_roles: ContextVar[list[str]] = ContextVar("current_partner_roles", default=[])
current_partner_department: ContextVar[str] = ContextVar("current_partner_department", default="all")
current_partner_is_admin: ContextVar[bool] = ContextVar("current_partner_is_admin", default=False)
