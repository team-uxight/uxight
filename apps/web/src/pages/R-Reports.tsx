import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { decisionLabels, getRunImprovements, patchKindLabels, type ImprovementList } from '../auth';
import { fetchExperimentRounds, fetchExperiments, type Experiment, type ExperimentRound } from './experiments';
import { fetchFindingDetail, fetchRunFindings, severityLabels, taxonomyLabels, type FindingDetail, type RunFindings } from './findings';
import { fetchRunPersonas, type RunPersona } from './runLogs';

const NOT_AGGREGATED = '집계 안 됨';

type Section<T> = { data: T | null; error: string };

type ReportData = {
	rounds: ExperimentRound[];
	finalRound: ExperimentRound;
	run: RunFindings['run'];
	findings: Section<FindingDetail[]>;
	personas: Section<RunPersona[]>;
	improvements: Section<ImprovementList>;
};

function errorMessage(error: unknown, fallback: string): string {
	return error instanceof Error ? error.message : fallback;
}

async function settle<T>(task: () => Promise<T>, fallback: string): Promise<Section<T>> {
	try {
		return { data: await task(), error: '' };
	} catch (error) {
		return { data: null, error: errorMessage(error, fallback) };
	}
}

const fixCostLabels: Record<string, string> = { low: '낮음', medium: '보통', high: '높음' };

function formatFixCost(value: string | null): string {
	if (!value) return '추정 없음';
	return fixCostLabels[value.toLowerCase()] ?? value;
}

function formatPercent(value: number | null | undefined): string {
	return value == null ? NOT_AGGREGATED : `${new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 1 }).format(value)}%`;
}

function formatDuration(seconds: number | null | undefined): string {
	if (seconds == null) return NOT_AGGREGATED;
	const total = Math.round(seconds);
	return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

export default function RReports() {
	const { firstRunId: firstRunIdParam } = useParams();
	const navigate = useNavigate();
	const [loadState, setLoadState] = useState<'loading' | 'ready' | 'empty' | 'error'>('loading');
	const [loadError, setLoadError] = useState('');
	const [data, setData] = useState<ReportData | null>(null);
	const [experiments, setExperiments] = useState<Experiment[]>([]);

	useEffect(() => {
		let active = true;
		fetchExperiments()
			.then((items) => {
				if (active) setExperiments(items.filter((experiment) => experiment.hasResult));
			})
			.catch(() => undefined);
		return () => {
			active = false;
		};
	}, []);

	useEffect(() => {
		let active = true;

		async function loadReport() {
			setLoadState('loading');
			setLoadError('');
			setData(null);

			try {
				if (!firstRunIdParam) {
					const experiments = await fetchExperiments();
					if (!active) return;
					const latest = experiments.find((experiment) => experiment.hasResult);
					if (!latest) {
						setLoadState('empty');
						return;
					}
					navigate(`/reports/${latest.firstRunId}`, { replace: true });
					return;
				}

				const firstRunId = Number(firstRunIdParam);
				if (!Number.isSafeInteger(firstRunId) || firstRunId <= 0) {
					throw new Error('올바르지 않은 실험 ID입니다.');
				}

				const { rounds } = await fetchExperimentRounds(firstRunId);
				const finalRound = rounds
					.filter((round) => round.status === 'done')
					.sort((left, right) => right.round - left.round)[0];
				if (!finalRound) {
					if (active) setLoadState('empty');
					return;
				}

				const runId = finalRound.runId;
				const [runFindings, personas, improvements] = await Promise.all([
					fetchRunFindings(runId),
					settle(async () => (await fetchRunPersonas(runId)).personas, 'Persona 정보를 불러오지 못했습니다.'),
					settle(() => getRunImprovements(runId), '개선안을 불러오지 못했습니다.'),
				]);
				const findings = await settle(
					() => Promise.all(runFindings.findings.map((finding) => fetchFindingDetail(finding.findingId))),
					'Friction 상세를 불러오지 못했습니다.',
				);
				if (!active) return;
				setData({ rounds, finalRound, run: runFindings.run, findings, personas, improvements });
				setLoadState('ready');
			} catch (error) {
				if (!active) return;
				setLoadError(errorMessage(error, '리포트를 불러오지 못했습니다.'));
				setLoadState('error');
			}
		}

		void Promise.resolve().then(() => {
			if (active) return loadReport();
		});
		return () => {
			active = false;
		};
	}, [firstRunIdParam, navigate]);

	if (loadState === 'loading') {
		return <section className="rd-report"><p className="rd-diagnosis-feedback" role="status">리포트를 불러오는 중입니다.</p></section>;
	}

	if (loadState === 'empty') {
		return (
			<section className="rd-report" aria-labelledby="report-title">
				<div className="rd-report-banner"><h1 id="report-title">최종 UX 평가 리포트</h1></div>
				<div className="rd-empty-state"><p>리포트를 만들 수 있는 완료 회차가 없습니다.</p></div>
			</section>
		);
	}

	if (loadState === 'error' || !data) {
		return (
			<section className="rd-report" aria-labelledby="report-title">
				<div className="rd-report-banner"><h1 id="report-title">최종 UX 평가 리포트</h1></div>
				<p className="rd-diagnosis-feedback is-error" role="alert">{loadError || '리포트를 불러오지 못했습니다.'}</p>
			</section>
		);
	}

	const { rounds, finalRound, run, findings, personas, improvements } = data;
	const metrics = finalRound.metrics;
	const personaTotal = personas.data?.length ?? 0;
	const runOptions = experiments.some((experiment) => experiment.firstRunId === run.firstRunId)
		? experiments
		: [...experiments, { firstRunId: run.firstRunId, projectTitle: run.projectTitle, createdAt: '' } as Experiment];

	return (
		<section className="rd-report" aria-labelledby="report-title">
			<div className="rd-report-banner">
				<h1 id="report-title">실험 {run.firstRunId} 최종 UX 평가 리포트</h1>
				<button type="button" onClick={() => window.print()}>▤ PDF 내보내기</button>
			</div>

			<label className="rd-fixes-run-select">
				<span>실험 선택</span>
				<select value={run.firstRunId} onChange={(event) => navigate(`/reports/${event.target.value}`)}>
					{runOptions.map((experiment) => (
						<option key={experiment.firstRunId} value={experiment.firstRunId}>
							#{experiment.firstRunId} · {experiment.projectTitle}
						</option>
					))}
				</select>
			</label>

			<div className="rd-report-overview">
				<section className="rd-report-card">
					<h2>실험 요약 <span>{run.projectTitle} · 총 {rounds.filter((round) => round.status === 'done').length}회차 완료 · {finalRound.round}회차 기준</span></h2>
					<div className="rd-score-grid">
						<article><span className="rd-score-icon">✓</span><div><small>task 성공률</small><strong>{formatPercent(metrics?.successRate)}</strong></div></article>
						<article><span className="rd-score-icon">◷</span><div><small>평균 소요 시간</small><strong>{formatDuration(metrics?.avgSeconds)}</strong></div></article>
					</div>
					<div className="rd-round-box">
						<table className="rd-round-table">
							<caption>회차별 결과</caption>
							<thead>
								<tr><th scope="col">회차</th><th scope="col">성공률</th><th scope="col">평균 step</th><th scope="col">평균 소요 시간</th></tr>
							</thead>
							<tbody>
								{[...rounds].sort((left, right) => left.round - right.round).map((round) => (
									<tr key={round.runId}>
										<th scope="row">{round.round}회차{round.runId === finalRound.runId ? ' (최종)' : ''}</th>
										<td>{formatPercent(round.metrics?.successRate)}</td>
										<td>{round.metrics?.avgSteps == null ? '—' : new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 1 }).format(round.metrics.avgSteps)}</td>
										<td>{formatDuration(round.metrics?.avgSeconds)}</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				</section>

				<section className="rd-report-card rd-friction-report">
					<h2>주요 UX 마찰 지점 (Friction Points)</h2>
					{findings.error && <p className="rd-diagnosis-feedback is-error" role="alert">{findings.error}</p>}
					{findings.data && findings.data.length === 0 && <p>이 회차에서 찾은 Friction이 없습니다.</p>}
					{findings.data && findings.data.length > 0 && (
						<div className="rd-friction-point-grid">
							{findings.data.map((finding) => {
								const observed = new Set(finding.evidence.map((item) => item.personaId)).size;
								return (
									<div key={finding.findingId}>
										<span className={`rd-point-severity rd-point-severity--${finding.severity}`}>{severityLabels[finding.severity]}</span>
										<strong>{taxonomyLabels[finding.taxonomy]}{finding.summary ? ` — ${finding.summary}` : ''}</strong>
										<small>{personaTotal > 0 ? `Persona ${observed}/${personaTotal} 발생` : `${observed}개 Persona에서 관찰`}</small>
									</div>
								);
							})}
						</div>
					)}
				</section>
			</div>

			<section className="rd-report-card rd-action-plan">
				<h2>AI 개선 제안 및 액션 플랜</h2>
				{improvements.error && <p className="rd-diagnosis-feedback is-error" role="alert">{improvements.error}</p>}
				{improvements.data && improvements.data.improvements.length === 0 && <p>이 회차에는 조회할 개선안이 없습니다.</p>}
				{improvements.data && improvements.data.improvements.length > 0 && (
					<ol>
						{improvements.data.improvements.map((item) => (
							<li key={item.improvementId}>
								<strong>개선안 {item.optionNo} · {patchKindLabels[item.patchKind]}</strong>
								<span>채택 시 구현 비용: <b>{formatFixCost(item.fixCost)}</b> · {item.decision ? decisionLabels[item.decision] : '미결정'}</span>
							</li>
						))}
					</ol>
				)}
			</section>
		</section>
	);
}
