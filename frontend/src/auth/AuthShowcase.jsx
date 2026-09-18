import { useEffect, useState } from "react";
import {
  ChevronLeft, ChevronRight, Compass, Mail, MessageCircle, MessageSquare, Search,
  Send, ShieldCheck, UserCheck, Camera, CheckCircle2, Wrench, Ticket,
  BarChart3, BookOpen, Plug, Bot
} from "lucide-react";

/* 
 * Decorative Waves Component
 * Renders layered smooth horizontal waves fading into the background.
 */
function DecorativeWaves() {
  return (
    <div className="absolute bottom-0 left-0 right-0 h-[40%] pointer-events-none overflow-hidden z-0">
      <svg viewBox="0 0 1000 300" className="absolute bottom-0 w-full h-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id="wave-grad-1" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#60a5fa" stopOpacity="0" />
            <stop offset="50%" stopColor="#22d3ee" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#60a5fa" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="wave-grad-2" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0" />
            <stop offset="50%" stopColor="#818cf8" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#38bdf8" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="wave-grad-3" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#818cf8" stopOpacity="0" />
            <stop offset="50%" stopColor="#a78bfa" stopOpacity="0.1" />
            <stop offset="100%" stopColor="#818cf8" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d="M0,200 C300,300 700,50 1000,200 L1000,300 L0,300 Z" fill="url(#wave-grad-1)" />
        <path d="M0,240 C400,150 600,300 1000,220 L1000,300 L0,300 Z" fill="url(#wave-grad-2)" />
        <path d="M0,260 C200,300 800,200 1000,280 L1000,300 L0,300 Z" fill="url(#wave-grad-3)" />
      </svg>
      {/* Subtle bottom fade */}
      <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-t from-[#0e214d] to-transparent" />
    </div>
  );
}

/* 
 * Glassmorphism Feature Card Component
 */
function FeatureCard({ icon: Icon, title, desc }) {
  return (
    <div className="relative flex flex-col items-center gap-4 w-[130px] sm:w-[150px] text-center z-10 group">
      <div className="flex h-[72px] w-[72px] sm:h-[84px] sm:w-[84px] items-center justify-center rounded-[20px] bg-white/10 border border-white/20 shadow-[0_8px_32px_rgba(0,0,0,0.2)] backdrop-blur-xl text-white transition-all duration-300 group-hover:-translate-y-2 group-hover:bg-white/15 group-hover:shadow-[0_12px_40px_rgba(56,189,248,0.3)]">
        <Icon size={36} strokeWidth={1.5} className="drop-shadow-[0_2px_10px_rgba(255,255,255,0.3)]" />
      </div>
      <div>
        <div className="text-[14px] sm:text-[15px] font-semibold text-white mb-2 drop-shadow-md tracking-wide">{title}</div>
        <div className="text-[11px] sm:text-[12px] text-white/75 leading-relaxed font-medium">{desc}</div>
      </div>
    </div>
  );
}

/* 
 * Pipeline Node Component
 */
function PipelineNode({ icon: Icon, label, highlight }) {
  return (
    <div className="flex flex-col items-center gap-3 z-10 group">
      <div className={`flex h-[64px] w-[64px] sm:h-[72px] sm:w-[72px] items-center justify-center rounded-2xl border backdrop-blur-xl transition-all duration-300 group-hover:scale-105 ${
        highlight 
          ? "bg-cyan-500/20 border-cyan-300/40 text-cyan-50 shadow-[0_0_30px_rgba(34,211,238,0.4)]" 
          : "bg-white/10 border-white/20 text-white shadow-[0_8px_32px_rgba(0,0,0,0.15)]"
      }`}>
        <Icon size={30} strokeWidth={1.5} className="drop-shadow-md" />
      </div>
      <span className="text-[12px] sm:text-[13px] font-semibold text-white/90 whitespace-nowrap drop-shadow-sm">{label}</span>
    </div>
  );
}


/* ================= SLIDES ================= */

function Slide1Features() {
  const features = [
    { icon: Bot, label: "AI Assistant", desc: "Instant answers for every query" },
    { icon: Ticket, label: "Ticket Management", desc: "Track, assign and resolve" },
    { icon: BarChart3, label: "Analytics", desc: "Insights for better decisions" },
    { icon: BookOpen, label: "Knowledge Base", desc: "Find trusted information" },
    { icon: Plug, label: "Integrations", desc: "Connect your tools and workflows" },
  ];

  return (
    <div className="flex flex-col items-center w-full max-w-5xl mt-16 px-4">
      <div className="flex w-full items-start justify-center gap-6 sm:gap-10 relative">
        {/* Connecting glowing line */}
        <div className="absolute top-[36px] sm:top-[42px] left-[10%] right-[10%] h-[2px] bg-gradient-to-r from-transparent via-cyan-200/50 to-transparent shadow-[0_0_15px_rgba(165,243,252,0.8)] z-0" />
        
        {features.map((f, i) => (
          <FeatureCard key={i} icon={f.icon} title={f.label} desc={f.desc} />
        ))}
      </div>
    </div>
  );
}

function Slide2Omnichannel() {
  const channels = [
    { icon: MessageSquare, label: "Live Chat" },
    { icon: Mail, label: "Email" },
    { icon: MessageCircle, label: "WhatsApp" },
    { icon: Camera, label: "Instagram" },
    { icon: Send, label: "Messenger" },
  ];

  return (
    <div className="flex flex-col items-center w-full max-w-5xl mt-20 px-4">
      <div className="flex w-full items-start justify-center gap-8 sm:gap-14 relative">
        <div className="absolute top-[36px] sm:top-[42px] left-[15%] right-[15%] h-[2px] bg-gradient-to-r from-transparent via-blue-300/60 to-transparent shadow-[0_0_15px_rgba(147,197,253,0.8)] z-0" />
        
        {channels.map((c, i) => (
          <FeatureCard key={i} icon={c.icon} title={c.label} desc="" />
        ))}
      </div>
    </div>
  );
}

function Slide3Pipeline() {
  const pipeline = [
    { icon: MessageSquare, label: "Message" },
    { icon: Search, label: "Classifier" },
    { icon: Compass, label: "Planner" },
    { icon: Wrench, label: "Specialist" },
    { icon: ShieldCheck, label: "Verification" },
    { icon: CheckCircle2, label: "Resolution" },
  ];

  return (
    <div className="flex flex-col items-center w-full max-w-5xl mt-12 px-4 relative">
      <div className="flex items-start justify-center gap-6 sm:gap-10 w-full relative">
        {/* Horizontal connection */}
        <div className="absolute top-[32px] sm:top-[36px] left-[8%] right-[8%] h-[2px] bg-white/20 shadow-[0_0_10px_rgba(255,255,255,0.4)] z-0" />
        
        {pipeline.map((step, i) => (
          <PipelineNode key={i} icon={step.icon} label={step.label} />
        ))}
      </div>
      
      {/* Branch down to Human Handoff */}
      <div className="mt-8 flex flex-col items-center relative">
        <div className="w-[2px] h-10 bg-gradient-to-b from-white/20 to-cyan-300/50 absolute -top-10 shadow-[0_0_10px_rgba(255,255,255,0.4)]" />
        <PipelineNode icon={UserCheck} label="Human Handoff" highlight={true} />
      </div>
    </div>
  );
}

const SLIDES = [
  { 
    Visual: Slide1Features, 
    title: "Smarter Support\nfor a Better Tomorrow", 
    subtitle: "AI-driven tools. Human-centered support.\nAll in one command center." 
  },
  { 
    Visual: Slide2Omnichannel, 
    title: "Every channel.\nOne support command center.", 
    subtitle: "Bring customer conversations together while preserving context across channels." 
  },
  { 
    Visual: Slide3Pipeline, 
    title: "Support that investigates\nbefore it answers.", 
    subtitle: "Understand the issue, plan the response, investigate with tools, verify the result, and escalate with context." 
  },
];

export default function AuthShowcase() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setIndex((i) => (i + 1) % SLIDES.length), 7000);
    return () => clearInterval(id);
  }, []);

  const go = (delta) => setIndex((i) => (i + delta + SLIDES.length) % SLIDES.length);
  const { Visual, title, subtitle } = SLIDES[index];

  return (
    <div className="group relative h-full w-full overflow-hidden rounded-[2.5rem] bg-gradient-to-br from-[#0f172a] via-[#1e3a8a] to-[#0284c7] shadow-2xl">
      
      {/* Deep Layered Backgrounds */}
      <div className="absolute -top-[10%] -left-[10%] w-[70%] h-[70%] rounded-full bg-blue-600/30 blur-[120px] pointer-events-none z-0" />
      <div className="absolute -bottom-[20%] right-0 w-[60%] h-[60%] rounded-full bg-cyan-400/20 blur-[130px] pointer-events-none z-0" />
      
      {/* Subtle dotted/grid texture */}
      <div className="absolute inset-0 opacity-[0.12] mix-blend-overlay pointer-events-none z-0" style={{ backgroundImage: "radial-gradient(circle at 1px 1px, white 2px, transparent 0)", backgroundSize: "32px 32px" }} />
      
      <DecorativeWaves />

      {/* Main Content Flow */}
      <div className="relative flex h-full flex-col px-10 sm:px-16 py-20 z-10">
        
        {/* Top Eyebrow */}
        <div className="w-full text-left mb-6">
          <span className="text-[13px] font-extrabold tracking-[0.3em] text-white/80 uppercase">Servora</span>
        </div>

        {/* Text Header Area - Adjusted for larger scale */}
        <div className="w-full text-left max-w-2xl mb-2 flex flex-col justify-end min-h-[140px]">
          <h2 className="text-4xl sm:text-[2.75rem] font-bold text-white mb-5 leading-[1.15]" style={{ fontFamily: "'Syne', sans-serif" }}>
            {title.split("\n").map((line, i) => (
              <span key={i} className="block">{line}</span>
            ))}
          </h2>
          <p className="text-[16px] sm:text-[18px] text-white/80 leading-relaxed font-medium">
            {subtitle.split("\n").map((line, i) => (
              <span key={i} className="block">{line}</span>
            ))}
          </p>
        </div>

        {/* Center Visual Component */}
        <div className="flex-1 flex flex-col items-center justify-start mt-6 transition-opacity duration-700">
          <Visual />
        </div>

        {/* Bottom Area */}
        <div className="mt-auto flex flex-col items-center justify-end pb-8">
          <div className="text-center text-[13px] font-bold tracking-[0.2em] uppercase mb-10">
            <span className="text-white/95">Powered by AI.</span> <span className="text-white/60">Driven by People.</span>
          </div>
          
          {/* Indicators */}
          <div className="flex items-center gap-3">
            {SLIDES.map((_, i) => (
              <button
                key={i}
                onClick={() => setIndex(i)}
                aria-label={`Slide ${i + 1}`}
                className="h-2 rounded-full transition-all duration-500 ease-out shadow-[0_0_10px_rgba(255,255,255,0.2)]"
                style={{ 
                  width: i === index ? 36 : 10, 
                  backgroundColor: i === index ? "#ffffff" : "rgba(255,255,255,0.25)" 
                }}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Controls */}
      <button
        onClick={() => go(-1)}
        aria-label="Previous"
        className="absolute left-6 top-1/2 -translate-y-1/2 flex h-12 w-12 items-center justify-center rounded-full bg-white/10 text-white opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-white/25 hover:scale-110 backdrop-blur-md shadow-xl z-20 border border-white/10"
      >
        <ChevronLeft size={24} />
      </button>
      <button
        onClick={() => go(1)}
        aria-label="Next"
        className="absolute right-6 top-1/2 -translate-y-1/2 flex h-12 w-12 items-center justify-center rounded-full bg-white/10 text-white opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-white/25 hover:scale-110 backdrop-blur-md shadow-xl z-20 border border-white/10"
      >
        <ChevronRight size={24} />
      </button>
    </div>
  );
}
