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

  if (loading) {
    return (
      <div className="omnichannel-dashboard">
        <div className="dashboard-header">
          <h1>Omnichannel Dashboard</h1>
          <p>Live operational view across every support channel</p>
        </div>
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
        <div className="dashboard-header">
          <h1>Omnichannel Dashboard</h1>
          <p>Live operational view across every support channel</p>
        </div>
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
      <div className="dashboard-header">
        <h1>Omnichannel Dashboard</h1>
        <p>Live operational view across every support channel</p>
      </div>

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
          <div className="summary-cards-grid">
            {channels.map((ch) => {
              const openCount = openInboxItems.filter((t) => t.channel_key === ch.key).length;
              
              const channelTickets = allInboxItems.filter((t) => t.channel_key === ch.key);
              let latestDate = null;
              if (channelTickets.length > 0) {
                // Since inbox items are sorted newest first from the API, the first is the latest.
                latestDate = channelTickets[0].updated_at;
              }

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
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
