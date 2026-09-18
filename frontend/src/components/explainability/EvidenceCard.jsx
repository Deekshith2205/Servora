// [Explainability #118]: a real clickable evidence card, replacing the
// plain-text `.ib-evidence-card` prose strings InvestigationBoard.jsx
// used to render. Built from one entry of a step's structured
// `evidence_refs` (already returned by GET /api/investigations/{id},
// just never rendered here before) — see
// utils/investigationEvidence.js::flattenEvidence() for how the parent
// page turns a full investigation into a flat list of these.
import { AgentIcon, agentLabel, ConfidenceBadge } from "../agentMeta.jsx";
import "./EvidenceCard.css";

const TYPE_ICON = {
  order: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><path d="M3 6h18"></path><path d="M16 10a4 4 0 0 1-8 0"></path>
    </svg>
  ),
  customer: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle>
    </svg>
  ),
  ticket: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
    </svg>
  ),
  kb_article: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
    </svg>
  ),
  // Shopify integration — a real external store lookup, visually
  // distinct (shopping-bag glyph) from Servora's own order/customer
  // icons above so it's clear at a glance the evidence came from a
  // connected real store, not this app's own seeded data.
  shopify_order: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><path d="M3 6h18"></path><path d="M16 10a4 4 0 0 1-8 0"></path>
    </svg>
  ),
  shopify_customer: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><path d="M3 6h18"></path><path d="M16 10a4 4 0 0 1-8 0"></path>
    </svg>
  ),
  payment: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1" y="4" width="22" height="16" rx="2"></rect><line x1="1" y1="10" x2="23" y2="10"></line>
    </svg>
  ),
};

function formatTime(isoString) {
  try {
    return new Date(isoString).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

/**
 * @param item — one entry from flattenEvidence(): { evidenceId, ref,
 *   stepNumber, agentName, confidence, usedTools, timestamp }.
 * @param active — true when this is the card currently open in the drawer.
 * @param onClick(evidenceId) — omit for the plain fallback (non-clickable) rendering.
 */
export default function EvidenceCard({ item, active, onClick }) {
  const clickable = typeof onClick === "function";
  const primaryTool = item.usedTools?.[0];
  const extraToolCount = Math.max(0, (item.usedTools?.length || 0) - 1);

  const content = (
    <>
      <span className="evc-icon">{TYPE_ICON[item.ref.type] || <AgentIcon agentName={item.agentName} />}</span>
      <span className="evc-body">
        <span className="evc-title">{item.ref.label}</span>
        <span className="evc-meta">
          <span className="evc-agent">{agentLabel(item.agentName)}</span>
          {item.timestamp && <span className="evc-time">{formatTime(item.timestamp)}</span>}
        </span>
      </span>
      <span className="evc-badges">
        <ConfidenceBadge value={item.confidence} />
        {primaryTool && (
          <span className="evc-tool-badge" title={item.usedTools.join(", ")}>
            {primaryTool}
            {extraToolCount > 0 && ` +${extraToolCount}`}
          </span>
        )}
      </span>
      {clickable && (
        <svg className="evc-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="9 18 15 12 9 6"></polyline>
        </svg>
      )}
    </>
  );

  if (!clickable) {
    return <div className="evc-card evc-static">{content}</div>;
  }

  return (
    <button
      className={`evc-card evc-clickable ${active ? "evc-active" : ""}`}
      onClick={() => onClick(item.evidenceId)}
      aria-pressed={active}
    >
      {content}
    </button>
  );
}
