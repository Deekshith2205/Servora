import { useState } from "react";
import { Loader2, Lock, Mail, Sparkles, User } from "lucide-react";
import { useAuth } from "../auth/AuthContext";

const DEMO_ACCOUNTS = [
  { email: "alice@example.com", role: "Customer" },
  { email: "bob@example.com", role: "Customer" },
  { email: "jordan.lee@servora.example", role: "Support Agent" },
  { email: "priya.shah@servora.example", role: "Manager" },
  { email: "sam.okafor@servora.example", role: "Administrator" },
];
const DEMO_PASSWORD = "Demo1234!";

// A real sign-in/sign-up screen backed by app/api/auth.py's real
// login/register endpoints — password verified against a real stored
// hash, a real server-side session token issued on success. No one-
// click role impersonation anywhere on this page by design.
export default function Login() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState("signin"); // "signin" | "signup"
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const isSignup = mode === "signup";

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

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-white px-4 py-10" style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center text-center mb-8">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-sky-500 text-white shadow-lg shadow-blue-500/30 mb-5">
            <Sparkles size={26} strokeWidth={1.75} />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900" style={{ fontFamily: "'Syne', sans-serif" }}>
            {isSignup ? "Create your account" : "Sign in to Servora"}
          </h1>
          <p className="text-slate-500 mt-3 text-[15px]">
            {isSignup ? "Set up a real customer account to chat with Servora's AI." : "Autonomous customer support, backed by a real login."}
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-[0_1px_2px_rgba(15,23,42,0.04),0_20px_25px_-5px_rgba(15,23,42,0.08)] flex flex-col gap-4"
        >
          {isSignup && (
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold text-slate-600">Full name</span>
              <div className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2.5 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-shadow">
                <User size={16} className="text-slate-400 shrink-0" />
                <input
                  type="text" required value={name} onChange={(e) => setName(e.target.value)}
                  placeholder="Alex Rivera" className="w-full text-sm outline-none bg-transparent text-slate-900"
                />
              </div>
            </label>
          )}

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-semibold text-slate-600">Email</span>
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2.5 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-shadow">
              <Mail size={16} className="text-slate-400 shrink-0" />
              <input
                type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com" className="w-full text-sm outline-none bg-transparent text-slate-900"
              />
            </div>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-semibold text-slate-600">Password</span>
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2.5 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-shadow">
              <Lock size={16} className="text-slate-400 shrink-0" />
              <input
                type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder={isSignup ? "At least 8 characters" : "••••••••"}
                className="w-full text-sm outline-none bg-transparent text-slate-900"
              />
            </div>
          </label>

          {isSignup && (
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold text-slate-600">Confirm password</span>
              <div className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2.5 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-shadow">
                <Lock size={16} className="text-slate-400 shrink-0" />
                <input
                  type="password" required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
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
            {isSignup ? "Create account" : "Sign in"}
          </button>

          <p className="text-center text-sm text-slate-500 mt-1">
            {isSignup ? (
              <>Already have an account?{" "}
                <button type="button" onClick={() => switchMode("signin")} className="text-blue-600 font-semibold hover:underline">Sign in</button>
              </>
            ) : (
              <>New here?{" "}
                <button type="button" onClick={() => switchMode("signup")} className="text-blue-600 font-semibold hover:underline">Create a customer account</button>
              </>
            )}
          </p>
        </form>

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
    </div>
  );
}
