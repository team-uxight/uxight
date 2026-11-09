const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8080';

export type UserRole = 'admin' | 'maintainer' | 'researcher';

export type CurrentUser = {
	userId: number;
	name: string;
	role: UserRole;
};

export type AdminUser = {
	userId: number;
	email: string;
	name: string;
	role: UserRole;
	authProvider: 'local' | 'google';
	isActive: boolean;
	createdAt: string;
	lastLoginAt: string | null;
	totalCostUsd: number;
};

export type PageResponse<T> = {
	content: T[];
	page: number;
	size: number;
	totalElements: number;
	totalPages: number;
};

let accessToken: string | null = null;

export function setAccessToken(token: string) {
	accessToken = token;
}

export function clearAccessToken() {
	accessToken = null;
}

export async function loginWithGoogle(idToken: string): Promise<void> {
	const response = await fetch(`${API_BASE_URL}/api/auth/google`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		credentials: 'include',
		body: JSON.stringify({ idToken }),
	});
	if (!response.ok) {
		// 처음 Google 로 가입한 계정은 운영자가 활성화하기 전까지 비활성이다 (AUT-ERR-005).
		if (response.status === 401 && (await apiErrorCode(response.clone())) === 'AUT-ERR-005') {
			throw new Error('운영자가 승인하면 로그인할 수 있습니다.');
		}
		throw new Error(await apiErrorMessage(response, 'Google 로그인에 실패했습니다.'));
	}

	const body: unknown = await response.json();
	if (
		typeof body !== 'object' ||
		body === null ||
		!('accessToken' in body) ||
		typeof body.accessToken !== 'string' ||
		body.accessToken.length === 0
	) {
		throw new Error('서버에서 올바르지 않은 인증 응답을 받았습니다.');
	}
	setAccessToken(body.accessToken);
}

async function apiErrorCode(response: Response): Promise<string | null> {
	try {
		const body: unknown = await response.json();
		if (typeof body === 'object' && body !== null && 'code' in body && typeof body.code === 'string') return body.code;
	} catch {
		return null;
	}
	return null;
}

export async function apiErrorMessage(response: Response, fallback: string): Promise<string> {
	try {
		const body: unknown = await response.json();
		if (typeof body !== 'object' || body === null) return fallback;

		if ('fieldErrors' in body && Array.isArray(body.fieldErrors)) {
			const firstFieldError = body.fieldErrors.find(
				(error: unknown): error is { message: string } =>
					typeof error === 'object' &&
					error !== null &&
					'message' in error &&
					typeof error.message === 'string',
			);
			if (firstFieldError) return firstFieldError.message;
		}

		if ('message' in body && typeof body.message === 'string') return body.message;
	} catch {
		return fallback;
	}

	return fallback;
}

async function refreshAccessToken(): Promise<string | null> {
	const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
		method: 'POST',
		credentials: 'include',
	});

	if (response.status === 401) {
		clearAccessToken();
		return null;
	}
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '세션을 확인할 수 없습니다.'));
	}

	const body: unknown = await response.json();
	if (
		typeof body !== 'object' ||
		body === null ||
		'accessToken' in body === false ||
		typeof body.accessToken !== 'string' ||
		body.accessToken.length === 0
	) {
		throw new Error('서버에서 올바르지 않은 인증 응답을 받았습니다.');
	}

	accessToken = body.accessToken;
	return accessToken;
}

export async function authenticatedFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
	let token = accessToken ?? await refreshAccessToken();
	const sendRequest = (accessTokenValue: string | null) => {
		const headers = new Headers(init.headers);
		if (accessTokenValue) headers.set('Authorization', `Bearer ${accessTokenValue}`);
		return fetch(input, { ...init, credentials: 'include', headers });
	};

	let response = await sendRequest(token);
	if (response.status !== 401) return response;

	token = await refreshAccessToken();
	if (!token) return response;

	response = await sendRequest(token);
	return response;
}

export async function getCurrentUser(): Promise<CurrentUser> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/users/me`);
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '사용자 정보를 불러오지 못했습니다.'));
	}

	const body: unknown = await response.json();
	if (
		typeof body !== 'object' ||
		body === null ||
		!('userId' in body) ||
		typeof body.userId !== 'number' ||
		!('name' in body) ||
		typeof body.name !== 'string' ||
		!('role' in body) ||
		(body.role !== 'admin' && body.role !== 'maintainer' && body.role !== 'researcher')
	) {
		throw new Error('서버에서 올바르지 않은 사용자 정보를 받았습니다.');
	}

	return { userId: body.userId, name: body.name, role: body.role };
}

export async function getCurrentUserRole(): Promise<UserRole> {
	return (await getCurrentUser()).role;
}

export function getRoleHomePath(role: UserRole): string {
	return role === 'researcher' ? '/dashboard' : '/admin/accounts';
}

export async function getAdminUsers(page = 0, size = 20): Promise<PageResponse<AdminUser>> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/admin/users?page=${page}&size=${size}`);
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '계정 목록을 불러오지 못했습니다.'));
	}

	const body: unknown = await response.json();
	if (
		typeof body !== 'object' ||
		body === null ||
		!('content' in body) ||
		!Array.isArray(body.content) ||
		!('page' in body) ||
		typeof body.page !== 'number' ||
		!('size' in body) ||
		typeof body.size !== 'number' ||
		!('totalElements' in body) ||
		typeof body.totalElements !== 'number' ||
		!('totalPages' in body) ||
		typeof body.totalPages !== 'number'
	) {
		throw new Error('서버에서 올바르지 않은 계정 목록을 받았습니다.');
	}

	const content = body.content.map((item): AdminUser => {
		if (
			typeof item !== 'object' ||
			item === null ||
			!('userId' in item) ||
			typeof item.userId !== 'number' ||
			!('email' in item) ||
			typeof item.email !== 'string' ||
			!('name' in item) ||
			typeof item.name !== 'string' ||
			!('role' in item) ||
			(item.role !== 'admin' && item.role !== 'maintainer' && item.role !== 'researcher') ||
			!('authProvider' in item) ||
			(item.authProvider !== 'local' && item.authProvider !== 'google') ||
			!('isActive' in item) ||
			typeof item.isActive !== 'boolean' ||
			!('createdAt' in item) ||
			typeof item.createdAt !== 'string' ||
			!('lastLoginAt' in item) ||
			(item.lastLoginAt !== null && typeof item.lastLoginAt !== 'string') ||
			!('totalCostUsd' in item) ||
			typeof item.totalCostUsd !== 'number' ||
			!Number.isFinite(item.totalCostUsd) ||
			item.totalCostUsd < 0
		) {
			throw new Error('서버에서 올바르지 않은 계정 정보를 받았습니다.');
		}

		return {
			userId: item.userId,
			email: item.email,
			name: item.name,
			role: item.role,
			authProvider: item.authProvider,
			isActive: item.isActive,
			createdAt: item.createdAt,
			lastLoginAt: item.lastLoginAt,
			totalCostUsd: item.totalCostUsd,
		};
	});

	return { content, page: body.page, size: body.size, totalElements: body.totalElements, totalPages: body.totalPages };
}

export async function createAdminUser(email: string, name: string): Promise<{ userId: number; initialPassword: string }> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/admin/users`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ email, name }),
	});
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '계정을 생성하지 못했습니다.'));
	}

	const body: unknown = await response.json();
	if (
		typeof body !== 'object' ||
		body === null ||
		!('userId' in body) ||
		typeof body.userId !== 'number' ||
		!Number.isSafeInteger(body.userId) ||
		body.userId <= 0 ||
		!('initialPassword' in body) ||
		typeof body.initialPassword !== 'string' ||
		body.initialPassword.length === 0
	) {
		throw new Error('계정 생성 응답이 올바르지 않습니다. 계정 목록을 확인해 주세요.');
	}
	return { userId: body.userId, initialPassword: body.initialPassword };
}

export async function changeUserRole(userId: number, role: UserRole): Promise<UserRole> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/admin/users/${userId}/role`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ role }),
	});
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '계정 역할을 변경하지 못했습니다.'));
	}

	const body: unknown = await response.json();
	if (
		typeof body !== 'object' ||
		body === null ||
		!('userId' in body) ||
		body.userId !== userId ||
		!('role' in body) ||
		(body.role !== 'admin' && body.role !== 'maintainer' && body.role !== 'researcher')
	) {
		throw new Error('서버에서 올바르지 않은 역할 변경 응답을 받았습니다.');
	}

	return body.role;
}

export async function changeUserActive(userId: number, isActive: boolean): Promise<boolean> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/admin/users/${userId}/active`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ isActive }),
	});
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '계정 상태를 변경하지 못했습니다.'));
	}

	const body: unknown = await response.json();
	if (
		typeof body !== 'object' ||
		body === null ||
		!('userId' in body) ||
		body.userId !== userId ||
		!('isActive' in body) ||
		typeof body.isActive !== 'boolean'
	) {
		throw new Error('서버에서 올바르지 않은 계정 상태 응답을 받았습니다.');
	}

	return body.isActive;
}

export type UsageDay = { date: string; costUsd: number; tokens: number; runCount: number };

export type MonthlyUsage = {
	month: string;
	total: { costUsd: number; tokens: number; runCount: number };
	daily: UsageDay[];
};

export type AuditLog = {
	auditLogId: number;
	actor: string;
	action: string;
	target: string;
	ts: string;
};

export type AdminExperiment = {
	firstRunId: number;
	projectTitle: string;
	projectDeleted: boolean;
	ownerEmail: string;
	taskGoal: string;
	mode: string;
	round: number;
	status: 'queued' | 'accepted' | 'running' | 'done' | 'failed' | 'cancelled';
	createdAt: string;
	finishedAt: string | null;
};

export type ImprovementDecision = 'approve' | 'reject';
export type ImprovementPatchKind = 'relabel' | 'move' | 'highlight' | 'help_text';

export const patchKindLabels: Record<ImprovementPatchKind, string> = {
	relabel: '레이블 변경',
	move: '요소 이동',
	highlight: '요소 강조',
	help_text: '도움말 추가',
};

export const decisionLabels: Record<ImprovementDecision, string> = {
	approve: '승인됨',
	reject: '반려됨',
};

export type ImprovementSummary = {
	improvementId: number;
	optionNo: number;
	patchKind: ImprovementPatchKind;
	fixCost: string | null;
	decision: ImprovementDecision | null;
};

export type ImprovementRun = {
	firstRunId: number;
	round: number;
	projectTitle: string;
	taskGoal: string;
	awaitingApproval: boolean;
};

export type ImprovementList = {
	run: ImprovementRun;
	improvements: ImprovementSummary[];
};

export type ImprovementDetail = {
	improvementId: number;
	runId: number;
	optionNo: number;
	patchKind: ImprovementPatchKind;
	patch: Record<string, unknown>;
	rationale: string;
	expectedEffect: string;
	fixCost: string | null;
	findings: { findingId: number; taxonomy: string; severity: string; summary: string }[];
	approval: { decision: ImprovementDecision; note: string | null; decidedAt: string } | null;
	awaitingApproval: boolean;
};

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null;
}

function isImprovementDecision(value: unknown): value is ImprovementDecision {
	return value === 'approve' || value === 'reject';
}

function isImprovementPatchKind(value: unknown): value is ImprovementPatchKind {
	return value === 'relabel' || value === 'move' || value === 'highlight' || value === 'help_text';
}

function isImprovementApproval(value: unknown): value is NonNullable<ImprovementDetail['approval']> {
	return isRecord(value) &&
		isImprovementDecision(value.decision) &&
		(value.note === null || typeof value.note === 'string') &&
		typeof value.decidedAt === 'string';
}

function parseUsageDay(item: unknown): UsageDay {
	if (
		!isRecord(item) ||
		typeof item.date !== 'string' ||
		typeof item.costUsd !== 'number' ||
		typeof item.tokens !== 'number' ||
		typeof item.runCount !== 'number'
	) {
		throw new Error('서버에서 올바르지 않은 사용량 정보를 받았습니다.');
	}
	return { date: item.date, costUsd: item.costUsd, tokens: item.tokens, runCount: item.runCount };
}

export async function getMonthlyUsage(month: string): Promise<MonthlyUsage> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/admin/usage?month=${encodeURIComponent(month)}`);
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '사용량을 불러오지 못했습니다.'));
	}

	const body: unknown = await response.json();
	if (!isRecord(body) || typeof body.month !== 'string' || !Array.isArray(body.daily)) {
		throw new Error('서버에서 올바르지 않은 사용량 정보를 받았습니다.');
	}
	const total = parseUsageDay({ date: '', ...(isRecord(body.total) ? body.total : {}) });
	return {
		month: body.month,
		total: { costUsd: total.costUsd, tokens: total.tokens, runCount: total.runCount },
		daily: body.daily.map(parseUsageDay),
	};
}

export async function getAuditLogs(from: string, to: string, page = 0, size = 20): Promise<PageResponse<AuditLog>> {
	const query = `from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&page=${page}&size=${size}`;
	const response = await authenticatedFetch(`${API_BASE_URL}/api/admin/audit-logs?${query}`);
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '감사 로그를 불러오지 못했습니다.'));
	}

	const body: unknown = await response.json();
	if (
		!isRecord(body) ||
		!Array.isArray(body.content) ||
		typeof body.page !== 'number' ||
		typeof body.size !== 'number' ||
		typeof body.totalElements !== 'number' ||
		typeof body.totalPages !== 'number'
	) {
		throw new Error('서버에서 올바르지 않은 감사 로그를 받았습니다.');
	}

	const content = body.content.map((item): AuditLog => {
		if (
			!isRecord(item) ||
			typeof item.auditLogId !== 'number' ||
			typeof item.actor !== 'string' ||
			typeof item.action !== 'string' ||
			typeof item.target !== 'string' ||
			typeof item.ts !== 'string'
		) {
			throw new Error('서버에서 올바르지 않은 감사 로그를 받았습니다.');
		}
		return { auditLogId: item.auditLogId, actor: item.actor, action: item.action, target: item.target, ts: item.ts };
	});

	return { content, page: body.page, size: body.size, totalElements: body.totalElements, totalPages: body.totalPages };
}

export async function getAdminExperiments(page = 0, size = 20): Promise<PageResponse<AdminExperiment>> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/admin/runs?page=${page}&size=${size}`);
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '최근 실행 목록을 불러오지 못했습니다.'));
	}

	const body: unknown = await response.json();
	if (
		!isRecord(body) ||
		!Array.isArray(body.content) ||
		typeof body.page !== 'number' ||
		typeof body.size !== 'number' ||
		typeof body.totalElements !== 'number' ||
		typeof body.totalPages !== 'number'
	) {
		throw new Error('서버에서 올바르지 않은 최근 실행 목록을 받았습니다.');
	}

	const content = body.content.map((item): AdminExperiment => {
		if (
			!isRecord(item) ||
			typeof item.firstRunId !== 'number' ||
			typeof item.projectTitle !== 'string' ||
			typeof item.projectDeleted !== 'boolean' ||
			typeof item.ownerEmail !== 'string' ||
			typeof item.taskGoal !== 'string' ||
			typeof item.mode !== 'string' ||
			typeof item.round !== 'number' ||
			(item.status !== 'queued' &&
				item.status !== 'accepted' &&
				item.status !== 'running' &&
				item.status !== 'done' &&
				item.status !== 'failed' &&
				item.status !== 'cancelled') ||
			typeof item.createdAt !== 'string' ||
			(item.finishedAt !== null && typeof item.finishedAt !== 'string')
		) {
			throw new Error('서버에서 올바르지 않은 실행 정보를 받았습니다.');
		}

		return {
			firstRunId: item.firstRunId,
			projectTitle: item.projectTitle,
			projectDeleted: item.projectDeleted,
			ownerEmail: item.ownerEmail,
			taskGoal: item.taskGoal,
			mode: item.mode,
			round: item.round,
			status: item.status,
			createdAt: item.createdAt,
			finishedAt: item.finishedAt,
		};
	});

	return { content, page: body.page, size: body.size, totalElements: body.totalElements, totalPages: body.totalPages };
}

export async function getRunImprovements(runId: number): Promise<ImprovementList> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/runs/${runId}/improvements`);
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '개선안 목록을 불러오지 못했습니다.'));
	}

	const body: unknown = await response.json();
	if (
		!isRecord(body) ||
		!isRecord(body.run) ||
		typeof body.run.firstRunId !== 'number' ||
		typeof body.run.round !== 'number' ||
		typeof body.run.projectTitle !== 'string' ||
		typeof body.run.taskGoal !== 'string' ||
		typeof body.run.awaitingApproval !== 'boolean' ||
		!Array.isArray(body.improvements)
	) {
		throw new Error('서버에서 올바르지 않은 개선안 목록을 받았습니다.');
	}

	const improvements = body.improvements.map((item): ImprovementSummary => {
		if (
			!isRecord(item) ||
			typeof item.improvementId !== 'number' ||
			typeof item.optionNo !== 'number' ||
			!isImprovementPatchKind(item.patchKind) ||
			(item.fixCost !== null && typeof item.fixCost !== 'string') ||
			(item.decision !== null && !isImprovementDecision(item.decision))
		) {
			throw new Error('서버에서 올바르지 않은 개선안 정보를 받았습니다.');
		}
		return {
			improvementId: item.improvementId,
			optionNo: item.optionNo,
			patchKind: item.patchKind,
			fixCost: item.fixCost,
			decision: item.decision,
		};
	});

	return {
		run: {
			firstRunId: body.run.firstRunId,
			round: body.run.round,
			projectTitle: body.run.projectTitle,
			taskGoal: body.run.taskGoal,
			awaitingApproval: body.run.awaitingApproval,
		},
		improvements,
	};
}

export async function getImprovementDetail(improvementId: number): Promise<ImprovementDetail> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/improvements/${improvementId}`);
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '개선안 상세를 불러오지 못했습니다.'));
	}

	const body: unknown = await response.json();
	if (
		!isRecord(body) ||
		typeof body.improvementId !== 'number' ||
		typeof body.runId !== 'number' ||
		typeof body.optionNo !== 'number' ||
		!isImprovementPatchKind(body.patchKind) ||
		!isRecord(body.patch) ||
		typeof body.rationale !== 'string' ||
		typeof body.expectedEffect !== 'string' ||
		(body.fixCost !== null && typeof body.fixCost !== 'string') ||
		!Array.isArray(body.findings) ||
		!body.findings.every((finding) =>
			isRecord(finding) &&
			typeof finding.findingId === 'number' &&
			typeof finding.taxonomy === 'string' &&
			typeof finding.severity === 'string' &&
			typeof finding.summary === 'string',
		) ||
		(body.approval !== null && !isImprovementApproval(body.approval)) ||
		typeof body.awaitingApproval !== 'boolean'
	) {
		throw new Error('서버에서 올바르지 않은 개선안 상세를 받았습니다.');
	}

	return {
		improvementId: body.improvementId,
		runId: body.runId,
		optionNo: body.optionNo,
		patchKind: body.patchKind,
		patch: body.patch,
		rationale: body.rationale,
		expectedEffect: body.expectedEffect,
		fixCost: body.fixCost,
		findings: body.findings,
		approval: body.approval,
		awaitingApproval: body.awaitingApproval,
	};
}

export async function decideImprovement(
	runId: number,
	improvementId: number,
	decision: ImprovementDecision,
	note: string,
): Promise<{ approvalId: number; runId: number | null }> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/runs/${runId}/approvals`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ improvementId, decision, note: note.trim() || undefined }),
	});
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '개선안 결정을 저장하지 못했습니다.'));
	}

	const body: unknown = await response.json();
	if (
		!isRecord(body) ||
		typeof body.approvalId !== 'number' ||
		(body.runId !== null && typeof body.runId !== 'number')
	) {
		throw new Error('서버에서 올바르지 않은 개선안 결정 응답을 받았습니다.');
	}
	return { approvalId: body.approvalId, runId: body.runId };
}

export { API_BASE_URL };
