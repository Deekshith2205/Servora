"""[RBAC] issue #171 — Role Foundation.

The 4 roles the whole RBAC epic is built around, defined ONCE here so
neither the backend nor (via GET /api/auth/permissions) the frontend
ever types a role string independently. Plain Python constants, not a
DB-backed lookup table — same "fixed-vocabulary-as-a-string-column"
convention `Order.status`/`Ticket.status` already use throughout this
codebase, not a new pattern; a real 5th role would be a deliberate code
change, not a migration.
"""

CUSTOMER = "customer"
SUPPORT_AGENT = "support_agent"
MANAGER = "manager"
ADMINISTRATOR = "administrator"

ALL_ROLES = {CUSTOMER, SUPPORT_AGENT, MANAGER, ADMINISTRATOR}

# "Any real staff member, not a customer" — used repeatedly by later
# permission/route-gating logic instead of re-listing the 3 staff roles
# every time.
STAFF_ROLES = {SUPPORT_AGENT, MANAGER, ADMINISTRATOR}
