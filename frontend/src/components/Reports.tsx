import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Download, Calendar, Target, BarChart3, ArrowLeft } from 'lucide-react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8443/api';

interface ReportsProps {
  token: string;
}

export default function Reports({ token }: ReportsProps) {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState<any>(null);
  const [filter, setFilter] = useState({ date: '', target: '', type: '' });

  useEffect(() => {
    fetchCampaigns();
  }, []);

  const fetchCampaigns = async () => {
    try {
      const resp = await axios.get(`${API_URL}/reports/campaigns`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setCampaigns(resp.data);
    } catch (e) {
      console.error('Failed to fetch campaigns');
    }
  };

  const fetchCampaignDetail = async (id: string) => {
    try {
      const resp = await axios.get(`${API_URL}/reports/campaigns/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSelectedCampaign(resp.data);
    } catch (e) {
      console.error('Failed to fetch campaign detail');
    }
  };

  const exportReport = (campaignId: string) => {
    window.open(`${API_URL}/reports/campaigns/${campaignId}/export?token=${token}`, '_blank');
  };

  const filteredCampaigns = campaigns.filter(c => {
    if (filter.target && !c.target?.includes(filter.target)) return false;
    if (filter.date && !c.created_at?.startsWith(filter.date)) return false;
    return true;
  });

  // Mock data for charts if no real data
  const attackData = [
    { name: 'Recon', success: 45, failed: 5 },
    { name: 'Analyze', success: 32, failed: 8 },
    { name: 'Storm', success: 28, failed: 2 },
    { name: 'Deface', success: 15, failed: 3 }
  ];

  const timelineData = [
    { time: '00:00', intensity: 20 },
    { time: '04:00', intensity: 45 },
    { time: '08:00', intensity: 80 },
    { time: '12:00', intensity: 95 },
    { time: '16:00', intensity: 60 },
    { time: '20:00', intensity: 30 }
  ];

  if (selectedCampaign) {
    return (
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        className="space-y-6"
      >
        <button 
          onClick={() => setSelectedCampaign(null)}
          className="hex-button text-sm"
        >
          <ArrowLeft className="w-4 h-4 inline mr-2" />
          Back to Campaigns
        </button>

        <div className="panel">
          <div className="panel-header">Campaign Detail: {selectedCampaign.campaign.name}</div>
          <div className="panel-body">
            <div className="grid grid-cols-4 gap-4 mb-6">
              <div className="bg-void p-4 rounded">
                <div className="text-xs text-warm/60 mb-1">Target</div>
                <div className="font-jetbrains text-amber">{selectedCampaign.campaign.target}</div>
              </div>
              <div className="bg-void p-4 rounded">
                <div className="text-xs text-warm/60 mb-1">Status</div>
                <div className="capitalize">{selectedCampaign.campaign.status}</div>
              </div>
              <div className="bg-void p-4 rounded">
                <div className="text-xs text-warm/60 mb-1">Started</div>
                <div className="font-jetbrains text-sm">{new Date(selectedCampaign.campaign.created_at).toLocaleString()}</div>
              </div>
              <div className="bg-void p-4 rounded">
                <div className="text-xs text-warm/60 mb-1">Tasks</div>
                <div className="font-jetbrains text-amber">{selectedCampaign.tasks?.length || 0}</div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div>
                <h3 className="font-orbitron text-amber text-sm mb-3">Attack Intensity</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={timelineData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                    <XAxis dataKey="time" stroke="#f0e6d0" fontSize={10} />
                    <YAxis stroke="#f0e6d0" fontSize={10} />
                    <Tooltip contentStyle={{ background: '#0a0a0a', border: '1px solid #e88a1e' }} />
                    <Line type="monotone" dataKey="intensity" stroke="#e88a1e" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div>
                <h3 className="font-orbitron text-amber text-sm mb-3">Task Results</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={attackData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                    <XAxis dataKey="name" stroke="#f0e6d0" fontSize={10} />
                    <YAxis stroke="#f0e6d0" fontSize={10} />
                    <Tooltip contentStyle={{ background: '#0a0a0a', border: '1px solid #e88a1e' }} />
                    <Bar dataKey="success" fill="#6ab04c" />
                    <Bar dataKey="failed" fill="#eb4d4b" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="mt-6">
              <h3 className="font-orbitron text-amber text-sm mb-3">Task History</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs font-orbitron text-amber/70 border-b border-amber/20">
                    <th className="pb-2">Type</th>
                    <th className="pb-2">Target</th>
                    <th className="pb-2">Status</th>
                    <th className="pb-2">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedCampaign.tasks?.map((task: any) => (
                    <tr key={task.id} className="border-b border-amber/10">
                      <td className="py-2 capitalize">{task.task_type}</td>
                      <td className="py-2 font-jetbrains text-sm">{task.target}</td>
                      <td className="py-2">
                        <span className={`status-dot ${
                          task.status === 'completed' ? 'status-active' :
                          task.status === 'failed' ? 'status-offline' :
                          'status-idle'
                        }`} />
                        {task.status}
                      </td>
                      <td className="py-2 text-warm/60 text-sm">
                        {new Date(task.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="panel">
        <div className="panel-header">Campaign Filters</div>
        <div className="panel-body">
          <div className="grid grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-orbitron text-amber mb-2">DATE</label>
              <input
                type="date"
                value={filter.date}
                onChange={e => setFilter({...filter, date: e.target.value})}
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-xs font-orbitron text-amber mb-2">TARGET</label>
              <input
                type="text"
                value={filter.target}
                onChange={e => setFilter({...filter, target: e.target.value})}
                placeholder="Search targets..."
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-xs font-orbitron text-amber mb-2">ATTACK TYPE</label>
              <select 
                value={filter.type}
                onChange={e => setFilter({...filter, type: e.target.value})}
                className="select-field w-full"
              >
                <option value="">All Types</option>
                <option value="recon">Recon</option>
                <option value="analyze">Analysis</option>
                <option value="storm">DDoS</option>
                <option value="deface">Defacement</option>
              </select>
            </div>
            <div className="flex items-end">
              <button 
                onClick={() => window.open(`${API_URL}/reports/export-all?token=${token}`, '_blank')}
                className="hex-button hex-button-primary w-full"
              >
                <Download className="w-4 h-4 inline mr-2" />
                Export All
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Campaign List */}
      <div className="panel">
        <div className="panel-header">Campaign History</div>
        <div className="panel-body">
          {filteredCampaigns.length === 0 ? (
            <div className="text-center py-8 text-warm/40">
              <BarChart3 className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No campaigns recorded yet. Launch an attack to generate reports.</p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs font-orbitron text-amber/70 border-b border-amber/20">
                  <th className="pb-2">Name</th>
                  <th className="pb-2">Target</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Created</th>
                  <th className="pb-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredCampaigns.map(campaign => (
                  <tr 
                    key={campaign.id} 
                    className="border-b border-amber/10 hover:bg-amber/5 cursor-pointer"
                    onClick={() => fetchCampaignDetail(campaign.id)}
                  >
                    <td className="py-3">{campaign.name}</td>
                    <td className="py-3 font-jetbrains text-sm">{campaign.target}</td>
                    <td className="py-3">
                      <span className={`status-dot ${
                        campaign.status === 'completed' ? 'status-active' :
                        campaign.status === 'failed' ? 'status-offline' :
                        'status-idle'
                      }`} />
                      {campaign.status}
                    </td>
                    <td className="py-3 text-warm/60 text-sm">
                      {new Date(campaign.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3">
                      <button 
                        onClick={(e) => {
                          e.stopPropagation();
                          exportReport(campaign.id);
                        }}
                        className="p-1 text-amber hover:text-amber-light"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Intelligence Summary */}
      <div className="grid grid-cols-2 gap-6">
        <div className="panel">
          <div className="panel-header">Common Vulnerabilities</div>
          <div className="panel-body">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={attackData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis type="number" stroke="#f0e6d0" fontSize={10} />
                <YAxis dataKey="name" type="category" stroke="#f0e6d0" fontSize={10} />
                <Tooltip contentStyle={{ background: '#0a0a0a', border: '1px solid #e88a1e' }} />
                <Bar dataKey="success" fill="#e88a1e" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">Target Patterns</div>
          <div className="panel-body space-y-3">
            {[
              { pattern: 'Apache 2.4.x vulnerabilities', count: 12 },
              { pattern: 'WordPress plugin exploits', count: 8 },
              { pattern: 'SQL injection in login forms', count: 6 },
              { pattern: 'Cloudflare bypass required', count: 4 }
            ].map(item => (
              <div key={item.pattern} className="flex justify-between items-center py-2 border-b border-amber/10">
                <span className="text-sm">{item.pattern}</span>
                <span className="font-jetbrains text-amber">{item.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
