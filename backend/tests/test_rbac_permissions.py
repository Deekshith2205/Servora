"""[RBAC] issues #171 (role model), #172 (user-role mapping), #173
(permission definitions) — pure unit tests, no FastAPI/DB involved, for
`app/auth/roles.py` and `app/auth/permissions.py`.
"""
from app.auth.permissions import ROLE_PERMISSIONS, has_any_permission, has_permission
from app.auth.roles import ADMINISTRATOR, ALL_ROLES, CUSTOMER, MANAGER, STAFF_ROLES, SUPPORT_AGENT


def test_all_four_roles_are_defined_and_distinct():
    assert ALL_ROLES == {CUSTOMER, SUPPORT_AGENT, MANAGER, ADMINISTRATOR}
    assert len(ALL_ROLES) == 4


def test_staff_roles_excludes_customer():
    assert CUSTOMER not in STAFF_ROLES
    assert STAFF_ROLES == {SUPPORT_AGENT, MANAGER, ADMINISTRATOR}


def test_every_role_has_a_permission_set():
    assert set(ROLE_PERMISSIONS.keys()) == ALL_ROLES
    for role, perms in ROLE_PERMISSIONS.items():
        assert isinstance(perms, set)
        assert len(perms) > 0


def test_customer_permissions_are_self_only():
    perms = ROLE_PERMISSIONS[CUSTOMER]
    assert perms == {"view_own_tickets", "view_own_profile", "view_own_notifications", "send_chat_message"}
    # No staff-only permission leaks into the Customer set.
    assert "manage_users" not in perms
    assert "view_investigation_board" not in perms


def test_support_agent_permissions_cover_investigation_and_evidence():
    perms = ROLE_PERMISSIONS[SUPPORT_AGENT]
    assert {"view_investigation_board", "view_evidence", "view_explainability", "handle_escalations"} <= perms
    assert "manage_users" not in perms
    assert "view_analytics" not in perms


def test_manager_permissions_cover_analytics_and_escalation_queue_only():
    perms = ROLE_PERMISSIONS[MANAGER]
    assert perms == {"view_analytics", "view_escalation_queue", "view_knowledge_base"}
    # A Manager can SEE the escalation queue but never ACT on it directly.
    assert "handle_escalations" not in perms
    assert "view_investigation_board" not in perms


def test_administrator_permissions_are_a_real_computed_union_not_a_duplicate_list():
    """[RBAC] issue #199: Administrator = union of every other role's
    permissions plus admin-only ones — never hand-duplicated."""
    admin = ROLE_PERMISSIONS[ADMINISTRATOR]
    expected = (
        ROLE_PERMISSIONS[CUSTOMER]
        | ROLE_PERMISSIONS[SUPPORT_AGENT]
        | ROLE_PERMISSIONS[MANAGER]
        | {"manage_users", "manage_integrations", "manage_knowledge_base", "manage_system_settings"}
    )
    assert admin == expected


def test_has_permission_true_and_false_cases():
    assert has_permission(ADMINISTRATOR, "manage_users") is True
    assert has_permission(SUPPORT_AGENT, "manage_users") is False


def test_has_permission_with_none_role_is_always_false():
    """The real anonymous/unresolved actor state — never accidentally
    grants anything."""
    assert has_permission(None, "view_own_tickets") is False
    assert has_permission(None, "manage_users") is False


def test_has_permission_with_unknown_role_string_is_false_not_a_crash():
    assert has_permission("not_a_real_role", "view_own_tickets") is False


def test_has_any_permission_true_if_any_match():
    assert has_any_permission(MANAGER, "view_investigation_board", "view_analytics") is True


def test_has_any_permission_false_if_none_match():
    assert has_any_permission(CUSTOMER, "manage_users", "view_analytics") is False


def test_has_any_permission_with_no_permissions_given_is_false():
    assert has_any_permission(ADMINISTRATOR) is False
