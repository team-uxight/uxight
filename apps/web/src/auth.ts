const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8080';

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

export { API_BASE_URL };
