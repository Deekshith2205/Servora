"""[RBAC] issues #217-#220 — the real, centralized visibility rules
every investigation/evidence/escalation-serving endpoint shares, rather
than each route re-deriving its own ad hoc ownership check. Written
down here explicitly because the underlying rules were built across
separate phases (#182-#190) and could otherwise silently drift between
two route handlers that are supposed to agree.
"""
from app.auth.dependency import CurrentActor
from app.auth.permissions import has_permission
from app.auth.roles import CUSTOMER
from app.db.models import Investigation


def can_view_investigation(actor: CurrentActor, investigation: Investigation) -> bool:
    """[RBAC] issue #217. A Customer may view ONLY an investigation
    whose `customer_id` is genuinely their own. Any staff role holding
    `view_investigation_board` may view ANY investigation — no per-
    staff-member data scoping, matching how the Investigation Board
    already works today. The ONE function both the customer-facing
    (`GET .../by-ticket/{id}`) and staff-facing (`GET .../{id}`)
    endpoints call, so the rule can never drift between the two."""
    if actor.role == CUSTOMER:
        return actor.customer_id is not None and actor.customer_id == investigation.customer_id
    return has_permission(actor.role, "view_investigation_board")


def can_view_evidence(actor: CurrentActor, resource_customer_id: int | None) -> bool:
    """[RBAC] issue #218. Staff holding `view_evidence` may view ANY
    evidence record (order/customer/ticket). A Customer may view ONLY a
    record that is genuinely their own — `resource_customer_id` is the
    real owning customer id the CALLER resolves (an order's own
    `customer_id`, a ticket's own `customer_id`, or a customer record's
    own `id`) before asking this function. Covers the exact overlap
    issue #188's own technical requirement named: `GET /api/records/
    customers/{id}` serves BOTH the staff evidence case and issue
    #184's customer-self-profile case through the SAME endpoint and the
    SAME check."""
    if has_permission(actor.role, "view_evidence"):
        return True
    if actor.role == CUSTOMER and actor.customer_id is not None and resource_customer_id is not None:
        return actor.customer_id == resource_customer_id
    return False


def can_view_explanation(actor: CurrentActor, investigation: Investigation) -> bool:
    """[RBAC] issue #219. A real, INTENTIONAL asymmetry, documented
    explicitly rather than left as an unexplained inconsistency: a
    Customer who genuinely owns an investigation (passes
    `can_view_investigation()`) still cannot reach the FULL
    Explainability Panel data — only staff holding `view_explainability`
    can. The customer-facing equivalent is the narrower summary already
    served by `GET .../by-ticket/{id}` (issue #183, Track B), not this
    endpoint."""
    return can_view_investigation(actor, investigation) and has_permission(actor.role, "view_explainability")


def can_view_escalation_queue(actor: CurrentActor) -> bool:
    """[RBAC] issue #220. A Manager (`view_escalation_queue`) or a
    Support Agent/Administrator (`handle_escalations`) may both list
    the real escalation queue — only `handle_escalations` holders may
    act on it (see `can_handle_escalation()` below)."""
    return has_permission(actor.role, "handle_escalations") or has_permission(actor.role, "view_escalation_queue")


def can_handle_escalation(actor: CurrentActor) -> bool:
    return has_permission(actor.role, "handle_escalations")
