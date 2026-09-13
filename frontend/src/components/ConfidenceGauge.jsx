// [EXPLAIN] issue #94: large visual confidence indicator + optional
// per-agent breakdown bars. Reuses agentMeta.jsx's confidenceTier() so
// this never disagrees with ConfidenceBadge's small-badge color logic
// for the same value — one color scale for the whole app, not two.
import { agentLabel, confidenceTier } from "./agentMeta";
import "./ConfidenceGauge.css";

const TIER_LABEL = { high: "High confidence", medium: "Moderate confidence", low: "Low confidence" };

export function ConfidenceGauge({ value, size = 160 }) {
  const tier = confidenceTier(value);
  const known = tier !== null;
  const pct = known ? Math.round(value * 100) : 0;

  const radius = (size - 16) / 2;
  const circumference = 2 * Math.PI * radius;
  const arcLength = circumference * 0.75; // 3/4 circle, matches the gap below
  const offset = arcLength * (1 - pct / 100);

  return (
    <div className="confidence-gauge" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
        <circle
          className="confidence-gauge-track"
          cx={size / 2} cy={size / 2} r={radius}
          strokeDasharray={`${arcLength} ${circumference}`}
          strokeDashoffset={0}
          transform={`rotate(135 ${size / 2} ${size / 2})`}
        />
        {known && (
          <circle
            className={`confidence-gauge-fill tier-${tier}`}
            cx={size / 2} cy={size / 2} r={radius}
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeDashoffset={offset}
            transform={`rotate(135 ${size / 2} ${size / 2})`}
          />
        )}
      </svg>
      <div className="confidence-gauge-center">
        <span className="confidence-gauge-value">{known ? `${pct}%` : "—"}</span>
        <span className="confidence-gauge-caption">{known ? TIER_LABEL[tier] : "Not available"}</span>
      </div>
    </div>
  );
}

// Secondary, smaller bars — one per contributing agent. [EXPLAIN] issue
// #90's confidence-breakdown data, rendered underneath the main gauge.
export function ConfidenceBreakdownBars({ byAgent }) {
  if (!byAgent || byAgent.length === 0) return null;
  return (
    <div className="confidence-breakdown">
      {byAgent.map((row) => {
        const tier = confidenceTier(row.confidence);
        const pct = Math.round(row.confidence * 100);
        return (
          <div key={row.agent_name} className="confidence-breakdown-row">
            <span className="confidence-breakdown-label">{agentLabel(row.agent_name)}</span>
            <div className="confidence-breakdown-track">
              <div className={`confidence-breakdown-fill tier-${tier}`} style={{ width: `${pct}%` }}></div>
            </div>
            <span className="confidence-breakdown-value">{pct}%</span>
          </div>
        );
      })}
    </div>
  );
}
