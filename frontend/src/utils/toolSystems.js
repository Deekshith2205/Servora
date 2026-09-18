// Connected Systems panel (Customer Chat): maps a real tool name — the
// same ones already recorded per-step as InvestigationStep.used_tools —
// to a friendly "which backend system did this touch" label. Purely a
// presentation layer: no new data, just a nicer name for data that
// already exists (see app/tools/tool_registry.py for the real tool list).
export const TOOL_TO_SYSTEM = {
  get_customer: "Customer Database",
  get_customer_orders: "Orders Database",
  get_customer_tickets: "Support Tickets",
  search_kb: "Knowledge Base",
  check_order_issue: "Orders Database",
  check_payment_issue: "Payments Database",
  issue_refund: "Payments Database",
  get_customer_payments: "Payments Database",
  check_payment_anomaly: "Payments Database",
  issue_payment_refund: "Payments Database",
  check_room_availability: "Rooms Database",
  lookup_shopify_order: "Orders Database (Shopify)",
  lookup_shopify_customer: "Customer Database (Shopify)",
  lookup_shopify_fulfillment: "Delivery Tracking (Shopify)",
};

export function systemForTool(toolName) {
  return TOOL_TO_SYSTEM[toolName] || toolName;
}

// One agent's used_tools -> a deduplicated list of real system labels,
// in first-seen order.
export function systemsForTools(usedTools) {
  const seen = new Set();
  const systems = [];
  for (const tool of usedTools || []) {
    const system = systemForTool(tool);
    if (!seen.has(system)) {
      seen.add(system);
      systems.push(system);
    }
  }
  return systems;
}
