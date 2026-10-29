import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import SignUp from './pages/SignUp';
import ProtectedRoute from './components/ProtectedRoute';
import ResearcherLayout from './components/ResearcherLayout';
import RDashboard from './pages/R-Dashboard';
import RRunSetting from './pages/R-RunSetting';
import RMonitor from './pages/R-Monitor';
import RMonitorLive from './pages/R-MonitorLive';
import RDiagnosis from './pages/R-Diagnosis';
import RFixes from './pages/R-Fixes';
import RReports from './pages/R-Reports';
import RCompare from './pages/R-Compare';
import DesignSystem from './pages/DesignSystem';
import AdminLayout from './components/AdminLayout';
import AdminAccounts from './pages/A-Accounts';
import AdminPolicy from './pages/A-Policy';
import AdminUsage from './pages/A-Usage';
import SomViewerDemo from './pages/SomViewerDemo';

// 프리뷰 CSS 가 전역(.admin-sidebar 등)이라 운영자 화면을 덮어쓰므로 해당 라우트에서만 로드한다.
const PreviewLayout = lazy(() => import('./preview/components/AdminLayout'));
const PreviewUsers = lazy(() => import('./preview/pages/AdminUsers'));
const PreviewResources = lazy(() => import('./preview/pages/AdminResources'));
const PreviewAudit = lazy(() => import('./preview/pages/AdminAudit'));

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={null}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<SignUp />} />
        <Route path="/design-system" element={<DesignSystem />} />
        <Route path="/som-viewer-demo" element={<SomViewerDemo />} />
        <Route element={<PreviewLayout />}>
          <Route path="/admin-preview" element={<PreviewUsers />} />
          <Route path="/admin-preview/resources" element={<PreviewResources />} />
          <Route path="/admin-preview/audit" element={<PreviewAudit />} />
        </Route>

        <Route element={<ProtectedRoute allowedRoles={['admin', 'maintainer', 'researcher']} />}>
          <Route element={<ResearcherLayout />}>
            <Route path="/dashboard" element={<RDashboard />} />
            <Route path="/run-setting" element={<RRunSetting />} />
            <Route path="/monitor" element={<RMonitor />} />
            <Route path="/monitor/:runId" element={<RMonitorLive />} />
            <Route path="/diagnosis" element={<RDiagnosis />} />
            <Route path="/fixes" element={<RFixes />} />
            <Route path="/reports" element={<RReports />} />
            <Route path="/compare" element={<RCompare />} />
            <Route path="/history" element={<Navigate to="/compare" replace />} />
          </Route>
        </Route>

        <Route element={<ProtectedRoute allowedRoles={['admin', 'maintainer']} />}>
          <Route element={<AdminLayout />}>
            <Route path="/admin/accounts" element={<AdminAccounts />} />
            <Route path="/admin/policy" element={<AdminPolicy />} />
            <Route path="/admin/usage" element={<AdminUsage />} />
          </Route>
        </Route>

        {/* 기본 리다이렉트 */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
      </Suspense>
    </BrowserRouter>
  );
}