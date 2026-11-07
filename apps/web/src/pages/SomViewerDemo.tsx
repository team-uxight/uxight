import { useState } from 'react';
import { ArrowLeft, ChevronLeft, ChevronRight, Minus, Plus } from 'lucide-react';
import { Link } from 'react-router-dom';
import './SomViewerDemo.css';

type Mark = { number: number; label: string; x: number; y: number; width: number; height: number };
type DemoStep = { title: string; image: string; width: number; height: number; marks: Mark[] };

const steps: DemoStep[] = [
	{
		title: '홈페이지에서 전체 메뉴 버튼 찾기',
		image: '/som-demo/gachon-homepage-step-01.jpg',
		width: 1794,
		height: 926,
		marks: [
			{ number: 1, label: '전체 메뉴 버튼', x: 1656, y: 80, width: 55, height: 54 },
		],
	},
	{
		title: '학사안내에서 장학공지 선택하기',
		image: '/som-demo/gachon-menu-open.jpg',
		width: 1794,
		height: 926,
		marks: [
			{ number: 1, label: '학사안내 메뉴', x: 904, y: 697, width: 344, height: 124 },
			{ number: 2, label: '장학공지 링크', x: 1318, y: 598, width: 150, height: 66 },
		],
	},
	{
		title: '장학공지에서 신청 안내 찾기',
		image: '/som-demo/gachon-scholarship-notice.jpg',
		width: 1794,
		height: 926,
		marks: [
			{ number: 1, label: '국가장학금 신청 안내', x: 141, y: 437, width: 796, height: 53 },
		],
	},
];

function HtmlBadges({ marks, width, height }: { marks: Mark[]; width: number; height: number }) {
	return (
		<div className="som-html-overlay" aria-label="HTML 번호 배지">
			{marks.map((mark) => (
				<span
					className="som-html-badge"
					key={mark.number}
					style={{
						left: `${mark.x / width * 100}%`,
						top: `${mark.y / height * 100}%`,
					}}
					aria-label={`${mark.number}. ${mark.label}`}
				>
					<span>{mark.number}</span>
				</span>
			))}
		</div>
	);
}

function HtmlMarks({ marks, width, height }: { marks: Mark[]; width: number; height: number }) {
	return (
		<div className="som-html-overlay" aria-label="HTML 오버레이 번호 박스">
			{marks.map((mark) => (
				<div
					className="som-html-mark"
					key={mark.number}
					style={{
						left: `${mark.x / width * 100}%`,
						top: `${mark.y / height * 100}%`,
						width: `${mark.width / width * 100}%`,
						height: `${mark.height / height * 100}%`,
					}}
					aria-label={`${mark.number}. ${mark.label}`}
				>
					<span>{mark.number}</span>
				</div>
			))}
		</div>
	);
}

function SvgMarks({ marks, width, height }: { marks: Mark[]; width: number; height: number }) {
	return (
		<svg className="som-svg-overlay" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-label="SVG 오버레이 번호 박스">
			{marks.map((mark) => (
				<rect
					className="som-svg-mark"
					key={mark.number}
					x={mark.x}
					y={mark.y}
					width={mark.width}
					height={mark.height}
					rx="8"
				/>
			))}
		</svg>
	);
}

function ViewerCard({
	title,
	method,
	description,
	step,
	zoom,
}: {
	title: string;
	method: 'html' | 'svg';
	description: string;
	step: DemoStep;
	zoom: number;
}) {
	return (
		<section className="som-viewer-card" aria-label={`${title} 방식 미리보기`}>
			<header className="som-viewer-heading">
				<div><span>{title}</span><h2>{method === 'html' ? 'HTML absolute overlay' : 'SVG viewBox overlay'}</h2></div>
				<span className="som-method-tag">{method.toUpperCase()}</span>
			</header>
			<p className="som-viewer-description">{description}</p>
			<div className="som-image-scroll">
				<div className="som-zoom-surface" style={{ width: `${zoom * 100}%` }}>
					<div className="som-image-frame" style={{ aspectRatio: `${step.width} / ${step.height}` }}>
						<img src={step.image} alt={`${step.title} 화면 예시`} />
						{method === 'html'
							? <HtmlMarks marks={step.marks} width={step.width} height={step.height} />
							: <>
								<SvgMarks marks={step.marks} width={step.width} height={step.height} />
								<HtmlBadges marks={step.marks} width={step.width} height={step.height} />
							</>}
					</div>
				</div>
			</div>
			<ol className="som-mark-list">
				{step.marks.map((mark) => <li key={mark.number}><span>{mark.number}</span>{mark.label}</li>)}
			</ol>
		</section>
	);
}

export default function SomViewerDemo() {
	const [stepIndex, setStepIndex] = useState(0);
	const [zoom, setZoom] = useState(0.72);
	const step = steps[stepIndex];

	const updateZoom = (nextZoom: number) => setZoom(Math.min(1.5, Math.max(0.5, nextZoom)));

	return (
		<main className="som-demo-page">
			<div className="som-demo-container">
				<Link className="som-back-link" to="/dashboard"><ArrowLeft size={16} aria-hidden="true" />리서처 화면으로</Link>
				<header className="som-demo-header">
					<div>
						<span className="som-eyebrow">GACA-98 · FE 기술 검증</span>
						<h1>가천대 포털 장학공지 탐색</h1>
						<p>홈페이지에서 전체 메뉴를 열고, 학사안내를 거쳐 장학금 신청 안내를 찾는 흐름입니다.</p>
					</div>
					<span className="som-demo-status">샘플 데이터 · AI 연동 불필요</span>
				</header>

				<section className="som-controls" aria-label="데모 조작 도구">
					<div className="som-step-controls">
						<button type="button" aria-label="이전 step" onClick={() => setStepIndex((current) => Math.max(0, current - 1))} disabled={stepIndex === 0}><ChevronLeft size={18} /></button>
						<div><strong>Step {stepIndex + 1} / {steps.length}</strong><span>{step.title}</span></div>
						<button type="button" aria-label="다음 step" onClick={() => setStepIndex((current) => Math.min(steps.length - 1, current + 1))} disabled={stepIndex === steps.length - 1}><ChevronRight size={18} /></button>
					</div>
					<div className="som-zoom-controls">
						<button type="button" aria-label="축소" onClick={() => updateZoom(zoom - 0.1)} disabled={zoom <= 0.5}><Minus size={16} /></button>
						<input aria-label="확대 비율" type="range" min="0.5" max="1.5" step="0.1" value={zoom} onChange={(event) => updateZoom(Number(event.target.value))} />
						<button type="button" aria-label="확대" onClick={() => updateZoom(zoom + 0.1)} disabled={zoom >= 1.5}><Plus size={16} /></button>
						<output>{Math.round(zoom * 100)}%</output>
					</div>
				</section>

				<div className="som-viewer-grid">
					<ViewerCard
						title="방식 A"
						method="html"
						description="퍼센트 기반 absolute 요소를 이미지 프레임 위에 배치"
						step={step}
						zoom={zoom}
					/>
					<ViewerCard
						title="방식 B"
						method="svg"
						description="원본 좌표 viewBox로 박스 렌더링 · 번호 배지는 두 방식 공통"
						step={step}
						zoom={zoom}
					/>
				</div>

				<aside className="som-decision">
					<span>방식 결정</span>
					<p><strong>SVG viewBox 오버레이를 채택합니다.</strong> 스크린샷 원본 좌표를 그대로 사용해 확대·반응형 크기 변경에도 번호 박스와 화면 요소의 정렬을 유지하기 쉽습니다.</p>
				</aside>
				<p className="som-demo-footnote">가천대학교 <a href="https://www.gachon.ac.kr/kor/index.do" target="_blank" rel="noreferrer">공개 홈페이지</a>와 장학공지 목록을 2026.10.15에 캡처한 데모 이미지입니다. step 이동과 확대/축소로 양쪽 오버레이를 비교해 보세요.</p>
			</div>
		</main>
	);
}
