import { Outlet, NavLink } from 'react-router-dom';
import { ShoppingBag, MessageSquare, Shield, Activity } from 'lucide-react';
import './DashboardLayout.css';

export default function DashboardLayout() {
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
      </aside>
      
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
