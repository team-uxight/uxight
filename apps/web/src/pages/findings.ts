import { API_BASE_URL, apiErrorMessage, authenticatedFetch } from '../auth';
import { ApiError } from './runLogs';

export type FindingTaxonomy =
	| 'navigation_confusion'
	| 'interaction_failure'
	| 'task_failure'
	| 'excessive_steps';

export type FindingSeverity = 'high' | 'medium' | 'low';

export const taxonomyLabels: Record<FindingTaxonomy, string> = {
	navigation_confusion: '길 찾기 혼란',
	interaction_failure: '조작 실패',
	task_failure: '과제 실패',
	excessive_steps: '과도한 단계',
};

export const severityLabels: Record<FindingSeverity, string> = {
	high: '높음',
	medium: '중간',
	low: '낮음',
};

export type RunFindings = {
	run: {
		firstRunId: number;
		round: number;
		projectTitle: string;
		taskGoal: string;
		improvementCount: number;
	};
	findings: {
		findingId: number;
		taxonomy: FindingTaxonomy;
		severity: FindingSeverity;
		summary: string | null;
	}[];
};

export type FindingEvidence = {
	personaId: number;
	stepFrom: number;
	stepTo: number;
	url: string | null;
};

export type FindingDetail = {
	findingId: number;
	runId: number;
	taxonomy: FindingTaxonomy;
	severity: FindingSeverity;
	summary: string | null;
	evidence: FindingEvidence[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null;
}

function isTaxonomy(value: unknown): value is FindingTaxonomy {
	return value === 'navigation_confusion' ||
		value === 'interaction_failure' ||
		value === 'task_failure' ||
		value === 'excessive_steps';
}

function isSeverity(value: unknown): value is FindingSeverity {
	return value === 'high' || value === 'medium' || value === 'low';
}

function isSummary(value: unknown): value is string | null {
	return value === null || typeof value === 'string';
}

function isFinding(value: unknown): value is RunFindings['findings'][number] {
	return isRecord(value) &&
		typeof value.findingId === 'number' &&
		isTaxonomy(value.taxonomy) &&
		isSeverity(value.severity) &&
		isSummary(value.summary);
}

function isEvidence(value: unknown): value is FindingEvidence {
	return isRecord(value) &&
		typeof value.personaId === 'number' &&
		typeof value.stepFrom === 'number' &&
		typeof value.stepTo === 'number' &&
		(value.url === null || typeof value.url === 'string');
}

export async function fetchRunFindings(runId: number): Promise<RunFindings> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/runs/${runId}/findings`);
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '회차 진단을 불러오지 못했습니다.'));
	}

	const body: unknown = await response.json();
	if (
		!isRecord(body) ||
		!isRecord(body.run) ||
		typeof body.run.firstRunId !== 'number' ||
		typeof body.run.round !== 'number' ||
		typeof body.run.projectTitle !== 'string' ||
		typeof body.run.taskGoal !== 'string' ||
		typeof body.run.improvementCount !== 'number' ||
		!Array.isArray(body.findings) ||
		!body.findings.every(isFinding)
	) {
		throw new Error('서버에서 올바르지 않은 회차 진단 정보를 받았습니다.');
	}

	return {
		run: {
			firstRunId: body.run.firstRunId,
			round: body.run.round,
			projectTitle: body.run.projectTitle,
			taskGoal: body.run.taskGoal,
			improvementCount: body.run.improvementCount,
		},
		findings: body.findings,
	};
}

export async function fetchFindingDetail(findingId: number): Promise<FindingDetail> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/findings/${findingId}`);
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '진단 근거를 불러오지 못했습니다.'));
	}

	const body: unknown = await response.json();
	if (
		!isRecord(body) ||
		typeof body.findingId !== 'number' ||
		typeof body.runId !== 'number' ||
		!isTaxonomy(body.taxonomy) ||
		!isSeverity(body.severity) ||
		!isSummary(body.summary) ||
		!Array.isArray(body.evidence) ||
		!body.evidence.every(isEvidence)
	) {
		throw new Error('서버에서 올바르지 않은 진단 근거를 받았습니다.');
	}

	return {
		findingId: body.findingId,
		runId: body.runId,
		taxonomy: body.taxonomy,
		severity: body.severity,
		summary: body.summary,
		evidence: body.evidence,
	};
}

export async function fetchFindingScreenshot(
	findingId: number,
	personaId: number,
	step: number,
	signal?: AbortSignal,
): Promise<Blob> {
	const query = new URLSearchParams({ personaId: String(personaId), step: String(step) });
	const response = await authenticatedFetch(
		`${API_BASE_URL}/api/findings/${findingId}/screenshots?${query.toString()}`,
		{ signal },
	);
	if (!response.ok) {
		throw new ApiError(await apiErrorMessage(response, '근거 화면을 불러오지 못했습니다.'), response.status);
	}
	return response.blob();
}
