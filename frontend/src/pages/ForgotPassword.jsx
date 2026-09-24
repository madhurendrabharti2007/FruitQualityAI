import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, KeyRound, CheckCircle2 } from 'lucide-react';
import { forgotPassword } from '../api/api';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async event => {
    event.preventDefault();
    setError('');
    const cleanEmail = email.trim();
    if (!cleanEmail) return setError('Please enter your email address.');
    setBusy(true);
    try {
      await forgotPassword({ email: cleanEmail });
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to request password reset right now.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth-shell">
      <div className="auth-panel">
        <span className="auth-icon">
          <KeyRound size={20} />
        </span>
        <p className="eyebrow">Account recovery</p>
        <h1>
          Forgot your
          <br />
          <em>password?</em>
        </h1>
        <p className="auth-copy">
          Enter your registered email address and we'll generate a secure link to reset your password.
        </p>

        {success ? (
          <div className="auth-success-box">
            <CheckCircle2 size={32} className="success-icon" />
            <h3>Reset link generated</h3>
            <p>
              If an account with that email exists, a password reset link has been prepared.
            </p>
            <p className="dev-notice">
              <strong>Dev Mode Notice:</strong> Since email services are not configured yet, the password reset link has been printed to the <strong>backend terminal console</strong>.
            </p>
            <Link to="/signin" className="secondary-button" style={{ marginTop: '16px', width: '100%' }}>
              Return to Sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={submit}>
            {error && <div className="form-error">{error}</div>}
            <label>
              Email address
              <input
                type="email"
                required
                value={email}
                onChange={event => setEmail(event.target.value)}
                placeholder="you@example.com"
              />
            </label>
            <button className="primary-button form-submit" disabled={busy}>
              {busy ? 'Sending request...' : 'Send reset link'} <ArrowRight size={16} />
            </button>
          </form>
        )}

        <p className="auth-switch">
          Remembered your password? <Link to="/signin">Sign in</Link>
        </p>
      </div>
    </main>
  );
}
