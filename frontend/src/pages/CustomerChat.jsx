import { useState, useRef, useEffect } from "react";
import {
  fetchCustomerRecord,
  fetchInvestigationByTicket,
  fetchMyTickets,
  openInvestigationStream,
  sendChatMessage,
} from "../api/client";
import { appendLiveStep, clearLive, finishLive, startLive } from "../liveInvestigation";
import { useAuth } from "../auth/AuthContext";

import InvestigationTimeline from "../components/InvestigationTimeline";
import ExplainableAIPanel from "../components/ExplainableAIPanel";
import ConnectedSystemsPanel from "../components/ConnectedSystemsPanel";
import DemoScenarioSelector from "../components/DemoScenarioSelector";
import { AgentIcon, agentLabel } from "../components/agentMeta";

export default function CustomerChat() {
  const { currentUser } = useAuth();
  // GET /api/auth/me returns customer_id/user_id, never a bare "id" — see
  // app/auth/dependency.py::CurrentActor. A staff identity (Administrator
  // included, despite holding every permission via the real union — see
  // CLAUDE.md's [RBAC] #199 entry) has no customer_id at all, since
  // issue #181 ties this chat to whoever is genuinely authenticated as a
  // customer rather than a hardcoded demo id.
  const customerId = currentUser?.customer_id;
  const customerName = currentUser?.name || (customerId ? `Customer #${customerId}` : null);

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  // [SWARM] issue #79: real steps arriving live via SSE while /api/chat is
  // still in flight — replaces the old "Investigating..." dots-only
  // placeholder with the actual pipeline stages as they complete.
  const [liveSteps, setLiveSteps] = useState([]);
  const messagesEndRef = useRef(null);

  // Customer Context panel (Part 3) — real, queried data, not the old
  // static placeholder text.
  const [customerContext, setCustomerContext] = useState(null);
  const [openTicketsCount, setOpenTicketsCount] = useState(null);
  // Connected Systems panel (Part 2) — the most recently completed
  // investigation's real steps, so it can show which systems each
  // agent actually queried (InvestigationStep.used_tools).
  const [lastInvestigationSteps, setLastInvestigationSteps] = useState(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, liveSteps]);

  function refreshCustomerContext() {
    if (!customerId) return;
    fetchCustomerRecord(customerId).then(setCustomerContext).catch(() => {});
    fetchMyTickets()
      .then((tickets) => setOpenTicketsCount(tickets.filter((t) => t.status === "open").length))
      .catch(() => {});
  }

  useEffect(() => {
    refreshCustomerContext();
    setLastInvestigationSteps(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerId]);

  async function handleSend() {
    if (!input.trim()) return;
    if (!customerId) {
      // A staff identity has no real customer_id to send as (see the
      // customerId derivation above) — fail clearly instead of letting
      // sendChatMessage go out with an undefined id and 422.
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          text: "Switch to a Customer identity (see \"Demo Role\" above) to send a message here — this chat represents what a real customer sees, not a staff view.",
          status: "error",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
      setInput("");
      return;
    }
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
      const result = await sendChatMessage(customerId, userMessage.text, streamKey);
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
      // Real investigation just completed — refresh the Customer Context
      // panel (open ticket count, recent refund requests, etc. may have
      // changed) and pull the real per-agent tool usage for the
      // Connected Systems panel.
      refreshCustomerContext();
      if (result.ticket_id) {
        fetchInvestigationByTicket(result.ticket_id)
          .then((inv) => setLastInvestigationSteps(inv.timeline))
          .catch(() => {});
      }
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
          <div className="chat-input-row" style={{marginBottom: '0.5rem'}}>
            <DemoScenarioSelector onSelect={setInput} disabled={loading} />
          </div>
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
        <div className="chat-customer-name">{customerName}</div>
        <div className="chat-customer-id">Active Session</div>

        {!customerId ? (
          <div className="chat-context-section">
            <div className="chat-context-value">
              Customer Context is only available when signed in as a Customer — this staff identity has no customer profile to show.
            </div>
          </div>
        ) : !customerContext ? (
          <div className="chat-context-section">
            <div className="chat-context-value">Loading customer profile…</div>
          </div>
        ) : (
          <div className="chat-context-section">
            <div className="chat-context-section-title">Profile</div>
            <dl className="chat-context-fields">
              <dt>Customer Since</dt>
              <dd>{customerContext.customer_since ? new Date(customerContext.customer_since).toLocaleDateString() : "—"}</dd>
              <dt>Account Status</dt>
              <dd style={{textTransform: 'capitalize'}}>{customerContext.account_status}</dd>
              <dt>Total Orders</dt>
              <dd>{customerContext.total_orders}</dd>
              <dt>Last Order</dt>
              <dd>
                {customerContext.last_order
                  ? `${customerContext.last_order.product} (${customerContext.last_order.status})`
                  : "None yet"}
              </dd>
              <dt>Payment Method</dt>
              <dd>{customerContext.payment_method || "None on file"}</dd>
              <dt>Open Tickets</dt>
              <dd>{openTicketsCount ?? "—"}</dd>
            </dl>

            {customerContext.recent_refund_requests.length > 0 && (
              <>
                <div className="chat-context-section-title" style={{marginTop: '0.75rem'}}>Recent Refund Requests</div>
                <ul style={{margin: 0, paddingLeft: '1.25rem', color: 'inherit'}}>
                  {customerContext.recent_refund_requests.map((r) => (
                    <li key={r.payment_id}>
                      ${r.amount.toFixed(2)} — {r.status.replace("_", " ")}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}

        <div className="chat-context-section">
          <div className="chat-context-section-title">Connected Systems</div>
          <ConnectedSystemsPanel steps={lastInvestigationSteps} />
        </div>
      </div>
    </div>
  );
}
