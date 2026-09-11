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
