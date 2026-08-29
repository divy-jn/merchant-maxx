import { Outlet, NavLink } from 'react-router-dom';
import { ShoppingBag, MessageSquare, Shield, Activity } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './DashboardLayout.css';

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  
  return (
    <div className="layout-container">
      <aside className="sidebar">
        <div className="brand">
          <Activity className="brand-icon" size={28} />
          <span>Merchant Maxx</span>
        </div>
        
        <nav className="nav-links">
          <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <ShoppingBag size={20} />
            Catalog
          </NavLink>
          <NavLink to="/chat" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <MessageSquare size={20} />
            Agent Chat
          </NavLink>
          <NavLink to="/audit" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <Shield size={20} />
            Audit Trail
          </NavLink>
        </nav>

        <div style={{ marginTop: 'auto', padding: '1rem' }}>
          {user ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div style={{ fontSize: '0.875rem', opacity: 0.8 }}>Logged in as {user.name}</div>
              <button onClick={logout} className="btn btn-outline" style={{ padding: '0.5rem' }}>Logout</button>
            </div>
          ) : (
            <NavLink to="/login" className="btn btn-primary" style={{ display: 'flex', width: '100%', textDecoration: 'none' }}>
              Login
            </NavLink>
          )}
        </div>
      </aside>
      
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
