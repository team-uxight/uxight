import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
	cancelExperiment,
	fetchExperimentById,
	fetchExperimentRounds,
	type Experiment,
	type ExperimentRound,
} from './experiments';
import './R-MonitorLive.css';

const stateLabels: Record<Experiment['state'], string> = {
	in_progress: '실험 진행 중',
	awaiting_approval: '다음 회차 승인 대기',
	completed: '실험 완료',
	stopped: '실험 중단',
};

const roundStatusLabels: Record<string, string> = {
	queued: '대기 중',
	accepted: '접수됨',
	running: '진행 중',
	done: '완료',
	failed: '실패',
	cancelled: '취소됨',
};

function formatDateTime(value: string | null): string {
	if (!value) return '—';
	const date = new Date(value);
	return Number.isNaN(date.getTime())
		? value
		: new Intl.DateTimeFormat('ko-KR', { dateStyle: 'short', timeStyle: 'short' }).format(date);
}

function formatNumber(value: number | null | undefined, digits = 0): string {
	return value == null ? '—' : new Intl.NumberFormat('ko-KR', { maximumFractionDigits: digits }).format(value);
}

export default function RMonitorLive() {
	const { runId } = useParams();
	const navigate = useNavigate();
	const [experiment, setExperiment] = useState<Experiment | null>(null);
	const [rounds, setRounds] = useState<ExperimentRound[]>([]);
	const [awaitingApproval, setAwaitingApproval] = useState(false);
	const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
	const [loadState, setLoadState] = useState<'loading' | 'ready' | 'notFound' | 'error'>('loading');
	const [loadedRunId, setLoadedRunId] = useState<string | null>(null);
	const [loadError, setLoadError] = useState<string | null>(null);
	const [cancelError, setCancelError] = useState<string | null>(null);
	const [cancelRequested, setCancelRequested] = useState(false);

	const refreshDetails = useCallback(async (): Promise<void> => {
		const firstRunId = Number(runId);
		if (!Number.isSafeInteger(firstRunId) || firstRunId <= 0) {
			setLoadedRunId(runId ?? '');
			setLoadState('notFound');
			return;
		}

		const [found, roundResponse] = await Promise.all([
			fetchExperimentById(firstRunId),
			fetchExperimentRounds(firstRunId),
		]);
		setExperiment(found);
		setRounds(roundResponse.rounds);
		setAwaitingApproval(roundResponse.awaitingApproval);
		setLoadedRunId(runId ?? '');
		setSelectedRunId((current) =>
			roundResponse.rounds.some((round) => round.runId === current)
				? current
				: roundResponse.rounds.length > 0
					? roundResponse.rounds[roundResponse.rounds.length - 1].runId
					: null,
		);
		setLoadState(found ? 'ready' : 'notFound');
		setLoadError(null);
	}, [runId]);

	useEffect(() => {
		let active = true;
		void Promise.resolve()
			.then(() => {
				if (!active) return;
				return refreshDetails();
			})
			.catch((error: unknown) => {
				if (!active) return;
				setLoadedRunId(runId ?? '');
				setLoadState('error');
				setLoadError(error instanceof Error ? error.message : '실험 정보를 불러오지 못했습니다.');
			});
		return () => {
			active = false;
		};
	}, [refreshDetails, runId]);

	useEffect(() => {
		if (loadState !== 'ready' || experiment?.state !== 'in_progress') return;
		const intervalId = window.setInterval(() => {
			refreshDetails().catch((error: unknown) => {
				setLoadError(error instanceof Error ? error.message : '실험 상태를 갱신하지 못했습니다.');
			});
		}, 3000);
		return () => window.clearInterval(intervalId);
	}, [experiment?.state, loadState, refreshDetails]);

	async function handleCancel() {
		if (!experiment || cancelRequested) return;
		setCancelRequested(true);
		setCancelError(null);
		try {
			await cancelExperiment(experiment.firstRunId);
			await refreshDetails();
		} catch (error) {
			setCancelError(error instanceof Error ? error.message : '실험 취소를 요청하지 못했습니다.');
		} finally {
			setCancelRequested(false);
		}
	}

	const isLoading = loadState === 'loading' || loadedRunId !== (runId ?? '');
	if (isLoading || loadState !== 'ready' || experiment === null) {
		const message = isLoading
			? '실험 정보를 불러오는 중입니다.'
			: loadState === 'notFound'
				? `실험 #${runId}을(를) 찾을 수 없습니다.`
				: loadError ?? '실험 정보를 불러오지 못했습니다.';
		return (
			<section className="rml">
				<div className="rml-panel rml-empty" role="status">
					<p>{message}</p>
					<button type="button" className="rml-back" onClick={() => navigate('/monitor')}>← 목록</button>
				</div>
			</section>
		);
	}

	const canCancel = experiment.state === 'in_progress' || experiment.state === 'awaiting_approval';
	const selectedRound = rounds.find((round) => round.runId === selectedRunId) ?? null;

	return (
		<section className="rml" aria-labelledby="rml-title">
			<div className="rml-panel">
				<header className="rml-header">
					<button type="button" className="rml-back" onClick={() => navigate('/monitor')}>← 목록</button>
					<span className="rml-run-label">실험 {experiment.firstRunId}</span>
					<h1 id="rml-title">{experiment.taskGoal}</h1>
					{experiment.agentUnreachable && (
						<span className="rml-unreachable-badge">AI 연결 재시도 중</span>
					)}
					<span className={`rml-live${canCancel ? '' : ' is-ended'}`}>{stateLabels[experiment.state]}</span>
					{canCancel && (
						<button type="button" className="rml-cancel" onClick={handleCancel} disabled={cancelRequested}>
							{cancelRequested ? '취소 요청 중…' : '실험 취소'}
						</button>
					)}
				</header>
				{experiment.agentUnreachable && (
					<div className="rml-unreachable-banner" role="status">
						<strong>AI 모듈에 연결하지 못해 재시도 중</strong>
						<span>실행 서비스에 일시적으로 연결할 수 없어 백엔드가 30초마다 자동으로 재전송을 시도하고 있습니다. 연결되면 자동으로 실험이 진행됩니다.</span>
					</div>
				)}
				<div className="rml-body">
					<div className="rml-sidebar">
						<div className="rml-rounds" aria-label="회차 목록">
							<h2>실험 회차</h2>
							{awaitingApproval && <p className="rml-approval">다음 회차 진행을 기다리고 있습니다.</p>}
							{rounds.length === 0
								? <p className="rml-muted">표시할 회차가 없습니다.</p>
								: rounds.map((round) => (
								<button
									type="button"
									aria-pressed={selectedRunId === round.runId}
									className={`rml-round${selectedRunId === round.runId ? ' is-selected' : ''}`}
									key={round.runId}
									onClick={() => setSelectedRunId(round.runId)}
								>
									<strong>{round.round}회차</strong>
									<span className={`rml-round-status rml-round-status--${round.status}`}>
										{roundStatusLabels[round.status] ?? round.status}
									</span>
									<small>{formatDateTime(round.createdAt)}</small>
								</button>
							))}
						</div>
						<div className="rml-bottom">
							<div className="rml-tiles">
								<div className="rml-tile"><small>완료 Persona</small><strong>{experiment.progress == null ? '—' : `${experiment.progress} / ${experiment.personaCount}`}</strong></div>
								<div className="rml-tile"><small>경과 시간</small><strong>{experiment.elapsedSeconds}초</strong></div>
								<div className="rml-tile"><small>진행 회차</small><strong>{experiment.round}회차</strong></div>
							</div>
							<div className="rml-log">
								<small>실험 정보</small>
								<p>{experiment.projectTitle} · {experiment.mode} · 최근 요청 {formatDateTime(experiment.createdAt)}</p>
								{loadError && <p className="rml-error" role="status">갱신 실패: {loadError}</p>}
								{cancelError && <p className="rml-error" role="alert">{cancelError}</p>}
							</div>
						</div>
					</div>
					<div className="rml-main">
						<div className="rml-viewer" aria-label="AI 실험 화면">
							<div className="rml-viewer-toolbar">
								<div className="rml-browser-dots" aria-hidden="true"><i /><i /><i /></div>
								<span>AI 브라우저 화면</span>
								<span className={`rml-viewer-state${experiment.agentUnreachable ? ' is-warning' : experiment.state === 'in_progress' ? ' is-live' : ''}`}>
									{experiment.agentUnreachable
										? 'AI 연결 재시도 중'
										: experiment.state === 'in_progress'
											? '실험 진행 중'
											: '연결 대기'}
								</span>
							</div>
							<div className="rml-screen" role="status">
								<div className="rml-screen-message">
									<svg viewBox="0 0 48 48" aria-hidden="true">
										<rect x="5" y="8" width="38" height="27" rx="4" />
										<path d="M17 41h14M24 35v6M19 21l4 4 7-8" />
									</svg>
									<strong>
										{experiment.agentUnreachable
											? 'AI 모듈에 연결하지 못해 재시도 중입니다'
											: 'AI가 실험 중인 화면이 여기에 표시됩니다'}
									</strong>
									<span>
										{experiment.agentUnreachable
											? '실행 서비스에 연결할 수 없어 30초마다 재전송을 시도하고 있습니다. 요청이 접수되면 상태가 갱신됩니다.'
											: '현재 API에서 브라우저 화면 스트림을 제공하지 않아 연결을 기다리고 있습니다.'}
									</span>
								</div>
							</div>
							<div className="rml-viewer-caption">
								<span>{experiment.projectTitle}</span>
								<span>
									{experiment.agentUnreachable
										? 'AI 모듈 연결을 재시도하고 있습니다. (30초마다 재전송)'
										: experiment.state === 'in_progress'
											? '실험 상태를 3초마다 확인합니다.'
											: stateLabels[experiment.state]}
								</span>
							</div>
						</div>
					</div>
					<div className="rml-round-detail">
						{selectedRound ? (
							<>
								<div className="rml-detail-heading">
									<div>
										<small>선택한 회차</small>
										<h2>{selectedRound.round}회차 상세</h2>
									</div>
									<span className={`rml-round-status rml-round-status--${selectedRound.status}`}>
										{roundStatusLabels[selectedRound.status] ?? selectedRound.status}
									</span>
								</div>
								<dl className="rml-round-times">
									<div><dt>시작</dt><dd>{formatDateTime(selectedRound.createdAt)}</dd></div>
									<div><dt>종료</dt><dd>{formatDateTime(selectedRound.finishedAt)}</dd></div>
									<div><dt>회차 ID</dt><dd>{selectedRound.runId}</dd></div>
									<div><dt>승인 개선안</dt><dd>{selectedRound.appliedImprovementId ?? '최초 회차'}</dd></div>
								</dl>
								<h3>완료 지표</h3>
								{selectedRound.metrics ? (
									<div className="rml-metrics">
										<div><small>성공률</small><strong>{formatNumber(selectedRound.metrics.successRate, 1)}%</strong></div>
										<div><small>평균 step</small><strong>{formatNumber(selectedRound.metrics.avgSteps, 1)}</strong></div>
										<div><small>평균 되돌아가기</small><strong>{formatNumber(selectedRound.metrics.avgBacktracks, 1)}</strong></div>
										<div><small>평균 시간</small><strong>{formatNumber(selectedRound.metrics.avgSeconds, 1)}초</strong></div>
										<div><small>토큰</small><strong>{formatNumber(selectedRound.metrics.tokens)}</strong></div>
										<div><small>비용</small><strong>{selectedRound.metrics.costUsd == null ? '—' : `$${formatNumber(selectedRound.metrics.costUsd, 4)}`}</strong></div>
									</div>
								) : (
									<p className="rml-muted">회차가 완료되면 지표가 표시됩니다.</p>
								)}
							</>
						) : (
							<p className="rml-muted">회차 정보를 기다리는 중입니다.</p>
						)}
					</div>
				</div>
			</div>
		</section>
	);
}
