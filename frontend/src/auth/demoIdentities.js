import { SUPPORT_AGENT, MANAGER, ADMINISTRATOR } from "./roles";

// Single source of truth for the demo staff/customer identities — shared
// by RoleSwitcher.jsx (header dropdown) and Login.jsx (entry screen) so
// the two never drift out of sync with each other.
export const DEMO_USERS = [
  { id: 1, role: SUPPORT_AGENT, name: "Jordan Lee" },
  { id: 2, role: MANAGER, name: "Priya Shah" },
  { id: 3, role: ADMINISTRATOR, name: "Sam Okafor" },
];

export const DEMO_CUSTOMERS = [
  { id: 1, name: "Alice Rao" },
  { id: 2, name: "Bob Nunez" },
];
