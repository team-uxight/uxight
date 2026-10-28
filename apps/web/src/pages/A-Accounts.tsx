import { useEffect, useMemo, useState } from 'react';
import { RefreshCw, Search, UserRoundCog, X } from 'lucide-react';
import { useOutletContext } from 'react-router-dom';
import { changeUserActive, changeUserRole, getAdminUsers, getCurrentUserRole, type AdminUser, type UserRole } from '../auth';

const pageSize = 20;

const roleLabels: Record<UserRole, string> = {
	admin: 'Admin',
	maintainer: 'Maintainer',
	researcher: 'Researcher',
};

type AccountFilter = 'all' | UserRole;
type StatusFilter = 'all' | 'active' | 'inactive';
type AdminLayoutContext = {
	accountSearch: string;
	setAccountSearch: (value: string) => void;
};

export default function AdminAccounts() {
	const { accountSearch, setAccountSearch } = useOutletContext<AdminLayoutContext>();
	const [accounts, setAccounts] = useState<AdminUser[]>([]);
	const [actorRole, setActorRole] = useState<UserRole>('admin');
	const [selectedAccount, setSelectedAccount] = useState<AdminUser | null>(null);
	const [selectedRole, setSelectedRole] = useState<UserRole>('researcher');
	const [page, setPage] = useState(0);
	const [totalElements, setTotalElements] = useState(0);
	const [totalPages, setTotalPages] = useState(0);
	const [loadedPage, setLoadedPage] = useState<number | null>(null);
	const [reloadKey, setReloadKey] = useState(0);
	const [busy, setBusy] = useState(false);
	const [roleFilter, setRoleFilter] = useState<AccountFilter>('all');
	const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
	const [error, setError] = useState('');
	const [notice, setNotice] = useState('');
	const loading = loadedPage !== page;

	useEffect(() => {
		let active = true;

		const loadAccounts = async () => {
			try {
				const role = await getCurrentUserRole();
				const result = await getAdminUsers(page, pageSize);
				if (!active) return;
				setActorRole(role);
				setAccounts(result.content);
				setTotalElements(result.totalElements);
				setTotalPages(result.totalPages);
			} catch (cause: unknown) {
				if (active) setError(cause instanceof Error ? cause.message : '계정 정보를 불러오지 못했습니다.');
			} finally {
				if (active) setLoadedPage(page);
			}
		};
		void loadAccounts();

		return () => {
			active = false;
		};
	}, [page, reloadKey]);

	const visibleAccounts = useMemo(() => {
		const query = accountSearch.trim().toLocaleLowerCase('ko-KR');
		return accounts.filter((account) => {
			const matchesSearch = !query ||
				account.name.toLocaleLowerCase('ko-KR').includes(query) ||
				account.email.toLocaleLowerCase('ko-KR').includes(query);
			const matchesRole = roleFilter === 'all' || account.role === roleFilter;
			const matchesStatus = statusFilter === 'all' || (statusFilter === 'active' ? account.isActive : !account.isActive);
			return matchesSearch && matchesRole && matchesStatus;
		});
	}, [accountSearch, accounts, roleFilter, statusFilter]);

	const refresh = () => {
		setError('');
		setNotice('');
		setLoadedPage(null);
		setReloadKey((current) => current + 1);
	};

	const openAccount = (account: AdminUser) => {
		setSelectedAccount(account);
		setSelectedRole(account.role);
		setError('');
		setNotice('');
	};

	const saveRole = async () => {
		if (!selectedAccount || selectedRole === selectedAccount.role) return;

		setBusy(true);
		setError('');
		setNotice('');
		try {
			const role = await changeUserRole(selectedAccount.userId, selectedRole);
			const updatedAccount = { ...selectedAccount, role };
			setAccounts((current) => current.map((item) => item.userId === updatedAccount.userId ? updatedAccount : item));
			setSelectedAccount(updatedAccount);
			setNotice(`${selectedAccount.name} 계정 역할을 ${roleLabels[role]}(으)로 변경했습니다.`);
		} catch (cause: unknown) {
			setError(cause instanceof Error ? cause.message : '계정 역할을 변경하지 못했습니다.');
		} finally {
			setBusy(false);
		}
	};

	const toggleActive = async () => {
		if (!selectedAccount) return;
		const nextActive = !selectedAccount.isActive;
		const action = nextActive ? '활성화' : '비활성화';

		setBusy(true);
		setError('');
		setNotice('');
		try {
			const isActive = await changeUserActive(selectedAccount.userId, nextActive);
			const updatedAccount = { ...selectedAccount, isActive };
			setAccounts((current) => current.map((item) => item.userId === updatedAccount.userId ? updatedAccount : item));
			setSelectedAccount(updatedAccount);
			setNotice(`${selectedAccount.name} 계정을 ${action}했습니다.`);
		} catch (cause: unknown) {
			setError(cause instanceof Error ? cause.message : `계정을 ${action}하지 못했습니다.`);
		} finally {
			setBusy(false);
		}
	};

	const activeCount = accounts.filter((account) => account.isActive).length;
	const inactiveCount = accounts.length - activeCount;
	const operatorCount = accounts.filter((account) => account.role === 'admin' || account.role === 'maintainer').length;
	const roleOptions: UserRole[] = actorRole === 'admin' ? ['admin', 'maintainer', 'researcher'] : ['researcher'];
	const canManageSelected = selectedAccount !== null &&
		(actorRole === 'admin' || selectedAccount.role === 'researcher');
	const canToggleSelected = selectedAccount?.role === 'researcher';

	return (
		<section className="admin-page" aria-labelledby="admin-accounts-title">
			<header className="admin-page-header">
				<div>
					<p className="admin-eyebrow">A1 · 계정·권한</p>
					<h1 id="admin-accounts-title">계정·권한</h1>
					<p>리서처 계정 관리 / 가입 계정</p>
				</div>
				<div className="admin-page-actions">
					<button className="admin-button admin-button--secondary admin-button--accounts-refresh" type="button" onClick={refresh} disabled={loading}>
						<RefreshCw size={14} aria-hidden="true" /> 새로고침
					</button>
				</div>
			</header>

			{error && <p className="admin-inline-feedback is-error" role="alert">{error}</p>}
			{notice && <p className="admin-inline-feedback" role="status">{notice}</p>}

			<div className="admin-stat-grid admin-stat-grid--accounts">
				<article className="admin-stat-card admin-stat-card--purple">
					<span>전체 사용자</span><strong>{totalElements}</strong><small>등록된 모든 계정</small>
				</article>
				<article className="admin-stat-card admin-stat-card--green">
					<span>활성 계정</span><strong>{activeCount}</strong><small>로그인 가능한 계정</small>
				</article>
				<article className="admin-stat-card admin-stat-card--violet">
					<span>운영자 계정</span><strong>{operatorCount}</strong><small>Admin + Maintainer</small>
				</article>
				<article className="admin-stat-card admin-stat-card--rose">
					<span>비활성 계정</span><strong>{inactiveCount}</strong><small>접근이 제한된 계정</small>
				</article>
			</div>

			<section className="admin-panel admin-accounts-panel">
				<div className="admin-panel-heading">
					<div>
						<h2>사용자 목록</h2>
						<p>계정 정보와 역할 및 접근 상태를 확인하거나 변경할 수 있습니다.</p>
					</div>
					<span className="admin-count-chip">{loading ? '불러오는 중…' : `${totalElements} accounts`}</span>
				</div>
				<div className="admin-account-filters">
					<label className="admin-search-field">
						<Search size={15} aria-hidden="true" />
						<input value={accountSearch} onChange={(event) => setAccountSearch(event.target.value)} placeholder="이름 또는 이메일 검색" aria-label="이름 또는 이메일 검색" />
					</label>
					<label>
						<span className="sr-only">역할 필터</span>
						<select value={roleFilter} onChange={(event) => {
							const value = event.target.value;
							if (value === 'all' || value === 'admin' || value === 'maintainer' || value === 'researcher') setRoleFilter(value);
						}}>
							<option value="all">모든 역할</option>
							<option value="admin">Admin</option>
							<option value="maintainer">Maintainer</option>
							<option value="researcher">Researcher</option>
						</select>
					</label>
					<label>
						<span className="sr-only">상태 필터</span>
						<select value={statusFilter} onChange={(event) => {
							if (event.target.value === 'all' || event.target.value === 'active' || event.target.value === 'inactive') setStatusFilter(event.target.value);
						}}>
							<option value="all">모든 상태</option>
							<option value="active">활성</option>
							<option value="inactive">비활성</option>
						</select>
					</label>
					<button className="admin-button admin-button--text" type="button" onClick={() => { setAccountSearch(''); setRoleFilter('all'); setStatusFilter('all'); }}>
						필터 초기화
					</button>
				</div>
				<div className="admin-table-wrap">
					<table className="admin-table">
						<thead>
							<tr><th>이메일</th><th>역할</th><th>상태</th><th>가입 경로</th><th>마지막 로그인</th><th>누적 비용</th><th>관리</th></tr>
						</thead>
						<tbody>
							{loading && <tr><td colSpan={7} className="admin-table-message">계정 목록을 불러오는 중입니다.</td></tr>}
							{!loading && visibleAccounts.length === 0 && <tr><td colSpan={7} className="admin-table-message">조건에 맞는 계정이 없습니다.</td></tr>}
							{!loading && visibleAccounts.map((account) => (
								<tr key={account.userId}>
									<td>{account.email}</td>
									<td><span className={`admin-role-badge admin-role-badge--${account.role}`}>{roleLabels[account.role]}</span></td>
									<td><span className={`admin-status${account.isActive ? ' is-active' : ' is-inactive'}`}>{account.isActive ? '활성' : '비활성'}</span></td>
									<td>{account.authProvider === 'google' ? 'Google' : '이메일'}</td>
									<td title="계정 API에서 제공되지 않는 정보">—</td>
									<td title="계정 API에서 제공되지 않는 정보">—</td>
									<td>
										<button className="admin-icon-button" type="button" aria-label={`${account.name} 계정 관리`} onClick={() => openAccount(account)}>
											<UserRoundCog size={16} aria-hidden="true" />
										</button>
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
				<div className="admin-pagination">
					<span>{totalElements === 0 ? '0개 계정' : `${page * pageSize + 1}–${Math.min((page + 1) * pageSize, totalElements)} / ${totalElements}`}</span>
					<div>
						<button className="admin-button admin-button--secondary" type="button" disabled={page === 0 || loading} onClick={() => setPage((current) => current - 1)}>이전</button>
						<span>{totalPages === 0 ? '0 / 0' : `${page + 1} / ${totalPages}`}</span>
						<button className="admin-button admin-button--secondary" type="button" disabled={page + 1 >= totalPages || loading} onClick={() => setPage((current) => current + 1)}>다음</button>
					</div>
				</div>
			</section>

			{selectedAccount && (
				<div className="admin-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) setSelectedAccount(null); }}>
					<section className="admin-account-modal" role="dialog" aria-modal="true" aria-labelledby="account-modal-title">
						<header>
							<span className="admin-modal-icon"><UserRoundCog size={18} aria-hidden="true" /></span>
							<button className="admin-icon-button" type="button" aria-label="계정 관리 닫기" disabled={busy} onClick={() => setSelectedAccount(null)}><X size={17} aria-hidden="true" /></button>
						</header>
						<h2 id="account-modal-title">{selectedAccount.name} 계정 관리</h2>
						<p>{selectedAccount.email} · 계정의 역할과 접근 상태를 변경할 수 있습니다.</p>
						<dl className="admin-account-summary">
							<div><dt>현재 역할</dt><dd>{roleLabels[selectedAccount.role]}</dd></div>
							<div><dt>현재 상태</dt><dd>{selectedAccount.isActive ? '활성' : '비활성'}</dd></div>
						</dl>
						<label className="admin-modal-role">
							변경할 역할
							<select value={selectedRole} disabled={!canManageSelected || busy} onChange={(event) => {
								const role = roleOptions.find((option) => option === event.target.value);
								if (role) setSelectedRole(role);
							}}>
								{(canManageSelected ? roleOptions : [selectedAccount.role]).map((role) => <option key={role} value={role}>{roleLabels[role]}</option>)}
							</select>
						</label>
						{error && <p className="admin-inline-feedback is-error" role="alert">{error}</p>}
						<footer>
							<button className="admin-button admin-button--secondary" type="button" disabled={busy} onClick={() => setSelectedAccount(null)}>취소</button>
							{canToggleSelected && (
								<button className="admin-button admin-button--danger-soft" type="button" disabled={busy} onClick={() => void toggleActive()}>
									{selectedAccount.isActive ? '비활성화' : '활성화'}
								</button>
							)}
							<button className="admin-button admin-button--primary" type="button" disabled={!canManageSelected || busy || selectedRole === selectedAccount.role} onClick={() => void saveRole()}>
								{busy ? '저장 중…' : '역할 변경'}
							</button>
						</footer>
					</section>
				</div>
			)}
		</section>
	);
}
