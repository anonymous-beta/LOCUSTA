import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Brain, Play, Pause, Settings, Check, X } from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8443/api';

interface AIControlProps {
  token: string;
}

export default function AIControl({ token }: AIControlProps) {
  const [status, setStatus] = useState<any>(null);
  const [reasoning, setReasoning] = useState<any[]>([]);
  const [config, setConfig] = useState({
    provider: 'openai',
    api_key: '',
    model: 'gpt-4',
    base_url: ''
  });
  const [personality, setPersonality] = useState({
    aggression: 0.7,
    creativity: 0.5,
    caution: 0.3,
    methodical: 0.6
  });

  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    fetchStatus();
    fetchReasoning();
    const interval = setInterval(fetchReasoning, 3000);
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const resp = await axios.get(`${API_URL}/ai/status`, { headers });
      setStatus(resp.data);
      setPersonality(resp.data.personality);
    } catch (e) {
      console.error('Failed to fetch AI status');
    }
  };

  const fetchReasoning = async () => {
    try {
      const resp = await axios.get(`${API_URL}/ai/reasoning?limit=20`, { headers });
      setReasoning(resp.data);
    } catch (e) {
      console.error('Failed to fetch reasoning');
    }
  };

  const toggleAI = async (enabled: boolean) => {
    try {
      await axios.post(`${API_URL}/ai/toggle`, { enabled }, { headers });
      fetchStatus();
    } catch (e) {
      console.error('Toggle failed');
    }
  };

  const toggleAutoExecute = async (auto: boolean) => {
    try {
      await axios.post(`${API_URL}/ai/toggle`, { auto_execute: auto }, { headers });
      fetchStatus();
    } catch (e) {
      console.error('Toggle failed');
    }
  };

  const pauseAI = async () => {
    try {
      await axios.post(`${API_URL}/ai/pause`, {}, { headers });
      fetchStatus();
    } catch (e) {
      console.error('Pause failed');
    }
  };

  const resumeAI = async () => {
    try {
      await axios.post(`${API_URL}/ai/resume`, {}, { headers });
      fetchStatus();
    } catch (e) {
      console.error('Resume failed');
    }
  };

  const updatePersonality = async () => {
    try {
      await axios.post(`${API_URL}/ai/personality`, personality, { headers });
      fetchStatus();
    } catch (e) {
      console.error('Personality update failed');
    }
  };

  const saveConfig = async () => {
    try {
      await axios.post(`${API_URL}/ai/config`, config, { headers });
      alert('AI configuration saved');
    } catch (e) {
      console.error('Config save failed');
    }
  };

  const approveDecision = async () => {
    try {
      await axios.post(`${API_URL}/ai/approve`, {}, { headers });
      fetchReasoning();
    } catch (e) {
      console.error('Approve failed');
    }
  };

  if (!status) return <div className="text-amber">Loading AI core...</div>;

  return (
    <div className="grid grid-cols-12 gap-6">
      {/* AI Status */}
      <div className="col-span-4 space-y-4">
        <div className="panel">
          <div className="panel-header flex items-center justify-between">
            <span>Hive Mind Status</span>
            <Brain className={`w-5 h-5 ${status.enabled ? 'text-amber animate-pulse' : 'text-warm/30'}`} />
          </div>
          <div className="panel-body space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm">Autonomous Mode</span>
              <button 
                onClick={() => toggleAI(!status.enabled)}
                className={`w-12 h-6 rounded-full transition-colors ${status.enabled ? 'bg-amber' : 'bg-honeycomb'}`}
              >
                <div className={`w-5 h-5 rounded-full bg-void transition-transform ${status.enabled ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-sm">Auto-Execute</span>
              <button 
                onClick={() => toggleAutoExecute(!status.auto_execute)}
                className={`w-12 h-6 rounded-full transition-colors ${status.auto_execute ? 'bg-blood' : 'bg-honeycomb'}`}
              >
                <div className={`w-5 h-5 rounded-full bg-void transition-transform ${status.auto_execute ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>

            <div className="pt-4 border-t border-amber/20">
              <div className="flex justify-between text-sm mb-2">
                <span>Confidence</span>
                <span className="font-jetbrains text-amber">{(status.confidence * 100).toFixed(0)}%</span>
              </div>
              <div className="w-full bg-void rounded-full h-2">
                <div 
                  className="bg-amber h-2 rounded-full transition-all"
                  style={{ width: `${status.confidence * 100}%` }}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 pt-4">
              {status.paused ? (
                <button onClick={resumeAI} className="hex-button hex-button-primary text-xs">
                  <Play className="w-3 h-3 inline mr-1" />
                  Resume
                </button>
              ) : (
                <button onClick={pauseAI} className="hex-button text-xs">
                  <Pause className="w-3 h-3 inline mr-1" />
                  Pause
                </button>
              )}
              <button onClick={approveDecision} className="hex-button hex-button-primary text-xs">
                <Check className="w-3 h-3 inline mr-1" />
                Approve
              </button>
            </div>
          </div>
        </div>

        {/* Personality Sliders */}
        <div className="panel">
          <div className="panel-header">Personality Matrix</div>
          <div className="panel-body space-y-4">
            {[
              { key: 'aggression', label: 'Aggression', color: 'blood' },
              { key: 'creativity', label: 'Creativity', color: 'amber' },
              { key: 'caution', label: 'Caution', color: 'wheat' },
              { key: 'methodical', label: 'Methodical', color: 'chlorophyll' }
            ].map(({ key, label, color }) => (
              <div key={key}>
                <div className="flex justify-between text-sm mb-1">
                  <span>{label}</span>
                  <span className="font-jetbrains text-amber">{personality[key as keyof typeof personality].toFixed(1)}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={personality[key as keyof typeof personality]}
                  onChange={e => setPersonality({
                    ...personality,
                    [key]: parseFloat(e.target.value)
                  })}
                  className="w-full h-2 bg-void rounded-lg appearance-none cursor-pointer"
                  style={{ accentColor: '#e88a1e' }}
                />
              </div>
            ))}
            <button onClick={updatePersonality} className="hex-button w-full text-xs">
              Update Personality
            </button>
          </div>
        </div>

        {/* AI Config */}
        <div className="panel">
          <div className="panel-header">AI Provider</div>
          <div className="panel-body space-y-3">
            <select 
              value={config.provider}
              onChange={e => setConfig({...config, provider: e.target.value})}
              className="select-field w-full"
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="local">Local (Ollama/LM Studio)</option>
            </select>
            <input
              type="password"
              placeholder="API Key"
              value={config.api_key}
              onChange={e => setConfig({...config, api_key: e.target.value})}
              className="input-field"
            />
            <input
              type="text"
              placeholder="Model (gpt-4, claude-3, llama2, etc.)"
              value={config.model}
              onChange={e => setConfig({...config, model: e.target.value})}
              className="input-field"
            />
            <input
              type="text"
              placeholder="Base URL (optional)"
              value={config.base_url}
              onChange={e => setConfig({...config, base_url: e.target.value})}
              className="input-field"
            />
            <button onClick={saveConfig} className="hex-button hex-button-primary w-full text-xs">
              Save & Test Connection
            </button>
          </div>
        </div>
      </div>

      {/* Reasoning Stream */}
      <div className="col-span-8">
        <div className="panel h-full flex flex-col">
          <div className="panel-header">Live Reasoning Stream</div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {reasoning.length === 0 ? (
              <div className="text-warm/40 text-center py-8">
                No reasoning activity. Enable autonomous mode to see the hive mind think.
              </div>
            ) : (
              reasoning.map((entry, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`p-3 rounded border-l-2 ${
                    entry.type === 'decision' ? 'border-amber bg-amber/10' :
                    entry.type === 'action' ? 'border-chlorophyll bg-chlorophyll/10' :
                    entry.type === 'error' ? 'border-blood bg-blood/10' :
                    'border-blue-500 bg-blue-500/10'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <span className={`text-xs font-orbitron uppercase mr-2 ${
                        entry.type === 'decision' ? 'text-amber' :
                        entry.type === 'action' ? 'text-chlorophyll' :
                        entry.type === 'error' ? 'text-blood' :
                        'text-blue-400'
                      }`}>
                        {entry.type}
                      </span>
                      <span className="text-sm">{entry.content}</span>
                    </div>
                    <span className="text-xs text-warm/40">
                      {new Date(entry.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                </motion.div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
