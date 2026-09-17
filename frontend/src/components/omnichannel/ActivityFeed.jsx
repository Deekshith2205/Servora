import { AlertTriangle, CheckCircle2, MessageSquarePlus } from "lucide-react";
import { channelStyle } from "./channelStyle";

// Every entry here is a real Ticket row (from GET /api/inbox), not a
// simulated event log — this app doesn't have a dedicated activity-event
// table, so "activity" is honestly derived from each real ticket's own
// current status, sorted by its real updated_at. No per-agent-step
// events ("Billing Agent completed investigation") are shown here since
// that granularity only exists per-investigation (see the Investigation
// Board), not as a cross-ticket feed — showing it here would mean
// re-fetching every ticket's full investigation, which isn't worth the
// N+1 cost for a dashboard glance.
const ENTRY_STYLE = {
  resolved: { icon: CheckCircle2, color: "#059669", verb: "resolved automatically" },
  escalated: { icon: AlertTriangle, color: "#D97706", verb: "escalated to a human agent" },
  open: { icon: MessageSquarePlus, color: "#2563EB", verb: "new conversation" },
};

function timeAgo(iso) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export default function ActivityFeed({ items, limit = 8 }) {
  const sorted = [...items]
    .sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
    .slice(0, limit);

  if (sorted.length === 0) {
    return <div className="text-sm text-slate-400">No recent activity.</div>;
  }

  return (
    <div className="flex flex-col">
      {sorted.map((item, i) => {
        const entry = ENTRY_STYLE[item.status] || ENTRY_STYLE.open;
        const Icon = entry.icon;
        const ch = channelStyle(item.channel_key);
        return (
          <div key={item.id} className="flex gap-3 relative">
            <div className="flex flex-col items-center">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full ring-4 ring-white" style={{ backgroundColor: `${entry.color}18`, color: entry.color }}>
                <Icon size={13} strokeWidth={2.5} />
              </span>
              {i < sorted.length - 1 && <span className="w-px flex-1 bg-slate-200" />}
            </div>
            <div className="pb-5 min-w-0">
              <div className="text-sm text-slate-700">
                <span className="font-semibold text-slate-900">Ticket #{item.id}</span> {entry.verb}
              </div>
              <div className="text-xs text-slate-500 truncate mt-0.5">{item.customer?.name} · {ch.label} · {item.subject}</div>
              <div className="text-[11px] text-slate-400 mt-0.5">{timeAgo(item.updated_at)}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
