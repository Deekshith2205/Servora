import { useEffect, useState } from "react";
import {
  ChevronLeft, ChevronRight, Compass, Mail, MessageCircle, MessageSquare, Search,
  Send, ShieldCheck, Sparkles, UserCheck, Camera, CheckCircle2, Wrench,
} from "lucide-react";

// Three honest, illustrative slides — no invented numbers/percentages
// (this codebase's own standing rule against fabricated stats, applied
// here too even though it's just a decorative login-page panel, not a
// real dashboard). Each slide illustrates something Servora's pipeline
// actually does, not a marketing claim.
const CHANNELS = [
  { icon: MessageSquare, color: "#60A5FA" },
  { icon: Mail, color: "#34D399" },
  { icon: MessageCircle, color: "#4ADE80" },
  { icon: Camera, color: "#F472B6" },
  { icon: Send, color: "#C4B5FD" },
];

const PIPELINE = [
  { icon: Search, label: "Classifier" },
  { icon: Compass, label: "Planner" },
  { icon: Wrench, label: "Specialist" },
  { icon: ShieldCheck, label: "Verification" },
  { icon: CheckCircle2, label: "Resolution" },
];

function ChannelsSlide() {
  return (
    <div className="relative flex h-full items-center justify-center">
      <div className="relative flex h-64 w-64 items-center justify-center">
        {CHANNELS.map((c, i) => {
          const angle = (i / CHANNELS.length) * 2 * Math.PI - Math.PI / 2;
          const r = 110;
          const x = Math.cos(angle) * r;
          const y = Math.sin(angle) * r;
          const Icon = c.icon;
          return (
            <div
              key={i}
              className="absolute flex h-14 w-14 items-center justify-center rounded-2xl bg-white/95 shadow-lg"
              style={{ transform: `translate(${x}px, ${y}px)`, color: c.color }}
            >
              <Icon size={24} strokeWidth={2} />
            </div>
          );
        })}
        <div className="absolute h-24 w-24 rounded-full bg-white/15 blur-xl" />
        <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl bg-white shadow-xl">
          <Sparkles size={30} className="text-blue-600" strokeWidth={1.75} />
        </div>
      </div>
    </div>
  );
}

function PipelineSlide() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 px-8">
      <div className="flex items-center gap-2 sm:gap-4">
        {PIPELINE.map((step, i) => {
          const Icon = step.icon;
          return (
            <div key={step.label} className="flex items-center gap-2 sm:gap-4">
              <div className="flex flex-col items-center gap-2">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/95 shadow-lg text-blue-600">
                  <Icon size={20} strokeWidth={2} />
                </div>
                <span className="text-[11px] font-medium text-white/80 whitespace-nowrap">{step.label}</span>
              </div>
              {i < PIPELINE.length - 1 && <div className="h-px w-4 sm:w-6 bg-white/40" />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function EscalationSlide() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 px-8">
      <div className="flex items-center gap-5">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/95 shadow-lg text-blue-600">
          <MessageSquare size={26} strokeWidth={2} />
        </div>
        <div className="h-px w-8 bg-white/40" />
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/95 shadow-lg text-amber-500">
          <ShieldCheck size={26} strokeWidth={2} />
        </div>
        <div className="h-px w-8 bg-white/40" />
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white shadow-xl text-emerald-600">
          <UserCheck size={26} strokeWidth={2} />
        </div>
      </div>
      <span className="text-[11px] font-medium text-white/80 tracking-wide text-center max-w-[260px]">MESSAGE → CONFIDENCE CHECK → HUMAN HANDOFF</span>
    </div>
  );
}

const SLIDES = [
  { Visual: ChannelsSlide, title: "Every channel, one AI core", subtitle: "WhatsApp, email, Instagram, Messenger, and live chat — Servora investigates and replies across all of them from one place." },
  { Visual: PipelineSlide, title: "Investigations that explain themselves", subtitle: "Every resolution carries a full reasoning trace — which agent acted, what evidence it used, and why." },
  { Visual: EscalationSlide, title: "Escalates only when it matters", subtitle: "A confidence-scored handoff to a human agent, with full context attached — not a cold re-explanation." },
];

export default function AuthShowcase() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setIndex((i) => (i + 1) % SLIDES.length), 5000);
    return () => clearInterval(id);
  }, []);

  const go = (delta) => setIndex((i) => (i + delta + SLIDES.length) % SLIDES.length);
  const { Visual, title, subtitle } = SLIDES[index];

  return (
    <div className="group relative h-full w-full overflow-hidden rounded-3xl bg-gradient-to-br from-blue-600 via-blue-500 to-sky-400">
      <div className="absolute inset-0 opacity-[0.15]" style={{ backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)", backgroundSize: "28px 28px" }} />

      <div className="relative flex h-full flex-col">
        <div className="flex-1">
          <Visual />
        </div>

        <div className="px-10 pb-14 text-center">
          <h2 className="text-2xl font-bold text-white mb-3" style={{ fontFamily: "'Syne', sans-serif" }}>{title}</h2>
          <p className="text-sm text-white/75 leading-relaxed max-w-sm mx-auto">{subtitle}</p>
        </div>
      </div>

      <button
        onClick={() => go(-1)}
        aria-label="Previous"
        className="absolute left-4 top-1/2 -translate-y-1/2 flex h-9 w-9 items-center justify-center rounded-full bg-white/15 text-white opacity-0 transition-opacity group-hover:opacity-100 hover:bg-white/25"
      >
        <ChevronLeft size={18} />
      </button>
      <button
        onClick={() => go(1)}
        aria-label="Next"
        className="absolute right-4 top-1/2 -translate-y-1/2 flex h-9 w-9 items-center justify-center rounded-full bg-white/15 text-white opacity-0 transition-opacity group-hover:opacity-100 hover:bg-white/25"
      >
        <ChevronRight size={18} />
      </button>

      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-1.5">
        {SLIDES.map((_, i) => (
          <button
            key={i}
            onClick={() => setIndex(i)}
            aria-label={`Slide ${i + 1}`}
            className="h-1.5 rounded-full transition-all"
            style={{ width: i === index ? 20 : 6, backgroundColor: i === index ? "white" : "rgba(255,255,255,0.4)" }}
          />
        ))}
      </div>
    </div>
  );
}
