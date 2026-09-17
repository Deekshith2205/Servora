import { useState } from "react";
import { ArrowLeft, Headset, LayoutDashboard, Shield, Sparkles, User } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { CUSTOMER, SUPPORT_AGENT, MANAGER, ADMINISTRATOR } from "../auth/roles";
import { DEMO_USERS, DEMO_CUSTOMERS } from "../auth/demoIdentities";

const ROLE_CARDS = [
  {
    role: CUSTOMER,
    title: "Customer",
    description: "Chat with Servora's AI, track resolutions, and book rooms.",
    icon: User,
    color: "#2563EB",
  },
  {
    role: SUPPORT_AGENT,
    title: "Support Agent",
    description: "Handle escalations and review live conversations.",
    icon: Headset,
    color: "#059669",
  },
  {
    role: MANAGER,
    title: "Manager",
    description: "Monitor analytics, channel health, and team activity.",
    icon: LayoutDashboard,
    color: "#7C3AED",
  },
  {
    role: ADMINISTRATOR,
    title: "Administrator",
    description: "Full access — users, integrations, and system settings.",
    icon: Shield,
    color: "#D97706",
  },
];

// This screen is a themed front door onto the exact same demo-identity
// mechanism RoleSwitcher.jsx already exposes in the header (switchIdentity
// from AuthContext) — it introduces no new access logic of its own, it
// just gives that existing mechanism a dedicated entry point.
export default function Login() {
  const { switchIdentity } = useAuth();
  const [pendingRole, setPendingRole] = useState(null);
  const [signingIn, setSigningIn] = useState(false);

  const handleRoleClick = (role) => {
    if (role === CUSTOMER) {
      setPendingRole(CUSTOMER);
      return;
    }
    const user = DEMO_USERS.find((u) => u.role === role);
    if (user) signIn(role, user.id, null);
  };

  const signIn = async (role, userId, customerId) => {
    setSigningIn(true);
    try {
      await switchIdentity(role, userId, customerId);
    } finally {
      setSigningIn(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-white px-4 py-10" style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="w-full max-w-3xl">
        <div className="flex flex-col items-center text-center mb-10">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-sky-500 text-white shadow-lg shadow-blue-500/30 mb-5">
            <Sparkles size={26} strokeWidth={1.75} />
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-slate-900" style={{ fontFamily: "'Syne', sans-serif" }}>
            Sign in to Servora
          </h1>
          <p className="text-slate-500 mt-3 max-w-md text-[15px]">
            Autonomous customer support, demoed as any role. Pick who you're signing in as.
          </p>
        </div>

        {pendingRole === CUSTOMER ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-[0_1px_2px_rgba(15,23,42,0.04),0_20px_25px_-5px_rgba(15,23,42,0.08)]">
            <button
              onClick={() => setPendingRole(null)}
              className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-900 transition-colors mb-6"
            >
              <ArrowLeft size={15} /> Back
            </button>
            <h2 className="text-lg font-bold text-slate-900 mb-1" style={{ fontFamily: "'Syne', sans-serif" }}>Sign in as a customer</h2>
            <p className="text-sm text-slate-500 mb-6">Choose which demo customer account to use.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {DEMO_CUSTOMERS.map((c) => (
                <button
                  key={c.id}
                  disabled={signingIn}
                  onClick={() => signIn(CUSTOMER, null, c.id)}
                  className="flex items-center gap-3 rounded-xl border border-slate-200 p-4 text-left hover:border-blue-300 hover:bg-blue-50/40 transition-colors disabled:opacity-50"
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-blue-700 font-bold">
                    {c.name.charAt(0)}
                  </span>
                  <span>
                    <span className="block text-sm font-semibold text-slate-900">{c.name}</span>
                    <span className="block text-xs text-slate-500">Customer</span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {ROLE_CARDS.map(({ role, title, description, icon: Icon, color }) => (
              <button
                key={role}
                disabled={signingIn}
                onClick={() => handleRoleClick(role)}
                className="text-left rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_1px_2px_rgba(15,23,42,0.04)] hover:shadow-[0_8px_24px_-12px_rgba(15,23,42,0.16)] hover:border-slate-300 transition-all disabled:opacity-50"
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-xl mb-4" style={{ backgroundColor: `${color}14`, color }}>
                  <Icon size={20} strokeWidth={2} />
                </span>
                <span className="block text-base font-bold text-slate-900 mb-1" style={{ fontFamily: "'Syne', sans-serif" }}>{title}</span>
                <span className="block text-sm text-slate-500 leading-relaxed">{description}</span>
              </button>
            ))}
          </div>
        )}

        <p className="text-center text-xs text-slate-400 mt-8">
          Demo environment — no password required. Access is scoped to the selected role's real permissions.
        </p>
      </div>
    </div>
  );
}
