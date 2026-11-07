import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, UserRoundPlus } from 'lucide-react';
import './R-Compare.css';

type ParticipantResult = 'success' | 'failure' | '';

const experiments = [
	{ id: '12', title: '장학금 신청 방법 찾기', aiSuccesses: 4, aiTotal: 5, stages: ['메인', '메뉴 탐색', '검색', '신청서', '제출'] },
	{ id: '11', title: '수강 신청 내역 확인하기', aiSuccesses: 4, aiTotal: 5, stages: ['로그인', '메뉴 탐색', '수강 조회', '시간표', '완료'] },
	{ id: '10', title: '학사 일정 확인하기', aiSuccesses: 2, aiTotal: 5, stages: ['메인', '학사 안내', '일정 검색', '상세 보기', '완료'] },
];

const initialResults: ParticipantResult[] = ['success', 'success', 'failure'];

export default function RCompare() {
	const [searchParams] = useSearchParams();
	const [experimentId, setExperimentId] = useState(experiments[0].id);
	const [participantResults, setParticipantResults] = useState(initialResults);
	const [notice, setNotice] = useState('');
	const projectIdValue = searchParams.get('projectId');
	const projectId = projectIdValue && /^\d+$/.test(projectIdValue) ? Number(projectIdValue) : null;
	const hasProjectContext = projectId !== null && Number.isSafeInteger(projectId) && projectId > 0;
	const experiment = experiments.find((item) => item.id === experimentId) ?? experiments[0];
	const aiSuccessRate = Math.round((experiment.aiSuccesses / experiment.aiTotal) * 100);
	const recordedResults = participantResults.filter((result) => result !== '');
	const realSuccesses = recordedResults.filter((result) => result === 'success').length;
	const realSuccessRate = recordedResults.length ? Math.round((realSuccesses / recordedResults.length) * 100) : null;
	const predictionGap = realSuccessRate === null ? null : aiSuccessRate - realSuccessRate;
	const aiMarkers: number[] = experiment.stages.map((_, index) => index).filter((index) => index === 1 || index === 2);
	const participantMarkers: number[] = experiment.stages.map((_, index) => index).filter((index) => index === 2);

	const updateParticipant = (index: number, result: ParticipantResult) => {
		setParticipantResults((current) => current.map((item, itemIndex) => itemIndex === index ? result : item));
	};

	const addParticipant = () => {
		setParticipantResults((current) => [...current, '']);
		setNotice('참가자가 추가되었습니다. 결과를 선택해 주세요.');
	};

	return (
		<section className="rd-compare" aria-labelledby="compare-title">
			<header className="rd-compare-heading">
				<div>
					<p className="rd-compare-eyebrow">실험 결과 분석</p>
					<h1 id="compare-title">Compare</h1>
					{hasProjectContext && <p className="rd-compare-eyebrow">프로젝트 #{projectId}에서 이동 · 비교 데이터는 예시</p>}
				</div>
			</header>

			<section className="rd-compare-selector" aria-label="비교 대상 실험">
				<label htmlFor="compare-experiment">비교 대상 실험</label>
				<select id="compare-experiment" value={experimentId} onChange={(event) => setExperimentId(event.target.value)}>
					{experiments.map((item) => (
						<option key={item.id} value={item.id}>실험 #{item.id} {item.title}</option>
					))}
				</select>
				<span>AI 결과 성공 {experiment.aiSuccesses}/{experiment.aiTotal}</span>
			</section>

			<div className="rd-compare-metrics">
				<article className="rd-compare-card">
					<div className="rd-compare-card-label"><span>AI 예측 성공률</span><span>AI 분석</span></div>
					<div className="rd-compare-metric"><strong>{aiSuccessRate}%</strong><span>{experiment.aiSuccesses}/{experiment.aiTotal} 명</span></div>
				</article>
				<article className="rd-compare-card">
					<div className="rd-compare-card-label"><span>실사용자 성공률</span><span>입력 결과</span></div>
					<div className="rd-compare-metric"><strong>{realSuccessRate === null ? '—' : `${realSuccessRate}%`}</strong><span>{realSuccesses}/{recordedResults.length} 명</span></div>
				</article>
				<article className="rd-compare-card">
					<div className="rd-compare-card-label"><span>예측 오차</span><span>AI와 실사용자 차이</span></div>
					<div className="rd-compare-metric"><strong>{predictionGap === null ? '—' : `${Math.abs(predictionGap)}%p`}</strong><span>{predictionGap === null ? '실사용자 결과 입력 필요' : predictionGap > 0 ? 'AI가 높게 예측' : predictionGap < 0 ? '실사용자가 높게 기록' : '예측 일치'}</span></div>
				</article>
			</div>

			<div className="rd-compare-panels">
				<section className="rd-compare-card rd-compare-participants">
					<div className="rd-compare-section-title">
						<div><h2>실사용자 결과 입력</h2><p>참가자별 태스크 성공 여부를 기록합니다.</p></div>
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
					</div>
					<p className="rd-compare-hint">결과를 입력하면 비교 지표가 바로 갱신됩니다.</p>
				</section>

				<section className="rd-compare-card rd-compare-rates">
					<div className="rd-compare-section-title">
						<div><h2>성공률 비교</h2><p>AI 예측과 실사용자 기록</p></div>
					</div>
					<div className="rd-compare-bar-row">
						<strong>AI 예측</strong>
						<div className="rd-compare-bar-track"><span className="is-ai" style={{ width: `${aiSuccessRate}%` }}><b>{aiSuccessRate}%</b></span></div>
					</div>
					<div className="rd-compare-bar-row">
						<strong>실사용자</strong>
						<div className="rd-compare-bar-track">						<span className="is-human" style={{ width: `${realSuccessRate ?? 0}%` }}>{realSuccessRate !== null && <b>{realSuccessRate}%</b>}</span></div>
					</div>
					<p className="rd-compare-hint">참가자 결과를 변경하면 막대가 바로 갱신됩니다.</p>
				</section>
			</div>

			<section className="rd-compare-card rd-compare-timeline">
				<div className="rd-compare-section-title">
					<div><h2>단계별 이탈 지점</h2><p>AI 진단과 실사용자 관찰 단계</p></div>
					<div className="rd-compare-legend"><span><i className="is-ai" />AI 진단</span><span><i className="is-human" />실사용자 관찰</span></div>
				</div>
				<div className="rd-compare-stage-track">
					<div className="rd-compare-stage-line" />
					{experiment.stages.map((stage, index) => (
						<div className="rd-compare-stage" key={`${experiment.id}-${stage}`}>
							<div className="rd-compare-stage-markers">
								{aiMarkers.includes(index) && <span className="is-ai" title="AI 진단 이탈 지점" />}
								{participantMarkers.includes(index) && <span className="is-human" title="실사용자 관찰 이탈 지점" />}
							</div>
							<span className="rd-compare-stage-node" />
							<strong>{stage}</strong>
						</div>
					))}
				</div>
			</section>

			{notice && <p className="rd-compare-notice" role="status">{notice}<button type="button" onClick={() => setNotice('')} aria-label="알림 닫기">×</button></p>}
			<p className="rd-compare-disclaimer">비교 지표와 실험 목록은 현재 화면 확인을 위한 예시 데이터입니다. 실사용자 입력은 이 화면 안에서만 유지됩니다.</p>
		</section>
	);
}
