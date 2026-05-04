import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LuHeartPulse, LuUser, LuStethoscope } from 'react-icons/lu';

export default function Signup() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');
  const [role, setRole] = useState('patient');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { signup } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await signup(name, email, password, phone, role);
    } catch (err) {
      setError(err.response?.data?.detail || 'Signup failed. Please try again.');
    }
    setLoading(false);
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <h1 style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}><LuHeartPulse color="var(--primary)" /> MediConnect</h1>
          <p>Create your account</p>
        </div>

        {error && <div className="error-msg">{error}</div>}

        <div className="role-selector">
          <div
            className={`role-option ${role === 'patient' ? 'active' : ''}`}
            onClick={() => setRole('patient')}
          >
            <div className="role-icon"><LuUser size={24} /></div>
            <div className="role-label">Patient</div>
          </div>
          <div
            className={`role-option ${role === 'doctor' ? 'active' : ''}`}
            onClick={() => setRole('doctor')}
          >
            <div className="role-icon"><LuStethoscope size={24} /></div>
            <div className="role-label">Doctor</div>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Full Name</label>
            <input
              type="text"
              placeholder="Enter your full name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
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
            <label>Phone</label>
            <input
              type="tel"
              placeholder="Enter phone number"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              placeholder="Create a password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Creating account...' : 'Create Account'}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
