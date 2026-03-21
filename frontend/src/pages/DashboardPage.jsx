import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  BarChart3, Rocket, Server, AlertTriangle, Globe, ExternalLink,
  Download, Github, FileArchive, Clock, CheckCircle2, XCircle, Loader2,
  RefreshCw
} from 'lucide-react';

const API_URL = "http://localhost:8000";

const statusConfig = {
  success: { color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/30', icon: CheckCircle2, label: 'Live' },
  running: { color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/30', icon: Loader2, label: 'Running' },
  pending: { color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/30', icon: Clock, label: 'Pending' },
  failed:  { color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30', icon: XCircle, label: 'Failed' },
  stopped: { color: 'text-zinc-400', bg: 'bg-zinc-500/10 border-zinc-500/30', icon: XCircle, label: 'Stopped' },
};

function StatusBadge({ status }) {
  const cfg = statusConfig[status] || statusConfig.pending;
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold tracking-widest uppercase rounded-full border ${cfg.bg} ${cfg.color}`}>
      <Icon size={12} className={status === 'running' ? 'animate-spin' : ''} />
      {cfg.label}
    </span>
  );
}

function StatCard({ icon: Icon, label, value, color = 'purple', sub }) {
  const colors = {
    purple: 'border-purple-500/20 bg-purple-500/5 text-purple-400',
    green: 'border-emerald-500/20 bg-emerald-500/5 text-emerald-400',
    red: 'border-red-500/20 bg-red-500/5 text-red-400',
    blue: 'border-blue-500/20 bg-blue-500/5 text-blue-400',
    yellow: 'border-yellow-500/20 bg-yellow-500/5 text-yellow-400',
  };
  return (
    <div className={`border rounded-xl p-5 ${colors[color]} backdrop-blur-sm transition-all hover:scale-[1.02]`}>
      <div className="flex items-center justify-between mb-3">
        <Icon size={20} className="opacity-70" />
        <span className="text-2xl font-bold">{value}</span>
      </div>
      <p className="text-[11px] font-semibold tracking-widest uppercase opacity-60">{label}</p>
      {sub && <p className="text-[10px] mt-1 opacity-40">{sub}</p>}
    </div>
  );
}

export default function DashboardPage({ onOpenTerminal }) {
  const { token } = useAuth();
  const [stats, setStats] = useState(null);
  const [deployments, setDeployments] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const headers = { Authorization: `Bearer ${token}` };

  const fetchData = async () => {
    try {
      const [dashRes, depRes] = await Promise.all([
        fetch(`${API_URL}/api/dashboard`, { headers }),
        fetch(`${API_URL}/api/deployments?limit=50`, { headers })
      ]);
      if (dashRes.ok) setStats(await dashRes.json());
      if (depRes.ok) {
        const data = await depRes.json();
        setDeployments(data.deployments || []);
        setTotal(data.total || 0);
      }
    } catch (err) {
      console.error('Failed to fetch dashboard:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleRefresh = () => { setRefreshing(true); fetchData(); };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={28} className="text-purple-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 lg:p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-wide">Dashboard</h1>
          <p className="text-zinc-500 text-sm mt-1">Overview of your deployment activity</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={handleRefresh}
            className="p-2.5 border border-zinc-800 rounded-lg text-zinc-400 hover:text-white hover:border-zinc-600 transition-all">
            <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
          </button>
          <button onClick={onOpenTerminal}
            className="flex items-center gap-2 px-5 py-2.5 bg-purple-500/15 border border-purple-500/40 text-purple-400 rounded-lg text-sm font-bold tracking-wide hover:bg-purple-500/25 hover:border-purple-500/60 hover:shadow-[0_0_20px_rgba(168,85,247,0.15)] transition-all">
            <Rocket size={16} />
            New Deploy
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Rocket} label="Total Deploys" value={stats?.total_deployments || 0} color="purple" />
        <StatCard icon={CheckCircle2} label="Active / Live" value={stats?.active_deployments || 0} color="green" />
        <StatCard icon={AlertTriangle} label="Failed" value={stats?.failed_deployments || 0} color="red" />
        <StatCard icon={Server} label="AWS Services" value={stats?.services_used?.length || 0} color="blue"
          sub={stats?.services_used?.join(', ') || 'None yet'} />
      </div>

      {/* Deployments Table */}
      <div className="border border-zinc-800/60 rounded-xl overflow-hidden bg-zinc-950/50 backdrop-blur-sm">
        <div className="px-6 py-4 border-b border-zinc-800/60 flex items-center justify-between">
          <h2 className="text-sm font-bold text-white tracking-wide">Deployment History</h2>
          <span className="text-[10px] text-zinc-500 tracking-widest">{total} TOTAL</span>
        </div>

        {deployments.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-zinc-600">
            <Rocket size={40} className="mb-4 opacity-30" />
            <p className="text-sm font-semibold tracking-wide">No deployments yet</p>
            <p className="text-xs mt-1 opacity-60">Click "New Deploy" to get started</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800/40">
                  <th className="text-left px-6 py-3 text-[10px] text-zinc-500 font-bold tracking-widest uppercase">Source</th>
                  <th className="text-left px-6 py-3 text-[10px] text-zinc-500 font-bold tracking-widest uppercase">Type</th>
                  <th className="text-left px-6 py-3 text-[10px] text-zinc-500 font-bold tracking-widest uppercase">Status</th>
                  <th className="text-left px-6 py-3 text-[10px] text-zinc-500 font-bold tracking-widest uppercase">Endpoint</th>
                  <th className="text-left px-6 py-3 text-[10px] text-zinc-500 font-bold tracking-widest uppercase">Service</th>
                  <th className="text-left px-6 py-3 text-[10px] text-zinc-500 font-bold tracking-widest uppercase">Date</th>
                  <th className="text-left px-6 py-3 text-[10px] text-zinc-500 font-bold tracking-widest uppercase">Actions</th>
                </tr>
              </thead>
              <tbody>
                {deployments.map((d) => (
                  <tr key={d.id} className="border-b border-zinc-800/20 hover:bg-zinc-900/40 transition-colors group">
                    {/* Source */}
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2.5">
                        {d.source_type === 'github' ? (
                          <Github size={16} className="text-zinc-400 shrink-0" />
                        ) : (
                          <FileArchive size={16} className="text-zinc-400 shrink-0" />
                        )}
                        <div>
                          <p className="text-zinc-200 font-medium text-xs truncate max-w-[180px]">
                            {d.source_filename || d.repo_url?.split('/').pop() || '—'}
                          </p>
                          {d.repo_url && (
                            <a href={d.repo_url} target="_blank" rel="noreferrer"
                              className="text-[10px] text-purple-400/60 hover:text-purple-400 transition-colors truncate block max-w-[180px]">
                              {d.repo_url.replace('https://github.com/', '')}
                            </a>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Type */}
                    <td className="px-6 py-4">
                      <span className="text-[10px] text-zinc-400 bg-zinc-800/50 px-2 py-0.5 rounded tracking-wide uppercase">
                        {d.deployment_type || d.project_type || '—'}
                      </span>
                    </td>

                    {/* Status */}
                    <td className="px-6 py-4">
                      <StatusBadge status={d.status} />
                    </td>

                    {/* Endpoint */}
                    <td className="px-6 py-4">
                      {d.endpoint ? (
                        <a href={d.endpoint} target="_blank" rel="noreferrer"
                          className="text-cyan-400 hover:text-cyan-300 text-xs flex items-center gap-1.5 transition-colors">
                          <Globe size={12} />
                          <span className="truncate max-w-[150px]">{d.endpoint.replace(/https?:\/\//, '')}</span>
                          <ExternalLink size={10} className="opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                        </a>
                      ) : (
                        <span className="text-zinc-600 text-xs">—</span>
                      )}
                    </td>

                    {/* AWS Service */}
                    <td className="px-6 py-4">
                      <span className="text-[10px] text-zinc-400 uppercase tracking-wider">
                        {d.aws_service || '—'}
                      </span>
                    </td>

                    {/* Date */}
                    <td className="px-6 py-4">
                      <span className="text-xs text-zinc-500">
                        {new Date(d.created_at).toLocaleDateString('en-IN', {
                          day: '2-digit', month: 'short', year: 'numeric'
                        })}
                      </span>
                      <span className="text-[10px] text-zinc-600 block">
                        {new Date(d.created_at).toLocaleTimeString('en-IN', {
                          hour: '2-digit', minute: '2-digit'
                        })}
                      </span>
                    </td>

                    {/* Actions */}
                    <td className="px-6 py-4">
                      {d.source_type === 'github' && d.repo_url ? (
                        <a href={d.repo_url} target="_blank" rel="noreferrer"
                          className="inline-flex items-center gap-1 text-[10px] text-zinc-400 hover:text-purple-400 border border-zinc-800 hover:border-purple-500/30 px-2 py-1 rounded transition-all">
                          <Github size={12} /> Repo
                        </a>
                      ) : d.file_path ? (
                        <a href={`${API_URL}/api/deployments/${d.id}/download`}
                          className="inline-flex items-center gap-1 text-[10px] text-zinc-400 hover:text-purple-400 border border-zinc-800 hover:border-purple-500/30 px-2 py-1 rounded transition-all">
                          <Download size={12} /> Download
                        </a>
                      ) : (
                        <span className="text-zinc-700 text-xs">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
