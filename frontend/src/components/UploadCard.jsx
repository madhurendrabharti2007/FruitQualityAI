import { useEffect, useRef, useState } from 'react';
import { Camera, ImagePlus, UploadCloud, X } from 'lucide-react';

export default function UploadCard({ onPredict, busy }) {
  const input = useRef(null);
  const video = useRef(null);
  const stream = useRef(null);
  const mounted = useRef(false);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState('');
  const [error, setError] = useState('');
  const [cameraOpen, setCameraOpen] = useState(false);
  const [captured, setCaptured] = useState(false);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      stream.current?.getTracks().forEach(track => track.stop());
      stream.current = null;
    };
  }, []);

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  useEffect(() => {
    if (!cameraOpen || captured || !stream.current || !video.current) return;
    video.current.srcObject = stream.current;
    video.current.play().catch(() => {
      if (mounted.current) setError('The camera preview could not be started. Please try again.');
    });
  }, [cameraOpen, captured]);

  const choose = selected => {
    const next = selected?.[0];
    if (!next) return;
    if (!next.type.startsWith('image/') || next.size > 8 * 1024 * 1024) {
      setError('Choose a JPG, PNG, or WEBP image under 8 MB.');
      return;
    }
    setError('');
    if (preview) URL.revokeObjectURL(preview);
    setFile(next);
    setPreview(URL.createObjectURL(next));
  };

  const clear = () => {
    if (preview) URL.revokeObjectURL(preview);
    setFile(null);
    setPreview('');
  };

  const openCamera = async () => {
    setError('');
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Camera access is unavailable in this browser or page. Use a secure connection or choose a photo.');
      return;
    }

    stream.current?.getTracks().forEach(track => track.stop());
    stream.current = null;
    try {
      const cameraStream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: 'environment' } },
      });
      if (!mounted.current) {
        cameraStream.getTracks().forEach(track => track.stop());
        return;
      }
      stream.current = cameraStream;
      setCaptured(false);
      setCameraOpen(true);
    } catch (cameraError) {
      if (!mounted.current) return;
      if (cameraError.name === 'NotAllowedError' || cameraError.name === 'SecurityError') {
        setError('Camera permission was denied. Allow camera access in your browser settings, or choose a photo instead.');
      } else if (cameraError.name === 'NotFoundError' || cameraError.name === 'DevicesNotFoundError') {
        setError('No camera is available on this device. Choose a photo instead.');
      } else if (cameraError.name === 'NotReadableError' || cameraError.name === 'TrackStartError') {
        setError('The camera could not be started. It may already be in use by another app.');
      } else {
        setError('The camera could not be opened. Please try again or choose a photo.');
      }
    }
  };

  const closeCamera = () => {
    stream.current?.getTracks().forEach(track => track.stop());
    stream.current = null;
    setCameraOpen(false);
  };

  const capturePhoto = () => {
    const videoElement = video.current;
    if (!videoElement?.videoWidth || !videoElement.videoHeight) {
      setError('The camera is not ready yet. Please wait a moment and try again.');
      return;
    }
    const canvas = document.createElement('canvas');
    canvas.width = videoElement.videoWidth;
    canvas.height = videoElement.videoHeight;
    canvas.getContext('2d')?.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(blob => {
      if (!blob) {
        setError('The photo could not be captured. Please try again.');
        return;
      }
      choose([new File([blob], `camera-${Date.now()}.jpg`, { type: 'image/jpeg' })]);
      setCaptured(true);
    }, 'image/jpeg', 0.92);
  };

  const retakePhoto = () => {
    if (preview) URL.revokeObjectURL(preview);
    setFile(null);
    setPreview('');
    setCaptured(false);
    setError('');
  };

  return (
    <div className="upload-card">
      {preview && !cameraOpen ? (
        <div className="preview">
          <img src={preview} alt="Fruit preview" />
          <button className="icon-button" onClick={clear} aria-label="Remove image"><X size={17} /></button>
        </div>
      ) : !cameraOpen ? (
        <button
          className="dropzone"
          onClick={() => input.current?.click()}
          onDragOver={event => event.preventDefault()}
          onDrop={event => { event.preventDefault(); choose(event.dataTransfer.files); }}
        >
          <span className="upload-icon"><UploadCloud size={25} /></span>
          <strong>Drop a fruit photo here</strong>
          <span>or browse from your device</span>
          <small>JPG, PNG, or WEBP · up to 8 MB</small>
        </button>
      ) : (
        <section aria-label="Camera preview">
          <div style={{ width: '100%', overflow: 'hidden', borderRadius: 16, background: '#151914' }}>
            {captured ? (
              <img src={preview} alt="Captured fruit preview" style={{ display: 'block', width: '100%', maxHeight: 420, objectFit: 'contain' }} />
            ) : (
              <video
                ref={video}
                autoPlay
                muted
                playsInline
                aria-label="Live camera preview"
                style={{ display: 'block', width: '100%', maxHeight: 420, objectFit: 'contain' }}
              />
            )}
          </div>
          <div className="upload-actions">
            {captured ? (
              <button className="secondary-button" onClick={retakePhoto}>Retake</button>
            ) : (
              <button className="primary-button" onClick={capturePhoto}>Capture Photo</button>
            )}
            <button className="secondary-button" onClick={closeCamera}>Close Camera</button>
          </div>
        </section>
      )}
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        onChange={event => choose(event.target.files)}
      />
      {!cameraOpen && (
        <div className="upload-actions">
          <button className="secondary-button" onClick={() => input.current?.click()}>
            <ImagePlus size={17} /> Choose photo
          </button>
          <button className="secondary-button" onClick={openCamera}>
            <Camera size={17} /> Use camera
          </button>
          {file && (
            <button className="primary-button" disabled={busy} onClick={() => onPredict(file)}>
              {busy ? 'Reading...' : 'Check freshness'}
            </button>
          )}
        </div>
      )}
      {cameraOpen && captured && file && (
        <div className="upload-actions">
          <button className="primary-button" disabled={busy} onClick={() => onPredict(file)}>
            {busy ? 'Reading...' : 'Check freshness'}
          </button>
        </div>
      )}
      {error && <p className="upload-error" role="alert">{error}</p>}
    </div>
  );
}
