import { useEffect, useState } from "react";
import { confirmBooking, fetchBookings, updateBooking } from "../api/client";

// Issue #20: staff review/edit UI for bookings the Booking Agent (#18)
// drafted. A separate component (rather than folding this into
// StaffDashboard.jsx's own state) since it's a genuinely independent
// list+drawer with its own data source — StaffDashboard renders it as a
// second section below the escalations table.

const ROOM_TYPES = ["standard", "deluxe", "suite"];

function statusBadgeClass(status) {
  if (status === "CONFIRMED") return "badge-success";
  if (status === "STAFF_REVIEWED") return "badge-info";
  return "badge-neutral"; // AI_DRAFTED
}

export default function BookingsPanel() {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [actionError, setActionError] = useState(null);
  // Issue #21: the notification (if any) the most recent save produced —
  // shown so staff can see exactly what the customer was told, since it's
  // otherwise an invisible side effect of "Save changes".
  const [lastNotification, setLastNotification] = useState(null);

  const load = () => {
    setLoading(true);
    setError(null);
    fetchBookings()
      .then(setBookings)
      .catch((err) => setError(err.message || "Failed to load bookings"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const openBooking = (booking) => {
    setSelected(booking);
    setForm({
      room_type: booking.room_type,
      check_in: booking.check_in,
      check_out: booking.check_out,
      guests: booking.guests,
      total_price: booking.total_price,
    });
    setActionError(null);
    setLastNotification(null);
  };

  const closeDrawer = () => {
    setSelected(null);
    setForm(null);
    setActionError(null);
    setLastNotification(null);
  };

  const applyUpdate = (updated) => {
    setSelected(updated);
    setBookings((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
  };

  const handleSave = () => {
    if (!selected || !form) return;
    setSaving(true);
    setActionError(null);
    setLastNotification(null);
    updateBooking(selected.id, {
      room_type: form.room_type,
      check_in: form.check_in,
      check_out: form.check_out,
      guests: Number(form.guests),
      total_price: Number(form.total_price),
    })
      .then((result) => {
        applyUpdate(result.booking);
        setLastNotification(result.notification);
      })
      .catch((err) => setActionError(err.message || "Failed to save changes"))
      .finally(() => setSaving(false));
  };

  const handleConfirm = () => {
    if (!selected) return;
    setConfirming(true);
    setActionError(null);
    confirmBooking(selected.id)
      .then(applyUpdate)
      .catch((err) => setActionError(err.message || "Failed to confirm booking"))
      .finally(() => setConfirming(false));
  };

  const isConfirmed = selected?.status === "CONFIRMED";

  if (loading) {
    return (
      <div className="app-panel-fit">
        <div className="app-table-container">
          {[1, 2].map((i) => (
            <div key={i} className="skeleton-row"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app-error-banner">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
          <span>Unable to load bookings: {error}</span>
        </div>
        <button
          onClick={load}
          style={{ background: "var(--app-surface)", color: "var(--app-danger-text)", border: "1px solid currentColor", padding: "0.4rem 1rem", borderRadius: "4px", cursor: "pointer", fontWeight: 600, fontSize: "0.8rem" }}
        >
          Retry
        </button>
      </div>
    );
  }

  if (bookings.length === 0) {
    return (
      <div className="app-panel-fit" style={{ justifyContent: "center", minHeight: "200px" }}>
        <div className="app-empty-state" style={{ padding: "2rem" }}>
          <p>No bookings yet — complete one in "Book a Room" to see it here for review.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="app-panel-fit">
      <div className="escalations-header">
        <div>
          <h3 style={{ margin: "0 0 0.25rem 0", fontSize: "1.1rem", color: "var(--app-text-primary)" }}>Bookings</h3>
          <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--app-text-secondary)" }}>
            Drafted by the Booking Agent, awaiting staff review and confirmation.
          </p>
        </div>
        <div className="escalations-count">{bookings.length} {bookings.length === 1 ? "booking" : "bookings"}</div>
      </div>

      <div className="app-table-container">
        <table className="app-table">
          <thead>
            <tr>
              <th style={{ width: "80px" }}>ID</th>
              <th style={{ width: "120px" }}>Room</th>
              <th>Dates</th>
              <th style={{ width: "80px" }}>Guests</th>
              <th style={{ width: "100px" }}>Total</th>
              <th style={{ width: "140px" }}>Status</th>
              <th style={{ width: "40px" }}></th>
            </tr>
          </thead>
          <tbody>
            {bookings.map((b) => (
              <tr
                key={b.id}
                onClick={() => openBooking(b)}
                className={`escalation-row ${selected?.id === b.id ? "active" : ""}`}
              >
                <td className="col-id">#{b.id}</td>
                <td style={{ textTransform: "capitalize" }}>{b.room_type}</td>
                <td>{b.check_in} &rarr; {b.check_out}</td>
                <td>{b.guests}</td>
                <td>${b.total_price.toFixed(2)}</td>
                <td>
                  <span className={`app-badge ${statusBadgeClass(b.status)}`}>{b.status}</span>
                </td>
                <td className="col-action">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="9 18 15 12 9 6"></polyline>
                  </svg>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && form && (
        <div className="app-drawer-overlay" onClick={closeDrawer}>
          <div className="app-drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <div className="app-drawer-header">
              <div>
                <h2 className="app-drawer-title">Booking #{selected.id}</h2>
                <p className="app-drawer-subtitle">Customer #{selected.customer_id}</p>
              </div>
              <button className="app-drawer-close" onClick={closeDrawer} aria-label="Close">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
              </button>
            </div>

            <div className="app-drawer-content">
              <div className="drawer-section">
                <div className="drawer-section-title">Status</div>
                <span className={`app-badge ${statusBadgeClass(selected.status)}`}>{selected.status}</span>
              </div>

              <div className="drawer-section">
                <div className="drawer-section-title">Details</div>
                <div className="drawer-field-grid">
                  <div className="drawer-field">
                    <span className="drawer-field-label">Room type</span>
                    <select
                      value={form.room_type}
                      disabled={isConfirmed}
                      onChange={(e) => setForm({ ...form, room_type: e.target.value })}
                      style={{ padding: "0.4rem", borderRadius: "6px", border: "1px solid var(--app-border)", textTransform: "capitalize" }}
                    >
                      {ROOM_TYPES.map((rt) => (
                        <option key={rt} value={rt} style={{ textTransform: "capitalize" }}>{rt}</option>
                      ))}
                    </select>
                  </div>
                  <div className="drawer-field">
                    <span className="drawer-field-label">Guests</span>
                    <input
                      type="number"
                      min="1"
                      value={form.guests}
                      disabled={isConfirmed}
                      onChange={(e) => setForm({ ...form, guests: e.target.value })}
                      style={{ padding: "0.4rem", borderRadius: "6px", border: "1px solid var(--app-border)" }}
                    />
                  </div>
                  <div className="drawer-field">
                    <span className="drawer-field-label">Check-in</span>
                    <input
                      type="date"
                      value={form.check_in}
                      disabled={isConfirmed}
                      onChange={(e) => setForm({ ...form, check_in: e.target.value })}
                      style={{ padding: "0.4rem", borderRadius: "6px", border: "1px solid var(--app-border)" }}
                    />
                  </div>
                  <div className="drawer-field">
                    <span className="drawer-field-label">Check-out</span>
                    <input
                      type="date"
                      value={form.check_out}
                      disabled={isConfirmed}
                      onChange={(e) => setForm({ ...form, check_out: e.target.value })}
                      style={{ padding: "0.4rem", borderRadius: "6px", border: "1px solid var(--app-border)" }}
                    />
                  </div>
                  <div className="drawer-field">
                    <span className="drawer-field-label">Total price ($)</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={form.total_price}
                      disabled={isConfirmed}
                      onChange={(e) => setForm({ ...form, total_price: e.target.value })}
                      style={{ padding: "0.4rem", borderRadius: "6px", border: "1px solid var(--app-border)" }}
                    />
                  </div>
                </div>
              </div>

              {selected.edit_log.length > 0 && (
                <div className="drawer-section">
                  <div className="drawer-section-title">Edit history</div>
                  <ul style={{ margin: 0, paddingLeft: "1.1rem", fontSize: "0.8rem", color: "var(--app-text-secondary)" }}>
                    {selected.edit_log.map((entry, i) => (
                      <li key={i}>
                        <strong>{entry.field}</strong>: {entry.old_value} &rarr; {entry.new_value}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Issue #21: surface the notification the last save produced
                  — otherwise it's an invisible side effect of "Save changes". */}
              {lastNotification && (
                <div className="drawer-section">
                  <div className="drawer-section-title">Customer notified</div>
                  <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--app-text-primary)" }}>
                    {lastNotification.body}
                  </p>
                </div>
              )}

              <div className="drawer-section">
                {isConfirmed ? (
                  <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--app-text-secondary)" }}>
                    This booking is confirmed and no longer editable.
                  </p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                    {actionError && <p className="error" style={{ fontSize: "0.8rem" }}>{actionError}</p>}
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                      <button
                        onClick={handleSave}
                        disabled={saving || confirming}
                        style={{ background: "var(--app-surface)", border: "1px solid var(--app-border)", padding: "0.5rem 1.2rem", borderRadius: "6px", cursor: "pointer", fontWeight: 600, fontSize: "0.85rem" }}
                      >
                        {saving ? "Saving…" : "Save changes"}
                      </button>
                      <button
                        onClick={handleConfirm}
                        disabled={saving || confirming}
                        style={{ background: "var(--app-primary)", color: "#fff", border: "none", padding: "0.5rem 1.2rem", borderRadius: "6px", cursor: "pointer", fontWeight: 600, fontSize: "0.85rem" }}
                      >
                        {confirming ? "Confirming…" : "Confirm booking"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
