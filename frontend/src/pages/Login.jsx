import { useState } from "react";
import { Eye, EyeOff, Headset, Loader2, Lock, Mail, ShieldCheck, User } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import GoogleSignInButton from "../auth/GoogleSignInButton";
import AuthShowcase from "../auth/AuthShowcase";
import "./Login.css";

const DEMO_ACCOUNTS = [
  { email: "alice@example.com", role: "Customer" },
  { email: "bob@example.com", role: "Customer" },
  { email: "jordan.lee@servora.example", role: "Support Agent" },
  { email: "priya.shah@servora.example", role: "Manager" },
  { email: "sam.okafor@servora.example", role: "Administrator" },
];
const DEMO_PASSWORD = "Demo1234!";

// A real sign-in/sign-up screen backed by app/api/auth.py's real
// login/register/google endpoints — password verified against a real
// stored hash (or a real Google-verified identity), a real server-side
// session token issued on success. No one-click role impersonation
// anywhere on this page by design.
export default function Login() {
  const { login, register, loginWithGoogle } = useAuth();
  const [accountType, setAccountType] = useState("customer"); // "customer" | "staff" — purely frames the form; the backend always resolves the real role from the account itself.
  const [mode, setMode] = useState("signin"); // "signin" | "signup"
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showForgotNote, setShowForgotNote] = useState(false);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const isSignup = mode === "signup" && accountType === "customer";

  const switchMode = (next) => {
    setMode(next);
    setError(null);
    setPassword("");
    setConfirmPassword("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (isSignup) {
      if (password.length < 8) {
        setError("Password must be at least 8 characters.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords don't match.");
        return;
      }
    }

    setSubmitting(true);
    try {
      if (isSignup) {
        await register(name.trim(), email.trim(), password);
      } else {
        await login(email.trim(), password);
      }
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleGoogleCredential = async (credential) => {
    setError(null);
    setSubmitting(true);
    try {
      await loginWithGoogle(credential);
    } catch (err) {
      setError(err.message || "Google sign-in failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page w-full min-h-screen flex items-stretch bg-white">
      {/* Left — form */}
      <div className="login-left-panel">
        
        {/* Brand Header */}
        <div className="login-brand px-6 py-8 lg:p-0 z-10">
          <a href="/" className="flex items-center gap-2.5" style={{ textDecoration: 'none' }}>
            <span className="flex h-[32px] w-[32px] items-center justify-center rounded-[8px] bg-blue-600 text-white shadow-sm">
              <ShieldCheck size={20} strokeWidth={2.5} />
            </span>
            <span className="text-[24px] font-bold text-slate-900 tracking-tight login-brand-name">Servora</span>
          </a>
          <span className="text-[13px] font-medium text-slate-500 tracking-wide mt-1">AI-Powered Support Command Center</span>
        </div>

        {/* Form Container */}
        <div className="login-content px-6 mx-auto lg:mx-0">
          
          <div className="w-full mb-8 text-left">
            <h1 className="text-[40px] font-bold text-slate-900 tracking-tight leading-tight login-heading">
              {isSignup ? "Create account" : "Welcome back"}
            </h1>
            <p className="text-[16px] text-slate-500 mt-2">
              {isSignup ? "Set up your customer profile to get started." : "Sign in to your support command center."}
            </p>
          </div>

          {/* Account type */}
          <div className="login-segmented-control mb-8">
            {[{ key: "customer", label: "Customer", icon: User }, { key: "staff", label: "Staff member", icon: Headset }].map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                type="button"
                onClick={() => { setAccountType(key); if (key === "staff") setMode("signin"); setError(null); }}
                className={`login-button-reset login-segment-btn ${accountType === key ? "active" : ""}`}
              >
                <Icon size={16} strokeWidth={2} /> {label}
              </button>
            ))}
          </div>

          <div className="w-full">
            <GoogleSignInButton onCredential={handleGoogleCredential} />
          </div>

          <div className="login-divider">
            <div className="login-divider-line" />
            <span className="login-divider-text">or</span>
            <div className="login-divider-line" />
          </div>

          <form onSubmit={handleSubmit} className="w-full flex flex-col gap-4">
            {isSignup && (
              <label className="flex flex-col gap-1.5">
                <span className="text-[13px] font-semibold text-slate-700">Full name</span>
                <div className="login-input-wrapper">
                  <User size={18} className="text-slate-400 shrink-0" />
                  <input
                    type="text" required value={name} onChange={(e) => setName(e.target.value)}
                    placeholder="Alex Rivera" className="login-input-reset"
                  />
                </div>
              </label>
            )}

            <label className="flex flex-col gap-1.5">
              <span className="text-[13px] font-semibold text-slate-700">Email / Username</span>
              <div className="login-input-wrapper">
                <Mail size={18} className="text-slate-400 shrink-0" />
                <input
                  type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com" className="login-input-reset"
                />
              </div>
            </label>

            <label className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-semibold text-slate-700">Password</span>
                {!isSignup && (
                  <button type="button" onClick={() => setShowForgotNote((v) => !v)} className="login-button-reset login-link-btn text-[13px]">
                    Forgot password?
                  </button>
                )}
              </div>
              <div className="login-input-wrapper">
                <Lock size={18} className="text-slate-400 shrink-0" />
                <input
                  type={showPassword ? "text" : "password"} required value={password} onChange={(e) => setPassword(e.target.value)}
                  placeholder={isSignup ? "At least 8 characters" : "•••••••••••••"}
                  className="login-input-reset"
                />
                <button type="button" onClick={() => setShowPassword((v) => !v)} className="login-button-reset text-slate-400 hover:text-slate-600 transition-colors shrink-0 flex items-center justify-center h-8 w-8 rounded-full hover:bg-slate-100">
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {showForgotNote && !isSignup && (
                <p className="text-[13px] font-medium text-slate-500 mt-1">
                  There's no automated reset yet — contact {accountType === "staff" ? "your Administrator" : "support"} to reset your password.
                </p>
              )}
            </label>

            {isSignup && (
              <label className="flex flex-col gap-1.5">
                <span className="text-[13px] font-semibold text-slate-700">Confirm password</span>
                <div className="login-input-wrapper">
                  <Lock size={18} className="text-slate-400 shrink-0" />
                  <input
                    type={showPassword ? "text" : "password"} required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter your password" className="login-input-reset"
                  />
                </div>
              </label>
            )}

            {error && (
              <div className="login-error-state mt-2">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="login-button-reset login-primary-btn mt-2"
            >
              {submitting && <Loader2 size={18} className="animate-spin" />}
              {isSignup ? "Create account" : "Sign in"}
            </button>
          </form>

          <div className="w-full mt-6 text-center text-[14px] text-slate-500">
            {accountType === "staff" ? (
              "Staff accounts are created by an Administrator."
            ) : isSignup ? (
              <>Already have an account? <button type="button" onClick={() => switchMode("signin")} className="login-button-reset login-link-btn ml-1">Sign in</button></>
            ) : (
              <>No account yet? <button type="button" onClick={() => switchMode("signup")} className="login-button-reset login-link-btn ml-1">Join for free</button></>
            )}
          </div>

          {!isSignup && (
            <div className="login-demo-card w-full mt-8">
              <div className="text-[12px] font-semibold text-slate-500 mb-3 tracking-wide flex justify-between items-center uppercase">
                <span>Demo accounts</span>
                <span className="normal-case">(password: {DEMO_PASSWORD})</span>
              </div>
              <div className="flex flex-col gap-2.5">
                {DEMO_ACCOUNTS.map((a) => (
                  <div key={a.email} className="flex justify-between items-center gap-3 text-[13px]">
                    <span className="font-medium text-slate-700 truncate">{a.email}</span>
                    <span className="text-slate-500 shrink-0">{a.role}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="login-footer w-full text-left">
            © {new Date().getFullYear()} Servora
          </div>
        </div>
      </div>

      {/* Right — showcase */}
      <div className="hidden lg:block lg:w-1/2 p-2">
        <AuthShowcase />
      </div>
    </div>
  );
}
