import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  changePasswordApi,
  resetMyDataApi,
  deleteAccountApi,
} from '../services/api';

export default function AccountSecurityScreen({ onDataReset }) {
  const { user, isAuthenticated, openAuth, logout, updateProfile } = useAuth();

  // Profile Edit
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [profileMsg, setProfileMsg] = useState(null);

  // Change Password
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordMsg, setPasswordMsg] = useState(null);
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  // Modals for Destructive Operations
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [resetPassword, setResetPassword] = useState('');
  const [resetPhrase, setResetPhrase] = useState('');
  const [resetError, setResetError] = useState(null);
  const [isResetting, setIsResetting] = useState(false);

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [deletePhrase, setDeletePhrase] = useState('');
  const [deleteError, setDeleteError] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleUpdateName = async (e) => {
    e.preventDefault();
    setProfileMsg(null);
    try {
      await updateProfile(fullName, user?.term_preference);
      setProfileMsg({ type: 'success', text: 'Profile updated successfully.' });
      setTimeout(() => setProfileMsg(null), 3000);
    } catch (err) {
      setProfileMsg({ type: 'error', text: err.message });
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    setPasswordMsg(null);
    if (newPassword !== confirmPassword) {
      setPasswordMsg({ type: 'error', text: 'New passwords do not match.' });
      return;
    }
    if (newPassword.length < 8) {
      setPasswordMsg({ type: 'error', text: 'Password must be at least 8 characters.' });
      return;
    }

    setIsChangingPassword(true);
    try {
      await changePasswordApi(currentPassword, newPassword);
      setPasswordMsg({ type: 'success', text: 'Password successfully updated.' });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => setPasswordMsg(null), 4000);
    } catch (err) {
      setPasswordMsg({ type: 'error', text: err.message || 'Failed to change password.' });
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleResetData = async (e) => {
    e.preventDefault();
    setResetError(null);
    if (resetPhrase !== 'RESET') {
      setResetError('Confirmation phrase must be exactly "RESET".');
      return;
    }

    setIsResetting(true);
    try {
      const res = await resetMyDataApi(resetPassword, 'RESET');
      setIsResetModalOpen(false);
      setResetPassword('');
      setResetPhrase('');
      alert(res.message || 'All your documents and stored files have been reset.');
      if (onDataReset) onDataReset();
    } catch (err) {
      setResetError(err.message || 'Reset failed.');
    } finally {
      setIsResetting(false);
    }
  };

  const handleDeleteAccount = async (e) => {
    e.preventDefault();
    setDeleteError(null);
    if (deletePhrase !== 'DELETE') {
      setDeleteError('Confirmation phrase must be exactly "DELETE".');
      return;
    }

    setIsDeleting(true);
    try {
      await deleteAccountApi(deletePassword, 'DELETE');
      setIsDeleteModalOpen(false);
      alert('Your account and all associated documents have been permanently purged.');
      window.location.reload();
    } catch (err) {
      setDeleteError(err.message || 'Account deletion failed.');
    } finally {
      setIsDeleting(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="max-w-xl mx-auto py-16 text-center space-y-4">
        <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-500">
          <span className="material-symbols-outlined text-[32px]">lock</span>
        </div>
        <h2 className="text-lg font-bold text-slate-900">Sign In to Manage Your Account</h2>
        <p className="text-xs text-slate-500 max-w-sm mx-auto">
          Log in with your auditor email or phone to view profile information, security settings, and manage persistent documents.
        </p>
        <button
          onClick={() => openAuth('login')}
          className="px-6 py-2.5 bg-[#0f172a] hover:bg-[#1e293b] text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
        >
          Sign In / Register
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">Account &amp; Security</h1>
        <p className="text-xs text-slate-500 mt-1">
          Auditor credentials, security credentials, and multi-user document data isolation controls.
        </p>
      </div>

      {/* Card 1: Auditor Profile & Identity */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-[#0f172a] text-white flex items-center justify-center font-bold text-base shadow-sm">
              {user?.full_name ? user.full_name.slice(0, 2).toUpperCase() : 'AO'}
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <span>{user?.full_name || 'Auditor Officer'}</span>
                {user?.is_verified && (
                  <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-semibold">
                    <span className="material-symbols-outlined text-[12px]">verified</span>
                    Verified
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-500 font-mono">
                {user?.email || user?.phone || user?.identifier}
              </p>
            </div>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            ID: {user?.id?.slice(0, 8)}...
          </span>
        </div>

        {profileMsg && (
          <div className={`p-2.5 rounded-lg text-xs flex items-center gap-2 ${profileMsg.type === 'success' ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-rose-50 text-rose-800 border border-rose-200'}`}>
            <span>{profileMsg.text}</span>
          </div>
        )}

        <form onSubmit={handleUpdateName} className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs items-end">
          <div className="md:col-span-2">
            <label className="block text-slate-700 font-semibold mb-1">Auditor Display Name</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Dr. Rajesh Sharma"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 text-xs focus:ring-1 focus:ring-blue-600 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            className="py-2 px-4 bg-[#0f172a] hover:bg-[#1e293b] text-white rounded-lg font-medium text-xs transition-colors shadow-sm"
          >
            Update Name
          </button>
        </form>
      </div>

      {/* Card 2: Change Password */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-2.5 pb-3 border-b border-slate-100">
          <span className="material-symbols-outlined text-blue-600 text-[20px]">lock_reset</span>
          <div>
            <h2 className="text-sm font-bold text-slate-900">Change Account Password</h2>
            <p className="text-xs text-slate-500">Requires your current password to verify identity.</p>
          </div>
        </div>

        {passwordMsg && (
          <div className={`p-2.5 rounded-lg text-xs flex items-center gap-2 ${passwordMsg.type === 'success' ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-rose-50 text-rose-800 border border-rose-200'}`}>
            <span>{passwordMsg.text}</span>
          </div>
        )}

        <form onSubmit={handleChangePassword} className="space-y-3 text-xs max-w-md">
          <div>
            <label className="block text-slate-700 font-semibold mb-1">Current Password</label>
            <input
              type="password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Enter current password"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 text-xs focus:ring-1 focus:ring-blue-600 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-slate-700 font-semibold mb-1">New Password (min 8 chars)</label>
            <input
              type="password"
              required
              minLength={8}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Enter new strong password"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 text-xs focus:ring-1 focus:ring-blue-600 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-slate-700 font-semibold mb-1">Confirm New Password</label>
            <input
              type="password"
              required
              minLength={8}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm new password"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 text-xs focus:ring-1 focus:ring-blue-600 focus:outline-none"
            />
          </div>

          <div className="pt-1">
            <button
              type="submit"
              disabled={isChangingPassword}
              className="px-4 py-2 bg-[#0f172a] hover:bg-[#1e293b] text-white rounded-lg text-xs font-medium transition-colors shadow-sm disabled:opacity-50"
            >
              {isChangingPassword ? 'Updating Password...' : 'Save New Password'}
            </button>
          </div>
        </form>
      </div>

      {/* Card 3: DANGER ZONE — Destructive Operations */}
      <div className="bg-white rounded-xl border border-rose-200 p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-2.5 pb-3 border-b border-rose-100">
          <span className="material-symbols-outlined text-rose-600 text-[22px]">warning</span>
          <div>
            <h2 className="text-sm font-bold text-rose-900">Danger Zone — Destructive Operations</h2>
            <p className="text-xs text-rose-600">
              Operations in this section require password re-authentication and typed confirmation.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          {/* Operation 1: Reset My Data */}
          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2 flex flex-col justify-between">
            <div>
              <h3 className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                <span className="material-symbols-outlined text-amber-600 text-[18px]">cleaning_services</span>
                Reset My Data
              </h3>
              <p className="text-slate-600 mt-1 text-xs">
                Permanently deletes all invoices, receipts, extracted line items, validation flags, and persistent storage files owned by your account.
              </p>
              <p className="text-slate-400 text-[11px] mt-1 italic">
                Your user account, login credentials, and profile settings remain intact.
              </p>
            </div>
            <button
              onClick={() => {
                setResetError(null);
                setResetPassword('');
                setResetPhrase('');
                setIsResetModalOpen(true);
              }}
              className="mt-3 px-3 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-medium text-xs transition-colors self-start shadow-2xs"
            >
              Reset My Ingested Data
            </button>
          </div>

          {/* Operation 2: Delete Account */}
          <div className="p-4 rounded-xl border border-rose-200 bg-rose-50/60 space-y-2 flex flex-col justify-between">
            <div>
              <h3 className="font-bold text-rose-900 text-sm flex items-center gap-1.5">
                <span className="material-symbols-outlined text-rose-600 text-[18px]">person_remove</span>
                Delete Account
              </h3>
              <p className="text-rose-800 mt-1 text-xs">
                Permanently purges your account credentials, active sessions, and all documents, line items, and physical storage files.
              </p>
              <p className="text-rose-600 text-[11px] mt-1 font-semibold">
                This action is irreversible. All data is deleted immediately.
              </p>
            </div>
            <button
              onClick={() => {
                setDeleteError(null);
                setDeletePassword('');
                setDeletePhrase('');
                setIsDeleteModalOpen(true);
              }}
              className="mt-3 px-3 py-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-medium text-xs transition-colors self-start shadow-2xs"
            >
              Permanently Delete Account
            </button>
          </div>
        </div>
      </div>

      {/* MODAL 1: RESET MY DATA */}
      {isResetModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-md w-full overflow-hidden">
            <div className="bg-amber-600 text-white px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[20px]">warning</span>
                <h3 className="font-bold text-sm">Confirm Data Reset</h3>
              </div>
              <button
                onClick={() => setIsResetModalOpen(false)}
                className="text-white hover:opacity-80"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            <form onSubmit={handleResetData} className="p-6 space-y-4 text-xs">
              <p className="text-slate-700">
                This will delete <strong>all extracted documents, line items, audit flags, and storage files</strong> associated with your account.
              </p>

              {resetError && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                  {resetError}
                </div>
              )}

              <div>
                <label className="block text-slate-700 font-semibold mb-1">
                  Re-enter Account Password
                </label>
                <input
                  type="password"
                  required
                  value={resetPassword}
                  onChange={(e) => setResetPassword(e.target.value)}
                  placeholder="Password"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 text-xs focus:ring-1 focus:ring-amber-600 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">
                  Type <span className="font-mono text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200 font-bold">RESET</span> to confirm
                </label>
                <input
                  type="text"
                  required
                  value={resetPhrase}
                  onChange={(e) => setResetPhrase(e.target.value)}
                  placeholder="RESET"
                  className="w-full font-mono bg-slate-50 border border-slate-300 rounded-lg p-2 text-xs tracking-wider font-bold focus:ring-1 focus:ring-amber-600 focus:outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsResetModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isResetting || resetPhrase !== 'RESET'}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                >
                  {isResetting ? 'Resetting...' : 'Confirm & Wipe Data'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: DELETE ACCOUNT */}
      {isDeleteModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-md w-full overflow-hidden">
            <div className="bg-rose-600 text-white px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[20px]">person_remove</span>
                <h3 className="font-bold text-sm">Permanent Account Deletion</h3>
              </div>
              <button
                onClick={() => setIsDeleteModalOpen(false)}
                className="text-white hover:opacity-80"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            <form onSubmit={handleDeleteAccount} className="p-6 space-y-4 text-xs">
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-lg">
                <strong>Warning:</strong> This action cannot be undone. Your user profile, sessions, all uploaded documents, and files will be permanently purged from the server.
              </div>

              {deleteError && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                  {deleteError}
                </div>
              )}

              <div>
                <label className="block text-slate-700 font-semibold mb-1">
                  Re-enter Account Password
                </label>
                <input
                  type="password"
                  required
                  value={deletePassword}
                  onChange={(e) => setDeletePassword(e.target.value)}
                  placeholder="Password"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 text-xs focus:ring-1 focus:ring-rose-600 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">
                  Type <span className="font-mono text-rose-700 bg-rose-50 px-1.5 py-0.5 rounded border border-rose-200 font-bold">DELETE</span> to confirm
                </label>
                <input
                  type="text"
                  required
                  value={deletePhrase}
                  onChange={(e) => setDeletePhrase(e.target.value)}
                  placeholder="DELETE"
                  className="w-full font-mono bg-slate-50 border border-slate-300 rounded-lg p-2 text-xs tracking-wider font-bold focus:ring-1 focus:ring-rose-600 focus:outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsDeleteModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isDeleting || deletePhrase !== 'DELETE'}
                  className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                >
                  {isDeleting ? 'Deleting...' : 'Delete My Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

