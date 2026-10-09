import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

export default function GoogleCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const token = searchParams.get('token');
    const role = searchParams.get('role') || 'researcher';

    if (token) {
      localStorage.setItem('accessToken', token);
      localStorage.setItem('userRole', role);
      // 로그인 완료 후 ProtectedRoute 안의 Dashboard로 이동
      navigate('/dashboard', { replace: true });
    } else {
      alert('Google 로그인 처리 실패');
      navigate('/login', { replace: true });
    }
  }, [searchParams, navigate]);

  return (
    <div className="flex h-screen items-center justify-center bg-[#1B1841] text-white">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#35D4C8] border-t-transparent" />
        <p className="text-sm text-gray-300">Google 로그인 중...</p>
      </div>
    </div>
  );
}