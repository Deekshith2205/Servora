// [Explainability #122]: "Section 5" — three sub-score progress bars.
// Values come straight from the backend's EvidenceConfidenceBreakdownOut
// (app/api/explanations.py::_evidence_confidence_breakdown()) — this
// component only renders them, it doesn't compute anything itself.

const ROWS = [
  { key: "evidence_quality", label: "Evidence Quality" },
  { key: "data_freshness", label: "Data Freshness" },
  { key: "source_reliability", label: "Source Reliability" },
];

export default function ConfidenceBreakdown({ breakdown }) {
  if (!breakdown) return null;
  return (
    <div className="expl-bar-list">
      {ROWS.map(({ key, label }) => {
        const pct = Math.round(breakdown[key] * 100);
        return (
          <div className="expl-bar-row" key={key}>
            <div className="expl-bar-row-top">
              <span className="expl-bar-label">{label}</span>
              <span className="expl-bar-value">{pct}%</span>
            </div>
            <div className="expl-bar-track">
              <div className="expl-bar-fill" style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
