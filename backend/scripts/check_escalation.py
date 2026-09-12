"""One-off sanity check for issue #12 ("[P2] Implement Escalation Agent +
confidence threshold") — acceptance criteria (interpreted at the
handle_message() level, not the raw HTTP endpoint — see the PR
description for why): handle_message() returns status="escalated" with a
populated (non-stub) handoff packet when confidence is below threshold.

Run from backend/ with your .env filled in:
    ./.venv/Scripts/python.exe -m scripts.check_escalation
"""
from app.db.database import SessionLocal
from app.db.seed import seed_if_empty
from app.orchestrator import handle_message


def main() -> None:
    seed_if_empty()
    db = SessionLocal()
    try:
        # A request no specialist can plausibly fix — should escalate straight
        # from the Planner.
        result = handle_message(db, 1, "I need you to grant a legal exception to your terms of service.")
        print(f"status:  {result.status}")
        print(f"reply:   {result.reply}")
        if result.handoff_packet:
            p = result.handoff_packet
            print(f"situation:            {p.situation}")
            print(f"attempted_fixes:      {p.attempted_fixes}")
            print(f"root_cause_hypothesis: {p.root_cause_hypothesis}")
            print(f"recommended_action:   {p.recommended_action}")
            print(f"urgency:              {p.urgency}")
        else:
            print("(no handoff packet — this request resolved instead of escalating)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
