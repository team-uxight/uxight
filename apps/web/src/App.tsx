import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import SignUp from './pages/SignUp';
import ProtectedRoute from './components/ProtectedRoute';
import RDashboard from './pages/R-Dashboard';

  export default function App() {
    return (
      <BrowserRouter>
        <Routes>
          {/* 공개 라우트 (Public Routes) */}
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<SignUp />} />

          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<RDashboard />} />
          </Route>

          {/* 기본 리다이렉트 */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    );
  }