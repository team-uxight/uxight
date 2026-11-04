import { useEffect, useRef, useState } from 'react';
import {
	chooseWatchedPersona,
	fetchPersonaSteps,
	fetchRunPersonas,
	fetchStepScreenshot,
	isRetryable,
	isRunLive,
	type RunPersona,
	type RunPersonaList,
	type StepLog,
} from './runLogs';

/** 실시간 모니터링 명세(10/24): 영상 대신 step 스크린샷을 1.5초마다 받아 본다. */
const pollMs = 1500;

const personaStatusLabels: Record<string, string> = {
	running: '진행 중',
	done: '완료 선언',
	max_steps: 'step 상한',
	token_limit: '토큰 상한',
	stuck: '막힘',
	fail: '실패',
	timeout: '시간 초과',
	cancelled: '취소',
};

function personaStatusLabel(persona: RunPersona): string {
	if (persona.status === null) return '대기';
	// agent 는 회차를 접수할 때 모든 Persona 를 running · 0 step 으로 만든다 — 브라우저 자리를 기다리는 중일 수 있다.
	if (persona.status === 'running' && !persona.steps) return '준비 중';
	return personaStatusLabels[persona.status] ?? persona.status;
}

function describeAction(step: StepLog): string {
	const action = step.action;
	if (!action?.kind) return '행동 없음';
	switch (action.kind) {
		case 'click':
			return `클릭 [${action.target ?? '?'}]`;
		case 'type':
			return `입력 [${action.target ?? '?'}] "${action.text ?? ''}"`;
		case 'scroll':
			return action.direction === 'up' ? '위로 스크롤' : '아래로 스크롤';
		case 'back':
			return '뒤로 가기';
		case 'done':
			return '완료 선언';
		default:
			return action.kind;
	}
}

function errorMessage(error: unknown, fallback: string): string {
	return error instanceof Error ? error.message : fallback;
}

type Props = {
	/** 보고 있는 회차. 회차가 바뀌면 부모가 key 로 이 화면을 새로 만든다. */
	runId: number | null;
	agentUnreachable: boolean;
};

export default function MonitorLiveViewer({ runId, agentUnreachable }: Props) {
	const [list, setList] = useState<RunPersonaList | null>(null);
	const [listError, setListError] = useState<string | null>(null);
	const [watchedId, setWatchedId] = useState<number | null>(null);
	const [stepState, setStepState] = useState<{ personaId: number; steps: StepLog[] } | null>(null);
	const [stepError, setStepError] = useState<string | null>(null);
	const [pinned, setPinned] = useState<{ personaId: number; step: number } | null>(null);
	const [image, setImage] = useState<{ personaId: number; step: number; url: string } | null>(null);
	const [imageError, setImageError] = useState<{ personaId: number; step: number; message: string } | null>(null);
	const watchedRef = useRef<number | null>(null);
	const pickedRef = useRef(false);
	const previousPersonas = useRef<RunPersona[] | null>(null);
	const imageUrlRef = useRef<string | null>(null);

	// Persona 목록 — 회차가 도는 동안 1.5초마다. 보던 사람이 끝나면 다음 running 으로 넘긴다.
	useEffect(() => {
		if (runId === null) return;
		let stopped = false;
		let timer: number | undefined;
		const controller = new AbortController();
		async function tick(id: number) {
			try {
				const next = await fetchRunPersonas(id, controller.signal);
				if (stopped) return;
				const previous = previousPersonas.current;
				previousPersonas.current = next.personas;
				setList(next);
				setListError(null);
				const chosen = chooseWatchedPersona(next.personas, watchedRef.current, previous, pickedRef.current);
				if (chosen !== watchedRef.current) {
					watchedRef.current = chosen;
					pickedRef.current = false;
					setWatchedId(chosen);
				}
				if (isRunLive(next)) timer = window.setTimeout(() => void tick(id), pollMs);
			} catch (error) {
				if (stopped) return;
				setListError(errorMessage(error, 'Persona 진행을 불러오지 못했습니다.'));
				if (isRetryable(error)) timer = window.setTimeout(() => void tick(id), pollMs);
			}
		}
		void tick(runId);
		return () => {
			stopped = true;
			controller.abort();
			window.clearTimeout(timer);
		};
	}, [runId]);

	const watched = list?.personas.find((persona) => persona.personaId === watchedId) ?? null;
	const watchedRunning = watched?.status === 'running';

	// 보고 있는 Persona 의 step 로그 — running 동안 1.5초마다, 끝나면 한 번 더 읽고 멈춘다.
	useEffect(() => {
		if (runId === null || watchedId === null) return;
		let stopped = false;
		let timer: number | undefined;
		const controller = new AbortController();
		async function tick(id: number, personaId: number) {
			try {
				const steps = await fetchPersonaSteps(id, personaId, controller.signal);
				if (stopped) return;
				setStepState({ personaId, steps });
				setStepError(null);
				if (watchedRunning) timer = window.setTimeout(() => void tick(id, personaId), pollMs);
			} catch (error) {
				if (stopped) return;
				setStepError(errorMessage(error, 'step 로그를 불러오지 못했습니다.'));
				// 끝난 Persona 의 마지막 읽기가 실패해도 다시 읽는다 — 마지막 step 이 빠지지 않게
				if (isRetryable(error)) timer = window.setTimeout(() => void tick(id, personaId), pollMs);
			}
		}
		void tick(runId, watchedId);
		return () => {
			stopped = true;
			controller.abort();
			window.clearTimeout(timer);
		};
	}, [runId, watchedId, watchedRunning]);

	const steps = stepState !== null && stepState.personaId === watchedId ? stepState.steps : [];
	const latest = steps.at(-1) ?? null;
	const pinnedStep = pinned !== null && pinned.personaId === watchedId
		? steps.find((step) => step.step === pinned.step) ?? null
		: null;
	const shown = pinnedStep ?? latest;
	const imageStep = shown?.hasScreenshot ? shown.step : null;

	// 보여 줄 step 의 스크린샷. 새 그림을 받은 뒤에 앞 그림 주소를 해제한다(바꿔 끼울 때 깜빡이지 않게).
	useEffect(() => {
		if (runId === null || watchedId === null || imageStep === null) return;
		const controller = new AbortController();
		let timer: number | undefined;
		function load(id: number, personaId: number, step: number) {
			fetchStepScreenshot(id, personaId, step, controller.signal)
				.then((blob) => {
					if (controller.signal.aborted) return;
					const url = URL.createObjectURL(blob);
					const previousUrl = imageUrlRef.current;
					imageUrlRef.current = url;
					setImage({ personaId, step, url });
					setImageError(null);
					if (previousUrl) URL.revokeObjectURL(previousUrl);
				})
				.catch((error: unknown) => {
					if (controller.signal.aborted) return;
					setImageError({ personaId, step, message: errorMessage(error, '화면을 불러오지 못했습니다.') });
					if (isRetryable(error)) timer = window.setTimeout(() => load(id, personaId, step), pollMs);
				});
		}
		load(runId, watchedId, imageStep);
		return () => {
			controller.abort();
			window.clearTimeout(timer);
		};
	}, [runId, watchedId, imageStep]);

	useEffect(() => () => {
		if (imageUrlRef.current) URL.revokeObjectURL(imageUrlRef.current);
	}, []);

	function pickPersona(personaId: number) {
		pickedRef.current = true;
		watchedRef.current = personaId;
		setWatchedId(personaId);
	}

	const currentImageError = imageError !== null && imageError.personaId === watchedId && imageError.step === imageStep
		? imageError.message
		: null;
	// 지금 step 에 화면이 있을 때만 그림을 보인다. 새 그림을 받는 동안에는 같은 Persona 의 앞 그림을 잠깐 두고,
	// 받기가 실패하면 앞 그림을 내린다(그 step 의 화면처럼 보이지 않게).
	const visibleImage = imageStep !== null && image !== null && image.personaId === watchedId && currentImageError === null
		? image
		: null;
	const live = list === null || isRunLive(list);
	const error = listError ?? stepError ?? currentImageError;

	let screenMessage: { title: string; detail: string };
	if (agentUnreachable) {
		screenMessage = {
			title: 'AI 모듈에 연결하지 못해 재시도 중입니다',
			detail: '실행 서비스에 연결할 수 없어 30초마다 재전송을 시도하고 있습니다. 요청이 접수되면 화면이 표시됩니다.',
		};
	} else if (runId === null) {
		screenMessage = { title: '회차 정보를 기다리는 중입니다', detail: '회차가 만들어지면 Persona 화면이 여기에 표시됩니다.' };
	} else if (list === null) {
		screenMessage = { title: 'Persona 진행을 불러오는 중입니다', detail: '' };
	} else if (watched === null || watched.status === null) {
		screenMessage = {
			title: watched ? `${watched.name} 님이 아직 시작하지 않았습니다` : '표시할 Persona 가 없습니다',
			detail: 'AI 모듈이 Persona 를 시작하면 step 마다 화면이 바뀝니다.',
		};
	} else if (shown !== null && !shown.hasScreenshot) {
		screenMessage = { title: `step ${shown.step} 은 화면을 남기지 않았습니다`, detail: '이 step 을 기록할 때 화면을 찍지 못했습니다.' };
	} else if (shown !== null) {
		screenMessage = { title: currentImageError ? '화면을 불러오지 못했습니다' : '화면을 불러오는 중입니다', detail: '' };
	} else if (watched.status === 'running') {
		screenMessage = { title: '첫 화면을 기다리는 중입니다', detail: 'step 하나가 끝나면 그때 본 화면이 표시됩니다.' };
	} else {
		screenMessage = { title: '기록된 화면이 없습니다', detail: '이 Persona 는 화면을 남기지 않고 끝났습니다.' };
	}

	const viewerState = agentUnreachable
		? { label: 'AI 연결 재시도 중', className: ' is-warning' }
		: watchedRunning
			? { label: '실시간', className: ' is-live' }
			: { label: watched?.status ? '끝남' : '대기', className: '' };

	return (
		<div className="rml-main">
			<div className="rml-personas" role="group" aria-label="Persona 목록">
				{list === null
					? <p className="rml-muted">{listError ?? 'Persona 진행을 불러오는 중입니다.'}</p>
					: list.personas.map((persona) => (
						<button
							type="button"
							key={persona.personaId}
							aria-pressed={persona.personaId === watchedId}
							className={`rml-persona${persona.personaId === watchedId ? ' is-selected' : ''}`}
							onClick={() => pickPersona(persona.personaId)}
						>
							<strong>{persona.name}</strong>
							<span className={`rml-persona-status rml-persona-status--${persona.status ?? 'waiting'}`}>
								{personaStatusLabel(persona)}
							</span>
							<small>{persona.steps ?? 0} step</small>
						</button>
					))}
			</div>

			<div className="rml-viewer" aria-label="AI 실험 화면">
				<div className="rml-viewer-toolbar">
					<div className="rml-browser-dots" aria-hidden="true"><i /><i /><i /></div>
					<span>
						{watched ? `${watched.name}${shown ? ` · step ${shown.step}` : ''}` : 'AI 브라우저 화면'}
					</span>
					<span className={`rml-viewer-state${viewerState.className}`}>{viewerState.label}</span>
				</div>
				<div className="rml-screen" role="status">
					{visibleImage ? (
						<img
							className="rml-screen-image"
							src={visibleImage.url}
							alt={`${watched?.name ?? 'Persona'} step ${visibleImage.step} 에서 본 화면`}
						/>
					) : (
						<div className="rml-screen-message">
							<svg viewBox="0 0 48 48" aria-hidden="true">
								<rect x="5" y="8" width="38" height="27" rx="4" />
								<path d="M17 41h14M24 35v6M19 21l4 4 7-8" />
							</svg>
							<strong>{screenMessage.title}</strong>
							{screenMessage.detail && <span>{screenMessage.detail}</span>}
						</div>
					)}
				</div>
				<div className="rml-viewer-caption">
					<span className="rml-viewer-url">{shown?.url ?? '—'}</span>
					{pinnedStep ? (
						<button type="button" className="rml-follow" onClick={() => setPinned(null)}>
							최신 step 보기
						</button>
					) : (
						<span>{live ? '1.5초마다 갱신합니다.' : '회차가 끝나 갱신을 멈췄습니다.'}</span>
					)}
				</div>
				{error && <p className="rml-error" role="status">{error}</p>}
			</div>

			{shown && (
				<dl className="rml-step-detail" aria-label={`step ${shown.step} 상세`}>
					<div><dt>step</dt><dd>{shown.step}</dd></div>
					<div><dt>행동</dt><dd>{describeAction(shown)}</dd></div>
					<div><dt>이유</dt><dd>{shown.reasoning ?? '—'}</dd></div>
					<div><dt>주소</dt><dd className="rml-break">{shown.url ?? '—'}</dd></div>
					{shown.blocked && (
						<div className="is-blocked"><dt>가드가 막음</dt><dd>{shown.blockedReason ?? '이유가 기록되지 않았습니다.'}</dd></div>
					)}
					{shown.result && !shown.result.ok && shown.result.error && (
						<div className="is-failed"><dt>행동 실패</dt><dd>{shown.result.error}</dd></div>
					)}
				</dl>
			)}

			{steps.length > 0 && (
				<ol className="rml-steps" aria-label="step 로그">
					{[...steps].reverse().map((step) => (
						<li key={step.step}>
							<button
								type="button"
								aria-current={shown?.step === step.step ? 'step' : undefined}
								className={`rml-step${shown?.step === step.step ? ' is-selected' : ''}${step.blocked ? ' is-blocked' : ''}`}
								onClick={() => setPinned(
									step.step === latest?.step || watchedId === null ? null : { personaId: watchedId, step: step.step },
								)}
							>
								<strong>step {step.step}</strong>
								<span>{describeAction(step)}</span>
								<small>{step.reasoning ?? ''}</small>
							</button>
						</li>
					))}
				</ol>
			)}
		</div>
	);
}
