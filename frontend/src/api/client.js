const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    // FastAPI's HTTPException bodies carry a "detail" string (e.g. issue
    // #18's "Anthropic API key is missing or invalid...") that used to be
    // silently discarded here in favor of a bare status code — surface it
    // when present, since several endpoints now go out of their way to
    // return a specific, readable detail instead of an opaque 500/502.
    let detail = null;
    try {
      detail = (await res.json()).detail;
    } catch {
      // Body wasn't JSON (or was empty) — fall through to the generic message.
    }
    throw new Error(detail || `Request to ${path} failed: ${res.status}`);
  }
  return res.json();
}

export function sendChatMessage(customerId, message) {
  return request("/api/chat", {
    method: "POST",
    body: JSON.stringify({ customer_id: customerId, message }),
  });
}

export function fetchEscalations() {
  return request("/api/escalations");
}

export function fetchEscalationDetail(ticketId) {
  return request(`/api/escalations/${ticketId}`);
}

export function fetchAnalyticsSummary() {
  return request("/api/analytics/summary");
}

export function resolveEscalation(ticketId, resolutionNotes) {
  return request(`/api/escalations/${ticketId}/resolve`, {
    method: "POST",
    body: JSON.stringify({ resolution_notes: resolutionNotes }),
  });
}

export function approveKBArticle(draft) {
  return request("/api/kb-articles", {
    method: "POST",
    body: JSON.stringify({ title: draft.title, body: draft.body, tags: draft.tags }),
  });
}

export function fetchBookings() {
  return request("/api/bookings");
}

export function updateBooking(bookingId, changes) {
  return request(`/api/bookings/${bookingId}`, {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
}

export function confirmBooking(bookingId) {
  return request(`/api/bookings/${bookingId}/confirm`, { method: "POST" });
}
