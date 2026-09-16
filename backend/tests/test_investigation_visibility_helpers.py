"""[RBAC] issues #217 (investigation visibility), #218 (evidence access),
#219 (explainability access), #220 (escalation access) — pure unit
tests of `app/auth/investigation_visibility.py`'s helper functions, no
FastAPI/DB round-trip needed.
"""
from app.auth.dependency import CurrentActor
from app.auth.investigation_visibility import (
    can_handle_escalation,
    can_view_escalation_queue,
    can_view_evidence,
    can_view_explanation,
    can_view_investigation,
)
from app.auth.roles import ADMINISTRATOR, CUSTOMER, MANAGER, SUPPORT_AGENT
from app.db.models import Investigation

_CUSTOMER_1 = CurrentActor(role=CUSTOMER, customer_id=1)
_CUSTOMER_2 = CurrentActor(role=CUSTOMER, customer_id=2)
_ANON = CurrentActor(role=None)
_SUPPORT_AGENT = CurrentActor(role=SUPPORT_AGENT, user_id=1)
_MANAGER = CurrentActor(role=MANAGER, user_id=2)
_ADMIN = CurrentActor(role=ADMINISTRATOR, user_id=3)

_INV_OF_CUSTOMER_1 = Investigation(ticket_id=1, customer_id=1)


# --------------------------------------------------------------------- #
# #217 can_view_investigation
# --------------------------------------------------------------------- #


def test_owning_customer_can_view_their_own_investigation():
    assert can_view_investigation(_CUSTOMER_1, _INV_OF_CUSTOMER_1) is True


def test_other_customer_cannot_view_a_different_customers_investigation():
    assert can_view_investigation(_CUSTOMER_2, _INV_OF_CUSTOMER_1) is False


def test_anonymous_actor_cannot_view_any_investigation():
    assert can_view_investigation(_ANON, _INV_OF_CUSTOMER_1) is False


def test_support_agent_can_view_any_investigation():
    assert can_view_investigation(_SUPPORT_AGENT, _INV_OF_CUSTOMER_1) is True


def test_manager_cannot_view_investigations_lacking_view_investigation_board():
    assert can_view_investigation(_MANAGER, _INV_OF_CUSTOMER_1) is False


def test_administrator_can_view_any_investigation():
    assert can_view_investigation(_ADMIN, _INV_OF_CUSTOMER_1) is True


# --------------------------------------------------------------------- #
# #218 can_view_evidence
# --------------------------------------------------------------------- #


def test_support_agent_can_view_evidence_for_any_customer():
    assert can_view_evidence(_SUPPORT_AGENT, resource_customer_id=1) is True
    assert can_view_evidence(_SUPPORT_AGENT, resource_customer_id=999) is True


def test_customer_can_view_only_their_own_evidence():
    assert can_view_evidence(_CUSTOMER_1, resource_customer_id=1) is True
    assert can_view_evidence(_CUSTOMER_1, resource_customer_id=2) is False


def test_manager_cannot_view_evidence_at_all():
    assert can_view_evidence(_MANAGER, resource_customer_id=1) is False


def test_evidence_check_handles_a_none_resource_customer_id_without_crashing():
    assert can_view_evidence(_CUSTOMER_1, resource_customer_id=None) is False
    assert can_view_evidence(_SUPPORT_AGENT, resource_customer_id=None) is True  # staff grant doesn't depend on it


# --------------------------------------------------------------------- #
# #219 can_view_explanation
# --------------------------------------------------------------------- #


def test_owning_customer_still_cannot_view_the_full_explanation():
    """[RBAC] issue #219's documented, intentional asymmetry: ownership
    alone (which grants can_view_investigation) is NOT enough for the
    full Explainability Panel — only view_explainability holders."""
    assert can_view_investigation(_CUSTOMER_1, _INV_OF_CUSTOMER_1) is True
    assert can_view_explanation(_CUSTOMER_1, _INV_OF_CUSTOMER_1) is False


def test_support_agent_can_view_the_full_explanation():
    assert can_view_explanation(_SUPPORT_AGENT, _INV_OF_CUSTOMER_1) is True


def test_manager_cannot_view_explanation_lacking_both_required_permissions():
    assert can_view_explanation(_MANAGER, _INV_OF_CUSTOMER_1) is False


def test_administrator_can_view_the_full_explanation():
    assert can_view_explanation(_ADMIN, _INV_OF_CUSTOMER_1) is True


# --------------------------------------------------------------------- #
# #220 can_view_escalation_queue / can_handle_escalation
# --------------------------------------------------------------------- #


def test_manager_can_view_but_not_handle_the_escalation_queue():
    assert can_view_escalation_queue(_MANAGER) is True
    assert can_handle_escalation(_MANAGER) is False


def test_support_agent_can_both_view_and_handle_the_escalation_queue():
    assert can_view_escalation_queue(_SUPPORT_AGENT) is True
    assert can_handle_escalation(_SUPPORT_AGENT) is True


def test_administrator_can_both_view_and_handle_the_escalation_queue():
    assert can_view_escalation_queue(_ADMIN) is True
    assert can_handle_escalation(_ADMIN) is True


def test_customer_can_neither_view_nor_handle_the_escalation_queue():
    assert can_view_escalation_queue(_CUSTOMER_1) is False
    assert can_handle_escalation(_CUSTOMER_1) is False
