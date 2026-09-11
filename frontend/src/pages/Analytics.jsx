import { useEffect, useState } from "react";
import { fetchAnalyticsSummary } from "../api/client";

// STUB page. Tracked by issue: "Analytics dashboard (churn/anomaly radar)".
export default function Analytics() {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    fetchAnalyticsSummary().then(setSummary).catch(() => {});
  }, []);

  return (
    <div className="panel">
      <h2>Analytics</h2>
      <p>Not implemented yet — placeholder wired to a real (stub) endpoint.</p>
      {summary && <pre>{JSON.stringify(summary, null, 2)}</pre>}
    </div>
  );
}
