// Part 2 of the "Connected Commerce Environment" demo-polish pass:
// visually shows which real backend systems each agent queried for the
// most recently completed investigation — no new data, just a friendly
// grouping of the real `used_tools` already recorded per
// InvestigationStep (see utils/toolSystems.js for the tool -> system
// label mapping, and CustomerChat.jsx for where `steps` comes from —
// the same GET /api/investigations/by-ticket/{id} call
// ExplainableAIPanel already makes for a customer's own ticket).
import { AgentIcon, agentLabel } from "./agentMeta.jsx";
import { systemsForTools } from "../utils/toolSystems";

const ALL_SYSTEMS = [
  "Orders Database",
  "Payments Database",
  "Delivery Tracking (Shopify)",
  "Knowledge Base",
  "Support Tickets",
];

export default function ConnectedSystemsPanel({ steps }) {
  const agentSystems = (steps || [])
    .map((step) => ({
      agentName: step.agent_name,
      systems: systemsForTools(step.used_tools),
    }))
    .filter((entry) => entry.systems.length > 0);

  return (
    <div className="connected-systems-panel">
      <div className="connected-systems-legend">
        {ALL_SYSTEMS.map((system) => (
          <span key={system} className="connected-systems-legend-item">{system}</span>
        ))}
      </div>

      {agentSystems.length === 0 ? (
        <p className="connected-systems-empty">
          Send a message — Servora will show exactly which systems each agent queries to investigate it.
        </p>
      ) : (
        <div className="connected-systems-agent-list">
          {agentSystems.map((entry, i) => (
            <div key={i} className="connected-systems-agent-row">
              <span className="connected-systems-agent-name">
                <AgentIcon agentName={entry.agentName} /> {agentLabel(entry.agentName)}
              </span>
              <ul className="connected-systems-checklist">
                {entry.systems.map((system) => (
                  <li key={system}>✓ {system}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
