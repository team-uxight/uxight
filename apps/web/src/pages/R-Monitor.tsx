import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useOutletContext } from 'react-router-dom';
import { API_BASE_URL, apiErrorMessage, authenticatedFetch } from '../auth';

type MonitorFilter = '전체' | '진행 중' | '완료' | '중단' | '실패';
type Experiment = {
	firstRunId: number;
	runId: number;
	round: number;
	status: string;
	state: 'in_progress' | 'awaiting_approval' | 'completed' | 'stopped';
	endType: string | null;
	stale: boolean;
	hasResult: boolean;
	projectTitle: string;
	taskGoal: string;
	mode: string;
	progress: number | null;
	personaCount: number;
	elapsedSeconds: number;
	createdAt: string;
};
type LocationState = {
	createdRunId?: number;
};
type LayoutContext = {
	query: string;
};

const pageSize = 20;
const activeStatuses = new Set(['queued', 'accepted', 'running']);

function isExperiment(value: unknown): value is Experiment {
	return typeof value === 'object' &&
		value !== null &&
		'firstRunId' in value && typeof value.firstRunId === 'number' &&
		'runId' in value && typeof value.runId === 'number' &&
		'round' in value && typeof value.round === 'number' &&
		'status' in value && typeof value.status === 'string' &&
		'state' in value && ['in_progress', 'awaiting_approval', 'completed', 'stopped'].includes(String(value.state)) &&
		'endType' in value && (typeof value.endType === 'string' || value.endType === null) &&
		'stale' in value && typeof value.stale === 'boolean' &&
		'hasResult' in value && typeof value.hasResult === 'boolean' &&
		'projectTitle' in value && typeof value.projectTitle === 'string' &&
		'taskGoal' in value && typeof value.taskGoal === 'string' &&
		'mode' in value && typeof value.mode === 'string' &&
		'progress' in value && (typeof value.progress === 'number' || value.progress === null) &&
		'personaCount' in value && typeof value.personaCount === 'number' &&
		'elapsedSeconds' in value && typeof value.elapsedSeconds === 'number' &&
		'createdAt' in value && typeof value.createdAt === 'string';
}

async function fetchExperiments(): Promise<Experiment[]> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/runs?page=0&size=${pageSize}`);
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '실험 목록을 불러오지 못했습니다.'));
	}
	const body: unknown = await response.json();
	if (
		typeof body !== 'object' ||
		body === null ||
		!('content' in body) ||
		!Array.isArray(body.content) ||
		!body.content.every(isExperiment)
	) {
		throw new Error('서버에서 올바르지 않은 실험 목록을 받지 못했습니다.');
	}
	return body.content;
}

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
	const { query } = useOutletContext<LayoutContext>();
	const [filter, setFilter] = useState<MonitorFilter>('전체');
	const [experiments, setExperiments] = useState<Experiment[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState('');
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
		if (!experiments.some((experiment) => activeStatuses.has(experiment.status))) return;
		const intervalId = window.setInterval(() => {
			void refreshExperiments();
		}, 3000);
		return () => window.clearInterval(intervalId);
	}, [experiments, refreshExperiments]);

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
			await refreshExperiments();
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
			{notice && <div className="rd-notice" role="status">{notice}</div>}
			{error && <div className="rd-notice" role="alert"><span>{error}</span></div>}
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
						const progress = experiment.progress === null
							? null
							: Math.min(100, Math.max(0, experiment.progress));
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
										<span className="rd-run-action" aria-label={`진행률 ${progress ?? 0}%`}>
											{progress === null ? '—' : `${progress}%`}
										</span>
									)}
								{isExpanded && (
									<div className="rd-run-details">
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
												{experiment.stale
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
													onClick={() => setNotice('AI 브라우저 실시간 모니터링은 백엔드 화면 연동 후 제공될 예정입니다.')}
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
