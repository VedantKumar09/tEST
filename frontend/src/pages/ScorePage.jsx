import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { normalizeCategoryMetrics } from '../utils/categoryScores';

export default function ScorePage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [result, setResult] = useState(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('mm_exam_result');
      if (stored) setResult(JSON.parse(stored));
    } catch {}
  }, []);

  const fmt = (s) => `${Math.floor(s / 60)}m ${s % 60}s`;

  const gradeColor = (s) =>
    s >= 80 ? 'var(--success)' : s >= 50 ? 'var(--warning)' : 'var(--danger)';

  const gradeLabel = (s) => {
    if (s >= 90) return 'Excellent 🏆';
    if (s >= 80) return 'Very Good 🌟';
    if (s >= 70) return 'Good 👍';
    if (s >= 50) return 'Pass 📖';
    return 'Needs Improvement ⚠️';
  };

  const riskLabel = (violations) => {
    if (violations >= 10) return { text: 'High', cls: 'badge-danger' };
    if (violations >= 5) return { text: 'Medium', cls: 'badge-warning' };
    return { text: 'Low', cls: 'badge-success' };
  };

  if (!result) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 24 }}>
        <div style={{ fontSize: '64px' }}>📝</div>
        <h2>No Exam Data Found</h2>
        <p style={{ color: 'var(--text-secondary)' }}>You haven't completed an exam yet.</p>
        <Link to="/exam" className="btn btn-primary">📝 Take Exam</Link>
      </div>
    );
  }

  const violations = result.proctoring_summary?.total_violations ?? 0;
  const risk = riskLabel(violations);

  return (
    <div className="score-page" style={{ maxWidth: 900, margin: '0 auto' }}>
      {/* Navbar */}
      <nav className="navbar" style={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100 }}>
        <div className="navbar-inner container">
          <span className="navbar-brand">🧠 MindMesh</span>
          <ul className="navbar-links">
            <li><span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>Welcome, {user?.name}</span></li>
            <li>
              <button className="btn btn-outline btn-sm" onClick={() => { logout(); navigate('/login'); }}>
                🚪 Logout
              </button>
            </li>
          </ul>
        </div>
      </nav>

      <div className="score-header">
        <h1 style={{ fontSize: 32, fontWeight: 900, marginBottom: 8 }}>📊 Your Results</h1>
        <p style={{ color: 'var(--text-secondary)' }}>{user?.name} — Exam completed</p>
      </div>

      {/* Score Circle */}
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 40 }}>
        <div className="score-circle" style={{ borderColor: gradeColor(result.score), color: gradeColor(result.score) }}>
          <span className="score-num">{result.score}</span>
          <span className="score-lbl">{gradeLabel(result.score)}</span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="score-grid" style={{ marginBottom: 32 }}>
        {[
          { val: `${result.correct}/${result.questions_total}`, lbl: 'Correct Answers', color: 'var(--success)' },
          { val: `${result.questions_answered}/${result.questions_total}`, lbl: 'Answered', color: 'var(--info)' },
          { val: fmt(result.time_used), lbl: 'Time Used', color: 'var(--accent)' },
          { val: violations, lbl: 'AI Violations', color: violations > 0 ? 'var(--warning)' : 'var(--success)' },
        ].map(({ val, lbl, color }) => (
          <div key={lbl} className="glass-card score-card">
            <div className="score-card-val" style={{ color }}>{val}</div>
            <div className="score-card-lbl">{lbl}</div>
          </div>
        ))}
      </div>

      {/* Category Breakdown */}
      {result.category_scores && (
        <div className="glass-card" style={{ padding: 28, marginBottom: 24 }}>
          <h3 style={{ marginBottom: 20, fontSize: 16 }}>📈 Category Performance</h3>
          {Object.entries(result.category_scores).map(([cat, data]) => {
            const normalized = normalizeCategoryMetrics(data);
            return (
              <div key={cat} style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontSize: 14, fontWeight: 600 }}>{cat}</span>
                  <span style={{ fontSize: 13, color: gradeColor(normalized.pct) }}>{normalized.label}</span>
                </div>
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${normalized.pct}%`, background: gradeColor(normalized.pct) }} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Proctoring Summary */}
      <div className="glass-card" style={{ padding: 28, marginBottom: 32 }}>
        <h3 style={{ marginBottom: 16, fontSize: 16 }}>🤖 AI Proctoring Summary</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div>Risk Level: <span className={`badge ${risk.cls}`}>{risk.text}</span></div>
          <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
            {violations} violation{violations !== 1 ? 's' : ''} detected by AI
          </div>
          {result.terminated && <span className="badge badge-danger">⚠️ Exam Terminated</span>}
        </div>
        {result.proctoring_summary?.violation_types?.length > 0 && (
          <div style={{ marginTop: 12, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {result.proctoring_summary.violation_types.map((v, i) => (
              <span key={i} className="badge badge-warning">{v}</span>
            ))}
          </div>
        )}
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
        <Link to="/exam" className="btn btn-primary btn-lg">📝 Retake Exam</Link>
        <button className="btn btn-outline btn-lg" onClick={() => { logout(); navigate('/login'); }}>
          🚪 Logout
        </button>
      </div>
    </div>
  );
}
