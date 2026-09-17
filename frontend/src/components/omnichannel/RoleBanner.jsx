import { Sparkles } from "lucide-react";

// Every count here is real — passed in from the same data the rest of the
// page already fetched (channels/agents/conversations), never a fabricated
// "1248" like the reference mockup's own sample data.
export default function RoleBanner({ roleLabel, name, channelCount, agentCount, conversationCount }) {
  return (
    <div className="inline-flex items-center gap-3 rounded-full border border-blue-100 bg-white/80 backdrop-blur-sm pl-1.5 pr-4 py-1.5 shadow-sm">
      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-sky-500 text-white">
        <Sparkles size={15} strokeWidth={2} />
      </span>
      <div className="flex flex-col leading-tight">
        <span className="text-xs font-bold text-slate-900">{roleLabel}{name ? ` · ${name}` : ""}</span>
        <span className="text-[11px] text-slate-500">
          Managing {channelCount} Channel{channelCount === 1 ? "" : "s"} · {agentCount} Agent{agentCount === 1 ? "" : "s"} · {conversationCount.toLocaleString()} Conversations
        </span>
      </div>
    </div>
  );
}
