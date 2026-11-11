import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { forgotPasswordApi, resetPasswordApi } from '../services/api';

export default function AuthModal() {
  const {
    authModalOpen,
    authModalMode,
    pendingIdentifier,
    setAuthModalMode,
    setPendingIdentifier,
    login,
    register,
    verify,
    closeAuth,
  } = useAuth();

  const [identifier, setIdentifier] = useState(pendingIdentifier || '');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [loading, setLoading] = useState(false);
  const [devCodeHint, setDevCodeHint] = useState(null);

  if (!authModalOpen) return null;

  const handleLogin = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(identifier, password);
    } catch (err) {
      if (err.message && err.message.toLowerCase().includes('not verified')) {
        setPendingIdentifier(identifier);
        setAuthModalMode('verify');
        setError('Please verify your account using the 6-digit code.');
      } else {
        setError(err.message || 'Login failed. Please check credentials.');
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
        setDevCodeHint(res.dev_verification_code);
      }
      setSuccessMsg('Account created. Enter the 6-digit code sent to complete verification.');
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
      await verify(pendingIdentifier || identifier, otpCode);
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
        setDevCodeHint(res.dev_reset_code);
      }
      setSuccessMsg('Password reset code generated. Enter code and new password.');
      setAuthModalMode('reset_pwd');
    } catch (err) {
      setError(err.message || 'Password reset request failed.');
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
      setSuccessMsg('Password reset successfully. You may now sign in.');
      setAuthModalMode('login');
      setPassword('');
      setOtpCode('');
    } catch (err) {
      setError(err.message || 'Password reset failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 animate-in fade-in duration-150">
      <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-md w-full overflow-hidden">
        {/* Modal Header */}
        <div className="bg-[#0f172a] text-white px-6 py-5 flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white shadow-sm">
              ₹
            </div>
            <div>
              <h2 className="text-base font-semibold leading-tight tracking-wide">
                {authModalMode === 'login' && 'Sign In to Auditor Portal'}
                {authModalMode === 'register' && 'Register Auditor Account'}
                {authModalMode === 'verify' && 'Verify 6-Digit OTP'}
                {authModalMode === 'forgot' && 'Reset Password'}
                {authModalMode === 'reset_pwd' && 'Set New Password'}
              </h2>
              <p className="text-xs text-slate-400">Institutional Financial Audit System</p>
            </div>
          </div>
          <button
            onClick={closeAuth}
            className="text-slate-400 hover:text-white transition-colors"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6">
          {error && (
            <div className="mb-4 p-3 rounded-md bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px] text-red-600">error</span>
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="mb-4 p-3 rounded-md bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px] text-emerald-600">check_circle</span>
              <span>{successMsg}</span>
            </div>
          )}

          {devCodeHint && (
            <div className="mb-4 p-3 rounded-md bg-blue-50 border border-blue-200 text-blue-800 text-xs flex items-center justify-between">
              <div>
                <span className="font-semibold">Verification Code: </span>
                <span className="font-mono bg-white px-2 py-0.5 rounded border border-blue-200 font-bold tracking-widest">
                  {devCodeHint}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setOtpCode(devCodeHint)}
                className="text-xs font-semibold text-blue-700 underline hover:text-blue-900"
              >
                Auto-fill
              </button>
            </div>
          )}

          {/* Mode 1: LOGIN */}
          {authModalMode === 'login' && (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Email or Phone Number
                </label>
                <input
                  type="text"
                  required
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="auditor@university.edu or +91..."
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-slate-700">Password</label>
                  <button
                    type="button"
                    onClick={() => {
                      setError(null);
                      setSuccessMsg(null);
                      setAuthModalMode('forgot');
                    }}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    Forgot password?
                  </button>
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 bg-[#0f172a] hover:bg-[#1e293b] text-white font-medium text-sm rounded-lg transition-colors shadow-sm disabled:opacity-50"
              >
                {loading ? 'Authenticating...' : 'Sign In'}
              </button>

              <div className="pt-2 text-center text-xs text-slate-500">
                Don't have an auditor account?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setSuccessMsg(null);
                    setAuthModalMode('register');
                  }}
                  className="text-blue-600 font-semibold hover:underline"
                >
                  Register here
                </button>
              </div>
            </form>
          )}

          {/* Mode 2: REGISTER */}
          {authModalMode === 'register' && (
            <form onSubmit={handleRegister} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Auditor Full Name
                </label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Dr. Rajesh Sharma"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Email or Phone Number
                </label>
                <input
                  type="text"
                  required
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="auditor@university.edu or +91 98765 43210"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Password (min 8 characters)
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Choose a strong password"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 bg-[#0f172a] hover:bg-[#1e293b] text-white font-medium text-sm rounded-lg transition-colors shadow-sm disabled:opacity-50"
              >
                {loading ? 'Creating Account...' : 'Register & Receive OTP'}
              </button>

              <div className="pt-2 text-center text-xs text-slate-500">
                Already registered?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setSuccessMsg(null);
                    setAuthModalMode('login');
                  }}
                  className="text-blue-600 font-semibold hover:underline"
                >
                  Sign in
                </button>
              </div>
            </form>
          )}

          {/* Mode 3: VERIFY OTP */}
          {authModalMode === 'verify' && (
            <form onSubmit={handleVerify} className="space-y-4">
              <p className="text-xs text-slate-600">
                Enter the 6-digit verification code sent to{' '}
                <span className="font-semibold text-slate-900">{pendingIdentifier || identifier}</span>.
              </p>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  6-Digit Verification Code
                </label>
                <input
                  type="text"
                  maxLength={6}
                  required
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                  placeholder="123456"
                  className="w-full px-3 py-2 text-center tracking-[0.5em] font-mono text-lg font-bold border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
                />
              </div>

              <button
                type="submit"
                disabled={loading || otpCode.length !== 6}
                className="w-full py-2.5 px-4 bg-[#0f172a] hover:bg-[#1e293b] text-white font-medium text-sm rounded-lg transition-colors shadow-sm disabled:opacity-50"
              >
                {loading ? 'Verifying...' : 'Verify & Continue'}
              </button>

              <div className="pt-2 text-center text-xs text-slate-500">
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setAuthModalMode('login');
                  }}
                  className="text-slate-600 hover:underline"
                >
                  Back to Sign In
                </button>
              </div>
            </form>
          )}

          {/* Mode 4: FORGOT PASSWORD */}
          {authModalMode === 'forgot' && (
            <form onSubmit={handleForgotPassword} className="space-y-4">
              <p className="text-xs text-slate-600">
                Enter the email or phone number associated with your auditor account to receive a reset code.
              </p>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Email or Phone Number
                </label>
                <input
                  type="text"
                  required
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="auditor@university.edu"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 bg-[#0f172a] hover:bg-[#1e293b] text-white font-medium text-sm rounded-lg transition-colors shadow-sm disabled:opacity-50"
              >
                {loading ? 'Sending Code...' : 'Send Reset Code'}
              </button>

              <div className="pt-2 text-center text-xs text-slate-500">
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setAuthModalMode('login');
                  }}
                  className="text-slate-600 hover:underline"
                >
                  Back to Sign In
                </button>
              </div>
            </form>
          )}

          {/* Mode 5: RESET PASSWORD WITH CODE */}
          {authModalMode === 'reset_pwd' && (
            <form onSubmit={handleResetPassword} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  6-Digit Reset Code
                </label>
                <input
                  type="text"
                  maxLength={6}
                  required
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                  placeholder="123456"
                  className="w-full px-3 py-2 text-center tracking-[0.4em] font-mono text-base font-bold border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  New Password (min 8 characters)
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new strong password"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
                />
              </div>

              <button
                type="submit"
                disabled={loading || otpCode.length !== 6 || newPassword.length < 8}
                className="w-full py-2.5 px-4 bg-[#0f172a] hover:bg-[#1e293b] text-white font-medium text-sm rounded-lg transition-colors shadow-sm disabled:opacity-50"
              >
                {loading ? 'Updating Password...' : 'Save New Password'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

