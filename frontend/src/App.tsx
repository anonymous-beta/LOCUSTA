import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Bug, Radio, Settings, Terminal, Activity, Brain,
  Shield, Zap, Globe, ChevronRight, AlertTriangle
} from 'lucide-react';
import axios from 'axios';
import { io, Socket } from 'socket.io-client';

import Dashboard from './components/Dashboard';
import SwarmControl from './components/SwarmControl';
import WorkerDetail from './components/WorkerDetail';
import AttackConfig from './components/AttackConfig';
import AIControl from './components/AIControl';
import Reports from './components/Reports';
import SettingsPanel from './components/SettingsPanel';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8443/api';
const WS_URL = process.env.REACT_APP_WS_URL || 'http://localhost:8443';

interface Worker {
  id: string;
  status: string;
  info: {
    hostname?: string;
    ip?: string;
    os?: string;
    role?: string;
    latency_ms?: number;
    tasks_completed?: number;
  };
  current_task?: any;
}

interface ActivityEntry {
  id: string;
  timestamp: string;
  severity: string;
  category: string;
  message: string;
  worker_id?: string;
}

function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [token, setToken] = useState('');
  const [activeView, setActiveView] = useState('dashboard');
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [socket, setSocket] = useState<Socket | null>(null);
  const [systemStatus, setSystemStatus] = useState('online');
  const [selectedWorker, setSelectedWorker] = useState<string | null>(null);

  useEffect(() => {
    if (authenticated) {
      initSocket();
      fetchWorkers();
      fetchActivity();
    }
  }, [authenticated]);

  const initSocket = () => {
    const newSocket = io(WS_URL, {
      auth: { token }
    });

    newSocket.on('connect', () => {
      console.log('Connected to hive');
      setSystemStatus('online');
    });

    newSocket.on('disconnect', () => {
      setSystemStatus('offline');
    });

    newSocket.on('activity', (entry: ActivityEntry) => {
      setActivity(prev => [entry, ...prev].slice(0, 100));
    });

    newSocket.on('worker_status', (data: any) => {
      setWorkers(prev => prev.map(w => 
        w.id === data.id ? { ...w, status: data.status } : w
      ));
    });

    newSocket.on('ai_reasoning', (data: any) => {
      // Handle AI reasoning stream
      console.log('AI:', data);
    });

    setSocket(newSocket);
    return () => { newSocket.close(); };
  };

  const fetchWorkers = async () => {
    try {
      const resp = await axios.get(`${API_URL}/workers`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setWorkers(resp.data);
    } catch (e) {
      console.error('Failed to fetch workers');
    }
  };

  const fetchActivity = async () => {
    try {
      const resp = await axios.get(`${API_URL}/activity?limit=50`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setActivity(resp.data);
    } catch (e) {
      console.error('Failed to fetch activity');
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const resp = await axios.post(`${API_URL}/auth/login`, {
        username,
        password
      });
      setToken(resp.data.access_token);
      setAuthenticated(true);
    } catch (e) {
      alert('Login failed');
    }
  };

  if (!authenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-void relative overflow-hidden">
        <div className="hex-grid absolute inset-0" />
        {[...Array(20)].map((_, i) => (
          <div 
            key={i}
            className="particle"
            style={{
              left: `${Math.random() * 100}%`,
              animationDelay: `${Math.random() * 10}s`,
              animationDuration: `${5 + Math.random() * 10}s`
            }}
          />
        ))}
        
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative z-10 w-full max-w-md"
        >
          <div className="text-center mb-8">
            <motion.div
              animate={{ 
                rotate: [0, 5, -5, 0],
                scale: [1, 1.05, 1]
              }}
              transition={{ duration: 4, repeat: Infinity }}
              className="inline-block mb-4"
            >
              <Bug className="w-16 h-16 text-amber" />
            </motion.div>
            <h1 className="font-orbitron text-4xl font-bold text-amber mb-2">LOCUSTA</h1>
            <p className="text-warm/60 font-jetbrains text-sm">The Hive Command Interface</p>
          </div>

          <form onSubmit={handleLogin} className="panel p-6 space-y-4">
            <div>
              <label className="block text-sm font-orbitron text-amber mb-2">OPERATOR ID</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="input-field"
                placeholder="admin"
              />
            </div>
            <div>
              <label className="block text-sm font-orbitron text-amber mb-2">ACCESS KEY</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="input-field"
                placeholder="••••••••"
              />
            </div>
            <button type="submit" className="hex-button hex-button-primary w-full py-3">
              Initialize Connection
            </button>
          </form>
        </motion.div>
      </div>
    );
  }

  const activeWorkers = workers.filter(w => w.status === 'active').length;
  const idleWorkers = workers.filter(w => w.status === 'idle').length;

  return (
    <div className="min-h-screen bg-void relative">
      <div className="hex-grid absolute inset-0 pointer-events-none" />
      
      {/* Top Navigation */}
      <nav className="relative z-20 border-b border-amber/20 bg-void/80 backdrop-blur-md">
        <div className="max-w-[1920px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <motion.div
                animate={{ scale: [1, 1.1, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <Bug className="w-8 h-8 text-amber" />
              </motion.div>
              <div>
                <h1 className="font-orbitron text-xl font-bold text-amber">LOCUSTA</h1>
                <p className="text-xs text-warm/50 font-jetbrains">Hive Command v1.0</p>
              </div>
            </div>

            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2 px-4 py-2 bg-honeycomb/50 rounded-lg">
                <span className={`status-dot ${systemStatus === 'online' ? 'status-active' : 'status-offline'}`} />
                <span className="font-jetbrains text-sm text-warm">
                  {workers.length} workers | {activeWorkers} active
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button 
                  onClick={() => setActiveView('dashboard')}
                  className={`hex-button ${activeView === 'dashboard' ? 'hex-button-primary' : ''}`}
                >
                  <Activity className="w-4 h-4 inline mr-2" />
                  Hive
                </button>
                <button 
                  onClick={() => setActiveView('swarm')}
                  className={`hex-button ${activeView === 'swarm' ? 'hex-button-primary' : ''}`}
                >
                  <Zap className="w-4 h-4 inline mr-2" />
                  Swarm
                </button>
                <button 
                  onClick={() => setActiveView('attack')}
                  className={`hex-button ${activeView === 'attack' ? 'hex-button-primary' : ''}`}
                >
                  <Shield className="w-4 h-4 inline mr-2" />
                  Attack
                </button>
                <button 
                  onClick={() => setActiveView('ai')}
                  className={`hex-button ${activeView === 'ai' ? 'hex-button-primary' : ''}`}
                >
                  <Brain className="w-4 h-4 inline mr-2" />
                  AI Core
                </button>
                <button 
                  onClick={() => setActiveView('reports')}
                  className={`hex-button ${activeView === 'reports' ? 'hex-button-primary' : ''}`}
                >
                  <Globe className="w-4 h-4 inline mr-2" />
                  Reports
                </button>
                <button 
                  onClick={() => setActiveView('settings')}
                  className={`hex-button ${activeView === 'settings' ? 'hex-button-primary' : ''}`}
                >
                  <Settings className="w-4 h-4 inline mr-2" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="relative z-10 max-w-[1920px] mx-auto p-6">
        <AnimatePresence mode="wait">
          {activeView === 'dashboard' && (
            <motion.div
              key="dashboard"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
            >
              <Dashboard 
                workers={workers}
                activity={activity}
                onSelectWorker={setSelectedWorker}
              />
            </motion.div>
          )}

          {activeView === 'swarm' && (
            <motion.div
              key="swarm"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
            >
              <SwarmControl workers={workers} token={token} />
            </motion.div>
          )}

          {activeView === 'attack' && (
            <motion.div
              key="attack"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
            >
              <AttackConfig token={token} />
            </motion.div>
          )}

          {activeView === 'ai' && (
            <motion.div
              key="ai"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
            >
              <AIControl token={token} />
            </motion.div>
          )}

          {activeView === 'reports' && (
            <motion.div
              key="reports"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
            >
              <Reports token={token} />
            </motion.div>
          )}

          {activeView === 'settings' && (
            <motion.div
              key="settings"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
            >
              <SettingsPanel token={token} />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Worker Detail Modal */}
      <AnimatePresence>
        {selectedWorker && (
          <WorkerDetail 
            workerId={selectedWorker}
            onClose={() => setSelectedWorker(null)}
            token={token}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

export default App;
