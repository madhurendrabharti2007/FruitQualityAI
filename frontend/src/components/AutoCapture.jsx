import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/api';

const SAMPLE_WIDTH = 64;
const SAMPLE_HEIGHT = 48;
const SAMPLE_INTERVAL = 100;
const PIXEL_THRESHOLD = 25;
const TRIGGER_PERCENT_DEFAULT = 3;
const EMPTY_PERCENT = 1.5;
const EMPTY_DURATION = 600;
const BACKGROUND_REFRESH_DURATION = 1000;
const CAPTURE_WINDOW = 600;
const MIN_COOLDOWN = 1500;
const ERROR_COOLDOWN = 3000;

export function AutoCaptureToggle({ enabled, onChange }) {
  return (
    <button
      type="button"
      className={enabled ? 'primary-button' : 'secondary-button'}
      role="switch"
      aria-checked={enabled}
      onClick={() => onChange(!enabled)}
    >
      Auto capture
    </button>
  );
}

function toGrayscale(video, canvas) {
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context) return null;
  context.drawImage(video, 0, 0, SAMPLE_WIDTH, SAMPLE_HEIGHT);
  const { data } = context.getImageData(0, 0, SAMPLE_WIDTH, SAMPLE_HEIGHT);
  const grayscale = new Uint8Array(SAMPLE_WIDTH * SAMPLE_HEIGHT);
  for (let i = 0; i < grayscale.length; i += 1) {
    const offset = i * 4;
    grayscale[i] = Math.round(data[offset] * 0.299 + data[offset + 1] * 0.587 + data[offset + 2] * 0.114);
  }
  return grayscale;
}

function motionPercent(frame, background) {
  let changedPixels = 0;
  for (let i = 0; i < frame.length; i += 1) {
    if (Math.abs(frame[i] - background[i]) > PIXEL_THRESHOLD) changedPixels += 1;
  }
  return (changedPixels / frame.length) * 100;
}

function updateBackground(background, frame) {
  for (let i = 0; i < background.length; i += 1) {
    background[i] = Math.round(background[i] + (frame[i] - background[i]) * 0.02);
  }
}

function snapshotFrame(video) {
  if (!video.videoWidth || !video.videoHeight) return null;
  const scale = Math.min(1, 1024 / Math.max(video.videoWidth, video.videoHeight));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  const context = canvas.getContext('2d');
  if (!context) return null;
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas;
}

function canvasToFile(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(blob => {
      if (!blob) {
        reject(new Error('The photo could not be captured. Please try again.'));
        return;
      }
      resolve(new File([blob], `auto-capture-${Date.now()}.jpg`, { type: 'image/jpeg' }));
    }, 'image/jpeg', 0.85);
  });
}

function captureVideoFrame(video) {
  const canvas = snapshotFrame(video);
  if (!canvas) return Promise.reject(new Error('The camera is not ready yet. Please wait a moment and try again.'));
  return canvasToFile(canvas);
}

export default function AutoCapture({ enabled, onPredict, onError }) {
  const videoRef = useRef(null);
  const sampleCanvasRef = useRef(null);
  const streamRef = useRef(null);
  const sessionRef = useRef(0);
  const triggerPercentRef = useRef(TRIGGER_PERCENT_DEFAULT);
  const backgroundRef = useRef(null);
  const emptySinceRef = useRef(null);
  const backgroundRefreshedRef = useRef(false);
  const aboveSamplesRef = useRef(0);
  const belowSinceRef = useRef(null);
  const armedRef = useRef(true);
  const objectPresentRef = useRef(false);
  const cooldownUntilRef = useRef(0);
  const captureWindowRef = useRef(null);
  const predictionInProgressRef = useRef(false);
  const pendingCaptureRef = useRef(null);
  const irRequestInProgressRef = useRef(false);
  const previousIrDetectedRef = useRef(false);
  const [triggerMode, setTriggerMode] = useState('camera');
  const [sensitivity, setSensitivity] = useState(72);
  const [cameraReady, setCameraReady] = useState(false);
  const [status, setStatus] = useState('Waiting for fruit');
  const [motionScore, setMotionScore] = useState(0);
  const [captureCount, setCaptureCount] = useState(0);
  const [debugVisible, setDebugVisible] = useState(true);

  const triggerPercent = 8 - ((sensitivity - 1) * 7) / 99;
  triggerPercentRef.current = triggerPercent;

  const reportError = useCallback(error => {
    onError(error);
  }, [onError]);

  useEffect(() => {
    if (!enabled) {
      setCameraReady(false);
      setStatus('Waiting for fruit');
      return undefined;
    }

    const session = sessionRef.current + 1;
    sessionRef.current = session;
    let cancelled = false;
    let restartTimer;
    let acquiredStream;
    let permissionDenied = false;
    let cameraErrorReported = false;

    setCameraReady(false);
    setStatus('Waiting for fruit');
    setMotionScore(0);
    setCaptureCount(0);
    backgroundRef.current = null;
    emptySinceRef.current = null;
    backgroundRefreshedRef.current = false;
    aboveSamplesRef.current = 0;
    belowSinceRef.current = null;
    armedRef.current = true;
    objectPresentRef.current = false;
    cooldownUntilRef.current = 0;
    captureWindowRef.current = null;
    predictionInProgressRef.current = false;
    pendingCaptureRef.current = null;
    previousIrDetectedRef.current = false;

    const startCamera = async () => {
      if (cancelled || permissionDenied) return;
      if (!navigator.mediaDevices?.getUserMedia) {
        permissionDenied = true;
        setStatus('Camera permission needed');
        reportError('Camera access is unavailable in this browser or page. Use a secure connection to enable it.');
        return;
      }

      try {
        acquiredStream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: { facingMode: { ideal: 'environment' } },
        });
        if (cancelled || sessionRef.current !== session) {
          acquiredStream.getTracks().forEach(track => track.stop());
          return;
        }

        streamRef.current = acquiredStream;
        const video = videoRef.current;
        if (!video) throw new Error('The camera preview could not be started. Please try again.');
        video.srcObject = acquiredStream;
        await video.play();
        if (cancelled || sessionRef.current !== session) return;
        cameraErrorReported = false;
        setCameraReady(true);

        acquiredStream.getVideoTracks().forEach(track => {
          track.addEventListener('ended', () => {
            if (cancelled || sessionRef.current !== session) return;
            setCameraReady(false);
            acquiredStream.getTracks().forEach(activeTrack => activeTrack.stop());
            if (streamRef.current === acquiredStream) streamRef.current = null;
            restartTimer = window.setTimeout(startCamera, 1000);
          }, { once: true });
        });
      } catch (error) {
        acquiredStream?.getTracks().forEach(track => track.stop());
        if (streamRef.current === acquiredStream) streamRef.current = null;
        if (cancelled || sessionRef.current !== session) return;
        if (error.name === 'NotAllowedError' || error.name === 'SecurityError') {
          permissionDenied = true;
          setStatus('Camera permission needed');
        } else {
          if (!cameraErrorReported) {
            cameraErrorReported = true;
            reportError(error.message || 'The camera could not be opened. Please try again.');
          }
          restartTimer = window.setTimeout(startCamera, 1000);
        }
      }
    };

    void startCamera();
    return () => {
      cancelled = true;
      sessionRef.current += 1;
      window.clearTimeout(restartTimer);
      acquiredStream?.getTracks().forEach(track => track.stop());
      if (streamRef.current === acquiredStream) streamRef.current = null;
      if (videoRef.current) videoRef.current.srcObject = null;
    };
  }, [enabled, reportError]);

  const runPrediction = useCallback(async (file, session) => {
    if (predictionInProgressRef.current) {
      if (!pendingCaptureRef.current) pendingCaptureRef.current = file;
      return;
    }

    predictionInProgressRef.current = true;
    setStatus('Analysing');
    setCaptureCount(count => count + 1);
    let failed = false;
    try {
      const outcome = await onPredict(file);
      failed = outcome?.ok === false;
    } catch (error) {
      failed = true;
      if (sessionRef.current === session) reportError(error);
    } finally {
      if (sessionRef.current !== session) return;
      cooldownUntilRef.current = Date.now() + (failed ? ERROR_COOLDOWN : MIN_COOLDOWN);
      predictionInProgressRef.current = false;
      const pending = pendingCaptureRef.current;
      pendingCaptureRef.current = null;
      if (pending) {
        void runPrediction(pending, session);
      } else if (!objectPresentRef.current) {
        setStatus('Waiting for fruit');
      } else {
        setStatus('Remove object');
      }
    }
  }, [onPredict, reportError]);

  const queueSnapshot = useCallback(async (snapshot, session) => {
    if (!snapshot || sessionRef.current !== session) return;
    try {
      const file = await canvasToFile(snapshot);
      if (sessionRef.current !== session) return;
      if (predictionInProgressRef.current) {
        if (!pendingCaptureRef.current) pendingCaptureRef.current = file;
      } else {
        void runPrediction(file, session);
      }
    } catch (error) {
      if (sessionRef.current !== session) return;
      cooldownUntilRef.current = Date.now() + ERROR_COOLDOWN;
      reportError(error);
      setStatus(objectPresentRef.current ? 'Remove object' : 'Waiting for fruit');
    }
  }, [reportError, runPrediction]);

  useEffect(() => {
    if (!enabled || !cameraReady) return undefined;
    const session = sessionRef.current;
    const interval = window.setInterval(() => {
      const video = videoRef.current;
      const sampleCanvas = sampleCanvasRef.current;
      if (!video?.videoWidth || !sampleCanvas) return;
      try {
        const frame = toGrayscale(video, sampleCanvas);
        if (!frame) return;
        if (!backgroundRef.current) {
          backgroundRef.current = frame;
          emptySinceRef.current = Date.now();
          setMotionScore(0);
          return;
        }

        const score = motionPercent(frame, backgroundRef.current);
        setMotionScore(score);
        const now = Date.now();

        if (triggerMode === 'camera') {
          if (score < EMPTY_PERCENT) {
            if (emptySinceRef.current === null) emptySinceRef.current = now;
            if (belowSinceRef.current === null) belowSinceRef.current = now;
            updateBackground(backgroundRef.current, frame);

            const emptyFor = now - emptySinceRef.current;
            if (emptyFor >= BACKGROUND_REFRESH_DURATION && !backgroundRefreshedRef.current) {
              backgroundRef.current = frame;
              backgroundRefreshedRef.current = true;
            }
            if (now - belowSinceRef.current >= EMPTY_DURATION) {
              objectPresentRef.current = false;
              if (now >= cooldownUntilRef.current) armedRef.current = true;
              if (!captureWindowRef.current && !predictionInProgressRef.current) {
                setStatus('Waiting for fruit');
              }
            }
          } else {
            emptySinceRef.current = null;
            backgroundRefreshedRef.current = false;
            belowSinceRef.current = null;
          }

          const windowState = captureWindowRef.current;
          if (windowState) {
            if (score > windowState.bestScore) {
              const bestFrame = snapshotFrame(video);
              if (bestFrame) {
                windowState.bestScore = score;
                windowState.bestFrame = bestFrame;
              }
            }
            if (now >= windowState.endsAt) {
              captureWindowRef.current = null;
              setStatus('Capturing');
              void queueSnapshot(windowState.bestFrame, session);
            } else {
              setStatus('Object detected');
            }
          }

          if (score >= triggerPercentRef.current) {
            aboveSamplesRef.current += 1;
            if (aboveSamplesRef.current >= 2 && armedRef.current && now >= cooldownUntilRef.current) {
              armedRef.current = false;
              objectPresentRef.current = true;
              const initialFrame = snapshotFrame(video);
              captureWindowRef.current = {
                endsAt: now + CAPTURE_WINDOW,
                bestScore: score,
                bestFrame: initialFrame,
              };
              setStatus('Object detected');
            }
          } else {
            aboveSamplesRef.current = 0;
          }
        } else if (captureWindowRef.current) {
          const windowState = captureWindowRef.current;
          if (now >= windowState.endsAt) {
            captureWindowRef.current = null;
            setStatus('Capturing');
            void queueSnapshot(windowState.bestFrame, session);
          } else {
            const currentFrame = snapshotFrame(video);
            if (currentFrame && score > windowState.bestScore) {
              windowState.bestScore = score;
              windowState.bestFrame = currentFrame;
            }
          }
        }
      } catch (error) {
        reportError(error);
      }
    }, SAMPLE_INTERVAL);
    return () => window.clearInterval(interval);
  }, [enabled, cameraReady, triggerMode, queueSnapshot, reportError]);

  useEffect(() => {
    if (!enabled || !cameraReady || triggerMode !== 'ir') return undefined;
    const session = sessionRef.current;
    const pollIrStatus = async () => {
      if (irRequestInProgressRef.current) return;
      irRequestInProgressRef.current = true;
      try {
        const response = await api.get('/hardware/ir-status');
        if (sessionRef.current !== session) return;
        const { object_detected: detected, seconds_since_update: age } = response.data;
        if (detected) {
          if (!previousIrDetectedRef.current && typeof age === 'number' && age < 10 &&
            armedRef.current && Date.now() >= cooldownUntilRef.current) {
            armedRef.current = false;
            objectPresentRef.current = true;
            const snapshot = snapshotFrame(videoRef.current);
            setStatus('Capturing');
            void queueSnapshot(snapshot, session);
          } else if (objectPresentRef.current && !predictionInProgressRef.current) {
            setStatus('Remove object');
          }
        } else {
          belowSinceRef.current ??= Date.now();
          if (Date.now() - belowSinceRef.current >= EMPTY_DURATION) {
            objectPresentRef.current = false;
            if (Date.now() >= cooldownUntilRef.current) armedRef.current = true;
            if (!predictionInProgressRef.current) setStatus('Waiting for fruit');
          }
        }
        previousIrDetectedRef.current = Boolean(detected);
      } catch (error) {
        if (sessionRef.current === session) reportError(error);
      } finally {
        irRequestInProgressRef.current = false;
      }
    };
    void pollIrStatus();
    const interval = window.setInterval(pollIrStatus, 700);
    return () => window.clearInterval(interval);
  }, [enabled, cameraReady, triggerMode, queueSnapshot, reportError]);

  useEffect(() => {
    if (triggerMode === 'ir') {
      belowSinceRef.current = null;
      previousIrDetectedRef.current = false;
    } else {
      aboveSamplesRef.current = 0;
      belowSinceRef.current = null;
      emptySinceRef.current = Date.now();
      backgroundRefreshedRef.current = false;
    }
  }, [triggerMode]);

  if (!enabled) return null;

  return (
    <section className="upload-card" aria-label="Automatic fruit capture">
      <div style={{ width: '100%', overflow: 'hidden', borderRadius: 16, background: '#151914' }}>
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          aria-label="Live camera preview for automatic capture"
          style={{ display: 'block', width: '100%', maxHeight: 420, objectFit: 'contain' }}
        />
      </div>
      <canvas ref={sampleCanvasRef} width={SAMPLE_WIDTH} height={SAMPLE_HEIGHT} hidden />
      <p role="status" aria-live="polite">{status}</p>
      {debugVisible ? (
        <div className="upload-actions" aria-live="polite">
          <span>Mode: {triggerMode === 'camera' ? 'Camera motion' : 'IR sensor'}</span>
          <span>State: {status}</span>
          <span>Motion: {motionScore.toFixed(1)}% / {triggerPercent.toFixed(1)}%</span>
          <span>Captures: {captureCount}</span>
          <button type="button" className="secondary-button" onClick={() => setDebugVisible(false)}>
            Hide debug
          </button>
        </div>
      ) : (
        <button type="button" className="secondary-button" onClick={() => setDebugVisible(true)}>
          Show debug
        </button>
      )}
      <div className="upload-actions">
        <label>
          Trigger mode{' '}
          <select value={triggerMode} onChange={event => setTriggerMode(event.target.value)}>
            <option value="camera">Camera motion</option>
            <option value="ir">IR sensor</option>
          </select>
        </label>
        {triggerMode === 'camera' && (
          <label>
            Trigger threshold {triggerPercent.toFixed(1)}%
            <input
              type="range"
              min="1"
              max="100"
              value={sensitivity}
              onChange={event => setSensitivity(Number(event.target.value))}
            />
          </label>
        )}
      </div>
    </section>
  );
}
