import { useState, useEffect } from "react";
import { fetchAnalyticsSummary, fetchInbox, fetchChannels } from "../api/client";
import { ChannelBadge } from "../components/channelMeta";
import "./OmnichannelDashboard.css";

export default function OmnichannelDashboard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Data state
  const [channels, setChannels] = useState([]);
  const [inboxItems, setInboxItems] = useState([]);
  const [analytics, setAnalytics] = useState(null);

  const loadData = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetchChannels(),
      fetchInbox(null, null, "open"),
      fetchAnalyticsSummary()
    ])
      .then(([channelsData, inboxData, analyticsData]) => {
        setChannels(channelsData);
        setInboxItems(inboxData);
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
  const totalActive = inboxItems.length;
  const todaysVolume = analytics?.trend?.length > 0 ? analytics.trend[analytics.trend.length - 1].count : 0;

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
        <h2 className="dashboard-section-title">Active by Channel</h2>
        {channels.length === 0 ? (
          <div className="empty-state">
            <p>No channels configured.</p>
          </div>
        ) : (
          <div className="summary-cards-grid">
            {channels.map((ch) => {
              const count = inboxItems.filter((t) => t.channel_key === ch.key).length;
              return (
                <div key={ch.key} className="summary-card">
                  <div className="summary-value">{count}</div>
                  <div className="summary-label">
                    <ChannelBadge channelKey={ch.key} />
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
