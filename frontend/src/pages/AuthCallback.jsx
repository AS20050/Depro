import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Loader2 } from 'lucide-react';

/**
 * This page handles the OAuth callback redirect from the backend.
 * URL: /auth/callback?token=xxx
 */
export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const { handleOAuthCallback } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const token = searchParams.get('token');
    if (token) {
      handleOAuthCallback(token).then(() => {
        navigate('/', { replace: true });
      });
    } else {
      navigate('/login', { replace: true });
    }
  }, []);

  return (
    <div className="min-h-screen bg-black flex items-center justify-center font-mono">
      <div className="text-center">
        <Loader2 size={32} className="text-purple-500 animate-spin mx-auto mb-4" />
        <p className="text-zinc-400 text-sm tracking-widest uppercase">
          Authenticating...
        </p>
      </div>
    </div>
  );
}
