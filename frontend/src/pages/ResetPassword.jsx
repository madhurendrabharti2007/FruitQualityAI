import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowRight, LockKeyhole, CheckCircle2, AlertTriangle } from 'lucide-react';
import { resetPassword } from '../api/api';

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const navigate = useNavigate();

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async event => {
    event.preventDefault();
    setError('');

    if (!token) {
      return setError('No reset token found in URL. Please request a new reset link.');
    }
    if (password.length < 8) {
      return setError('Password must be at least 8 characters long.');
    }
    if (password !== confirmPassword) {
      return setError('Passwords do not match.');
    }

    setBusy(true);
    try {
      await resetPassword({ token, new_password: password });
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reset password. The token may be expired.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth-shell">
      <div className="auth-panel">
        <span className="auth-icon">
          <LockKeyhole size={20} />
        </span>
        <p className="eyebrow">Secure update</p>
        <h1>
          Set a new
          <br />
          <em>password.</em>
        </h1>
        <p className="auth-copy">
          Choose a strong password with at least 8 characters to secure your account.
        </p>

        {!token ? (
          <div className="form-error" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={18} />
            <span>Missing reset token. Please check your reset link or request a new one.</span>
            <Link to="/forgot-password" className="text-button" style={{ marginTop: '8px' }}>
              Request new link
            </Link>
          </div>
        ) : success ? (
          <div className="auth-success-box">
            <CheckCircle2 size={32} className="success-icon" />
            <h3>Password updated</h3>
            <p>Your password has been successfully reset. You can now sign in with your new credentials.</p>
            <button
              onClick={() => navigate('/signin')}
              className="primary-button form-submit"
              style={{ marginTop: '16px' }}
            >
              Sign in now <ArrowRight size={16} />
            </button>
          </div>
        ) : (
          <form onSubmit={submit}>
            {error && <div className="form-error">{error}</div>}
            <label>
              New password
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={event => setPassword(event.target.value)}
                placeholder="At least 8 characters"
              />
            </label>
            <label>
              Confirm new password
              <input
                type="password"
                required
                minLength={8}
                value={confirmPassword}
                onChange={event => setConfirmPassword(event.target.value)}
                placeholder="Re-enter your new password"
              />
            </label>
            <button className="primary-button form-submit" disabled={busy}>
              {busy ? 'Updating password...' : 'Reset password'} <ArrowRight size={16} />
            </button>
          </form>
        )}

        <p className="auth-switch">
          Back to <Link to="/signin">Sign in</Link>
        </p>
      </div>
    </main>
  );
}
