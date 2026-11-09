import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  fetchMeApi,
  loginApi,
  registerApi,
  verifyApi,
  logoutApi,
  updateProfileApi,
  getAuthToken,
} from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState('login'); // 'login' | 'register' | 'verify' | 'forgot'
  const [pendingIdentifier, setPendingIdentifier] = useState('');

  const refreshUser = useCallback(async () => {
    try {
      const token = getAuthToken();
      if (!token) {
        setUser(null);
        return null;
      }
      const userData = await fetchMeApi();
      setUser(userData);
      return userData;
    } catch {
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async (identifier, password) => {
    const data = await loginApi(identifier, password);
    setUser(data.user);
    setAuthModalOpen(false);
    return data;
  };

  const register = async (identifier, password, fullName = '') => {
    const data = await registerApi(identifier, password, fullName);
    setPendingIdentifier(identifier);
    setAuthModalMode('verify');
    return data;
  };

  const verify = async (identifier, code) => {
    const data = await verifyApi(identifier, code);
    setUser(data.user);
    setAuthModalOpen(false);
    return data;
  };

  const logout = async () => {
    await logoutApi();
    setUser(null);
  };

  const updateProfile = async (fullName, termPreference) => {
    const updated = await updateProfileApi(fullName, termPreference);
    setUser(updated);
    return updated;
  };

  const openAuth = (mode = 'login', initialId = '') => {
    setAuthModalMode(mode);
    if (initialId) setPendingIdentifier(initialId);
    setAuthModalOpen(true);
  };

  const closeAuth = () => {
    setAuthModalOpen(false);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: !!user,
        authModalOpen,
        authModalMode,
        pendingIdentifier,
        setAuthModalMode,
        setPendingIdentifier,
        login,
        register,
        verify,
        logout,
        updateProfile,
        refreshUser,
        openAuth,
        closeAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}

