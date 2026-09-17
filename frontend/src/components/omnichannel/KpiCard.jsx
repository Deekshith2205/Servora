import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import Sparkline from "./Sparkline";

// trend is optional and, when present, is a REAL computed number (e.g.
// this-week vs last-week volume) — never shown when there's nothing
// honest to compute it from, rather than a decorative placeholder.
export default function KpiCard({ icon: Icon, label, value, trend, trendLabel, sparkline, accent = "#2563EB" }) {
  const hasTrend = typeof trend === "number" && Number.isFinite(trend);
  const up = trend > 0;
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_1px_2px_rgba(15,23,42,0.04),0_8px_24px_-12px_rgba(15,23,42,0.12)] flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl" style={{ backgroundColor: `${accent}14`, color: accent }}>
          <Icon size={20} strokeWidth={2} />
        </div>
        {sparkline && sparkline.length > 1 && <Sparkline values={sparkline} color={accent} />}
      </div>
      <div>
        <div className="text-3xl font-bold tracking-tight text-slate-900" style={{ fontFamily: "'Syne', sans-serif" }}>{value}</div>
        <div className="text-sm text-slate-500 mt-0.5">{label}</div>
      </div>
      {hasTrend && (
        <div className={`inline-flex items-center gap-1 text-xs font-semibold w-fit ${up ? "text-emerald-600" : "text-rose-600"}`}>
          {up ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
          {Math.abs(trend)}% {trendLabel || "vs last week"}
        </div>
      )}
    </div>
  );
}
