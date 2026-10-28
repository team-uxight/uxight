import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Bell, CalendarDays, LogOut, Monitor, Search, Settings2, UsersRound } from 'lucide-react';
import BrandLogo from './BrandLogo';
import { API_BASE_URL, apiErrorMessage, clearAccessToken, getCurrentUser, type CurrentUser } from '../auth';
import './Admin.css';

const navigation = [
	{ label: '계정·권한', to: '/admin/accounts', icon: UsersRound },
	{ label: '정책·자원', to: '/admin/policy', icon: Settings2 },
	{ label: '사용량·감사', to: '/admin/usage', icon: Monitor },
];

export default function AdminLayout() {
	const navigate = useNavigate();
	const [notice, setNotice] = useState('');
	const [user, setUser] = useState<CurrentUser | null>(null);
	const [accountSearch, setAccountSearch] = useState('');

	useEffect(() => {
		let active = true;
		getCurrentUser()
			.then((currentUser) => {
				if (active) setUser(currentUser);
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
			navigate('/login', { replace: true });
		} catch (error: unknown) {
			setNotice(error instanceof Error ? error.message : '로그아웃 중 오류가 발생했습니다.');
		}
	};

	return (
		<div className="admin-shell">
			<aside className="admin-sidebar" aria-label="운영자 메뉴">
				<NavLink className="admin-brand" to="/admin/accounts" aria-label="UXight 운영자 대시보드">
					<BrandLogo variant="light-bg" size="nav" />
				</NavLink>

				<nav className="admin-nav">
					{navigation.map(({ label, to, icon: Icon }) => (
						<NavLink
							className={({ isActive }) => `admin-nav-item${isActive ? ' is-active' : ''}`}
							key={to}
							to={to}
						>
							<Icon size={18} aria-hidden="true" />
							<span>{label}</span>
						</NavLink>
					))}
				</nav>

				<div className="admin-sidebar-bottom">
					<button className="admin-utility-link" type="button" disabled>
						<Bell size={18} aria-hidden="true" />
						<span>알림</span>
					</button>
					<button className="admin-utility-link" type="button" onClick={logout}>
						<LogOut size={18} aria-hidden="true" />
						<span>로그아웃</span>
					</button>
				</div>
			</aside>

			<main className="admin-main">
				<header className="admin-topbar">
					<label className="admin-workspace-search">
						<Search size={16} aria-hidden="true" />
						<input
							value={accountSearch}
							onChange={(event) => setAccountSearch(event.target.value)}
							placeholder="계정 이름 또는 이메일 검색"
							aria-label="계정 이름 또는 이메일 검색"
						/>
					</label>
					<div className="admin-topbar-date"><CalendarDays size={15} aria-hidden="true" />{new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric' }).format(new Date())}</div>
					<div className="admin-user-profile" aria-label={`${user?.name ?? '사용자'} · ${user?.role ?? '권한 확인 중'}`}>
						<Link className="admin-researcher-link" to="/dashboard">리서처 페이지</Link>
						<svg className="admin-user-avatar" viewBox="0 0 40 40" role="img" aria-label="기본 프로필">
							<circle className="admin-user-avatar-ring" cx="20" cy="20" r="17" />
							<circle className="admin-user-avatar-head" cx="20" cy="15" r="6" />
							<path className="admin-user-avatar-body" d="M9 33c.8-6.2 4.8-9.4 11-9.4s10.2 3.2 11 9.4" />
						</svg>
						<span className="admin-user-name">{user?.name ?? '불러오는 중'}</span>
						<span className="admin-role-chip">{user?.role === 'maintainer' ? 'Maintainer' : user?.role === 'admin' ? 'Admin' : '권한 확인 중'}</span>
					</div>
				</header>
				{notice && (
					<div className="admin-notice" role="alert">
						<span>{notice}</span>
						<button type="button" aria-label="알림 닫기" onClick={() => setNotice('')}>×</button>
					</div>
				)}
				<Outlet context={{ accountSearch, setAccountSearch }} />
			</main>
		</div>
	);
}
