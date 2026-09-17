import { channelStyle } from "./channelStyle";

// Real percentages from channel_metrics' totals — sorted so the segmented
// bar (and the legend beneath it) always reads largest-share-first.
export default function ChannelDistributionBar({ channelMetrics }) {
  const total = channelMetrics.reduce((sum, m) => sum + m.total, 0);
  const sorted = [...channelMetrics].filter((m) => m.total > 0).sort((a, b) => b.total - a.total);

  if (total === 0) {
    return <div className="text-sm text-slate-400">No ticket volume recorded yet.</div>;
  }

  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-slate-100">
        {sorted.map((m) => {
          const style = channelStyle(m.channel);
          const pct = (m.total / total) * 100;
          return <div key={m.channel} style={{ width: `${pct}%`, backgroundColor: style.color }} title={`${style.label}: ${Math.round(pct)}%`} />;
        })}
      </div>
      <div className="mt-4 flex flex-col gap-2">
        {sorted.map((m) => {
          const style = channelStyle(m.channel);
          const pct = Math.round((m.total / total) * 100);
          return (
            <div key={m.channel} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: style.color }} />
                <span className="text-slate-600">{style.label}</span>
              </div>
              <span className="font-semibold text-slate-900">{pct}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
