import { API_BASE_URL, apiErrorMessage, authenticatedFetch } from '../auth';

/** 회차의 Persona 한 명. AI 모듈이 접수하기 전이면 status · steps · finishedAt 이 null 이다. */
export type RunPersona = {
	personaId: number;
	name: string;
	/** running · done · max_steps · token_limit · stuck · fail · timeout · cancelled, 시작 전이면 null */
	status: string | null;
	steps: number | null;
	finishedAt: string | null;
};

export type RunPersonaList = {
	runId: number;
	/** queued · accepted · running · done · failed · cancelled */
	status: string;
	personas: RunPersona[];
};

export type StepAction = {
	kind: string | null;
	target: number | null;
	text: string | null;
	direction: string | null;
};

export type StepResult = {
	ok: boolean;
	urlAfter: string | null;
	error: string | null;
	errorCode: string | null;
};

/** step 하나의 로그. 스크린샷은 그 step 에서 Persona 가 보고 행동을 고른 화면이다. */
export type StepLog = {
	step: number;
	ts: string | null;
	url: string | null;
	reasoning: string | null;
	action: StepAction | null;
	result: StepResult | null;
	blocked: boolean;
	blockedReason: string | null;
	urlReached: boolean | null;
	hasScreenshot: boolean;
};

/** 응답 상태 코드를 함께 담은 오류. */
export class ApiError extends Error {
	readonly status: number;

	constructor(message: string, status: number) {
		super(message);
		this.status = status;
	}
}

/** 401 · 403 · 404 는 다시 불러도 같은 답이라 갱신을 멈춘다. 그 밖(네트워크 · 5xx)은 다시 부른다. */
export function isRetryable(error: unknown): boolean {
	return !(error instanceof ApiError && [401, 403, 404].includes(error.status));
}

const liveRunStatuses = ['queued', 'accepted', 'running'];

/** 회차가 아직 돌고 있으면 true. 회차가 끝나도 아직 running 인 Persona 가 있으면 계속 본다. */
export function isRunLive(list: RunPersonaList): boolean {
	return liveRunStatuses.includes(list.status) || list.personas.some((persona) => persona.status === 'running');
}

/**
 * 지금 보여 줄 Persona 를 고른다.
 * - 아직 고른 사람이 없거나 목록에 없으면: running 중 목록 순서가 가장 앞인 사람, 없으면 첫 사람.
 * - 보던 사람이 방금 끝났으면(running → 다른 상태): running 중 가장 앞인 사람.
 * - 저절로 고른 사람이 아직 시작 전인데 다른 사람이 running 이면: running 중 가장 앞인 사람.
 *   리서처가 직접 고른(picked) 시작 전 Persona 는 기다린다.
 * - 그 밖에는 그대로 둔다. 리서처가 끝난 사람을 골라 보고 있으면 다른 사람으로 넘기지 않는다.
 */
export function chooseWatchedPersona(
	personas: RunPersona[],
	current: number | null,
	previous: RunPersona[] | null,
	picked = false,
): number | null {
	if (personas.length === 0) return null;
	const firstRunning = personas.find((persona) => persona.status === 'running');
	const now = personas.find((persona) => persona.personaId === current);
	if (!now) return (firstRunning ?? personas[0]).personaId;
	if (!firstRunning) return now.personaId;

	const before = previous?.find((persona) => persona.personaId === current);
	const justFinished = before?.status === 'running' && now.status !== 'running';
	const waitingUnpicked = now.status === null && !picked;
	return justFinished || waitingUnpicked ? firstRunning.personaId : now.personaId;
}

export async function fetchRunPersonas(runId: number, signal?: AbortSignal): Promise<RunPersonaList> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/runs/${runId}/personas`, { signal });
	if (!response.ok) {
		throw new ApiError(await apiErrorMessage(response, 'Persona 진행을 불러오지 못했습니다.'), response.status);
	}
	const body: unknown = await response.json();
	if (
		typeof body !== 'object' ||
		body === null ||
		!('runId' in body) || typeof body.runId !== 'number' ||
		!('status' in body) || typeof body.status !== 'string' ||
		!('personas' in body) || !Array.isArray(body.personas) ||
		!body.personas.every(isRunPersona)
	) {
		throw new Error('서버에서 올바르지 않은 Persona 진행을 받았습니다.');
	}
	return { runId: body.runId, status: body.status, personas: body.personas };
}

export async function fetchPersonaSteps(runId: number, personaId: number, signal?: AbortSignal): Promise<StepLog[]> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/runs/${runId}/personas/${personaId}/steps`, { signal });
	// 자리를 얻기 전에 취소됐거나 접수 직후 실패해 로그 파일 없이 끝난 Persona 는 서버가 404 를 준다 — 기록이 없는 것으로 읽는다.
	if (response.status === 404) return [];
	if (!response.ok) {
		throw new ApiError(await apiErrorMessage(response, 'step 로그를 불러오지 못했습니다.'), response.status);
	}
	const body: unknown = await response.json();
	if (typeof body !== 'object' || body === null || !('steps' in body) || !Array.isArray(body.steps)) {
		throw new Error('서버에서 올바르지 않은 step 로그를 받았습니다.');
	}
	const steps = body.steps.map(toStepLog);
	if (steps.some((step) => step === null)) {
		throw new Error('서버에서 올바르지 않은 step 로그를 받았습니다.');
	}
	return steps as StepLog[];
}

/** 스크린샷 PNG. img 태그로는 Authorization 헤더를 못 붙여서 fetch 로 받는다. */
export async function fetchStepScreenshot(
	runId: number,
	personaId: number,
	step: number,
	signal?: AbortSignal,
): Promise<Blob> {
	const response = await authenticatedFetch(
		`${API_BASE_URL}/api/runs/${runId}/personas/${personaId}/steps/${step}/screenshot`,
		{ signal },
	);
	if (!response.ok) {
		throw new ApiError(await apiErrorMessage(response, '화면을 불러오지 못했습니다.'), response.status);
	}
	return response.blob();
}

function isRunPersona(value: unknown): value is RunPersona {
	return typeof value === 'object' &&
		value !== null &&
		'personaId' in value && typeof value.personaId === 'number' &&
		'name' in value && typeof value.name === 'string' &&
		isNullable(value, 'status', 'string') &&
		isNullable(value, 'steps', 'number') &&
		isNullable(value, 'finishedAt', 'string');
}

/** 칸이 없거나 null 이면 null 로 읽는다 — 명세 형식을 다 쓰지 않는 agent 로그도 서버가 넘겨 준다. */
function toStepLog(value: unknown): StepLog | null {
	if (typeof value !== 'object' || value === null || !('step' in value) || typeof value.step !== 'number') return null;
	const record = value as Record<string, unknown>;
	return {
		step: value.step,
		ts: stringOrNull(record.ts),
		url: stringOrNull(record.url),
		reasoning: stringOrNull(record.reasoning),
		action: toStepAction(record.action),
		result: toStepResult(record.result),
		blocked: record.blocked === true,
		blockedReason: stringOrNull(record.blockedReason),
		urlReached: typeof record.urlReached === 'boolean' ? record.urlReached : null,
		hasScreenshot: record.hasScreenshot === true,
	};
}

function toStepAction(value: unknown): StepAction | null {
	if (typeof value !== 'object' || value === null) return null;
	const record = value as Record<string, unknown>;
	return {
		kind: stringOrNull(record.kind),
		target: typeof record.target === 'number' ? record.target : null,
		text: stringOrNull(record.text),
		direction: stringOrNull(record.direction),
	};
}

function toStepResult(value: unknown): StepResult | null {
	if (typeof value !== 'object' || value === null) return null;
	const record = value as Record<string, unknown>;
	return {
		ok: record.ok === true,
		urlAfter: stringOrNull(record.urlAfter),
		error: stringOrNull(record.error),
		errorCode: stringOrNull(record.errorCode),
	};
}

function stringOrNull(value: unknown): string | null {
	return typeof value === 'string' ? value : null;
}

function isNullable(record: object, key: string, type: 'string' | 'number'): boolean {
	const value = (record as Record<string, unknown>)[key];
	return value === undefined || value === null || typeof value === type;
}
