import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import BrandLogo from '../components/BrandLogo';
import GoogleSignInButton from '../components/GoogleSignInButton';
import { API_BASE_URL, apiErrorMessage, loginWithGoogle } from '../auth';
import './Login.css';
import './SignUp.css';

export default function SignUp() {
	const navigate = useNavigate();
	const [name, setName] = useState('');
	const [email, setEmail] = useState('');
	const [password, setPassword] = useState('');
	const [confirmPassword, setConfirmPassword] = useState('');
	const [showPassword, setShowPassword] = useState(false);
	const [showConfirmPassword, setShowConfirmPassword] = useState(false);
	const [message, setMessage] = useState('');
	const [loading, setLoading] = useState(false);

	const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
		event.preventDefault();
		setMessage('');

		if (password !== confirmPassword) {
			setMessage('Passwords do not match.');
			return;
		}

		setLoading(true);
		try {
			const response = await fetch(`${API_BASE_URL}/api/auth/signup`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email, password, name }),
			});

			if (response.status !== 201) {
				throw new Error(await apiErrorMessage(response, '회원가입에 실패했습니다.'));
			}

			const body: unknown = await response.json();
			if (
				typeof body !== 'object' ||
				body === null ||
				!('userId' in body) ||
				typeof body.userId !== 'number'
			) {
				throw new Error('서버에서 올바르지 않은 회원가입 응답을 받았습니다.');
			}

			navigate('/login', { replace: true, state: { signupSuccess: true } });
		} catch (error: unknown) {
			setMessage(error instanceof Error ? error.message : '회원가입 중 오류가 발생했습니다.');
		} finally {
			setLoading(false);
		}
	};

	const handleGoogleSignUp = async (idToken: string) => {
		setMessage('');
		setLoading(true);
		try {
			await loginWithGoogle(idToken);
			navigate('/dashboard', { replace: true });
		} finally {
			setLoading(false);
		}
	};

	return (
		<main className="login-screen signup-screen">
			<section className="login-layout" aria-label="UXight sign up">
				<div className="login-intro">
					<div className="intro-content">
						<BrandLogo variant="dark-bg" size="hero" className="brand-light" />
						<h2>Ship it. But test it with 5 people first.</h2>
						<p>Give us a URL and a task. Persona agents will walk through it and show you exactly where they got stuck.</p>
					</div>
				</div>

				<section className="login-panel signup-panel" aria-labelledby="signup-heading">
					<div className="login-panel-content signup-panel-content">
						<header className="login-header signup-header">
							<h1 id="signup-heading">Sign Up!</h1>
						</header>

						{message && <p className="signup-message" role="alert">{message}</p>}

						<form className="signup-form" onSubmit={handleSubmit}>
							<label className="visually-hidden" htmlFor="signup-name">Name</label>
							<input
								className="ui-input"
								id="signup-name"
								name="name"
								type="text"
								autoComplete="name"
								maxLength={100}
								required
								placeholder="Name"
								value={name}
								onChange={(event) => setName(event.target.value)}
							/>

							<label className="visually-hidden" htmlFor="signup-email">Email</label>
							<input
								className="ui-input"
								id="signup-email"
								name="email"
								type="email"
								autoComplete="email"
								required
								placeholder="Email"
								value={email}
								onChange={(event) => setEmail(event.target.value)}
							/>

							<div className="signup-password-field">
								<label className="visually-hidden" htmlFor="signup-password">Password</label>
								<input
								className="ui-input"
									id="signup-password"
									name="password"
									type={showPassword ? 'text' : 'password'}
									autoComplete="new-password"
									minLength={8}
									maxLength={12}
									pattern="(?=.*[a-z])(?=.*\d).{8,12}"
									required
									placeholder="Password"
									value={password}
									onChange={(event) => setPassword(event.target.value)}
								/>
								<button
									type="button"
									className="password-toggle"
									onClick={() => setShowPassword(!showPassword)}
									aria-label={showPassword ? 'Hide password' : 'Show password'}
									aria-pressed={showPassword}
								>
									<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
										<path d="M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6Z" />
										<circle cx="12" cy="12" r="2.6" />
										{!showPassword && <path d="m4 4 16 16" />}
									</svg>
								</button>
							</div>

							<div className="signup-password-field">
								<label className="visually-hidden" htmlFor="signup-confirm-password">Re-enter password</label>
								<input
								className="ui-input"
									id="signup-confirm-password"
									name="confirmPassword"
									type={showConfirmPassword ? 'text' : 'password'}
									autoComplete="new-password"
									minLength={8}
									maxLength={12}
									pattern="(?=.*[a-z])(?=.*\d).{8,12}"
									required
									placeholder="Re-enter password"
									value={confirmPassword}
									onChange={(event) => setConfirmPassword(event.target.value)}
								/>
								<button
									type="button"
									className="password-toggle"
									onClick={() => setShowConfirmPassword(!showConfirmPassword)}
									aria-label={showConfirmPassword ? 'Hide confirmation password' : 'Show confirmation password'}
									aria-pressed={showConfirmPassword}
								>
									<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
										<path d="M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6Z" />
										<circle cx="12" cy="12" r="2.6" />
										{!showConfirmPassword && <path d="m4 4 16 16" />}
									</svg>
								</button>
							</div>

							<button className="ui-button-primary login-submit signup-submit" type="submit" disabled={loading}>
								{loading ? 'Creating account...' : 'Sign Up'}
							</button>
						</form>

						<div className="login-divider signup-divider"><span>OR</span></div>

						<GoogleSignInButton
							text="signup_with"
							onCredential={handleGoogleSignUp}
							onError={setMessage}
						/>

						<p className="signup-prompt signup-login-prompt">
							Already have an account? <Link to="/login" className="text-link signup-link">Log In</Link>
						</p>
					</div>
				</section>
			</section>
		</main>
	);
}
