import { useState, useRef, useEffect } from 'react';
import { Send } from 'lucide-react';
import './AgentChat.css';

export default function AgentChat() {
  const [messages, setMessages] = useState([
    { sender: 'bot', text: 'Hi! I am MAXX, your AI Commerce Orchestrator. Looking for a product, or want me to create a payment link for something?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { sender: 'user', text: userMessage }]);
    setLoading(true);

    try {
      const res = await fetch('http://localhost:8000/chat/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage })
      });
      
      const data = await res.json();
      setMessages(prev => [...prev, { sender: 'bot', text: data.response || 'Sorry, I encountered an error.' }]);
    } catch (err) {
      setMessages(prev => [...prev, { sender: 'bot', text: 'Error connecting to the agent backend.' }]);
    } finally {
      setLoading(false);
    }
  };

  // Helper to safely render text with potential URLs
  const renderMessageText = (text) => {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    return text.split(urlRegex).map((part, i) => {
      if (part.match(urlRegex)) {
        return <a key={i} href={part} target="_blank" rel="noopener noreferrer">{part}</a>;
      }
      return part;
    });
  };

  return (
    <div className="chat-container animate-fade-in">
      <div className="chat-header">
        <h1>Agent Chat</h1>
        <p>Talk to MAXX, Scout, and Closer to discover and buy products.</p>
      </div>

      <div className="chat-box glass-panel">
        <div className="messages-list">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message-item ${msg.sender}`}>
              <div className="message-bubble">
                {renderMessageText(msg.text)}
              </div>
            </div>
          ))}
          {loading && (
            <div className="message-item bot">
              <div className="typing-indicator">MAXX is thinking...</div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-container">
          <form className="chat-form" onSubmit={handleSubmit}>
            <input 
              type="text" 
              className="chat-input"
              placeholder="E.g., I want to buy a gaming keyboard..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            <button type="submit" className="btn btn-primary send-btn" disabled={loading || !input.trim()}>
              <Send size={18} />
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
