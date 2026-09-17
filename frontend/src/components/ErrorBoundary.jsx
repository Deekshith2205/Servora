import { Component } from "react";

// A real, repeated failure mode this app has hit twice now — a page
// component with a genuine JS bug (Analytics.jsx once, StaffDashboard.jsx
// again, both a hook used without being imported) throws during render.
// React has no built-in recovery from that: without a boundary, the
// WHOLE app unmounts to a blank white screen, and every other page stays
// blank/stuck until a hard reload — not just the one broken page. This
// boundary contains that failure to the single page that crashed, so a
// bug in one tab can never again take down navigation, the Role
// Switcher, or every other already-working page along with it.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("Page crashed:", error, info?.componentStack);
  }

  componentDidUpdate(prevProps) {
    // Reset once the user navigates away — the user's fix for "this page
    // is broken" is to click a different tab, not to know a magic key
    // combo, so a new resetKey (App.jsx passes the active tab) clears
    // the crashed state as soon as they do that.
    if (this.props.resetKey !== prevProps.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="app-error-banner" style={{ margin: "2rem auto", maxWidth: "600px", textAlign: "center", padding: "3rem" }}>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--app-error, #dc2626)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: "1rem" }}>
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
          <h2 style={{ color: "var(--app-text-primary)", margin: "0 0 0.5rem 0" }}>This page hit a real error</h2>
          <p style={{ color: "var(--app-text-muted)", margin: "0 0 1rem" }}>{this.state.error.message}</p>
          <p style={{ color: "var(--app-text-muted)", fontSize: "0.85rem", margin: 0 }}>
            The rest of the app is unaffected — pick another tab, or come back to this one to retry.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
