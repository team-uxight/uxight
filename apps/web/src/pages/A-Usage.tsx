import { useEffect, useMemo, useState } from 'react';
import { CircleAlert } from 'lucide-react';
import { getAuditLogs, getMonthlyUsage, type AuditLog, type MonthlyUsage } from '../auth';

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

const formatUsd = (value: number) => `$ ${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const formatTime = (ts: string) => ts.replace('T', ' ').slice(0, 16);

export default function AdminUsage() {
	const months = useMemo(() => monthOptions(), []);
	const [month, setMonth] = useState(months[0]);
	const [usage, setUsage] = useState<MonthlyUsage | null>(null);
	const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
	const [auditTotal, setAuditTotal] = useState(0);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState('');

	useEffect(() => {
		let cancelled = false;
		const { from, to } = monthRange(month);
		setLoading(true);
		setError('');
		Promise.all([getMonthlyUsage(month), getAuditLogs(from, to, 0, 20)])
			.then(([usageResult, auditResult]) => {
				if (cancelled) return;
				setUsage(usageResult);
				setAuditLogs(auditResult.content);
				setAuditTotal(auditResult.totalElements);
			})
			.catch((reason: unknown) => {
				if (!cancelled) setError(reason instanceof Error ? reason.message : '사용량·감사 정보를 불러오지 못했습니다.');
			})
			.finally(() => {
				if (!cancelled) setLoading(false);
			});
		return () => {
			cancelled = true;
		};
	}, [month]);

	const daily = usage?.daily ?? [];
	const maxCost = Math.max(...daily.map((day) => day.costUsd), 0);
	const peakDay = daily.reduce<(typeof daily)[number] | null>((peak, day) => (!peak || day.costUsd > peak.costUsd ? day : peak), null);

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
						<select value={month} onChange={(event) => setMonth(event.target.value)}>
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
						<article className="admin-stat-card"><span>월 비용</span><strong>{formatUsd(usage.total.costUsd)}</strong><small>runs 비용 합계(USD) · {usage.month}</small></article>
						<article className="admin-stat-card"><span>사용 토큰</span><strong>{usage.total.tokens.toLocaleString('ko-KR')}</strong><small>월 누적 토큰</small></article>
						<article className="admin-stat-card"><span>회차 수</span><strong>{usage.total.runCount.toLocaleString('ko-KR')}</strong><small>월 누적 run 수</small></article>
						<article className="admin-stat-card"><span>최대 비용 일</span><strong>{peakDay && peakDay.costUsd > 0 ? peakDay.date.slice(5) : '—'}</strong><small>{peakDay && peakDay.costUsd > 0 ? formatUsd(peakDay.costUsd) : '비용 기록 없음'}</small></article>
					</div>

					<div className="admin-usage-overview">
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
												title={`${day.date} · ${formatUsd(day.costUsd)} · ${day.runCount}회`}
											/>
											<span>{Number(day.date.slice(8))}일</span>
										</div>
									))}
								</div>
							)}
							<p className="admin-chart-caption">일별 비용(USD) · 최대 {formatUsd(maxCost)} · 기간 합계 {formatUsd(usage.total.costUsd)}</p>
						</section>
					</div>
				</>
			)}

			<div className="admin-usage-details">
				<section className="admin-panel admin-audit-panel">
					<div className="admin-panel-heading"><h2>감사 로그</h2><span>audit_log · 총 {auditTotal}건</span></div>
					{auditLogs.length === 0 ? (
						<p>이 기간의 감사 로그가 없습니다.</p>
					) : (
						<ul className="admin-audit-list">
							{auditLogs.map((log) => (
								<li key={log.auditLogId}>
									<span className="admin-audit-icon admin-audit-icon--warning"><CircleAlert size={15} aria-hidden="true" /></span>
									<div><strong>{log.action} · {log.target}</strong><small>{log.actor} · {formatTime(log.ts)}</small></div>
								</li>
							))}
						</ul>
					)}
				</section>
			</div>
		</section>
	);
}
