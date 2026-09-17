import { useState } from "react";
import { Eye, EyeOff, Headset, Loader2, Lock, Mail, Sparkles, User } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import GoogleSignInButton from "../auth/GoogleSignInButton";
import AuthShowcase from "../auth/AuthShowcase";

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
    <div className="min-h-screen w-full bg-white flex items-stretch p-3" style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Left — form */}
      <div className="flex w-full lg:w-1/2 flex-col px-4 sm:px-10 lg:px-16 py-8">
        <a href="/" className="flex items-center gap-2 mb-auto pb-10">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-600 to-sky-500 text-white">
            <Sparkles size={16} strokeWidth={2} />
          </span>
          <span className="text-lg font-bold text-slate-900" style={{ fontFamily: "'Syne', sans-serif" }}>Servora</span>
        </a>

        <div className="w-full max-w-md mx-auto lg:mx-0 my-auto py-10">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900" style={{ fontFamily: "'Syne', sans-serif" }}>
            {isSignup ? "Create your account" : "Welcome back"}
          </h1>
          <p className="text-slate-500 mt-2 text-[15px]">
            {isSignup ? "Set up a real customer account to chat with Servora's AI." : "Sign in to your support command center."}
          </p>

          {/* Account type — framing only, the backend always resolves the real role from the account */}
          <div className="mt-6 inline-flex rounded-full border border-slate-200 bg-slate-50 p-1 text-sm">
            {[{ key: "customer", label: "Customer", icon: User }, { key: "staff", label: "Staff member", icon: Headset }].map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                type="button"
                onClick={() => { setAccountType(key); if (key === "staff") setMode("signin"); setError(null); }}
                className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 font-medium transition-colors ${accountType === key ? "bg-white text-blue-700 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
              >
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>

          <div className="mt-6">
            <GoogleSignInButton onCredential={handleGoogleCredential} />
          </div>

          <div className="flex items-center gap-3 my-6">
            <div className="h-px flex-1 bg-slate-200" />
            <span className="text-xs text-slate-400">or</span>
            <div className="h-px flex-1 bg-slate-200" />
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {isSignup && (
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-semibold text-slate-600">Full name</span>
                <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-shadow">
                  <User size={16} className="text-slate-400 shrink-0" />
                  <input
                    type="text" required value={name} onChange={(e) => setName(e.target.value)}
                    placeholder="Alex Rivera" className="w-full text-sm outline-none bg-transparent text-slate-900"
                  />
                </div>
              </label>
            )}

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold text-slate-600">Email / Username</span>
              <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-shadow">
                <Mail size={16} className="text-slate-400 shrink-0" />
                <input
                  type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com" className="w-full text-sm outline-none bg-transparent text-slate-900"
                />
              </div>
            </label>

            <label className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-600">Password</span>
                {!isSignup && (
                  <button type="button" onClick={() => setShowForgotNote((v) => !v)} className="text-xs font-medium text-blue-600 hover:underline">
                    Forgot password?
                  </button>
                )}
              </div>
              <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-shadow">
                <Lock size={16} className="text-slate-400 shrink-0" />
                <input
                  type={showPassword ? "text" : "password"} required value={password} onChange={(e) => setPassword(e.target.value)}
                  placeholder={isSignup ? "At least 8 characters" : "••••••••"}
                  className="w-full text-sm outline-none bg-transparent text-slate-900"
                />
                <button type="button" onClick={() => setShowPassword((v) => !v)} className="text-slate-400 hover:text-slate-600 shrink-0">
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {showForgotNote && !isSignup && (
                <p className="text-xs text-slate-500 mt-0.5">
                  There's no automated reset yet — contact {accountType === "staff" ? "your Administrator" : "support"} to reset your password.
                </p>
              )}
            </label>

            {isSignup && (
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-semibold text-slate-600">Confirm password</span>
                <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-shadow">
                  <Lock size={16} className="text-slate-400 shrink-0" />
                  <input
                    type={showPassword ? "text" : "password"} required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter your password" className="w-full text-sm outline-none bg-transparent text-slate-900"
                  />
                </div>
              </label>
            )}

            {error && (
              <div className="rounded-lg bg-rose-50 border border-rose-200 px-3 py-2 text-sm text-rose-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="mt-1 flex items-center justify-center gap-2 rounded-xl bg-blue-600 text-white font-semibold text-sm py-2.5 hover:bg-blue-700 transition-colors disabled:opacity-60"
            >
              {submitting && <Loader2 size={15} className="animate-spin" />}
              {isSignup ? "Create account" : "Sign In"}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-5">
            {accountType === "staff" ? (
              "Staff accounts are created by an Administrator — contact them for access."
            ) : isSignup ? (
              <>Already have an account?{" "}
                <button type="button" onClick={() => switchMode("signin")} className="text-blue-600 font-semibold hover:underline">Sign in</button>
              </>
            ) : (
              <>No account yet?{" "}
                <button type="button" onClick={() => switchMode("signup")} className="text-blue-600 font-semibold hover:underline">Join for free</button>
              </>
            )}
          </p>

          {!isSignup && (
            <div className="mt-6 rounded-xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-3 text-xs text-slate-500">
              <div className="font-semibold text-slate-600 mb-1.5">Demo accounts (password: {DEMO_PASSWORD})</div>
              <div className="flex flex-col gap-0.5">
                {DEMO_ACCOUNTS.map((a) => (
                  <div key={a.email} className="flex justify-between gap-3">
                    <span>{a.email}</span>
                    <span className="text-slate-400">{a.role}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="mt-auto pt-10 text-xs text-slate-400">© {new Date().getFullYear()} Servora</div>
      </div>

      {/* Right — showcase */}
      <div className="hidden lg:block lg:w-1/2 p-2">
        <AuthShowcase />
      </div>
    </div>
  );
}
