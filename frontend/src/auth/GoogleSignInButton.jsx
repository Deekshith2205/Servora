import { useEffect, useRef, useState } from "react";

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

let scriptPromise = null;
function loadGoogleScript() {
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Google Identity Services"));
    document.head.appendChild(script);
  });
  return scriptPromise;
}

// A real "Sign in with Google" button — Google's own renderButton()
// draws it (required by Google's branding terms; a hand-drawn look-
// alike button isn't allowed). Renders a plain "not configured" notice
// instead if no VITE_GOOGLE_CLIENT_ID is set, matching this app's own
// convention for an unconfigured integration (see Integrations.jsx's
// Shopify card) rather than showing a broken button.
export default function GoogleSignInButton({ onCredential, onError }) {
  const containerRef = useRef(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!CLIENT_ID || !containerRef.current) return;
    let cancelled = false;

    const renderButton = () => {
      if (!containerRef.current) return;
      const width = Math.round(containerRef.current.getBoundingClientRect().width) || 360;
      containerRef.current.innerHTML = "";
      window.google.accounts.id.renderButton(containerRef.current, {
        type: "standard",
        theme: "outline",
        size: "large",
        text: "signin_with",
        shape: "rectangular",
        logo_alignment: "left",
        width,
      });
    };

    loadGoogleScript()
      .then(() => {
        if (cancelled || !containerRef.current) return;
        window.google.accounts.id.initialize({
          client_id: CLIENT_ID,
          callback: (response) => onCredential(response.credential),
        });
        renderButton();
      })
      .catch((err) => {
        if (cancelled) return;
        setFailed(true);
        onError?.(err.message);
      });

    // Google renders the button at a fixed pixel width — re-render on
    // resize/rotation (e.g. a real device rotation, not just window
    // drag) so it doesn't stay stuck at whatever width it first
    // measured, which would either overflow a now-narrower container
    // or look tiny in a now-wider one.
    const resizeObserver = new ResizeObserver(() => {
      if (window.google?.accounts?.id) renderButton();
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      cancelled = true;
      resizeObserver.disconnect();
    };
  }, [onCredential, onError]);

  if (!CLIENT_ID) {
    return (
      <div className="login-button-reset login-google-btn">
        <svg viewBox="0 0 24 24" width="18" height="18" xmlns="http://www.w3.org/2400/svg">
          <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
          <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
          <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
          <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
        </svg>
        Sign in with Google <span className="text-slate-400 font-normal ml-1">(not configured)</span>
      </div>
    );
  }

  if (failed) {
    return (
      <div className="w-full flex items-center justify-center rounded-xl border border-dashed border-rose-200 bg-rose-50 py-2.5 text-sm text-rose-500">
        Couldn't load Google Sign-In
      </div>
    );
  }

  return <div ref={containerRef} className="w-full flex justify-center [&>div]:!w-full" />;
}
