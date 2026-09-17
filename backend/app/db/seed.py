"""Seeds the demo database with just enough mock data that every agent has
something real to look up instead of hallucinating an answer.

Run automatically on startup (see app/main.py) if the DB is empty.
"""
from app.auth.password import hash_password
from app.auth.roles import ADMINISTRATOR, CUSTOMER, MANAGER, SUPPORT_AGENT
from app.db.database import SessionLocal
from app.db.models import Channel, Credential, Customer, KBArticle, Order, Room, SystemSetting, Ticket, User

# Real auth: every seeded demo account (2 customers, 3 staff) shares this
# one password so a fresh clone is immediately demoable without an
# out-of-band credential handoff — see Login.jsx's own "Demo accounts"
# hint box, which shows this same value.
_DEMO_PASSWORD = "Demo1234!"


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
    finally:
        db.close()
