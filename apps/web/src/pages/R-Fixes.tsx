import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
	decideImprovement,
	getImprovementDetail,
	getRunImprovements,
	type ImprovementDecision,
	type ImprovementDetail,
	type ImprovementList,
	decisionLabels,
	patchKindLabels,
} from '../auth';
import { fetchExperiments, type Experiment } from './experiments';

function readRunIdFromState(state: unknown): number | null {
	if (typeof state !== 'object' || state === null || !('runId' in state)) return null;
	return typeof state.runId === 'number' && Number.isSafeInteger(state.runId) && state.runId > 0
		? state.runId
		: null;
}

function formatDate(value: string): string {
	const date = new Date(value);
	return Number.isNaN(date.getTime())
		? value
		: new Intl.DateTimeFormat('ko-KR', { dateStyle: 'short', timeStyle: 'short' }).format(date);
}

export default function RFixes() {
	const navigate = useNavigate();
	const location = useLocation();
	const requestedRunId = readRunIdFromState(location.state);
	const [experiments, setExperiments] = useState<Experiment[]>([]);
	const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
	const [experimentsLoading, setExperimentsLoading] = useState(true);
	const [experimentsError, setExperimentsError] = useState('');
	const [improvementList, setImprovementList] = useState<ImprovementList | null>(null);
	const [improvementsRunId, setImprovementsRunId] = useState<number | null>(null);
	const [improvementsError, setImprovementsError] = useState('');
	const [selectedImprovementId, setSelectedImprovementId] = useState<number | null>(null);
	const [detail, setDetail] = useState<ImprovementDetail | null>(null);
	const [detailId, setDetailId] = useState<number | null>(null);
	const [detailError, setDetailError] = useState('');
	const [note, setNote] = useState('');
	const [busy, setBusy] = useState(false);
	const [notice, setNotice] = useState('');

	useEffect(() => {
		let cancelled = false;
		fetchExperiments()
			.then((items) => {
				if (cancelled) return;
				const completed = items.filter((experiment) => experiment.hasResult);
				setExperiments(completed);
				setSelectedRunId(
					requestedRunId ??
					completed[0]?.firstRunId ??
					null,
				);
				setExperimentsError('');
			})
			.catch((error: unknown) => {
				if (!cancelled) setExperimentsError(error instanceof Error ? error.message : '완료된 실험을 불러오지 못했습니다.');
			})
			.finally(() => {
				if (!cancelled) setExperimentsLoading(false);
			});
		return () => {
			cancelled = true;
		};
	}, [requestedRunId]);

	useEffect(() => {
		if (selectedRunId === null) return;
		let cancelled = false;
		getRunImprovements(selectedRunId)
			.then((result) => {
				if (cancelled) return;
				setImprovementList(result);
				setImprovementsRunId(selectedRunId);
				setSelectedImprovementId((current) =>
					result.improvements.some((item) => item.improvementId === current)
						? current
						: result.improvements[0]?.improvementId ?? null,
				);
				setImprovementsError('');
			})
			.catch((error: unknown) => {
				if (!cancelled) {
					setImprovementList(null);
					setImprovementsRunId(selectedRunId);
					setSelectedImprovementId(null);
					setImprovementsError(error instanceof Error ? error.message : '개선안 목록을 불러오지 못했습니다.');
				}
			});
		return () => {
			cancelled = true;
		};
	}, [selectedRunId]);

	useEffect(() => {
		if (selectedImprovementId === null) return;
		let cancelled = false;
		getImprovementDetail(selectedImprovementId)
			.then((result) => {
				if (cancelled) return;
				setDetail(result);
				setDetailId(selectedImprovementId);
				setDetailError('');
			})
			.catch((error: unknown) => {
				if (!cancelled) {
					setDetail(null);
					setDetailId(selectedImprovementId);
					setDetailError(error instanceof Error ? error.message : '개선안 상세를 불러오지 못했습니다.');
				}
			});
		return () => {
			cancelled = true;
		};
	}, [selectedImprovementId]);

	const completedRuns = useMemo(() => experiments, [experiments]);
	const selectedExperiment = completedRuns.find((experiment) => experiment.firstRunId === selectedRunId) ?? null;
	const selectedFirstRunId = selectedExperiment?.firstRunId ?? improvementList?.run.firstRunId ?? null;
	const selectedRound = selectedExperiment?.round ?? improvementList?.run.round ?? null;
	const selectedSummary = improvementList?.improvements.find((item) => item.improvementId === selectedImprovementId) ?? null;
	const listLoading = selectedRunId !== null && improvementsRunId !== selectedRunId;
	const detailLoading = selectedImprovementId !== null && detailId !== selectedImprovementId;
	const canDecide = Boolean(improvementList?.run.awaitingApproval && detail?.awaitingApproval && detail.approval === null);

	const changeRun = (runId: number) => {
		setSelectedRunId(runId);
		setImprovementList(null);
		setImprovementsRunId(null);
		setSelectedImprovementId(null);
		setDetail(null);
		setDetailId(null);
		setNote('');
		setNotice('');
	};

	const handleDecision = async (decision: ImprovementDecision) => {
		if (!selectedRunId || !detail || !canDecide || busy) return;
		setBusy(true);
		setDetailError('');
		setNotice('');
		try {
			const result = await decideImprovement(selectedRunId, detail.improvementId, decision, note);
			if (decision === 'approve') {
				if (selectedFirstRunId !== null) navigate(`/monitor/${selectedFirstRunId}`);
				return;
			}

			const [nextList, nextDetail] = await Promise.all([
				getRunImprovements(selectedRunId),
				getImprovementDetail(detail.improvementId),
			]);
			setImprovementList(nextList);
			setImprovementsRunId(selectedRunId);
			setDetail(nextDetail);
			setDetailId(nextDetail.improvementId);
			setNotice(`개선안을 반려했습니다. 결정 #${result.approvalId}`);
		} catch (error: unknown) {
			setDetailError(error instanceof Error ? error.message : '개선안 결정을 저장하지 못했습니다.');
		} finally {
			setBusy(false);
		}
	};

	return (
		<section className="rd-fixes" aria-labelledby="fixes-title">
			<div className="rd-fixes-main">
				<div className="rd-report-title-row">
					<div className="rd-title-inline"><h1 id="fixes-title">Fixes</h1><span>— 개선안</span></div>
					{selectedFirstRunId !== null && selectedRound !== null && (
						<button className="rd-run-chip" type="button" onClick={() => navigate(`/monitor/${selectedFirstRunId}`)}>
							실험 #{selectedFirstRunId} · {selectedRound}회차
						</button>
					)}
				</div>

				<label className="rd-fixes-run-select">
					<span>완료된 실험</span>
					<select
						value={selectedRunId ?? ''}
						disabled={experimentsLoading || (completedRuns.length === 0 && selectedRunId === null)}
						onChange={(event) => {
							const value = Number(event.target.value);
							if (Number.isSafeInteger(value) && value > 0) changeRun(value);
						}}
					>
						{selectedRunId !== null && !completedRuns.some((experiment) => experiment.firstRunId === selectedRunId) && (
							<option value={selectedRunId}>
								#{improvementList?.run.firstRunId ?? selectedRunId} · {improvementList?.run.projectTitle ?? '선택한 회차'}
								{improvementList ? ` · ${improvementList.run.round}회차` : ''}
							</option>
						)}
						{completedRuns.length === 0 && selectedRunId === null && <option value="">완료된 실험 없음</option>}
						{completedRuns.map((experiment) => (
							<option key={experiment.firstRunId} value={experiment.firstRunId}>
								#{experiment.firstRunId} · {experiment.projectTitle} · {formatDate(experiment.createdAt)}
							</option>
						))}
					</select>
				</label>

				{experimentsLoading && <p className="rd-fixes-feedback" role="status">완료된 실험을 불러오는 중입니다.</p>}
				{experimentsError && <p className="rd-fixes-feedback is-error" role="alert">{experimentsError}</p>}
				{notice && <p className="rd-fixes-feedback" role="status">{notice}</p>}
				{detailError && <p className="rd-fixes-feedback is-error" role="alert">{detailError}</p>}
				{improvementsError && <p className="rd-fixes-feedback is-error" role="alert">{improvementsError}</p>}

				{!experimentsLoading && !experimentsError && completedRuns.length === 0 && selectedRunId === null && (
					<div className="rd-empty-state"><p>개선안을 확인할 완료된 실험이 없습니다.</p><button type="button" onClick={() => navigate('/monitor')}>실험 모니터로 이동</button></div>
				)}
				{listLoading && <p className="rd-fixes-feedback" role="status">개선안 목록을 불러오는 중입니다.</p>}
				{!listLoading && improvementList && improvementList.improvements.length === 0 && (
					<div className="rd-empty-state"><p>이 회차에는 조회할 개선안이 없습니다.</p></div>
				)}

				{detailLoading && <p className="rd-fixes-feedback" role="status">개선안 상세를 불러오는 중입니다.</p>}
				{detail && detailId === selectedImprovementId && (
					<article className="rd-fixes-detail">
						<header>
							<div><span>개선안 {detail.optionNo}</span><h2>{patchKindLabels[detail.patchKind]}</h2></div>
							<span className={`rd-fixes-decision${detail.approval ? ` is-${detail.approval.decision}` : ''}`}>
								{detail.approval ? decisionLabels[detail.approval.decision] : canDecide ? '결정 대기' : '결정 불가'}
							</span>
						</header>
						<div className="rd-fixes-copy-grid">
							<section><h3>개선 근거</h3><p>{detail.rationale || '제공된 근거가 없습니다.'}</p></section>
							<section><h3>예상 효과</h3><p>{detail.expectedEffect || '예상 효과가 제공되지 않았습니다.'}</p></section>
							<section><h3>구현 비용</h3><p>{detail.fixCost ?? '추정 없음'}</p></section>
						</div>
						<section className="rd-fixes-data"><h3>적용 패치</h3><pre>{JSON.stringify(detail.patch, null, 2)}</pre></section>
						<section className="rd-fixes-data">
							<h3>관련 진단 ({detail.findings.length})</h3>
							{detail.findings.length === 0 ? <p>연결된 진단이 없습니다.</p> : (
								<ul>{detail.findings.map((finding) => (
									<li key={finding.findingId}><strong>{finding.taxonomy} · {finding.severity}</strong><span>{finding.summary}</span></li>
								))}</ul>
							)}
						</section>
						{detail.approval && (
							<p className="rd-fixes-decision-note">
								{detail.approval.note || '결정 사유 없음'} · {formatDate(detail.approval.decidedAt)}
							</p>
						)}
						{canDecide && (
							<div className="rd-fixes-decision-form">
								<label>결정 사유 (선택)<textarea value={note} onChange={(event) => setNote(event.target.value)} rows={3} maxLength={1000} /></label>
								<div className="rd-fixes-actions">
									<button className="rd-dark-pill" type="button" disabled={busy} onClick={() => void handleDecision('approve')}>
										{busy ? '처리 중…' : '승인 및 다음 회차 실행'}
									</button>
									<button className="rd-pill-button" type="button" disabled={busy} onClick={() => void handleDecision('reject')}>반려</button>
								</div>
							</div>
						)}
					</article>
				)}
			</div>

			<aside className="rd-suggestion-panel" aria-label="개선안 목록">
				<h2>개선안 목록</h2>
				{listLoading && <p className="rd-fixes-feedback" role="status">불러오는 중입니다.</p>}
				{improvementList?.improvements.map((improvement) => (
					<button
						className={`rd-suggestion-card${selectedImprovementId === improvement.improvementId ? ' is-selected' : ''}`}
						type="button"
						key={improvement.improvementId}
						onClick={() => {
							setSelectedImprovementId(improvement.improvementId);
							setDetail(null);
							setDetailId(null);
							setDetailError('');
							setNote('');
							setNotice('');
						}}
					>
						<span className="rd-suggestion-id">안 {improvement.optionNo} · #{improvement.improvementId}</span>
						<span className="rd-suggestion-icon" aria-hidden="true">{improvement.optionNo}</span>
						<strong>{patchKindLabels[improvement.patchKind]}</strong>
						<small>구현 비용: {improvement.fixCost ?? '추정 없음'} · {improvement.decision ? decisionLabels[improvement.decision] : '미결정'}</small>
					</button>
				))}
				{improvementList && improvementList.improvements.length > 0 && (
					<p className="rd-suggestion-selected">
						{improvementList.run.projectTitle} · {improvementList.run.taskGoal}
					</p>
				)}
				{selectedSummary && <span className="sr-only">선택된 개선안 {selectedSummary.optionNo}</span>}
			</aside>
		</section>
	);
}
