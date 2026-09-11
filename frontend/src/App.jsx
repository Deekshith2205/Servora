import { useState } from "react";
import "./App.css";
import Analytics from "./pages/Analytics";
import CustomerChat from "./pages/CustomerChat";
import StaffDashboard from "./pages/StaffDashboard";

const TABS = {
  chat: { label: "Customer Chat", component: CustomerChat },
  dashboard: { label: "Staff Dashboard", component: StaffDashboard },
  analytics: { label: "Analytics", component: Analytics },
};

export default function App() {
  const [activeTab, setActiveTab] = useState("chat");
  const ActiveComponent = TABS[activeTab].component;

  return (
    <div className="app-shell">
      <header>
        <h1>Servora</h1>
        <nav>
          {Object.entries(TABS).map(([key, { label }]) => (
            <button
              key={key}
              className={activeTab === key ? "active" : ""}
              onClick={() => setActiveTab(key)}
            >
              {label}
            </button>
          ))}
        </nav>
      </header>
      <main>
        <ActiveComponent />
      </main>
    </div>
  );
}
