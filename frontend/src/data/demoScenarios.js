// Part 9 "Demo Mode": each entry's `message` is written to naturally
// surface a real seeded anomaly (see backend/app/db/seed.py::
// seed_payment_scenarios_if_missing() and the pre-existing order-issue
// seed data) through the real pipeline — selecting one only fills the
// chat input, it never fabricates a canned reply. Grounded in Alice
// Rao's account (the demo customer these scenarios were seeded against).
export const DEMO_SCENARIOS = [
  {
    label: "Double Charge (no order created)",
    message: "I think I was charged twice for my Noise Cancelling Earbuds but I only see one order in my account.",
  },
  {
    label: "Refund Delay",
    message: "I requested a refund for my Desk Lamp almost two weeks ago and still haven't received it.",
  },
  {
    label: "Wrong Item Delivered",
    message: "I ordered a Yoga Mat but received a set of resistance bands instead.",
  },
  {
    label: "Cancelled Order, Not Refunded",
    message: "I cancelled my Air Fryer order over a week ago but the money still hasn't been returned to my card.",
  },
  {
    label: "Package Damaged in Transit",
    message: "My Ceramic Vase Set arrived with two pieces shattered — the box looked crushed in transit.",
  },
  {
    label: "Subscription Charged After Cancellation",
    message: "I cancelled my Premium Membership subscription last week but was just charged again.",
  },
  {
    label: "Missing Delivery (marked delivered, never arrived)",
    message: "My package was marked delivered but never actually arrived. Can you help?",
  },
  {
    label: "Delivery Delayed",
    message: "My headphones haven't shipped in 3 days, any update?",
  },
];
