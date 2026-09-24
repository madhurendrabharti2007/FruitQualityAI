import { useState } from 'react';
import { FileStack, UploadCloud, ArrowRight, AlertCircle, LockKeyhole } from 'lucide-react';
import { batchPredict } from '../api/api';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Loader from '../components/Loader';
import { motion } from 'framer-motion';

export default function BatchScan() {
  const { user, loading } = useAuth();
  const [files, setFiles] = useState([]);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');

  const choose = selected => {
    const next = Array.from(selected || [])
      .filter(file => file.type.startsWith('image/') && file.size <= 8 * 1024 * 1024)
      .slice(0, 50);
    setFiles(next);
    setResult(null);
    setError(next.length ? '' : 'Choose up to 50 JPG, PNG, or WEBP images under 8 MB each.');
  };

  const submit = async event => {
    event.preventDefault();
    if (!files.length || busy) return;
    setBusy(true);
    setProgress(0);
    setError('');
    try {
      setResult(
        await batchPredict(files, event =>
          setProgress(Math.round((event.loaded / (event.total || 1)) * 100))
        )
      );
    } catch (err) {
      setError(err.response?.data?.detail || 'The batch could not be processed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="page-shell batch-page">
      <div className="page-intro">
        <p className="eyebrow">
          <FileStack size={15} /> Vendor workspace
        </p>
        <h1>
          Scan a whole
          <br />
          <em>fruit lot.</em>
        </h1>
        <p>
          Upload up to 50 photos for a quick intake report. Not-recognized images remain separate from freshness totals.
        </p>
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
            Batch scanning requires an authenticated vendor account. Please sign in or create an account to get started.
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
          <form onSubmit={submit} className="batch-uploader">
            <label className="batch-dropzone">
              <UploadCloud size={28} />
              <strong>{files.length ? `${files.length} images selected` : 'Drop multiple fruit photos here'}</strong>
              <span>or browse a folder from your device</span>
              <small>JPG, PNG, or WEBP · 50 images max</small>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                onChange={event => choose(event.target.files)}
              />
            </label>
            {busy && (
              <div className="batch-progress">
                <span style={{ width: `${progress}%` }} />
                <strong>Uploading and processing {files.length} images...</strong>
              </div>
            )}
            {error && (
              <p className="inline-error">
                <AlertCircle size={15} /> {error}
              </p>
            )}
            <button className="primary-button" disabled={!files.length || busy}>
              {busy ? 'Processing...' : 'Run batch scan'} <ArrowRight size={16} />
            </button>
          </form>

          {result && (
            <section className="batch-results">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Batch complete</p>
                  <h2>{result.batch_id}</h2>
                </div>
                <Link className="text-button" to="/reports">
                  Open reports <ArrowRight size={15} />
                </Link>
              </div>
              <div className="stat-grid">
                <article>
                  <span>Total images</span>
                  <strong>{result.total}</strong>
                </article>
                <article>
                  <span>Fresh</span>
                  <strong>{result.fresh_count}</strong>
                  <small>{result.fresh_percentage}% of batch</small>
                </article>
                <article>
                  <span>Rotten</span>
                  <strong>{result.rotten_count}</strong>
                  <small>{result.rotten_percentage}% of batch</small>
                </article>
              </div>
              <div className="batch-item-list">
                {result.items.map(item => (
                  <article key={item.filename}>
                    <strong>{item.filename}</strong>
                    <span className={`history-status ${item.status}`}>
                      {item.status === 'not_recognized' ? 'Not recognized' : item.status}{' '}
                      {item.confidence ? `${item.confidence}%` : ''}
                    </span>
                    <small>
                      {item.fruit || 'Upload a clearer single-fruit photo'} · {item.shelf_life_estimate}
                    </small>
                  </article>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </main>
  );
}
