import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Signup from './pages/Signup';
import PatientDashboard from './pages/PatientDashboard';
import DoctorDashboard from './pages/DoctorDashboard';
import './index.css';

function ProtectedRoute({ children, requiredRole }) {
  const { user, loading } = useAuth();
  
  if (loading) return <div className="loading-screen"><div className="spinner"></div></div>;
  if (!user) return <Navigate to="/login" />;
  if (requiredRole && user.role !== requiredRole) {
    return <Navigate to={user.role === 'doctor' ? '/doctor' : '/dashboard'} />;
  }
  return children;
}

function AppRoutes() {
  const { user } = useAuth();
  
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={user.role === 'doctor' ? '/doctor' : '/dashboard'} /> : <Login />} />
      <Route path="/signup" element={user ? <Navigate to={user.role === 'doctor' ? '/doctor' : '/dashboard'} /> : <Signup />} />
      <Route path="/dashboard" element={
        <ProtectedRoute requiredRole="patient"><PatientDashboard /></ProtectedRoute>
      } />
      <Route path="/doctor" element={
        <ProtectedRoute requiredRole="doctor"><DoctorDashboard /></ProtectedRoute>
      } />
      <Route path="/" element={<Navigate to="/login" />} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <AppRoutes />
      </Router>
    </AuthProvider>
  );
}

export default App;
