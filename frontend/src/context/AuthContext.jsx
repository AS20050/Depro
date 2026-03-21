import React, { createContext, useState, useContext, useEffect } from 'react';

const API_URL = "http://localhost:8000";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('depro_token'));
  const [loading, setLoading] = useState(true);

  // On mount / token change, fetch user profile
  useEffect(() => {
    if (token) {
      fetchProfile(token);
    } else {
      setLoading(false);
    }
  }, []);

  const fetchProfile = async (jwt) => {
    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${jwt}` }
      });
      if (res.ok) {
        const userData = await res.json();
        setUser(userData);
        setToken(jwt);
      } else {
        // Token expired or invalid
        logout();
      }
    } catch {
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    const res = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Login failed');

    localStorage.setItem('depro_token', data.access_token);
    setToken(data.access_token);
    setUser(data.user);
    return data;
  };

  const register = async (email, password, username, display_name) => {
    const res = await fetch(`${API_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, username, display_name })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Registration failed');

    localStorage.setItem('depro_token', data.access_token);
    setToken(data.access_token);
    setUser(data.user);
    return data;
  };

  const loginWithGithub = () => {
    window.location.href = `${API_URL}/auth/github`;
  };

  const handleOAuthCallback = async (jwt) => {
    localStorage.setItem('depro_token', jwt);
    setToken(jwt);
    await fetchProfile(jwt);
  };

  const logout = () => {
    localStorage.removeItem('depro_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{
      user, token, loading,
      login, register, logout,
      loginWithGithub, handleOAuthCallback,
      isAuthenticated: !!user
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};
