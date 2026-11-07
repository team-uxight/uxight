import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

type LocationState = { friction?: string };

const suggestions = [
	{ id: 'GACA-1234', title: '메뉴 탐색 배치', detail: '장학금 메뉴를 학사 메뉴 상단에 배치합니다.' },
	{ id: 'GACA-1235', title: '메뉴 라벨 변경', detail: '“장학 안내”를 “장학금 신청·안내”로 명확하게 바꿉니다.' },
	{ id: 'GACA-1236', title: '도움말 추가', detail: '신청 자격과 다음 단계를 안내하는 도움말을 추가합니다.' },
];

function Preview({ after = false }: { after?: boolean }) {
	return (
		<div className={`rd-site-preview${after ? ' rd-site-preview--after' : ''}`} aria-label={after ? '개선 후 더미 사이트 미리보기' : '개선 전 더미 사이트 미리보기'}>
			<div className="rd-preview-browser">
				<span /><span /><span />
				<small>www.gachon.ac.kr</small>
			</div>
			<div className="rd-preview-site">
				<div className="rd-preview-logo">G <span>가천대학교</span></div>
				<div className="rd-preview-banner"><small>2026년 교육부 대학혁신지원사업</small><strong>학생의 꿈을 응원합니다</strong></div>
				<div className="rd-preview-menu"><span>대학소개</span><span>학사</span><span className={after ? 'is-highlighted' : ''}>{after ? '장학금 신청·안내' : '학생지원'}</span><span>공지사항</span></div>
				{after && <div className="rd-preview-callout">장학금 신청 자격과 일정을 확인하세요 <b aria-hidden="true">
					<svg viewBox="0 0 16 16" focusable="false"><path d="M2.5 8h10m-4-4 4 4-4 4" /></svg>
				</b></div>}
			</div>
		</div>
	);
}

export default function RFixes() {
	const navigate = useNavigate();
	const location = useLocation();
	const friction = (location.state as LocationState | null)?.friction;
	const [selected, setSelected] = useState(suggestions[0].id);
	const [decision, setDecision] = useState('');
	const [notice, setNotice] = useState('');

	const selectedSuggestion = suggestions.find((suggestion) => suggestion.id === selected) ?? suggestions[0];

	return (
		<section className="rd-fixes" aria-labelledby="fixes-title">
			<div className="rd-fixes-main">
				<div className="rd-report-title-row">
					<div className="rd-title-inline"><h1 id="fixes-title">Fixes</h1><span>— 개선안</span></div>
					<button type="button" className="rd-run-chip" onClick={() => navigate('/reports')}>실험 13</button>
				</div>
				{friction && <p className="rd-fixes-context">진단 항목: <strong>{friction}</strong></p>}
				<div className="rd-before-after">
					<div><Preview /><span className="rd-preview-label">Before</span></div>
					<div><Preview after /><span className="rd-preview-label">After · 더미 미리보기</span></div>
				</div>
				<div className="rd-impact-grid">
					<article><span>실패율 감소</span><strong>80% ↓</strong><small>예상 개선 효과</small></article>
					<article><span>탐색 단계 단축</span><strong>12 → 4</strong><small>평균 step 기준</small></article>
					<article><span>개발 공수</span><strong>Low</strong><small>난이도 예상</small></article>
				</div>
				<div className="rd-comparison">
					<div><strong>Before</strong><span>탐색 성공률: 1/5</span><span>Steps: 12</span><span>Task 소요 시간: 10분 30초</span></div>
					<div><strong>After · 예상</strong><span>탐색 성공률: 4/5</span><span>Steps: 4</span><span>Task 소요 시간: 7분 45초</span></div>
				</div>
				{decision && <p className="rd-inline-notice" role="status">{decision} — 실제 반영이나 재실험은 아직 연결되지 않았습니다.</p>}
				{notice && <p className="rd-inline-notice" role="status">{notice}</p>}
				<div className="rd-fixes-actions">
					<button className="rd-dark-pill" type="button" onClick={() => setDecision('개선안 승인')}>승인 및 재실험</button>
					<span />
					<button className="rd-pill-button" type="button" onClick={() => setNotice('미리보기는 화면 구성 확인용 더미 데이터입니다.')}>미리보기 및 상세</button>
					<button className="rd-pill-button" type="button" onClick={() => setDecision('개선안을 반려했습니다')}>반려</button>
				</div>
			</div>
			<aside className="rd-suggestion-panel" aria-label="개선안 목록">
				<h2>개선안 목록</h2>
				{suggestions.map((suggestion) => (
					<button className={`rd-suggestion-card${selected === suggestion.id ? ' is-selected' : ''}`} type="button" key={suggestion.id} onClick={() => { setSelected(suggestion.id); setDecision(''); }}>
						<span className="rd-suggestion-id">{suggestion.id}</span>
						<span className="rd-suggestion-icon" aria-hidden="true">
							<svg viewBox="0 0 24 24" focusable="false">
								<path d="M7 5.5h12M7 10h12M7 14.5h12M7 19h12" />
								<circle cx="4" cy="5.5" r=".75" />
								<circle cx="4" cy="10" r=".75" />
								<circle cx="4" cy="14.5" r=".75" />
								<circle cx="4" cy="19" r=".75" />
							</svg>
						</span>
						<strong>{suggestion.title}</strong>
						<small>{suggestion.detail}</small>
						<span className="rd-suggestion-chevron" aria-hidden="true">
							<svg viewBox="0 0 24 24" focusable="false"><path d="m6 9 6 6 6-6" /></svg>
						</span>
					</button>
				))}
				<p className="rd-suggestion-selected">선택됨: {selectedSuggestion.title}</p>
			</aside>
		</section>
	);
}
