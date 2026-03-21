import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import {
  Monitor, Mail, Lock, User, ArrowRight, Loader2, Eye, EyeOff
} from 'lucide-react';

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isRegister) {
        await register(email, password, username, displayName || username);
      } else {
        await login(email, password);
      }
      navigate('/');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-black flex items-center justify-center p-4 relative overflow-hidden font-mono">
      {/* Background effects */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(168,85,247,0.08),transparent_60%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,rgba(59,130,246,0.05),transparent_60%)]" />
      <div className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)`,
          backgroundSize: '60px 60px'
        }}
      />

      {/* Floating particles */}
      <div className="absolute top-1/4 left-1/4 w-1 h-1 bg-purple-500/30 rounded-full animate-pulse" />
      <div className="absolute top-3/4 right-1/3 w-1.5 h-1.5 bg-blue-500/20 rounded-full animate-pulse" style={{ animationDelay: '1s' }} />
      <div className="absolute top-1/2 right-1/4 w-1 h-1 bg-cyan-500/20 rounded-full animate-pulse" style={{ animationDelay: '2s' }} />

      <div className="w-full max-w-md relative z-10">
        {/* Logo & Title */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 border border-purple-500/30 bg-purple-500/5 rounded-2xl mb-6 shadow-[0_0_40px_rgba(168,85,247,0.15)]">
            <Monitor size={28} className="text-purple-400" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-[0.15em] mb-2"
            style={{ textShadow: '0 0 20px rgba(168,85,247,0.3)' }}>
            DEPRO
          </h1>
          <p className="text-zinc-500 text-sm tracking-widest uppercase">
            Deployment Control System
          </p>
        </div>

        {/* Card */}
        <div className="bg-zinc-950/80 border border-zinc-800/80 rounded-xl p-8 backdrop-blur-xl shadow-[0_0_60px_rgba(0,0,0,0.5)]">
          {/* Tab Switcher */}
          <div className="flex mb-8 border border-zinc-800 rounded-lg p-1 bg-black/50">
            <button
              onClick={() => { setIsRegister(false); setError(''); }}
              className={`flex-1 py-2.5 text-xs font-bold tracking-widest rounded-md transition-all duration-300 ${
                !isRegister
                  ? 'bg-purple-500/15 text-purple-400 border border-purple-500/30 shadow-[0_0_15px_rgba(168,85,247,0.15)]'
                  : 'text-zinc-500 hover:text-zinc-300 border border-transparent'
              }`}
            >
              SIGN IN
            </button>
            <button
              onClick={() => { setIsRegister(true); setError(''); }}
              className={`flex-1 py-2.5 text-xs font-bold tracking-widest rounded-md transition-all duration-300 ${
                isRegister
                  ? 'bg-purple-500/15 text-purple-400 border border-purple-500/30 shadow-[0_0_15px_rgba(168,85,247,0.15)]'
                  : 'text-zinc-500 hover:text-zinc-300 border border-transparent'
              }`}
            >
              REGISTER
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {isRegister && (
              <>
                <div>
                  <label className="text-[10px] text-zinc-500 uppercase tracking-widest mb-1.5 block font-semibold">Username</label>
                  <div className="relative">
                    <User className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600" size={15} />
                    <input
                      type="text" value={username} onChange={(e) => setUsername(e.target.value)}
                      required minLength={3}
                      className="w-full bg-black/60 border border-zinc-800 text-zinc-100 rounded-lg py-3 pl-11 pr-4 text-sm focus:outline-none focus:border-purple-500/50 focus:shadow-[0_0_15px_rgba(168,85,247,0.1)] transition-all placeholder-zinc-700"
                      placeholder="devops_ninja"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-[10px] text-zinc-500 uppercase tracking-widest mb-1.5 block font-semibold">Display Name</label>
                  <div className="relative">
                    <User className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600" size={15} />
                    <input
                      type="text" value={displayName} onChange={(e) => setDisplayName(e.target.value)}
                      className="w-full bg-black/60 border border-zinc-800 text-zinc-100 rounded-lg py-3 pl-11 pr-4 text-sm focus:outline-none focus:border-purple-500/50 focus:shadow-[0_0_15px_rgba(168,85,247,0.1)] transition-all placeholder-zinc-700"
                      placeholder="Optional"
                    />
                  </div>
                </div>
              </>
            )}

            <div>
              <label className="text-[10px] text-zinc-500 uppercase tracking-widest mb-1.5 block font-semibold">Email</label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600" size={15} />
                <input
                  type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full bg-black/60 border border-zinc-800 text-zinc-100 rounded-lg py-3 pl-11 pr-4 text-sm focus:outline-none focus:border-purple-500/50 focus:shadow-[0_0_15px_rgba(168,85,247,0.1)] transition-all placeholder-zinc-700"
                  placeholder="you@example.com"
                />
              </div>
            </div>

            <div>
              <label className="text-[10px] text-zinc-500 uppercase tracking-widest mb-1.5 block font-semibold">Password</label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600" size={15} />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password} onChange={(e) => setPassword(e.target.value)}
                  required minLength={6}
                  className="w-full bg-black/60 border border-zinc-800 text-zinc-100 rounded-lg py-3 pl-11 pr-11 text-sm focus:outline-none focus:border-purple-500/50 focus:shadow-[0_0_15px_rgba(168,85,247,0.1)] transition-all placeholder-zinc-700"
                  placeholder="••••••••"
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-zinc-600 hover:text-zinc-400 transition-colors">
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg p-3 font-mono">
                ⚠ {error}
              </div>
            )}

            <button
              type="submit" disabled={loading}
              className="w-full py-3.5 mt-2 bg-purple-500/15 border border-purple-500/40 text-purple-400 rounded-lg text-sm font-bold tracking-widest hover:bg-purple-500/25 hover:border-purple-500/60 hover:shadow-[0_0_25px_rgba(168,85,247,0.2)] transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <>
                  {isRegister ? 'CREATE ACCOUNT' : 'SIGN IN'}
                  <ArrowRight size={14} />
                </>
              )}
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-[10px] text-zinc-700 mt-6 tracking-[0.15em] uppercase">
          Secure Connection • 256-Bit Encryption
        </p>
      </div>
    </div>
  );
}
