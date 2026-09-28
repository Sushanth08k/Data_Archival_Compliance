/**
 * AI for Controls — main application with routing.
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './layouts/AppLayout';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import PoliciesPage from './pages/PoliciesPage';
import PolicyDetailPage from './pages/PolicyDetailPage';
import ControlRunsPage from './pages/ControlRunsPage';
import ApprovalsPage from './pages/ApprovalsPage';
import AuditEvidencePage from './pages/AuditEvidencePage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Default route — open login page at start */}
        <Route path="/" element={<Navigate to="/login" replace />} />

        {/* Protected routes */}
        <Route
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/policies" element={<PoliciesPage />} />
          <Route path="/policies/:policyId" element={<PolicyDetailPage />} />
          <Route path="/control-runs" element={<ControlRunsPage />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/audit-evidence" element={<AuditEvidencePage />} />
        </Route>

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
