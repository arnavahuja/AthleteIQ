import { useState, useRef, useEffect } from "react";
import VoiceRecorder from "./VoiceRecorder";
import ResultsTable from "./ResultsTable";
import Visualization from "./Visualization";
import { sendQuery } from "../api/client";

export default function ChatInterface() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [pendingTranscription, setPendingTranscription] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const addMessage = (msg) => {
    setMessages((prev) => [...prev, { ...msg, timestamp: new Date().toLocaleTimeString() }]);
  };

  // Build conversation history from messages for context
  const buildHistory = () => {
    const history = [];
    for (const msg of messages) {
      if (msg.role === "user" && msg.type !== "voice") {
        history.push({ role: "user", content: msg.content });
      } else if (msg.role === "assistant" && msg.type === "result") {
        history.push({
          role: "assistant",
          content: msg.content,
          sql: msg.sql || "",
          summary: msg.content || "",
        });
      }
    }
    // Keep last 6 messages (3 exchanges)
    return history.slice(-6);
  };

  const processResponse = (data, userQuery) => {
    if (data.error) {
      const isRateLimit = data.error_type === "rate_limit";
      const retryAfter = data.retry_after;
      let errorContent = data.error;
      if (isRateLimit && retryAfter) {
        errorContent = `${data.error}\n\nYour query will be ready if you retry in ~${retryAfter} seconds.`;
      }
      addMessage({
        role: "assistant",
        content: errorContent,
        type: "error",
        retryQuery: isRateLimit ? userQuery : null,
        retryAfter: retryAfter,
      });
      return;
    }

    addMessage({
      role: "assistant",
      content: data.summary || "Here are the results:",
      table: data.table,
      visualization: data.visualization,
      sql: data.sql,
      context: data.retrieved_context,
      type: "result",
    });
  };

  const handleTextSubmit = async (e) => {
    e.preventDefault();
    const query = input.trim();
    if (!query || loading) return;

    addMessage({ role: "user", content: query });
    setInput("");
    setLoading(true);

    try {
      const data = await sendQuery(query, buildHistory());
      processResponse(data, query);
    } catch (err) {
      addMessage({ role: "assistant", content: `Error: ${err.message}`, type: "error" });
    } finally {
      setLoading(false);
    }
  };

  const handleVoiceTranscription = (transcript) => {
    // Show transcription for confirmation before sending
    addMessage({ role: "user", content: `Voice: "${transcript}"`, type: "voice" });
    setPendingTranscription(transcript);
    addMessage({
      role: "assistant",
      content: `I heard: "${transcript}"`,
      type: "transcription",
    });
  };

  const confirmTranscription = async () => {
    if (!pendingTranscription || loading) return;
    const query = pendingTranscription;
    setPendingTranscription(null);
    setLoading(true);

    try {
      const data = await sendQuery(query, buildHistory());
      processResponse(data, query);
    } catch (err) {
      addMessage({ role: "assistant", content: `Error: ${err.message}`, type: "error" });
    } finally {
      setLoading(false);
    }
  };

  const editTranscription = () => {
    if (!pendingTranscription) return;
    setInput(pendingTranscription);
    setPendingTranscription(null);
  };

  const handleRetry = async (query) => {
    if (!query || loading) return;
    setLoading(true);
    try {
      const data = await sendQuery(query, buildHistory());
      processResponse(data, query);
    } catch (err) {
      addMessage({ role: "assistant", content: `Error: ${err.message}`, type: "error" });
    } finally {
      setLoading(false);
    }
  };

  const [expandedSql, setExpandedSql] = useState(null);

  return (
    <div className="chat-interface">
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="empty-state">
            <h2>AthleteIQ</h2>
            <p>Ask questions about athlete performance using text or voice.</p>
            <div className="example-queries">
              <p>Try asking:</p>
              <button onClick={() => setInput("Which athletes had the highest workload?")}>
                "Which athletes had the highest workload?"
              </button>
              <button onClick={() => setInput("Show average sprint distance by position")}>
                "Show average sprint distance by position"
              </button>
              <button onClick={() => setInput("How has fatigue changed over the weeks?")}>
                "How has fatigue changed over the weeks?"
              </button>
              <button onClick={() => setInput("Compare Team A vs Team B total workload")}>
                "Compare Team A vs Team B total workload"
              </button>
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role} ${msg.type || ""}`}>
            <div className="message-header">
              <span className="role-label">{msg.role === "user" ? "You" : "AthleteIQ"}</span>
              <span className="timestamp">{msg.timestamp}</span>
            </div>
            <div className="message-content" style={{ whiteSpace: "pre-wrap" }}>{msg.content}</div>

            {msg.retryQuery && (
              <div className="retry-actions">
                <button
                  onClick={() => handleRetry(msg.retryQuery)}
                  disabled={loading}
                  className="retry-btn"
                >
                  Retry Query
                </button>
              </div>
            )}

            {msg.type === "transcription" && pendingTranscription && (
              <div className="transcription-actions">
                <button onClick={confirmTranscription} className="confirm-btn">
                  Confirm & Search
                </button>
                <button onClick={editTranscription} className="edit-btn">
                  Edit Query
                </button>
              </div>
            )}

            {msg.visualization && msg.table && (
              <Visualization config={msg.visualization} data={msg.table} />
            )}

            {msg.table && msg.table.rows && msg.table.rows.length > 0 && (
              <ResultsTable columns={msg.table.columns} rows={msg.table.rows} />
            )}

            {msg.sql && (
              <div className="sql-section">
                <button
                  className="sql-toggle"
                  onClick={() => setExpandedSql(expandedSql === idx ? null : idx)}
                >
                  {expandedSql === idx ? "Hide SQL" : "Show SQL"}
                </button>
                {expandedSql === idx && (
                  <pre className="sql-display">{msg.sql}</pre>
                )}
              </div>
            )}

            {msg.context && (
              <div className="context-tags">
                {msg.context.kpis?.map((k) => (
                  <span key={k.name} className="tag kpi-tag">KPI: {k.name}</span>
                ))}
                {msg.context.schema_tables?.map((t) => (
                  <span key={t} className="tag schema-tag">{t}</span>
                ))}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="message assistant loading">
            <div className="typing-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="input-area" onSubmit={handleTextSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about athlete performance..."
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()} className="send-btn">
          Send
        </button>
        <VoiceRecorder onTranscription={handleVoiceTranscription} disabled={loading} />
      </form>
    </div>
  );
}
