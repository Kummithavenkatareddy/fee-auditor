import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

export default function Header({
  activeTab,
  onTabChange,
  searchValue = '',
  onSearchChange,
  selectedDoc = null,
  onResetData,
  isCollapsed = false,
  academicTerm = 'Fall 2026',
  onAcademicTermChange,
  onToggleMobileMenu,
}) {
  const { user, isAuthenticated, logout, openAuth } = useAuth();
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const menuRef = useRef(null);

  // Close profile menu on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setProfileMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getBreadcrumbTitle = () => {
    switch (activeTab) {
      case 'dashboard':
      case 'overview':
        return 'Dashboard & Metrics';
      case 'upload':
      case 'upload-documents':
        return 'Upload & Ingest';
      case 'documents':
        return 'Document Library';
      case 'findings':
      case 'audit-results':
        return 'Audit Findings';
      case 'review':
      case 'manual-review':
        return 'Review Queue (Exceptions)';
      case 'reports':
      case 'reports-export':
        return 'Reports & Ledger Export';
      case 'settings':
        return 'Audit Preferences & Settings';
      case 'account':
        return 'Account & Security';
      default:
        return 'Institutional Auditor';
    }
  };

  return (
    <header
      className="h-16 w-full bg-white border-b border-slate-200 shrink-0 z-30 px-6 flex items-center justify-between shadow-xs"
    >
      {/* Left: Mobile Toggle & Breadcrumbs & Academic Term Selector */}
      <div className="flex items-center gap-3 min-w-0">
        {onToggleMobileMenu && (
          <button
            onClick={onToggleMobileMenu}
            className="md:hidden p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
            title="Toggle Menu"
          >
            <span className="material-symbols-outlined text-[20px]">menu</span>
          </button>
        )}
        <div className="flex items-center gap-1.5 text-xs text-slate-500 min-w-0">
          <span className="font-semibold text-slate-700 hidden sm:inline">Auditor Console</span>
          <span className="material-symbols-outlined text-[14px] text-slate-400">chevron_right</span>
          <span className="font-medium text-slate-900 truncate">{getBreadcrumbTitle()}</span>
          {selectedDoc && (
            <>
              <span className="material-symbols-outlined text-[14px] text-slate-400">chevron_right</span>
              <span className="font-mono text-blue-700 font-semibold truncate bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                {selectedDoc.file_name}
              </span>
            </>
          )}
        </div>

        <div className="h-4 w-px bg-slate-200 hidden md:block"></div>

        {/* Academic Term Dropdown */}
        <div className="relative hidden md:flex items-center">
          <span className="material-symbols-outlined absolute left-2 text-[16px] text-slate-400 pointer-events-none">
            calendar_today
          </span>
          <select
            value={academicTerm}
            onChange={(e) => onAcademicTermChange && onAcademicTermChange(e.target.value)}
            className="appearance-none bg-slate-50 border border-slate-300 text-slate-700 text-xs py-1.5 pl-7 pr-7 rounded-md font-medium focus:outline-none focus:ring-1 focus:ring-blue-600 focus:border-blue-600 cursor-pointer shadow-2xs hover:bg-slate-100 transition-colors"
          >
            <option value="Fall 2026">Term: Fall 2026 (Aug 1 - Dec 31, 2026)</option>
            <option value="Spring 2027">Term: Spring 2027 (Jan 1 - May 31, 2027)</option>
            <option value="Summer 2026">Term: Summer 2026 (Jun 1 - Jul 31, 2026)</option>
            <option value="AY 2026-27">Term: AY 2026-27 (Full Academic Year)</option>
          </select>
          <span className="material-symbols-outlined absolute right-1.5 text-[16px] text-slate-400 pointer-events-none">
            arrow_drop_down
          </span>
        </div>
      </div>

      {/* Right: Search, Engine Tag, and Profile Menu */}
      <div className="flex items-center gap-3">
        {/* Global Search Input */}
        <div className="relative w-44 sm:w-60 lg:w-72">
          <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-[16px] text-slate-400">
            search
          </span>
          <input
            value={searchValue}
            onChange={(e) => onSearchChange && onSearchChange(e.target.value)}
            className="w-full h-8.5 bg-slate-50 border border-slate-300 rounded-md pl-8 pr-7 text-xs font-mono text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-600 focus:border-blue-600 focus:bg-white transition-all shadow-2xs"
            placeholder="Search invoice, vendor, tax ID..."
            type="text"
          />
          {searchValue && (
            <button
              onClick={() => onSearchChange && onSearchChange('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"
            >
              <span className="material-symbols-outlined text-[14px]">close</span>
            </button>
          )}
        </div>

        {/* Engine Compliance Badge */}
        <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-1 bg-blue-50 border border-blue-200 text-blue-800 rounded-md text-[11px] font-medium">
          <span className="material-symbols-outlined text-[14px] text-blue-600">verified</span>
          <span>Zero-LLM • Deterministic V01–V05</span>
        </div>

        {/* User Account Menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setProfileMenuOpen(!profileMenuOpen)}
            className="flex items-center gap-2 p-1 pl-2 rounded-lg hover:bg-slate-100 border border-transparent hover:border-slate-200 transition-colors"
          >
            <div className="w-7 h-7 rounded-full bg-[#0f172a] text-white flex items-center justify-center font-bold text-xs shadow-2xs">
              {user?.full_name ? user.full_name.slice(0, 2).toUpperCase() : 'AO'}
            </div>
            <span className="material-symbols-outlined text-[16px] text-slate-500">
              {profileMenuOpen ? 'expand_less' : 'expand_more'}
            </span>
          </button>

          {/* Profile Dropdown */}
          {profileMenuOpen && (
            <div className="absolute right-0 mt-2 w-64 bg-white rounded-xl shadow-xl border border-slate-200 py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
              <div className="px-4 py-2 border-b border-slate-100">
                <p className="text-xs font-semibold text-slate-900 truncate">
                  {user?.full_name || user?.identifier || 'Guest Auditor'}
                </p>
                <p className="text-[11px] text-slate-500 font-mono truncate">
                  {user?.email || user?.phone || 'Local Session'}
                </p>
                {user?.is_verified && (
                  <span className="inline-flex items-center gap-1 mt-1 px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-medium">
                    <span className="material-symbols-outlined text-[11px]">verified</span>
                    Verified Auditor
                  </span>
                )}
              </div>

              <div className="py-1">
                <button
                  onClick={() => {
                    setProfileMenuOpen(false);
                    onTabChange && onTabChange('account');
                  }}
                  className="w-full px-4 py-2 text-left text-xs text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                >
                  <span className="material-symbols-outlined text-[16px] text-slate-500">
                    admin_panel_settings
                  </span>
                  Account &amp; Security
                </button>

                <button
                  onClick={() => {
                    setProfileMenuOpen(false);
                    onTabChange && onTabChange('settings');
                  }}
                  className="w-full px-4 py-2 text-left text-xs text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                >
                  <span className="material-symbols-outlined text-[16px] text-slate-500">tune</span>
                  Audit Preferences
                </button>
              </div>

              <div className="border-t border-slate-100 pt-1">
                {isAuthenticated ? (
                  <button
                    onClick={() => {
                      setProfileMenuOpen(false);
                      logout();
                    }}
                    className="w-full px-4 py-2 text-left text-xs text-rose-600 hover:bg-rose-50 flex items-center gap-2 font-medium"
                  >
                    <span className="material-symbols-outlined text-[16px]">logout</span>
                    Sign Out
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      setProfileMenuOpen(false);
                      openAuth('login');
                    }}
                    className="w-full px-4 py-2 text-left text-xs text-blue-600 hover:bg-blue-50 flex items-center gap-2 font-medium"
                  >
                    <span className="material-symbols-outlined text-[16px]">login</span>
                    Sign In / Register
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
