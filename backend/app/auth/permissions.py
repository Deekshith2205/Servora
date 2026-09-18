"""[RBAC] issue #173 — Permission definitions.

The one authoritative allow-list mapping each role to the named
permissions it holds. Every later route-gating issue (#177 onward) adds
its own real endpoints to the ROUTE side of this — this module is only
ever the DEFINITION side, and deliberately has zero FastAPI/HTTP
imports so it stays reusable by a pure test, `app/auth/dependency.py`,
and (via GET /api/auth/permissions) the frontend's cache, without
dragging in the whole app.

Mirrors the already-proven `SPECIALIST_TOOL_PERMISSIONS` pattern
(app/tools/tool_registry.py) — a single dict as the one real security
boundary, not a rule re-derived ad hoc in every route file.
"""
from app.auth.roles import ADMINISTRATOR, CUSTOMER, MANAGER, SUPPORT_AGENT

# --------------------------------------------------------------------- #
# Customer — Phase 3. Every permission here is paired with a real
# ownership check at the route (actor.customer_id must match the
# resource's own customer_id) — the permission alone only says "a
# Customer can reach this KIND of data," never "any Customer's data."
# --------------------------------------------------------------------- #
_CUSTOMER_PERMISSIONS: set[str] = {
    "view_own_tickets",         # #182 — GET /api/tickets/mine
    "view_own_profile",         # #184 — GET /api/records/customers/{id}, own record only
    "view_own_notifications",   # #185 — GET /api/notifications, own rows only
    "send_chat_message",        # #177 — POST /api/chat, own customer_id only
}

# --------------------------------------------------------------------- #
# Support Agent — Phase 4. Full, unscoped access to every existing
# staff-facing investigation surface — no per-customer data scoping,
# matching how these pages already work today.
# --------------------------------------------------------------------- #
_SUPPORT_AGENT_PERMISSIONS: set[str] = {
    "view_investigation_board",     # #187
    "view_evidence",                # #188
    "view_explainability",          # #189
    "handle_escalations",           # #190 — act (assign/resolve) AND view the queue
    "view_customer_conversations",  # Phase 4's own spec item (Track B builds the UI)
    "view_knowledge_base",          # [RAG] #268 — browse/search the Knowledge Center, read-only
}

# --------------------------------------------------------------------- #
# Manager — Phase 5. Read/oversight permissions, deliberately excluding
# `handle_escalations` (#198's own acceptance criteria: a Manager can
# VIEW the escalation queue via `view_escalation_queue`, never act on
# it) and excluding `view_investigation_board` (#194's own point — a
# Manager reaches the one specific metrics endpoint via `view_analytics`
# instead, not the full Board).
# --------------------------------------------------------------------- #
_MANAGER_PERMISSIONS: set[str] = {
    "view_analytics",           # #193 (also satisfies #194's metrics OR-check, #197's team activity)
    "view_escalation_queue",    # #196 — read-only queue visibility
    "view_knowledge_base",      # [RAG] #268 — same read-only browse/search as Support Agent
}

# --------------------------------------------------------------------- #
# Administrator-only — Phase 6. Real, new write/management surfaces
# that exist ONLY for Administrator; every non-admin-only permission
# above still reaches Administrator via the union below.
# --------------------------------------------------------------------- #
_ADMIN_ONLY_PERMISSIONS: set[str] = {
    "manage_users",             # #200
    "manage_integrations",      # #202
    "manage_knowledge_base",    # #203
    "manage_system_settings",   # #204
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    CUSTOMER: set(_CUSTOMER_PERMISSIONS),
    SUPPORT_AGENT: set(_SUPPORT_AGENT_PERMISSIONS),
    MANAGER: set(_MANAGER_PERMISSIONS),
    # [RBAC] issue #173's own explicit requirement: computed as the UNION
    # of every other role's permissions plus Administrator's own —
    # never hand-duplicated, so a new permission added to any role above
    # automatically reaches Administrator with zero second edit. Proven
    # by issue #199's own dedicated test, re-run against the FULL set
    # this module ends up defining.
    ADMINISTRATOR: (
        _CUSTOMER_PERMISSIONS | _SUPPORT_AGENT_PERMISSIONS | _MANAGER_PERMISSIONS | _ADMIN_ONLY_PERMISSIONS
    ),
}


def has_permission(role: str | None, permission: str) -> bool:
    """The one function every authorization check calls — `role=None`
    (an unresolved/anonymous actor, see `get_current_actor()`) always
    returns `False` for every permission, never a default-allow."""
    return permission in ROLE_PERMISSIONS.get(role, set())


def has_any_permission(role: str | None, *permissions: str) -> bool:
    """For the real OR-gated endpoints this epic's own issues call for
    (e.g. #194's metrics endpoint: `view_investigation_board` OR
    `view_analytics`; #196's escalation queue: `handle_escalations` OR
    `view_escalation_queue`) — centralizes the OR check itself in one
    place rather than each route re-writing `any(...)` inline."""
    return any(has_permission(role, p) for p in permissions)
