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
			typeof item.createdAt !== 'string'
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
		};
	});

	return { content, page: body.page, size: body.size, totalElements: body.totalElements, totalPages: body.totalPages };
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

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null;
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

export { API_BASE_URL };
