import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Trash2, CreditCard } from 'lucide-react';
import { API_BASE_URL } from '../config';
import { useAuth } from '../context/AuthContext';
import './AgentChat.css';

const RAZORPAY_KEY_ID = import.meta.env.VITE_RAZORPAY_KEY_ID || '';

// Detects Razorpay order ID in bot messages (order_XXXX pattern)
const ORDER_ID_REGEX = /Order ID:\s*(order_\w+)/i;
// Detects amount in bot messages
const AMOUNT_REGEX = /Amount:\s*Rs\.\s*([\d,]+\.\d{2})/i;

export default function AgentChat({ sessionId = 'guest' }) {
  const { token } = useAuth();
  const [currentConvId, setCurrentConvId] = useState(sessionId);
  const [messages, setMessages] = useState([
    { sender: 'bot', text: 'Hi! I\'m MAXX, your AI shopping assistant at Merchant Maxx. I can help you discover products, compare options, and complete purchases. What are you looking for today?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [paymentInProgress, setPaymentInProgress] = useState(false);
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

  // ── Razorpay Checkout handler ─────────────────────────────────────
  const openCheckout = useCallback((orderId, amountStr) => {
    if (paymentInProgress) return; // double-click guard
    if (!RAZORPAY_KEY_ID) {
      setMessages(prev => [...prev, { sender: 'bot', text: '⚠️ Payment configuration is missing. Please contact support.' }]);
      return;
    }
    if (!window.Razorpay) {
      setMessages(prev => [...prev, { sender: 'bot', text: '⚠️ Payment service is loading. Please try again in a moment.' }]);
      return;
    }

    setPaymentInProgress(true);

    // Amount comes from server via chat message — we display it but Razorpay
    // uses the amount from the order (server-side). We don't pass amount to
    // Razorpay options because the order already has the authoritative amount.
    const options = {
      key: RAZORPAY_KEY_ID,
      order_id: orderId,
      name: 'Merchant Maxx',
      description: 'Purchase via MAXX AI Assistant',
      theme: { color: '#4F46E5' },
      handler: async function (response) {
        // Payment successful callback — verify with backend
        setMessages(prev => [...prev, { sender: 'bot', text: '⏳ Verifying payment...' }]);
        try {
          const headers = { 'Content-Type': 'application/json' };
          if (token) headers['Authorization'] = `Bearer ${token}`;

          const res = await fetch(`${API_BASE_URL}/chat/`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
              message: 'Check payment status',
              conversation_id: currentConvId
            })
          });
          const data = await res.json();
          setMessages(prev => {
            // Remove the "Verifying..." message and add the real status
            const filtered = prev.filter(m => m.text !== '⏳ Verifying payment...');
            return [...filtered, { sender: 'bot', text: data.response || '✅ Payment received! Thank you for your purchase.' }];
          });
        } catch {
          setMessages(prev => {
            const filtered = prev.filter(m => m.text !== '⏳ Verifying payment...');
            return [...filtered, { sender: 'bot', text: '✅ Payment submitted. Your order will be confirmed shortly.' }];
          });
        }
        setPaymentInProgress(false);
      },
      modal: {
        ondismiss: function () {
          setMessages(prev => [...prev, { sender: 'bot', text: 'Payment was cancelled. You can try again by saying "pay" or "proceed".' }]);
          setPaymentInProgress(false);
        },
        escape: true,
        confirm_close: true
      }
    };

    try {
      const rzp = new window.Razorpay(options);
      rzp.on('payment.failed', function (response) {
        setMessages(prev => [...prev, {
          sender: 'bot',
          text: `❌ Payment failed: ${response.error?.description || 'Please try again'}. You can say "retry" to attempt again.`
        }]);
        setPaymentInProgress(false);
      });
      rzp.open();
    } catch (err) {
      setMessages(prev => [...prev, { sender: 'bot', text: '⚠️ Unable to open payment window. Please try again.' }]);
      setPaymentInProgress(false);
    }
  }, [paymentInProgress, token, currentConvId]);

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

      const botText = data.response || 'Sorry, something went wrong.';
      setMessages(prev => [...prev, { sender: 'bot', text: botText }]);

      // ── Auto-detect Razorpay order and offer checkout ──
      const orderMatch = botText.match(ORDER_ID_REGEX);
      const amountMatch = botText.match(AMOUNT_REGEX);
      if (orderMatch && orderMatch[1]) {
        // Small delay so the order message renders first
        setTimeout(() => {
          setMessages(prev => [...prev, {
            sender: 'bot',
            text: `__PAY_BUTTON__${orderMatch[1]}__${amountMatch ? amountMatch[1] : ''}`,
            isPayButton: true
          }]);
        }, 300);
      }
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

  const renderMessageText = (text, msg) => {
    // Pay button special message
    if (msg && msg.isPayButton) {
      const parts = text.replace('__PAY_BUTTON__', '').split('__');
      const orderId = parts[0];
      const amount = parts[1] || '';
      return (
        <button
          className="btn btn-primary pay-now-btn"
          onClick={() => openCheckout(orderId, amount)}
          disabled={paymentInProgress}
          style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            padding: '0.75rem 1.5rem', fontSize: '1rem', fontWeight: 600,
            cursor: paymentInProgress ? 'not-allowed' : 'pointer',
            opacity: paymentInProgress ? 0.6 : 1
          }}
        >
          <CreditCard size={18} />
          {paymentInProgress ? 'Processing...' : `Pay Now${amount ? ` — Rs. ${amount}` : ''}`}
        </button>
      );
    }

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
                {msg.sender === 'bot' && !msg.isPayButton && <span className="agent-label">MAXX</span>}
                {renderMessageText(msg.text, msg)}
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
