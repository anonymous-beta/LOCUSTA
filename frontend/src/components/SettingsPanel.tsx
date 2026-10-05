import React from 'react';

interface SettingsPanelProps {
  token: string;
}

export default function SettingsPanel({ token }: SettingsPanelProps) {
  return (
    <div className="panel p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-orbitron text-2xl text-amber">Settings</h2>
        <span className="text-xs uppercase tracking-[0.25em] text-warm/60">Token</span>
      </div>

      <div className="rounded-xl border border-amber/20 bg-void/70 p-4">
        <p className="text-sm text-warm/70">Session status</p>
        <p className="mt-2 break-all font-jetbrains text-xs text-amber">
          {token ? 'Authenticated' : 'No active token'}
        </p>
      </div>

      <div className="rounded-xl border border-amber/20 bg-void/70 p-4">
        <p className="text-sm text-warm/70">Notes</p>
        <p className="mt-2 text-sm text-warm/80">
          This placeholder panel keeps the dashboard shell working while the real settings UI is implemented.
        </p>
      </div>
    </div>
  );
}
