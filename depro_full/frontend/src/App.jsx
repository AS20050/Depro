import React, { useState, useEffect, useRef } from 'react';
import { 
  Terminal, 
  Upload, 
  Monitor, 
  Paperclip,
  CheckCircle,
  AlertCircle,
  Globe,
  Loader2,
  Server,
  Github,
  Lock,
  Key,
  ShieldCheck,
  GitBranch
} from 'lucide-react';

// --- CONFIG ---
// const API_URL = "http://52.66.116.188:8080";
const API_URL = "http://localhost:8000";

// --- STYLES ---
const customStyles = `
  .retro-glow { text-shadow: 0 0 10px currentColor; }
  .retro-text-base { text-shadow: 0 0 2px rgba(255, 255, 255, 0.5); }
  .crt-scanline {
    background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,0,0,0.2) 50%, rgba(0,0,0,0.2));
    background-size: 100% 4px;
    animation: scanline 10s linear infinite;
    pointer-events: none;
  }
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
      <div className="absolute top-0 left-0 w-1 h-1 border-t border-l border-current opacity-70" />
      <div className="absolute bottom-0 right-0 w-1 h-1 border-b border-r border-current opacity-70" />
    </button>
  );
};

// --- AWS MODAL (For JARs) ---
const AwsAuthModal = ({ isOpen, onSubmit, onCancel }) => {
  const [accessKey, setAccessKey] = useState('');
  const [secretKey, setSecretKey] = useState('');
  const [vaultStatus, setVaultStatus] = useState(null); // null | 'checking' | 'found' | 'not_found'

  const checkVault = async (akid) => {
    if (!akid || akid.length < 16) return;
    setVaultStatus('checking');
    try {
      const res = await fetch(`${API_URL}/vault/check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_key_id: akid }),
      });
      const data = await res.json();
      setVaultStatus(data.exists ? 'found' : 'not_found');
    } catch {
      setVaultStatus('not_found');
    }
  };

  useEffect(() => {
    if (!isOpen) {
      setAccessKey('');
      setSecretKey('');
      setVaultStatus(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const canSubmit = accessKey && (vaultStatus === 'found' || secretKey);

  return (
    <div className="absolute inset-0 z-[100] bg-black/90 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-lg bg-zinc-950 border border-yellow-500/50 shadow-[0_0_50px_rgba(234,179,8,0.15)] p-8 relative overflow-hidden">
        <div className="flex items-center gap-3 mb-6 border-b border-zinc-800 pb-4">
          <ShieldCheck className="text-yellow-500 animate-pulse" size={24} />
          <h2 className="text-yellow-500 font-mono text-xl tracking-widest font-bold retro-glow">SECURITY CLEARANCE</h2>
        </div>
        <p className="text-zinc-400 font-mono text-sm mb-6 leading-relaxed">
          Target artifact <span className="text-white bg-zinc-800 px-1">.JAR</span> requires direct EC2 provisioning.
          Provide your AWS Access Key ID. If a vault entry exists, the secret is retrieved automatically.
        </p>

        {vaultStatus === 'found' && (
          <div className="mb-4 p-3 bg-green-900/20 border border-green-500/40 flex items-start gap-2">
            <CheckCircle size={14} className="text-green-400 shrink-0 mt-0.5" />
            <p className="text-green-400 font-mono text-xs leading-relaxed">
              Credentials found in Algorand Vault. Secret key not required.
            </p>
          </div>
        )}
        {vaultStatus === 'not_found' && (
          <div className="mb-4 p-3 bg-zinc-800/50 border border-zinc-700/40 flex items-start gap-2">
            <AlertCircle size={14} className="text-zinc-300 shrink-0 mt-0.5" />
            <p className="text-zinc-300 font-mono text-xs leading-relaxed">
              No vault entry found. Enter your secret key; it will be encrypted and stored on Algorand.
            </p>
          </div>
        )}

        <div className="space-y-4 mb-8">
          <div className="group">
            <label className="text-[10px] text-zinc-500 font-mono uppercase tracking-widest mb-1 block">Access Key ID</label>
            <div className="relative">
              <Key className="absolute left-3 top-3 text-zinc-600" size={16} />
              <input
                type="text"
                value={accessKey}
                onChange={(e) => setAccessKey(e.target.value)}
                onBlur={(e) => checkVault(e.target.value.trim())}
                className="w-full bg-zinc-900 border border-zinc-700 text-yellow-100 font-mono p-2.5 pl-10 focus:border-yellow-500 focus:outline-none transition-all"
                placeholder="AKIA..."
              />
              {vaultStatus === 'checking' && (
                <div className="absolute right-3 top-3 text-zinc-500 text-[10px] font-mono tracking-widest">
                  CHECKING...
                </div>
              )}
            </div>
          </div>

          {vaultStatus !== 'found' && (
            <div className="group">
              <label className="text-[10px] text-zinc-500 font-mono uppercase tracking-widest mb-1 block">Secret Access Key</label>
              <div className="relative">
                <Lock className="absolute left-3 top-3 text-zinc-600" size={16} />
                <input
                  type="password"
                  value={secretKey}
                  onChange={(e) => setSecretKey(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-700 text-yellow-100 font-mono p-2.5 pl-10 focus:border-yellow-500 focus:outline-none transition-all"
                  placeholder="••••••••••••••••••••"
                />
              </div>
              <p className="text-[10px] text-zinc-600 mt-2">
                * Will be AES-256-GCM encrypted and stored on Algorand. Never written to disk.
              </p>
            </div>
          )}
        </div>

        <div className="flex gap-4">
          <TerminalButton onClick={onCancel} variant="ghost" className="flex-1">CANCEL</TerminalButton>
          <button
            onClick={() => onSubmit({ accessKey, secretKey: vaultStatus === 'found' ? '' : secretKey })}
            disabled={!canSubmit || vaultStatus === 'checking'}
            className="flex-1 bg-yellow-500/20 border border-yellow-500 text-yellow-500 hover:bg-yellow-500 hover:text-black py-2 font-mono text-sm tracking-widest transition-all shadow-[0_0_15px_rgba(234,179,8,0.3)] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {vaultStatus === 'found' ? 'RETRIEVE & DEPLOY' : 'ENCRYPT & DEPLOY'}
          </button>
        </div>
      </div>
    </div>
  );
}

// --- GITHUB TOKEN MODAL (For CI/CD) ---
const GithubAuthModal = ({ isOpen, onSubmit, onCancel }) => {
  const [token, setToken] = useState('');

  if (!isOpen) return null;

  return (
    <div className="absolute inset-0 z-[100] bg-black/90 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-lg bg-zinc-950 border border-purple-500/50 shadow-[0_0_50px_rgba(168,85,247,0.15)] p-8 relative overflow-hidden">
        <div className="flex items-center gap-3 mb-6 border-b border-zinc-800 pb-4">
          <GitBranch className="text-purple-500 animate-pulse" size={24} />
          <h2 className="text-purple-500 font-mono text-xl tracking-widest font-bold retro-glow">CI/CD PIPELINE CONFIG</h2>
        </div>
        <p className="text-zinc-400 font-mono text-sm mb-6 leading-relaxed">
          To enable <span className="text-white bg-zinc-800 px-1">AUTO-DEPLOYMENT</span>, AWS requires a GitHub Personal Access Token (Classic) with <code>repo</code> and <code>admin:repo_hook</code> scopes.
        </p>
        <div className="space-y-4 mb-8">
          <div className="group">
            <label className="text-[10px] text-zinc-500 font-mono uppercase tracking-widest mb-1 block">GitHub Personal Access Token</label>
            <div className="relative">
              <Github className="absolute left-3 top-3 text-zinc-600" size={16} />
              <input type="password" value={token} onChange={(e) => setToken(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700 text-purple-100 font-mono p-2.5 pl-10 focus:border-purple-500 focus:outline-none transition-all"
                placeholder="ghp_xxxxxxxxxxxx"
              />
            </div>
            <p className="text-[10px] text-zinc-600 mt-2">
              * Leave empty to perform a one-time Snapshot deployment (No Auto-Updates).
            </p>
          </div>
        </div>
        <div className="flex gap-4">
          <TerminalButton onClick={onCancel} variant="ghost" className="flex-1">CANCEL</TerminalButton>
          <button onClick={() => onSubmit(token)}
            className="flex-1 bg-purple-500/20 border border-purple-500 text-purple-500 hover:bg-purple-500 hover:text-black py-2 font-mono text-sm tracking-widest transition-all shadow-[0_0_15px_rgba(168,85,247,0.3)]">
            {token ? "ENABLE CI/CD" : "DEPLOY SNAPSHOT"}
          </button>
        </div>
      </div>
    </div>
  );
}

const SuccessCard = ({ endpoint, deployment, warning }) => (
  <div className="mt-4 p-4 bg-zinc-900/90 border border-green-500/50 rounded-none shadow-[0_0_20px_rgba(34,197,94,0.2)] animate-in fade-in slide-in-from-bottom-2 relative overflow-hidden group">
    <div className="absolute top-0 left-0 w-full h-[2px] bg-green-500/50 animate-pulse" />
    <div className="flex items-start gap-4 relative z-10">
      <div className="p-3 bg-green-500/10 border border-green-500/30">
        <Globe className="w-6 h-6 text-green-400 retro-glow" />
      </div>
      <div className="flex-1 space-y-3">
        <div className="flex items-center justify-between border-b border-green-500/20 pb-2">
          <h3 className="text-green-400 font-bold font-mono text-sm tracking-widest retro-glow">MISSION ACCOMPLISHED</h3>
          <span className="text-[10px] bg-green-900/40 text-green-300 px-2 py-0.5 border border-green-500/40 uppercase font-mono">STRATEGY: {deployment || "UNKNOWN"}</span>
        </div>
        {warning && (
           <div className="flex items-start gap-2 text-yellow-400 text-xs bg-yellow-900/20 p-2 border border-yellow-500/30 font-mono">
             <AlertCircle size={14} className="shrink-0 mt-0.5 retro-glow" />
             <p className="retro-text-base">{warning}</p>
           </div>
        )}
        <div className="bg-black/80 p-3 border border-zinc-700/50 flex flex-col gap-1 group-hover:border-green-500/50 transition-colors">
          <span className="text-zinc-500 text-[10px] uppercase tracking-widest font-mono">Secure Uplink Established</span>
          <a href={endpoint} target="_blank" rel="noreferrer" className="text-cyan-400 hover:text-cyan-300 font-mono text-lg break-all hover:underline flex items-center gap-2 retro-glow transition-all">
            {endpoint} <Server size={14} />
          </a>
        </div>
      </div>
    </div>
  </div>
);

export default function App() {
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  
  // Modals State
  const [showAwsModal, setShowAwsModal] = useState(false);
  const [showGithubModal, setShowGithubModal] = useState(false);
  
  const [pendingFile, setPendingFile] = useState(null);
  const [pendingRepoUrl, setPendingRepoUrl] = useState('');
  const [pendingGithubToken, setPendingGithubToken] = useState('');
  
  const scrollRef = useRef(null);
  const fileInputRef = useRef(null);
  
  const [messages, setMessages] = useState([
    { id: 1, role: 'system', content: 'OPSonic Kernel v2.4 initialized. Uplink established to ap-south-1.', timestamp: new Date().toLocaleTimeString() },
    { id: 2, role: 'assistant', content: 'System Ready. Upload project source (.zip, .jar) or authorize GitHub repository.', timestamp: new Date().toLocaleTimeString() }
  ]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  const addMessage = (role, content, type = 'text', extra = {}) => {
    setMessages(prev => [...prev, { id: Date.now(), role, content, type, timestamp: new Date().toLocaleTimeString([], { hour12: false }), ...extra }]);
  };

  const simulateProgress = () => {
    const steps = ["Parsing directory tree structure...", "Analyzing dependency graph...", "AI Decision Engine: Optimizing deployment matrix...", "Provisioning isolated container resources...", "Configuring firewall rules...", "Compiling assets...", "Finalizing secure handshake..."];
    let i = 0;
    return setInterval(() => { if (i < steps.length) { addMessage('system', `>> ${steps[i]}`); i++; } }, 2500);
  };

  // --- JAR FILE HANDLING ---
  const handleFileSelection = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.name.endsWith('.jar') || file.name.endsWith('.zip')) {
      setPendingFile(file);
      setShowAwsModal(true);
      return;
    }
    performUpload(file);
  };

  const performUpload = async (file, awsCreds = null) => {
    setIsProcessing(true);
    addMessage('user', `Initializing upload: ${file.name}`);
    addMessage('system', `[IO] Transferring bitstream (${(file.size/1024).toFixed(1)} KB)...`);
    if (awsCreds) addMessage('system', '>> Authenticating with AWS IAM...');

    const intervalId = simulateProgress();

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (awsCreds) {
          formData.append('aws_access_key_id', awsCreds.accessKey);
          if (awsCreds.secretKey) {
            formData.append('aws_secret_access_key', awsCreds.secretKey);
          }
      }

      const res = await fetch(`${API_URL}/upload`, { method: 'POST', body: formData });
      const data = await res.json();
      clearInterval(intervalId);

      if (!res.ok) {
        throw new Error(data.detail || data.message || "Upload failed");
      }

      if (data.status && data.status !== 'success') {
        throw new Error(data.message || `Deployment did not succeed (status: ${data.status})`);
      }

      const finalLink = data.endpoint || data.url || data.details?.url;
      if (!finalLink) {
        throw new Error(data.message || "Deployment did not return a URL/endpoint.");
      }

      if (data.vault_stored) {
        addMessage('system', '>> AWS credentials encrypted and stored on Algorand vault.');
      }
      addMessage('assistant', null, 'success', { endpoint: finalLink, deployment: data.deployment, warning: data.warning });
    } catch (error) {
      clearInterval(intervalId);
      addMessage('system', `CRITICAL FAILURE: ${error.message}`, 'error');
    } finally {
      setIsProcessing(false);
      setPendingFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleAwsSubmit = (creds) => {
    setShowAwsModal(false);
    if (pendingFile) {
      performUpload(pendingFile, creds);
      return;
    }
    if (pendingRepoUrl) {
      performGithubDeploy(pendingRepoUrl, pendingGithubToken, creds);
      setPendingRepoUrl('');
      setPendingGithubToken('');
    }
  };

  // --- GITHUB HANDLING ---
  const performGithubDeploy = async (repoUrl, token, awsCreds = null) => {
    setIsProcessing(true);
    addMessage('system', '>> GitHub Remote Detected. Initiating Clone Sequence...');
    
    if (token) {
        addMessage('system', '>> Token detected. Attempting to establish CI/CD Pipeline...');
    } else {
        addMessage('system', '>> No Token provided. Fallback to Snapshot Mode.');
    }

    const intervalId = simulateProgress();

    try {
      const formData = new FormData();
      formData.append('repo_url', repoUrl);
      if (token) {
          formData.append('github_token', token);
      }
      if (awsCreds) {
        formData.append('aws_access_key_id', awsCreds.accessKey);
        if (awsCreds.secretKey) {
          formData.append('aws_secret_access_key', awsCreds.secretKey);
        }
      }
       
      const res = await fetch(`${API_URL}/upload/github`, { method: 'POST', body: formData });
      const data = await res.json();
      clearInterval(intervalId);

      if (!res.ok) {
        throw new Error(data.detail || data.message || "GitHub deployment failed");
      }

      if (data.status && data.status !== 'success') {
        throw new Error(data.message || `Deployment did not succeed (status: ${data.status})`);
      }

      const finalLink = data.endpoint || data.url || data.details?.url;
      if (!finalLink) {
        throw new Error(data.message || "Deployment did not return a URL/endpoint.");
      }

      if (data.vault_stored) {
        addMessage('system', '>> AWS credentials encrypted and stored on Algorand vault.');
      }

      addMessage('assistant', null, 'success', { endpoint: finalLink, deployment: data.deployment, warning: data.warning });
    } catch (error) {
      clearInterval(intervalId);
      addMessage('system', `DEPLOYMENT ABORTED: ${error.message}`, 'error');
    } finally { setIsProcessing(false); }
  };

  const handleGithubSubmit = (token) => {
      setShowGithubModal(false);
      if (pendingRepoUrl) {
          setPendingGithubToken(token || '');
          setShowAwsModal(true);
      }
  };

  // --- CHAT INPUT HANDLING ---
  const handleSend = async () => {
    if (!input.trim()) return;
    const userInput = input.trim();
    addMessage('user', userInput);
    setInput('');

    if (userInput.includes('github.com')) {
      setPendingRepoUrl(userInput);
      setShowGithubModal(true); // Trigger GitHub Modal
      return;
    }
    setTimeout(() => { addMessage('assistant', 'Syntax Error. Please upload a project file or provide a valid GitHub repository URL.'); }, 600);
  };

  return (
    <div className="min-h-screen bg-black flex items-center justify-center p-4 md:p-8 font-sans selection:bg-purple-500 selection:text-white overflow-hidden relative">
      <style>{customStyles}</style>
      
      {/* Modals */}
      <AwsAuthModal
        isOpen={showAwsModal}
        onSubmit={handleAwsSubmit}
        onCancel={() => {
          setShowAwsModal(false);
          setPendingFile(null);
          setPendingRepoUrl('');
          setPendingGithubToken('');
        }}
      />
      <GithubAuthModal isOpen={showGithubModal} onSubmit={handleGithubSubmit} onCancel={() => setShowGithubModal(false)} />

      <div className={`w-full max-w-[1600px] aspect-video bg-zinc-950 relative flex flex-col border-[3px] border-zinc-800 rounded-lg shadow-[0_0_80px_rgba(0,0,0,0.8)] overflow-hidden transition-all duration-500 ${showAwsModal || showGithubModal ? 'blur-sm scale-[0.98] grayscale' : ''}`}>
        <div className="absolute inset-0 z-50 pointer-events-none crt-scanline opacity-10" />
        <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_center,rgba(168,85,247,0.03),transparent_70%)]" />
        <header className="h-14 bg-black/80 border-b border-zinc-800 flex items-center justify-between px-8 z-40 shrink-0 backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <Monitor size={20} className="text-purple-500 animate-pulse retro-glow" />
              <span className="font-mono text-lg font-bold tracking-[0.2em] text-zinc-100 retro-text-base">OPSONIC</span>
            </div>
            <span className="px-3 py-1 bg-purple-900/20 text-purple-300 text-[10px] font-mono border border-purple-500/30 rounded tracking-widest">v2.0.4-LTS</span>
          </div>
          <div className="flex items-center gap-8 text-[11px] font-mono text-zinc-500 uppercase tracking-widest">
             <span className="flex items-center gap-2">
               <span className={`w-2 h-2 rounded-full ${isProcessing ? 'bg-yellow-400 retro-glow animate-bounce' : 'bg-green-500 retro-glow'}`}></span>
               SYS_STATUS: {isProcessing ? 'COMPUTING' : 'ONLINE'}
             </span>
             <span>REGION: AP-SOUTH-1</span>
          </div>
        </header>
        <main className="flex-1 overflow-hidden relative flex flex-col w-full bg-black/40">
          <div className="absolute inset-0 pointer-events-none opacity-[0.04]" style={{ backgroundImage: `linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)`, backgroundSize: '40px 40px' }}></div>
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-8 space-y-6 font-mono text-base relative z-30 scrollbar-hide">
            <div className="w-full flex justify-center mb-12 opacity-80 select-none pointer-events-none">
              <pre className="text-purple-500/80 font-black text-[10px] sm:text-xs md:text-sm leading-none tracking-tighter retro-glow">
{`   ___  ____  ____   ___  _   _ ___ ____ 
  / _ \\|  _ \\/ ___| / _ \\| \\ | |_ _/ ___|
 | | | | |_) \\___ \\| | | |  \\| || | |    
 | |_| |  __/ ___) | |_| | |\\  || | |___ 
  \\___/|_|   |____/ \\___/|_| \\_|___\\____|`}
              </pre>
            </div>
            <div className="text-zinc-600 text-xs mb-8 border-b border-dashed border-zinc-800 pb-2 flex justify-between tracking-widest">
              <span>SESSION: 0x8F21-ALPHA</span>
              <span>PROTOCOL: SECURE_SHELL_V2</span>
            </div>
            {messages.map((msg) => (
              <div key={msg.id} className={`group flex gap-6 ${msg.role === 'user' ? 'opacity-90' : 'opacity-100'}`}>
                <div className="shrink-0 w-40 text-right select-none pt-1">
                  {msg.role === 'user' ? (<span className="text-zinc-500 font-bold tracking-tight">OPSonic@user:$</span>) : msg.role === 'system' ? (<span className="text-yellow-600/80 font-bold tracking-tight">sys_kernel@log:!</span>) : (<span className="text-purple-400 font-bold tracking-tight retro-glow">root@opsonic:~$</span>)}
                </div>
                <div className="flex-1 max-w-4xl">
                  {msg.type === 'success' ? (<SuccessCard endpoint={msg.endpoint} deployment={msg.deployment} warning={msg.warning} />) : msg.type === 'error' ? (
                      <div className="p-4 bg-red-950/30 border border-red-500/50 text-red-400 font-mono text-sm shadow-[0_0_15px_rgba(239,68,68,0.2)]"><strong className="block mb-1 text-red-300">!!! SYSTEM FAILURE !!!</strong>{msg.content}</div>
                  ) : (<p className={`leading-relaxed whitespace-pre-wrap ${msg.role === 'system' ? 'text-yellow-600/80 italic text-xs' : 'text-zinc-200 retro-text-base'}`}>{msg.content}</p>)}
                  <span className="text-[9px] text-zinc-700 block mt-2 font-mono tracking-widest opacity-0 group-hover:opacity-100 transition-opacity">TIMESTAMP: {msg.timestamp}</span>
                </div>
              </div>
            ))}
            {isProcessing && (<div className="flex gap-6 animate-pulse mt-4"><div className="shrink-0 w-40 text-right text-purple-500/50">sys_io@net:~$</div><div className="text-purple-400 flex items-center gap-3 font-mono tracking-widest text-sm"><Loader2 className="w-4 h-4 animate-spin" />EXECUTING_DEPLOYMENT_MATRIX...</div></div>)}
          </div>
          <div className="p-6 bg-black border-t-2 border-zinc-800 relative z-40">
            <div className="flex items-end gap-4 max-w-6xl mx-auto">
              <div className="relative group">
                <input ref={fileInputRef} type="file" className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-20 disabled:cursor-not-allowed" onChange={handleFileSelection} disabled={isProcessing} accept=".zip,.jar" />
                <button disabled={isProcessing} className="w-14 h-14 border border-zinc-600 bg-zinc-900/50 hover:bg-purple-900/20 hover:border-purple-500 text-zinc-400 hover:text-purple-300 transition-all flex items-center justify-center disabled:opacity-30 disabled:hover:border-zinc-600"><Paperclip size={20} /></button>
                <div className="absolute bottom-full left-0 mb-3 hidden group-hover:block whitespace-nowrap bg-zinc-900 border border-zinc-700 text-zinc-300 text-[10px] px-3 py-1 tracking-widest shadow-xl">UPLOAD SOURCE</div>
              </div>
              <div className="flex-1 relative group">
                 <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none"><span className={`text-purple-500 font-mono text-xl ${isProcessing ? '' : 'animate-pulse retro-glow'}`}>{'>'}</span></div>
                 <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if(e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }}} disabled={isProcessing} className="block w-full pl-10 pr-12 py-4 bg-zinc-950 border border-zinc-700 text-zinc-100 placeholder-zinc-700 font-mono text-base focus:outline-none focus:border-purple-500 focus:shadow-[0_0_20px_rgba(168,85,247,0.2)] transition-all resize-none h-14 min-h-14 max-h-40 disabled:opacity-50 disabled:cursor-wait retro-text-base" placeholder={isProcessing ? "SYSTEM BUSY..." : "Paste GitHub Repository URL or Upload Archive..."} />
              </div>
              <TerminalButton onClick={handleSend} disabled={isProcessing} variant="primary" className="h-14 px-8 font-bold text-base tracking-widest">EXECUTE</TerminalButton>
            </div>
            <div className="mt-3 text-center text-[10px] text-zinc-600 font-mono uppercase tracking-[0.2em]">SECURE CONNECTION • 256-BIT ENCRYPTION • OPSONIC PROTOCOL</div>
          </div>
        </main>
      </div>
    </div>
  );
}
