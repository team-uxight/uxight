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
import DesignSystem from './pages/DesignSystem';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 공개 라우트 (Public Routes) */}
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<SignUp />} />
        <Route path="/design-system" element={<DesignSystem />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<ResearcherLayout />}>
            <Route path="/dashboard" element={<RDashboard />} />
            <Route path="/run-setting" element={<RRunSetting />} />
            <Route path="/monitor" element={<RMonitor />} />
            <Route path="/monitor/:runId" element={<RMonitorLive />} />
            <Route path="/diagnosis" element={<RDiagnosis />} />
            <Route path="/fixes" element={<RFixes />} />
            <Route path="/reports" element={<RReports />} />
            <Route path="/history" element={<RReports />} />
          </Route>
        </Route>

        {/* 기본 리다이렉트 */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}