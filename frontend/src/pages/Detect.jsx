import { useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { LockKeyhole, ArrowRight } from 'lucide-react';
import UploadCard from '../components/UploadCard';
import AutoCapture, { AutoCaptureToggle } from '../components/AutoCapture';
import ResultCard from '../components/ResultCard';
import Loader from '../components/Loader';
import { predictFruit } from '../api/api';
import { useAuth } from '../context/AuthContext';

export default function Detect() {
  const { user, loading } = useAuth();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [autoCaptureEnabled, setAutoCaptureEnabled] = useState(false);
  const inFlight = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const submit = useCallback(async file => {
    if (inFlight.current) return { ok: false, busy: true };
    inFlight.current = true;
    setBusy(true);
    setError('');
    try {
      const prediction = await predictFruit(file);
      if (!mounted.current) return { ok: false, stale: true };
      setResult(prediction);
      return { ok: true };
    } catch (err) {
      if (mounted.current) {
        setError(
          err.response?.data?.detail ||
            (err.request
              ? 'The detector is unavailable right now. Please refresh and try again in a moment.'
              : 'The detector could not process that image.')
        );
      }
      return { ok: false, status: err.response?.status };
    } finally {
      inFlight.current = false;
      if (mounted.current) setBusy(false);
    }
  }, []);

  const reportAutoError = useCallback(error => {
    if (!mounted.current) return;
    setError(
      typeof error === 'string'
        ? error
        : error.response?.data?.detail ||
          (error.request
            ? 'The detector is unavailable right now. Please refresh and try again in a moment.'
            : error.message || 'The detector could not process that image.')
    );
  }, []);

  const autoCaptureToggle = (
    <AutoCaptureToggle enabled={autoCaptureEnabled} onChange={setAutoCaptureEnabled} />
  );

  return (
    <main className="page-shell">
      <div className="page-intro">
        <p className="eyebrow">The quick check</p>
        <h1>
          Let’s inspect
          <br />
          <em>your fruit.</em>
        </h1>
        <p>Use a clear photo with the fruit in frame. Our model will identify its type and look for freshness signals.</p>
      </div>

      {loading ? (
        <Loader />
      ) : !user ? (
        <motion.section
          className="upload-card auth-gate-card"
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="auth-gate-icon">
            <LockKeyhole size={28} />
          </div>
          <h2>Please sign in to use the fruit detector</h2>
          <p>
            Create an account or sign in to inspect produce, verify freshness, and track shelf life records.
          </p>
          <div className="auth-gate-actions">
            <Link to="/signin" className="primary-button">
              Sign In <ArrowRight size={16} />
            </Link>
            <Link to="/signup" className="secondary-button">
              Sign Up
            </Link>
          </div>
        </motion.section>
      ) : (
        <>
          {busy ? (
            <Loader />
          ) : result ? (
            <ResultCard result={result} onReset={() => setResult(null)} />
          ) : (
            <UploadCard onPredict={submit} busy={busy} autoCaptureControl={autoCaptureToggle} />
          )}
          {(busy || result) && <div className="upload-actions">{autoCaptureToggle}</div>}
          <AutoCapture
            enabled={autoCaptureEnabled}
            onPredict={submit}
            onError={reportAutoError}
          />
        </>
      )}

      {error && (
        <motion.div className="error-toast" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          {error}
        </motion.div>
      )}
    </main>
  );
}
