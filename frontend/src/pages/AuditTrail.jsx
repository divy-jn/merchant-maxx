import { useState, useEffect } from 'react';
import { ShieldCheck, ShieldAlert } from 'lucide-react';
import { API_BASE_URL } from '../config';
import { useAuth } from '../context/AuthContext';
import './AuditTrail.css';

export default function AuditTrail() {
  const { token } = useAuth();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    fetch(`${API_BASE_URL}/audit/`, { headers })
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch audit logs');
        return res.json();
      })
      .then(data => {
        setLogs(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const getStatusClass = (status) => {
    if (status === 'APPROVED') return 'status-approved';
    if (status === 'REJECTED') return 'status-rejected';
    return 'status-pending';
  };

  const getRiskClass = (score) => {
    if (score < 0.3) return 'risk-low';
    if (score < 0.7) return 'risk-med';
    return 'risk-high';
  };

  if (loading) return <div className="loading animate-fade-in">Loading audit trail...</div>;
  if (error) return <div className="error animate-fade-in">{error}</div>;

  return (
    <div className="audit-container animate-fade-in">
      <div className="audit-header">
        <h1>Agent Audit Trail</h1>
        <p>Immutable log of all AI agent decisions and constitutional safety checks.</p>
      </div>

      <div className="glass-panel audit-table-wrapper">
        <table className="audit-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Agent</th>
              <th>Action Intent</th>
              <th>Safety Status</th>
              <th>Risk Score</th>
              <th>Reasoning</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  No audit logs found. Try chatting with MAXX first.
                </td>
              </tr>
            ) : logs.map(log => (
              <tr key={log.id}>
                <td style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                  {new Date(log.timestamp || log.created_at).toLocaleString()}
                </td>
                <td style={{ fontWeight: '600' }}>{log.agent_name}</td>
                <td>{log.input_summary}</td>
                <td>
                  <span className={`status-badge ${getStatusClass(log.status)}`}>
                    {log.status === 'APPROVED' ? <ShieldCheck size={14} style={{ marginRight: '4px' }}/> : <ShieldAlert size={14} style={{ marginRight: '4px' }}/>}
                    {log.status}
                  </span>
                </td>
                <td>
                  <span className={`risk-score ${getRiskClass(log.risk_score)}`}>
                    {log.risk_score.toFixed(2)}
                  </span>
                </td>
                <td style={{ fontSize: '0.875rem', maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={log.reasoning}>
                  {log.reasoning}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
