import { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { getCurrentUserRole, getRoleHomePath, type UserRole } from '../auth';

interface ProtectedRouteProps {
  allowedRoles?: UserRole[];
}

export default function ProtectedRoute({ allowedRoles }: ProtectedRouteProps) {
  const [authStatus, setAuthStatus] = useState<'checking' | 'authenticated' | 'unauthenticated'>('checking');
  const [userRole, setUserRole] = useState<UserRole | null>(null);

  useEffect(() => {
    let active = true;

    getCurrentUserRole()
      .then((role) => {
        if (active) {
          setUserRole(role);
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

  if (allowedRoles && (!userRole || !allowedRoles.includes(userRole))) {
    return <Navigate to={userRole ? getRoleHomePath(userRole) : '/login'} replace />;
  }

  return <Outlet />;
}