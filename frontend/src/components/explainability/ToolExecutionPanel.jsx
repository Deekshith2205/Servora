// [Explainability #121]: "Section 3" — which tool(s) actually ran.
// Data: EvidenceDetailOut.tools (ToolExecutionOut[]) — duration/records
// are STEP-level values attributed to each tool (see that schema's
// docstring for why), so this renders them plainly rather than implying
// per-tool precision the backend doesn't actually have.

function formatDuration(ms) {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

export default function ToolExecutionPanel({ tools }) {
  if (!tools || tools.length === 0) {
    return <p className="expl-empty-note">No tool call is associated with this evidence item.</p>;
  }
  return (
    <div className="expl-tool-list">
      {tools.map((tool) => (
        <div className="expl-tool-row" key={tool.tool_name}>
          <div className="expl-tool-name">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
            </svg>
            {tool.tool_name}
          </div>
          <div className="expl-tool-stats">
            <span><strong>{formatDuration(tool.duration_ms)}</strong> duration</span>
            <span><strong>{tool.records_returned}</strong> record{tool.records_returned === 1 ? "" : "s"} returned</span>
          </div>
        </div>
      ))}
    </div>
  );
}
