import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import BrandLogo from '../components/BrandLogo';
import GoogleSignInButton from '../components/GoogleSignInButton';
import { API_BASE_URL, apiErrorMessage, loginWithGoogle, setAccessToken } from '../auth';
import './Login.css';

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const signupSuccess = (location.state as { signupSuccess?: boolean } | null)?.signupSuccess === true;

  const handleGoogleLogin = async (idToken: string) => {
    setErrorMsg('');
    setLoading(true);
    try {
      await loginWithGoogle(idToken);
      navigate('/dashboard', { replace: true });
    } finally {
      setLoading(false);
    }
  };

  const handleEmailLogin = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorMsg('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        throw new Error(await apiErrorMessage(res, '로그인에 실패했습니다.'));
      }

      const body: unknown = await res.json();
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
      navigate('/dashboard', { replace: true });
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : '로그인 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-screen">
      <section className="login-layout" aria-label="UXight login">
        <div className="login-intro">
          <div className="intro-content">
            <BrandLogo variant="dark-bg" size="hero" className="brand-light" />
            <h2>Ship it. But test it with 5 people first.</h2>
            <p>Give us a URL and a task. Persona agents will walk through it and show you exactly where they got stuck.</p>
          </div>
        </div>

        <section className="login-panel" aria-labelledby="login-heading">
          <div className="login-panel-content">
            <header className="login-header">
              <h1 id="login-heading">Welcome to</h1>
              <BrandLogo variant="light-bg" size="form" className="brand-dark" suffix="!" />
            </header>

            {errorMsg && <p className="login-error" role="alert">{errorMsg}</p>}
            {signupSuccess && <p className="login-success" role="status">Account created. Please log in.</p>}

            <form onSubmit={handleEmailLogin} className="login-form">
              <label className="visually-hidden" htmlFor="login-email">Email</label>
              <input
                className="ui-input"
                id="login-email"
                type="email"
                autoComplete="email"
                required
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />

              <div className="password-field">
                <label className="visually-hidden" htmlFor="login-password">Password</label>
                <input
                  className="ui-input"
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
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
                    {showPassword && <path d="m4 4 16 16" />}
                  </svg>
                </button>
              </div>

              <button type="button" className="text-link forgot-link" onClick={() => setErrorMsg('Password reset is not available yet.')}>
                Forgot Password?
              </button>

              <button type="submit" className="ui-button-primary login-submit" disabled={loading}>
                {loading ? 'Logging in...' : 'Login'}
              </button>
            </form>

            <div className="login-divider"><span>OR</span></div>

            <GoogleSignInButton
              text="signin_with"
              onCredential={handleGoogleLogin}
              onError={setErrorMsg}
            />

            <p className="signup-prompt">
              Don't have an account?{' '}
              <Link to="/signup" className="text-link signup-link">
                Sign Up
              </Link>
            </p>
          </div>
        </section>
      </section>
    </main>
  );
}