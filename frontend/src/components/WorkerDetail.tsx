import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { X, Activity, Clock, Cpu, Terminal } from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8443/api';

interface WorkerDetailProps {
  workerId: string;
  onClose: () => void;
  token: string;
}

export default function WorkerDetail({ workerId, onClose, token }: WorkerDetailProps) {
  const [worker, setWorker] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);

  useEffect(() => {
    fetchWorker();
    fetchLogs();
    const interval = setInterval(() => {
      fetchWorker();
      fetchLogs();
    }, 2000);
    return () => clearInterval(interval);
  }, [workerId]);

  const fetchWorker = async () => {
    try {
      const resp = await axios.get(`${API_URL}/workers/${workerId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setWorker(resp.data);
    } catch (e) {
      console.error('Failed to fetch worker');
    }
  };

  const fetchLogs = async () => {
    try {
      const resp = await axios.get(`${API_URL}/activity?worker_id=${workerId}&limit=20`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setLogs(resp.data);
    } catch (e) {
      console.error('Failed to fetch logs');
    }
  };

  if (!worker) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-void/80 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.9, y: 20 }}
        className="panel w-full max-w-4xl max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        <div className="panel-header flex items-center justify-between">
          <span>Worker: {workerId}</span>
          <button onClick={onClose} className="text-warm/60 hover:text-amber">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="panel-body">
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-4">
              <div>
                <h3 className="font-orbitron text-amber text-sm mb-2">STATUS</h3>
                <div className="flex items-center">
                  <span className={`status-dot status-${worker.status}`} />
                  <span className="capitalize">{worker.status}</span>
                </div>
              </div>

              <div>
                <h3 className="font-orbitron text-amber text-sm mb-2">SYSTEM INFO</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-warm/60">Hostname</span>
                    <span>{worker.info?.hostname || '-'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-warm/60">IP Address</span>
                    <span className="font-jetbrains">{worker.info?.ip || '-'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-warm/60">OS</span>
                    <span className="capitalize">{worker.info?.os || '-'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-warm/60">Role</span>
                    <span className="capitalize">{worker.info?.role || '-'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-warm/60">Latency</span>
                    <span className="font-jetbrains">{worker.info?.latency_ms ? `${worker.info.latency_ms}ms` : '-'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-warm/60">Tasks Completed</span>
                    <span className="font-jetbrains">{worker.info?.tasks_completed || 0}</span>
                  </div>
                </div>
              </div>

              {worker.current_task && (
                <div>
                  <h3 className="font-orbitron text-amber text-sm mb-2">CURRENT TASK</h3>
                  <div className="p-3 bg-void rounded">
                    <div className="flex justify-between text-sm mb-2">
                      <span className="text-amber">{worker.current_task.type}</span>
                      <span>{worker.current_task.progress || 0}%</span>
                    </div>
                    <div className="w-full bg-honeycomb rounded-full h-2">
                      <div 
                        className="bg-amber h-2 rounded-full transition-all"
                        style={{ width: `${worker.current_task.progress || 0}%` }}
                      />
                    </div>
                    <div className="text-xs text-warm/60 mt-2">
                      Target: {worker.current_task.target}
                    </div>
                  </div>
                </div>
              )}

              <div className="flex gap-2 pt-4">
                <button className="hex-button text-xs">Retask</button>
                <button className="hex-button text-xs">Quarantine</button>
                <button className="hex-button hex-button-danger text-xs">Kill</button>
              </div>
            </div>

            <div>
              <h3 className="font-orbitron text-amber text-sm mb-2">LIVE LOGS</h3>
              <div className="bg-void rounded p-3 h-96 overflow-y-auto font-jetbrains text-xs">
                {logs.map((log, i) => (
                  <div key={i} className={`py-1 log-${log.severity}`}>
                    <span className="text-warm/40">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                    <span className="ml-2">{log.message}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
