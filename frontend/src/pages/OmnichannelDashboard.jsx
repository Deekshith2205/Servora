import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock, Loader2, MessageSquare, Smile, Timer, UserCheck } from "lucide-react";
import { fetchAnalyticsSummary, fetchInbox, fetchChannels, fetchAgentPerformanceMetrics } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import KpiCard from "../components/omnichannel/KpiCard";
import AIFlowDiagram from "../components/omnichannel/AIFlowDiagram";
import ChannelHealthCard from "../components/omnichannel/ChannelHealthCard";
import ChannelDistributionBar from "../components/omnichannel/ChannelDistributionBar";
import InboxPreview from "../components/omnichannel/InboxPreview";
import ActivityFeed from "../components/omnichannel/ActivityFeed";
import RoleBanner from "../components/omnichannel/RoleBanner";

function weekOverWeekTrend(trend) {
  if (!trend || trend.length < 14) return undefined;
  const last7 = trend.slice(-7).reduce((s, d) => s + d.count, 0);
  const prev7 = trend.slice(-14, -7).reduce((s, d) => s + d.count, 0);
  if (prev7 === 0) return undefined;
  return Math.round(((last7 - prev7) / prev7) * 100);
}

function channelSparkline(channelTrend, channelKey) {
  if (!channelTrend) return [];
  return channelTrend.slice(-14).map((d) => d.channels?.[channelKey] ?? 0);
}

function roleLabel(role) {
  if (!role) return "Workspace";
  return `${role.charAt(0).toUpperCase()}${role.slice(1).replace(/_/g, " ")} Workspace`;
}

export default function OmnichannelDashboard() {
  const { currentUser } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [channels, setChannels] = useState([]);
  const [openInboxItems, setOpenInboxItems] = useState([]);
  const [allInboxItems, setAllInboxItems] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [agentMetrics, setAgentMetrics] = useState(null);

  const loadData = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetchChannels(),
      // Conversation content (Inbox) is gated separately from analytics
      // (`view_customer_conversations` vs `view_analytics`) — a role
      // with real, legitimate access to this dashboard (e.g. Manager)
      // can still lack the former. Degrading those two specifically to
      // an empty list on failure means the dashboard's own real
      // sections (KPIs, channel health, analytics) still render
      // instead of the whole page failing over one optional widget —
      // InboxPreview already has a real empty state for "no
      // conversations," which this also matches honestly.
      fetchInbox(null, null, "open").catch(() => []),
      fetchInbox().catch(() => []),
      fetchAnalyticsSummary(),
      fetchAgentPerformanceMetrics(),
    ])
      .then(([channelsData, openInboxData, allInboxData, analyticsData, agentMetricsData]) => {
        setChannels(channelsData);
        setOpenInboxItems(openInboxData);
        setAllInboxItems(allInboxData);
        setAnalytics(analyticsData);
        setAgentMetrics(agentMetricsData);
      })
      .catch((err) => setError(err.message || "Failed to load dashboard data"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      fetchInbox(null, null, "open")
        .then(setOpenInboxItems)
        .catch((err) => console.error("Polling fetch failed", err));
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32 text-slate-400 gap-2">
        <Loader2 size={20} className="animate-spin" /> Loading Omnichannel Dashboard…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-32 text-center">
        <p className="text-sm text-rose-600">{error}</p>
        <button onClick={loadData} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors">
          Retry
        </button>
      </div>
    );
  }

  const resolutionRate = analytics?.resolution_rate?.rate ?? 0;
  const escalationRate = analytics?.escalation_rate?.rate ?? 0;
  const activeTrend = weekOverWeekTrend(analytics?.trend);
  const activeSparkline = (analytics?.trend || []).slice(-14).map((d) => d.count);

  const sentimentTotals = (analytics?.sentiment_trend || []).reduce(
    (acc, d) => ({ positive: acc.positive + d.positive, total: acc.total + d.positive + d.neutral + d.negative }),
    { positive: 0, total: 0 }
  );
  const positiveSentimentPct = sentimentTotals.total > 0 ? Math.round((sentimentTotals.positive / sentimentTotals.total) * 100) : null;

  const totalAgentMs = (agentMetrics?.agents || []).reduce((s, a) => s + (a.avg_duration_ms || 0), 0);
  const avgInvestigationSeconds = totalAgentMs > 0 ? (totalAgentMs / 1000).toFixed(1) : null;

  const distinctAgentCount = agentMetrics?.agents?.length ?? 0;

  return (
    <div className="flex flex-col gap-10 pb-16" style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Role Banner */}
      <div className="flex justify-start">
        <RoleBanner
          roleLabel={roleLabel(currentUser?.role)}
          name={currentUser?.name}
          channelCount={channels.length}
          agentCount={distinctAgentCount}
          conversationCount={allInboxItems.length}
        />
      </div>

      {/* Hero */}
      <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_1fr] gap-8 items-start">
        <div className="flex flex-col gap-6">
          <div>
            <h1 className="text-4xl font-bold tracking-tight text-slate-900" style={{ fontFamily: "'Syne', sans-serif" }}>
              Omnichannel AI Operations Center
            </h1>
            <p className="text-slate-500 mt-2 text-[15px] max-w-lg">
              Every conversation, every channel, one autonomous pipeline — real-time visibility into how Servora's AI is handling your customers right now.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <KpiCard icon={MessageSquare} label="Active Conversations" value={openInboxItems.length} trend={activeTrend} sparkline={activeSparkline} accent="#2563EB" />
            <KpiCard icon={CheckCircle2} label="Resolution Rate" value={`${Math.round(resolutionRate * 100)}%`} accent="#059669" />
            <KpiCard icon={Clock} label="Avg Response Time" value="—" accent="#7C3AED" />
            <KpiCard icon={AlertTriangle} label="Escalation Rate" value={`${Math.round(escalationRate * 100)}%`} accent="#D97706" />
          </div>
        </div>
        <AIFlowDiagram channels={channels} resolvedPct={Math.round(resolutionRate * 100)} escalatedPct={Math.round(escalationRate * 100)} />
      </div>

      {/* Channel Health */}
      <section>
        <h2 className="text-xl font-bold text-slate-900 mb-1" style={{ fontFamily: "'Syne', sans-serif" }}>Channel Health</h2>
        <p className="text-sm text-slate-500 mb-5">Real-time status across every connected channel.</p>
        {channels.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-200 p-8 text-center text-sm text-slate-400">No channels configured.</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
            {channels.map((ch) => (
              <ChannelHealthCard
                key={ch.key}
                channel={ch}
                metrics={analytics?.channel_metrics?.find((m) => m.channel === ch.key)}
                sparkline={channelSparkline(analytics?.channel_trend, ch.key)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Unified Inbox Preview */}
      <section>
        <h2 className="text-xl font-bold text-slate-900 mb-1" style={{ fontFamily: "'Syne', sans-serif" }}>Unified Inbox</h2>
        <p className="text-sm text-slate-500 mb-5">Recent conversations across every channel, with AI investigation context.</p>
        <InboxPreview items={allInboxItems} />
      </section>

      {/* AI Performance Center */}
      <section>
        <h2 className="text-xl font-bold text-slate-900 mb-1" style={{ fontFamily: "'Syne', sans-serif" }}>AI Performance Center</h2>
        <p className="text-sm text-slate-500 mb-5">How well the autonomous pipeline is performing, end to end.</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <KpiCard icon={CheckCircle2} label="AI Resolution Rate" value={`${Math.round(resolutionRate * 100)}%`} accent="#059669" />
          <KpiCard icon={UserCheck} label="Human Handoff Rate" value={`${Math.round(escalationRate * 100)}%`} accent="#D97706" />
          <KpiCard icon={Timer} label="Avg Investigation Time" value={avgInvestigationSeconds ? `${avgInvestigationSeconds}s` : "—"} accent="#2563EB" />
          <KpiCard icon={Smile} label="Positive Sentiment" value={positiveSentimentPct !== null ? `${positiveSentimentPct}%` : "—"} accent="#7C3AED" />
        </div>
      </section>

      {/* Channel Distribution + Activity Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-bold text-slate-900 mb-4" style={{ fontFamily: "'Syne', sans-serif" }}>Channel Distribution</h2>
          <ChannelDistributionBar channelMetrics={analytics?.channel_metrics || []} />
        </section>
        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-bold text-slate-900 mb-4" style={{ fontFamily: "'Syne', sans-serif" }}>Live Activity</h2>
          <ActivityFeed items={allInboxItems} />
        </section>
      </div>
    </div>
  );
}
