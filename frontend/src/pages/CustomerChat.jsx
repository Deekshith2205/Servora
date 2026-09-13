import { useState, useRef, useEffect } from "react";
import { openInvestigationStream, sendChatMessage } from "../api/client";
import { appendLiveStep, clearLive, finishLive, startLive } from "../liveInvestigation";

// Demo customer — issue "Wire up real auth / customer identity" replaces this.
const DEMO_CUSTOMER_ID = 1;

import InvestigationTimeline from "../components/InvestigationTimeline";
import ExplainableAIPanel from "../components/ExplainableAIPanel";
import { AgentIcon, agentLabel } from "../components/agentMeta";

export default function CustomerChat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  // [SWARM] issue #79: real steps arriving live via SSE while /api/chat is
  // still in flight — replaces the old "Investigating..." dots-only
  // placeholder with the actual pipeline stages as they complete.
  const [liveSteps, setLiveSteps] = useState([]);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, liveSteps]);

  async function handleSend() {
    if (!input.trim()) return;
    const userMessage = { role: "customer", text: input, timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    setLiveSteps([]);

    // [SWARM] issue #79: open the real-time stream BEFORE the request that
    // will actually produce events on it — see openInvestigationStream's
    // docstring in api/client.js. [SWARM] issue #85: publish to the
    // shared liveInvestigation module too, so the Agent Swarm view (a
    // different page) can show this same investigation as "LIVE" if the
    // user switches to it mid-flight.
    const streamKey = crypto.randomUUID();
    startLive(streamKey);
    const closeStream = openInvestigationStream(streamKey, {
      onStep: (step) => {
        setLiveSteps((prev) => [...prev, step]);
        appendLiveStep(step);
      },
      onDone: (doneEvent) => finishLive(doneEvent),
    });

    try {
      const result = await sendChatMessage(DEMO_CUSTOMER_ID, userMessage.text, streamKey);
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          text: result.reply,
          status: result.status,
          trace: result.trace,
          handoffPacket: result.handoff_packet,
          ticketId: result.ticket_id,
          timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          text: `Error: ${err.message}`,
          timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
        }
      ]);
    } finally {
      setLoading(false);
      setLiveSteps([]);
      closeStream();
      clearLive();
    }
  }

  return (
    <div className="chat-layout">
      {/* Main Chat Area */}
      <div className="chat-main">
        <div className="chat-window">
          {messages.length === 0 && (
            <div className="app-empty-state" style={{padding: '2rem 1rem', marginTop: 'auto', marginBottom: 'auto'}}>
              <p>Start a conversation. Servora will investigate and respond.</p>
            </div>
          )}
          
          {messages.map((m, i) => (
            <div key={i} className={`chat-bubble-wrapper ${m.role}`}>
              <div className={`chat-bubble ${m.role}`}>
                {m.text}
              </div>
              
              {m.handoffPacket && (
                <div className="handoff-card">
                  <p className="handoff-card-title">What we're passing to a human agent</p>
                  <dl>
                    <dt>Situation</dt>
                    <dd>{m.handoffPacket.situation}</dd>
                    <dt>Likely cause</dt>
                    <dd>{m.handoffPacket.root_cause_hypothesis}</dd>
                    <dt>Recommended next step</dt>
                    <dd>{m.handoffPacket.recommended_action}</dd>
                    <dt>Urgency</dt>
                    <dd>{m.handoffPacket.urgency}/10</dd>
                  </dl>
                </div>
              )}

              <div className="chat-meta">
                {m.timestamp && <span>{m.timestamp}</span>}
                {m.status && (
                  <span className={`app-badge badge-${m.status === 'resolved' ? 'success' : m.status === 'escalated' ? 'warning' : 'neutral'}`}>
                    {m.status}
                  </span>
                )}
              </div>
              
              {m.role === 'agent' && m.trace && m.trace.length > 0 && (
                <InvestigationTimeline trace={m.trace} />
              )}

              {/* [EXPLAIN] issue #93/#99: "Why did Servora recommend this?" */}
              {m.role === 'agent' && m.ticketId && (
                <ExplainableAIPanel ticketId={m.ticketId} mode="compact" />
              )}
            </div>
          ))}
          
          {loading && (
            <div className="chat-bubble-wrapper agent">
              <div className="chat-bubble agent live-investigating-bubble">
                {liveSteps.length === 0 ? (
                  <div style={{display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
                    <span style={{opacity: 0.5}}>Investigating</span>
                    <span className="dot-pulse">...</span>
                  </div>
                ) : (
                  <div className="live-steps-list">
                    {liveSteps.map((s, i) => (
                      <div key={i} className="live-step-row">
                        <span className="live-step-icon"><AgentIcon agentName={s.agent_name} /></span>
                        <span>{agentLabel(s.agent_name)}</span>
                        <span className="live-step-dots">...</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        
        <div className="chat-input-area">
          <div className="chat-input-row">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Type a message... e.g. 'Where is my order?'"
              disabled={loading}
            />
            <button onClick={handleSend} disabled={loading || !input.trim()}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
              Send
            </button>
          </div>
        </div>
      </div>

      {/* Right Side Context Panel */}
      <div className="chat-context">
        <h3>Customer Context</h3>
        <div className="chat-customer-name">Demo Customer #{DEMO_CUSTOMER_ID}</div>
        <div className="chat-customer-id">Active Session</div>

        <div className="chat-context-section">
          <div className="chat-context-section-title">Available Information</div>
          <div className="chat-context-value">
            <ul style={{margin: 0, paddingLeft: '1.25rem', color: 'inherit'}}>
              <li>Account active</li>
              <li>Order history accessible</li>
              <li>Knowledge base enabled</li>
            </ul>
          </div>
        </div>
        
        <div className="chat-context-section">
          <div className="chat-context-section-title">Workflow</div>
          <div className="chat-context-value">
            This demo environment connects to a live SQLite backend. The agent has tools to query orders and tickets.
          </div>
        </div>
      </div>
    </div>
  );
}
