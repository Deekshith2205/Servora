import { useEffect, useState } from "react";
import { fetchSettings, updateSetting } from "../api/client";
import Can from "../auth/Can";

export default function AdminSettings() {
  const [settings, setSettings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [updatingKey, setUpdatingKey] = useState(null);

  const loadSettings = () => {
    setLoading(true);
    setError(null);
    fetchSettings()
      .then((data) => setSettings(data))
      .catch((err) => setError(err.message || "Failed to load settings"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const handleToggle = (key, currentValue) => {
    const newValue = currentValue === "true" ? "false" : "true";
    setUpdatingKey(key);
    updateSetting(key, newValue)
      .then((updatedSetting) => {
        setSettings((curr) => curr.map((s) => (s.key === key ? updatedSetting : s)));
      })
      .catch((err) => {
        alert(err.message || "Failed to update setting");
      })
      .finally(() => {
        setUpdatingKey(null);
      });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", flex: 1, overflowY: "auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ fontFamily: "'Syne', sans-serif", fontSize: "1.75rem", margin: "0 0 0.5rem 0", color: "var(--app-text-primary)" }}>System Configuration</h2>
          <p style={{ margin: 0, color: "var(--app-text-secondary)" }}>Manage global feature toggles and settings.</p>
        </div>
        <button onClick={loadSettings} className="app-btn-secondary">Refresh</button>
      </div>

      {error && (
        <div className="app-error-banner">
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="app-panel" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div className="skeleton-row" style={{ height: "60px" }}></div>
          <div className="skeleton-row" style={{ height: "60px" }}></div>
        </div>
      ) : settings.length === 0 ? (
        <div className="app-empty-state">
          <h3>No settings found</h3>
          <p>There are no system configurations available.</p>
        </div>
      ) : (
        <div className="app-panel" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ display: "flex", flexDirection: "column" }}>
            {settings.map((setting, index) => {
              const isBoolean = setting.value === "true" || setting.value === "false";
              const isEnabled = setting.value === "true";
              
              const SETTING_DESCRIPTIONS = {
                "demo_mode": "Enable or disable global demo behaviors",
                "default_escalation_confidence_threshold": "Minimum confidence required for autonomous escalation (0.0 - 1.0)",
                "feature_shopify_lookup_enabled": "Allow agents to query real customer orders from connected Shopify store",
              };
              
              const description = SETTING_DESCRIPTIONS[setting.key] || "No description provided.";

              return (
                <div key={setting.key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1.25rem 1.5rem", borderBottom: index < settings.length - 1 ? "1px solid var(--app-border)" : "none" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                    <span style={{ fontWeight: 600, color: "var(--app-text-primary)", fontFamily: "monospace", fontSize: "0.95rem" }}>{setting.key}</span>
                    <span style={{ color: "var(--app-text-secondary)", fontSize: "0.85rem" }}>{description}</span>
                  </div>
                  <div>
                    <Can permission="manage_system_settings">
                      {isBoolean ? (
                        <button
                          onClick={() => handleToggle(setting.key, setting.value)}
                          disabled={updatingKey === setting.key}
                          style={{
                            background: isEnabled ? "var(--app-primary)" : "var(--app-surface-hover)",
                            color: isEnabled ? "white" : "var(--app-text-secondary)",
                            border: isEnabled ? "1px solid var(--app-primary)" : "1px solid var(--app-border)",
                            padding: "0.4rem 1rem",
                            borderRadius: "20px",
                            cursor: updatingKey === setting.key ? "not-allowed" : "pointer",
                            fontWeight: 600,
                            fontSize: "0.85rem",
                            transition: "all 0.2s ease"
                          }}
                        >
                          {updatingKey === setting.key ? "Saving..." : isEnabled ? "Enabled" : "Disabled"}
                        </button>
                      ) : (
                        <span style={{ color: "var(--app-text-muted)", fontStyle: "italic", fontSize: "0.85rem" }}>Non-boolean setting</span>
                      )}
                    </Can>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
