import { CheckCircle2, Sparkles, UserCheck } from "lucide-react";
import { channelStyle } from "./channelStyle";

// The visual centerpiece: real seeded channels (from GET /api/channels)
// flowing into the real pipeline's outcome split (resolution_rate /
// escalation_rate from GET /api/analytics/summary) — every number here
// is live data, the "flow" is a styling device for the real architecture
// (Classifier -> Planner -> Specialist(s) -> Critic -> Verification ->
// Escalation/Memory) this app actually runs, not a fabricated diagram.
export default function AIFlowDiagram({ channels, resolvedPct, escalatedPct }) {
  const activeChannels = channels.filter((c) => c.status === "active");
  const otherChannels = channels.filter((c) => c.status !== "active");
  const ordered = [...activeChannels, ...otherChannels];

  return (
    <div className="relative rounded-2xl border border-slate-200 bg-gradient-to-br from-blue-50/60 via-white to-white p-6 lg:p-8 overflow-hidden">
      <div className="flex flex-col lg:flex-row items-center justify-between gap-6 lg:gap-2">
        {/* Channels */}
        <div className="flex lg:flex-col gap-3 flex-wrap justify-center">
          {ordered.map((ch) => {
            const style = channelStyle(ch.key);
            const Icon = style.icon;
            const dim = ch.status !== "active";
            return (
              <div
                key={ch.key}
                title={dim ? `${style.label} — not configured` : style.label}
                className={`flex items-center gap-2 rounded-full border bg-white px-3 py-2 shadow-sm transition-opacity ${dim ? "opacity-40" : ""}`}
                style={{ borderColor: dim ? "#E2E8F0" : style.color + "40" }}
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full" style={{ backgroundColor: style.bg, color: style.color }}>
                  <Icon size={14} strokeWidth={2.25} />
                </span>
                <span className="text-xs font-medium text-slate-700 hidden sm:inline">{style.label}</span>
              </div>
            );
          })}
        </div>

        {/* Connector: channels -> core */}
        <FlowConnector />

        {/* Core */}
        <div className="relative flex flex-col items-center gap-2 shrink-0">
          <div className="absolute inset-0 -m-3 rounded-full bg-blue-500/15 blur-xl animate-pulse" aria-hidden="true" />
          <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-sky-500 text-white shadow-lg shadow-blue-500/30">
            <Sparkles size={30} strokeWidth={1.75} />
          </div>
          <div className="text-sm font-bold text-slate-900" style={{ fontFamily: "'Syne', sans-serif" }}>Servora AI Core</div>
          <div className="text-[11px] text-slate-500">Classifier → Planner → Specialists</div>
        </div>

        {/* Connector: core -> outcomes */}
        <FlowConnector />

        {/* Outcomes */}
        <div className="flex lg:flex-col gap-3">
          <div className="flex items-center gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5">
            <CheckCircle2 size={18} className="text-emerald-600" />
            <div>
              <div className="text-sm font-bold text-emerald-700">{resolvedPct}%</div>
              <div className="text-[11px] text-emerald-600/80">Resolved by AI</div>
            </div>
          </div>
          <div className="flex items-center gap-2.5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5">
            <UserCheck size={18} className="text-amber-600" />
            <div>
              <div className="text-sm font-bold text-amber-700">{escalatedPct}%</div>
              <div className="text-[11px] text-amber-600/80">Escalated to human</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function FlowConnector() {
  return (
    <svg width="56" height="24" viewBox="0 0 56 24" className="hidden lg:block shrink-0" aria-hidden="true">
      <line x1="0" y1="12" x2="56" y2="12" stroke="#93C5FD" strokeWidth="2" strokeDasharray="4 4">
        <animate attributeName="stroke-dashoffset" from="16" to="0" dur="1s" repeatCount="indefinite" />
      </line>
      <polygon points="50,7 56,12 50,17" fill="#60A5FA" />
    </svg>
  );
}
