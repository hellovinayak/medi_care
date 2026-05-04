import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LuHeartPulse, LuUser, LuStethoscope } from 'react-icons/lu';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Please try again.');
    }
    setLoading(false);
  };

  const fillDemo = (type) => {
    if (type === 'patient') {
      setEmail('vinayak@gmail.com');
      setPassword('123');
    } else {
      setEmail('doctor@mediconnect.com');
      setPassword('doctor123');
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <h1 style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}><LuHeartPulse color="var(--primary)" /> MediConnect</h1>
          <p>Smart Healthcare Assistant</p>
        </div>

        {error && <div className="error-msg">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
          <button className="btn btn-outline btn-sm" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }} onClick={() => fillDemo('patient')}>
            <LuUser /> Demo Patient
          </button>
          <button className="btn btn-outline btn-sm" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }} onClick={() => fillDemo('doctor')}>
            <LuStethoscope /> Demo Doctor
          </button>
        </div>

        <div className="auth-footer">
          Don't have an account? <Link to="/signup">Sign up</Link>
        </div>
      </div>
    </div>
  );
}
