import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authAPI } from '../services/api';

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [role, setRole] = useState('student');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!email || !password) { setError('Please fill in all fields.'); return; }
    setLoading(true);
    setError('');
    try {
      const data = await authAPI.login(email, password, role);
      login(data.access_token, data.user);
      navigate(role === 'admin' ? '/admin' : '/exam');
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Check credentials.');
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = () => {
    if (role === 'student') { setEmail('student@mindmesh.ai'); setPassword('student123'); }
    else { setEmail('admin@mindmesh.ai'); setPassword('admin123'); }
  };

  return (
    <div className="login-page">
      <div className="login-container">
        
        <div className="login-logo">
          <div style={{ fontSize: '48px', marginBottom: '8px' }}>🧠</div>
          <h1>MindMesh</h1>
          <p>AI-Powered Assessment & Proctoring Platform</p>
        </div>

        
        <div className="role-cards">
          <div
            className={`role-card ${role === 'student' ? 'active' : ''}`}
            onClick={() => { setRole('student'); setEmail(''); setPassword(''); setError(''); }}
          >
            <div className="icon">🎓</div>
            <h3>I'm a Student</h3>
            <p>Take your exam</p>
          </div>
          <div
            className={`role-card ${role === 'admin' ? 'active' : ''}`}
            onClick={() => { setRole('admin'); setEmail(''); setPassword(''); setError(''); }}
          >
            <div className="icon">🛡️</div>
            <h3>I'm an Admin</h3>
            <p>Monitor & review</p>
          </div>
        </div>

        
        <div className="glass-card login-card">
          <form className="login-form" onSubmit={handleLogin}>
            <div style={{ textAlign: 'center', marginBottom: '4px' }}>
              <span className="badge badge-info" style={{ fontSize: '12px', padding: '5px 12px' }}>
                Logging in as {role === 'student' ? '🎓 Student' : '🛡️ Admin'}
              </span>
            </div>

            {error && <div className="alert alert-error">{error}</div>}

            <div className="form-group">
              <label className="form-label">Email Address</label>
              <input
                className="form-input"
                type="email"
                placeholder={role === 'student' ? 'student@mindmesh.ai' : 'admin@mindmesh.ai'}
                value={email}
                onChange={e => setEmail(e.target.value)}
                autoComplete="email"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Password</label>
              <input
                className="form-input"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>

            <button type="submit" className="btn btn-primary btn-lg" disabled={loading} style={{ width: '100%', justifyContent: 'center' }}>
              {loading ? '⏳ Signing in...' : `🚀 Sign In as ${role === 'student' ? 'Student' : 'Admin'}`}
            </button>

            <button type="button" className="btn btn-outline" onClick={fillDemo} style={{ width: '100%', justifyContent: 'center' }}>
              ✨ Fill Demo Credentials
            </button>
          </form>

          <div style={{ marginTop: '20px', padding: '14px', background: 'rgba(99,102,241,0.07)', borderRadius: 'var(--radius-sm)', fontSize: '12px', color: 'var(--text-muted)' }}>
            <strong style={{ color: 'var(--text-secondary)' }}>Demo credentials:</strong><br />
            Student: student@mindmesh.ai / student123<br />
            Admin: admin@mindmesh.ai / admin123
          </div>
        </div>
      </div>
    </div>
  );
}

