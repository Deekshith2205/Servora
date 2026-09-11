import { useState } from "react";
import { sendChatMessage } from "../api/client";

// Demo customer — issue "Wire up real auth / customer identity" replaces this.
const DEMO_CUSTOMER_ID = 1;

export default function CustomerChat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSend() {
    if (!input.trim()) return;
    const userMessage = { role: "customer", text: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    try {
      const result = await sendChatMessage(DEMO_CUSTOMER_ID, userMessage.text);
      setMessages((prev) => [
        ...prev,
        { role: "agent", text: result.reply, status: result.status, trace: result.trace },
      ]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "agent", text: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel">
      <h2>Customer Chat</h2>
      <div className="chat-window">
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            <p>{m.text}</p>
            {m.status && <span className={`status-tag ${m.status}`}>{m.status}</span>}
          </div>
        ))}
        {loading && <div className="bubble agent">…thinking</div>}
      </div>
      <div className="chat-input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Type a message… e.g. 'Where is my order?'"
        />
        <button onClick={handleSend} disabled={loading}>
          Send
        </button>
      </div>
    </div>
  );
}
