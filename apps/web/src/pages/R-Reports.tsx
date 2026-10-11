const frictionPoints = [
	{ severity: '고', tone: 'high', label: '학사 안내 메뉴 시인성 부족' },
	{ severity: '중', tone: 'medium', label: '검색 필터 복잡성' },
	{ severity: '저', tone: 'low', label: '검색 결과 메뉴 복잡성' },
	{ severity: '중', tone: 'medium', label: '메뉴 간 용어 일관성 부족' },
	{ severity: '저', tone: 'low', label: '도움말 진입 경로가 깊음' },
	{ severity: '저', tone: 'low', label: '현재 위치 표시 부족' },
];

const actionPlans = [
	{ title: '학사 안내 메뉴 시인성 개선', estimate: '개선 시 성공률 +15% 예상' },
	{ title: '검색 필터 프리셋 적용', estimate: '개선 시 성공률 +10% 예상' },
	{ title: '장학 신청 가이드 추가', estimate: '초보 사용자 탐색 단계 감소 예상' },
	{ title: '현재 위치 및 다음 단계 표시', estimate: '탐색 오류와 재방문 감소 예상' },
];

const personaScores = [
	{ name: 'Novice', success: 60, score: 68 },
	{ name: 'Expert', success: 100, score: 88 },
	{ name: 'Mobile', success: 80, score: 76 },
];

export default function RReports() {
	return (
		<section className="rd-report" aria-labelledby="report-title">
			<div className="rd-report-banner">
				<h1 id="report-title">실험 13 최종 UX 평가 리포트</h1>
				<button type="button" onClick={() => window.print()}>▤ PDF 내보내기</button>
			</div>

			<div className="rd-report-overview">
				<section className="rd-report-card">
					<h2>실험 요약 <span>시안 예시 데이터</span></h2>
					<div className="rd-score-grid">
						<article><span className="rd-score-icon">✦</span><div><small>종합 UX 점수</small><strong>74점</strong></div></article>
						<article><span className="rd-score-icon">✓</span><div><small>태스크 성공률</small><strong>82%</strong></div></article>
						<article><span className="rd-score-icon">◷</span><div><small>평균 소요 시간</small><strong>01:45</strong></div></article>
						<article><span className="rd-score-icon">△</span><div><small>예외 발생률</small><strong>18%</strong></div></article>
					</div>
				</section>

				<section className="rd-report-card rd-persona-report">
					<h2>페르소나별 성과 분석</h2>
					<div className="rd-persona-chart" role="img" aria-label="페르소나별 태스크 성공률 그래프">
						{personaScores.map((persona) => (
							<div className="rd-chart-column" key={persona.name}>
								<div className="rd-chart-bars">
									<span className="rd-chart-bar rd-chart-bar--success" style={{ height: `${persona.success}%` }} />
									<span className="rd-chart-bar rd-chart-bar--score" style={{ height: `${persona.score}%` }} />
								</div>
								<strong>{persona.name}</strong>
								<small>{persona.success}% / {persona.score}점</small>
							</div>
						))}
					</div>
					<div className="rd-chart-legend"><span>태스크 성공률</span><span>UX 점수</span></div>
				</section>
			</div>

			<section className="rd-report-card rd-friction-report">
				<h2>주요 UX 마찰 지점 (Friction Points)</h2>
				<div className="rd-friction-point-grid">
					{frictionPoints.map((point, index) => (
						<div key={point.label}>
							<span className={`rd-point-severity rd-point-severity--${point.tone}`}>{point.severity}</span>
							<strong>{point.label}</strong>
							<small>{index + 2}개 Persona에서 관찰</small>
						</div>
					))}
				</div>
			</section>

			<section className="rd-report-card rd-action-plan">
				<h2>AI 개선 제안 및 액션 플랜</h2>
				<ol>
					{actionPlans.map((plan) => (
						<li key={plan.title}>
							<strong>{plan.title}</strong>
							<span>{plan.estimate}</span>
						</li>
					))}
				</ol>
			</section>
			<p className="rd-report-disclaimer">표시된 점수·분석·개선 효과는 화면 확인을 위한 더미 데이터이며 실제 실험 결과가 아닙니다.</p>
		</section>
	);
}
