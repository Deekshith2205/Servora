// [EXPLAIN] issue #95: Evidence Explorer + Policy References — clickable
// cards that open a real inline preview, replacing the plain-text
// evidence list and chip-only policy references ExplainableAIPanel.jsx
// shipped with in #93. Reuses the existing KB router (issue #17) for
// kb_article previews rather than building a second KB viewer, and the
// new minimal `app/api/records.py` lookups (#95) for order/customer/
// ticket previews.
import { useState } from "react";
import { fetchCustomerRecord, fetchKBArticle, fetchOrderRecord, fetchPaymentRecord, fetchShopifyCustomerRecord, fetchShopifyOrderRecord, fetchTicketRecord } from "../api/client";
import "./EvidenceExplorer.css";

const TYPE_ICON = {
  order: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><path d="M3 6h18"></path><path d="M16 10a4 4 0 0 1-8 0"></path>
    </svg>
  ),
  customer: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle>
    </svg>
  ),
  ticket: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
    </svg>
  ),
  kb_article: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
    </svg>
  ),
  // Shopify integration — a real external store lookup.
  shopify_order: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><path d="M3 6h18"></path><path d="M16 10a4 4 0 0 1-8 0"></path>
    </svg>
  ),
  shopify_customer: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><path d="M3 6h18"></path><path d="M16 10a4 4 0 0 1-8 0"></path>
    </svg>
  ),
  payment: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1" y="4" width="22" height="16" rx="2"></rect><line x1="1" y1="10" x2="23" y2="10"></line>
    </svg>
  ),
};

const FETCHERS = {
  order: fetchOrderRecord,
  customer: fetchCustomerRecord,
  ticket: fetchTicketRecord,
  kb_article: fetchKBArticle,
  shopify_order: fetchShopifyOrderRecord,
  shopify_customer: fetchShopifyCustomerRecord,
  payment: fetchPaymentRecord,
};

function RecordPreview({ type, record }) {
  if (type === "order") {
    return (
      <dl className="ee-preview-fields">
        <dt>Product</dt><dd>{record.product}</dd>
        <dt>Amount</dt><dd>${record.amount.toFixed(2)}</dd>
        <dt>Status</dt><dd>{record.status}</dd>
        <dt>Payment</dt><dd>{record.payment_status}</dd>
        {record.duplicate_of && <><dt>Duplicate of</dt><dd>Order #{record.duplicate_of}</dd></>}
      </dl>
    );
  }
  if (type === "customer") {
    return (
      <dl className="ee-preview-fields">
        <dt>Name</dt><dd>{record.name}</dd>
        <dt>Email</dt><dd>{record.email}</dd>
        <dt>Tier</dt><dd>{record.tier}</dd>
      </dl>
    );
  }
  if (type === "ticket") {
    return (
      <dl className="ee-preview-fields">
        <dt>Subject</dt><dd>{record.subject}</dd>
        <dt>Category</dt><dd>{record.category}</dd>
        <dt>Status</dt><dd>{record.status}</dd>
        <dt>Urgency</dt><dd>{record.urgency}/10</dd>
      </dl>
    );
  }
  if (type === "shopify_order") {
    return (
      <dl className="ee-preview-fields">
        <dt>Order</dt><dd>{record.order_number}</dd>
        <dt>Total</dt><dd>${record.total_price}</dd>
        <dt>Payment</dt><dd>{record.financial_status}</dd>
        <dt>Fulfillment</dt><dd>{record.fulfillment_status || "unfulfilled"}</dd>
      </dl>
    );
  }
  if (type === "shopify_customer") {
    return (
      <dl className="ee-preview-fields">
        <dt>Name</dt><dd>{record.first_name} {record.last_name}</dd>
        <dt>Email</dt><dd>{record.email}</dd>
        <dt>Orders</dt><dd>{record.orders_count}</dd>
      </dl>
    );
  }
  if (type === "payment") {
    return (
      <dl className="ee-preview-fields">
        <dt>Description</dt><dd>{record.description}</dd>
        <dt>Amount</dt><dd>${record.amount.toFixed(2)}</dd>
        <dt>Status</dt><dd>{record.status}</dd>
        <dt>Method</dt><dd>{record.method}</dd>
        <dt>Linked Order</dt><dd>{record.order_id ? `Order #${record.order_id}` : "None — no order was ever created"}</dd>
      </dl>
    );
  }
  // kb_article
  return (
    <div className="ee-preview-kb">
      <p>{record.body}</p>
      {record.tags && <div className="ee-chip-row">{record.tags.split(",").filter(Boolean).map((t) => <span key={t} className="ee-tag">{t}</span>)}</div>}
    </div>
  );
}

function EvidenceCard({ item: evidenceRef }) {
  const [open, setOpen] = useState(false);
  const [record, setRecord] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const toggle = () => {
    setOpen((v) => !v);
    if (!record && !loading) {
      setLoading(true);
      setError(null);
      FETCHERS[evidenceRef.type](evidenceRef.ref_id)
        .then(setRecord)
        .catch((err) => setError(err.message || "Failed to load"))
        .finally(() => setLoading(false));
    }
  };

  return (
    <div className="ee-card">
      <button className="ee-card-header" onClick={toggle} aria-expanded={open}>
        <span className="ee-card-icon">{TYPE_ICON[evidenceRef.type]}</span>
        <span className="ee-card-label">{evidenceRef.label}</span>
        <svg className={`ee-chevron ${open ? "open" : ""}`} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>
      {open && (
        <div className="ee-card-body">
          {loading && <div className="ee-loading">Loading…</div>}
          {error && <div className="ee-error">{error}</div>}
          {record && <RecordPreview type={evidenceRef.type} record={record} />}
        </div>
      )}
    </div>
  );
}

// Real duplicates happen: a genuinely cross-cutting issue (#88's
// parallel fan-out) can have TWO specialists independently look up the
// SAME real record (e.g. both Billing and Order calling
// lookup_shopify_order on the same Shopify order) — found live wiring
// up the Shopify integration, when both specialists produced the exact
// same {type: "shopify_order", ref_id: 5001} ref and React warned about
// a duplicate key. Collapses to one card per real (type, ref_id) pair —
// same fix already applied in utils/investigationEvidence.js's
// dedupeEvidence() for the newer Explainability drawer, just adapted
// here for this component's plain {type, ref_id, label} shape.
function dedupeRefs(refs) {
  const seen = new Set();
  const result = [];
  for (const r of refs) {
    const key = `${r.type}:${r.ref_id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(r);
  }
  return result;
}

export function EvidenceExplorer({ evidenceRefs }) {
  const general = dedupeRefs((evidenceRefs || []).filter((r) => r.type !== "kb_article"));
  return (
    <div className="eap-section">
      <div className="eap-section-label">Evidence Explorer</div>
      {general.length === 0 ? (
        <p className="ee-empty">No tool-derived evidence was recorded for this investigation.</p>
      ) : (
        <div className="ee-card-list">
          {general.map((r) => <EvidenceCard key={`${r.type}-${r.ref_id}`} item={r} />)}
        </div>
      )}
    </div>
  );
}

export function PolicyReferenceExplorer({ policyReferences }) {
  const deduped = dedupeRefs(policyReferences || []);
  if (deduped.length === 0) return null;
  return (
    <div className="eap-section">
      <div className="eap-section-label">Policy References</div>
      <div className="ee-card-list">
        {deduped.map((r) => <EvidenceCard key={`${r.type}-${r.ref_id}`} item={r} />)}
      </div>
    </div>
  );
}
