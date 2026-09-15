// Settings -> Integrations (Phase 5). Real connection to a real Shopify
// store — see backend/app/api/integrations.py + app/services/
// shopify_service.py. This page only ever talks to
// /api/integrations/shopify/... — it never touches the access token
// after submitting it once (the backend never returns it back, see
// ShopifyStatusOut's own docstring).
import { useEffect, useState } from "react";
import { connectShopify, disconnectShopify, fetchShopifyStatus } from "../api/client";
import "./Integrations.css";

const STATUS_BADGE = {
  connected: "badge-success",
  disconnected: "badge-neutral",
  error: "badge-danger",
  never_connected: "badge-neutral",
};

const STATUS_LABEL = {
  connected: "Connected",
  disconnected: "Disconnected",
  error: "Connection Error",
  never_connected: "Not Connected",
};

function ShopifyIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path>
      <path d="M3 6h18"></path>
      <path d="M16 10a4 4 0 0 1-8 0"></path>
    </svg>
  );
}

function formatTimestamp(iso) {
  if (!iso) return "Never";
  try {
    return new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

export default function Integrations() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [storeUrl, setStoreUrl] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState(null);
  const [disconnecting, setDisconnecting] = useState(false);

  const loadStatus = () => {
    setLoading(true);
    setError(null);
    fetchShopifyStatus()
      .then(setStatus)
      .catch((err) => setError(err.message || "Failed to load integration status"))
      .finally(() => setLoading(false));
  };

  useEffect(loadStatus, []);

  const handleConnect = (e) => {
    e.preventDefault();
    setConnecting(true);
    setConnectError(null);
    connectShopify(storeUrl.trim(), accessToken.trim())
      .then((newStatus) => {
        setStatus(newStatus);
        setStoreUrl("");
        setAccessToken("");
      })
      .catch((err) => setConnectError(err.message || "Failed to connect"))
      .finally(() => setConnecting(false));
  };

  const handleDisconnect = () => {
    setDisconnecting(true);
    disconnectShopify()
      .then(setStatus)
      .catch((err) => setError(err.message || "Failed to disconnect"))
      .finally(() => setDisconnecting(false));
  };

  const isConnected = status?.connected;

  return (
    <div className="ig-page">
      <div className="ig-section-title">Connected Apps</div>

      <div className="ig-app-card">
        <div className="ig-app-header">
          <div className="ig-app-icon"><ShopifyIcon /></div>
          <div className="ig-app-titles">
            <div className="ig-app-name">Shopify</div>
            <div className="ig-app-desc">Investigate real orders from a connected Shopify store.</div>
          </div>
          {!loading && status && (
            <span className={`app-badge ${STATUS_BADGE[status.status] || "badge-neutral"}`}>
              {STATUS_LABEL[status.status] || status.status}
            </span>
          )}
        </div>

        {loading ? (
          <div className="ig-loading">Loading…</div>
        ) : error ? (
          <div className="app-error-banner"><span>{error}</span><button onClick={loadStatus}>Retry</button></div>
        ) : isConnected ? (
          <div className="ig-connected-detail">
            <div className="ig-field-grid">
              <div className="ig-field">
                <span className="ig-field-label">Store</span>
                <span className="ig-field-value">{status.store_url}</span>
              </div>
              <div className="ig-field">
                <span className="ig-field-label">Last Sync</span>
                <span className="ig-field-value">{formatTimestamp(status.last_sync_at)}</span>
              </div>
              <div className="ig-field">
                <span className="ig-field-label">Connected Orders</span>
                <span className="ig-field-value">{status.connected_orders_count ?? 0}</span>
              </div>
            </div>
            {status.last_error && (
              <div className="ig-last-error">Last error: {status.last_error}</div>
            )}
            <button className="ig-btn-secondary" onClick={handleDisconnect} disabled={disconnecting}>
              {disconnecting ? "Disconnecting…" : "Disconnect"}
            </button>
          </div>
        ) : (
          <form className="ig-connect-form" onSubmit={handleConnect}>
            <p className="ig-connect-hint">
              Connect a real Shopify store — Servora's Order and Billing agents will be able to
              look up real orders, customers, and fulfillment status from it, alongside this app's
              own seeded demo data.
            </p>
            <div className="ig-form-row">
              <label className="ig-form-label" htmlFor="ig-store-url">Store URL</label>
              <input
                id="ig-store-url"
                className="ig-input"
                type="text"
                placeholder="my-store.myshopify.com"
                value={storeUrl}
                onChange={(e) => setStoreUrl(e.target.value)}
                required
              />
            </div>
            <div className="ig-form-row">
              <label className="ig-form-label" htmlFor="ig-access-token">Admin API Access Token</label>
              <input
                id="ig-access-token"
                className="ig-input"
                type="password"
                placeholder="shpat_..."
                value={accessToken}
                onChange={(e) => setAccessToken(e.target.value)}
                required
              />
            </div>
            {connectError && <div className="ig-connect-error">{connectError}</div>}
            <button className="ig-btn-primary" type="submit" disabled={connecting}>
              {connecting ? "Connecting…" : "Connect Shopify"}
            </button>
          </form>
        )}
      </div>

      <p className="ig-footnote">
        Real integrations coexist with Servora's own seeded demo data — the Order and Billing
        agents use whichever source is actually relevant to a customer's message, never replacing
        one with the other.
      </p>
    </div>
  );
}
