import { useState } from 'react';
import { Activity, ArrowRight, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import './Login.css';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, error } = useAuth();
  const navigate = useNavigate();

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
          <div className="login-mark"><Activity size={22} /></div>
          <span className="login-eyebrow">MERCHANT MAXX</span>
          <h1>Welcome back</h1>
          <p>Sign in to continue to your commerce workspace.</p>
        </div>

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
          <button type="submit" disabled={loading} className="btn btn-primary login-btn">
            {loading ? 'Signing in…' : <>Sign in <ArrowRight size={17} /></>}
          </button>
        </form>

        <div className="login-security"><ShieldCheck size={16} /><span>Secure merchant workspace</span></div>
      </div>
    </div>
  );
}
