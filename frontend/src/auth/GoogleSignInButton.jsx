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
      <div className="w-full flex items-center justify-center rounded-xl border border-dashed border-slate-300 py-2.5 text-sm text-slate-400">
        Sign in with Google (not configured)
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
