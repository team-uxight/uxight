import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import BrandLogo from './BrandLogo';
import { API_BASE_URL, apiErrorMessage, authenticatedFetch, clearAccessToken, type UserRole } from '../auth';
import '../pages/R-Dashboard.css';

type IconName = 'dashboard' | 'monitor' | 'diagnosis' | 'fixes' | 'reports' | 'history' | 'search' | 'settings' | 'bell' | 'logout' | 'menu';

const navigation: { label: string; icon: IconName; to: string }[] = [
	{ label: 'Dashboard', icon: 'dashboard', to: '/dashboard' },
	{ label: 'Monitor', icon: 'monitor', to: '/monitor' },
	{ label: 'Diagnosis', icon: 'diagnosis', to: '/diagnosis' },
	{ label: 'Fixes', icon: 'fixes', to: '/fixes' },
	{ label: 'Reports', icon: 'reports', to: '/reports' },
	{ label: 'History', icon: 'history', to: '/history' },
];

function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
	const paths: Record<IconName, string> = {
		dashboard: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
		monitor: 'M3 4h18v13H3zM8 21h8M12 17v4',
		diagnosis: 'M12 3a7 7 0 0 0-4 12.7V19h8v-3.3A7 7 0 0 0 12 3ZM9 22h6M12 7v4l2 1',
		fixes: 'M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z',
		reports: 'M6 3h12v18H6zM9 7h6M9 11h6M9 15h3M4 6v15h12',
		history: 'M3 12a9 9 0 1 0 2.6-6.4L3 8M3 3v5h5M12 7v5l3 2',
		search: 'm20 20-4.5-4.5M18 10.5a7.5 7.5 0 1 1-15 0 7.5 7.5 0 0 1 15 0Z',
		settings: 'M19.14 12.94a7.3 7.3 0 0 0 0-1.88l2.03-1.58-2-3.46-2.4.97a7.2 7.2 0 0 0-1.63-.94L14.78 3.5h-4l-.36 2.55c-.58.22-1.12.54-1.63.94l-2.4-.97-2 3.46 2.03 1.58a7.3 7.3 0 0 0 0 1.88l-2.03 1.58 2 3.46 2.4-.97c.5.4 1.05.72 1.63.94l.36 2.55h4l.36-2.55a7.2 7.2 0 0 0 1.63-.94l2.4.97 2-3.46-2.03-1.58Z',
		bell: 'M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4',
		logout: 'M10 17l5-5-5-5M15 12H3M21 4v16',
		menu: 'M4 6h16M4 12h16M4 18h16',
	};

	return (
		<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
			<path d={paths[name]} />
			{name === 'settings' && <circle cx="12.78" cy="12" r="2.5" />}
		</svg>
	);
}

export default function ResearcherLayout() {
	const navigate = useNavigate();
	const [userName, setUserName] = useState('리서처');
	const [userRole, setUserRole] = useState<UserRole | null>(null);
	const [query, setQuery] = useState('');
	const [notice, setNotice] = useState('');
	const [mobileNavOpen, setMobileNavOpen] = useState(false);

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
			<aside className={`rd-sidebar${mobileNavOpen ? ' is-open' : ''}`} aria-label="주 메뉴">
				<div className="rd-sidebar-top">
					<button className="rd-avatar" type="button" aria-label="프로필" onClick={() => setNotice('프로필 설정은 준비 중입니다.')}>
						<svg className="rd-profile-icon" viewBox="0 0 64 64" aria-hidden="true">
							<defs>
								<clipPath id="rd-profile-clip"><circle cx="32" cy="32" r="24.5" /></clipPath>
							</defs>
							<g clipPath="url(#rd-profile-clip)">
								<circle cx="32" cy="24" r="9" />
								<path d="M8 60v-7c1.5-10.3 12.2-16 24-16s22.5 5.7 24 16v7H8Z" />
							</g>
							<circle className="rd-profile-ring" cx="32" cy="32" r="27" />
						</svg>
					</button>
					<button className="rd-collapse" type="button" aria-label="메뉴 접기" onClick={() => setMobileNavOpen(false)}>
						<Icon name="menu" />
					</button>
				</div>

				<nav className="rd-nav">
					{navigation.map((item) => (
						<NavLink
							className={({ isActive }) => `rd-nav-item${isActive ? ' is-active' : ''}`}
							key={item.label}
							to={item.to}
							onClick={() => setMobileNavOpen(false)}
						>
							<Icon name={item.icon} />
							<span>{item.label}</span>
						</NavLink>
					))}
				</nav>

				<button className="rd-logout" type="button" aria-label="로그아웃" onClick={logout}>
					<Icon name="logout" size={24} />
				</button>
			</aside>

			<section className="rd-main">
				<header className="rd-topbar">
					<button className="rd-mobile-menu" type="button" aria-label="메뉴 열기" onClick={() => setMobileNavOpen(!mobileNavOpen)}>
						<Icon name="menu" />
					</button>
					<NavLink className="rd-brand" to="/dashboard" aria-label="UXight 대시보드">
						<BrandLogo variant="light-bg" size="nav" />
					</NavLink>
					<label className="rd-search">
						<Icon name="search" size={17} />
						<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search" aria-label="검색" />
						{query && <button type="button" aria-label="검색 지우기" onClick={() => setQuery('')}>×</button>}
					</label>
					<time className="rd-date" dateTime={new Date().toISOString()}>
						{new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric' }).format(new Date())}
					</time>
					<div className="rd-top-actions">
						{(userRole === 'admin' || userRole === 'maintainer') && (
							<Link className="rd-admin-link" to="/admin/accounts" onClick={() => setMobileNavOpen(false)}>
								관리자 페이지
							</Link>
						)}
						<button type="button" className="rd-icon-button" aria-label="설정" onClick={() => setNotice('설정은 준비 중입니다.')}><Icon name="settings" size={22} /></button>
						<button type="button" className="rd-icon-button" aria-label="알림" onClick={() => setNotice('새 알림이 없습니다.')}><Icon name="bell" size={22} /></button>
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
