import { useEffect, useState } from "react";
import { AlertCircle, Bot, Loader2, MessageCircle } from "lucide-react";
import { fetchInboxDetail, fetchInvestigationByTicket, fetchTicketRecord } from "../../api/client";
import { channelStyle } from "./channelStyle";

const STATUS_TONE = {
  open: "bg-blue-50 text-blue-700 border-blue-200",
  resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  escalated: "bg-amber-50 text-amber-700 border-amber-200",
};

const URGENCY_LABEL = { 1: "Low", 2: "Low", 3: "Medium", 4: "High", 5: "Critical" };

function timeShort(iso) {
  const d = new Date(iso);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  return sameDay
    ? d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
    : d.toLocaleDateString([], { month: "short", day: "numeric" });
}

// Right-pane detail is fetched on selection, not preloaded for every row —
// avoids an N+1 fetch across the whole list for data (AI classification,
// investigation outcome) only the selected conversation needs.
function ConversationDetail({ item }) {
  const [detail, setDetail] = useState(null);
  const [investigation, setInvestigation] = useState(null);
  const [record, setRecord] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setDetail(null);
    setInvestigation(null);
    setRecord(null);

    Promise.all([
      fetchInboxDetail(item.id).catch(() => null),
      fetchTicketRecord(item.id).catch(() => null),
    ]).then(([detailData, recordData]) => {
      if (cancelled) return;
      setDetail(detailData);
      setRecord(recordData);
      if (detailData?.investigation_id) {
        fetchInvestigationByTicket(item.id)
          .then((inv) => { if (!cancelled) setInvestigation(inv); })
          .catch(() => {})
          .finally(() => { if (!cancelled) setLoading(false); });
      } else {
        setLoading(false);
      }
    });

    return () => { cancelled = true; };
  }, [item.id]);

  const style = channelStyle(item.channel_key);
  const topAgent = investigation?.agents?.length
    ? [...investigation.agents].sort((a, b) => b.steps - a.steps)[0].agent_name
    : null;

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-slate-400 gap-2 text-sm">
        <Loader2 size={16} className="animate-spin" /> Loading conversation…
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-start justify-between p-5 border-b border-slate-100">
        <div>
          <div className="font-bold text-slate-900">{item.customer?.name}</div>
          <div className="text-xs text-slate-500">{item.customer?.email}</div>
        </div>
        <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold capitalize ${STATUS_TONE[item.status] || STATUS_TONE.open}`}>
          {item.status}
        </span>
      </div>

      <div className="p-5 flex-1 overflow-y-auto flex flex-col gap-4">
        <div className="rounded-xl bg-slate-50 border border-slate-200 p-4">
          <div className="flex items-center gap-2 mb-2 text-xs font-semibold text-slate-500">
            <span className="flex h-5 w-5 items-center justify-center rounded-full" style={{ backgroundColor: style.bg, color: style.color }}>
              <style.icon size={11} />
            </span>
            {style.label} · {item.subject}
          </div>
          <p className="text-sm text-slate-700 leading-relaxed">{detail?.message || item.preview}</p>
        </div>

        {record && (
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl border border-slate-200 p-3">
              <div className="text-[11px] text-slate-400 mb-1">AI Classification</div>
              <div className="text-sm font-semibold text-slate-900 capitalize">{record.category}</div>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <div className="text-[11px] text-slate-400 mb-1">Priority</div>
              <div className="text-sm font-semibold text-slate-900">{URGENCY_LABEL[record.urgency] || `Level ${record.urgency}`}</div>
            </div>
          </div>
        )}

        {investigation ? (
          <div className="rounded-xl border border-blue-100 bg-blue-50/40 p-4">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-blue-700 mb-2">
              <Bot size={13} /> Suggested Resolution
            </div>
            <p className="text-sm text-slate-700 leading-relaxed">{investigation.resolution || "Investigation still in progress — no resolution recorded yet."}</p>
            {topAgent && (
              <div className="mt-3 pt-3 border-t border-blue-100 text-xs text-slate-500">
                Assigned agent: <span className="font-semibold text-slate-700">{topAgent.replace(/_/g, " ")}</span>
                {investigation.confidence != null && <span> · {Math.round(investigation.confidence * 100)}% confidence</span>}
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2 text-xs text-slate-400 rounded-xl border border-dashed border-slate-200 p-4">
            <AlertCircle size={14} /> No AI investigation recorded for this conversation yet.
          </div>
        )}
      </div>
    </div>
  );
}

export default function InboxPreview({ items, limit = 12 }) {
  const sorted = [...items].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at)).slice(0, limit);
  const [selectedId, setSelectedId] = useState(sorted[0]?.id ?? null);

  useEffect(() => {
    if (!sorted.some((i) => i.id === selectedId) && sorted.length > 0) {
      setSelectedId(sorted[0].id);
    }
  }, [items]); // eslint-disable-line react-hooks/exhaustive-deps

  const selected = sorted.find((i) => i.id === selectedId);

  if (sorted.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-2xl border border-slate-200 bg-white p-12 text-sm text-slate-400 gap-2">
        <MessageCircle size={16} /> No conversations yet.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-[0_1px_2px_rgba(15,23,42,0.04)]" style={{ minHeight: 420 }}>
      <div className="border-b lg:border-b-0 lg:border-r border-slate-100 overflow-y-auto" style={{ maxHeight: 460 }}>
        {sorted.map((item) => {
          const style = channelStyle(item.channel_key);
          const active = item.id === selectedId;
          return (
            <button
              key={item.id}
              onClick={() => setSelectedId(item.id)}
              className={`w-full text-left px-4 py-3.5 border-b border-slate-50 flex items-start gap-3 transition-colors ${active ? "bg-blue-50/60" : "hover:bg-slate-50"}`}
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full mt-0.5" style={{ backgroundColor: style.bg, color: style.color }}>
                <style.icon size={14} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-slate-900 truncate">{item.customer?.name}</span>
                  <span className="text-[10px] text-slate-400 shrink-0">{timeShort(item.updated_at)}</span>
                </div>
                <div className="text-xs text-slate-500 truncate">{item.subject}</div>
                <div className="text-[11px] text-slate-400 truncate mt-0.5">{item.preview}</div>
              </div>
            </button>
          );
        })}
      </div>
      <div>{selected && <ConversationDetail item={selected} />}</div>
    </div>
  );
}
