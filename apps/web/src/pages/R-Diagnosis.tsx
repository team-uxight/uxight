import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

type Friction = {
	id: string;
	title: string;
	severity: '높음' | '중간';
	personas: number;
	occurrences: { persona: string; step: string; issue?: string }[];
};

const frictions: Friction[] = [
	{
		id: 'navigation-confusion',
		title: 'Navigation Confusion',
		severity: '높음',
		personas: 4,
		occurrences: [
			{ persona: 'Novice-1', step: 'step 3', issue: '장학금 메뉴를 찾지 못하고 학사 안내를 반복 탐색했습니다.' },
			{ persona: 'Novice-2', step: 'step 4', issue: '유사한 메뉴 이름을 선택해 이전 화면으로 돌아왔습니다.' },
			{ persona: 'Expert-1', step: '이상 없음' },
			{ persona: 'Novice-3', step: 'step 4', issue: '장학 공지와 장학 신청 메뉴를 구분하지 못했습니다.' },
		],
	},
	{
		id: 'label-ambiguity',
		title: 'Label Ambiguity',
		severity: '중간',
		personas: 2,
		occurrences: [
			{ persona: 'Novice-1', step: 'step 6', issue: '신청 현황 링크를 신청 시작 버튼으로 오해했습니다.' },
			{ persona: 'Expert-1', step: 'step 2', issue: '축약된 메뉴 레이블의 의미를 추측해야 했습니다.' },
		],
	},
];

export default function RDiagnosis() {
	const navigate = useNavigate();
	const [expanded, setExpanded] = useState('navigation-confusion');
	const [severity, setSeverity] = useState('전체');
	const [type, setType] = useState('전체');
	const [notice, setNotice] = useState('');

	const visibleFrictions = frictions.filter((friction) =>
		(severity === '전체' || friction.severity === severity) &&
		(type === '전체' || friction.title === type),
	);

	return (
		<section className="rd-diagnosis" aria-labelledby="diagnosis-title">
			<div className="rd-report-title-row">
				<div className="rd-title-inline">
					<h1 id="diagnosis-title">Diagnosis</h1>
					<span>— 진단 결과</span>
				</div>
				<span className="rd-demo-label">R4 · 시안 예시 데이터</span>
			</div>

			<div className="rd-diagnosis-run">
				<div>
					<span>실험 13</span>
					<strong>장학금 신청 프로세스 UX 및 예외 처리 검증</strong>
				</div>
				<span>성공 3/5 · 평균 12 step</span>
			</div>

			<div className="rd-friction-toolbar">
				<h2>Friction {visibleFrictions.length}건</h2>
				<div>
					<label>심각도:
						<select value={severity} onChange={(event) => setSeverity(event.target.value)}>
							<option>전체</option><option>높음</option><option>중간</option>
						</select>
					</label>
					<label>유형:
						<select value={type} onChange={(event) => setType(event.target.value)}>
							<option>전체</option><option>Navigation Confusion</option><option>Label Ambiguity</option>
						</select>
					</label>
				</div>
			</div>

			<div className="rd-friction-list">
				{visibleFrictions.map((friction) => {
					const isExpanded = expanded === friction.id;
					return (
						<article className={`rd-friction-card${isExpanded ? ' is-expanded' : ''}`} key={friction.id}>
							<button className="rd-friction-card-heading" type="button" aria-expanded={isExpanded} onClick={() => setExpanded(isExpanded ? '' : friction.id)}>
								<span className={`rd-severity-badge rd-severity-badge--${friction.severity === '높음' ? 'high' : 'medium'}`}>△ {friction.severity}</span>
								<strong>{friction.title}</strong>
								<span className="rd-friction-occurrence">Persona {friction.personas}/5 발생</span>
								<span className="rd-friction-chevron" aria-hidden="true">
									<svg viewBox="0 0 24 24" focusable="false">
										<path d={isExpanded ? 'm6 9 6 6 6-6' : 'm9 18 6-6-6-6'} />
									</svg>
								</span>
							</button>
							{isExpanded && (
								<div className="rd-friction-details">
									{friction.occurrences.map((occurrence) => (
										<div className="rd-occurrence-row" key={occurrence.persona}>
											<strong>{occurrence.persona}</strong>
											<span>{occurrence.step}</span>
											{occurrence.issue ? (
												<button type="button" className="rd-evidence-button" onClick={() => setNotice(`${occurrence.persona}의 ${occurrence.step} 근거 화면은 데모 데이터입니다.`)}>근거 보기</button>
											) : <span className="rd-no-issue">이상 없음</span>}
											{occurrence.issue && <p>{occurrence.issue}</p>}
										</div>
									))}
									<div className="rd-friction-footer">
										<span><b>AI</b> 이 유형에 제안된 개선안 3건</span>
										<button type="button" className="rd-pill-button" onClick={() => navigate('/fixes', { state: { friction: friction.title } })}>개선안 확인하기</button>
									</div>
								</div>
							)}
						</article>
					);
				})}
				{visibleFrictions.length === 0 && <div className="rd-empty-state"><p>선택한 조건에 맞는 진단 결과가 없습니다.</p></div>}
			</div>
			{notice && <div className="rd-inline-notice" role="status">{notice}<button type="button" onClick={() => setNotice('')} aria-label="닫기">×</button></div>}
		</section>
	);
}
