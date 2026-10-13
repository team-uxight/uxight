import { API_BASE_URL, apiErrorMessage, authenticatedFetch } from '../auth';

export type Experiment = {
	firstRunId: number;
	runId: number;
	round: number;
	status: string;
	state: 'in_progress' | 'awaiting_approval' | 'completed' | 'stopped';
	endType: string | null;
	stale: boolean;
	agentUnreachable: boolean;
	hasResult: boolean;
	projectTitle: string;
	taskGoal: string;
	mode: string;
	progress: number | null;
	personaCount: number;
	elapsedSeconds: number;
	createdAt: string;
};

export type RoundMetrics = {
	successRate: number | null;
	avgSteps: number | null;
	avgBacktracks: number | null;
	avgSeconds: number | null;
	tokens: number | null;
	costUsd: number | null;
};

export type ExperimentRound = {
	runId: number;
	round: number;
	status: string;
	appliedImprovementId: number | null;
	createdAt: string;
	finishedAt: string | null;
	metrics: RoundMetrics | null;
};

export type ExperimentRounds = {
	rounds: ExperimentRound[];
	awaitingApproval: boolean;
};

export type ExperimentStats = {
	totalCount: number;
	inProgressCount: number;
	completedCount: number;
	completedThisWeekCount: number;
	awaitingApprovalCount: number;
	totalTokens: number;
	thisWeekFrom: string;
};

const pageSize = 20;

async function fetchExperimentPage(page: number): Promise<{ content: Experiment[]; totalPages: number }> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/runs?page=${page}&size=${pageSize}`);
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '실험 목록을 불러오지 못했습니다.'));
	}
	const body: unknown = await response.json();
	if (
		typeof body !== 'object' ||
		body === null ||
		!('content' in body) ||
		!Array.isArray(body.content) ||
		!body.content.every(isExperiment) ||
		!('totalPages' in body) ||
		typeof body.totalPages !== 'number' ||
		!Number.isInteger(body.totalPages) ||
		body.totalPages < 0
	) {
		throw new Error('서버에서 올바르지 않은 실험 목록을 받지 못했습니다.');
	}
	return { content: body.content, totalPages: body.totalPages };
}

function isExperiment(value: unknown): value is Experiment {
	return typeof value === 'object' &&
		value !== null &&
		'firstRunId' in value && typeof value.firstRunId === 'number' &&
		'runId' in value && typeof value.runId === 'number' &&
		'round' in value && typeof value.round === 'number' &&
		'status' in value && typeof value.status === 'string' &&
		'state' in value && ['in_progress', 'awaiting_approval', 'completed', 'stopped'].includes(String(value.state)) &&
		'endType' in value && (typeof value.endType === 'string' || value.endType === null) &&
		'stale' in value && typeof value.stale === 'boolean' &&
		'agentUnreachable' in value && typeof value.agentUnreachable === 'boolean' &&
		'hasResult' in value && typeof value.hasResult === 'boolean' &&
		'projectTitle' in value && typeof value.projectTitle === 'string' &&
		'taskGoal' in value && typeof value.taskGoal === 'string' &&
		'mode' in value && typeof value.mode === 'string' &&
		'progress' in value && (typeof value.progress === 'number' || value.progress === null) &&
		'personaCount' in value && typeof value.personaCount === 'number' &&
		'elapsedSeconds' in value && typeof value.elapsedSeconds === 'number' &&
		'createdAt' in value && typeof value.createdAt === 'string';
}

function isRoundMetrics(value: unknown): value is RoundMetrics {
	return typeof value === 'object' &&
		value !== null &&
		'successRate' in value && (typeof value.successRate === 'number' || value.successRate === null) &&
		'avgSteps' in value && (typeof value.avgSteps === 'number' || value.avgSteps === null) &&
		'avgBacktracks' in value && (typeof value.avgBacktracks === 'number' || value.avgBacktracks === null) &&
		'avgSeconds' in value && (typeof value.avgSeconds === 'number' || value.avgSeconds === null) &&
		'tokens' in value && (typeof value.tokens === 'number' || value.tokens === null) &&
		'costUsd' in value && (typeof value.costUsd === 'number' || value.costUsd === null);
}

function isExperimentRound(value: unknown): value is ExperimentRound {
	return typeof value === 'object' &&
		value !== null &&
		'runId' in value && typeof value.runId === 'number' &&
		'round' in value && typeof value.round === 'number' &&
		'status' in value && typeof value.status === 'string' &&
		'appliedImprovementId' in value && (typeof value.appliedImprovementId === 'number' || value.appliedImprovementId === null) &&
		'createdAt' in value && typeof value.createdAt === 'string' &&
		'finishedAt' in value && (typeof value.finishedAt === 'string' || value.finishedAt === null) &&
		'metrics' in value && (value.metrics === null || isRoundMetrics(value.metrics));
}

function isExperimentStats(value: unknown): value is ExperimentStats {
	return typeof value === 'object' &&
		value !== null &&
		'totalCount' in value && typeof value.totalCount === 'number' &&
		'inProgressCount' in value && typeof value.inProgressCount === 'number' &&
		'completedCount' in value && typeof value.completedCount === 'number' &&
		'completedThisWeekCount' in value && typeof value.completedThisWeekCount === 'number' &&
		'awaitingApprovalCount' in value && typeof value.awaitingApprovalCount === 'number' &&
		'totalTokens' in value && typeof value.totalTokens === 'number' &&
		'thisWeekFrom' in value && typeof value.thisWeekFrom === 'string';
}

export async function fetchExperiments(): Promise<Experiment[]> {
	return (await fetchExperimentPage(0)).content;
}

export async function fetchExperimentStats(): Promise<ExperimentStats> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/runs/stats`);
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '실험 통계를 불러오지 못했습니다.'));
	}
	const body: unknown = await response.json();
	if (!isExperimentStats(body)) {
		throw new Error('서버에서 올바르지 않은 실험 통계를 받지 못했습니다.');
	}
	return body;
}

export async function fetchExperimentById(firstRunId: number): Promise<Experiment | null> {
	const firstPage = await fetchExperimentPage(0);
	const firstMatch = firstPage.content.find((item) => item.firstRunId === firstRunId);
	if (firstMatch) return firstMatch;

	for (let page = 1; page < firstPage.totalPages; page += 1) {
		const nextPage = await fetchExperimentPage(page);
		const match = nextPage.content.find((item) => item.firstRunId === firstRunId);
		if (match) return match;
	}
	return null;
}

export async function fetchExperimentRounds(firstRunId: number): Promise<ExperimentRounds> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/runs/${firstRunId}/rounds`);
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '실험 회차를 불러오지 못했습니다.'));
	}
	const body: unknown = await response.json();
	if (
		typeof body !== 'object' ||
		body === null ||
		!('rounds' in body) ||
		!Array.isArray(body.rounds) ||
		!body.rounds.every(isExperimentRound) ||
		!('awaitingApproval' in body) ||
		typeof body.awaitingApproval !== 'boolean'
	) {
		throw new Error('서버에서 올바르지 않은 실험 회차 정보를 받지 못했습니다.');
	}
	return { rounds: body.rounds, awaitingApproval: body.awaitingApproval };
}

export async function cancelExperiment(firstRunId: number): Promise<void> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/runs/${firstRunId}/cancel`, {
		method: 'POST',
	});
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '실험 취소를 요청하지 못했습니다.'));
	}
}
