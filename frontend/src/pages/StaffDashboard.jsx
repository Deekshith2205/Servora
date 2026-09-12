import { useEffect, useState } from "react";
import { fetchEscalationDetail, fetchEscalations } from "../api/client";

export default function StaffDashboard() {
  const [tickets, setTickets] = useState([]);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    fetchEscalations().then(setTickets).catch((err) => setError(err.message));
  }, []);

  function selectTicket(id) {
    setSelectedId(id);
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    fetchEscalationDetail(id)
      .then(setDetail)
      .catch((err) => setDetailError(err.message))
      .finally(() => setDetailLoading(false));
  }

  return (
    <div className="dashboard-layout">
      <div className="panel">
        <h2>Staff Dashboard — Escalation Queue</h2>
        {error && <p className="error">{error}</p>}
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Category</th>
              <th>Subject</th>
              <th>Sentiment</th>
              <th>Urgency</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {tickets.map((t) => (
              <tr
                key={t.id}
                onClick={() => selectTicket(t.id)}
                className={t.id === selectedId ? "ticket-row selected" : "ticket-row"}
              >
                <td>{t.id}</td>
                <td>{t.category}</td>
                <td>{t.subject}</td>
                <td>{t.sentiment}</td>
                <td>{t.urgency}</td>
                <td>{t.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {tickets.length === 0 && !error && <p>No open tickets — or backend not seeded yet.</p>}
      </div>

      {/* Issue #14: click a ticket above to see exactly what the AI tried
          before escalating, instead of just the summary row. */}
      {selectedId && (
        <div className="panel escalation-detail">
          <h3>Ticket #{selectedId} — what the AI tried</h3>
          {detailLoading && <p>Loading…</p>}
          {detailError && <p className="error">{detailError}</p>}

          {detail && !detail.trace && !detailLoading && (
            <p>
              No reasoning trace on file for this ticket — it predates the AI pipeline (e.g. a
              seeded demo ticket), so there's nothing beyond the summary row to show.
            </p>
          )}

          {detail?.trace && (
            <>
              <h4>Reasoning trace</h4>
              <ol className="trace-list">
                {detail.trace.map((step, i) => (
                  <li key={i}>
                    <strong>{step.agent}:</strong> {step.output}
                  </li>
                ))}
              </ol>
            </>
          )}

          {detail?.handoff_packet && (
            <>
              <h4>Handoff packet</h4>
              <dl>
                <dt>Situation</dt>
                <dd>{detail.handoff_packet.situation}</dd>
                <dt>Likely cause</dt>
                <dd>{detail.handoff_packet.root_cause_hypothesis}</dd>
                <dt>Recommended next step</dt>
                <dd>{detail.handoff_packet.recommended_action}</dd>
                <dt>Urgency</dt>
                <dd>{detail.handoff_packet.urgency}/10</dd>
              </dl>
            </>
          )}
        </div>
      )}
    </div>
  );
}
