// Lucide has no brand logos (no real WhatsApp/Instagram/Messenger glyphs)
// — generic, meaning-appropriate icons instead, differentiated by a real
// per-channel accent color so the set still reads instantly at a glance,
// matching the same 5 real channels app/db/seed.py seeds
// (backend/app/db/models.py::Channel).
import { Camera, Mail, MessageCircle, MessageSquare, Send } from "lucide-react";

export const CHANNEL_STYLE = {
  live_chat: { label: "Live Chat", icon: MessageSquare, color: "#2563EB", bg: "#EFF6FF" },
  email: { label: "Email", icon: Mail, color: "#059669", bg: "#ECFDF5" },
  whatsapp: { label: "WhatsApp", icon: MessageCircle, color: "#22C55E", bg: "#F0FDF4" },
  instagram: { label: "Instagram", icon: Camera, color: "#DB2777", bg: "#FDF2F8" },
  messenger: { label: "Messenger", icon: Send, color: "#7C3AED", bg: "#F5F3FF" },
};

export function channelStyle(key) {
  return CHANNEL_STYLE[key] || { label: key, icon: MessageSquare, color: "#64748B", bg: "#F1F5F9" };
}
