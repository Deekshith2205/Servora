"""One-off sanity check for issue #18 ("[P4] Booking Agent: slot-filling +
room availability + AI_DRAFTED state") — acceptance criteria: a full
booking conversation produces an AI_DRAFTED row with correct pricing.

Run from backend/ with your .env filled in (uses the real DB via
app.db.database — make sure the app has run at least once to seed it):
    ./.venv/Scripts/python.exe -m scripts.check_booking

Simulates the conversation turn-by-turn exactly as POST /api/booking would
receive it (frontend resends the full transcript each turn — see
app/agents/booking.py's docstring) rather than actually prompting for
input, since this is a scripted sanity check, not an interactive demo.
"""
from app.agents.booking import run_booking_agent
from app.db.database import SessionLocal
from app.db.seed import seed_if_empty

SCRIPTED_TURNS = [
    "I'd like to book a deluxe room for 2 guests, checking in 2026-12-01 and out 2026-12-04.",
    "Yes, please go ahead and book it.",
]


def main() -> None:
    seed_if_empty()
    db = SessionLocal()
    try:
        messages: list[dict] = []
        for turn in SCRIPTED_TURNS:
            messages.append({"role": "user", "content": turn})
            result = run_booking_agent(db, customer_id=1, messages=messages)
            messages.append({"role": "assistant", "content": result.reply})

            print(f"customer:  {turn}")
            print(f"agent:     {result.reply}")
            print(f"tools:     {result.used_tools}")
            if result.booking:
                print(
                    f"BOOKING:   id={result.booking.id} status={result.booking.status} "
                    f"total=${result.booking.total_price}"
                )
            print("-" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    main()
