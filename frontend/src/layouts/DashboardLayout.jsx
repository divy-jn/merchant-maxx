import { Outlet, NavLink } from 'react-router-dom';
import { ShoppingBag, MessageSquare, Shield, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './DashboardLayout.css';

export default function DashboardLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="layout-container">
      <aside className="sidebar">
        <NavLink to="/" end className="brand" aria-label="Merchant Maxx home">
          <img src="/merchant-maxx-logo.svg" alt="Merchant Maxx" className="brand-logo" />
        </NavLink>
        <div className="brand-tagline">AI commerce workspace</div>

        <nav className="nav-links" aria-label="Primary navigation">
          <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <ShoppingBag size={18} />
            <span>Catalog</span>
          </NavLink>
          <NavLink to="/chat" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <MessageSquare size={18} />
            <span>MAXX Assistant</span>
          </NavLink>
          <NavLink to="/audit" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <Shield size={18} />
            <span>Agent Activity</span>
          </NavLink>
        </nav>

        <div className="account-area">
          {user ? (
            <div className="account-card">
              <div className="account-avatar">{(user.name || user.email || 'M').charAt(0).toUpperCase()}</div>
              <div className="account-info">
                <strong>{user.name || 'Merchant'}</strong>
                <span>{user.role || 'Account'}</span>
              </div>
              <button onClick={logout} className="icon-button" aria-label="Log out" title="Log out">
                <LogOut size={16} />
              </button>
            </div>
          ) : (
            <NavLink to="/login" className="btn btn-primary login-link">Sign in</NavLink>
          )}
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
