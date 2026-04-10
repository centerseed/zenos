"""ZenOS Domain — Identity Layer Models."""

from __future__ import annotations

from dataclasses import dataclass, field

from .enums import Classification, CLASSIFICATION_ORDER, InheritanceMode


@dataclass
class UserPrincipal:
    user_id: str
    partner_id: str
    role_ids: list[str] = field(default_factory=list)
    department_ids: list[str] = field(default_factory=list)
    is_admin: bool = False


@dataclass
class AgentScope:
    read_classification_max: str = Classification.OPEN.value
    write_classification_max: str = Classification.INTERNAL.value
    allowed_role_ids: list[str] = field(default_factory=list)
    allowed_department_ids: list[str] = field(default_factory=list)
    allowed_entity_ids: list[str] = field(default_factory=list)


@dataclass
class AgentPrincipal:
    agent_id: str
    owner_user_id: str
    partner_id: str
    scope: AgentScope = field(default_factory=AgentScope)


@dataclass
class AccessPolicy:
    classification: str = Classification.OPEN.value
    inheritance_mode: str = InheritanceMode.INHERIT.value
    allowed_role_ids: list[str] = field(default_factory=list)
    allowed_department_ids: list[str] = field(default_factory=list)
    allowed_member_ids: list[str] = field(default_factory=list)

    def validate_transition_from_parent(self, parent_classification: str | None) -> bool:
        if not parent_classification:
            return True
        return CLASSIFICATION_ORDER[self.classification] >= CLASSIFICATION_ORDER[parent_classification]

    def validate_custom_scope(self) -> bool:
        if self.inheritance_mode == InheritanceMode.INHERIT.value:
            return not (self.allowed_role_ids or self.allowed_department_ids or self.allowed_member_ids)
        return True
