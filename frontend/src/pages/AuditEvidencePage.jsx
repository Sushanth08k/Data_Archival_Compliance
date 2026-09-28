/**
 * Audit Evidence page — displays real audit trail from the backend.
 */

import { useState, useEffect } from 'react';
import api from '../services/api';

const EVENT_COLORS = {
  POLICY_UPLOADED: 'badge-info',
  POLICY_ANALYZED: 'badge-success',
  RULES_CREATED: 'badge-success',
  CONTROL_RUN_STARTED: 'badge-info',
  RECORDS_EVALUATED: 'badge-info',
  ARCHIVE_STARTED: 'badge-warning',
  ARCHIVE_COMPLETED: 'badge-success',
  VERIFICATION_COMPLETED: 'badge-success',
  APPROVAL_REQUESTED: 'badge-warning',
  APPROVAL_GRANTED: 'badge-success',
  APPROVAL_REJECTED: 'badge-error',
  CLEANUP_STARTED: 'badge-warning',
  CLEANUP_COMPLETED: 'badge-success',
};

export default function AuditEvidencePage() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const response = await api.get('/audit-evidence');
        setEvents(response.data.events || []);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    };
    fetchEvents();
  }, []);

  const formatTime = (ts) => {
    return new Date(ts).toLocaleString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Audit Evidence</h1>
        <p className="subtitle">Immutable audit trail for all compliance actions.</p>
      </div>

      {loading ? (
        <div className="loading-overlay"><div className="spinner" /></div>
      ) : events.length === 0 ? (
        <div className="empty-state">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: '16px' }}>
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          <h3>No audit evidence yet</h3>
          <p>Events will appear here as you upload and analyze policies.</p>
        </div>
      ) : (
        <div>
          {events.map((event) => (
            <div key={event.id} className="card" style={{ marginBottom: '8px', padding: '16px 20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span className={`badge ${EVENT_COLORS[event.event_type] || 'badge-neutral'}`}>
                    {event.event_type}
                  </span>
                  {event.actor_email && (
                    <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>
                      by {event.actor_email}
                    </span>
                  )}
                </div>
                <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                  {formatTime(event.timestamp)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
