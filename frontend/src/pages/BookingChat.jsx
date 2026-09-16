import { useState, useRef, useEffect, useCallback } from "react";
import { sendBookingMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";

// Issue #19: browser-mic voice I/O, demo-safe (no telephony/Twilio) — see
// CLAUDE.md's "Key decisions". Both Web Speech APIs are optional browser
// features (Firefox in particular has no SpeechRecognition), so every use
// is feature-detected and the text path always works regardless.
const SpeechRecognitionCtor =
  typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);
const speechSynthesisSupported = typeof window !== "undefined" && "speechSynthesis" in window;

function BookingConfirmationCard({ booking }) {
  return (
    <div className="handoff-card">
      <p className="handoff-card-title">Booking drafted — pending staff review</p>
      <dl>
        <dt>Room</dt>
        <dd style={{ textTransform: "capitalize" }}>{booking.room_type}</dd>
        <dt>Dates</dt>
        <dd>{booking.check_in} &rarr; {booking.check_out}</dd>
        <dt>Guests</dt>
        <dd>{booking.guests}</dd>
        <dt>Total price</dt>
        <dd>${booking.total_price.toFixed(2)}</dd>
        <dt>Status</dt>
        <dd>
          <span className="app-badge badge-neutral">{booking.status}</span>
        </dd>
      </dl>
    </div>
  );
}

export default function BookingChat() {
  const { currentUser } = useAuth();
  const customerId = currentUser?.id;
  const customerName = currentUser?.name || `Customer #${customerId}`;

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [booking, setBooking] = useState(null);
  const [listening, setListening] = useState(false);
  const [voiceReplies, setVoiceReplies] = useState(speechSynthesisSupported);
  const [micError, setMicError] = useState(null);
  const messagesEndRef = useRef(null);
  const recognitionRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const speak = useCallback(
    (text) => {
      if (!voiceReplies || !speechSynthesisSupported) return;
      window.speechSynthesis.cancel(); // don't stack replies if one is still talking
      const utterance = new SpeechSynthesisUtterance(text);
      window.speechSynthesis.speak(utterance);
    },
    [voiceReplies]
  );

  const sendTurn = useCallback(
    async (text) => {
      if (!text.trim() || booking) return; // #18's agent creates at most one booking per chat
      const userMessage = { role: "user", content: text };
      const nextMessages = [...messages, userMessage];
      setMessages(nextMessages);
      setInput("");
      setLoading(true);
      try {
        const result = await sendBookingMessage(customerId, nextMessages);
        setMessages([...nextMessages, { role: "assistant", content: result.reply }]);
        if (result.booking) setBooking(result.booking);
        speak(result.reply);
      } catch (err) {
        setMessages([
          ...nextMessages,
          { role: "assistant", content: `Error: ${err.message}`, isError: true },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [messages, booking, speak, customerId]
  );

  const handleSend = () => sendTurn(input);

  const handleMicClick = () => {
    if (!SpeechRecognitionCtor) return;
    setMicError(null);

    if (listening) {
      recognitionRef.current?.stop();
      return;
    }

    const recognition = new SpeechRecognitionCtor();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      sendTurn(transcript);
    };
    recognition.onerror = (event) => {
      setMicError(
        event.error === "not-allowed" || event.error === "service-not-allowed"
          ? "Microphone access was denied — allow it in your browser to use voice input."
          : `Speech recognition error: ${event.error}`
      );
    };
    recognition.onend = () => setListening(false);

    recognitionRef.current = recognition;
    setListening(true);
    recognition.start();
  };

  // Stop any in-flight recognition on unmount so it doesn't keep listening
  // after the user navigates away from this tab.
  useEffect(() => {
    return () => recognitionRef.current?.stop();
  }, []);

  return (
    <div className="chat-layout">
      <div className="chat-main">
        <div className="chat-window">
          {messages.length === 0 && (
            <div className="app-empty-state" style={{ padding: "2rem 1rem", marginTop: "auto", marginBottom: "auto" }}>
              <p>Tell Servora what kind of room you'd like — by typing or speaking.</p>
              <p style={{ fontSize: "0.85rem", opacity: 0.7 }}>
                e.g. "I'd like a deluxe room for 2 guests, checking in Dec 1st and out Dec 4th."
              </p>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`chat-bubble-wrapper ${m.role === "user" ? "customer" : "agent"}`}>
              <div className={`chat-bubble ${m.role === "user" ? "customer" : "agent"} ${m.isError ? "error" : ""}`}>
                {m.content}
              </div>
            </div>
          ))}

          {booking && (
            <div className="chat-bubble-wrapper agent">
              <BookingConfirmationCard booking={booking} />
            </div>
          )}

          {loading && (
            <div className="chat-bubble-wrapper agent">
              <div className="chat-bubble agent" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span style={{ opacity: 0.5 }}>Thinking</span>
                <span className="dot-pulse">...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {micError && (
          <p className="error" style={{ margin: "0 1rem", fontSize: "0.8rem" }}>
            {micError}
          </p>
        )}

        <div className="chat-input-area">
          <div className="chat-input-row">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder={booking ? "Booking drafted — a staff member will review it next." : "Type a message, or use the mic..."}
              disabled={loading || !!booking}
            />
            {SpeechRecognitionCtor && (
              <button
                type="button"
                onClick={handleMicClick}
                disabled={loading || !!booking}
                title={listening ? "Stop listening" : "Speak instead of typing"}
                style={{
                  background: listening ? "var(--app-danger, #dc2626)" : "var(--app-surface)",
                  color: listening ? "#fff" : "inherit",
                  border: "1px solid var(--app-border)",
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                  <line x1="12" y1="19" x2="12" y2="23"></line>
                </svg>
                {listening ? "Listening…" : "Speak"}
              </button>
            )}
            <button onClick={handleSend} disabled={loading || !input.trim() || !!booking}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
              Send
            </button>
          </div>
        </div>
      </div>

      <div className="chat-context">
        <h3>Voice Booking</h3>
        <div className="chat-customer-name">{customerName}</div>
        <div className="chat-customer-id">Active Session</div>

        <div className="chat-context-section">
          <div className="chat-context-section-title">Voice</div>
          <div className="chat-context-value">
            {SpeechRecognitionCtor ? (
              <p style={{ margin: "0 0 0.5rem" }}>Click "Speak" and talk — no phone call needed.</p>
            ) : (
              <p style={{ margin: "0 0 0.5rem" }}>
                This browser doesn't support speech-to-text. Type instead — the same Booking Agent handles both.
              </p>
            )}
            {speechSynthesisSupported && (
              <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.85rem" }}>
                <input
                  type="checkbox"
                  checked={voiceReplies}
                  onChange={(e) => setVoiceReplies(e.target.checked)}
                />
                Read replies aloud
              </label>
            )}
          </div>
        </div>

        <div className="chat-context-section">
          <div className="chat-context-section-title">Room types</div>
          <div className="chat-context-value">
            <ul style={{ margin: 0, paddingLeft: "1.25rem", color: "inherit" }}>
              <li>Standard</li>
              <li>Deluxe</li>
              <li>Suite</li>
            </ul>
          </div>
        </div>

        <div className="chat-context-section">
          <div className="chat-context-section-title">What happens next</div>
          <div className="chat-context-value">
            A confirmed booking here is drafted, not final — hotel staff review and confirm it in the Staff Dashboard.
          </div>
        </div>
      </div>
    </div>
  );
}
