import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import BrandLogo from '../components/BrandLogo';
import { API_BASE_URL, apiErrorMessage, authenticatedFetch, clearAccessToken } from '../auth';
import './R-Dashboard.css';

type IconName = 'dashboard' | 'monitor' | 'diagnosis' | 'fixes' | 'reports' | 'history' | 'search' | 'settings' | 'bell' | 'arrow' | 'clock' | 'plus' | 'user' | 'logout' | 'menu';

type Project = {
	id: string;
	initial: string;
	name: string;
	url: string;
	description: string;
	lastRun: string;
	frictions: number;
	personas: string;
};

const exampleProjects: Project[] = [
	{
		id: 'gachon-portal',
		initial: '가',
		name: '가천대 포털',
		url: 'https://www.gachon.ac.kr/',
		description: '가천대학교 대표 홈페이지 및 학생 포털 UX 리서치',
		lastRun: '2026-09-21 14:30',
		frictions: 4,
		personas: '5명 (Nov 3 / Exp 2)',
	},
	{
		id: 'course-registration',
		initial: '수',
		name: '수강신청 시스템(사본)',
		url: 'https://www.gachon.ac.kr/',
		description: '2026학년도 수강신청 시뮬레이션 및 장애 개선',
		lastRun: '2026-09-21 14:30',
		frictions: 4,
		personas: '5명 (Nov 3 / Exp 2)',
	},
];

const navigation: { label: string; icon: IconName }[] = [
	{ label: 'Dashboard', icon: 'dashboard' },
	{ label: 'Monitor', icon: 'monitor' },
	{ label: 'Diagnosis', icon: 'diagnosis' },
	{ label: 'Fixes', icon: 'fixes' },
	{ label: 'Reports', icon: 'reports' },
	{ label: 'History', icon: 'history' },
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
		arrow: 'M7 17 17 7M7 7h10v10',
		clock: 'M12 8v4l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
		plus: 'M12 5v14M5 12h14',
		user: 'M20 21a8 8 0 0 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z',
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

export default function RDashboard() {
	const navigate = useNavigate();
	const [userName, setUserName] = useState('리서처');
	const [query, setQuery] = useState('');
	const [notice, setNotice] = useState('');
	const [createOpen, setCreateOpen] = useState(false);
	const [mobileNavOpen, setMobileNavOpen] = useState(false);
	const [projects, setProjects] = useState(exampleProjects);

	useEffect(() => {
		let active = true;

		authenticatedFetch(`${API_BASE_URL}/api/users/me`)
			.then(async (response) => {
				if (!response.ok) {
					if (active) setNotice(await apiErrorMessage(response, '사용자 정보를 불러오지 못했습니다.'));
					return;
				}
				const user = (await response.json()) as { name?: string };
				if (active && user.name) setUserName(user.name);
			})
			.catch((error: unknown) => {
				if (active) setNotice(error instanceof Error ? error.message : '사용자 정보를 불러오지 못했습니다.');
			});

		return () => {
			active = false;
		};
	}, []);

	const filteredProjects = projects.filter((project) =>
		`${project.name} ${project.url} ${project.description}`.toLowerCase().includes(query.toLowerCase()),
	);

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

	const createProject = (event: React.FormEvent<HTMLFormElement>) => {
		event.preventDefault();
		const formData = new FormData(event.currentTarget);
		const name = String(formData.get('name') ?? '').trim();
		const url = String(formData.get('url') ?? '').trim();
		if (!name || !url) return;

		setProjects((current) => [{
			id: `draft-${Date.now()}`,
			initial: name.slice(0, 1),
			name,
			url,
			description: '새 프로젝트',
			lastRun: '실험 기록 없음',
			frictions: 0,
			personas: '미설정',
		}, ...current]);
		setCreateOpen(false);
		setNotice('프로젝트를 이 화면에 추가했습니다. 서버 저장 API는 아직 연결되지 않았습니다.');
	};

	const announceUnavailable = (label: string) => {
		setNotice(`${label} 화면은 준비 중입니다.`);
		setMobileNavOpen(false);
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
					{navigation.map((item, index) => (
						<button
							className={`rd-nav-item${index === 0 ? ' is-active' : ''}`}
							key={item.label}
							type="button"
							aria-current={index === 0 ? 'page' : undefined}
							onClick={() => index === 0 ? setMobileNavOpen(false) : announceUnavailable(item.label)}
						>
							<Icon name={item.icon} />
							<span>{item.label}</span>
						</button>
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
					<a className="rd-brand" href="/dashboard" aria-label="UXight 대시보드">
						<BrandLogo variant="light-bg" size="nav" />
					</a>
					<label className="rd-search">
						<Icon name="search" size={17} />
						<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search" aria-label="프로젝트 검색" />
						{query && <button type="button" aria-label="검색 지우기" onClick={() => setQuery('')}>×</button>}
					</label>
					<time className="rd-date" dateTime={new Date().toISOString()}>
						{new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric' }).format(new Date())}
					</time>
					<div className="rd-top-actions">
						<button type="button" className="rd-icon-button" aria-label="설정" onClick={() => setNotice('설정은 준비 중입니다.')}><Icon name="settings" size={22} /></button>
						<button type="button" className="rd-icon-button" aria-label="알림" onClick={() => setNotice('새 알림이 없습니다.')}><Icon name="bell" size={22} /></button>
					</div>
				</header>

				<div className="rd-content">
					<div className="rd-welcome-row">
						<h1>안녕하세요, {userName}님<span aria-hidden="true"> 👋</span></h1>
						<button type="button" className="rd-create-button" onClick={() => setCreateOpen(true)}>
							<Icon name="plus" size={18} /> 새 프로젝트 생성
						</button>
					</div>

					{notice && (
						<div className="rd-notice" role="status">
							<span>{notice}</span>
							<button type="button" aria-label="알림 닫기" onClick={() => setNotice('')}>×</button>
						</div>
					)}

					<div className="rd-section-heading">
						<div>
							<h2>내 프로젝트</h2>
							<span className="rd-demo-label">시안 예시 데이터</span>
						</div>
						<span className="rd-project-count">{filteredProjects.length}개</span>
					</div>

					{filteredProjects.length > 0 ? (
						<div className="rd-project-grid">
							{filteredProjects.map((project) => (
								<article className="rd-project-card" key={project.id}>
									<div className="rd-project-card-top">
										<span className="rd-project-avatar">{project.initial}</span>
										<div className="rd-project-title">
											<h3>{project.name}</h3>
											<a href={project.url} target="_blank" rel="noreferrer">{project.url.replace(/^https?:\/\//, '')}</a>
										</div>
										<button type="button" className="rd-open-project" aria-label={`${project.name} 열기`} onClick={() => setNotice('프로젝트 상세 화면은 준비 중입니다.')}>
											<Icon name="arrow" size={18} />
										</button>
									</div>
									<p className="rd-project-description">{project.description}</p>
									<div className="rd-project-stats">
										<div><span>마지막 실험</span><strong>{project.lastRun}</strong></div>
										<div><span>Friction 수</span><strong>{project.frictions}건</strong></div>
										<div><span>Persona</span><strong>{project.personas}</strong></div>
									</div>
									<footer className="rd-project-footer">
										<button type="button" onClick={() => setNotice(`${project.name}의 실험 기록은 준비 중입니다.`)}><Icon name="clock" size={14} /> History</button>
										<button type="button" className="rd-config-button" onClick={() => setNotice(`${project.name}의 실험 설정은 준비 중입니다.`)}><Icon name="settings" size={15} /> 실험 설정</button>
									</footer>
								</article>
							))}
						</div>
					) : (
						<div className="rd-empty-state">
							<Icon name="search" size={26} />
							<p>검색 결과가 없습니다.</p>
							<button type="button" onClick={() => setQuery('')}>검색 지우기</button>
						</div>
					)}
				</div>
			</section>

			{createOpen && (
				<div className="rd-modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setCreateOpen(false)}>
					<section className="rd-modal" role="dialog" aria-modal="true" aria-labelledby="create-project-title">
						<button className="rd-modal-close" type="button" aria-label="닫기" onClick={() => setCreateOpen(false)}>×</button>
						<h2 id="create-project-title">새 프로젝트 생성</h2>
						<p>프로젝트 정보를 입력하세요.</p>
						<form onSubmit={createProject}>
							<label>프로젝트 이름<input name="name" required maxLength={80} placeholder="예: 가천대 포털" /></label>
							<label>대상 URL<input name="url" type="url" required placeholder="https://example.com" /></label>
							<div className="rd-modal-actions">
								<button type="button" className="rd-cancel-button" onClick={() => setCreateOpen(false)}>취소</button>
								<button type="submit" className="rd-create-button">프로젝트 추가</button>
							</div>
						</form>
					</section>
				</div>
			)}
		</main>
	);
}
