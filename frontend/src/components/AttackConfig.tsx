import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Play, Square, Eye, Shield, Zap, Brush } from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8443/api';

interface AttackConfigProps {
  token: string;
}

export default function AttackConfig({ token }: AttackConfigProps) {
  const [activeTab, setActiveTab] = useState('recon');
  const headers = { Authorization: `Bearer ${token}` };

  // Recon state
  const [reconTargets, setReconTargets] = useState('');
  const [reconScope, setReconScope] = useState('quick');
  const [reconStealth, setReconStealth] = useState(false);

  // Analyze state
  const [analyzeTarget, setAnalyzeTarget] = useState('');
  const [vulnClasses, setVulnClasses] = useState<string[]>(['sqli', 'xss']);
  const [autoExploit, setAutoExploit] = useState(false);

  // Storm state
  const [stormTarget, setStormTarget] = useState('');
  const [attackType, setAttackType] = useState('l7_http');
  const [duration, setDuration] = useState(300);
  const [workerCount, setWorkerCount] = useState('all');

  // Deface state
  const [defaceTarget, setDefaceTarget] = useState('');
  const [payloadType, setPayloadType] = useState('html');
  const [payloadContent, setPayloadContent] = useState('');
  const [revertHours, setRevertHours] = useState<number | null>(null);

  const startRecon = async () => {
    try {
      await axios.post(`${API_URL}/modules/recon`, {
        targets: reconTargets,
        scope: reconScope,
        stealth: reconStealth
      }, { headers });
    } catch (e) {
      console.error('Recon failed');
    }
  };

  const startAnalysis = async () => {
    try {
      await axios.post(`${API_URL}/modules/analyze`, {
        target: analyzeTarget,
        vuln_classes: vulnClasses,
        auto_exploit: autoExploit
      }, { headers });
    } catch (e) {
      console.error('Analysis failed');
    }
  };

  const startStorm = async () => {
    try {
      await axios.post(`${API_URL}/modules/storm`, {
        target: stormTarget,
        attack_type: attackType,
        duration: duration,
        worker_count: workerCount
      }, { headers });
    } catch (e) {
      console.error('Storm failed');
    }
  };

  const startDeface = async () => {
    try {
      await axios.post(`${API_URL}/modules/deface`, {
        target_url: defaceTarget,
        payload_type: payloadType,
        payload_content: payloadContent,
        revert_after_hours: revertHours
      }, { headers });
    } catch (e) {
      console.error('Deface failed');
    }
  };

  const tabs = [
    { id: 'recon', label: 'Recon', icon: Eye },
    { id: 'analyze', label: 'Analyze', icon: Shield },
    { id: 'storm', label: 'Storm', icon: Zap },
    { id: 'deface', label: 'Deface', icon: Brush }
  ];

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex gap-4 mb-6">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`hex-button ${activeTab === tab.id ? 'hex-button-primary' : ''}`}
            >
              <Icon className="w-4 h-4 inline mr-2" />
              {tab.label}
            </button>
          );
        })}
      </div>

      <motion.div
        key={activeTab}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="panel"
      >
        <div className="panel-header">
          {activeTab === 'recon' && 'Locust-Scout: Reconnaissance Module'}
          {activeTab === 'analyze' && 'Locust-Analyze: Vulnerability Analysis'}
          {activeTab === 'storm' && 'Locust-Storm: DDoS Module'}
          {activeTab === 'deface' && 'Locust-Graffiti: Defacement Engine'}
        </div>
        <div className="panel-body">
          {activeTab === 'recon' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-orbitron text-amber mb-2">TARGET DOMAINS</label>
                <input
                  type="text"
                  value={reconTargets}
                  onChange={e => setReconTargets(e.target.value)}
                  placeholder="target.com, example.org (comma-separated)"
                  className="input-field"
                />
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-orbitron text-amber mb-2">SCOPE</label>
                  <select 
                    value={reconScope}
                    onChange={e => setReconScope(e.target.value)}
                    className="select-field w-full"
                  >
                    <option value="quick">Quick Scan</option>
                    <option value="deep">Deep Recon</option>
                    <option value="full">Full Assault</option>
                  </select>
                </div>
                <div className="flex items-end pb-2">
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={reconStealth}
                      onChange={e => setReconStealth(e.target.checked)}
                      className="mr-2"
                    />
                    <span className="text-sm">Stealth Mode</span>
                  </label>
                </div>
              </div>
              <button onClick={startRecon} className="hex-button hex-button-primary">
                <Play className="w-4 h-4 inline mr-2" />
                Start Reconnaissance
              </button>
            </div>
          )}

          {activeTab === 'analyze' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-orbitron text-amber mb-2">TARGET</label>
                <input
                  type="text"
                  value={analyzeTarget}
                  onChange={e => setAnalyzeTarget(e.target.value)}
                  placeholder="http://target.com"
                  className="input-field"
                />
              </div>
              <div>
                <label className="block text-sm font-orbitron text-amber mb-2">VULNERABILITY CLASSES</label>
                <div className="flex gap-4">
                  {['sqli', 'xss', 'lfi', 'xxe', 'ssrf'].map(vc => (
                    <label key={vc} className="flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={vulnClasses.includes(vc)}
                        onChange={e => {
                          if (e.target.checked) {
                            setVulnClasses([...vulnClasses, vc]);
                          } else {
                            setVulnClasses(vulnClasses.filter(v => v !== vc));
                          }
                        }}
                        className="mr-2"
                      />
                      <span className="text-sm uppercase">{vc}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <label className="flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoExploit}
                    onChange={e => setAutoExploit(e.target.checked)}
                    className="mr-2"
                  />
                  <span className="text-sm">Auto-Exploit (attempt exploitation if found)</span>
                </label>
              </div>
              <button onClick={startAnalysis} className="hex-button hex-button-primary">
                <Play className="w-4 h-4 inline mr-2" />
                Start Analysis
              </button>
            </div>
          )}

          {activeTab === 'storm' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-orbitron text-amber mb-2">TARGET</label>
                <input
                  type="text"
                  value={stormTarget}
                  onChange={e => setStormTarget(e.target.value)}
                  placeholder="target.com or IP"
                  className="input-field"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-orbitron text-amber mb-2">ATTACK TYPE</label>
                  <select 
                    value={attackType}
                    onChange={e => setAttackType(e.target.value)}
                    className="select-field w-full"
                  >
                    <optgroup label="Layer 7">
                      <option value="l7_http">HTTP Flood</option>
                      <option value="l7_slowloris">Slowloris</option>
                    </optgroup>
                    <optgroup label="Layer 4">
                      <option value="l4_syn">SYN Flood</option>
                      <option value="l4_udp">UDP Flood</option>
                    </optgroup>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-orbitron text-amber mb-2">DURATION (seconds)</label>
                  <input
                    type="number"
                    value={duration}
                    onChange={e => setDuration(parseInt(e.target.value))}
                    className="input-field"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-orbitron text-amber mb-2">WORKERS</label>
                <select 
                  value={workerCount}
                  onChange={e => setWorkerCount(e.target.value)}
                  className="select-field w-full"
                >
                  <option value="all">Use All Available</option>
                  <option value="5">5 Workers</option>
                  <option value="10">10 Workers</option>
                  <option value="25">25 Workers</option>
                  <option value="50">50 Workers</option>
                </select>
              </div>
              <button onClick={startStorm} className="hex-button hex-button-danger">
                <Zap className="w-4 h-4 inline mr-2" />
                Initiate Storm
              </button>
            </div>
          )}

          {activeTab === 'deface' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-orbitron text-amber mb-2">TARGET URL</label>
                <input
                  type="text"
                  value={defaceTarget}
                  onChange={e => setDefaceTarget(e.target.value)}
                  placeholder="http://target.com/page.html"
                  className="input-field"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-orbitron text-amber mb-2">PAYLOAD TYPE</label>
                  <select 
                    value={payloadType}
                    onChange={e => setPayloadType(e.target.value)}
                    className="select-field w-full"
                  >
                    <option value="html">HTML Replacement</option>
                    <option value="js">JavaScript Injection</option>
                    <option value="upload">File Upload</option>
                    <option value="db">Database Edit</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-orbitron text-amber mb-2">REVERT AFTER (hours)</label>
                  <input
                    type="number"
                    value={revertHours || ''}
                    onChange={e => setRevertHours(e.target.value ? parseInt(e.target.value) : null)}
                    placeholder="Leave empty for permanent"
                    className="input-field"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-orbitron text-amber mb-2">PAYLOAD CONTENT</label>
                <textarea
                  value={payloadContent}
                  onChange={e => setPayloadContent(e.target.value)}
                  placeholder={payloadType === 'html' ? '<html><body><h1>Defaced by LOCUSTA</h1></body></html>' : 'alert("LOCUSTA was here");'}
                  className="input-field h-32 resize-none font-jetbrains"
                />
              </div>
              <button onClick={startDeface} className="hex-button hex-button-primary">
                <Brush className="w-4 h-4 inline mr-2" />
                Deploy Defacement
              </button>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
