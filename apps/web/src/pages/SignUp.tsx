import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import './Login.css';
import './SignUp.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8080';

export default function SignUp() {
	const [username, setUsername] = useState('');
	const [email, setEmail] = useState('');
	const [password, setPassword] = useState('');
	const [confirmPassword, setConfirmPassword] = useState('');
	const [showPassword, setShowPassword] = useState(false);
	const [showConfirmPassword, setShowConfirmPassword] = useState(false);
	const [message, setMessage] = useState('');

	const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
		event.preventDefault();
		setMessage('');

		if (password !== confirmPassword) {
			setMessage('Passwords do not match.');
			return;
		}

		setMessage('Account registration is not available yet.');
	};

	const handleGoogleSignUp = () => {
		window.location.assign(`${API_BASE_URL}/api/auth/google`);
	};

	return (
		<main className="login-screen signup-screen">
			<section className="login-layout" aria-label="UXight sign up">
				<div className="login-intro">
					<div className="intro-content">
						<div className="brand brand-light">
							<svg className="brand-mark" viewBox="0 0 48 48" aria-hidden="true">
								<rect className="brand-mark-frame" x="3" y="3" width="42" height="42" rx="13" />
								<path className="brand-mark-u" d="M14 14v14a10 10 0 0 0 20 0V14" />
								<path className="brand-mark-cross" d="m16 16 16 16M32 16 16 32" />
							</svg>
							<span className="brand-name"><span>UX</span>ight</span>
						</div>
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
							<label className="visually-hidden" htmlFor="signup-username">Username</label>
							<input
								id="signup-username"
								name="username"
								type="text"
								autoComplete="username"
								minLength={2}
								maxLength={50}
								required
								placeholder="Username"
								value={username}
								onChange={(event) => setUsername(event.target.value)}
							/>

							<label className="visually-hidden" htmlFor="signup-email">Email</label>
							<input
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
									id="signup-password"
									name="password"
									type={showPassword ? 'text' : 'password'}
									autoComplete="new-password"
									minLength={8}
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
									id="signup-confirm-password"
									name="confirmPassword"
									type={showConfirmPassword ? 'text' : 'password'}
									autoComplete="new-password"
									minLength={8}
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

							<button className="login-submit signup-submit" type="submit">Sign Up</button>
						</form>

						<div className="login-divider signup-divider"><span>OR</span></div>

						  <button type="button" className="google-login" onClick={handleGoogleSignUp}>
							<svg className="google-mark" viewBox="0 0 48 48" aria-hidden="true">
								<path fill="#4285F4" d="M43.6 24.5c0-1.4-.1-2.8-.4-4.1H24v7.8h11a9.4 9.4 0 0 1-4.1 6.2v5.1h6.6c3.9-3.6 6.1-8.8 6.1-15Z" />
								<path fill="#34A853" d="M24 44c5.5 0 10.1-1.8 13.5-4.9l-6.6-5.1c-1.8 1.2-4.1 2-6.9 2-5.3 0-9.8-3.6-11.4-8.4H5.8v5.3A20 20 0 0 0 24 44Z" />
								<path fill="#FBBC05" d="M12.6 27.6a12 12 0 0 1 0-7.2v-5.3H5.8a20 20 0 0 0 0 17.8l6.8-5.3Z" />
								<path fill="#EA4335" d="M24 12c3 0 5.7 1 7.8 3l5.8-5.8A19.5 19.5 0 0 0 24 4 20 20 0 0 0 5.8 15.1l6.8 5.3C14.2 15.6 18.7 12 24 12Z" />
							</svg>
							Sign up with Google
						</button>

						<p className="signup-prompt signup-login-prompt">
							Already have an account? <Link to="/login" className="text-link signup-link">Log In</Link>
						</p>
					</div>
				</section>
			</section>
		</main>
	);
}
