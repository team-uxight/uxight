import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ApiError, describeAction, fetchPersonaSteps, fetchRunPersonas, type RunPersona, type StepLog } from './runLogs';
import { fetchExperimentRounds, fetchExperiments, type Experiment, type ExperimentRound } from './experiments';
import {
	fetchFindingDetail,
	fetchFindingScreenshot,
	fetchRunFindings,
	type FindingDetail,
	type FindingEvidence,
	type FindingSeverity,
	type FindingTaxonomy,
	severityLabels,
	taxonomyLabels,
} from './findings';

type DiagnosisData = {
	run: Awaited<ReturnType<typeof fetchRunFindings>>['run'];
	findings: FindingDetail[];
	personas: RunPersona[];
	successRate: number | null;
	avgSteps: number | null;
	rounds: ExperimentRound[];
};

type EvidenceTarget = {
	finding: FindingDetail;
	evidence: FindingEvidence;
	personaName: string;
};

type ScreenshotState = {
	url: string | null;
	error: string | null;
};

function errorMessage(error: unknown, fallback: string): string {
	return error instanceof Error ? error.message : fallback;
}

function isFindingSeverity(value: string): value is FindingSeverity {
	return value === 'high' || value === 'medium' || value === 'low';
}

function isFindingTaxonomy(value: string): value is FindingTaxonomy {
	return Object.keys(taxonomyLabels).some((key) => key === value);
}

function formatDateTime(value: string | null): string {
	if (!value) return '시간 정보 없음';
	const date = new Date(value);
	return Number.isNaN(date.getTime())
		? value
		: new Intl.DateTimeFormat('ko-KR', { dateStyle: 'short', timeStyle: 'medium' }).format(date);
}

function EvidenceDialog({
	runId,
	target,
	onClose,
}: {
	runId: number;
	target: EvidenceTarget;
	onClose: () => void;
}) {
	const [steps, setSteps] = useState<StepLog[]>([]);
	const [screenshots, setScreenshots] = useState<Record<number, ScreenshotState>>({});
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const controller = new AbortController();
		let active = true;
		const objectUrls: string[] = [];

		async function loadEvidence() {
			setLoading(true);
			setError(null);
			setSteps([]);
			setScreenshots({});
			try {
				const allSteps = await fetchPersonaSteps(runId, target.evidence.personaId, controller.signal);
				const rangedSteps = allSteps
					.filter((step) => step.step >= target.evidence.stepFrom && step.step <= target.evidence.stepTo)
					.sort((left, right) => left.step - right.step);

				const screenshotResults = await Promise.all(rangedSteps.map(async (step) => {
					if (!step.hasScreenshot) return { step: step.step, blob: null, error: null };
					try {
						const blob = await fetchFindingScreenshot(
							target.finding.findingId,
							target.evidence.personaId,
							step.step,
							controller.signal,
						);
						return { step: step.step, blob, error: null };
					} catch (screenshotError) {
						if (screenshotError instanceof ApiError && screenshotError.status === 404) {
							return { step: step.step, blob: null, error: null };
						}
						return {
							step: step.step,
							blob: null,
							error: errorMessage(screenshotError, '근거 화면을 불러오지 못했습니다.'),
						};
					}
				}));

				if (!active) return;
				const screenshotState: Record<number, ScreenshotState> = {};
				for (const result of screenshotResults) {
					const url = result.blob ? URL.createObjectURL(result.blob) : null;
					if (url) objectUrls.push(url);
					screenshotState[result.step] = { url, error: result.error };
				}
				setSteps(rangedSteps);
				setScreenshots(screenshotState);
			} catch (loadError) {
				if (active) setError(errorMessage(loadError, '근거 로그를 불러오지 못했습니다.'));
			} finally {
				if (active) setLoading(false);
			}
		}

		void loadEvidence();
		return () => {
			active = false;
			controller.abort();
			objectUrls.forEach((url) => URL.revokeObjectURL(url));
		};
	}, [runId, target]);

	return (
		<div className="rd-evidence-backdrop" role="presentation" onClick={onClose}>
			<section
				className="rd-evidence-panel"
				role="dialog"
				aria-modal="true"
				aria-labelledby="evidence-title"
				onClick={(event) => event.stopPropagation()}
			>
				<header className="rd-evidence-head">
					<span>근거 타임라인</span>
					<button type="button" onClick={onClose} aria-label="닫기">×</button>
				</header>
				<h2 id="evidence-title">{taxonomyLabels[target.finding.taxonomy]}</h2>
				<div className="rd-evidence-meta">
					<strong>{target.personaName} · step {target.evidence.stepFrom}-{target.evidence.stepTo}</strong>
					{target.evidence.url && <span className="rd-evidence-url">{target.evidence.url}</span>}
				</div>
				{loading && <p className="rd-diagnosis-feedback" role="status">근거 로그와 화면을 불러오는 중입니다.</p>}
				{error && <p className="rd-diagnosis-feedback is-error" role="alert">{error}</p>}
				{!loading && !error && steps.length === 0 && (
					<p className="rd-diagnosis-feedback">해당 구간의 step 로그가 없습니다.</p>
				)}
				{!loading && !error && steps.length > 0 && (
					<ol className="rd-evidence-steps">
						{steps.map((step) => {
							const screenshot = screenshots[step.step];
							return (
								<li className="rd-evidence-step" key={step.step}>
									<h3>Step {step.step} <time>{formatDateTime(step.ts)}</time></h3>
									<div className="rd-evidence-body">
										<div className="rd-evidence-shot">
											{screenshot?.url
												? <img src={screenshot.url} alt={`${target.personaName} step ${step.step} 화면`} />
												: <span>{screenshot?.error ? `화면을 불러오지 못했습니다: ${screenshot.error}` : '화면 없음'}</span>}
										</div>
										<dl className="rd-evidence-notes">
											<div><dt>생각</dt><dd>{step.reasoning ?? '기록된 생각이 없습니다.'}</dd></div>
											<div><dt>행동</dt><dd>{describeAction(step)}</dd></div>
											<div><dt>주소</dt><dd className="rd-evidence-url">{step.url ?? '—'}</dd></div>
										</dl>
									</div>
								</li>
							);
						})}
					</ol>
				)}
			</section>
		</div>
	);
}

export default function RDiagnosis() {
	const { runId: runIdParam } = useParams();
	const navigate = useNavigate();
	const [loadState, setLoadState] = useState<'loading' | 'ready' | 'empty' | 'error'>('loading');
	const [data, setData] = useState<DiagnosisData | null>(null);
	const [loadError, setLoadError] = useState('');
	const [metricsError, setMetricsError] = useState('');
	const [expandedId, setExpandedId] = useState<number | null>(null);
	const [severity, setSeverity] = useState<'전체' | FindingSeverity>('전체');
	const [taxonomy, setTaxonomy] = useState<'전체' | FindingTaxonomy>('전체');
	const [evidenceTarget, setEvidenceTarget] = useState<EvidenceTarget | null>(null);
	const [runOptions, setRunOptions] = useState<Experiment[]>([]);

	useEffect(() => {
		let active = true;
		fetchExperiments()
			.then((experiments) => {
				if (active) setRunOptions(experiments.filter((experiment) => experiment.hasResult));
			})
			.catch(() => {
				if (active) setRunOptions([]);
			});
		return () => {
			active = false;
		};
	}, []);

	useEffect(() => {
		let active = true;

		async function loadDiagnosis() {
			setLoadState('loading');
			setLoadError('');
			setMetricsError('');
			setData(null);
			setEvidenceTarget(null);

			if (!runIdParam) {
				try {
					const experiments = await fetchExperiments();
					if (!active) return;
					const latest = experiments.find((experiment) => experiment.hasResult);
					if (!latest) {
						setLoadState('empty');
						return;
					}
					navigate(`/diagnosis/${latest.firstRunId}`, { replace: true });
				} catch (error) {
					if (!active) return;
					setLoadError(errorMessage(error, '실험 목록을 불러오지 못했습니다.'));
					setLoadState('error');
				}
				return;
			}

			const runId = Number(runIdParam);
			if (!Number.isSafeInteger(runId) || runId <= 0) {
				setLoadError('올바르지 않은 회차 ID입니다.');
				setLoadState('error');
				return;
			}

			try {
				const [runResponse, personaList] = await Promise.all([
					fetchRunFindings(runId),
					fetchRunPersonas(runId),
				]);
				const [findings, metricsResult] = await Promise.all([
					Promise.all(runResponse.findings.map((finding) => fetchFindingDetail(finding.findingId))),
					fetchExperimentRounds(runResponse.run.firstRunId)
						.then((rounds) => ({ rounds, error: '' }))
						.catch((error: unknown) => ({
							rounds: null,
							error: errorMessage(error, '회차 지표를 불러오지 못했습니다.'),
						})),
				]);
				if (!active) return;

				const round = metricsResult.rounds?.rounds.find((item) => item.runId === runId);
				setData({
					run: runResponse.run,
					findings,
					personas: personaList.personas,
					successRate: round?.metrics?.successRate ?? null,
					avgSteps: round?.metrics?.avgSteps ?? null,
					rounds: metricsResult.rounds?.rounds.filter((item) => item.status === 'done') ?? [],
				});
				setMetricsError(metricsResult.error);
				setExpandedId(findings[0]?.findingId ?? null);
				setLoadState('ready');
			} catch (error) {
				if (!active) return;
				setLoadError(errorMessage(error, '진단 결과를 불러오지 못했습니다.'));
				setLoadState('error');
			}
		}

		void Promise.resolve().then(() => {
			if (active) return loadDiagnosis();
		});
		return () => {
			active = false;
		};
	}, [navigate, runIdParam]);

	const visibleFindings = useMemo(() => data?.findings.filter((finding) =>
		(severity === '전체' || finding.severity === severity) &&
		(taxonomy === '전체' || finding.taxonomy === taxonomy),
	) ?? [], [data, severity, taxonomy]);

	const personaNames = useMemo(
		() => new Map(data?.personas.map((persona) => [persona.personaId, persona.name]) ?? []),
		[data],
	);

	if (loadState === 'loading') {
		return <section className="rd-diagnosis"><p className="rd-diagnosis-feedback" role="status">진단 결과를 불러오는 중입니다.</p></section>;
	}

	if (loadState === 'empty') {
		return (
			<section className="rd-diagnosis" aria-labelledby="diagnosis-title">
				<div className="rd-report-title-row"><div className="rd-title-inline"><h1 id="diagnosis-title">Diagnosis</h1><span>— 진단 결과</span></div></div>
				<div className="rd-empty-state"><p>진단 결과가 있는 완료 회차가 없습니다.</p></div>
			</section>
		);
	}

	if (loadState === 'error' || !data) {
		return (
			<section className="rd-diagnosis" aria-labelledby="diagnosis-title">
				<div className="rd-report-title-row"><div className="rd-title-inline"><h1 id="diagnosis-title">Diagnosis</h1><span>— 진단 결과</span></div></div>
				<p className="rd-diagnosis-feedback is-error" role="alert">{loadError || '진단 결과를 불러오지 못했습니다.'}</p>
			</section>
		);
	}

	const successRate = data.successRate == null ? '—' : `${new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 1 }).format(data.successRate)}%`;
	const avgSteps = data.avgSteps == null ? '—' : new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 1 }).format(data.avgSteps);

	return (
		<section className="rd-diagnosis" aria-labelledby="diagnosis-title">
			<div className="rd-report-title-row">
				<div className="rd-title-inline">
					<h1 id="diagnosis-title">Diagnosis</h1>
					<span>— 진단 결과</span>
				</div>
			</div>

			{runOptions.length > 0 && (
				<label className="rd-fixes-run-select">
					<span>실험 선택</span>
					<select value={data.run.firstRunId} onChange={(event) => navigate(`/diagnosis/${event.target.value}`)}>
						{runOptions.map((experiment) => (
							<option key={experiment.firstRunId} value={experiment.firstRunId}>
								#{experiment.firstRunId} · {experiment.projectTitle}
							</option>
						))}
					</select>
				</label>
			)}

			{data.rounds.length > 1 && (
				<label className="rd-fixes-run-select">
					<span>회차 선택</span>
					<select value={runIdParam} onChange={(event) => navigate(`/diagnosis/${event.target.value}`)}>
						{data.rounds.map((item) => (
							<option key={item.runId} value={item.runId}>{item.round}회차</option>
						))}
					</select>
				</label>
			)}

			<div className="rd-diagnosis-run">
				<div>
					<span>실험 {data.run.firstRunId} · {data.run.round}회차</span>
					<strong title={data.run.taskGoal}>{data.run.taskGoal || data.run.projectTitle}</strong>
				</div>
				<span>성공률 {successRate} · 평균 {avgSteps} step</span>
			</div>
			{metricsError && <p className="rd-diagnosis-feedback is-error" role="status">{metricsError}</p>}
			{data.run.improvementCount > 0 && (
				<div className="rd-diagnosis-actions">
					<button
						type="button"
						className="rd-pill-button"
						onClick={() => navigate('/fixes', { state: { runId: Number(runIdParam) } })}
					>
						개선안 확인하기
					</button>
				</div>
			)}

			<div className="rd-friction-toolbar">
				<h2>Friction {visibleFindings.length}건</h2>
				<div>
					<label>심각도:
						<select value={severity} onChange={(event) => {
							const value = event.target.value;
							if (value === '전체' || isFindingSeverity(value)) setSeverity(value);
						}}>
							<option value="전체">전체</option>
							<option value="high">높음</option><option value="medium">중간</option><option value="low">낮음</option>
						</select>
					</label>
					<label>유형:
						<select value={taxonomy} onChange={(event) => {
							const value = event.target.value;
							if (value === '전체' || isFindingTaxonomy(value)) setTaxonomy(value);
						}}>
							<option value="전체">전체</option>
							{Object.entries(taxonomyLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
						</select>
					</label>
				</div>
			</div>

			<div className="rd-friction-list">
				{visibleFindings.map((finding) => {
					const isExpanded = expandedId === finding.findingId;
					const personaCount = new Set(finding.evidence.map((item) => item.personaId)).size;
					return (
						<article className={`rd-friction-card${isExpanded ? ' is-expanded' : ''}`} key={finding.findingId}>
							<button
								className="rd-friction-card-heading"
								type="button"
								aria-expanded={isExpanded}
								onClick={() => setExpandedId(isExpanded ? null : finding.findingId)}
							>
								<span className={`rd-severity-badge rd-severity-badge--${finding.severity}`}>△ {severityLabels[finding.severity]}</span>
								<strong>{taxonomyLabels[finding.taxonomy]}</strong>
								<span className="rd-friction-occurrence">Persona {personaCount}/{data.personas.length} 발생</span>
								<span className="rd-friction-chevron" aria-hidden="true">
									<svg viewBox="0 0 24 24" focusable="false">
										<path d={isExpanded ? 'm6 9 6 6 6-6' : 'm9 18 6-6-6-6'} />
									</svg>
								</span>
							</button>
							{isExpanded && (
								<div className="rd-friction-details">
									<p className="rd-finding-summary">{finding.summary ?? taxonomyLabels[finding.taxonomy]}</p>
									{finding.evidence.map((evidence, index) => {
										const personaName = personaNames.get(evidence.personaId) ?? `Persona ${evidence.personaId}`;
										return (
											<div className="rd-occurrence-row" key={`${evidence.personaId}-${evidence.stepFrom}-${evidence.stepTo}-${index}`}>
												<div className="rd-occurrence-info"><strong>{personaName}</strong></div>
												<span>step {evidence.stepFrom}-{evidence.stepTo}</span>
												<button
													type="button"
													className="rd-evidence-button"
													onClick={() => setEvidenceTarget({ finding, evidence, personaName })}
												>
													근거 보기
												</button>
											</div>
										);
									})}
									{finding.evidence.length === 0 && <p className="rd-diagnosis-feedback">연결된 근거 구간이 없습니다.</p>}
								</div>
							)}
						</article>
					);
				})}
				{visibleFindings.length === 0 && (
					<div className="rd-empty-state">
						<p>{data.findings.length === 0 ? '이 회차에서 찾은 Friction이 없습니다.' : '선택한 조건에 맞는 진단 결과가 없습니다.'}</p>
					</div>
				)}
			</div>

			{evidenceTarget && runIdParam && (
				<EvidenceDialog
					runId={Number(runIdParam)}
					target={evidenceTarget}
					onClose={() => setEvidenceTarget(null)}
				/>
			)}
		</section>
	);
}
