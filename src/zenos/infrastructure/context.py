"""Per-request context variables for ZenOS infrastructure layer."""
from contextvars import ContextVar

# Current partner ID for per-request Firestore collection routing.
# Set by ApiKeyMiddleware in the interface layer; read by repositories.
current_partner_id: ContextVar[str] = ContextVar("current_partner_id", default="")
