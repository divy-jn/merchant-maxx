import { useState } from 'react';
import { ArrowRight, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import './Login.css';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, error } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const successMessage = location.state?.message;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    const success = await login(email, password);
    setLoading(false);
    if (success) navigate('/chat');
  };

  return (
    <div className="login-container">
      <div className="login-card animate-fade-in">
        <div className="login-header">
          <img src="/merchant-maxx-logo.svg" alt="Merchant Maxx" className="login-logo" />
          <span className="login-eyebrow">AI COMMERCE WORKSPACE</span>
          <h1>Welcome back</h1>
          <p>Sign in to continue to your commerce workspace.</p>
        </div>

        {successMessage && <div className="success-message" role="status" style={{ background: '#ecfdf5', color: '#047857', padding: '11px 13px', borderRadius: '10px', fontSize: '0.86rem', border: '1px solid #a7f3d0' }}>{successMessage}</div>}
        {error && <div className="error-message" role="alert">{error}</div>}

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
          </div>
          <div className="form-group">
            <div className="label-row"><label htmlFor="password">Password</label></div>
            <input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" />
          </div>
          <button type="submit" disabled={loading} className="btn btn-primary login-btn" style={{ marginTop: '5px' }}>
            {loading ? 'Signing in…' : <>Sign in <ArrowRight size={17} /></>}
          </button>
        </form>

        <div className="login-footer" style={{ textAlign: 'center', marginTop: '10px', fontSize: '0.9rem' }}>
          <span style={{ color: 'var(--text-soft)' }}>New to Merchant MAXX? </span>
          <Link to="/register" style={{ color: 'var(--primary)', fontWeight: 600, textDecoration: 'none' }}>Create an account</Link>
        </div>

        <div className="login-security" style={{ marginTop: '5px' }}><ShieldCheck size={16} /><span>Secure merchant workspace</span></div>
      </div>
    </div>
  );
}
