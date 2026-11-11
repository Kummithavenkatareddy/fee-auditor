import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { forgotPasswordApi, resetPasswordApi } from '../services/api';

export default function LoginScreen({ onLoginSuccess }) {
  const { login, register, verify } = useAuth();
  const [mode, setMode] = useState('login'); // 'login' | 'register' | 'verify' | 'forgot'
  const [identifier, setIdentifier] = useState('auditor@university.edu');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [loading, setLoading] = useState(false);
  const [devOtpHint, setDevOtpHint] = useState(null);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(identifier, password);
      if (onLoginSuccess) onLoginSuccess();
    } catch (err) {
      if (err.message && err.message.toLowerCase().includes('not verified')) {
        setMode('verify');
        setError('Account is not verified. Please enter your 6-digit OTP.');
      } else {
        setError(err.message || 'Authentication failed. Please verify credentials.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await register(identifier, password, fullName);
      if (res?.dev_verification_code) {
        setDevOtpHint(res.dev_verification_code);
        setOtpCode(res.dev_verification_code);
      }
      setSuccessMsg('Account registered. Please enter the 6-digit OTP to verify.');
      setMode('verify');
    } catch (err) {
      setError(err.message || 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await verify(identifier, otpCode);
      if (onLoginSuccess) onLoginSuccess();
    } catch (err) {
      setError(err.message || 'Verification failed. Please check the code.');
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await forgotPasswordApi(identifier);
      if (res?.dev_reset_code) {
        setDevOtpHint(res.dev_reset_code);
        setOtpCode(res.dev_reset_code);
      }
      setSuccessMsg('Reset code sent. Please enter the code and your new password.');
      setMode('reset_pwd');
    } catch (err) {
      setError(err.message || 'Failed to request password reset.');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await resetPasswordApi(identifier, otpCode, newPassword);
      setSuccessMsg('Password updated successfully. Please log in.');
      setMode('login');
      setPassword('');
    } catch (err) {
      setError(err.message || 'Password reset failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col justify-center items-center px-4 py-12 relative overflow-hidden select-none">
      {/* Background Institutional Watermark Pattern */}
      <div className="absolute inset-0 opacity-5 pointer-events-none flex items-center justify-center">
        <span className="material-symbols-outlined text-[600px] text-white">account_balance</span>
      </div>

      <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden relative z-10 animate-in fade-in zoom-in-95 duration-200">
        {/* Navy Header Card */}
        <div className="bg-[#0f172a] px-8 py-6 text-white text-center border-b border-slate-800">
          <div className="w-12 h-12 mx-auto rounded-xl bg-blue-600 flex items-center justify-center text-white mb-3 shadow-md">
            <span className="material-symbols-outlined text-[28px]">lock</span>
          </div>
          <h2 className="text-xl font-bold tracking-tight">Institutional Auditor Portal</h2>
          <p className="text-xs text-slate-400 mt-1">
            College Accounts Department • Fee Receipt &amp; Invoice Auditor
          </p>
        </div>

        {/* Form Body */}
        <div className="p-8">
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-rose-600 shrink-0">error</span>
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="mb-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-emerald-600 shrink-0">check_circle</span>
              <span>{successMsg}</span>
            </div>
          )}

          {devOtpHint && (
            <div className="mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-center justify-between font-mono">
              <span>Demo OTP: <strong className="text-sm font-bold tracking-wider">{devOtpHint}</strong></span>
              <button
                type="button"
                onClick={() => setOtpCode(devOtpHint)}
                className="text-amber-700 underline text-[11px] font-sans font-medium hover:text-amber-900"
              >
                Auto-fill
              </button>
            </div>
          )}

          {/* Mode 1: Login */}
          {mode === 'login' && (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Email or Mobile Number
                </label>
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-slate-400">
                    person
                  </span>
                  <input
                    type="text"
                    required
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    placeholder="auditor@university.edu"
                    className="w-full pl-9 pr-3 py-2 border border-slate-300 rounded-lg text-xs font-medium focus:ring-2 focus:ring-blue-600 focus:outline-none transition-shadow"
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                    Password
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      setError(null);
                      setSuccessMsg(null);
                      setMode('forgot');
                    }}
                    className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                  >
                    Forgot?
                  </button>
                </div>
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-slate-400">
                    key
                  </span>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full pl-9 pr-3 py-2 border border-slate-300 rounded-lg text-xs font-medium focus:ring-2 focus:ring-blue-600 focus:outline-none transition-shadow"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full mt-2 py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-lg shadow-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {loading ? (
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <span className="material-symbols-outlined text-[18px]">login</span>
                    <span>Sign In to Audit Console</span>
                  </>
                )}
              </button>

              <div className="pt-4 border-t border-slate-200 text-center">
                <span className="text-xs text-slate-500">Need an auditor account? </span>
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setSuccessMsg(null);
                    setMode('register');
                  }}
                  className="text-xs font-semibold text-blue-600 hover:text-blue-800"
                >
                  Register Account
                </button>
              </div>
            </form>
          )}

          {/* Mode 2: Register */}
          {mode === 'register' && (
            <form onSubmit={handleRegister} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Senior Auditor Name"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs font-medium focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Institutional Email or Phone
                </label>
                <input
                  type="text"
                  required
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="auditor@university.edu"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs font-medium focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Create Password (min 8 chars)
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs font-medium focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-lg shadow-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {loading ? (
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <span className="material-symbols-outlined text-[18px]">person_add</span>
                    <span>Register &amp; Receive Code</span>
                  </>
                )}
              </button>

              <div className="pt-3 text-center">
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setSuccessMsg(null);
                    setMode('login');
                  }}
                  className="text-xs text-slate-600 hover:text-slate-900 font-medium"
                >
                  ← Back to Sign In
                </button>
              </div>
            </form>
          )}

          {/* Mode 3: Verify OTP */}
          {mode === 'verify' && (
            <form onSubmit={handleVerify} className="space-y-4">
              <p className="text-xs text-slate-600">
                Enter the 6-digit verification code sent for <strong className="font-semibold text-slate-800">{identifier}</strong>:
              </p>

              <div>
                <input
                  type="text"
                  required
                  maxLength={6}
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.trim())}
                  placeholder="000000"
                  className="w-full text-center tracking-[0.5em] font-mono text-lg py-2 border-2 border-blue-600 rounded-lg font-bold focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <button
                type="submit"
                disabled={loading || otpCode.length !== 6}
                className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-lg shadow-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {loading ? (
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <span className="material-symbols-outlined text-[18px]">verified</span>
                    <span>Verify &amp; Enter Console</span>
                  </>
                )}
              </button>

              <div className="pt-3 text-center">
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setSuccessMsg(null);
                    setMode('login');
                  }}
                  className="text-xs text-slate-600 hover:text-slate-900 font-medium"
                >
                  ← Back to Sign In
                </button>
              </div>
            </form>
          )}

          {/* Mode 4: Forgot Password */}
          {mode === 'forgot' && (
            <form onSubmit={handleForgotPassword} className="space-y-4">
              <p className="text-xs text-slate-600">
                Enter your registered identifier to receive a 6-digit password reset code:
              </p>

              <div>
                <input
                  type="text"
                  required
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="auditor@university.edu"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs font-medium focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-lg shadow-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {loading ? (
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <span>Send Reset Code</span>
                )}
              </button>

              <div className="pt-3 text-center">
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setSuccessMsg(null);
                    setMode('login');
                  }}
                  className="text-xs text-slate-600 hover:text-slate-900 font-medium"
                >
                  ← Back to Sign In
                </button>
              </div>
            </form>
          )}

          {/* Mode 5: Reset Password */}
          {mode === 'reset_pwd' && (
            <form onSubmit={handleResetPassword} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  6-Digit Reset Code
                </label>
                <input
                  type="text"
                  required
                  maxLength={6}
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.trim())}
                  placeholder="000000"
                  className="w-full text-center tracking-[0.4em] font-mono text-base py-2 border border-slate-300 rounded-lg font-bold focus:outline-none focus:ring-2 focus:ring-blue-600"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  New Password (min 8 chars)
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs font-medium focus:ring-2 focus:ring-blue-600 focus:outline-none"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-lg shadow-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {loading ? (
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <span>Update Password</span>
                )}
              </button>

              <div className="pt-3 text-center">
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setSuccessMsg(null);
                    setMode('login');
                  }}
                  className="text-xs text-slate-600 hover:text-slate-900 font-medium"
                >
                  ← Back to Sign In
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

