import React, { useState, useEffect, useRef } from "react";
import { fetchInbox, fetchInboxDetail, fetchChannels } from "../api/client";
import { ChannelBadge } from "../components/channelMeta";
import "./Inbox.css";

function StatusBadge({ status }) {
  let className = "inbox-status-badge ";
  switch (status) {
    case "resolved": className += "status-resolved"; break;
    case "escalated": className += "status-escalated"; break;
    case "open": className += "status-open"; break;
    case "closed": className += "status-closed"; break;
    default: className += "status-default"; break;
  }
  return <span className={className}>{status}</span>;
}

function ConversationRow({ item, isSelected, onClick }) {
  const timeStr = new Date(item.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <button
      className={`inbox-row ${isSelected ? 'selected' : ''}`}
      onClick={() => onClick(item.id)}
      aria-label={`Conversation with ${item.customer.name}`}
    >
      <div className="inbox-row-header">
        <span className="inbox-row-customer">{item.customer.name}</span>
        <span className="inbox-row-time">{timeStr}</span>
      </div>
      <div className="inbox-row-meta">
        <ChannelBadge channelKey={item.channel_key} />
        <StatusBadge status={item.status} />
      </div>
      <div className="inbox-row-subject">{item.subject}</div>
      <div className="inbox-row-preview">{item.preview}</div>
    </button>
  );
}

export default function Inbox() {
  const [channels, setChannels] = useState([]);
  const [selectedChannelKey, setSelectedChannelKey] = useState(null);
  const [channelCounts, setChannelCounts] = useState({});
  const [totalCount, setTotalCount] = useState(0);
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);

  const requestRef = useRef(0);

  useEffect(() => {
    let isMounted = true;
    const init = async () => {
      try {
        const chans = await fetchChannels();
        if (!isMounted) return;
        setChannels(chans);

        const counts = {};

        fetchInbox().then(data => {
          if (isMounted) setTotalCount(data.length);
        }).catch(err => console.error("Failed to load total count", err));

        await Promise.all(chans.map(async (c) => {
          try {
            const data = await fetchInbox(c.key);
            if (isMounted) counts[c.key] = data.length;
          } catch (err) {
            console.error(`Failed to load count for ${c.key}`, err);
            if (isMounted) counts[c.key] = 0;
          }
        }));

        if (isMounted) {
          setChannelCounts(counts);
        }
      } catch (err) {
        console.error("Failed to load channels/counts", err);
      }
    };
    init();
    loadInbox(null);
    return () => { isMounted = false; };
  }, []);

  const loadInbox = async (channelKey) => {
    const currentReq = ++requestRef.current;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInbox(channelKey);
      if (currentReq === requestRef.current) {
        setConversations(data);
        setLoading(false);
      }
    } catch (err) {
      if (currentReq === requestRef.current) {
        setError(err.message || "Failed to load conversations.");
        setLoading(false);
      }
    }
  };

  const handleChannelSelect = (channelKey) => {
    setSelectedChannelKey(channelKey);
    setSelectedId(null);
    loadInbox(channelKey);
  };

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }

    let isMounted = true;
    const loadDetail = async () => {
      setDetailLoading(true);
      setDetailError(null);
      try {
        const data = await fetchInboxDetail(selectedId);
        if (isMounted) setDetail(data);
      } catch (err) {
        if (isMounted) setDetailError(err.message || "Failed to load detail.");
      } finally {
        if (isMounted) setDetailLoading(false);
      }
    };

    loadDetail();

    return () => { isMounted = false; };
  }, [selectedId]);

  return (
    <div className="inbox-container">
      <div className="inbox-channels-sidebar">
        <button
          className={`channel-tab ${selectedChannelKey === null ? 'active' : ''}`}
          onClick={() => handleChannelSelect(null)}
        >
          All
          {totalCount > 0 && <span className="channel-count">{totalCount}</span>}
        </button>
        {channels.map(ch => (
          <button
            key={ch.key}
            className={`channel-tab ${selectedChannelKey === ch.key ? 'active' : ''}`}
            onClick={() => handleChannelSelect(ch.key)}
          >
            {ch.display_name || ch.key}
            {channelCounts[ch.key] !== undefined && channelCounts[ch.key] > 0 && (
              <span className="channel-count">{channelCounts[ch.key]}</span>
            )}
          </button>
        ))}
      </div>
      <div className={`inbox-list-panel ${selectedId ? 'hide-on-mobile' : ''}`}>
        {loading ? (
          <div className="inbox-loading skeleton">Loading conversations...</div>
        ) : error ? (
          <div className="inbox-error">
            <p>{error}</p>
            <button className="app-btn-primary" onClick={loadInbox}>Retry</button>
          </div>
        ) : conversations.length === 0 ? (
          <div className="inbox-empty">Your inbox is clear.</div>
        ) : (
          <div className="inbox-list">
            {conversations.map(conv => (
              <ConversationRow
                key={conv.id}
                item={conv}
                isSelected={selectedId === conv.id}
                onClick={setSelectedId}
              />
            ))}
          </div>
        )}
      </div>

      <div className={`inbox-detail-panel ${selectedId ? 'open' : ''}`}>
        {!selectedId ? (
          <div className="inbox-empty-detail">Select a conversation to view details.</div>
        ) : detailLoading ? (
          <div className="inbox-detail-loading skeleton">Loading detail...</div>
        ) : detailError ? (
          <div className="inbox-error">
            <p>{detailError}</p>
            <button className="app-btn-secondary" onClick={() => setSelectedId(null)}>Close</button>
          </div>
        ) : detail ? (
          <div className="inbox-detail-content">
            <div className="inbox-detail-header">
              <button className="inbox-back-btn" onClick={() => setSelectedId(null)} aria-label="Back to list">
                ← Back
              </button>
              <h2>{detail.customer.name}</h2>
              <div className="inbox-detail-email">{detail.customer.email}</div>
            </div>

            <div className="inbox-detail-meta summary-card">
              <div className="detail-meta-row">
                <span className="meta-label">Channel:</span>
                <ChannelBadge channelKey={detail.channel_key} />
              </div>
              <div className="detail-meta-row">
                <span className="meta-label">Status:</span>
                <StatusBadge status={detail.status} />
              </div>
              <div className="detail-meta-row">
                <span className="meta-label">Subject:</span>
                <span className="meta-value">{detail.subject}</span>
              </div>
              <div className="detail-meta-row">
                <span className="meta-label">Time:</span>
                <span className="meta-value">{new Date(detail.updated_at).toLocaleString()}</span>
              </div>
              {detail.investigation_id && (
                <div className="detail-meta-row">
                  <span className="meta-label">Investigation:</span>
                  <span className="meta-value status-resolved-text">Investigation available</span>
                </div>
              )}
            </div>

            <div className="inbox-detail-message summary-card">
              <h3>Message</h3>
              <p className="message-body">{detail.message}</p>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
