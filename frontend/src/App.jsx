import { useEffect, useMemo, useState } from "react";
import {
  BarChart3, BookOpen, ClipboardList, Compass, History, Inbox as InboxIcon, LayoutDashboard,
  MessageSquare, Mic, Plug, Settings as SettingsIcon, Share2, Users as UsersIcon,
} from "lucide-react";
import "./App.css";
import Analytics from "./pages/Analytics";
import AgentSwarmView from "./pages/AgentSwarmView";
import BookingChat from "./pages/BookingChat";
import CustomerChat from "./pages/CustomerChat";
import Integrations from "./pages/Integrations";
import KnowledgeCenter from "./pages/KnowledgeCenter";
import InvestigationBoard from "./pages/InvestigationBoard";
import StaffDashboard from "./pages/StaffDashboard";
import Inbox from "./pages/Inbox";
import OmnichannelDashboard from "./pages/OmnichannelDashboard";
import CustomerResolutionHistory from "./pages/CustomerResolutionHistory";
import UserManagement from "./pages/UserManagement";
import AdminSettings from "./pages/AdminSettings";
import RoleSwitcher from "./auth/RoleSwitcher";
import ProtectedRoute from "./auth/ProtectedRoute";
import ErrorBoundary from "./components/ErrorBoundary";
import Login from "./pages/Login";
import { useAuth } from "./auth/AuthContext";
import { isPermitted } from "./auth/roles";
import RoleBadge from "./components/RoleBadge";
import UserProfileMenu from "./components/UserProfileMenu";

import CustomerDashboard from "./pages/CustomerDashboard";
import AdminDashboard from "./pages/AdminDashboard";

const TABS = {
  dashboard_customer: {
    label: "My Dashboard",
    description: "Overview of your support activity",
    component: CustomerDashboard,
    permission: "view_own_tickets",
    icon: <LayoutDashboard className="app-nav-icon" size={18} strokeWidth={2} />
  },
  dashboard_omni: {
    label: "Omnichannel Dashboard",
    description: "Live operational view across every support channel",
    component: OmnichannelDashboard,
    // Tightened from an OR with view_investigation_board: the page's own
    // core data fetch (GET /api/analytics/summary) requires
    // view_analytics specifically, so a viewer who reached this tab
    // ONLY via view_investigation_board (Support Agent) landed on a
    // broken page, not a working one — a real bug, not a permission
    // decision. Every role that could actually use this page
    // (Manager/Administrator) already has view_analytics.
    permission: "view_analytics",
    icon: <LayoutDashboard className="app-nav-icon" size={18} strokeWidth={2} />
  },
  admin_dashboard: {
    label: "Admin Dashboard",
    description: "System administration and organizational analytics",
    component: AdminDashboard,
    permission: "manage_users", // Only admins have manage_users in this app
    icon: <LayoutDashboard className="app-nav-icon" size={18} strokeWidth={2} />
  },
  chat: {
    label: "Customer Chat",
    description: "AI-powered customer conversation",
    component: CustomerChat,
    permission: "send_chat_message",
    icon: <MessageSquare className="app-nav-icon" size={18} strokeWidth={2} />
  },
  history: {
    label: "Resolution History",
    description: "View outcomes of your support tickets",
    component: CustomerResolutionHistory,
    permission: "view_own_tickets",
    icon: <History className="app-nav-icon" size={18} strokeWidth={2} />
  },
  dashboard: {
    label: "Staff Dashboard",
    description: "Review cases requiring human attention",
    component: StaffDashboard,
    permission: ["handle_escalations", "view_escalation_queue"],
    icon: <ClipboardList className="app-nav-icon" size={18} strokeWidth={2} />
  },
  investigations: {
    label: "Investigation Board",
    description: "Autonomous reasoning timeline for every conversation",
    component: InvestigationBoard,
    permission: "view_investigation_board",
    icon: <Compass className="app-nav-icon" size={18} strokeWidth={2} />
  },
  swarm: {
    label: "Agent Swarm",
    description: "Multi-agent network view of a single investigation",
    component: AgentSwarmView,
    permission: "view_investigation_board",
    icon: <Share2 className="app-nav-icon" size={18} strokeWidth={2} />
  },
  booking: {
    label: "Book a Room",
    description: "Voice or text hotel booking (stretch feature)",
    component: BookingChat,
    permission: "send_chat_message",
    icon: <Mic className="app-nav-icon" size={18} strokeWidth={2} />
  },
  analytics: {
    label: "Analytics",
    description: "Understand support activity and outcomes",
    component: Analytics,
    permission: "view_analytics",
    icon: <BarChart3 className="app-nav-icon" size={18} strokeWidth={2} />
  },
  integrations: {
    label: "Integrations",
    description: "Connect real external systems for Servora to investigate",
    component: Integrations,
    permission: "manage_integrations",
    icon: <Plug className="app-nav-icon" size={18} strokeWidth={2} />
  },
  knowledge_center: {
    label: "Knowledge Center",
    description: "Upload and manage documents specialists ground answers in",
    component: KnowledgeCenter,
    // Read-only browse/search for Support Agent + Manager (view_knowledge_base);
    // upload/delete/reprocess is gated inline with <Can permission="manage_knowledge_base">
    // (Administrator only) — same two-tier pattern Integrations uses.
    permission: "view_knowledge_base",
    icon: <BookOpen className="app-nav-icon" size={18} strokeWidth={2} />
  },
  inbox: {
    label: "Unified Inbox",
    description: "All customer conversations in one place",
    component: Inbox,
    permission: "view_customer_conversations",
    icon: <InboxIcon className="app-nav-icon" size={18} strokeWidth={2} />
  },
  users: {
    label: "User Management",
    description: "Manage roles and access for staff members",
    component: UserManagement,
    permission: "manage_users",
    icon: <UsersIcon className="app-nav-icon" size={18} strokeWidth={2} />
  },
  settings: {
    label: "System Configuration",
    description: "Manage global feature toggles and settings",
    component: AdminSettings,
    permission: "manage_system_settings",
    icon: <SettingsIcon className="app-nav-icon" size={18} strokeWidth={2} />
  },
};

const DEFAULT_TABS = {
  customer: "dashboard_customer",
  support_agent: "dashboard",
  manager: "analytics",
  administrator: "admin_dashboard"
};

export default function App() {
  const [activeTab, setActiveTab] = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { currentRole, loading } = useAuth();
  const [lastRole, setLastRole] = useState(null);

  // The real, permission-filtered set of tabs this role can actually
  // reach — recomputed whenever the resolved role changes (sign-in,
  // sign-out, a different account). Order follows TABS' own declared
  // order, not permission-grant order.
  const visibleTabs = useMemo(
    () => Object.entries(TABS).filter(([, tab]) => isPermitted(currentRole, tab.permission)),
    [currentRole]
  );

  // Whenever the visible set changes and the current tab isn't in it
  // (first load, or a role switch that drops access to whatever was
  // open), land on the first tab this role can actually see instead of
  // showing a dead nav item or an Access Denied banner.
  // We also incorporate Role-Specific Default Landing here.
  useEffect(() => {
    if (visibleTabs.length === 0) return;
    
    // Role switch logic: if role changed, try to land on default tab
    if (currentRole && currentRole !== lastRole) {
      setLastRole(currentRole);
      const defaultTab = DEFAULT_TABS[currentRole];
      
      // If the default tab is valid and permitted for this role, use it
      if (defaultTab && visibleTabs.some(([key]) => key === defaultTab)) {
        setActiveTab(defaultTab);
        return;
      }
    }
    
    // Fallback enforcement: if the current tab is invalid or not visible
    if (!visibleTabs.some(([key]) => key === activeTab)) {
      setActiveTab(visibleTabs[0][0]);
    }
  }, [visibleTabs, activeTab, currentRole, lastRole]);

  const activeTabInfo = activeTab ? TABS[activeTab] : null;
  const ActiveComponent = activeTabInfo?.component;

  const handleTabClick = (key) => {
    setActiveTab(key);
    setMobileMenuOpen(false);
  };

  if (loading) {
    return <div className="servora-app" style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--app-text-muted)" }}>Loading Servora…</div>;
  }

  if (!currentRole) {
    return (
      <div className="servora-app">
        <Login />
      </div>
    );
  }

  if (visibleTabs.length === 0) {
    return (
      <div className="servora-app" style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--app-text-muted)", textAlign: "center", padding: "2rem" }}>
        Your account ({currentRole.replace("_", " ")}) doesn't have access to any page yet. Contact an Administrator.
      </div>
    );
  }

  if (!activeTabInfo) {
    return null; // one render tick while the effect above picks the first visible tab
  }

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
          {visibleTabs.map(([key, { label, icon }]) => (
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
        
        <div className="app-sidebar-footer" style={{ display: "flex", flexDirection: "column", gap: "1rem", alignItems: "flex-start" }}>
          <RoleBadge />
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
          <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginLeft: "auto", marginRight: "1rem" }}>
            <RoleSwitcher />
            <UserProfileMenu />
          </div>
        </header>
        
        <div className="app-content">
          <ErrorBoundary resetKey={activeTab}>
            <ProtectedRoute permission={activeTabInfo.permission}>
              <ActiveComponent setActiveTab={setActiveTab} />
            </ProtectedRoute>
          </ErrorBoundary>
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
