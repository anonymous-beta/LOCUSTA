import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  Activity, Server, Cpu, Network, AlertTriangle,
  ChevronRight, Terminal
} from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

interface Worker {
  id: string;
  status: string;
  info: any;
  current_task?: any;
}

interface ActivityEntry {
  id: string;
  timestamp: string;
  severity: string;
  message: string;
  worker_id?: string;
}

interface DashboardProps {
  workers: Worker[];
  activity: ActivityEntry[];
  onSelectWorker: (id: string) => void;
}

const COLORS = ['#6ab04c', '#f0932b', '#eb4d4b', '#e88a1e'];

export default function Dashboard({ workers, activity, onSelectWorker }: DashboardProps) {
  const [rpsData, setRpsData] = useState<any[]>([]);
  const [filter, setFilter] = useState('all');

  // Simulate RPS data
  useEffect(() => {
    const interval = setInterval(() => {
      setRpsData(prev => [...prev.slice(-30), {
        time: new Date().toLocaleTimeString(),
        rps: Math.floor(Math.random() * 3000) + 500,
        workers: workers.filter(w => w.status === 'active').length
      }]);
    }, 2000);
    return () => clearInterval(interval);
  }, [workers]);

  const statusCounts = {
    active: workers.filter(w => w.status === 'active').length,
    idle: workers.filter(w => w.status === 'idle').length,
    offline: workers.filter(w => w.status === 'offline').length,
    quarantined: workers.filter(w => w.status === 'quarantined').length
  };

  const pieData = [
    { name: 'Active', value: statusCounts.active },
    { name: 'Idle', value: statusCounts.idle },
    { name: 'Offline', value: statusCounts.offline },
    { name: 'Quarantined', value: statusCounts.quarantined }
  ].filter(d => d.value > 0);

  const filteredActivity = filter === 'all' 
    ? activity 
    : activity.filter(a => a.severity === filter);

  return (
    <div className="grid grid-cols-12 gap-6 h-[calc(100vh-120px)]">
      {/* Left Panel - Swarm Control */}
      <div className="col-span-2 space-y-4">
        <div className="panel">
          <div className="panel-header">Swarm Control</div>
          <div className="panel-body space-y-3">
            <div className="space-y-2">
              <div className="text-xs font-orbitron text-amber/70">WORKER GROUPS</div>
              {['Scouts', 'Analyzers', 'Storm', 'Graffiti'].map(group => (
                <div key={group} className="flex items-center justify-between text-sm">
                  <span className="text-warm/80">{group}</span>
                  <span className="font-jetbrains text-amber">
                    {workers.filter(w => w.info?.role === group.toLowerCase().slice(0, -1)).length}
                  </span>
                </div>
              ))}
            </div>
            
            <div className="pt-4 space-y-2">
              <div className="text-xs font-orbitron text-amber/70">MASTER CONTROLS</div>
              <button className="hex-button w-full text-xs">Start Recon</button>
              <button className="hex-button w-full text-xs">Launch Attack</button>
              <button className="hex-button w-full text-xs">Deploy Deface</button>
              <button className="hex-button hex-button-danger w-full text-xs">Emergency Stop</button>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">Command Queue</div>
          <div className="panel-body max-h-48 overflow-y-auto">
            {workers.filter(w => w.current_task).map(w => (
              <div key={w.id} className="text-xs py-2 border-b border-amber/10">
                <div className="flex justify-between">
                  <span className="text-amber">{w.id}</span>
                  <span className="text-warm/60">{w.current_task?.type}</span>
                </div>
                <div className="w-full bg-void rounded-full h-1 mt-1">
                  <div 
                    className="bg-amber h-1 rounded-full transition-all"
                    style={{ width: `${w.current_task?.progress || 0}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Center Panel - Live Activity */}
      <div className="col-span-7 flex flex-col">
        <div className="panel flex-1 flex flex-col">
          <div className="panel-header flex items-center justify-between">
            <span>Live Activity Feed</span>
            <div className="flex gap-2">
              {['all', 'info', 'warning', 'critical', 'success'].map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-2 py-1 text-xs rounded ${filter === f ? 'bg-amber text-void' : 'text-warm/60 hover:text-amber'}`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-1">
            {filteredActivity.map((entry, i) => (
              <motion.div
                key={entry.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.01 }}
                className={`log-entry log-${entry.severity}`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    {entry.worker_id && (
                      <span className="text-amber/70 mr-2">[{entry.worker_id}]</span>
                    )}
                    <span>{entry.message}</span>
                  </div>
                  <span className="text-xs opacity-50 ml-4">
                    {new Date(entry.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>

      {/* Right Panel - Telemetry */}
      <div className="col-span-3 space-y-4">
        <div className="panel">
          <div className="panel-header">Requests Per Second</div>
          <div className="panel-body h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rpsData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="time" stroke="#f0e6d0" fontSize={10} />
                <YAxis stroke="#f0e6d0" fontSize={10} />
                <Tooltip 
                  contentStyle={{ background: '#0a0a0a', border: '1px solid #e88a1e' }}
                  labelStyle={{ color: '#e88a1e' }}
                />
                <Line type="monotone" dataKey="rps" stroke="#e88a1e" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">Worker Health</div>
          <div className="panel-body h-48">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ background: '#0a0a0a', border: '1px solid #e88a1e' }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex justify-center gap-4 mt-2 text-xs">
              {pieData.map((d, i) => (
                <div key={d.name} className="flex items-center">
                  <div className="w-3 h-3 rounded-full mr-1" style={{ background: COLORS[i] }} />
                  <span className="text-warm/70">{d.name}: {d.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">Active Workers</div>
          <div className="panel-body max-h-64 overflow-y-auto">
            {workers.filter(w => w.status === 'active').map(w => (
              <div 
                key={w.id}
                onClick={() => onSelectWorker(w.id)}
                className="flex items-center justify-between py-2 px-2 hover:bg-amber/10 cursor-pointer rounded group"
              >
                <div className="flex items-center">
                  <span className="status-dot status-active" />
                  <span className="font-jetbrains text-sm text-warm group-hover:text-amber">
                    {w.id}
                  </span>
                </div>
                <ChevronRight className="w-4 h-4 text-warm/30 group-hover:text-amber" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
