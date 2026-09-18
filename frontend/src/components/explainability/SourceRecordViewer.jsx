// [Explainability #120]: "Section 2: Source Record" — the actual
// order/customer/ticket/KB-article row an evidence item points to,
// rendered as a real structured card.
//
// Reuses the EXACT SAME fetchers EvidenceExplorer.jsx already uses
// (api/client.js) — this is a richer rendering of the same data, not a
// second fetch path. See EvidenceDetailOut's backend docstring for why
// the evidence-detail endpoint itself doesn't re-embed this data.
import { useEffect, useState } from "react";
import {
  fetchCustomerRecord,
  fetchKBArticle,
  fetchOrderRecord,
  fetchPaymentRecord,
  fetchShopifyCustomerRecord,
  fetchShopifyOrderRecord,
  fetchTicketRecord,
} from "../../api/client";

const FETCHERS = {
  order: fetchOrderRecord,
  customer: fetchCustomerRecord,
  ticket: fetchTicketRecord,
  kb_article: fetchKBArticle,
  payment: fetchPaymentRecord,
  shopify_order: fetchShopifyOrderRecord,
  shopify_customer: fetchShopifyCustomerRecord,
};

const TYPE_LABEL = {
  order: "Order Record",
  customer: "Customer Record",
  ticket: "Ticket Record",
  kb_article: "Knowledge Base Article",
  payment: "Payment Record",
  shopify_order: "Shopify Order (Live)",
  shopify_customer: "Shopify Customer (Live)",
};

function Field({ label, value }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="expl-field">
      <span className="expl-field-label">{label}</span>
      <span className="expl-field-value">{value}</span>
    </div>
  );
}

function OrderFields({ record }) {
  return (
    <>
      <Field label="Order ID" value={`#${record.id}`} />
      <Field label="Product" value={record.product} />
      <Field label="Amount" value={`$${record.amount.toFixed(2)}`} />
      <Field label="Status" value={record.status} />
      <Field label="Payment Status" value={record.payment_status} />
      <Field label="Failure Reason" value={record.failure_reason} />
      {record.duplicate_of && <Field label="Duplicate Of" value={`Order #${record.duplicate_of}`} />}
    </>
  );
}

function CustomerFields({ record }) {
  // Deliberately no "Account Status" row — that isn't a real field
  // anywhere in this schema (no active/suspended concept on Customer),
  // and this drawer never fabricates data to match a mockup. `tier` and
  // the two real derived fields below (#123) are shown instead.
  const riskClass = record.risk_level ? `expl-risk-${record.risk_level}` : "";
  return (
    <>
      <Field label="Customer ID" value={`#${record.id}`} />
      <Field label="Name" value={record.name} />
      <Field label="Tier" value={record.tier} />
      <Field label="Previous Tickets" value={record.previous_tickets_count} />
      {record.risk_level && (
        <div className="expl-field">
          <span className="expl-field-label">Risk Score</span>
          <span className={`expl-field-value expl-risk-badge ${riskClass}`}>{record.risk_level}</span>
        </div>
      )}
    </>
  );
}

function TicketFields({ record }) {
  return (
    <>
      <Field label="Subject" value={record.subject} />
      <Field label="Category" value={record.category} />
      <Field label="Status" value={record.status} />
      <Field label="Urgency" value={`${record.urgency}/10`} />
      <Field label="Created" value={record.created_at && new Date(record.created_at).toLocaleDateString()} />
    </>
  );
}

function KBFields({ record }) {
  return (
    <>
      <Field label="Title" value={record.title} />
      {record.tags && <Field label="Category" value={record.tags.split(",").filter(Boolean).join(", ")} />}
      <div className="expl-field expl-field-full">
        <span className="expl-field-label">Excerpt</span>
        <p className="expl-kb-excerpt">{record.body}</p>
      </div>
    </>
  );
}

function PaymentFields({ record }) {
  return (
    <>
      <Field label="Payment ID" value={`#${record.id}`} />
      <Field label="Description" value={record.description} />
      <Field label="Amount" value={`$${record.amount.toFixed(2)}`} />
      <Field label="Method" value={record.method} />
      <Field label="Status" value={record.status} />
      <Field label="Type" value={record.payment_type} />
      <Field label="Linked Order" value={record.order_id ? `Order #${record.order_id}` : "None — no order was ever created"} />
      {record.duplicate_of && <Field label="Duplicate Of" value={`Payment #${record.duplicate_of}`} />}
    </>
  );
}

function ShopifyOrderFields({ record }) {
  return (
    <>
      <Field label="Order" value={record.order_number} />
      <Field label="Total" value={record.total_price ? `$${record.total_price}` : null} />
      <Field label="Payment" value={record.financial_status} />
      <Field label="Fulfillment" value={record.fulfillment_status || "unfulfilled"} />
      <Field label="Email" value={record.email} />
    </>
  );
}

function ShopifyCustomerFields({ record }) {
  return (
    <>
      <Field label="Name" value={`${record.first_name || ""} ${record.last_name || ""}`.trim()} />
      <Field label="Email" value={record.email} />
      <Field label="Orders" value={record.orders_count} />
      <Field label="Total Spent" value={record.total_spent ? `$${record.total_spent}` : null} />
    </>
  );
}

const FIELD_COMPONENTS = {
  order: OrderFields,
  customer: CustomerFields,
  ticket: TicketFields,
  kb_article: KBFields,
  payment: PaymentFields,
  shopify_order: ShopifyOrderFields,
  shopify_customer: ShopifyCustomerFields,
};

export default function SourceRecordViewer({ evidenceRef }) {
  const [record, setRecord] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setRecord(null);
    setError(null);
    setLoading(true);
    const fetcher = FETCHERS[evidenceRef.type];
    if (!fetcher) {
      setError(`Unknown evidence type "${evidenceRef.type}"`);
      setLoading(false);
      return;
    }
    fetcher(evidenceRef.ref_id)
      .then(setRecord)
      .catch((err) => setError(err.message || "Failed to load the source record"))
      .finally(() => setLoading(false));
  }, [evidenceRef.type, evidenceRef.ref_id]);

  if (loading) return <div className="expl-loading">Loading source record…</div>;
  if (error) return <div className="expl-error">{error}</div>;
  if (!record) return null;

  const Fields = FIELD_COMPONENTS[evidenceRef.type];
  return (
    <div className="expl-record-card">
      <div className="expl-record-card-label">{TYPE_LABEL[evidenceRef.type]}</div>
      <div className="expl-field-grid">
        <Fields record={record} />
      </div>
    </div>
  );
}
