import { useEffect, useMemo, useState } from 'react';
import { CircleAlert } from 'lucide-react';
import { getAdminExperiments, getAuditLogs, getMonthlyUsage, type AdminExperiment, type AuditLog, type MonthlyUsage } from '../auth';

type RunStatusFilter = 'all' | AdminExperiment['status'];

function monthOptions(count = 6): string[] {
	const now = new Date();
	return Array.from({ length: count }, (_, index) => {
		const date = new Date(now.getFullYear(), now.getMonth() - index, 1);
		return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
	});
}

function monthRange(month: string): { from: string; to: string } {
	const [year, monthIndex] = month.split('-').map(Number);
	const next = new Date(year, monthIndex, 1);
	const nextMonth = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}`;
	return { from: `${month}-01T00:00:00+09:00`, to: `${nextMonth}-01T00:00:00+09:00` };
}

const KRW_PER_USD = 1400;
const formatKrw = (usd: number) => `₩ ${Math.round(usd * KRW_PER_USD).toLocaleString('ko-KR')}`;
const formatTime = (ts: string) => ts.replace('T', ' ').slice(0, 16);
const runStatusLabels: Record<AdminExperiment['status'], string> = {
	queued: '대기',
	accepted: '접수',
	running: '실행 중',
	done: '완료',
	failed: '오류',
	cancelled: '취소',
};
const runStatuses: AdminExperiment['status'][] = ['queued', 'accepted', 'running', 'done', 'failed', 'cancelled'];

function isRunStatus(value: string): value is AdminExperiment['status'] {
	return runStatuses.some((status) => status === value);
}

export default function AdminUsage() {
	const months = useMemo(() => monthOptions(), []);
	const [month, setMonth] = useState(months[0]);
	const [usage, setUsage] = useState<MonthlyUsage | null>(null);
	const [runs, setRuns] = useState<AdminExperiment[]>([]);
	const [runsTotal, setRunsTotal] = useState(0);
	const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
	const [auditTotal, setAuditTotal] = useState(0);
	const [loading, setLoading] = useState(true);
	const [runsLoading, setRunsLoading] = useState(true);
	const [error, setError] = useState('');
	const [runsError, setRunsError] = useState('');
	const [runStatusFilter, setRunStatusFilter] = useState<RunStatusFilter>('all');
	const [auditQuery, setAuditQuery] = useState('');

	useEffect(() => {
		let cancelled = false;
		const { from, to } = monthRange(month);
		Promise.allSettled([getMonthlyUsage(month), getAuditLogs(from, to, 0, 20)])
			.then(([usageResult, auditResult]) => {
				if (cancelled) return;
				const errors: string[] = [];
				if (usageResult.status === 'fulfilled') {
					setUsage(usageResult.value);
				} else {
					errors.push(usageResult.reason instanceof Error ? usageResult.reason.message : '사용량을 불러오지 못했습니다.');
				}
				if (auditResult.status === 'fulfilled') {
					setAuditLogs(auditResult.value.content);
					setAuditTotal(auditResult.value.totalElements);
				} else {
					errors.push(auditResult.reason instanceof Error ? auditResult.reason.message : '감사 로그를 불러오지 못했습니다.');
				}
				setError(errors.join(' '));
			})
			.finally(() => {
				if (!cancelled) setLoading(false);
			});
		return () => {
			cancelled = true;
		};
	}, [month]);

	useEffect(() => {
		let cancelled = false;
		getAdminExperiments(0, 20)
			.then((result) => {
				if (cancelled) return;
				setRuns(result.content);
				setRunsTotal(result.totalElements);
				setRunsError('');
			})
			.catch((reason: unknown) => {
				if (!cancelled) setRunsError(reason instanceof Error ? reason.message : '최근 실행 목록을 불러오지 못했습니다.');
			})
			.finally(() => {
				if (!cancelled) setRunsLoading(false);
			});
		return () => {
			cancelled = true;
		};
	}, []);

	const daily = usage?.daily ?? [];
	const maxCost = Math.max(...daily.map((day) => day.costUsd), 0);
	const peakDay = daily.reduce<(typeof daily)[number] | null>((peak, day) => (!peak || day.costUsd > peak.costUsd ? day : peak), null);
	const visibleRuns = runStatusFilter === 'all' ? runs : runs.filter((run) => run.status === runStatusFilter);
	const statusCounts = runStatuses.reduce<Record<AdminExperiment['status'], number>>(
		(counts, status) => ({ ...counts, [status]: runs.filter((run) => run.status === status).length }),
		{ queued: 0, accepted: 0, running: 0, done: 0, failed: 0, cancelled: 0 },
	);
	const normalizedAuditQuery = auditQuery.trim().toLocaleLowerCase('ko-KR');
	const visibleAuditLogs = normalizedAuditQuery
		? auditLogs.filter((log) => `${log.action} ${log.actor} ${log.target}`.toLocaleLowerCase('ko-KR').includes(normalizedAuditQuery))
		: auditLogs;

	return (
		<section className="admin-page" aria-labelledby="admin-usage-title">
			<header className="admin-page-header admin-page-header--actions">
				<div>
					<p className="admin-eyebrow">A3 · USAGE & AUDIT</p>
					<h1 id="admin-usage-title">사용량·감사</h1>
					<p>실험 사용량과 주요 운영 이벤트를 확인합니다.</p>
				</div>
				<div className="admin-page-actions">
					<label className="admin-period-select">
						<span className="sr-only">조회 월</span>
						<select value={month} onChange={(event) => {
							setLoading(true);
							setError('');
							setMonth(event.target.value);
						}}>
							{months.map((value) => <option key={value} value={value}>{value.replace('-', '.')}</option>)}
						</select>
					</label>
					<button className="admin-button admin-button--secondary" type="button" disabled>로그 내보내기 · P2</button>
				</div>
			</header>

			{error && <p role="alert">{error}</p>}
			{loading && !usage && <p>불러오는 중입니다...</p>}

			{usage && (
				<>
					<div className="admin-stat-grid admin-stat-grid--usage">
						<article className="admin-stat-card"><span>월 비용</span><strong>{formatKrw(usage.total.costUsd)}</strong><small>runs 비용 합계(원화 환산) · {usage.month}</small></article>
						<article className="admin-stat-card"><span>사용 토큰</span><strong>{usage.total.tokens.toLocaleString('ko-KR')}</strong><small>월 누적 토큰</small></article>
						<article className="admin-stat-card"><span>회차 수</span><strong>{usage.total.runCount.toLocaleString('ko-KR')}</strong><small>월 누적 run 수</small></article>
						<article className="admin-stat-card"><span>최대 비용 일</span><strong>{peakDay && peakDay.costUsd > 0 ? peakDay.date.slice(5) : '—'}</strong><small>{peakDay && peakDay.costUsd > 0 ? formatKrw(peakDay.costUsd) : '비용 기록 없음'}</small></article>
					</div>
				</>
			)}

			<div className="admin-usage-layout">
				<div className="admin-usage-main">
					{usage && (
						<section className="admin-panel admin-cost-panel">
							<div className="admin-panel-heading"><h2>일별 비용</h2><span>{usage.month}</span></div>
							{daily.length === 0 ? (
								<p>이 기간의 사용량이 없습니다.</p>
							) : (
								<div className="admin-bar-chart" role="img" aria-label={`${usage.month} 일별 비용 그래프`}>
									{daily.map((day) => (
										<div className="admin-bar-column" key={day.date}>
											<div
												className={`admin-bar${peakDay?.date === day.date && day.costUsd > 0 ? ' is-highlighted' : ''}`}
												style={{ height: `${maxCost > 0 ? Math.max((day.costUsd / maxCost) * 100, 2) : 2}%` }}
												title={`${day.date} · ${formatKrw(day.costUsd)} · ${day.runCount}회`}
											/>
											<span>{Number(day.date.slice(8))}일</span>
										</div>
									))}
								</div>
							)}
							<p className="admin-chart-caption">일별 비용(원) · 최대 {formatKrw(maxCost)} · 기간 합계 {formatKrw(usage.total.costUsd)} · 환산 기준 1 USD = ₩{KRW_PER_USD.toLocaleString('ko-KR')}</p>
						</section>
					)}

					<section className="admin-panel admin-recent-runs">
					<div className="admin-panel-heading">
						<div><h2>최근 실행</h2><span>최신 {runs.length}건 · 전체 {runsTotal}건</span></div>
						<label className="admin-period-select">
							<span className="sr-only">실행 상태 필터</span>
							<select value={runStatusFilter} onChange={(event) => {
								const value = event.target.value;
								if (value === 'all' || isRunStatus(value)) setRunStatusFilter(value);
							}}>
								<option value="all">모든 상태</option>
								{Object.entries(runStatusLabels).map(([status, label]) => <option key={status} value={status}>{label}</option>)}
							</select>
						</label>
					</div>
					{runsError && <p role="alert">{runsError}</p>}
					<div className="admin-table-wrap">
						<table className="admin-table admin-runs-table">
							<thead><tr><th>누가</th><th>언제</th><th>대상</th><th>비용</th><th>상태</th></tr></thead>
							<tbody>
								{visibleRuns.map((run) => (
									<tr key={run.firstRunId}>
										<td>{run.ownerEmail}</td>
										<td>{formatTime(run.createdAt)}</td>
										<td><strong>{run.projectTitle}{run.projectDeleted ? ' · 삭제된 프로젝트' : ''}</strong><small>{run.taskGoal || `실험 #${run.firstRunId}`}</small></td>
										<td title="관리자 실행 목록 API에서 회차별 비용을 제공하지 않습니다.">—</td>
										<td><span className={`admin-run-badge admin-run-badge--${run.status}`}>{runStatusLabels[run.status]}</span></td>
									</tr>
								))}
								{runsLoading && runs.length === 0 && <tr><td colSpan={5} className="admin-table-message">실행 목록을 불러오는 중입니다.</td></tr>}
								{!runsLoading && !runsError && visibleRuns.length === 0 && (
									<tr><td colSpan={5} className="admin-table-message">{runs.length ? '선택한 상태의 실행이 없습니다.' : '실행 기록이 없습니다.'}</td></tr>
								)}
							</tbody>
						</table>
					</div>
				</section>
				</div>

				<div className="admin-usage-side">
				<section className="admin-panel admin-run-status-panel">
					<div className="admin-panel-heading"><h2>상태</h2><span>최근 {runs.length}건 기준</span></div>
					<dl>
						{runStatuses.map((status) => (
							<div key={status}>
								<dt>{runStatusLabels[status]}</dt>
								<dd>{statusCounts[status]}</dd>
							</div>
						))}
					</dl>
					<div className="admin-callout">
						<strong>비고</strong>
						<p>상태 집계는 아래 최근 실행 목록에 불러온 실행 기준이며, 전체 {runsTotal}건 중 일부일 수 있습니다.</p>
					</div>
				</section>

				<section className="admin-panel admin-audit-panel">
					<div className="admin-panel-heading">
						<div><h2>감사 로그</h2><span>조회 기간 내 총 {auditTotal}건 · 최근 {auditLogs.length}건</span></div>
						<label className="admin-search-field admin-audit-search">
							<span className="sr-only">감사 로그 검색</span>
							<input value={auditQuery} onChange={(event) => setAuditQuery(event.target.value)} placeholder="행위·대상·사용자 검색" />
						</label>
					</div>
					{auditLogs.length === 0 ? (
						<p>이 기간의 감사 로그가 없습니다.</p>
					) : visibleAuditLogs.length === 0 ? (
						<p>최근 감사 로그에서 검색 결과가 없습니다.</p>
					) : (
						<ul className="admin-audit-list">
							{visibleAuditLogs.map((log) => (
								<li key={log.auditLogId}>
									<span className="admin-audit-icon admin-audit-icon--warning"><CircleAlert size={15} aria-hidden="true" /></span>
									<div><strong>{log.action} · {log.target}</strong><small>{log.actor} · {formatTime(log.ts)}</small></div>
								</li>
							))}
						</ul>
					)}
				</section>
				</div>
			</div>
		</section>
	);
}
