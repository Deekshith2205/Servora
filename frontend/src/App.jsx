import { useState } from "react";
import "./App.css";
import Analytics from "./pages/Analytics";
import AgentSwarmView from "./pages/AgentSwarmView";
import BookingChat from "./pages/BookingChat";
import CustomerChat from "./pages/CustomerChat";
import Integrations from "./pages/Integrations";
import InvestigationBoard from "./pages/InvestigationBoard";
import StaffDashboard from "./pages/StaffDashboard";
import Inbox from "./pages/Inbox";
import OmnichannelDashboard from "./pages/OmnichannelDashboard";
import CustomerResolutionHistory from "./pages/CustomerResolutionHistory";
import RoleSwitcher from "./auth/RoleSwitcher";
import ProtectedRoute from "./auth/ProtectedRoute";

const TABS = {
  dashboard_omni: {
    label: "Omnichannel Dashboard",
    description: "Live operational view across every support channel",
    component: OmnichannelDashboard,
    permission: ["view_analytics", "view_investigation_board"],
    icon: (
      <svg className="app-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
        <line x1="3" y1="9" x2="21" y2="9"></line>
        <line x1="9" y1="21" x2="9" y2="9"></line>
      </svg>
    )
  },
  chat: {
    label: "Customer Chat",
    description: "AI-powered customer conversation",
    component: CustomerChat,
    permission: "send_chat_message",
    icon: (
      <svg className="app-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
      </svg>
    )
  },
  history: {
    label: "Resolution History",
    description: "View outcomes of your support tickets",
    component: CustomerResolutionHistory,
    permission: "view_own_tickets",
    icon: (
      <svg className="app-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <polyline points="12 6 12 12 16 14"></polyline>
      </svg>
    )
  },
  dashboard: {
    label: "Staff Dashboard",
    description: "Review cases requiring human attention",
    component: StaffDashboard,
    permission: ["handle_escalations", "view_escalation_queue"],
    icon: (
      <svg className="app-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
        <line x1="3" y1="9" x2="21" y2="9"></line>
        <line x1="9" y1="21" x2="9" y2="9"></line>
      </svg>
    )
  },
  investigations: {
    label: "Investigation Board",
    description: "Autonomous reasoning timeline for every conversation",
    component: InvestigationBoard,
    permission: "view_investigation_board",
    icon: (
      <svg className="app-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8"></circle>
        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        <line x1="11" y1="8" x2="11" y2="12"></line>
        <line x1="11" y1="14.5" x2="11.01" y2="14.5"></line>
      </svg>
    )
  },
  swarm: {
    label: "Agent Swarm",
    description: "Multi-agent network view of a single investigation",
    component: AgentSwarmView,
    permission: "view_investigation_board",
    icon: (
      <svg className="app-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="6" cy="6" r="3"></circle>
        <circle cx="18" cy="6" r="3"></circle>
        <circle cx="12" cy="18" r="3"></circle>
        <line x1="8.6" y1="7.6" x2="10.5" y2="16.2"></line>
        <line x1="15.4" y1="7.6" x2="13.5" y2="16.2"></line>
        <line x1="9" y1="6" x2="15" y2="6"></line>
      </svg>
    )
  },
  booking: {
    label: "Book a Room",
    description: "Voice or text hotel booking (stretch feature)",
    component: BookingChat,
    permission: "send_chat_message",
    icon: (
      <svg className="app-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
        <line x1="12" y1="19" x2="12" y2="23"></line>
      </svg>
    )
  },
  analytics: {
    label: "Analytics",
    description: "Understand support activity and outcomes",
    component: Analytics,
    permission: "view_analytics",
    icon: (
      <svg className="app-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="18" y1="20" x2="18" y2="10"></line>
        <line x1="12" y1="20" x2="12" y2="4"></line>
        <line x1="6" y1="20" x2="6" y2="14"></line>
      </svg>
    )
  },
  integrations: {
    label: "Integrations",
    description: "Connect real external systems for Servora to investigate",
    component: Integrations,
    permission: "manage_integrations",
    icon: (
      <svg className="app-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 3v6m6-6v6M4 9h16l-1 10a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2z"></path>
      </svg>
    )
  },
  inbox: {
    label: "Unified Inbox",
    description: "All customer conversations in one place",
    component: Inbox,
    permission: "view_customer_conversations",
    icon: (
      <svg className="app-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 12 16 12 14 15 10 15 8 12 2 12"></polyline>
        <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"></path>
      </svg>
    )
  },
};

export default function App() {
  const [activeTab, setActiveTab] = useState("chat");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  
  const activeTabInfo = TABS[activeTab];
  const ActiveComponent = activeTabInfo.component;

  const handleTabClick = (key) => {
    setActiveTab(key);
    setMobileMenuOpen(false);
  };

  return (
    <div className="servora-app app-layout">
      
      {/* Sidebar */}
      <aside className={`app-sidebar ${mobileMenuOpen ? 'open' : ''}`}>
        <a href="/" className="app-brand">
          <div className="app-brand-icon">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          Servora
        </a>
        
        <nav className="app-nav">
          {Object.entries(TABS).map(([key, { label, icon }]) => (
            <button
              key={key}
              className={`app-nav-item ${activeTab === key ? "active" : ""}`}
              onClick={() => handleTabClick(key)}
            >
              {icon}
              {label}
            </button>
          ))}
        </nav>
        
        <div className="app-sidebar-footer">
          <a href="https://github.com/Deekshith2205/Servora" target="_blank" rel="noreferrer" style={{color: 'inherit', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path></svg>
            GitHub
          </a>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="app-main">
        <header className="app-header">
          <button 
            className="mobile-menu-btn" 
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="12" x2="21" y2="12"></line>
              <line x1="3" y1="6" x2="21" y2="6"></line>
              <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
          </button>
          <div className="app-header-content">
            <h1>{activeTabInfo.label}</h1>
            <p>{activeTabInfo.description}</p>
          </div>
          <RoleSwitcher />
        </header>
        
        <div className="app-content">
          <ProtectedRoute permission={activeTabInfo.permission}>
            <ActiveComponent />
          </ProtectedRoute>
        </div>
      </main>
      
      {/* Mobile overlay to click-close sidebar */}
      {mobileMenuOpen && (
        <div 
          style={{position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 30}} 
          onClick={() => setMobileMenuOpen(false)}
        />
      )}
    </div>
  );
}
