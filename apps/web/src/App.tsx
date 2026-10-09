  import { useState } from 'react';
  import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
  import Login from './pages/Login';
  import SignUp from './pages/SignUp';
  import GoogleCallback from './pages/GoogleCallback';
  import ProtectedRoute from './components/ProtectedRoute';

  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8080';

  type Health = { status: string; service: string };
  type RunCreated = { id: number; status: string };

  // 기존 작성하신 Walking Skeleton 메인 대시보드 화면
  function Dashboard() {
    const navigate = useNavigate();
    const [health, setHealth] = useState<string>('—');
    const [run, setRun] = useState<string>('—');

    async function checkHealth() {
      try {
        const res = await fetch(`${API_BASE_URL}/api/health`, {
          credentials: 'include',
        });
        const body = (await res.json()) as Health;
        setHealth(`${body.service}: ${body.status}`);
      } catch (e) {
        setHealth(`error: ${(e as Error).message}`);
      }
    }

    async function createRun() {
      try {
        const res = await fetch(`${API_BASE_URL}/api/runs`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ targetUrl: 'https://www.gachon.ac.kr', task: '장학금 신청 방법 찾기' }),
        });
        const body = (await res.json()) as RunCreated;
        setRun(`run #${body.id} → ${body.status}`);
      } catch (e) {
        setRun(`error: ${(e as Error).message}`);
      }
    }

    const handleLogout = async () => {
      try {
        await fetch(`${API_BASE_URL}/api/auth/logout`, {
          method: 'POST',
          credentials: 'include',
        });
      } catch {
        // Clear local state even if the API is unreachable.
      } finally {
        localStorage.removeItem('userRole');
        navigate('/login');
      }
    };

    return (
      <main className="p-8">
        <div className="flex items-center justify-between">
          <h1>UXight Dashboard</h1>
          <button onClick={handleLogout} className="rounded bg-red-500 px-3 py-1 text-sm text-white">
            로그아웃
          </button>
        </div>
        <p>walking skeleton — web → api → agent → mysql → web</p>
        <section className="mt-4">
          <button onClick={checkHealth}>GET /api/health</button> <code>{health}</code>
        </section>
        <section className="mt-2">
          <button onClick={createRun}>POST /api/runs</button> <code>{run}</code>
        </section>
      </main>
    );
  }

  export default function App() {
    return (
      <BrowserRouter>
        <Routes>
          {/* 공개 라우트 (Public Routes) */}
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<SignUp />} />
          <Route path="/auth/google/callback" element={<GoogleCallback />} />

          {/* 보호된 라우트 (Protected Routes) */}
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<Dashboard />} />
          </Route>

          {/* 기본 리다이렉트 */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    );
  }