import { useState, useRef, useEffect } from 'react';
import { Send, Trash2 } from 'lucide-react';
import { API_BASE_URL } from '../config';
import { useAuth } from '../context/AuthContext';
import './AgentChat.css';

export default function AgentChat({ sessionId = 'guest' }) {
  const { token } = useAuth();
  const [currentConvId, setCurrentConvId] = useState(sessionId);
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
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    fetch(`${API_BASE_URL}/chat/history?conversation_id=${currentConvId}`, { headers })
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
  }, [currentConvId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { sender: 'user', text: userMessage }]);
    setLoading(true);

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(`${API_BASE_URL}/chat/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ message: userMessage, conversation_id: currentConvId })
      });
      
      const data = await res.json();
      if (data.conversation_id && data.conversation_id !== currentConvId) {
        setCurrentConvId(data.conversation_id);
      }
      setMessages(prev => [...prev, { sender: 'bot', text: data.response || 'Sorry, something went wrong.' }]);
    } catch (err) {
      setMessages(prev => [...prev, { sender: 'bot', text: 'Connection error. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = async () => {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    await fetch(`${API_BASE_URL}/chat/history?conversation_id=${currentConvId}`, { method: 'DELETE', headers });
    setMessages([
      { sender: 'bot', text: 'Hi! I\'m MAXX, your AI shopping assistant at Merchant Maxx. What are you looking for today?' }
    ]);
  };

  const renderMessageText = (text) => {
    // Match URLs but strip trailing punctuation that isn't part of the URL
    const urlRegex = /(https?:\/\/[^\s\)\]\>,]+)/g;
    return text.split(urlRegex).map((part, i) => {
      if (part.match(/^https?:\/\//)) {
        // Clean any remaining trailing punctuation
        const cleanUrl = part.replace(/[)}\].,;:!?]+$/, '');
        return <a key={i} href={cleanUrl} target="_blank" rel="noopener noreferrer">{cleanUrl}</a>;
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
