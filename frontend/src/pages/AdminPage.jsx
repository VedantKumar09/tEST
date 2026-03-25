/**
 * Admin Page — View all student submissions + proctoring data
 */
import React, { useState, useEffect } from 'react';

import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { adminAPI } from '../services/api';

export default function AdminPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [submissions, setSubmissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    adminAPI.getSubmissions()
      .then(data => setSubmissions(data))
      .catch(() => setSubmissions([]))
      .finally(() => setLoading(false));
  }, []);

  const fmt = (s) => `${Math.floor(s / 60)}m ${s % 60}s`;
  const fmtDate = (iso) => iso ? new Date(iso).toLocaleString() : '—';

  const gradeColor = (s) => s >= 80 ? 'var(--success)' : s >= 50 ? 'var(--warning)' : 'var(--danger)';
  const riskColor = (r) => r === 'High' ? 'var(--danger)' : r === 'Medium' ? 'var(--warning)' : 'var(--success)';
  const riskBadge = (r) => r === 'High' ? 'badge-danger' : r === 'Medium' ? 'badge-warning' : 'badge-success';

  const filtered = submissions.filter(s =>
    s.student_name?.toLowerCase().includes(search.toLowerCase()) ||
    s.student_email?.toLowerCase().includes(search.toLowerCase())
  );

  const stats = {
    total: submissions.length,
    avgScore: submissions.length ? Math.round(submissions.reduce((a, s) => a + s.score, 0) / submissions.length) : 0,
    highRisk: submissions.filter(s => s.proctoring_summary?.risk_level === 'High').length,
    avgViolations: submissions.length ? Math.round(submissions.reduce((a, s) => a + (s.proctoring_summary?.total_violations ?? 0), 0) / submissions.length) : 0,
  };

  return (
    <div className="admin-page">
      {/* Navbar */}
      <nav className="navbar" style={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100 }}>
        <div className="navbar-inner container">
          <span className="navbar-brand">🧠 MindMesh — Admin</span>
          <ul className="navbar-links">
            <li><span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{user?.name}</span></li>
            <li>
              <button className="btn btn-outline btn-sm" onClick={() => { logout(); navigate('/login'); }}>
                🚪 Logout
              </button>
            </li>
          </ul>
        </div>
      </nav>

      <div className="container">
        {/* Header */}
        <div className="admin-header">
          <h1>🛡️ Proctoring Dashboard</h1>
          <p>Exam results and AI proctoring reports for all students</p>
        </div>

        {/* Summary Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, marginBottom: 32 }}>
          {[
            { val: stats.total, lbl: 'Total Submissions', icon: '📋', color: 'var(--accent)' },
            { val: `${stats.avgScore}%`, lbl: 'Average Score', icon: '📊', color: gradeColor(stats.avgScore) },
            { val: stats.highRisk, lbl: 'High Risk Students', icon: '🚨', color: 'var(--danger)' },
            { val: stats.avgViolations, lbl: 'Avg. Violations', icon: '⚠️', color: 'var(--warning)' },
          ].map(({ val, lbl, icon, color }) => (
            <div key={lbl} className="glass-card" style={{ padding: '20px 16px', textAlign: 'center' }}>
              <div style={{ fontSize: 24, marginBottom: 6 }}>{icon}</div>
              <div style={{ fontSize: 28, fontWeight: 800, color }}>{val}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', marginTop: 4 }}>{lbl}</div>
            </div>
          ))}
        </div>

        {/* Search */}
        <div style={{ marginBottom: 16 }}>
          <input
            className="form-input"
            placeholder="🔍 Search by student name or email..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ maxWidth: 400 }}
          />
        </div>

        {/* Table */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>⏳ Loading submissions...</div>
        ) : filtered.length === 0 ? (
          <div className="glass-card" style={{ padding: 48, textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>📭</div>
            <h3>No submissions found</h3>
            <p style={{ color: 'var(--text-secondary)', marginTop: 8 }}>No students have submitted exams yet.</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="submissions-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Score</th>
                  <th>Answered</th>
                  <th>Time Used</th>
                  <th>Violations</th>
                  <th>Risk Level</th>
                  <th>Submitted</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((sub) => {
                  const risk = sub.proctoring_summary?.risk_level ?? 'Low';
                  const viols = sub.proctoring_summary?.total_violations ?? 0;
                  const isOpen = expanded === sub.submission_id;
                  return (
                    <React.Fragment key={sub.submission_id}>
                      <tr key={sub.submission_id} onClick={() => setExpanded(isOpen ? null : sub.submission_id)}>
                        <td>
                          <div style={{ fontWeight: 600 }}>{sub.student_name}</div>
                          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{sub.student_email}</div>
                        </td>
                        <td>
                          <span style={{ fontWeight: 800, fontSize: 18, color: gradeColor(sub.score) }}>{sub.score}%</span>
                        </td>
                        <td style={{ color: 'var(--text-secondary)' }}>{sub.questions_answered}/{sub.questions_total}</td>
                        <td style={{ color: 'var(--text-secondary)' }}>{fmt(sub.time_used)}</td>
                        <td>
                          <span style={{ fontWeight: 700, color: viols > 0 ? 'var(--warning)' : 'var(--success)' }}>{viols}</span>
                        </td>
                        <td>
                          <span className={`badge ${riskBadge(risk)}`}>{risk}</span>
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{fmtDate(sub.submitted_at)}</td>
                        <td>
                          <span style={{ color: 'var(--accent)', fontSize: 12 }}>{isOpen ? '▲ Hide' : '▼ Details'}</span>
                        </td>
                      </tr>

                      {/* Detail row */}
                      {isOpen && (
                        <tr key={`${sub.submission_id}-detail`}>
                          <td colSpan={8} style={{ padding: 0 }}>
                            <div className="detail-panel">
                              <h4 style={{ marginBottom: 16, color: 'var(--accent)' }}>🔍 Proctoring Report — {sub.student_name}</h4>

                              {/* Summary stats */}
                              <div className="detail-grid">
                                {[
                                  { val: `${sub.score}%`, lbl: 'Final Score', color: gradeColor(sub.score) },
                                  { val: `${sub.correct}/${sub.questions_total}`, lbl: 'Correct', color: 'var(--success)' },
                                  { val: viols, lbl: 'AI Violations', color: viols > 0 ? 'var(--warning)' : 'var(--success)' },
                                  { val: sub.proctoring_summary?.tab_switches ?? 0, lbl: 'Tab Switches', color: 'var(--info)' },
                                  { val: risk, lbl: 'Risk Level', color: riskColor(risk) },
                                  { val: fmt(sub.time_used), lbl: 'Time Used', color: 'var(--text-secondary)' },
                                ].map(({ val, lbl, color }) => (
                                  <div key={lbl} className="glass-card" style={{ padding: '16px 12px', textAlign: 'center' }}>
                                    <div className="detail-stat-val" style={{ color }}>{val}</div>
                                    <div className="detail-stat-lbl">{lbl}</div>
                                  </div>
                                ))}
                              </div>

                              {/* AI Supervisor Analysis */}
                              {sub.ai_supervisor && (
                                <div className="glass-card" style={{ padding: 16, marginBottom: 16, background: 'rgba(255,255,255,0.02)', borderLeft: `4px solid ${riskColor(sub.ai_supervisor.probability_cheating)}` }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                                    <h5 style={{ margin: 0, fontSize: 15, display: 'flex', alignItems: 'center', gap: 8 }}>
                                      🤖 Agentic Supervisor Analysis
                                    </h5>
                                    <div>
                                      <span className={`badge ${riskBadge(sub.ai_supervisor.probability_cheating)}`} style={{ marginRight: 8 }}>
                                        Prob: {sub.ai_supervisor.probability_cheating}
                                      </span>
                                      <span className="badge" style={{ background: 'var(--accent)' }}>
                                        Action: {sub.ai_supervisor.recommended_action}
                                      </span>
                                    </div>
                                  </div>
                                  <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0, fontStyle: 'italic' }}>
                                    "{sub.ai_supervisor.reasoning}"
                                  </p>
                                </div>
                              )}

                              {/* Category breakdown */}
                              {sub.category_scores && (
                                <div style={{ marginBottom: 16 }}>
                                  <p style={{ fontSize: 13, fontWeight: 700, marginBottom: 12 }}>📈 Category Performance</p>
                                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
                                    {Object.entries(sub.category_scores).map(([cat, data]) => {
                                      const pct = data.total > 0 ? Math.round((data.correct / data.total) * 100) : 0;
                                      return (
                                        <div key={cat} className="glass-card" style={{ padding: 16 }}>
                                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                                            <span style={{ fontSize: 13, fontWeight: 600 }}>{cat}</span>
                                            <span style={{ fontSize: 13, color: gradeColor(pct) }}>{data.correct}/{data.total}</span>
                                          </div>
                                          <div className="progress-bar">
                                            <div className="progress-fill" style={{ width: `${pct}%`, background: gradeColor(pct) }} />
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              )}

                              {/* Violation types */}
                              {sub.proctoring_summary?.violation_types?.length > 0 && (
                                <div>
                                  <p style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>🚨 Detected Violations</p>
                                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                    {sub.proctoring_summary.violation_types.map((v, i) => (
                                      <span key={i} className="badge badge-warning">{v.replace('object:', '📦 ')}</span>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
