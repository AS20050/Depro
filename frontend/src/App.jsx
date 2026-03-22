import React, { useState, useEffect, useRef } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import AuthCallback from './pages/AuthCallback';
import DashboardPage from './pages/DashboardPage';
import BillingDashboard from './pages/BillingDashboard';
import {
  Monitor, Paperclip, Globe, Loader2, Server, Github, Lock, Key,
  ShieldCheck, GitBranch, AlertCircle, LogOut, User as UserIcon,
  LayoutDashboard, Terminal as TerminalIcon, Rocket, ChevronLeft, X
} from 'lucide-react';

const API_URL = "http://localhost:8000";

const customStyles = `
  .retro-glow { text-shadow: 0 0 10px currentColor; }
  .retro-text-base { text-shadow: 0 0 2px rgba(255, 255, 255, 0.5); }
  .scrollbar-hide::-webkit-scrollbar { display: none; }
  .scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
`;

// --- COMPONENTS ---
const TerminalButton = ({ children, onClick, variant = 'primary', className = '', icon: Icon, disabled = false }) => {
  const baseStyles = "relative px-4 py-2 font-mono text-sm border transition-all duration-75 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed active:translate-x-[2px] active:translate-y-[2px] active:shadow-none uppercase tracking-widest";
  const variants = {
    primary: "bg-purple-900/20 border-purple-400/50 text-purple-300 hover:bg-purple-500 hover:text-black shadow-[0_0_10px_rgba(168,85,247,0.4)] retro-text-base",
    ghost: "bg-transparent border-transparent text-zinc-500 hover:text-purple-400 px-2",
  };
  return (
    <button onClick={onClick} disabled={disabled} className={`${baseStyles} ${variants[variant]} ${className}`}>
      {Icon && <Icon size={16} />} {children}
    </button>
  );
};

// --- AWS MODAL ---
const AwsAuthModal = ({ isOpen, onSubmit, onCancel }) => {
  const [accessKey, setAccessKey] = useState('');
  const [secretKey, setSecretKey] = useState('');
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-[200] bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-zinc-950 border border-yellow-500/50 shadow-[0_0_50px_rgba(234,179,8,0.15)] p-8 rounded-xl">
        <div className="flex items-center gap-3 mb-6 border-b border-zinc-800 pb-4">
          <ShieldCheck className="text-yellow-500 animate-pulse" size={24} />
          <h2 className="text-yellow-500 font-mono text-xl tracking-widest font-bold">SECURITY CLEARANCE</h2>
        </div>
        <div className="space-y-4 mb-8">
          <div><label className="text-[10px] text-zinc-500 font-mono uppercase tracking-widest mb-1 block">Access Key ID</label>
            <div className="relative"><Key className="absolute left-3 top-3 text-zinc-600" size={16} />
              <input type="text" value={accessKey} onChange={e => setAccessKey(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 text-yellow-100 font-mono p-2.5 pl-10 rounded-lg focus:border-yellow-500 focus:outline-none" placeholder="AKIA..." /></div></div>
          <div><label className="text-[10px] text-zinc-500 font-mono uppercase tracking-widest mb-1 block">Secret Access Key</label>
            <div className="relative"><Lock className="absolute left-3 top-3 text-zinc-600" size={16} />
              <input type="password" value={secretKey} onChange={e => setSecretKey(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 text-yellow-100 font-mono p-2.5 pl-10 rounded-lg focus:border-yellow-500 focus:outline-none" placeholder="••••••••••••••••••••" /></div></div>
        </div>
        <div className="flex gap-4">
          <TerminalButton onClick={onCancel} variant="ghost" className="flex-1">CANCEL</TerminalButton>
          <button onClick={() => onSubmit({ accessKey, secretKey })} disabled={!accessKey || !secretKey}
            className="flex-1 bg-yellow-500/20 border border-yellow-500 text-yellow-500 hover:bg-yellow-500 hover:text-black py-2 font-mono text-sm tracking-widest rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed">AUTHENTICATE & DEPLOY</button>
        </div>
      </div>
    </div>
  );
};

// --- GITHUB CI/CD MODAL ---
const GithubAuthModal = ({ isOpen, onSubmit, onCancel }) => {
  const [token, setToken] = useState('');
  const [awsAccessKey, setAwsAccessKey] = useState('');
  const [awsSecretKey, setAwsSecretKey] = useState('');
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-[200] bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-zinc-950 border border-purple-500/50 shadow-[0_0_50px_rgba(168,85,247,0.15)] p-8 rounded-xl max-h-[90vh] overflow-y-auto scrollbar-hide">
        <div className="flex items-center gap-3 mb-6 border-b border-zinc-800 pb-4">
          <GitBranch className="text-purple-500 animate-pulse" size={24} />
          <h2 className="text-purple-500 font-mono text-xl tracking-widest font-bold">CI/CD CONFIG</h2>
        </div>
        <div className="space-y-4 mb-8">
          <div><label className="text-[10px] text-zinc-500 font-mono uppercase tracking-widest mb-1 block">GitHub PAT</label>
            <div className="relative"><Github className="absolute left-3 top-3 text-zinc-600" size={16} />
              <input type="password" value={token} onChange={e => setToken(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 text-purple-100 font-mono p-2.5 pl-10 rounded-lg focus:border-purple-500 focus:outline-none" placeholder="ghp_xxxxxxxxxxxx" /></div>
            <p className="text-[10px] text-zinc-600 mt-1">* Leave empty for Snapshot mode</p></div>
          <div className="border-t border-zinc-800 pt-4"><div className="flex items-center gap-2 mb-3"><ShieldCheck className="text-yellow-500" size={16} /><span className="text-[10px] text-yellow-500/80 font-mono uppercase tracking-widest font-bold">AWS IAM</span></div></div>
          <div><label className="text-[10px] text-zinc-500 font-mono uppercase tracking-widest mb-1 block">Access Key ID</label>
            <div className="relative"><Key className="absolute left-3 top-3 text-zinc-600" size={16} />
              <input type="text" value={awsAccessKey} onChange={e => setAwsAccessKey(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 text-yellow-100 font-mono p-2.5 pl-10 rounded-lg focus:border-yellow-500 focus:outline-none" placeholder="AKIA..." /></div></div>
          <div><label className="text-[10px] text-zinc-500 font-mono uppercase tracking-widest mb-1 block">Secret Key</label>
            <div className="relative"><Lock className="absolute left-3 top-3 text-zinc-600" size={16} />
              <input type="password" value={awsSecretKey} onChange={e => setAwsSecretKey(e.target.value)} className="w-full bg-zinc-900 border border-zinc-700 text-yellow-100 font-mono p-2.5 pl-10 rounded-lg focus:border-yellow-500 focus:outline-none" placeholder="••••••••••••••••••••" /></div></div>
        </div>
        <div className="flex gap-4">
          <TerminalButton onClick={onCancel} variant="ghost" className="flex-1">CANCEL</TerminalButton>
          <button onClick={() => onSubmit({ token, awsAccessKey, awsSecretKey })} disabled={!awsAccessKey || !awsSecretKey}
            className="flex-1 bg-purple-500/20 border border-purple-500 text-purple-500 hover:bg-purple-500 hover:text-black py-2 font-mono text-sm tracking-widest rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed">{token ? "ENABLE CI/CD" : "DEPLOY SNAPSHOT"}</button>
        </div>
      </div>
    </div>
  );
};

const SuccessCard = ({ endpoint, deployment, warning }) => (
  <div className="mt-4 p-4 bg-zinc-900/90 border border-green-500/50 rounded-lg shadow-[0_0_20px_rgba(34,197,94,0.2)] relative overflow-hidden group">
    <div className="absolute top-0 left-0 w-full h-[2px] bg-green-500/50 animate-pulse" />
    <div className="flex items-start gap-4 relative z-10">
      <div className="p-3 bg-green-500/10 border border-green-500/30 rounded-lg"><Globe className="w-6 h-6 text-green-400" /></div>
      <div className="flex-1 space-y-3">
        <div className="flex items-center justify-between border-b border-green-500/20 pb-2">
          <h3 className="text-green-400 font-bold font-mono text-sm tracking-widest">DEPLOYED</h3>
          <span className="text-[10px] bg-green-900/40 text-green-300 px-2 py-0.5 border border-green-500/40 uppercase font-mono rounded">{deployment || "UNKNOWN"}</span>
        </div>
        {warning && (<div className="flex items-start gap-2 text-yellow-400 text-xs bg-yellow-900/20 p-2 border border-yellow-500/30 font-mono rounded"><AlertCircle size={14} className="shrink-0 mt-0.5" /><p>{warning}</p></div>)}
        <div className="bg-black/80 p-3 border border-zinc-700/50 rounded-lg flex flex-col gap-1 group-hover:border-green-500/50 transition-colors">
          <span className="text-zinc-500 text-[10px] uppercase tracking-widest font-mono">Live Endpoint</span>
          <a href={endpoint} target="_blank" rel="noreferrer" className="text-cyan-400 hover:text-cyan-300 font-mono text-lg break-all hover:underline flex items-center gap-2 transition-all">{endpoint} <Server size={14} /></a>
        </div>
      </div>
    </div>
  </div>
);


// =============================================
// TERMINAL VIEW (Panel)
// =============================================
function TerminalPanel({ onClose }) {
  const { user, token } = useAuth();
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [showAwsModal, setShowAwsModal] = useState(false);
  const [showGithubModal, setShowGithubModal] = useState(false);
  const [pendingFile, setPendingFile] = useState(null);
  const [pendingRepoUrl, setPendingRepoUrl] = useState('');
  const scrollRef = useRef(null);
  const fileInputRef = useRef(null);

  const username = user?.username || 'user';
  const displayName = user?.display_name || username;

  const [messages, setMessages] = useState([
    { id: 1, role: 'system', content: `DePro Terminal v3.0 • Logged in as ${displayName}`, timestamp: new Date().toLocaleTimeString() },
    { id: 2, role: 'assistant', content: 'Ready. Upload .zip/.jar or paste a GitHub URL.', timestamp: new Date().toLocaleTimeString() }
  ]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  const addMessage = (role, content, type = 'text', extra = {}) => {
    setMessages(prev => [...prev, { id: Date.now(), role, content, type, timestamp: new Date().toLocaleTimeString([], { hour12: false }), ...extra }]);
  };

  const simulateProgress = () => {
    const steps = ["Parsing directory tree...", "Analyzing dependencies...", "AI selecting deploy strategy...", "Provisioning resources...", "Compiling assets...", "Finalizing..."];
    let i = 0;
    return setInterval(() => { if (i < steps.length) { addMessage('system', `>> ${steps[i]}`); i++; } }, 2500);
  };

  const handleFileSelection = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.name.endsWith('.jar')) { setPendingFile(file); setShowAwsModal(true); return; }
    performUpload(file);
  };

  const performUpload = async (file, awsCreds = null) => {
    setIsProcessing(true);
    addMessage('user', `Upload: ${file.name}`);
    const intervalId = simulateProgress();
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (awsCreds) { formData.append('aws_access_key_id', awsCreds.accessKey); formData.append('aws_secret_access_key', awsCreds.secretKey); }
      const headers = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${API_URL}/upload`, { method: 'POST', body: formData, headers });
      const data = await res.json();
      clearInterval(intervalId);
      if (res.ok) {
        const finalLink = data.endpoint || data.url || data.details?.url;
        addMessage('assistant', null, 'success', { endpoint: finalLink, deployment: data.deployment, warning: data.warning });
      } else { throw new Error(data.detail || "Upload failed"); }
    } catch (error) { clearInterval(intervalId); addMessage('system', `FAILURE: ${error.message}`, 'error'); }
    finally { setIsProcessing(false); setPendingFile(null); if (fileInputRef.current) fileInputRef.current.value = ""; }
  };

  const handleAwsSubmit = (creds) => { setShowAwsModal(false); if (pendingFile) performUpload(pendingFile, creds); };

  const performGithubDeploy = async (repoUrl, ghToken, awsCreds = null) => {
    setIsProcessing(true);
    addMessage('system', '>> GitHub clone initiated...');
    const intervalId = simulateProgress();
    try {
      const formData = new FormData();
      formData.append('repo_url', repoUrl);
      if (ghToken) formData.append('github_token', ghToken);
      if (awsCreds) { formData.append('aws_access_key_id', awsCreds.awsAccessKey); formData.append('aws_secret_access_key', awsCreds.awsSecretKey); }
      const headers = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${API_URL}/upload/github`, { method: 'POST', body: formData, headers });
      const data = await res.json();
      clearInterval(intervalId);
      if (res.ok) {
        const finalLink = data.endpoint || data.url || data.details?.url;
        addMessage('assistant', null, 'success', { endpoint: finalLink, deployment: data.deployment, warning: data.warning });
      } else { throw new Error(data.detail || "Deployment failed"); }
    } catch (error) { clearInterval(intervalId); addMessage('system', `ABORTED: ${error.message}`, 'error'); }
    finally { setIsProcessing(false); }
  };

  const handleGithubSubmit = ({ token: ghToken, awsAccessKey, awsSecretKey }) => {
    setShowGithubModal(false);
    if (pendingRepoUrl) { performGithubDeploy(pendingRepoUrl, ghToken, { awsAccessKey, awsSecretKey }); setPendingRepoUrl(''); }
  };

  const handleSend = () => {
    if (!input.trim()) return;
    const userInput = input.trim();
    addMessage('user', userInput);
    setInput('');
    if (userInput.includes('github.com')) { setPendingRepoUrl(userInput); setShowGithubModal(true); return; }
    setTimeout(() => addMessage('assistant', 'Upload a project file or paste a GitHub URL to deploy.'), 600);
  };

  return (
    <div className="flex-1 flex flex-col bg-black/40 relative overflow-hidden">
      <AwsAuthModal isOpen={showAwsModal} onSubmit={handleAwsSubmit} onCancel={() => setShowAwsModal(false)} />
      <GithubAuthModal isOpen={showGithubModal} onSubmit={handleGithubSubmit} onCancel={() => setShowGithubModal(false)} />

      {/* Terminal Header */}
      <div className="h-12 bg-zinc-950 border-b border-zinc-800/60 flex items-center justify-between px-5 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/70 cursor-pointer hover:bg-red-500 transition-colors" onClick={onClose} />
            <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
            <div className="w-3 h-3 rounded-full bg-green-500/70" />
          </div>
          <span className="text-zinc-400 text-xs font-mono ml-2">{username}@depro — deploy terminal</span>
        </div>
        <button onClick={onClose} className="text-zinc-600 hover:text-zinc-300 transition-colors"><X size={16} /></button>
      </div>

      {/* Terminal Body */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-4 font-mono text-sm scrollbar-hide">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-4 ${msg.role === 'user' ? 'opacity-90' : ''}`}>
            <div className="shrink-0 w-36 text-right select-none pt-0.5">
              {msg.role === 'user'
                ? <span className="text-cyan-500/80 font-bold text-xs">{username}@depro:$</span>
                : msg.role === 'system'
                ? <span className="text-yellow-600/70 font-bold text-xs">sys@log:!</span>
                : <span className="text-purple-400 font-bold text-xs">depro:~$</span>
              }
            </div>
            <div className="flex-1 max-w-3xl">
              {msg.type === 'success' ? <SuccessCard endpoint={msg.endpoint} deployment={msg.deployment} warning={msg.warning} />
              : msg.type === 'error' ? <div className="p-3 bg-red-950/30 border border-red-500/50 text-red-400 font-mono text-xs rounded-lg"><strong className="block mb-1 text-red-300">ERROR</strong>{msg.content}</div>
              : <p className={`leading-relaxed whitespace-pre-wrap ${msg.role === 'system' ? 'text-yellow-600/70 italic text-xs' : 'text-zinc-200'}`}>{msg.content}</p>}
            </div>
          </div>
        ))}
        {isProcessing && <div className="flex gap-4 animate-pulse"><div className="shrink-0 w-36 text-right text-purple-500/50 text-xs">sys@io:~$</div><div className="text-purple-400 flex items-center gap-2 text-xs"><Loader2 className="w-3.5 h-3.5 animate-spin" />DEPLOYING...</div></div>}
      </div>

      {/* Terminal Input */}
      <div className="p-4 bg-zinc-950 border-t border-zinc-800/60 shrink-0">
        <div className="flex items-end gap-3">
          <div className="relative group">
            <input ref={fileInputRef} type="file" className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-20" onChange={handleFileSelection} disabled={isProcessing} accept=".zip,.jar" />
            <button disabled={isProcessing} className="w-11 h-11 border border-zinc-700 bg-zinc-900/50 hover:border-purple-500/50 text-zinc-400 hover:text-purple-300 transition-all flex items-center justify-center rounded-lg disabled:opacity-30"><Paperclip size={16} /></button>
          </div>
          <div className="flex-1 relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-purple-500 font-mono text-lg">{'>'}</span>
            <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleSend(); } }} disabled={isProcessing}
              className="w-full pl-8 pr-4 py-2.5 bg-black border border-zinc-700 text-zinc-100 placeholder-zinc-700 font-mono text-sm rounded-lg focus:outline-none focus:border-purple-500/50 transition-all disabled:opacity-50"
              placeholder={isProcessing ? "Deploying..." : "Paste GitHub URL or upload archive..."} />
          </div>
          <TerminalButton onClick={handleSend} disabled={isProcessing} className="h-11 px-6 text-xs rounded-lg">DEPLOY</TerminalButton>
        </div>
      </div>
    </div>
  );
}


// =============================================
// MAIN APP SHELL
// =============================================
function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [activeView, setActiveView] = useState('dashboard'); // 'dashboard' | 'terminal'

  const username = user?.username || 'user';
  const displayName = user?.display_name || username;
  const avatarUrl = user?.avatar_url;

  const handleLogout = () => { logout(); navigate('/login'); };

  return (
    <div className="min-h-screen bg-black flex font-mono">
      <style>{customStyles}</style>

      {/* Sidebar */}
      <aside className="w-64 bg-zinc-950 border-r border-zinc-800/60 flex flex-col shrink-0">
        {/* Logo */}
        <div className="h-16 flex items-center gap-3 px-6 border-b border-zinc-800/60">
          <Monitor size={22} className="text-purple-500" />
          <span className="text-lg font-bold text-white tracking-[0.15em]">DEPRO</span>
          <span className="text-[9px] text-purple-400/60 bg-purple-500/10 px-1.5 py-0.5 rounded border border-purple-500/20 ml-auto">v3.0</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1">
          <button onClick={() => setActiveView('dashboard')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-semibold tracking-wide transition-all ${
              activeView === 'dashboard'
                ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900 border border-transparent'
            }`}>
            <LayoutDashboard size={18} /> Dashboard
          </button>
          <button onClick={() => setActiveView('terminal')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-semibold tracking-wide transition-all ${
              activeView === 'terminal'
                ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900 border border-transparent'
            }`}>
            <TerminalIcon size={18} /> Terminal
          </button>
          <button onClick={() => setActiveView('billing')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-semibold tracking-wide transition-all ${
              activeView === 'billing'
                ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900 border border-transparent'
            }`}>
            <Rocket size={18} /> Billing
          </button>
        </nav>

        {/* User Section */}
        <div className="p-4 border-t border-zinc-800/60">
          <div className="flex items-center gap-3 px-2">
            {avatarUrl ? (
              <img src={avatarUrl} alt="" className="w-8 h-8 rounded-full border border-zinc-700" />
            ) : (
              <div className="w-8 h-8 rounded-full border border-zinc-700 bg-purple-500/10 flex items-center justify-center">
                <UserIcon size={14} className="text-purple-400" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm text-zinc-200 font-semibold truncate">{displayName}</p>
              <p className="text-[10px] text-zinc-600 truncate">{user?.email}</p>
            </div>
            <button onClick={handleLogout} className="text-zinc-600 hover:text-red-400 transition-colors p-1" title="Logout">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden bg-[radial-gradient(ellipse_at_top,rgba(168,85,247,0.03),transparent_60%)]">
        {activeView === 'dashboard' ? (
          <DashboardPage onOpenTerminal={() => setActiveView('terminal')} />
        ) : activeView === 'terminal' ? (
          <TerminalPanel onClose={() => setActiveView('dashboard')} />
        ) : activeView === 'billing' ? (
          <BillingDashboard />
        ) : null}
      </main>
    </div>
  );
}


// =============================================
// ROUTE GUARDS
// =============================================
function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <div className="min-h-screen bg-black flex items-center justify-center"><Loader2 size={32} className="text-purple-500 animate-spin" /></div>;
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

// =============================================
// APP ROUTER
// =============================================
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/" element={<ProtectedRoute><AppShell /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}