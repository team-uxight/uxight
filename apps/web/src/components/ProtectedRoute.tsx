import { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { API_BASE_URL, authenticatedFetch } from '../auth';

type UserMe = { role: string };

interface ProtectedRouteProps {
  allowedRoles?: string[];
}

export default function ProtectedRoute({ allowedRoles }: ProtectedRouteProps) {
  const [authStatus, setAuthStatus] = useState<'checking' | 'authenticated' | 'unauthenticated'>('checking');
  const [userRole, setUserRole] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    authenticatedFetch(`${API_BASE_URL}/api/users/me`)
      .then(async (res) => {
        if (!res.ok) {
          throw new Error('Session is not authenticated');
        }

        const user = (await res.json()) as UserMe;
        if (active) {
          setUserRole(user.role);
          setAuthStatus('authenticated');
        }
      })
      .catch(() => {
        if (active) {
          localStorage.removeItem('userRole');
          setAuthStatus('unauthenticated');
        }
      });

    return () => {
      active = false;
    };
  }, []);

  if (authStatus === 'checking') {
    return <div className="flex min-h-screen items-center justify-center">Checking your session...</div>;
  }

  if (authStatus === 'unauthenticated') {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && userRole && !allowedRoles.includes(userRole)) {
    // 권한이 없으면 메인 대시보드로 이동
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}