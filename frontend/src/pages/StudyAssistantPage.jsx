import { useEffect, useRef, useState } from "react";
import Icon from "../components/Icon.jsx";

const suggestedPrompts = [
  "How am I performing overall?",
  "Show my attendance for every subject.",
  "Which assignments are due this week?",
  "Explain database indexing in simple words.",
  "What is the difference between supervised and unsupervised learning?",
  "Give me a practical example of a REST API.",
  "Explain a topic step by step.",
];

export default function StudyAssistantPage({ sendMessage }) {
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [draft, setDraft] = useState("");
  const [pendingMessage, setPendingMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const conversationRef = useRef(null);
  const inputRef = useRef(null);
  const submittingRef = useRef(false);

  useEffect(() => {
    if (conversationRef.current) {
      conversationRef.current.scrollTop = conversationRef.current.scrollHeight;
    }
  }, [messages, pendingMessage, isLoading]);

  async function submitMessage(event) {
    event?.preventDefault();
    const message = draft.trim();
    if (!message || submittingRef.current) return;

    submittingRef.current = true;
    setError("");
    setDraft("");
    setPendingMessage(message);
    setIsLoading(true);
    try {
      const response = await sendMessage(message, conversationId);
      setMessages((current) => [
        ...current,
        { role: "user", content: message },
        { role: "assistant", content: response.answer },
      ]);
      setConversationId(response.conversation_id);
    } catch (requestError) {
      setDraft(message);
      setError(
        requestError?.message || "Could not send your question. Please try again.",
      );
    } finally {
      setPendingMessage("");
      submittingRef.current = false;
      setIsLoading(false);
      inputRef.current?.focus();
    }
  }

  function startNewConversation() {
    setMessages([]);
    setConversationId(null);
    setDraft("");
    setPendingMessage("");
    setError("");
    inputRef.current?.focus();
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitMessage();
    }
  }

  return (
    <section className="chat-shell" aria-label="Study Assistant chat">
      <header className="chat-header">
        <div className="chat-title">
          <span className="chat-avatar">
            <Icon name="assistant" size={20} />
          </span>
          <div>
            <h2>Study Assistant</h2>
            <p>Your AI tutor for learning, one question at a time.</p>
          </div>
        </div>
        <button
          className="new-chat-button"
          type="button"
          onClick={startNewConversation}
          disabled={isLoading}
        >
          <span aria-hidden="true">+</span>
          New conversation
        </button>
      </header>

      <div className="chat-messages" ref={conversationRef} aria-live="polite">
        {messages.length === 0 && !pendingMessage ? (
          <div className="chat-empty">
            <span className="chat-empty-icon">
              <Icon name="assistant" size={25} />
            </span>
            <h3>What would you like to learn?</h3>
            <p>
              Ask a question, paste your notes to summarize them, or explore a
              concept step by step.
            </p>
            <div className="prompt-grid" aria-label="Suggested prompts">
              {suggestedPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="suggested-prompt"
                  disabled={isLoading}
                  onClick={() => {
                    setDraft(prompt);
                    inputRef.current?.focus();
                  }}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat-thread">
            {messages.map((message, index) => (
              <article className={`chat-message ${message.role}`} key={`${index}-${message.role}`}>
                <span className="message-label">
                  {message.role === "assistant" ? "Study Assistant" : "You"}
                </span>
                <p>{message.content}</p>
              </article>
            ))}
            {pendingMessage && (
              <>
                <article className="chat-message user">
                  <span className="message-label">You</span>
                  <p>{pendingMessage}</p>
                </article>
                {isLoading && (
                  <article className="chat-message assistant" role="status">
                    <span className="message-label">Study Assistant</span>
                    <p className="thinking-indicator">
                      <span />
                      <span />
                      <span />
                      <span className="sr-only">Thinking…</span>
                    </p>
                  </article>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="chat-error" role="alert">
          <span>{error}</span>
          <small>Your question is still in the box; you can retry it.</small>
        </div>
      )}

      <form className="chat-composer" onSubmit={submitMessage}>
        <label className="sr-only" htmlFor="study-assistant-message">
          Your question
        </label>
        <textarea
          ref={inputRef}
          id="study-assistant-message"
          value={draft}
          maxLength={5000}
          placeholder="Ask a question or paste your notes…"
          onChange={(event) => {
            setDraft(event.target.value);
            if (error) setError("");
          }}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          rows={2}
        />
        <div className="composer-footer">
          <span>Enter to send · Shift+Enter for a new line</span>
          <button
            className="send-button"
            type="submit"
            disabled={isLoading || !draft.trim()}
          >
            {isLoading ? "Sending…" : "Send"}
            <Icon name="arrow" size={16} />
          </button>
        </div>
      </form>
    </section>
  );
}
