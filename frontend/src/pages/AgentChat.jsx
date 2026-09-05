import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Trash2, CreditCard, Sparkles, Plus, MessageSquare, Search, PanelLeftClose, PanelLeftOpen, ShieldCheck } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { API_BASE_URL } from '../config';
import { useAuth } from '../context/AuthContext';
import './AgentChat.css';

const RAZORPAY_KEY_ID = import.meta.env.VITE_RAZORPAY_KEY_ID || '';
const WELCOME = 'Hi! I\'m MAXX, your AI shopping assistant at Merchant Maxx. I can help you discover products, compare options, and complete purchases.';

function titleForConversation(conversation) {
  return conversation?.title?.trim() || 'Untitled conversation';
}

export default function AgentChat({ sessionId = 'guest' }) {
  const { token } = useAuth();
  const [currentConvId, setCurrentConvId] = useState(sessionId);
  const [conversations, setConversations] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [search, setSearch] = useState('');
  const [messages, setMessages] = useState([{ sender: 'bot', text: WELCOME }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [paymentInProgress, setPaymentInProgress] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const authHeaders = useCallback(() => {
    const headers = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
  }, [token]);

  const loadConversations = useCallback(async () => {
    if (!token) {
      setConversations([]);
      return;
    }
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/chat/conversations`, { headers: authHeaders() });
      if (!res.ok) throw new Error('Could not load conversations');
      const data = await res.json();
      setConversations(Array.isArray(data) ? data : []);
    } catch (err) {
      setHistoryError(err.message);
    } finally {
      setHistoryLoading(false);
    }
  }, [token, authHeaders]);

  useEffect(() => { loadConversations(); }, [loadConversations]);

  // Restore guest conversation after login and claim ownership
  useEffect(() => {
    if (!token) return;
    const pendingConvId = localStorage.getItem('pending_conv_id');
    if (!pendingConvId) return;
    localStorage.removeItem('pending_conv_id');
    // Claim the orphan conversation on the backend
    fetch(`${API_BASE_URL}/chat/claim`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: pendingConvId })
    }).then(res => {
      if (res.ok) {
        setCurrentConvId(pendingConvId);
        loadConversations();
      }
    }).catch(() => {});
  }, [token, authHeaders, loadConversations]);

  useEffect(() => {
    if (!currentConvId || currentConvId === 'guest') {
      setMessages([{ sender: 'bot', text: WELCOME }]);
      return;
    }
    const loadHistory = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/chat/history?conversation_id=${encodeURIComponent(currentConvId)}`, { headers: authHeaders() });
        if (!res.ok) throw new Error('Could not load conversation');
        const data = await res.json();
        const loadedMessages = [{ sender: 'bot', text: WELCOME }, ...(Array.isArray(data) ? data : [])];
        let lastCheckoutIdx = -1;
        loadedMessages.forEach((m, i) => { if (m.checkout_data) lastCheckoutIdx = i; });
        if (lastCheckoutIdx !== -1) {
          loadedMessages.forEach((m, i) => { if (m.checkout_data && i !== lastCheckoutIdx) m.checkout_data = { ...m.checkout_data, _stale: true }; });
        }
        setMessages(loadedMessages);
      } catch {
        setMessages([{ sender: 'bot', text: 'This conversation could not be loaded. Start a new chat or try again.' }]);
      }
    };
    loadHistory();
  }, [currentConvId, authHeaders]);

  const selectConversation = (id) => {
    if (loading || id === currentConvId) return;
    setCurrentConvId(id);
    setInput('');
  };

  const startNewChat = () => {
    setCurrentConvId('guest');
    setInput('');
    setMessages([{ sender: 'bot', text: WELCOME }]);
  };

  const handleActionClick = async (actionType, payload) => {
    if (loading) return;
    // Handle LOGIN action: save current chat, then redirect to sign-in page
    if (actionType === 'LOGIN') {
      if (currentConvId && currentConvId !== 'guest') {
        localStorage.setItem('pending_conv_id', currentConvId);
      }
      window.location.href = '/login';
      return;
    }
    setLoading(true);
    setMessages(prev => [...prev, { sender: 'user', text: `[Action: ${actionType.replace(/_/g, ' ')}]` }]);
    try {
      const res = await fetch(`${API_BASE_URL}/chat/action`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: actionType, payload, conversation_id: currentConvId })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Action failed');
      const newMsg = { sender: 'bot', text: data.response || '' };
      if (data.checkout_data) newMsg.checkout_data = data.checkout_data;
      if (data.actions) newMsg.actions = data.actions;

      setMessages(prev => {
        const updated = [...prev];
        if (data.checkout_data || data.purchase_state === 'PAYMENT_SUCCESS') {
          updated.forEach(m => { if (m.checkout_data) m.checkout_data = { ...m.checkout_data, _stale: true }; });
        }
        if (data.actions) {
          updated.forEach(m => { if (m.actions) m.actions = m.actions.map(a => ({ ...a, _stale: true })); });
        }
        if (newMsg.text || newMsg.checkout_data || (newMsg.actions && newMsg.actions.length > 0)) {
          return [...updated, newMsg];
        }
        return updated;
      });
      await loadConversations();
    } catch (err) {
      setMessages(prev => [...prev, { sender: 'bot', text: err.message || 'Connection error. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  const openCheckout = useCallback((orderId, amountStr, purchaseIntentId) => {
    console.log('[Checkout Diagnostics] Public Key present:', !!RAZORPAY_KEY_ID, '| Script loaded:', !!window.Razorpay, '| Order ID:', orderId, '| Amount:', amountStr);

    if (paymentInProgress) return;
    if (!purchaseIntentId) {
      setMessages(prev => [...prev, { sender: 'bot', text: 'This checkout session is missing its purchase reference. Please refresh and try again.' }]);
      return;
    }
    if (!RAZORPAY_KEY_ID) { setMessages(prev => [...prev, { sender: 'bot', text: 'Payment configuration is missing. Please contact support.' }]); return; }
    if (!window.Razorpay) { setMessages(prev => [...prev, { sender: 'bot', text: 'Payment service is loading. Please try again in a moment.' }]); return; }
    setPaymentInProgress(true);
    const options = {
      key: RAZORPAY_KEY_ID,
      order_id: orderId,
      name: 'Merchant Maxx',
      description: 'Purchase via MAXX AI Assistant',
      theme: { color: '#635BFF' },
      handler: async function () {
        setMessages(prev => [...prev, { sender: 'bot', text: '⏳ Verifying payment...' }]);
        try {
          const res = await fetch(`${API_BASE_URL}/chat/action`, {
            method: 'POST',
            headers: { ...authHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({
              action: 'VERIFY_PAYMENT',
              payload: { purchase_intent_id: purchaseIntentId },
              conversation_id: currentConvId
            })
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || 'Payment verification failed');
          const paymentSucceeded = data.purchase_state === 'PAYMENT_SUCCESS';
          setMessages(prev => {
            const updated = prev.filter(m => m.text !== '⏳ Verifying payment...');
            if (paymentSucceeded) {
              updated.forEach(m => {
                if (m.checkout_data) m.checkout_data = { ...m.checkout_data, _stale: true };
                if (m.actions) m.actions = m.actions.map(a => ({ ...a, _stale: true }));
              });
            }
            return [...updated, { sender: 'bot', text: data.response || (paymentSucceeded ? 'Payment received! Thank you for your purchase.' : 'Payment is still being confirmed. Please check again shortly.') }];
          });
          await loadConversations();
        } catch (err) {
          setMessages(prev => [...prev.filter(m => m.text !== '⏳ Verifying payment...'), { sender: 'bot', text: err.message || 'We could not verify the payment yet. Please try again.' }]);
        } finally {
          setPaymentInProgress(false);
        }
      },
      modal: {
        ondismiss: () => {
          setMessages(prev => [...prev, { sender: 'bot', text: 'Payment was cancelled. You can try again when you\'re ready.' }]);
          setPaymentInProgress(false);
        },
        escape: true,
        confirm_close: true
      }
    };
    try {
      const rzp = new window.Razorpay(options);
      rzp.on('payment.failed', paymentFailure => {
        setMessages(prev => [...prev, { sender: 'bot', text: `Payment failed: ${paymentFailure.error?.description || 'Please try again'}.` }]);
        setPaymentInProgress(false);
      });
      // Handle potential internal Razorpay errors
      rzp.on('payment.error', err => {
        setMessages(prev => [...prev, { sender: 'bot', text: 'Payment error encountered. Please try again.' }]);
        setPaymentInProgress(false);
      });

      const rzpOpen = rzp.open();
      // If open() returns a promise (e.g. if blocked), handle rejection
      if (rzpOpen && typeof rzpOpen.catch === 'function') {
        rzpOpen.catch(err => {
          setMessages(prev => [...prev, { sender: 'bot', text: 'Unable to open payment window. Please try again.' }]);
          setPaymentInProgress(false);
        });
      }
    } catch {
      setMessages(prev => [...prev, { sender: 'bot', text: 'Unable to open payment window. Please try again.' }]);
      setPaymentInProgress(false);
    }
  }, [paymentInProgress, authHeaders, currentConvId, loadConversations]);

  const handleSubmit = async (e) => {
    e.preventDefault(); if (!input.trim() || loading) return;
    const userMessage = input.trim(); setInput(''); setMessages(prev => [...prev, { sender: 'user', text: userMessage }]); setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/chat/`, { method: 'POST', headers: { ...authHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify({ message: userMessage, conversation_id: currentConvId }) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Message failed');
      if (data.conversation_id && data.conversation_id !== currentConvId) setCurrentConvId(data.conversation_id);

      const newMsg = { sender: 'bot', text: data.response || '' };
      if (data.checkout_data) newMsg.checkout_data = data.checkout_data;
      if (data.actions) newMsg.actions = data.actions;

      setMessages(prev => {
        const updated = [...prev];
        if (data.checkout_data || data.purchase_state === 'PAYMENT_SUCCESS') {
          updated.forEach(m => { if (m.checkout_data) m.checkout_data = { ...m.checkout_data, _stale: true }; });
        }
        if (data.actions) {
          updated.forEach(m => { if (m.actions) m.actions = m.actions.map(a => ({ ...a, _stale: true })); });
        }
        return [...updated, newMsg];
      });
      await loadConversations();
    } catch (err) { setMessages(prev => [...prev, { sender: 'bot', text: err.message || 'Connection error. Please try again.' }]); }
    finally { setLoading(false); }
  };

  const clearChat = async () => {
    if (currentConvId === 'guest') {
      setMessages([{ sender: 'bot', text: WELCOME }]);
      return;
    }
    await fetch(`${API_BASE_URL}/chat/history?conversation_id=${encodeURIComponent(currentConvId)}`, { method: 'DELETE', headers: authHeaders() });
    setConversations(prev => prev.filter(c => c.id !== currentConvId));
    startNewChat();
  };

  const renderMessageText = (text, msg) => {
    let content = [];
    if (msg?.checkout_data) {
      const d = msg.checkout_data;
      if (d._stale) {
        // Do not render anything for stale checkout cards to avoid confusing the user during recovery.
      } else {
        const formattedAmount = (d.amount_paise / 100).toLocaleString('en-IN', { style: 'currency', currency: 'INR' });
        content.push(
          <div key="checkout" className="checkout-card animate-fade-in">
            <div className="checkout-header">
              <h4>ORDER READY</h4>
            </div>
            <div className="checkout-items">
              {d.items && d.items.map((item, i) => (
                <div key={i} className="checkout-item-row">
                  <span className="item-name">{item.name}</span>
                  <span className="item-qty">Qty {item.quantity}</span>
                </div>
              ))}
            </div>
            <div className="checkout-total">
              <span>Total</span>
              <strong>{formattedAmount}</strong>
            </div>
            <div className="checkout-secure-badge">
              <ShieldCheck size={14} /> Secure payment via Razorpay
            </div>
            <button className="btn btn-primary pay-now-btn" onClick={() => openCheckout(d.order_id, d.amount_paise / 100, d.purchase_intent_id)} disabled={paymentInProgress}>
              <CreditCard size={18} />
              {paymentInProgress ? 'Processing…' : `Pay ${formattedAmount}`}
            </button>
          </div>
        );
      }
    }

    if (msg?.sender === 'user') {
      content.push(<span key="text">{text}</span>);
    } else {
      if (text) content.push(<div key="text" className="markdown-body"><ReactMarkdown>{text}</ReactMarkdown></div>);
    }

    if (msg?.actions && msg.actions.length > 0) {
      content.push(
        <div key="actions" className="message-actions" style={{display: 'flex', gap: '8px', marginTop: '12px', flexWrap: 'wrap'}}>
          {msg.actions.map((action, i) => (
             <button key={i} className="btn btn-outline action-btn" disabled={action._stale || loading} onClick={() => handleActionClick(action.type, action.payload)}>
               {action.label}
             </button>
          ))}
        </div>
      );
    }

    return content;
  };

  const filteredConversations = conversations.filter(c => titleForConversation(c).toLowerCase().includes(search.trim().toLowerCase()));

  return (
    <div className={`chat-workspace ${sidebarOpen ? '' : 'sidebar-collapsed'} animate-fade-in`}>
      {sidebarOpen && <aside className="conversation-sidebar">
        <div className="conversation-header">
          <div className="conversation-brand"><div className="conversation-brand-mark"><Sparkles size={16} /></div><div><strong>MAXX</strong><span>Conversations</span></div></div>
          <button className="icon-button chat-sidebar-close" onClick={() => setSidebarOpen(false)} aria-label="Close conversations"><PanelLeftClose size={17} /></button>
        </div>
        <button className="new-chat-button" onClick={startNewChat}><Plus size={17} /> New chat</button>
        <div className="conversation-search"><Search size={15} /><input aria-label="Search conversations" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search chats" /></div>
        <div className="conversation-list">
          {historyLoading && <div className="conversation-empty">Loading chats…</div>}
          {historyError && <div className="conversation-empty error">{historyError}</div>}
          {!historyLoading && !historyError && filteredConversations.length === 0 && <div className="conversation-empty"><MessageSquare size={18} /><span>{search ? 'No matching chats' : 'Your saved chats will appear here'}</span></div>}
          {!historyLoading && !historyError && filteredConversations.map(conversation => (
            <button key={conversation.id} className={`conversation-item ${conversation.id === currentConvId ? 'active' : ''}`} onClick={() => selectConversation(conversation.id)}>
              <MessageSquare size={16} />
              <span className="conversation-copy"><strong>{titleForConversation(conversation)}</strong><small>{conversation.updated_at ? new Date(conversation.updated_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : ''}</small></span>
            </button>
          ))}
        </div>
      </aside>}

      <section className="chat-main">
        <div className="chat-header">
          <div className="chat-title-group"><button className={`icon-button chat-sidebar-open ${sidebarOpen ? 'hidden' : ''}`} onClick={() => setSidebarOpen(true)} aria-label="Open conversations"><PanelLeftOpen size={18} /></button><div className="assistant-mark"><Sparkles size={19} /></div><div><h1>MAXX Assistant</h1><p>Your AI commerce copilot</p></div></div>
          <button className="btn btn-outline" onClick={clearChat}><Trash2 size={16} /> Clear</button>
        </div>
        <div className="chat-box glass-panel">
          <div className="messages-list">
            {messages.map((msg, idx) => <div key={idx} className={`message-item ${msg.sender}`}><div className={`message-bubble ${msg.checkout_data ? 'checkout-bubble' : ''}`}>{msg.sender === 'bot' && !msg.checkout_data && <span className="agent-label">MAXX · AI ASSISTANT</span>}{renderMessageText(msg.text, msg)}</div></div>)}
            {loading && <div className="message-item bot"><div className="typing-indicator"><span></span><span></span><span></span> MAXX is thinking</div></div>}
            <div ref={messagesEndRef} />
          </div>
          <div className="chat-input-container"><form className="chat-form" onSubmit={handleSubmit}><input aria-label="Message MAXX" type="text" className="chat-input" placeholder="Ask MAXX to find, compare, or buy…" value={input} onChange={e => setInput(e.target.value)} disabled={loading} /><button type="submit" className="btn btn-primary send-btn" disabled={loading || !input.trim()}><Send size={18} /><span>Send</span></button></form></div>
        </div>
      </section>
    </div>
  );
}
