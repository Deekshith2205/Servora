import { useState, useEffect } from "react";
import { fetchAnalyticsSummary, fetchInbox, fetchChannels } from "../api/client";
import { ChannelBadge } from "../components/channelMeta";
import "./OmnichannelDashboard.css";

export default function OmnichannelDashboard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Data state
  const [channels, setChannels] = useState([]);
  const [openInboxItems, setOpenInboxItems] = useState([]);
  const [allInboxItems, setAllInboxItems] = useState([]);
  const [analytics, setAnalytics] = useState(null);

  const loadData = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetchChannels(),
      fetchInbox(null, null, "open"),
      fetchInbox(),
      fetchAnalyticsSummary()
    ])
      .then(([channelsData, openInboxData, allInboxData, analyticsData]) => {
        setChannels(channelsData);
        setOpenInboxItems(openInboxData);
        setAllInboxItems(allInboxData);
        setAnalytics(analyticsData);
      })
      .catch((err) => {
        setError(err.message || "Failed to load dashboard data");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    loadData();
  }, []);

  // Polling for active conversations (Issue #156)
  useEffect(() => {
    const interval = setInterval(() => {
      fetchInbox(null, null, "open")
        .then((openInboxData) => {
          setOpenInboxItems(openInboxData);
        })
        .catch((err) => {
          console.error("Polling fetch failed", err);
        });
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="omnichannel-dashboard">
        <div className="summary-cards-grid">
          <div className="summary-card skeleton-pulse">
            <div className="skeleton-stat"></div>
            <div className="skeleton-text short"></div>
          </div>
          <div className="summary-card skeleton-pulse">
            <div className="skeleton-stat"></div>
            <div className="skeleton-text short"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="omnichannel-dashboard">
        <div className="dashboard-error-state">
          <p>{error}</p>
          <button className="primary-button" onClick={loadData}>Retry</button>
        </div>
      </div>
    );
  }

  // Derive metrics
  const totalActive = openInboxItems.length;
  const todaysVolume = analytics?.trend?.length > 0 ? analytics.trend[analytics.trend.length - 1].count : 0;

  // Format date helper
  const formatDate = (dateStr) => {
    if (!dateStr) return "—";
    const d = new Date(dateStr);
    return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  };

  return (
    <div className="omnichannel-dashboard">
      <div className="summary-cards-grid dashboard-section">
        <div className="summary-card">
          <div className="summary-value">{totalActive}</div>
          <div className="summary-label">Active Conversations</div>
        </div>
        <div className="summary-card">
          <div className="summary-value">{todaysVolume}</div>
          <div className="summary-label">Today's Volume</div>
        </div>
      </div>

      <div className="dashboard-section">
        <h2 className="dashboard-section-title">Channel Activity</h2>
        {channels.length === 0 ? (
          <div className="empty-state">
            <p>No channels configured.</p>
          </div>
        ) : (
          <div className="channel-cards-grid">
            {channels.map((ch) => {
              const openCount = openInboxItems.filter((t) => t.channel_key === ch.key).length;
              
              const channelTickets = allInboxItems.filter((t) => t.channel_key === ch.key);
              let latestDate = null;
              if (channelTickets.length > 0) {
                // Since inbox items are sorted newest first from the API, the first is the latest.
                latestDate = channelTickets[0].updated_at;
              }

              // Compute statistics from analytics
              const chStats = analytics?.channel_metrics?.find((m) => m.channel === ch.key);
              const processed = chStats ? chStats.resolved + chStats.escalated : 0;
              const resolutionRate = processed > 0 ? chStats.resolved / processed : 0;
              const hasStats = processed > 0;

              return (
                <div key={ch.key} className="channel-widget-card">
                  <div className="channel-widget-header">
                    <ChannelBadge channelKey={ch.key} />
                  </div>
                  <div className="channel-widget-metrics">
                    <div className="channel-widget-metric">
                      <span className="channel-widget-metric-label">Open</span>
                      <span className="channel-widget-metric-value">{openCount}</span>
                    </div>
                    <div className="channel-widget-metric">
                      <span className="channel-widget-metric-label">Latest</span>
                      <span className={`channel-widget-metric-value ${!latestDate ? "dim" : ""}`} style={{ fontSize: "14px", marginTop: "4px" }}>
                        {formatDate(latestDate)}
                      </span>
                    </div>
                    <div className="channel-widget-metric">
                      <span className="channel-widget-metric-label">Resolution Rate</span>
                      <span className={`channel-widget-metric-value ${!hasStats ? "dim" : ""}`}>
                        {hasStats ? `${Math.round(resolutionRate * 100)}%` : "—"}
                      </span>
                    </div>
                    <div className="channel-widget-metric">
                      <span className="channel-widget-metric-label">Avg Response Time</span>
                      <span className="channel-widget-metric-value dim">—</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="dashboard-section">
        <h2 className="dashboard-section-title">Active Conversations</h2>
        {openInboxItems.length === 0 ? (
          <div className="empty-state">
            <p>No active conversations across any channel.</p>
          </div>
        ) : (
          <div className="active-conversations-list">
            {openInboxItems.map((ticket) => (
              <div key={ticket.id} className="active-conversation-item">
                <ChannelBadge channelKey={ticket.channel_key} />
                <div className="active-conversation-main">
                  <div className="active-conversation-header">
                    <span className="active-conversation-customer">{ticket.customer.name}</span>
                    <span className="active-conversation-time">{formatDate(ticket.updated_at)}</span>
                  </div>
                  <h3 className="active-conversation-subject">{ticket.subject}</h3>
                  <p className="active-conversation-preview">{ticket.preview}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
