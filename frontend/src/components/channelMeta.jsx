import React from "react";

const CHANNEL_LABELS = {
  live_chat: "Live Chat",
  email: "Email",
  whatsapp: "WhatsApp",
  instagram: "Instagram",
  messenger: "Messenger",
};

export function channelLabel(channelKey) {
  if (!channelKey) return "Unknown Channel";
  return CHANNEL_LABELS[channelKey] || channelKey.charAt(0).toUpperCase() + channelKey.slice(1);
}

export function ChannelIcon({ channelKey }) {
  const common = { 
    width: 14, 
    height: 14, 
    viewBox: "0 0 24 24", 
    fill: "none", 
    stroke: "currentColor", 
    strokeWidth: "2", 
    strokeLinecap: "round", 
    strokeLinejoin: "round",
    className: "channel-icon"
  };

  if (channelKey === "live_chat") {
    return (
      <svg {...common}>
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
      </svg>
    );
  }
  if (channelKey === "email") {
    return (
      <svg {...common}>
        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
        <polyline points="22,6 12,13 2,6"></polyline>
      </svg>
    );
  }
  if (channelKey === "whatsapp") {
    return (
      <svg {...common}>
        <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
      </svg>
    );
  }
  if (channelKey === "instagram") {
    return (
      <svg {...common}>
        <rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect>
        <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path>
        <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line>
      </svg>
    );
  }
  if (channelKey === "messenger") {
    return (
      <svg {...common}>
        <path d="M12 2a10 10 0 0 0-10 10c0 2.93 1.25 5.56 3.25 7.37.28.25.46.6.49.98l.18 2.22c.04.5.54.82 1 .63l2.42-.98c.3-.12.64-.13.95-.03a9.92 9.92 0 0 0 1.71.15c5.52 0 10-4.48 10-10S17.52 2 12 2z"></path>
        <path d="M7 14l3.5-3.5 2.5 2.5 4-5-3.5 3.5-2.5-2.5-4 5z"></path>
      </svg>
    );
  }

  // fallback
  return (
    <svg {...common}>
      <circle cx="12" cy="12" r="10"></circle>
      <line x1="12" y1="8" x2="12" y2="12"></line>
      <line x1="12" y1="16" x2="12.01" y2="16"></line>
    </svg>
  );
}

export function ChannelBadge({ channelKey }) {
  return (
    <span className="inbox-channel-badge">
      <ChannelIcon channelKey={channelKey} />
      <span>{channelLabel(channelKey)}</span>
    </span>
  );
}
