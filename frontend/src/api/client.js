const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`Request to ${path} failed: ${res.status}`);
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
