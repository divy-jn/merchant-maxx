import { useState, useRef, useEffect } from 'react';
import { Send, Trash2 } from 'lucide-react';
import './AgentChat.css';

export default function AgentChat({ sessionId = 'guest' }) {
  const [messages, setMessages] = useState([
    { sender: 'bot', text: 'Hi! I\'m MAXX, your AI shopping assistant at Merchant Maxx. I can help you discover products, compare options, and complete purchases. What are you looking for today?' }
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

  // Load chat history on mount
  useEffect(() => {
    fetch(`http://localhost:8002/chat/history?session_id=${sessionId}`)
      .then(res => res.json())
      .then(data => {
        if (data.length > 0) {
          setMessages([
            { sender: 'bot', text: 'Hi! I\'m MAXX, your AI shopping assistant at Merchant Maxx. I can help you discover products, compare options, and complete purchases. What are you looking for today?' },
            ...data
          ]);
        }
      })
      .catch(() => {}); // Silently fail if no history
  }, [sessionId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { sender: 'user', text: userMessage }]);
    setLoading(true);

    try {
      const res = await fetch('http://localhost:8002/chat/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage, session_id: sessionId })
      });
      
      const data = await res.json();
      setMessages(prev => [...prev, { sender: 'bot', text: data.response || 'Sorry, something went wrong.' }]);
    } catch (err) {
      setMessages(prev => [...prev, { sender: 'bot', text: 'Connection error. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = async () => {
    await fetch(`http://localhost:8002/chat/history?session_id=${sessionId}`, { method: 'DELETE' });
    setMessages([
      { sender: 'bot', text: 'Hi! I\'m MAXX, your AI shopping assistant at Merchant Maxx. What are you looking for today?' }
    ]);
  };

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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1>Chat with MAXX</h1>
            <p>Your AI-powered shopping assistant</p>
          </div>
          <button className="btn btn-outline" onClick={clearChat} style={{ padding: '0.5rem 1rem', fontSize: '0.875rem' }}>
            <Trash2 size={16} />
            Clear Chat
          </button>
        </div>
      </div>

      <div className="chat-box glass-panel">
        <div className="messages-list">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message-item ${msg.sender}`}>
              <div className="message-bubble">
                {msg.sender === 'bot' && <span className="agent-label">MAXX</span>}
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
              placeholder="Ask MAXX anything about our products..."
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
