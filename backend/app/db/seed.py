"""Seeds the demo database with just enough mock data that every agent has
something real to look up instead of hallucinating an answer.

Run automatically on startup (see app/main.py) if the DB is empty.
"""
from app.db.database import SessionLocal
from app.db.models import Customer, KBArticle, Order, Room, Ticket


def seed_if_empty() -> None:
    db = SessionLocal()
    try:
        if db.query(Customer).first():
            return  # already seeded

        alice = Customer(name="Alice Rao", email="alice@example.com", phone="+1-555-0101", tier="vip")
        bob = Customer(name="Bob Nunez", email="bob@example.com", phone="+1-555-0102", tier="standard")
        db.add_all([alice, bob])
        db.flush()

        db.add_all(
            [
                Order(customer_id=alice.id, product="Wireless Headphones", amount=129.99, status="shipped"),
                Order(customer_id=alice.id, product="Phone Case", amount=19.99, status="delivered"),
                # Issue #22: backs demo scenario 2 (see docs/DEMO_SCRIPT.md) —
                # a billing duplicate-charge complaint the Billing specialist
                # can investigate and actually refund. Alice, not Bob, since
                # the Customer Chat UI is hardcoded to DEMO_CUSTOMER_ID=1
                # (CustomerChat.jsx/BookingChat.jsx) — every live-demo
                # scenario has to be something *she* can trigger.
                Order(customer_id=alice.id, product="Bluetooth Speaker", amount=79.99, status="processing"),
                Order(customer_id=bob.id, product="Smart Watch", amount=249.00, status="processing"),
            ]
        )

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

        db.commit()
    finally:
        db.close()
