import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useOutletContext } from 'react-router-dom';
import { apiErrorMessage, authenticatedFetch, API_BASE_URL } from '../auth';
import { fetchExperimentStats, fetchExperiments, type Experiment, type ExperimentStats } from './experiments';

type MonitorFilter = '전체' | '진행 중' | '완료' | '중단' | '실패';
type LocationState = {
	createdRunId?: number;
};
type LayoutContext = {
	query: string;
};

const activeStatuses = new Set(['queued', 'accepted', 'running']);

function displayStatus(experiment: Experiment): string {
	if (experiment.state === 'completed') return '완료';
	if (experiment.state === 'awaiting_approval') return '승인 대기';
	if (experiment.state === 'in_progress') return '진행 중';
	if (experiment.endType === 'failed' || experiment.status === 'failed') return '실패';
	return '중단';
}

function displayStatusClass(status: string): string {
	if (status === '진행 중' || status === '승인 대기') return 'running';
	if (status === '완료') return 'done';
	return 'failed';
}

function formatDate(value: string): string {
	const date = new Date(value);
	return Number.isNaN(date.getTime())
		? value
		: new Intl.DateTimeFormat('ko-KR', { dateStyle: 'short', timeStyle: 'short' }).format(date);
}

export default function RMonitor() {
	const location = useLocation();
	const navigate = useNavigate();
	const { query } = useOutletContext<LayoutContext>();
	const [filter, setFilter] = useState<MonitorFilter>('전체');
	const [experiments, setExperiments] = useState<Experiment[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState('');
	const [stats, setStats] = useState<ExperimentStats | null>(null);
	const [statsError, setStatsError] = useState('');
	const [cancelingId, setCancelingId] = useState<number | null>(null);
	const [expandedRunId, setExpandedRunId] = useState<number | null>(null);
	const [notice, setNotice] = useState('');
	const locationState = location.state as LocationState | null;

	const refreshExperiments = useCallback(async () => {
		try {
			setExperiments(await fetchExperiments());
			setError('');
		} catch (loadError: unknown) {
			setError(loadError instanceof Error ? loadError.message : '실험 목록을 불러오지 못했습니다.');
		} finally {
			setIsLoading(false);
		}
	}, []);

	const refreshStats = useCallback(async () => {
		try {
			setStats(await fetchExperimentStats());
			setStatsError('');
		} catch (loadError: unknown) {
			setStatsError(loadError instanceof Error ? loadError.message : '실험 통계를 불러오지 못했습니다.');
		}
	}, []);

	useEffect(() => {
		let active = true;
		fetchExperiments()
			.then((data) => {
				if (active) {
					setExperiments(data);
					setError('');
				}
			})
			.catch((loadError: unknown) => {
				if (active) {
					setError(loadError instanceof Error ? loadError.message : '실험 목록을 불러오지 못했습니다.');
				}
			})
			.finally(() => {
				if (active) setIsLoading(false);
			});
		return () => {
			active = false;
		};
	}, []);

	useEffect(() => {
		let active = true;
		fetchExperimentStats()
			.then((data) => {
				if (active) {
					setStats(data);
					setStatsError('');
				}
			})
			.catch((loadError: unknown) => {
				if (active) {
					setStatsError(loadError instanceof Error ? loadError.message : '실험 통계를 불러오지 못했습니다.');
				}
			});
		return () => {
			active = false;
		};
	}, []);

	useEffect(() => {
		if (!experiments.some((experiment) => activeStatuses.has(experiment.status))) return;
		const intervalId = window.setInterval(() => {
			void refreshExperiments();
			void refreshStats();
		}, 3000);
		return () => window.clearInterval(intervalId);
	}, [experiments, refreshExperiments, refreshStats]);

	const cancelExperiment = async (firstRunId: number) => {
		setCancelingId(firstRunId);
		setError('');
		try {
			const response = await authenticatedFetch(`${API_BASE_URL}/api/runs/${firstRunId}/cancel`, {
				method: 'POST',
			});
			if (!response.ok) {
				throw new Error(await apiErrorMessage(response, '실험 취소 요청에 실패했습니다.'));
			}
			setNotice(`실험 #${firstRunId}의 취소를 요청했습니다.`);
			await Promise.all([refreshExperiments(), refreshStats()]);
		} catch (cancelError: unknown) {
			setError(cancelError instanceof Error ? cancelError.message : '실험 취소 요청에 실패했습니다.');
		} finally {
			setCancelingId(null);
		}
	};

	const filteredExperiments = useMemo(
		() => experiments
			.filter((experiment) => filter === '전체' || displayStatus(experiment) === filter)
			.filter((experiment) =>
				`${experiment.projectTitle} ${experiment.taskGoal} ${experiment.firstRunId}`
					.toLowerCase()
					.includes(query.toLowerCase()),
			),
		[experiments, filter, query],
	);

	const hasUnreachable = useMemo(
		() => experiments.some((experiment) => experiment.agentUnreachable),
		[experiments],
	);

	return (
		<section className="rd-monitor" aria-labelledby="monitor-title">
			{locationState?.createdRunId !== undefined && (
				<div className="rd-save-confirmation" role="status">
					<div>
						<strong>실험 요청을 접수했습니다. (#{locationState.createdRunId})</strong>
						<span>Agent가 실행을 수락하면 진행 상태가 여기에 반영됩니다.</span>
					</div>
				</div>
			)}
			<div className="rd-monitor-heading">
				<div className="rd-title-inline">
					<h1 id="monitor-title">Monitor</h1>
					<span>— 실험 진행 상태와 최근 실행 결과 확인</span>
				</div>
				<span className="rd-demo-label">실제 실험 데이터</span>
			</div>
			{statsError && <div className="rd-notice" role="status">{statsError}</div>}
			<div className="rd-monitor-stats" aria-label="실험 통계">
				<div><span>전체 실험</span><strong>{stats ? formatCount(stats.totalCount) : '—'}</strong></div>
				<div><span>진행 중</span><strong>{stats ? formatCount(stats.inProgressCount) : '—'}</strong></div>
				<div><span>전체 완료</span><strong>{stats ? formatCount(stats.completedCount) : '—'}</strong></div>
				<div><span>승인 대기</span><strong>{stats ? formatCount(stats.awaitingApprovalCount) : '—'}</strong></div>
				<div><span>이번 주 완료</span><strong>{stats ? formatCount(stats.completedThisWeekCount) : '—'}</strong></div>
				<div><span>누적 토큰</span><strong>{stats ? formatCount(stats.totalTokens) : '—'}</strong></div>
			</div>
			{notice && <div className="rd-notice" role="status">{notice}</div>}
			{error && <div className="rd-notice" role="alert"><span>{error}</span></div>}
			{hasUnreachable && (
				<div className="rd-notice rd-notice--warning" role="status">
					<span>AI 모듈에 연결하지 못해 재시도 중인 실험이 있습니다. 백엔드에서 30초마다 자동으로 재전송합니다.</span>
				</div>
			)}
			<div className="rd-monitor-toolbar">
				<div className="rd-monitor-tabs" role="tablist" aria-label="실험 상태 필터">
					{(['전체', '진행 중', '완료', '중단', '실패'] as const).map((item) => (
						<button
							className={filter === item ? 'is-selected' : ''}
							key={item}
							type="button"
							role="tab"
							aria-selected={filter === item}
							onClick={() => setFilter(item)}
						>
							{item}
						</button>
					))}
				</div>
				<span className="rd-monitor-result-count">{filteredExperiments.length}개 실험</span>
			</div>
			{isLoading ? (
				<div className="rd-empty-state" role="status"><p>실험 목록을 불러오는 중입니다.</p></div>
			) : filteredExperiments.length > 0 ? (
				<div className="rd-run-list">
					{filteredExperiments.map((experiment) => {
						const status = displayStatus(experiment);
						const canCancel = experiment.state === 'in_progress' && activeStatuses.has(experiment.status);
						const isExpanded = expandedRunId === experiment.firstRunId;
						// API 의 progress 는 종료된 Persona 수이므로 퍼센트로 환산한다.
						const progress = experiment.progress === null || experiment.personaCount <= 0
							? null
							: Math.min(100, Math.max(0, Math.round((experiment.progress / experiment.personaCount) * 100)));
						return (
							<article className={`rd-run-row${isExpanded ? ' is-expanded' : ''}`} key={experiment.firstRunId}>
								<button
									type="button"
									className="rd-run-chevron"
									aria-label={isExpanded ? '실험 세부정보 접기' : '실험 세부정보 펼치기'}
									aria-expanded={isExpanded}
									onClick={() => setExpandedRunId(isExpanded ? null : experiment.firstRunId)}
								>
									<svg viewBox="0 0 24 24" aria-hidden="true">
										<path d={isExpanded ? 'm6 9 6 6 6-6' : 'm9 18 6-6-6-6'} />
									</svg>
								</button>
								<span className={`rd-run-status rd-run-status--${displayStatusClass(status)}`}>{status}</span>
								{experiment.agentUnreachable && (
									<span className="rd-run-unreachable-badge">AI 연결 재시도 중</span>
								)}
								<span className="rd-run-id">#{experiment.firstRunId} · {experiment.round}회차</span>
								<div className="rd-run-description">
									<strong>{experiment.taskGoal}</strong>
									<span>{experiment.projectTitle} · {formatDate(experiment.createdAt)} · Persona {experiment.personaCount}명</span>
								</div>
								{canCancel
									? (
										<button
											type="button"
											className="rd-run-action"
											aria-label={`실험 ${experiment.firstRunId} 취소`}
											disabled={cancelingId === experiment.firstRunId}
											onClick={() => void cancelExperiment(experiment.firstRunId)}
										>
											{cancelingId === experiment.firstRunId ? '…' : 'Ⅱ'}
										</button>
									)
									: (
										<span className="rd-run-action rd-run-action--progress" aria-label={`진행률 ${progress ?? 0}%`}>
											{progress === null ? '—' : `${progress}%`}
										</span>
									)}
								{isExpanded && (
									<div className="rd-run-details">
										{experiment.agentUnreachable && (
											<div className="rd-run-unreachable-banner" role="status">
												<strong>AI 모듈에 연결하지 못해 재시도 중</strong>
												<span>실행 서비스에 일시적으로 연결할 수 없어 30초마다 재전송을 시도하고 있습니다.</span>
											</div>
										)}
										<div className="rd-run-progress-card">
											<div className="rd-run-progress-heading">
												<span>진행률</span>
												<strong>{progress === null ? '집계 전' : `${progress}%`}</strong>
											</div>
											<div
												className="rd-run-progress-track"
												role="progressbar"
												aria-label="실험 진행률"
												aria-valuemin={0}
												aria-valuemax={100}
												aria-valuenow={progress ?? 0}
											>
												<span style={{ width: `${progress ?? 0}%` }} />
											</div>
										</div>
										<div className="rd-run-detail-chip">
											<span>참여 Persona</span>
											<strong>{experiment.personaCount}명</strong>
										</div>
										<div className="rd-run-detail-chip">
											<span>경과 시간</span>
											<strong>{formatElapsed(experiment.elapsedSeconds)}</strong>
										</div>
										<div className="rd-run-detail-chip">
											<span>실험 범위</span>
											<strong>{experiment.mode}</strong>
										</div>
										<div className="rd-run-detail-foot">
											<span>
												{experiment.agentUnreachable
													? 'AI 모듈에 연결하지 못해 재시도 중입니다. (30초마다 자동 재전송)'
													: experiment.stale
														? '진행 상태가 오래 갱신되지 않았습니다.'
														: experiment.hasResult
															? '실험 결과가 등록되어 있습니다.'
															: '실험 결과를 기다리는 중입니다.'}
											</span>
											<div className="rd-run-detail-actions">
												<button
													type="button"
													className="rd-live-monitor-button"
													aria-label={`실험 ${experiment.firstRunId} 실시간 모니터링`}
													onClick={() => navigate(`/monitor/${experiment.firstRunId}`)}
												>
													<svg viewBox="0 0 24 24" aria-hidden="true">
														<path d="M7 17 17 7M8 7h9v9" />
													</svg>
													<span>실시간 모니터링</span>
												</button>
												{canCancel && (
													<button
														type="button"
														className="rd-run-detail-cancel"
														disabled={cancelingId === experiment.firstRunId}
														onClick={() => void cancelExperiment(experiment.firstRunId)}
													>
														{cancelingId === experiment.firstRunId ? '취소 요청 중…' : '실험 취소'}
													</button>
												)}
											</div>
										</div>
									</div>
								)}
							</article>
						);
					})}
				</div>
			) : error ? (
				<div className="rd-empty-state" role="alert">
					<p>실험 목록을 표시하지 못했습니다.</p>
					<button type="button" onClick={() => {
						setIsLoading(true);
						void refreshExperiments();
					}}>다시 시도</button>
				</div>
			) : (
				<div className="rd-empty-state">
					<p>{experiments.length === 0 ? '아직 등록된 실험이 없습니다.' : '조건에 맞는 실험이 없습니다.'}</p>
				</div>
			)}
		</section>
	);
}

function formatElapsed(seconds: number): string {
	const safeSeconds = Math.max(0, seconds);
	const minutes = Math.floor(safeSeconds / 60);
	const remainingSeconds = safeSeconds % 60;
	return minutes > 0 ? `${minutes}분 ${remainingSeconds}초` : `${remainingSeconds}초`;
}

function formatCount(value: number): string {
	return new Intl.NumberFormat('ko-KR').format(value);
}
