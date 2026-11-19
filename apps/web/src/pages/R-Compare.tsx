import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, UserRoundPlus } from 'lucide-react';
import { patchKindLabels } from '../auth';
import { fetchComparison, fetchExperiments, type Comparison, type Experiment } from './experiments';
import './R-Compare.css';

type ParticipantResult = 'success' | 'failure' | '';
type LoadState = 'loading-experiments' | 'loading-comparison' | 'ready' | 'empty' | 'error';

function errorMessage(error: unknown, fallback: string): string {
	return error instanceof Error ? error.message : fallback;
}

function formatNumber(value: number, maximumFractionDigits = 1): string {
	return new Intl.NumberFormat('ko-KR', { maximumFractionDigits }).format(value);
}

function formatPercent(value: number | null): string {
	return value === null ? '집계 안 됨' : `${formatNumber(value)}%`;
}

function formatMetric(value: number | null, unit = '', maximumFractionDigits = 1): string {
	return value === null ? '집계 안 됨' : `${formatNumber(value, maximumFractionDigits)}${unit}`;
}

function formatChange(value: number | null): string {
	if (value === null) return '비교할 완료 회차가 없습니다.';
	return `${value > 0 ? '+' : ''}${formatNumber(value)}%p`;
}

function metricRows(comparison: Comparison) {
	const before = comparison.before.metrics;
	const after = comparison.after?.metrics ?? null;
	return [
		{ label: 'Task 성공률', before: formatPercent(before.successRate), after: after ? formatPercent(after.successRate) : '완료된 재실험 없음' },
		{ label: '평균 step', before: formatMetric(before.avgSteps, '회'), after: after ? formatMetric(after.avgSteps, '회') : '완료된 재실험 없음' },
		{ label: '평균 되돌아가기', before: formatMetric(before.avgBacktracks, '회'), after: after ? formatMetric(after.avgBacktracks, '회') : '완료된 재실험 없음' },
		{ label: '평균 소요 시간', before: formatMetric(before.avgSeconds, '초'), after: after ? formatMetric(after.avgSeconds, '초') : '완료된 재실험 없음' },
		{ label: '토큰', before: formatMetric(before.tokens, '', 0), after: after ? formatMetric(after.tokens, '', 0) : '완료된 재실험 없음' },
		{ label: '비용', before: before.costUsd === null ? '집계 안 됨' : `$${formatNumber(before.costUsd, 4)}`, after: after ? after.costUsd === null ? '집계 안 됨' : `$${formatNumber(after.costUsd, 4)}` : '완료된 재실험 없음' },
	];
}

export default function RCompare() {
	const [searchParams] = useSearchParams();
	const projectIdValue = searchParams.get('projectId');
	const parsedProjectId = projectIdValue && /^\d+$/.test(projectIdValue) ? Number(projectIdValue) : null;
	const projectId = parsedProjectId !== null && Number.isSafeInteger(parsedProjectId) && parsedProjectId > 0 ? parsedProjectId : null;
	const [experiments, setExperiments] = useState<Experiment[]>([]);
	const [firstRunId, setFirstRunId] = useState<number | null>(null);
	const [comparison, setComparison] = useState<Comparison | null>(null);
	const [loadState, setLoadState] = useState<LoadState>('loading-experiments');
	const [loadError, setLoadError] = useState('');
	const [participantResults, setParticipantResults] = useState<ParticipantResult[]>([]);
	const [notice, setNotice] = useState('');

	useEffect(() => {
		let active = true;
		fetchExperiments()
			.then((items) => {
				if (!active) return;
				const available = items.filter((item) => item.hasResult);
				setExperiments(available);
				if (available.length === 0) {
					setLoadState('empty');
					return;
				}
				setFirstRunId((current) => current && available.some((item) => item.firstRunId === current)
					? current
					: available[0].firstRunId);
			})
			.catch((error: unknown) => {
				if (!active) return;
				setLoadError(errorMessage(error, '실험 목록을 불러오지 못했습니다.'));
				setLoadState('error');
			});
		return () => {
			active = false;
		};
	}, []);

	useEffect(() => {
		if (firstRunId === null) return;
		let active = true;
		fetchComparison(firstRunId)
			.then((result) => {
				if (!active) return;
				setComparison(result);
				setLoadState('ready');
			})
			.catch((error: unknown) => {
				if (!active) return;
				setLoadError(errorMessage(error, '비교 결과를 불러오지 못했습니다.'));
				setLoadState('error');
			});
		return () => {
			active = false;
		};
	}, [firstRunId]);

	const recordedResults = participantResults.filter((result) => result !== '');
	const realSuccesses = recordedResults.filter((result) => result === 'success').length;
	const realSuccessRate = recordedResults.length ? Math.round((realSuccesses / recordedResults.length) * 100) : null;

	const addParticipant = () => {
		setParticipantResults((current) => [...current, '']);
		setNotice('참가자가 추가되었습니다. 결과를 선택해 주세요.');
	};

	const updateParticipant = (index: number, result: ParticipantResult) => {
		setParticipantResults((current) => current.map((item, itemIndex) => itemIndex === index ? result : item));
	};

	if (loadState === 'loading-experiments' || loadState === 'loading-comparison') {
		return <section className="rd-compare"><p className="rd-compare-feedback" role="status">비교 데이터를 불러오는 중입니다.</p></section>;
	}

	if (loadState === 'empty') {
		return (
			<section className="rd-compare" aria-labelledby="compare-title">
				<header className="rd-compare-heading"><h1 id="compare-title">Compare</h1></header>
				<div className="rd-compare-empty">비교할 완료 실험이 없습니다.</div>
			</section>
		);
	}

	if (loadState === 'error' || !comparison || firstRunId === null) {
		return (
			<section className="rd-compare" aria-labelledby="compare-title">
				<header className="rd-compare-heading"><h1 id="compare-title">Compare</h1></header>
				<p className="rd-compare-feedback is-error" role="alert">{loadError || '비교 결과를 불러오지 못했습니다.'}</p>
			</section>
		);
	}

	const beforeRate = comparison.before.metrics.successRate;
	const afterRate = comparison.after?.metrics.successRate ?? null;
	const rateChange = beforeRate !== null && afterRate !== null ? afterRate - beforeRate : null;
	const humanGap = afterRate !== null && realSuccessRate !== null ? afterRate - realSuccessRate : null;

	return (
		<section className="rd-compare" aria-labelledby="compare-title">
			<header className="rd-compare-heading">
				<div>
					<p className="rd-compare-eyebrow">{comparison.experiment.projectTitle}</p>
					<h1 id="compare-title">실험 결과 비교</h1>
					<p className="rd-compare-task">{comparison.experiment.taskGoal}</p>
					{projectId !== null && <p className="rd-compare-eyebrow">프로젝트 #{projectId}에서 이동 · 목록은 내 전체 실험 기준</p>}
				</div>
			</header>

			<section className="rd-compare-selector" aria-label="비교 대상 실험">
				<label htmlFor="compare-experiment">비교 대상 실험</label>
				<select
					id="compare-experiment"
					value={firstRunId}
					onChange={(event) => {
						setFirstRunId(Number(event.target.value));
						setComparison(null);
						setLoadError('');
						setLoadState('loading-comparison');
						setParticipantResults([]);
						setNotice('');
					}}
				>
					{experiments.map((item) => (
						<option key={item.firstRunId} value={item.firstRunId}>
							실험 #{item.firstRunId} · {item.projectTitle} · {item.taskGoal}
						</option>
					))}
				</select>
				<span>Before #{comparison.before.runId}{comparison.after ? ` · After ${comparison.after.round}회차` : ' · 재실험 없음'}</span>
			</section>

			<div className="rd-compare-metrics">
				<article className="rd-compare-card">
					<div className="rd-compare-card-label"><span>AI Before 성공률</span><span>최초 회차</span></div>
					<div className="rd-compare-metric"><strong>{formatPercent(beforeRate)}</strong><span>run #{comparison.before.runId}</span></div>
				</article>
				<article className="rd-compare-card">
					<div className="rd-compare-card-label"><span>AI After 성공률</span><span>마지막 완료 회차</span></div>
					<div className="rd-compare-metric"><strong>{comparison.after ? formatPercent(afterRate) : '—'}</strong><span>{comparison.after ? `run #${comparison.after.runId}` : '완료된 재실험 없음'}</span></div>
				</article>
				<article className="rd-compare-card">
					<div className="rd-compare-card-label"><span>실사용자 입력 성공률</span><span>현재 화면에만 저장</span></div>
					<div className="rd-compare-metric"><strong>{realSuccessRate === null ? '—' : `${realSuccessRate}%`}</strong><span>{realSuccesses}/{recordedResults.length} 명</span></div>
				</article>
			</div>

			<div className="rd-compare-panels">
				<section className="rd-compare-card rd-compare-participants">
					<div className="rd-compare-section-title">
						<div><h2>실사용자 결과 입력</h2><p>예시 기능입니다. 참가자별 태스크 성공 여부를 임시로 기록합니다.</p></div>
						<button className="rd-compare-add" type="button" onClick={addParticipant} aria-label="참가자 추가" title="참가자 추가">
							<UserRoundPlus size={16} aria-hidden="true" /><Plus size={11} aria-hidden="true" />
						</button>
					</div>
					<div className="rd-compare-participant-list">
						{participantResults.map((result, index) => (
							<label className="rd-compare-participant" key={index}>
								<span>참가자 {index + 1}</span>
								<select aria-label={`참가자 ${index + 1} 결과`} value={result} onChange={(event) => updateParticipant(index, event.target.value as ParticipantResult)}>
									<option value="">결과 선택</option>
									<option value="success">성공</option>
									<option value="failure">실패</option>
								</select>
							</label>
						))}
						{participantResults.length === 0 && <p className="rd-compare-hint">참가자를 추가해 결과를 입력하세요.</p>}
					</div>
					<p className="rd-compare-hint">입력 결과는 서버에 저장되지 않으며 실험을 바꾸면 초기화됩니다.</p>
				</section>

				<section className="rd-compare-card rd-compare-rates">
					<div className="rd-compare-section-title">
						<div><h2>성공률 비교</h2><p>AI Before/After와 이 화면의 실사용자 입력</p></div>
					</div>
					<div className="rd-compare-bar-row">
						<strong>AI Before</strong>
						<div className="rd-compare-bar-track"><span className="is-ai" style={{ width: `${beforeRate ?? 0}%` }}>{beforeRate !== null && <b>{formatPercent(beforeRate)}</b>}</span></div>
					</div>
					<div className="rd-compare-bar-row">
						<strong>AI After</strong>
						<div className="rd-compare-bar-track"><span className="is-after" style={{ width: `${afterRate ?? 0}%` }}>{afterRate !== null && <b>{formatPercent(afterRate)}</b>}</span></div>
					</div>
					<div className="rd-compare-bar-row">
						<strong>실사용자</strong>
						<div className="rd-compare-bar-track"><span className="is-human" style={{ width: `${realSuccessRate ?? 0}%` }}>{realSuccessRate !== null && <b>{realSuccessRate}%</b>}</span></div>
					</div>
					<p className="rd-compare-hint">AI 변화: {formatChange(rateChange)} · AI After와 입력 결과 차이: {formatChange(humanGap)}</p>
				</section>
			</div>

			<section className="rd-compare-card rd-compare-detail">
				<div className="rd-compare-section-title">
					<div><h2>회차별 실제 집계 지표</h2><p>값이 없는 지표는 집계 안 됨으로 표시합니다.</p></div>
				</div>
				<div className="rd-compare-table-wrap">
					<table className="rd-compare-table">
						<thead><tr><th scope="col">지표</th><th scope="col">Before · 최초 회차</th><th scope="col">After · 마지막 완료 회차</th></tr></thead>
						<tbody>
							{metricRows(comparison).map((row) => (
								<tr key={row.label}><th scope="row">{row.label}</th><td>{row.before}</td><td>{row.after}</td></tr>
							))}
						</tbody>
					</table>
				</div>
			</section>

			<section className="rd-compare-card rd-compare-patches">
				<div className="rd-compare-section-title">
					<div><h2>회차별 적용 개선안</h2><p>비교 API가 반환한 실제 패치 적용 결과</p></div>
				</div>
				{comparison.patches.length === 0
					? <p className="rd-compare-hint">기록된 개선안 적용 내역이 없습니다.</p>
					: (
						<ul className="rd-compare-patch-list">
							{comparison.patches.map((patch, index) => (
								<li key={`${patch.round}-${patch.patchKind}-${index}`}>
									<span>{patch.round}회차 · {patchKindLabels[patch.patchKind]}</span>
									<strong className={patch.applied ? 'is-applied' : 'is-not-applied'}>{patch.applied ? '적용됨' : '미적용'}</strong>
								</li>
							))}
						</ul>
					)}
			</section>

			{notice && <p className="rd-compare-notice" role="status">{notice}<button type="button" onClick={() => setNotice('')} aria-label="알림 닫기">×</button></p>}
			<p className="rd-compare-disclaimer">실험 지표와 적용 개선안은 서버에서 불러옵니다. 실사용자 결과 입력은 이 화면 안에서만 유지됩니다.</p>
		</section>
	);
}
