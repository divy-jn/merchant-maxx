import { useState } from 'react';
import { ArrowRight, ShieldCheck } from 'lucide-react';
import { useNavigate, Link } from 'react-router-dom';
import { API_BASE_URL } from '../config';
import './Login.css'; // Reusing Login styling

export default function Register() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password, role: 'customer' })
      });
      
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail || 'Registration failed');
      }
      
      // Navigate to login with success state
      navigate('/login', { state: { message: "Account created successfully. Please sign in." } });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card animate-fade-in">
        <div className="login-header">
          <img src="/merchant-maxx-logo.svg" alt="Merchant Maxx" className="login-logo" />
          <span className="login-eyebrow">AI COMMERCE WORKSPACE</span>
          <h1>Create an account</h1>
          <p>Join Merchant Maxx to start shopping.</p>
        </div>

        {error && <div className="error-message" role="alert">{error}</div>}

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="name">Name</label>
            <input id="name" type="text" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Doe" />
          </div>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
          </div>
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Create a password" minLength={6} />
          </div>
          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm Password</label>
            <input id="confirmPassword" type="password" autoComplete="new-password" required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="Confirm your password" minLength={6} />
          </div>
          <button type="submit" disabled={loading} className="btn btn-primary login-btn" style={{ marginTop: '10px' }}>
            {loading ? 'Creating account…' : <>Create account <ArrowRight size={17} /></>}
          </button>
        </form>

        <div className="login-footer" style={{ textAlign: 'center', marginTop: '15px', fontSize: '0.9rem' }}>
          <span style={{ color: 'var(--text-soft)' }}>Already have an account? </span>
          <Link to="/login" style={{ color: 'var(--primary)', fontWeight: 600, textDecoration: 'none' }}>Sign in</Link>
        </div>
        
        <div className="login-security" style={{ marginTop: '5px' }}><ShieldCheck size={16} /><span>Secure merchant workspace</span></div>
      </div>
    </div>
  );
}
