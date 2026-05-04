import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import { LuHeartPulse, LuBot, LuCalendarDays, LuBell } from 'react-icons/lu';

export default function DoctorDashboard() {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState('chat');
  const [messages, setMessages] = useState([
    { role: 'assistant', content: "Hello, Doctor! 👋 I'm your MediConnect reporting assistant. I can help you:\n\n• Check today's/tomorrow's appointments\n• Get patient visit statistics\n• Find patients by symptoms\n• Generate summary reports\n• Send report notifications\n\nTry asking: \"How many patients do I have today?\"" }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [appointments, setAppointments] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showNotifs, setShowNotifs] = useState(false);
  const [stats, setStats] = useState({ today: 0, scheduled: 0, completed: 0 });
  const [apptTab, setApptTab] = useState('upcoming');
  const chatEndRef = useRef(null);

  useEffect(() => {
    fetchAppointments();
    fetchNotifications();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const fetchAppointments = async () => {
    try {
      const res = await api.get('/api/appointments');
      const appts = res.data.appointments || [];
      setAppointments(appts);
      const today = new Date().toISOString().split('T')[0];
      setStats({
        today: appts.filter(a => a.date === today).length,
        scheduled: appts.filter(a => a.status === 'scheduled').length,
        completed: appts.filter(a => a.status === 'completed').length
      });
    } catch (err) { console.error(err); }
  };

  const fetchNotifications = async () => {
    try {
      const res = await api.get('/api/notifications');
      setNotifications(res.data.notifications || []);
      setUnreadCount(res.data.unread_count || 0);
    } catch (err) { console.error(err); }
  };

  const markRead = async (id) => {
    try {
      await api.post(`/api/notifications/mark-read/${id}`);
      fetchNotifications();
    } catch (err) { console.error(err); }
  };

  const updateStatus = async (id, status) => {
    try {
      setLoading(true);
      await api.put(`/api/appointments/${id}/status?status=${status}`);
      await fetchAppointments();
    } catch (err) {
      console.error(err);
      alert('Failed to update appointment status');
    } finally {
      setLoading(false);
    }
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
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.data.response,
        toolCalls: res.data.tool_calls
      }]);
      // Refresh if notifications were sent
      if (res.data.tool_calls?.some(tc => tc.tool === 'send_notification')) {
        fetchNotifications();
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please check that the backend is running.'
      }]);
    }
    setLoading(false);
  };

  const generateReport = () => {
    setInput('Generate a summary report of all appointments today and send it as a notification');
  };

  const quickActions = [
    "How many patients visited yesterday?",
    "How many appointments do I have today?",
    "How many appointments tomorrow?",
    "How many patients with fever?",
    "Generate summary report for this week",
  ];

  return (
    <div className="dashboard">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><LuHeartPulse color="var(--primary)" /> MediConnect</h2>
          <span>Doctor Portal</span>
        </div>
        <nav className="sidebar-nav">
          <button className={`nav-item ${activeTab === 'chat' ? 'active' : ''}`} onClick={() => setActiveTab('chat')}>
            <span className="nav-icon"><LuBot /></span> AI Reports
          </button>
          <button className={`nav-item ${activeTab === 'appointments' ? 'active' : ''}`} onClick={() => setActiveTab('appointments')}>
            <span className="nav-icon"><LuCalendarDays /></span> Appointments
          </button>
          <button className={`nav-item ${activeTab === 'notifications' ? 'active' : ''}`} onClick={() => setActiveTab('notifications')}>
            <span className="nav-icon"><LuBell /></span> Notifications
            {unreadCount > 0 && <span style={{
              background: 'var(--danger)', color: 'white', borderRadius: '10px',
              padding: '2px 8px', fontSize: '11px', fontWeight: '700', marginLeft: 'auto'
            }}>{unreadCount}</span>}
          </button>
        </nav>
        <div className="sidebar-user">
          <div className="user-avatar" style={{ background: 'linear-gradient(135deg, #10b981, #059669)' }}>
            {user?.name?.[0] || 'D'}
          </div>
          <div className="user-info">
            <div className="user-name">{user?.name}</div>
            <div className="user-role">Doctor</div>
          </div>
          <button className="logout-btn" onClick={logout} title="Logout">⏻</button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {activeTab === 'chat' && (
          <>
            <div className="page-header">
              <h1>AI Reports & Summary</h1>
              <p>Ask questions about your schedule, patient visits, and generate reports</p>
            </div>

            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Today</div>
                <div className="stat-value">{stats.today}</div>
                <div className="stat-sub">appointments today</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Scheduled</div>
                <div className="stat-value">{stats.scheduled}</div>
                <div className="stat-sub">upcoming appointments</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Completed</div>
                <div className="stat-value">{stats.completed}</div>
                <div className="stat-sub">completed visits</div>
              </div>
              <div className="stat-card" style={{ cursor: 'pointer' }} onClick={generateReport}>
                <div className="stat-label">Quick Action</div>
                <div style={{ fontSize: '20px', fontWeight: '700', color: 'var(--accent)' }}>📊 Generate Report</div>
                <div className="stat-sub">click to generate today's report</div>
              </div>
            </div>

            <div className="chat-container" style={{ height: 'calc(100vh - 340px)' }}>
              <div className="chat-header" style={{ background: 'linear-gradient(135deg, #059669, #10b981)' }}>
                <div className="chat-status"></div>
                <div>
                  <h3>MediConnect AI — Doctor Reports</h3>
                  <p>Powered by Gemini • In-app notifications</p>
                </div>
              </div>

              <div className="chat-messages">
                {messages.map((msg, i) => (
                  <div key={i} className={`message ${msg.role}`}>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                    {msg.toolCalls?.length > 0 && (
                      <div style={{ marginTop: '8px' }}>
                        {msg.toolCalls.map((tc, j) => (
                          <span key={j} className="tool-badge" style={{ background: 'rgba(16,185,129,0.15)', color: 'var(--accent)' }}>
                            🔧 {tc.tool}
                          </span>
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
                  <button key={i} className="quick-action" onClick={() => setInput(action)}
                    style={{ borderColor: 'rgba(16,185,129,0.2)', background: 'rgba(16,185,129,0.1)', color: 'var(--accent)' }}>
                    {action}
                  </button>
                ))}
              </div>

              <div className="chat-input">
                <input
                  type="text"
                  placeholder="Ask about your schedule... (e.g., 'How many patients yesterday?')"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                  disabled={loading}
                />
                <button onClick={sendMessage} disabled={loading || !input.trim()}
                  style={{ background: 'linear-gradient(135deg, var(--accent), var(--accent-dark))' }}>
                  {loading ? '⏳' : '➤'}
                </button>
              </div>
            </div>
          </>
        )}

        {activeTab === 'appointments' && (
          <>
            <div className="page-header">
              <h1>Patient Appointments</h1>
              <p>View upcoming schedule and visit history</p>
            </div>

            <div style={{ display: 'flex', gap: '12px', marginBottom: '20px' }}>
              <button
                className={`btn ${apptTab === 'upcoming' ? 'btn-accent' : 'btn-outline'}`}
                onClick={() => setApptTab('upcoming')}
              >
                Upcoming
              </button>
              <button
                className={`btn ${apptTab === 'history' ? 'btn-accent' : 'btn-outline'}`}
                onClick={() => setApptTab('history')}
              >
                History
              </button>
            </div>

            <div className="card">
              <div className="card-header">
                <h3>{apptTab === 'upcoming' ? 'Upcoming Appointments' : 'Appointment History'}</h3>
                <button className="btn btn-accent btn-sm" onClick={fetchAppointments}>↻ Refresh</button>
              </div>
              <div className="card-body">
                {appointments.filter(a => apptTab === 'upcoming' ? a.status === 'scheduled' : a.status !== 'scheduled').length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-icon"><LuCalendarDays /></div>
                    <p>No {apptTab} appointments found.</p>
                  </div>
                ) : (
                  <div className="appointments-list">
                    {appointments
                      .filter(a => apptTab === 'upcoming' ? a.status === 'scheduled' : a.status !== 'scheduled')
                      .map(appt => (
                        <div key={appt.id} className="appointment-item">
                          <div className="appt-info">
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                              <h4>{appt.patient_name}</h4>
                              <span className={`appt-status ${appt.status}`} style={{ fontSize: '10px', padding: '2px 6px' }}>{appt.status}</span>
                            </div>
                            <p>📅 {appt.date} at {appt.time_slot} • {appt.reason || 'General'} {appt.symptoms ? `• Symptoms: ${appt.symptoms}` : ''}</p>
                          </div>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            {appt.status === 'scheduled' && (
                              <button
                                className="btn btn-accent btn-sm"
                                onClick={() => updateStatus(appt.id, 'completed')}
                                style={{ background: 'var(--success)', borderColor: 'var(--success)' }}
                              >
                                ✓ Mark Done
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {activeTab === 'notifications' && (
          <>
            <div className="page-header">
              <h1 style={{ display: 'flex', alignItems: 'center', gap: '12px' }}><LuBell color="var(--accent)" /> Notifications</h1>
              <p>In-app notifications and reports ({unreadCount} unread)</p>
            </div>
            <div className="card">
              <div className="card-header">
                <h3>All Notifications</h3>
                <button className="btn btn-accent btn-sm" onClick={fetchNotifications}>↻ Refresh</button>
              </div>
              <div className="card-body">
                {notifications.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-icon"><LuBell /></div>
                    <p>No notifications yet. Use AI Reports to generate summary reports — they'll appear here!</p>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {notifications.map(notif => (
                      <div key={notif.id}
                        className={`notif-item ${!notif.is_read ? 'unread' : ''}`}
                        onClick={() => markRead(notif.id)}>
                        <div className="notif-title">{notif.title}</div>
                        <div className="notif-msg" style={{ whiteSpace: 'pre-wrap' }}>{notif.message}</div>
                        <div className="notif-time">
                          {notif.created_at ? new Date(notif.created_at).toLocaleString() : ''} •
                          {notif.is_read ? ' Read' : ' Unread'}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
