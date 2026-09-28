/**
 * AppLayout — sidebar navigation + main content area.
 * Matches the prototype's layout with sidebar nav and safety banner.
 */

import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import authService from '../services/auth';

export default function AppLayout() {
  const navigate = useNavigate();
  const user = authService.getUser();

  const handleLogout = () => {
    authService.logout();
    navigate('/login');
  };

  const getInitials = (name) => {
    if (!name) return '?';
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const formatRole = (role) => {
    if (!role) return '';
    return role.replace(/_/g, ' ');
  };

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h1>AI for Controls</h1>
          <p>Policy control runs</p>
        </div>

        <nav className="sidebar-nav">
          <NavLink to="/dashboard">
            <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
            </svg>
            Dashboard
          </NavLink>

          <NavLink to="/policies">
            <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
            </svg>
            Policies
          </NavLink>

          <NavLink to="/control-runs">
            <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
            Control runs
          </NavLink>

          <NavLink to="/approvals">
            <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
            </svg>
            Approval queue
          </NavLink>

          <NavLink to="/audit-evidence">
            <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            Audit evidence
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="sidebar-user-avatar">
              {getInitials(user?.full_name)}
            </div>
            <div className="sidebar-user-info">
              <div className="sidebar-user-name">{user?.full_name || 'User'}</div>
              <div className="sidebar-user-role">{formatRole(user?.role)}</div>
            </div>
          </div>
          <button className="btn btn-sm" onClick={handleLogout} style={{ marginTop: '8px', width: '100%', color: 'rgba(255,255,255,0.6)' }}>
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="main-content">
        {/* Safety banner */}
        <div className="safety-banner">
          <strong>Archive first. Verify. Then obtain human approval before source cleanup.</strong>
          <p>Source records are never removed without an approval on record.</p>
        </div>

        <Outlet />
      </main>
    </div>
  );
}
