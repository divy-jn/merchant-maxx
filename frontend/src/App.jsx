import { BrowserRouter, Routes, Route } from 'react-router-dom';
import DashboardLayout from './layouts/DashboardLayout';
import Catalog from './pages/Catalog';
import AgentChat from './pages/AgentChat';
import AuditTrail from './pages/AuditTrail';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<Catalog />} />
          <Route path="chat" element={<AgentChat />} />
          <Route path="audit" element={<AuditTrail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
