"""ZenOS Application — Identity Layer.

Services responsible for workspace context resolution,
permission risk assessment, and policy suggestions.
"""

from .workspace_context import (
    resolve_active_workspace_id,
    active_partner_view,
    build_available_workspaces,
    build_workspace_context_sync,
)
from .permission_risk_service import PermissionRiskService
from .policy_suggestion_service import PolicySuggestionService

__all__ = [
    "resolve_active_workspace_id",
    "active_partner_view",
    "build_available_workspaces",
    "build_workspace_context_sync",
    "PermissionRiskService",
    "PolicySuggestionService",
]
