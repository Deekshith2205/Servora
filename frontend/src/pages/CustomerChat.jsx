import { useState, useRef, useEffect } from "react";
import { sendChatMessage } from "../api/client";

// Demo customer — issue "Wire up real auth / customer identity" replaces this.
const DEMO_CUSTOMER_ID = 1;

function InvestigationPanel({ trace }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!trace || trace.length === 0) return null;

  return (
    <div className="investigation-panel">
      <div 
        className={`investigation-header ${isOpen ? 'open' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          {isOpen ? <polyline points="6 9 12 15 18 9"></polyline> : <polyline points="9 18 15 12 9 6"></polyline>}
        </svg>
        Investigation details
      </div>
      {isOpen && (
        <div className="investigation-content">
          {trace.map((t, idx) => (
            <div key={idx} className="investigation-step">
              <div className="investigation-step-icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              </div>
              <div>{t}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CustomerChat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  async function handleSend() {
    if (!input.trim()) return;
    const userMessage = { role: "customer", text: input, timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    try {
      const result = await sendChatMessage(DEMO_CUSTOMER_ID, userMessage.text);
      setMessages((prev) => [
        ...prev,
        { 
          role: "agent", 
          text: result.reply, 
          status: result.status, 
          trace: result.trace,
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
              <div className="chat-meta">
                {m.timestamp && <span>{m.timestamp}</span>}
                {m.status && (
                  <span className={`app-badge badge-${m.status === 'resolved' ? 'success' : m.status === 'escalated' ? 'warning' : 'neutral'}`}>
                    {m.status}
                  </span>
                )}
              </div>
              
              {m.role === 'agent' && m.trace && m.trace.length > 0 && (
                <InvestigationPanel trace={m.trace} />
              )}
            </div>
          ))}
          
          {loading && (
            <div className="chat-bubble-wrapper agent">
              <div className="chat-bubble agent" style={{display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
                <span style={{opacity: 0.5}}>Investigating</span>
                <span className="dot-pulse">...</span>
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
