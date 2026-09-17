import { ChevronRight } from "lucide-react";
import { channelStyle } from "./channelStyle";
import Sparkline from "./Sparkline";

// status badge is a real DERIVED classification from the channel's own
// resolution rate (>=70% healthy, >=40% warning, else critical) — never
// a hand-picked label. A channel with no processed tickets yet reads as
// "New", not a fabricated health score.
function deriveStatus(resolutionRate, processedCount) {
  if (processedCount === 0) return { label: "New", tone: "slate" };
  if (resolutionRate >= 0.7) return { label: "Healthy", tone: "emerald" };
  if (resolutionRate >= 0.4) return { label: "Warning", tone: "amber" };
  return { label: "Critical", tone: "rose" };
}

const TONE_CLASSES = {
  emerald: "bg-emerald-50 text-emerald-700 border-emerald-200",
  amber: "bg-amber-50 text-amber-700 border-amber-200",
  rose: "bg-rose-50 text-rose-700 border-rose-200",
  slate: "bg-slate-100 text-slate-600 border-slate-200",
};

export default function ChannelHealthCard({ channel, metrics, sparkline, onClick }) {
  const style = channelStyle(channel.key);
  const Icon = style.icon;
  const processed = metrics ? metrics.resolved + metrics.escalated : 0;
  const resolutionRate = processed > 0 ? metrics.resolved / processed : 0;
  const status = deriveStatus(resolutionRate, processed);
  const openCount = metrics?.open ?? 0;

  return (
    <button
      onClick={onClick}
      className="text-left w-full rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)] hover:shadow-[0_8px_24px_-12px_rgba(15,23,42,0.16)] hover:border-slate-300 transition-all group"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl" style={{ backgroundColor: style.bg, color: style.color }}>
            <Icon size={17} strokeWidth={2.25} />
          </span>
          <div>
            <div className="text-sm font-bold text-slate-900">{style.label}</div>
            <div className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold mt-0.5 ${TONE_CLASSES[status.tone]}`}>
              {status.label}
            </div>
          </div>
        </div>
        <ChevronRight size={16} className="text-slate-300 group-hover:text-slate-500 transition-colors mt-1" />
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <div className="text-lg font-bold text-slate-900">{openCount}</div>
          <div className="text-[11px] text-slate-500">Open tickets</div>
        </div>
        <div>
          <div className="text-lg font-bold text-slate-900">{processed > 0 ? `${Math.round(resolutionRate * 100)}%` : "—"}</div>
          <div className="text-[11px] text-slate-500">Resolution rate</div>
        </div>
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-slate-100">
        <span className="text-[11px] text-slate-400">14-day volume</span>
        <Sparkline values={sparkline} color={style.color} width={72} height={24} />
      </div>
    </button>
  );
}
