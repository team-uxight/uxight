import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

type Evidence = {
	timestamp: string;
	score: number;
	thought: string;
	action: string;
	context: string;
};

type Occurrence = { persona: string; step: string; issue?: string; evidence?: Evidence };

type Friction = {
	id: string;
	title: string;
	severity: '높음' | '중간';
	personas: number;
	occurrences: Occurrence[];
};

// 시안용 예시 데이터. 근거 스크린샷과 로그 API 가 생기면 교체한다.
const frictions: Friction[] = [
	{
		id: 'navigation-confusion',
		title: 'Navigation Confusion',
		severity: '높음',
		personas: 4,
		occurrences: [
			{
				persona: 'Novice-1', step: 'step 3', issue: '장학금 메뉴를 찾지 못하고 학사 안내를 반복 탐색했습니다.',
				evidence: { timestamp: '2026/09/24 21:03:55', score: 4, thought: '장학금 메뉴가 학사안내 아래 있어서 찾기 어려웠다.', action: '장학금 메뉴를 찾기 위해 아래로 스크롤을 반복했다.', context: 'Novice-1 유저가 직관적인 위치에 장학 항목이 없어 탐색이 지연되었다.' },
			},
			{
				persona: 'Novice-2', step: 'step 4', issue: '유사한 메뉴 이름을 선택해 이전 화면으로 돌아왔습니다.',
				evidence: { timestamp: '2026/09/24 21:05:12', score: 3, thought: '비슷한 이름의 메뉴가 여러 개라 어느 쪽인지 확신이 없었다.', action: '장학 공지를 눌렀다가 뒤로 가기를 눌렀다.', context: '유사한 메뉴 이름 때문에 잘못된 화면으로 진입했다.' },
			},
			{ persona: 'Expert-1', step: '이상 없음' },
			{
				persona: 'Novice-3', step: 'step 4', issue: '장학 공지와 장학 신청 메뉴를 구분하지 못했습니다.',
				evidence: { timestamp: '2026/09/24 21:07:40', score: 4, thought: '장학 공지와 장학 신청이 같은 것이라고 생각했다.', action: '장학 공지 게시판을 열어 신청 버튼을 찾았다.', context: '두 메뉴의 역할이 구분되지 않아 신청 경로를 놓쳤다.' },
			},
		],
	},
	{
		id: 'label-ambiguity',
		title: 'Label Ambiguity',
		severity: '중간',
		personas: 2,
		occurrences: [
			{
				persona: 'Novice-1', step: 'step 6', issue: '신청 현황 링크를 신청 시작 버튼으로 오해했습니다.',
				evidence: { timestamp: '2026/09/24 21:09:03', score: 3, thought: '신청 현황이 신청을 시작하는 버튼인 줄 알았다.', action: '신청 현황 링크를 클릭했다.', context: '레이블이 기능을 정확히 설명하지 못해 오해가 생겼다.' },
			},
			{
				persona: 'Expert-1', step: 'step 2', issue: '축약된 메뉴 레이블의 의미를 추측해야 했습니다.',
				evidence: { timestamp: '2026/09/24 21:02:31', score: 2, thought: '축약된 레이블이라 의미를 추측해야 했다.', action: '메뉴에 마우스를 올려 설명을 확인했다.', context: '축약 레이블 때문에 의도 파악에 시간이 걸렸다.' },
			},
		],
	},
];

export default function RDiagnosis() {
	const navigate = useNavigate();
	const [expanded, setExpanded] = useState('navigation-confusion');
	const [severity, setSeverity] = useState('전체');
	const [type, setType] = useState('전체');
	const [evidenceTarget, setEvidenceTarget] = useState<{ friction: Friction; occurrence: Occurrence } | null>(null);

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
											<div className="rd-occurrence-info">
												<strong>{occurrence.persona}</strong>
												{occurrence.issue && <p>{occurrence.issue}</p>}
											</div>
											<span>{occurrence.issue ? occurrence.step : '이상 없음'}</span>
											{occurrence.issue && (
												<button type="button" className="rd-evidence-button" onClick={() => setEvidenceTarget({ friction, occurrence })}>근거 보기</button>
											)}
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
			{evidenceTarget?.occurrence.evidence && (
				<div className="rd-evidence-backdrop" role="presentation" onClick={() => setEvidenceTarget(null)}>
					<div
						className="rd-evidence-panel"
						role="dialog"
						aria-modal="true"
						aria-labelledby="evidence-title"
						onClick={(event) => event.stopPropagation()}
					>
						<header className="rd-evidence-head">
							<span>근거 (Evidence)</span>
							<button type="button" onClick={() => setEvidenceTarget(null)} aria-label="닫기">×</button>
						</header>
						<h2 id="evidence-title">{evidenceTarget.friction.title}</h2>
						<div className="rd-evidence-meta">
							<strong>{evidenceTarget.occurrence.persona} · {evidenceTarget.occurrence.step} | {evidenceTarget.occurrence.evidence.timestamp}</strong>
							<span className="rd-evidence-score">Friction {evidenceTarget.occurrence.evidence.score}/5 ({evidenceTarget.friction.severity})</span>
						</div>
						<div className="rd-evidence-body">
							<div className="rd-evidence-shot" role="img" aria-label="근거 스크린샷 (연동 예정)">
								<span>스크린샷을 불러올 수 없습니다</span>
							</div>
							<dl className="rd-evidence-notes">
								<div><dt>Thought</dt><dd>{evidenceTarget.occurrence.evidence.thought}</dd></div>
								<div><dt>Action</dt><dd>{evidenceTarget.occurrence.evidence.action}</dd></div>
								<div><dt>Friction Context</dt><dd>{evidenceTarget.occurrence.evidence.context}</dd></div>
							</dl>
						</div>
					</div>
				</div>
			)}
		</section>
	);
}
