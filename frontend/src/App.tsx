import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Landing from './pages/Landing';
import './App.css';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/dashboard" element={
          <div className="app-container">
            <Navbar />
            <main className="main-content">
              <Dashboard />
            </main>
          </div>
        } />
      </Routes>
    </Router>
  );
}

export default App;
