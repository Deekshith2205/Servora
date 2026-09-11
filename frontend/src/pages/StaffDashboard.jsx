import { useEffect, useState } from "react";
import { fetchEscalations } from "../api/client";

export default function StaffDashboard() {
  const [tickets, setTickets] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchEscalations().then(setTickets).catch((err) => setError(err.message));
  }, []);

  return (
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
            <tr key={t.id}>
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
  );
}
