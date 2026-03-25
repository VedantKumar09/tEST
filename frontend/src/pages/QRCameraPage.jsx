/**
 * QR Camera Page — 30 FPS via WebSocket
 * Phone streams frames to backend /ws/phone/{sid} using requestAnimationFrame
 */
import { useState, useEffect, useRef } from 'react';

export default function QRCameraPage() {
  const [connected, setConnected] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [error, setError] = useState('');
  const [fps, setFps] = useState(0);
  const [facingMode, setFacingMode] = useState('environment');

  const videoRef = useRef(null);
  const canvasRef = useRef(document.createElement('canvas'));
  const wsRef = useRef(null);
  const rafRef = useRef(null);
  const fpsCountRef = useRef(0);
  const lastFpsTime = useRef(performance.now());

  // Extract student_id from URL
  const getSid = () => new URLSearchParams(window.location.search).get('sid') || 'anonymous';

  // ── WebSocket connection ─────────────────────────────────────────────────────
  const connectWS = () => {
    const sid = getSid();
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/phone/${encodeURIComponent(sid)}`;
    const ws = new WebSocket(url);

    ws.onopen = () => {
      setWsConnected(true);
      setError('');
    };
    ws.onclose = () => {
      setWsConnected(false);
      // Auto-reconnect after 2s
      setTimeout(() => { if (streaming) connectWS(); }, 2000);
    };
    ws.onerror = () => setError('WebSocket error — retrying...');
    wsRef.current = ws;
  };

  // ── Camera ───────────────────────────────────────────────────────────────────
  const startCamera = async (mode = facingMode) => {
    setError('');
    try {
      if (!navigator.mediaDevices?.getUserMedia)
        throw new Error('Camera requires HTTPS. Open via HTTPS link.');
      if (videoRef.current?.srcObject)
        videoRef.current.srcObject.getTracks().forEach(t => t.stop());

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: mode }, width: { ideal: 640 }, height: { ideal: 480 } },
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        // Wait for video metadata to load before starting rAF
        videoRef.current.onloadedmetadata = () => {
          setConnected(true);
          setStreaming(true);
          connectWS();
        };
      }
    } catch (err) {
      setError(err.message.includes('HTTPS') ? err.message : 'Camera access denied. Allow camera permission and retry.');
    }
  };

  // ── requestAnimationFrame frame sender ───────────────────────────────────────
  useEffect(() => {
    if (!streaming) return;

    const canvas = canvasRef.current;
    canvas.width = 320;
    canvas.height = 240;
    const ctx = canvas.getContext('2d');

    const sendFrame = () => {
      if (!streaming) return;

      if (videoRef.current && videoRef.current.readyState >= 2 &&
          wsRef.current?.readyState === WebSocket.OPEN) {
        ctx.drawImage(videoRef.current, 0, 0, 320, 240);
        const frame = canvas.toDataURL('image/jpeg', 0.5);
        wsRef.current.send(frame);

        // FPS counter
        fpsCountRef.current++;
        const now = performance.now();
        if (now - lastFpsTime.current >= 1000) {
          setFps(fpsCountRef.current);
          fpsCountRef.current = 0;
          lastFpsTime.current = now;
        }
      }

      rafRef.current = requestAnimationFrame(sendFrame);
    };

    rafRef.current = requestAnimationFrame(sendFrame);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [streaming]);

  // ── Cleanup ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (wsRef.current) wsRef.current.close();
      if (videoRef.current?.srcObject)
        videoRef.current.srcObject.getTracks().forEach(t => t.stop());
    };
  }, []);

  const switchCamera = () => {
    const next = facingMode === 'environment' ? 'user' : 'environment';
    setFacingMode(next);
    startCamera(next);
  };

  return (
    <div className="qr-camera-page">
      <div className="glass-card qr-camera-card">
        <div style={{ fontSize: '40px', marginBottom: '12px' }}>📱</div>
        <h1 style={{ fontSize: '20px', fontWeight: 800, marginBottom: '6px' }}>MindMesh — Secondary Camera</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginBottom: '20px' }}>
          Keep this page open during the exam. Streaming at up to 30 FPS.
        </p>

        {error && <div className="alert alert-error" style={{ marginBottom: 16, fontSize: 12 }}>{error}</div>}

        {/* Camera preview */}
        <div className="qr-camera-preview" style={{ border: `2px solid ${wsConnected ? 'var(--success)' : connected ? 'var(--warning)' : 'var(--border)'}` }}>
          <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>

        {/* Status */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
          <span className={`badge ${wsConnected ? 'badge-success' : connected ? 'badge-warning' : 'badge-info'}`}>
            {wsConnected ? '🟢 Streaming Live' : connected ? '⏳ Connecting WS...' : '⏸ Not Started'}
          </span>
          {fps > 0 && (
            <span className="badge badge-info">{fps} FPS</span>
          )}
        </div>

        {!connected ? (
          <button className="btn btn-primary btn-lg" onClick={() => startCamera()} style={{ width: '100%', justifyContent: 'center' }}>
            📹 Start Camera
          </button>
        ) : (
          <button className="btn btn-outline" onClick={switchCamera} style={{ width: '100%', justifyContent: 'center' }}>
            🔄 Flip Camera ({facingMode === 'environment' ? 'Rear → Front' : 'Front → Rear'})
          </button>
        )}

        <p style={{ color: 'var(--text-muted)', fontSize: '11px', marginTop: 20 }}>🧠 MindMesh AI Proctoring Platform</p>
      </div>
    </div>
  );
}
