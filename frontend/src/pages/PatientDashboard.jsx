import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import { LuHeartPulse, LuMessageSquare, LuCalendarDays, LuStethoscope } from 'react-icons/lu';

export default function PatientDashboard() {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState('chat');
  const [messages, setMessages] = useState([
    { role: 'assistant', content: "Hello! 👋 I'm your MediConnect AI assistant. I can help you:\n\n• Check doctor availability\n• Book appointments\n• View your upcoming appointments\n• Cancel appointments\n\nTry saying something like \"I want to book an appointment with Dr. Ahuja tomorrow morning\"" }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [appointments, setAppointments] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [stats, setStats] = useState({ upcoming: 0, completed: 0, total: 0 });
  const chatEndRef = useRef(null);

  useEffect(() => {
    fetchAppointments();
    fetchDoctors();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const fetchAppointments = async () => {
    try {
      const res = await api.get('/api/appointments');
      const appts = res.data.appointments || [];
      setAppointments(appts);
      setStats({
        upcoming: appts.filter(a => a.status === 'scheduled').length,
        completed: appts.filter(a => a.status === 'completed').length,
        total: appts.length
      });
    } catch (err) { console.error(err); }
  };

  const fetchDoctors = async () => {
    try {
      const res = await api.get('/api/doctors');
      setDoctors(res.data.doctors || []);
    } catch (err) { console.error(err); }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      const res = await api.post('/api/chat', {
        message: userMsg,
        session_id: sessionId
      });
      setSessionId(res.data.session_id);
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: res.data.response,
          toolCalls: res.data.tool_calls
        }
      ]);
      // Refresh appointments after potential booking
      if (res.data.tool_calls?.some(tc => ['book_appointment', 'cancel_appointment'].includes(tc.tool))) {
        fetchAppointments();
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please make sure the backend server is running on http://localhost:8000'
      }]);
    }
    setLoading(false);
  };

  const handleQuickAction = (text) => {
    setInput(text);
  };

  const quickActions = [
    "Show available doctors",
    "Check Dr. Ahuja's availability for tomorrow",
    "Book appointment with Dr. Pyari",
    "Show my appointments",
  ];

  return (
    <div className="dashboard">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><LuHeartPulse color="var(--primary)" /> MediConnect</h2>
          <span>Patient Portal</span>
        </div>
        <nav className="sidebar-nav">
          <button className={`nav-item ${activeTab === 'chat' ? 'active' : ''}`} onClick={() => setActiveTab('chat')}>
            <span className="nav-icon"><LuMessageSquare /></span> AI Assistant
          </button>
          <button className={`nav-item ${activeTab === 'appointments' ? 'active' : ''}`} onClick={() => setActiveTab('appointments')}>
            <span className="nav-icon"><LuCalendarDays /></span> My Appointments
          </button>
          <button className={`nav-item ${activeTab === 'doctors' ? 'active' : ''}`} onClick={() => setActiveTab('doctors')}>
            <span className="nav-icon"><LuStethoscope /></span> Doctors
          </button>
        </nav>
        <div className="sidebar-user">
          <div className="user-avatar">{user?.name?.[0] || 'U'}</div>
          <div className="user-info">
            <div className="user-name">{user?.name}</div>
            <div className="user-role">{user?.role}</div>
          </div>
          <button className="logout-btn" onClick={logout} title="Logout">⏻</button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {activeTab === 'chat' && (
          <>
            <div className="page-header">
              <h1>AI Appointment Assistant</h1>
              <p>Book appointments using natural language — just type what you need</p>
            </div>

            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Upcoming</div>
                <div className="stat-value">{stats.upcoming}</div>
                <div className="stat-sub">scheduled appointments</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Completed</div>
                <div className="stat-value">{stats.completed}</div>
                <div className="stat-sub">past visits</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Doctors</div>
                <div className="stat-value">{doctors.length}</div>
                <div className="stat-sub">available specialists</div>
              </div>
            </div>

            <div className="chat-container" style={{ height: 'calc(100vh - 340px)' }}>
              <div className="chat-header">
                <div className="chat-status"></div>
                <div>
                  <h3>MediConnect AI</h3>
                  <p>Powered by Gemini • Multi-turn conversations</p>
                </div>
              </div>

              <div className="chat-messages">
                {messages.map((msg, i) => (
                  <div key={i} className={`message ${msg.role}`}>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                    {msg.toolCalls?.length > 0 && (
                      <div style={{ marginTop: '8px' }}>
                        {msg.toolCalls.map((tc, j) => (
                          <span key={j} className="tool-badge">🔧 {tc.tool}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {loading && (
                  <div className="typing-indicator">
                    <span></span><span></span><span></span>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              <div className="quick-actions">
                {quickActions.map((action, i) => (
                  <button key={i} className="quick-action" onClick={() => handleQuickAction(action)}>
                    {action}
                  </button>
                ))}
              </div>

              <div className="chat-input">
                <input
                  type="text"
                  placeholder="Type your message... (e.g., 'Book appointment with Dr. Ahuja tomorrow at 10 AM')"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                  disabled={loading}
                />
                <button onClick={sendMessage} disabled={loading || !input.trim()}>
                  {loading ? '⏳' : '➤'}
                </button>
              </div>
            </div>
          </>
        )}

        {activeTab === 'appointments' && (
          <>
            <div className="page-header">
              <h1>My Appointments</h1>
              <p>View and manage your scheduled appointments</p>
            </div>
            <div className="card">
              <div className="card-header">
                <h3>All Appointments</h3>
                <button className="btn btn-accent btn-sm" onClick={fetchAppointments}>↻ Refresh</button>
              </div>
              <div className="card-body">
                {appointments.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-icon"><LuCalendarDays /></div>
                    <p>No appointments yet. Use the AI Assistant to book one!</p>
                  </div>
                ) : (
                  <div className="appointments-list">
                    {appointments.map(appt => (
                      <div key={appt.id} className="appointment-item">
                        <div className="appt-info">
                          <h4>{appt.doctor_name} — {appt.doctor_specialty}</h4>
                          <p>📅 {appt.date} at {appt.time_slot} • {appt.reason || 'General consultation'}</p>
                        </div>
                        <span className={`appt-status ${appt.status}`}>{appt.status}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {activeTab === 'doctors' && (
          <>
            <div className="page-header">
              <h1>Our Doctors</h1>
              <p>Expert medical professionals at your service</p>
            </div>
            <div className="stats-grid">
              {doctors.map(doc => (
                <div key={doc.id} className="stat-card" style={{ cursor: 'pointer' }}
                     onClick={() => { setActiveTab('chat'); setInput(`Check ${doc.name}'s availability for tomorrow`); }}>
                  <div className="stat-label">{doc.specialty}</div>
                  <div style={{ fontSize: '18px', fontWeight: '700', marginBottom: '4px' }}>{doc.name}</div>
                  <div className="stat-sub">{doc.bio?.substring(0, 80)}...</div>
                </div>
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
