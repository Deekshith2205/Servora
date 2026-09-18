"""Seeds the demo database with just enough mock data that every agent has
something real to look up instead of hallucinating an answer.

Run automatically on startup (see app/main.py) if the DB is empty.
"""
from datetime import datetime, timedelta

from app.auth.password import hash_password
from app.auth.roles import ADMINISTRATOR, CUSTOMER, MANAGER, SUPPORT_AGENT
from app.db.database import SessionLocal
from app.db.models import Channel, Credential, Customer, KBArticle, Order, Payment, Room, SystemSetting, Ticket, User

# Real auth: every seeded demo account (2 customers, 3 staff) shares this
# one password so a fresh clone is immediately demoable without an
# out-of-band credential handoff — see Login.jsx's own "Demo accounts"
# hint box, which shows this same value.
_DEMO_PASSWORD = "Demo1234!"

# Marks the payment-scenario backfill's idempotency check — see
# seed_payment_scenarios_if_missing()'s own docstring for why this can't
# just be "if db.query(Customer).first()" like seed_if_empty() itself.
_EARBUDS_DESCRIPTION = "Noise Cancelling Earbuds"


def seed_if_empty() -> None:
    db = SessionLocal()
    try:
        if not db.query(Customer).first():
            _seed_core(db)
        # Runs on every startup, not just a fresh DB — see this
        # function's own docstring. The real deployment's Neon DB was
        # already seeded by many prior sessions before this table
        # existed, so a `db.query(Customer).first()` guard alone would
        # never backfill it there.
        seed_payment_scenarios_if_missing(db)
    finally:
        db.close()


def _seed_core(db) -> None:
    alice = Customer(name="Alice Rao", email="alice@example.com", phone="+1-555-0101", tier="vip")
    bob = Customer(name="Bob Nunez", email="bob@example.com", phone="+1-555-0102", tier="standard")
    db.add_all([alice, bob])
    db.flush()

    db.add_all(
        [
            Credential(actor_type=CUSTOMER, actor_id=alice.id, password_hash=hash_password(_DEMO_PASSWORD)),
            Credential(actor_type=CUSTOMER, actor_id=bob.id, password_hash=hash_password(_DEMO_PASSWORD)),
        ]
    )

    o1 = Order(customer_id=alice.id, product="Wireless Headphones", amount=129.99, status="shipped", payment_status="paid")
    o2 = Order(customer_id=alice.id, product="Phone Case", amount=19.99, status="delivered", payment_status="paid")
    o3 = Order(customer_id=alice.id, product="Bluetooth Speaker", amount=79.99, status="processing", payment_status="paid")
    o4 = Order(customer_id=bob.id, product="Smart Watch", amount=249.00, status="processing", payment_status="paid")

    db.add_all([o1, o2, o3, o4])
    db.flush()

    # Issue #59: Duplicate Payment
    duplicate = Order(
        customer_id=alice.id,
        product="Wireless Headphones",
        amount=129.99,
        status="processing",
        payment_status="paid",
        duplicate_of=o1.id
    )

    # Issue #59: Payment/Fulfillment Mismatch
    mismatch = Order(
        customer_id=alice.id,
        product="Gaming Mouse",
        amount=59.99,
        status="failed",
        payment_status="paid"
    )

    # Issue #60: Cancelled Order
    cancelled_order = Order(
        customer_id=alice.id,
        product="Tablet",
        amount=399.00,
        status="cancelled",
        payment_status="refunded"
    )

    # Issue #60: Inventory Shortfall
    inventory_shortfall = Order(
        customer_id=alice.id,
        product="Mechanical Keyboard",
        amount=149.99,
        status="failed",
        payment_status="paid",
        failure_reason="inventory_shortfall"
    )

    db.add_all([duplicate, mismatch, cancelled_order, inventory_shortfall])
    db.flush()

    db.add_all(
        [
            Ticket(
                customer_id=bob.id,
                category="billing",
                subject="Charged twice",
                message="I was charged twice for my smart watch order.",
                sentiment="negative",
                urgency=8,
                status="open",
            ),
            Ticket(
                customer_id=alice.id,
                category="order",
                subject="Where is my order",
                message="My headphones haven't shipped in 3 days, any update?",
                sentiment="neutral",
                urgency=4,
                status="open",
            ),
            Ticket(
                customer_id=alice.id,
                category="order",
                subject="Order delayed after shipping label creation",
                message="I got a tracking number but the order is delayed after shipping label creation.",
                sentiment="negative",
                urgency=6,
                status="open",
            ),
            Ticket(
                customer_id=bob.id,
                category="order",
                subject="Tracking hasn't updated in days",
                message="My tracking hasn't updated in days and I need this item soon.",
                sentiment="negative",
                urgency=7,
                status="open",
            ),
            Ticket(
                customer_id=alice.id,
                category="order",
                subject="Package stuck at fulfillment stage",
                message="The package appears stuck at the fulfillment stage without any movement.",
                sentiment="negative",
                urgency=5,
                status="open",
            ),
            Ticket(
                customer_id=bob.id,
                category="order",
                subject="Shipment hasn't moved for a week",
                message="My shipment hasn't moved for a week. Can someone check?",
                sentiment="negative",
                urgency=6,
                status="open",
            ),
            # Issue #22: backs demo scenario 3 (see docs/DEMO_SCRIPT.md) —
            # two PRIOR, RESOLVED tickets about the same underlying
            # problem (a package never arriving), so the Planner Agent's
            # "was this already tried and failed?" signal has something
            # real to weigh when the live demo message reports a THIRD
            # occurrence. Deliberately calm/neutral wording on both — the
            # point of this scenario is that a repeated, serious problem
            # must still escalate even without an angry tone.
            Ticket(
                customer_id=alice.id,
                category="order",
                subject="Package never arrived",
                message="My package was marked delivered but never actually arrived. Can you help?",
                sentiment="neutral",
                urgency=5,
                status="resolved",
            ),
            Ticket(
                customer_id=alice.id,
                category="order",
                subject="Second package also never arrived",
                message="Similar to last time, this package also shows delivered but I never received it.",
                sentiment="neutral",
                urgency=5,
                status="resolved",
            ),
        ]
    )

    # [Omnichannel] issue #162: real, coherent conversations on each
    # of the other 4 channels (Live Chat already has plenty above,
    # via the model's own "live_chat" default) — grounded in Alice/
    # Bob's real seeded orders, not lorem-ipsum, same convention
    # issue #22's own seed data already established. Deliberately
    # Ticket rows only, no fabricated Investigation/InvestigationStep
    # rows: this codebase has never seeded a fake reasoning trace for
    # any Ticket (every existing seeded ticket "predates the
    # pipeline," and the Staff Dashboard/Investigation Board already
    # handle that honestly) — inventing one here would mean
    # fabricating AI output that never actually ran, which this
    # project's own conventions consistently avoid. The Inbox
    # (#136) already renders a Ticket with no Investigation
    # correctly (`has_investigation=False`), so this is a real,
    # fully-supported state, not a gap.
    db.add_all(
        [
            Ticket(
                customer_id=alice.id,
                category="order",
                subject="Bluetooth Speaker still processing",
                message="Hi! Just checking in on my Bluetooth Speaker order, it's still showing processing.",
                sentiment="neutral",
                urgency=3,
                status="open",
                channel_key="whatsapp",
            ),
            Ticket(
                customer_id=bob.id,
                category="billing",
                subject="Refund question",
                message="hey do refunds usually take a while? still don't see mine",
                sentiment="neutral",
                urgency=3,
                status="open",
                channel_key="instagram",
            ),
            Ticket(
                customer_id=alice.id,
                category="billing",
                subject="Duplicate charge on headphones",
                message="I think I was charged twice for my Wireless Headphones order — can someone check?",
                sentiment="negative",
                urgency=6,
                status="open",
                channel_key="messenger",
            ),
            Ticket(
                customer_id=bob.id,
                category="order",
                subject="Smart Watch tracking not updating",
                message="Hello, I'm writing to follow up on my Smart Watch order. The tracking information "
                "has not updated in several days and I would appreciate a status check at your earliest "
                "convenience.",
                sentiment="negative",
                urgency=5,
                status="open",
                channel_key="email",
            ),
        ]
    )

    db.add_all(
        [
            KBArticle(
                title="Refund policy",
                body="Refunds are issued to the original payment method within 5-7 business days "
                "once a return or duplicate charge is confirmed.",
                tags="billing,refund",
            ),
            KBArticle(
                title="Order delays",
                body="Orders delayed beyond the estimated ship date are automatically eligible "
                "for a 10% courtesy discount code on request.",
                tags="order,shipping",
            ),
        ]
    )

    db.add_all(
        [
            Room(room_type="standard", price_per_night=89.0, total_count=10),
            Room(room_type="deluxe", price_per_night=139.0, total_count=6),
            Room(room_type="suite", price_per_night=229.0, total_count=2),
        ]
    )

    # [Omnichannel] issue #132: the 5 supported channels. Live Chat is
    # the one channel that genuinely works today (it's the existing
    # /api/chat path), so it seeds "active"; the other 4 seed
    # "not_configured" — an honest starting state, not a claim that
    # they're wired up yet (later Omnichannel phases build the actual
    # adapters).
    db.add_all(
        [
            Channel(key="live_chat", display_name="Live Chat", status="active"),
            Channel(key="email", display_name="Email", status="not_configured"),
            Channel(key="whatsapp", display_name="WhatsApp", status="not_configured"),
            Channel(key="instagram", display_name="Instagram", status="not_configured"),
            Channel(key="messenger", display_name="Facebook Messenger", status="not_configured"),
        ]
    )

    # [RBAC] issue #172: 3 seeded staff identities, one per staff
    # role — real names, real roles. Originally no password (see
    # User's own docstring); now each gets a real Credential row
    # (below) using the same shared demo password as the seeded
    # customers, so every seeded identity is reachable through the
    # real Login.jsx screen, not just the ones a demo role-switcher
    # used to expose.
    jordan = User(name="Jordan Lee", email="jordan.lee@servora.example", role=SUPPORT_AGENT)
    priya = User(name="Priya Shah", email="priya.shah@servora.example", role=MANAGER)
    sam = User(name="Sam Okafor", email="sam.okafor@servora.example", role=ADMINISTRATOR)
    db.add_all([jordan, priya, sam])
    db.flush()

    db.add_all(
        [
            Credential(actor_type="staff", actor_id=jordan.id, password_hash=hash_password(_DEMO_PASSWORD)),
            Credential(actor_type="staff", actor_id=priya.id, password_hash=hash_password(_DEMO_PASSWORD)),
            Credential(actor_type="staff", actor_id=sam.id, password_hash=hash_password(_DEMO_PASSWORD)),
        ]
    )

    # [RBAC] issue #204: 2 real, meaningful starting settings — not a
    # placeholder empty table.
    db.add_all(
        [
            SystemSetting(key="demo_mode", value="true"),
            SystemSetting(key="default_escalation_confidence_threshold", value="0.5"),
            SystemSetting(key="feature_shopify_lookup_enabled", value="true"),
        ]
    )

    db.commit()


def seed_payment_scenarios_if_missing(db) -> None:
    """Backs the "Connected Commerce" demo-polish pass: 6 realistic
    e-commerce complaint scenarios that need a real `Payment` row (see
    models.py::Payment) — a duplicate charge with no order, a stuck
    refund, a wrong item, a cancelled-but-unrefunded order, a damaged
    package, and a subscription charged after cancellation. Grounded in
    Alice's account, matching frontend/src/data/demoScenarios.js.

    Deliberately its OWN idempotency check (an Earbuds payment
    description), not `_seed_core()`'s "any customer exists" guard —
    this table didn't exist for most of this project's history, so the
    real deployment's Neon database already has Alice/Bob seeded from
    many earlier sessions and would never pick this up if it only ran
    inside the empty-database path. Called unconditionally (but safely,
    idempotently) on every startup so an already-seeded environment
    picks this up on its next restart without a manual backfill script.
    """
    alice = db.query(Customer).filter(Customer.email == "alice@example.com").first()
    if alice is None:
        return  # no customers at all yet — _seed_core() will run first and this will run again next startup

    already_seeded = (
        db.query(Payment)
        .filter(Payment.customer_id == alice.id, Payment.description == _EARBUDS_DESCRIPTION)
        .first()
    )
    if already_seeded:
        return

    now = datetime.utcnow()

    # Scenario: charged twice, second charge never created an order.
    earbuds_order = Order(
        customer_id=alice.id, product="Noise Cancelling Earbuds", amount=89.99,
        status="processing", payment_status="paid",
    )
    db.add(earbuds_order)
    db.flush()
    earbuds_payment = Payment(
        customer_id=alice.id, order_id=earbuds_order.id, amount=89.99,
        method="Visa •••• 4242", description=_EARBUDS_DESCRIPTION,
        status="paid", charged_at=now - timedelta(days=3),
    )
    db.add(earbuds_payment)
    db.flush()
    earbuds_duplicate_payment = Payment(
        customer_id=alice.id, order_id=None, amount=89.99,
        method="Visa •••• 4242", description=_EARBUDS_DESCRIPTION,
        status="paid", duplicate_of=earbuds_payment.id, charged_at=now - timedelta(days=3),
    )

    # Scenario: refund requested, still pending past the policy window.
    lamp_order = Order(
        customer_id=alice.id, product="Desk Lamp", amount=34.99,
        status="delivered", payment_status="paid",
    )
    db.add(lamp_order)
    db.flush()
    lamp_payment = Payment(
        customer_id=alice.id, order_id=lamp_order.id, amount=34.99,
        method="Mastercard •••• 1187", description="Desk Lamp",
        status="refund_pending", charged_at=now - timedelta(days=20),
        refund_requested_at=now - timedelta(days=12),
    )

    # Scenario: wrong item delivered.
    wrong_item_order = Order(
        customer_id=alice.id, product="Yoga Mat", amount=24.99,
        status="delivered", payment_status="paid",
    )

    # Scenario: order cancelled but the payment was never refunded
    # (the OPPOSITE of the existing `cancelled_order` seed in
    # _seed_core(), which is already correctly refunded).
    air_fryer_order = Order(
        customer_id=alice.id, product="Air Fryer", amount=119.99,
        status="cancelled", payment_status="paid",
    )
    db.add(air_fryer_order)
    db.flush()
    air_fryer_payment = Payment(
        customer_id=alice.id, order_id=air_fryer_order.id, amount=119.99,
        method="Visa •••• 4242", description="Air Fryer",
        status="paid", charged_at=now - timedelta(days=9),
    )

    # Scenario: package damaged in transit.
    vase_order = Order(
        customer_id=alice.id, product="Ceramic Vase Set", amount=44.99,
        status="delivered", payment_status="paid",
    )

    db.add_all([earbuds_duplicate_payment, lamp_payment, wrong_item_order, air_fryer_payment, vase_order])
    db.flush()

    # Scenario: subscription charged after it was already cancelled —
    # no linked Order at all, a subscription charge isn't a product order.
    subscription_payment = Payment(
        customer_id=alice.id, order_id=None, amount=14.99,
        method="Visa •••• 4242", description="Premium Membership — Monthly",
        status="paid", payment_type="subscription",
        charged_at=now - timedelta(days=2),
        subscription_cancelled_at=now - timedelta(days=5),
    )
    db.add(subscription_payment)

    # Deliberately `status="resolved"` (not "open"): the demo scenario
    # selector's whole point is a customer sending this EXACT complaint
    # live and watching a real investigation run — a matching "open"
    # ticket already sitting in the queue would be redundant, and would
    # also inflate Alice's open-ticket count enough to trip the
    # Planner's own real "too much unresolved history, escalate
    # straight to a human" heuristic (found live while verifying this
    # seed data), defeating the demo's purpose of showing specialist
    # tool-calling. "Resolved" matches issue #22's own established
    # convention for backing-history tickets: a real prior occurrence
    # that's already been handled, not an unrelated duplicate complaint
    # still sitting open.
    db.add_all(
        [
            Ticket(
                customer_id=alice.id,
                category="billing",
                subject="Charged twice for earbuds",
                message="I was charged twice for my Noise Cancelling Earbuds but I only see one order in my account.",
                sentiment="negative",
                urgency=7,
                status="resolved",
            ),
            Ticket(
                customer_id=alice.id,
                category="billing",
                subject="Refund still not received",
                message="I requested a refund for my Desk Lamp almost two weeks ago and still haven't received it.",
                sentiment="negative",
                urgency=6,
                status="resolved",
            ),
            Ticket(
                customer_id=alice.id,
                category="order",
                subject="Received the wrong item",
                message="I ordered a Yoga Mat but received a set of resistance bands instead.",
                sentiment="negative",
                urgency=5,
                status="resolved",
            ),
            Ticket(
                customer_id=alice.id,
                category="billing",
                subject="Cancelled order, no refund",
                message="I cancelled my Air Fryer order over a week ago but the money still hasn't been returned to my card.",
                sentiment="negative",
                urgency=7,
                status="resolved",
            ),
            Ticket(
                customer_id=alice.id,
                category="order",
                subject="Package arrived damaged",
                message="My Ceramic Vase Set arrived with two pieces shattered — the box looked crushed in transit.",
                sentiment="negative",
                urgency=6,
                status="resolved",
            ),
            Ticket(
                customer_id=alice.id,
                category="billing",
                subject="Charged after cancelling subscription",
                message="I cancelled my Premium Membership subscription last week but was just charged again.",
                sentiment="negative",
                urgency=6,
                status="resolved",
            ),
        ]
    )

    db.commit()
