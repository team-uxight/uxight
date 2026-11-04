import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Bell, CalendarDays, LogOut } from 'lucide-react';
import BrandLogo from './BrandLogo';
import { API_BASE_URL, apiErrorMessage, authenticatedFetch, clearAccessToken, type UserRole } from '../auth';
import '../pages/R-Dashboard.css';

type IconName = 'dashboard' | 'monitor' | 'diagnosis' | 'fixes' | 'reports' | 'compare' | 'search';

const navigation: { label: string; icon: IconName; to: string }[] = [
	{ label: 'Dashboard', icon: 'dashboard', to: '/dashboard' },
	{ label: 'Monitor', icon: 'monitor', to: '/monitor' },
	{ label: 'Diagnosis', icon: 'diagnosis', to: '/diagnosis' },
	{ label: 'Fixes', icon: 'fixes', to: '/fixes' },
	{ label: 'Reports', icon: 'reports', to: '/reports' },
	{ label: 'Compare', icon: 'compare', to: '/compare' },
];

function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
	const paths: Record<IconName, string> = {
		dashboard: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
		monitor: 'M3 4h18v13H3zM8 21h8M12 17v4',
		diagnosis: 'M12 3a7 7 0 0 0-4 12.7V19h8v-3.3A7 7 0 0 0 12 3ZM9 22h6M12 7v4l2 1',
		fixes: 'M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z',
		reports: 'M6 3h12v18H6zM9 7h6M9 11h6M9 15h3M4 6v15h12',
		compare: 'M8 5H5a2 2 0 0 0-2 2v3m0 4v3a2 2 0 0 0 2 2h3m8-14h3a2 2 0 0 1 2 2v3m0 4v3a2 2 0 0 1-2 2h-3M8 12h8m-4-4v8',
		search: 'm20 20-4.5-4.5M18 10.5a7.5 7.5 0 1 1-15 0 7.5 7.5 0 0 1 15 0Z',
	};

	return (
		<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
			<path d={paths[name]} />
		</svg>
	);
}

export default function ResearcherLayout() {
	const navigate = useNavigate();
	const [userName, setUserName] = useState('리서처');
	const [userRole, setUserRole] = useState<UserRole | null>(null);
	const [query, setQuery] = useState('');
	const [notice, setNotice] = useState('');

	useEffect(() => {
		let active = true;

		authenticatedFetch(`${API_BASE_URL}/api/users/me`)
			.then(async (response) => {
				if (!response.ok) {
					if (active) setNotice(await apiErrorMessage(response, '사용자 정보를 불러오지 못했습니다.'));
					return;
				}
				const user: unknown = await response.json();
				if (typeof user !== 'object' || user === null) {
					throw new Error('서버에서 올바르지 않은 사용자 정보를 받았습니다.');
				}
				if ('name' in user && typeof user.name === 'string' && active) setUserName(user.name);
				if (
					'role' in user &&
					(user.role === 'admin' || user.role === 'maintainer' || user.role === 'researcher') &&
					active
				) {
					setUserRole(user.role);
				}
			})
			.catch((error: unknown) => {
				if (active) setNotice(error instanceof Error ? error.message : '사용자 정보를 불러오지 못했습니다.');
			});

		return () => {
			active = false;
		};
	}, []);

	const logout = async () => {
		try {
			const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
				method: 'POST',
				credentials: 'include',
			});
			if (!response.ok) {
				setNotice(await apiErrorMessage(response, '로그아웃에 실패했습니다. 다시 시도해 주세요.'));
				return;
			}

			clearAccessToken();
			localStorage.removeItem('userRole');
			navigate('/login', { replace: true });
		} catch (error: unknown) {
			setNotice(error instanceof Error ? error.message : '로그아웃 중 오류가 발생했습니다.');
		}
	};

	return (
		<main className="rd-shell">
			<aside className="rd-sidebar" aria-label="주 메뉴">
				<NavLink className="rd-brand" to="/dashboard" aria-label="UXight 리서처 대시보드">
					<BrandLogo variant="light-bg" size="nav" />
				</NavLink>

				<nav className="rd-nav">
					{navigation.map((item) => (
						<NavLink
							className={({ isActive }) => `rd-nav-item${isActive ? ' is-active' : ''}`}
							key={item.label}
							to={item.to}
						>
							<Icon name={item.icon} />
							<span>{item.label}</span>
						</NavLink>
					))}
				</nav>

				<div className="rd-sidebar-bottom">
					<button className="rd-utility-link" type="button" onClick={() => setNotice('새 알림이 없습니다.')}>
						<Bell size={18} aria-hidden="true" />
						<span>알림</span>
					</button>
					<button className="rd-utility-link" type="button" onClick={logout}>
						<LogOut size={18} aria-hidden="true" />
						<span>로그아웃</span>
					</button>
				</div>
			</aside>

			<section className="rd-main">
				<header className="rd-topbar">
					<label className="rd-search">
						<Icon name="search" size={16} />
						<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search" aria-label="검색" />
						{query && <button type="button" aria-label="검색 지우기" onClick={() => setQuery('')}>×</button>}
					</label>
					<time className="rd-date" dateTime={new Date().toISOString()}>
						<CalendarDays size={15} aria-hidden="true" />
						{new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric' }).format(new Date())}
					</time>
					<div className="rd-top-actions">
						{(userRole === 'admin' || userRole === 'maintainer') && (
							<Link className="rd-admin-link" to="/admin/accounts">
								관리자 페이지
							</Link>
						)}
						<div className="rd-user-profile" aria-label={`${userName} · ${userRole ?? '권한 확인 중'}`}>
							<svg className="rd-user-avatar" viewBox="0 0 40 40" role="img" aria-label="기본 프로필">
								<circle className="rd-user-avatar-ring" cx="20" cy="20" r="17" />
								<circle className="rd-user-avatar-head" cx="20" cy="15" r="6" />
								<path className="rd-user-avatar-body" d="M9 33c.8-6.2 4.8-9.4 11-9.4s10.2 3.2 11 9.4" />
							</svg>
							<span className="rd-user-name">{userName}</span>
							<span className="rd-role-chip">
								{userRole === 'researcher' ? 'Researcher' : userRole === 'admin' ? 'Admin' : userRole === 'maintainer' ? 'Maintainer' : '권한 확인 중'}
							</span>
						</div>
					</div>
				</header>

				<div className="rd-content">
					{notice && (
						<div className="rd-notice" role="status">
							<span>{notice}</span>
							<button type="button" aria-label="알림 닫기" onClick={() => setNotice('')}>×</button>
						</div>
					)}
					<Outlet context={{ userName, query }} />
				</div>
			</section>
		</main>
	);
}
