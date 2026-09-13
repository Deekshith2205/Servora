// [SWARM] issue #79/#85: a tiny cross-page pub-sub for the ONE
// investigation currently streaming live (if any), so Customer Chat
// (which starts a stream) and the Agent Swarm view (which can show it as
// a "LIVE" entry) agree on the same state without needing a React
// Context provider wired through App.jsx for what is, at most, a single
// in-flight investigation at a time — this is a hackathon-scoped app,
// not a multi-tab collaborative one.
//
// Deliberately a plain module-level singleton (not localStorage/
// sessionStorage): this state is meaningful only for the lifetime of one
// in-flight request in this tab, never needs to survive a reload, and
// must never leak to another browser tab.

let state = null; // { streamKey, steps: [], done: null } | null
const listeners = new Set();

function notify() {
  for (const fn of listeners) fn(state);
}

export function startLive(streamKey) {
  state = { streamKey, steps: [], done: null };
  notify();
}

export function appendLiveStep(step) {
  if (!state) return;
  state = { ...state, steps: [...state.steps, step] };
  notify();
}

export function finishLive(doneEvent) {
  if (!state) return;
  state = { ...state, done: doneEvent };
  notify();
}

export function clearLive() {
  state = null;
  notify();
}

export function getLiveState() {
  return state;
}

export function subscribeLive(fn) {
  listeners.add(fn);
  // Push the CURRENT value immediately, not just future changes — a
  // real bug this fixed: AgentSwarmView.jsx unmounts/remounts every time
  // the user switches tabs, so `useState(null)` + only-future-notifications
  // meant a component mounting AFTER startLive() had already been called
  // (the exact "switch to Agent Swarm mid-investigation" demo path) would
  // never learn a stream was active until its NEXT event — missing an
  // already-in-progress or already-finished investigation entirely.
  fn(state);
  return () => listeners.delete(fn);
}
