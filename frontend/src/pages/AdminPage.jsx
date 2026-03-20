import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { adminAPI } from '../services/api';

/* ════════════════════════════════════════════════════════════════════════════
   MindMesh v2 — Admin Dashboard
   Phase 3: Risk timeline chart, evidence viewer, flag/mark, live alerts
   ════════════════════════════════════════════════════════════════════════════ */

// ── Helpers ──────────────────────────────────────────────────────────────────

const fmtTime = (ms) => {
  if (!ms) return '—';
  const d = new Date(ms);
  return d.toLocaleString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
};

const fmtDate = (ms) => {
  if (!ms) return '—';
  return new Date(ms).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: true,
  });
};

const riskColor = (level) => {
  switch (level) {
    case 'Low': return '#22c55e';
    case 'Medium': return '#f59e0b';
    case 'High': return '#f97316';
    case 'Critical': return '#ef4444';
    default: return '#6b7280';
  }
};

const violationLabel = (v) => {
  const map = {
    no_face: '👤 No Face', multiple_faces: '👥 Multiple Faces',
    looking_away: '👀 Looking Away', gaze_offscreen: '🔍 Gaze Offscreen',
    tab_switch: '🔄 Tab Switch', fullscreen_exit: '⛶ Fullscreen Exit',
    copy_paste: '📋 Copy/Paste', right_click: '🖱 Right Click',
  };
  if (v.startsWith('object:')) return `📱 ${v.split(':')[1]}`;
  return map[v] || v;
};

// ── Risk Timeline Canvas Chart ───────────────────────────────────────────────

function TimelineChart({ data }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data || data.length === 0) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const W = canvas.clientWidth;
    const H = canvas.clientHeight;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.scale(dpr, dpr);

    // Clear
    ctx.clearRect(0, 0, W, H);

    // Compute bounds
    const scores = data.map(d => d.score);
    const maxScore = Math.max(...scores, 20);
    const pad = { top: 24, right: 16, bottom: 32, left: 44 };
    const plotW = W - pad.left - pad.right;
    const plotH = H - pad.top - pad.bottom;

    // Y-axis labels
    ctx.fillStyle = '#9ca3af';
    ctx.font = '10px Inter, sans-serif';
    ctx.textAlign = 'right';
    const ySteps = 4;
    for (let i = 0; i <= ySteps; i++) {
      const val = Math.round((maxScore / ySteps) * i);
      const y = pad.top + plotH - (i / ySteps) * plotH;
      ctx.fillText(val.toString(), pad.left - 6, y + 3);
      // Grid line
      ctx.strokeStyle = 'rgba(255,255,255,0.05)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(W - pad.right, y);
      ctx.stroke();
    }

    // Risk level zones (background bands)
    const zones = [
      { max: 20, color: 'rgba(34,197,94,0.06)' },
      { max: 50, color: 'rgba(245,158,11,0.06)' },
      { max: 80, color: 'rgba(249,115,22,0.06)' },
      { max: maxScore, color: 'rgba(239,68,68,0.06)' },
    ];
    zones.forEach(z => {
      const y1 = pad.top + plotH - (Math.min(z.max, maxScore) / maxScore) * plotH;
      const prevMax = zones.indexOf(z) > 0 ? zones[zones.indexOf(z) - 1].max : 0;
      const y2 = pad.top + plotH - (prevMax / maxScore) * plotH;
      ctx.fillStyle = z.color;
      ctx.fillRect(pad.left, y1, plotW, y2 - y1);
    });

    // Plot line
    if (data.length > 1) {
      const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + plotH);
      grad.addColorStop(0, '#ef4444');
      grad.addColorStop(0.4, '#f59e0b');
      grad.addColorStop(1, '#22c55e');

      // Fill area
      ctx.beginPath();
      data.forEach((d, i) => {
        const x = pad.left + (i / (data.length - 1)) * plotW;
        const y = pad.top + plotH - (d.score / maxScore) * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.lineTo(pad.left + plotW, pad.top + plotH);
      ctx.lineTo(pad.left, pad.top + plotH);
      ctx.closePath();
      ctx.fillStyle = 'rgba(99,102,241,0.1)';
      ctx.fill();

      // Stroke line
      ctx.beginPath();
      data.forEach((d, i) => {
        const x = pad.left + (i / (data.length - 1)) * plotW;
        const y = pad.top + plotH - (d.score / maxScore) * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = '#6366f1';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Dots
      data.forEach((d, i) => {
        const x = pad.left + (i / (data.length - 1)) * plotW;
        const y = pad.top + plotH - (d.score / maxScore) * plotH;
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        const sc = d.score;
        ctx.fillStyle = sc <= 20 ? '#22c55e' : sc <= 50 ? '#f59e0b' : sc <= 80 ? '#f97316' : '#ef4444';
        ctx.fill();
      });
    }

    // X-axis labels (first, mid, last)
    ctx.fillStyle = '#9ca3af';
    ctx.font = '9px Inter, sans-serif';
    ctx.textAlign = 'center';
    if (data.length > 0) {
      ctx.fillText(fmtTime(data[0].timestamp), pad.left, H - 6);
      if (data.length > 2) {
        const mid = Math.floor(data.length / 2);
        ctx.fillText(fmtTime(data[mid].timestamp), pad.left + plotW / 2, H - 6);
      }
      ctx.fillText(fmtTime(data[data.length - 1].timestamp), pad.left + plotW, H - 6);
    }
  }, [data]);

  if (!data || data.length === 0) {
    return <div className="timeline-empty">No timeline data available for this session.</div>;
  }

  return (
    <div className="timeline-chart-container">
      <canvas ref={canvasRef} className="timeline-canvas" />
    </div>
  );
}

// ── Evidence Modal ───────────────────────────────────────────────────────────

function EvidenceModal({ evidence, onClose }) {
  const [selectedImg, setSelectedImg] = useState(null);

  if (!evidence) return null;

  return (
    <div className="evidence-modal-overlay" onClick={onClose}>
      <div className="evidence-modal" onClick={e => e.stopPropagation()}>
        <div className="evidence-modal-header">
          <h3>📸 Evidence Snapshots ({evidence.total})</h3>
          <button className="modal-close-btn" onClick={onClose}>✕</button>
        </div>

        {selectedImg ? (
          <div className="evidence-fullview">
            <button className="evidence-back-btn" onClick={() => setSelectedImg(null)}>← Back to grid</button>
            <img src={selectedImg.url} alt={selectedImg.type} className="evidence-full-img" loading="lazy" />
            <div className="evidence-full-meta">
              <span className="evidence-badge">{violationLabel(selectedImg.type)}</span>
              <span>{fmtDate(selectedImg.timestamp)}</span>
            </div>
          </div>
        ) : (
          <div className="evidence-grid">
            {evidence.evidence.length === 0 && <p className="text-muted">No evidence captures found.</p>}
            {evidence.evidence.map((ev, i) => (
              <div key={i} className="evidence-thumb" onClick={() => setSelectedImg(ev)}>
                <img src={ev.url} alt={ev.type} loading="lazy" />
                <div className="evidence-thumb-meta">
                  <span className="evidence-type-label">{violationLabel(ev.type)}</span>
                  <span className="evidence-time-label">{fmtTime(ev.timestamp)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Live Alert Banner ────────────────────────────────────────────────────────

function LiveAlertBanner({ alerts }) {
  if (!alerts || alerts.length === 0) return null;
  const recent = alerts.slice(-3).reverse();

  return (
    <div className="live-alert-banner">
      <span className="live-dot" /> LIVE
      {recent.map((a, i) => (
        <div key={i} className="live-alert-item">
          <span style={{ color: riskColor(a.risk_level) }}>●</span>
          <strong>{a.student_id}</strong>
          {a.violations.map(v => violationLabel(v)).join(', ')}
          <span className="alert-time">{fmtTime(a.timestamp)}</span>
        </div>
      ))}
    </div>
  );
}

// ── Main Admin Page Component ────────────────────────────────────────────────

export default function AdminPage() {
  const { logout } = useAuth();
  const [submissions, setSubmissions] = useState([]);
  const [expanded, setExpanded] = useState(null);   // submission_id
  const [timeline, setTimeline] = useState([]);
  const [evidence, setEvidence] = useState(null);    // for modal
  const [showEvidence, setShowEvidence] = useState(false);
  const [liveAlerts, setLiveAlerts] = useState([]);
  const [sortBy, setSortBy] = useState('time');      // time | risk
  const wsRef = useRef(null);

  // ── Load submissions ──
  const loadSubmissions = useCallback(async () => {
    try {
      const data = await adminAPI.getSubmissions();
      setSubmissions(data);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadSubmissions(); }, [loadSubmissions]);

  // ── WebSocket for live alerts ──
  useEffect(() => {
    let ws;
    let reconnectTimer;

    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      ws = new WebSocket(`${proto}://${window.location.host}/ws/admin/alerts`);
      wsRef.current = ws;

      ws.onmessage = (evt) => {
        try {
          const alert = JSON.parse(evt.data);
          setLiveAlerts(prev => [...prev.slice(-49), alert]);
        } catch { /* ignore */ }
      };

      ws.onclose = () => {
        reconnectTimer = setTimeout(connect, 3000); // auto-reconnect
      };

      ws.onerror = () => ws.close();
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  // ── Expand row → fetch timeline ──
  const toggleExpand = async (sub) => {
    const id = sub.submission_id || sub.student_email || 'demo_001';
    if (expanded === id) {
      setExpanded(null);
      setTimeline([]);
      return;
    }
    setExpanded(id);
    try {
      const tl = await adminAPI.getRiskTimeline(sub.student_name || id);
      setTimeline(tl.timeline || []);
    } catch {
      setTimeline([]);
    }
  };

  // ── Evidence modal ──
  const openEvidence = async (sub) => {
    try {
      const ev = await adminAPI.getEvidence(sub.student_name || sub.student_email || 'demo');
      setEvidence(ev);
      setShowEvidence(true);
    } catch { /* ignore */ }
  };

  // ── Flag / Mark ──
  const handleFlag = async (sub) => {
    const id = sub.submission_id || 'demo_001';
    try {
      await adminAPI.flagSubmission(id);
      loadSubmissions();
    } catch { /* ignore */ }
  };

  const handleMark = async (sub, status) => {
    const id = sub.submission_id || 'demo_001';
    try {
      await adminAPI.markSubmission(id, status);
      loadSubmissions();
    } catch { /* ignore */ }
  };

  // ── Sort ──
  const sorted = [...submissions].sort((a, b) => {
    if (sortBy === 'risk') {
      const ra = a.proctoring_summary?.total_violations || 0;
      const rb = b.proctoring_summary?.total_violations || 0;
      return rb - ra;
    }
    return (b.submitted_at || 0) - (a.submitted_at || 0);
  });

  return (
    <div className="admin-page">
      {/* Header */}
      <div className="admin-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1>🛡️ Admin Dashboard</h1>
            <p>Monitor candidates, review evidence, and manage exam integrity.</p>
          </div>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <select className="admin-sort-select" value={sortBy} onChange={e => setSortBy(e.target.value)}>
              <option value="time">Sort by Time</option>
              <option value="risk">Sort by Risk</option>
            </select>
            <button className="btn btn-secondary" onClick={loadSubmissions}>↻ Refresh</button>
            <button className="btn btn-secondary" onClick={logout}>Logout</button>
          </div>
        </div>
      </div>

      {/* Live Alert Banner */}
      <LiveAlertBanner alerts={liveAlerts} />

      {/* Submissions Table */}
      <div className="table-wrapper card">
        <table className="submissions-table">
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Score</th>
              <th>Risk Level</th>
              <th>Violations</th>
              <th>Status</th>
              <th>Submitted</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((sub, idx) => {
              const id = sub.submission_id || sub.student_email || `sub_${idx}`;
              const riskLevel = sub.proctoring_summary?.risk_level || 'Low';
              const isExpanded = expanded === id;
              return (
                <tr key={id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{sub.student_name || 'Unknown'}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{sub.student_email || ''}</div>
                  </td>
                  <td><strong>{sub.score ?? 0}%</strong></td>
                  <td>
                    <span className="risk-badge" style={{ background: riskColor(riskLevel) + '22', color: riskColor(riskLevel), border: `1px solid ${riskColor(riskLevel)}44` }}>
                      {riskLevel}
                    </span>
                  </td>
                  <td>{sub.proctoring_summary?.total_violations ?? 0}</td>
                  <td>
                    {sub.flagged && <span className="status-badge status-flagged">Flagged</span>}
                    {sub.review_status === 'valid' && <span className="status-badge status-valid">Valid</span>}
                    {sub.review_status === 'invalid' && <span className="status-badge status-invalid">Invalid</span>}
                    {!sub.flagged && !sub.review_status && <span className="status-badge status-pending">Pending</span>}
                  </td>
                  <td style={{ fontSize: '12px' }}>{fmtDate(sub.submitted_at)}</td>
                  <td>
                    <div className="admin-actions">
                      <button className="admin-btn admin-btn-expand" onClick={() => toggleExpand(sub)} title="View details">
                        {isExpanded ? '▲' : '▼'}
                      </button>
                      <button className="admin-btn admin-btn-evidence" onClick={() => openEvidence(sub)} title="View evidence">
                        📸
                      </button>
                      <button className={`admin-btn ${sub.flagged ? 'admin-btn-unflag' : 'admin-btn-flag'}`} onClick={() => handleFlag(sub)} title={sub.flagged ? 'Unflag' : 'Flag'}>
                        🚩
                      </button>
                      <button className="admin-btn admin-btn-valid" onClick={() => handleMark(sub, 'valid')} title="Mark Valid">
                        ✓
                      </button>
                      <button className="admin-btn admin-btn-invalid" onClick={() => handleMark(sub, 'invalid')} title="Mark Invalid">
                        ✗
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {sorted.length === 0 && (
              <tr><td colSpan={7} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>No submissions yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Expanded Detail Panel */}
      {expanded && (
        <div className="detail-panel card">
          <h3 style={{ marginBottom: '16px' }}>📊 Risk Score Timeline</h3>
          <TimelineChart data={timeline} />

          {/* Category scores */}
          {(() => {
            const sub = submissions.find(s => (s.submission_id || s.student_email) === expanded);
            if (!sub) return null;
            return (
              <div className="detail-grid" style={{ marginTop: '20px' }}>
                <div className="detail-stat">
                  <div className="detail-stat-val">{sub.score ?? 0}%</div>
                  <div className="detail-stat-lbl">Overall Score</div>
                </div>
                <div className="detail-stat">
                  <div className="detail-stat-val">{sub.mcq_correct ?? sub.correct ?? 0}/{sub.mcq_total ?? sub.questions_total ?? 0}</div>
                  <div className="detail-stat-lbl">MCQ Correct</div>
                </div>
                <div className="detail-stat">
                  <div className="detail-stat-val">{sub.coding_score ?? 0}%</div>
                  <div className="detail-stat-lbl">Coding Score</div>
                </div>
                <div className="detail-stat">
                  <div className="detail-stat-val">{sub.proctoring_summary?.total_violations ?? 0}</div>
                  <div className="detail-stat-lbl">Violations</div>
                </div>
                <div className="detail-stat">
                  <div className="detail-stat-val">{Math.floor((sub.time_used || 0) / 60)}m {(sub.time_used || 0) % 60}s</div>
                  <div className="detail-stat-lbl">Time Used</div>
                </div>
                <div className="detail-stat">
                  <div className="detail-stat-val" style={{ color: riskColor(sub.proctoring_summary?.risk_level) }}>
                    {sub.proctoring_summary?.risk_level || 'Low'}
                  </div>
                  <div className="detail-stat-lbl">Risk Level</div>
                </div>
              </div>
            );
          })()}

          {/* Violation types */}
          {(() => {
            const sub = submissions.find(s => (s.submission_id || s.student_email) === expanded);
            const types = sub?.proctoring_summary?.violation_types || [];
            if (types.length === 0) return null;
            return (
              <div style={{ marginTop: '12px' }}>
                <strong style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Violation Types</strong>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '8px' }}>
                  {types.map((v, i) => (
                    <span key={i} className="violation-tag">{violationLabel(v)}</span>
                  ))}
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* Evidence Modal */}
      {showEvidence && <EvidenceModal evidence={evidence} onClose={() => setShowEvidence(false)} />}
    </div>
  );
}
