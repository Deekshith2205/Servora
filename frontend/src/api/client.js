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

export function sendChatMessage(customerId, message, streamKey = null) {
  // [SWARM] issue #79: streamKey is optional/additive — omitting it
  // reproduces the exact previous request body.
  const body = { customer_id: customerId, message };
  if (streamKey) body.stream_key = streamKey;
  return request("/api/chat", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// [SWARM] issue #79: opens the real-time SSE stream for one in-flight
// investigation. Returns a cleanup function — call it to close the
// connection (component unmount, or once the stream naturally ends).
// Plain EventSource, not a wrapper library: the format is simple and
// EventSource's built-in auto-reconnect is explicitly NOT wanted here —
// a stream_key is single-use (one investigation), so a reconnect after
// "end"/"timeout" would just hang forever against an already-cleaned-up
// server-side queue.
export function openInvestigationStream(streamKey, { onStep, onDone, onEnd }) {
  const source = new EventSource(`${BASE_URL}/api/investigations/stream/${streamKey}`);

  source.addEventListener("message", (evt) => {
    try {
      const data = JSON.parse(evt.data);
      if (data.type === "step") onStep?.(data);
      else if (data.type === "done") onDone?.(data);
    } catch {
      // Malformed event — ignore rather than crash the live view over one bad frame.
    }
  });
  source.addEventListener("end", () => { onEnd?.(); source.close(); });
  source.addEventListener("timeout", () => { onEnd?.(); source.close(); });
  source.onerror = () => { onEnd?.(); source.close(); };

  return () => source.close();
}

export function fetchEscalations() {
  return request("/api/escalations");
}

export function fetchInbox(channel = null, q = null, status = null) {
  const params = new URLSearchParams();
  if (channel) params.append("channel", channel);
  if (q) params.append("q", q);
  if (status && status !== "all") params.append("status", status);
  
  const queryStr = params.toString();
  const url = queryStr ? `/api/inbox?${queryStr}` : "/api/inbox";
  return request(url);
}

export function fetchChannels() {
  return request("/api/channels");
}

export function fetchInboxDetail(ticketId) {
  return request(`/api/inbox/${ticketId}`);
}

export function fetchResolvedHistory() {
  return request("/api/tickets/resolved");
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

export function assignEscalation(ticketId, assignedTo) {
  return request(`/api/escalations/${ticketId}/assign`, {
    method: "POST",
    body: JSON.stringify({ assigned_to: assignedTo }),
  });
}

export function closeEscalation(ticketId) {
  return request(`/api/escalations/${ticketId}/close`, {
    method: "POST",
  });
}

export function approveKBArticle(draft) {
  return request("/api/kb-articles", {
    method: "POST",
    body: JSON.stringify({ title: draft.title, body: draft.body, tags: draft.tags }),
  });
}

export function sendBookingMessage(customerId, messages) {
  return request("/api/booking", {
    method: "POST",
    body: JSON.stringify({ customer_id: customerId, messages }),
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

export function fetchInvestigations(limit = 50) {
  return request(`/api/investigations?limit=${limit}`);
}

export function fetchInvestigation(investigationId) {
  return request(`/api/investigations/${investigationId}`);
}

export function fetchInvestigationByTicket(ticketId) {
  return request(`/api/investigations/by-ticket/${ticketId}`);
}

export function fetchAgentPerformanceMetrics() {
  return request("/api/investigations/metrics/agents");
}

// [EXPLAIN] issue #92.
export function fetchExplanation(investigationId) {
  return request(`/api/investigations/${investigationId}/explanation`);
}

// [EXPLAIN] issue #95 — Evidence Explorer inline-preview lookups.
export function fetchOrderRecord(orderId) {
  return request(`/api/records/orders/${orderId}`);
}

export function fetchCustomerRecord(customerId) {
  return request(`/api/records/customers/${customerId}`);
}

export function fetchTicketRecord(ticketId) {
  return request(`/api/records/tickets/${ticketId}`);
}

export function fetchKBArticle(articleId) {
  return request(`/api/kb-articles/${articleId}`);
}

// [Explainability #123] — the drill-down drawer's data source.
// `evidenceId` is "{step_number}:{index}" (see EvidenceDetailOut's
// backend docstring for why).
export function fetchEvidenceDetail(investigationId, evidenceId) {
  return request(`/api/investigations/${investigationId}/evidence/${evidenceId}`);
}

// Shopify integration — Settings -> Integrations.
export function fetchShopifyStatus() {
  return request("/api/integrations/shopify/status");
}

export function connectShopify(storeUrl, accessToken) {
  return request("/api/integrations/shopify/connect", {
    method: "POST",
    body: JSON.stringify({ store_url: storeUrl, access_token: accessToken }),
  });
}

export function disconnectShopify() {
  return request("/api/integrations/shopify/disconnect", { method: "POST" });
}

// Shopify evidence inline-preview lookups — same role as
// fetchOrderRecord/fetchCustomerRecord above, backed by a live Shopify
// API call instead of Servora's own DB.
export function fetchShopifyOrderRecord(orderId) {
  return request(`/api/records/shopify-orders/${orderId}`);
}

export function fetchShopifyCustomerRecord(customerId) {
  return request(`/api/records/shopify-customers/${customerId}`);
}
