import { useEffect, useRef, useState } from 'react';

type GoogleCredentialResponse = {
	credential: string;
};

type GoogleIdentityApi = {
	initialize: (options: {
		client_id: string;
		callback: (response: GoogleCredentialResponse) => void;
	}) => void;
	renderButton: (
		parent: HTMLElement,
		options: {
			type: 'standard';
			theme: 'outline';
			size: 'large';
			text: 'signin_with' | 'signup_with';
			shape: 'pill';
			width: number;
		},
	) => void;
};

declare global {
	interface Window {
		google?: {
			accounts: {
				id: GoogleIdentityApi;
			};
		};
	}
}

const GOOGLE_SCRIPT_URL = 'https://accounts.google.com/gsi/client';
let googleScriptPromise: Promise<void> | undefined;

function loadGoogleIdentityServices(): Promise<void> {
	if (window.google?.accounts.id) return Promise.resolve();
	if (googleScriptPromise) return googleScriptPromise;

	googleScriptPromise = new Promise((resolve, reject) => {
		const script = document.createElement('script');
		script.src = GOOGLE_SCRIPT_URL;
		script.async = true;
		script.defer = true;
		script.onload = () => {
			if (window.google?.accounts.id) resolve();
			else reject(new Error('Google 로그인 SDK를 불러오지 못했습니다.'));
		};
		script.onerror = () => {
			googleScriptPromise = undefined;
			reject(new Error('Google 로그인 SDK를 불러오지 못했습니다.'));
		};
		document.head.appendChild(script);
	});

	return googleScriptPromise;
}

type GoogleSignInButtonProps = {
	text: 'signin_with' | 'signup_with';
	onCredential: (idToken: string) => Promise<void>;
	onError: (message: string) => void;
};

export default function GoogleSignInButton({ text, onCredential, onError }: GoogleSignInButtonProps) {
	const buttonRef = useRef<HTMLDivElement>(null);
	const onCredentialRef = useRef(onCredential);
	const onErrorRef = useRef(onError);
	const [loadError, setLoadError] = useState('');
	const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;

	useEffect(() => {
		onCredentialRef.current = onCredential;
	}, [onCredential]);

	useEffect(() => {
		onErrorRef.current = onError;
	}, [onError]);

	useEffect(() => {
		let active = true;

		if (!clientId) {
			return () => {
				active = false;
			};
		}

		loadGoogleIdentityServices()
			.then(() => {
				if (!active || !buttonRef.current || !window.google) return;

				window.google.accounts.id.initialize({
					client_id: clientId,
					callback: ({ credential }) => {
						void onCredentialRef.current(credential).catch((error: unknown) => {
							onErrorRef.current(error instanceof Error ? error.message : 'Google 로그인에 실패했습니다.');
						});
					},
				});
				window.google.accounts.id.renderButton(buttonRef.current, {
					type: 'standard',
					theme: 'outline',
					size: 'large',
					text,
					shape: 'pill',
					width: 236,
				});
				setLoadError('');
			})
			.catch((error: unknown) => {
				if (active) setLoadError(error instanceof Error ? error.message : 'Google 로그인 SDK를 불러오지 못했습니다.');
			});

		return () => {
			active = false;
		};
	}, [clientId, text]);

	const displayedError = clientId
		? loadError
		: 'Google 로그인을 사용하려면 VITE_GOOGLE_CLIENT_ID 설정이 필요합니다.';

	return (
		<div className="google-signin">
			<div ref={buttonRef} className="google-signin-button" />
			{displayedError && <p className="google-signin-error" role="status">{displayedError}</p>}
		</div>
	);
}
