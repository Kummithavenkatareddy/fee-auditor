import React from 'react';
import { useAuth } from '../context/AuthContext';

export default function Sidebar({
  activeTab,
  onTabChange,
  pendingReviewCount = 0,
  isCollapsed = false,
  onToggleCollapse,
}) {
  const { user, isAuthenticated, openAuth } = useAuth();

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: 'dashboard', description: 'Overview & Metrics' },
    { id: 'upload', label: 'Upload & Process', icon: 'cloud_upload', description: '3-Stage Ingestion' },
    { id: 'documents', label: 'My Documents', icon: 'folder_open', description: 'Document Library' },
    { id: 'findings', label: 'Audit Findings', icon: 'policy', description: 'V01–V05 Violations' },
    { id: 'review', label: 'Review Queue', icon: 'rate_review', badge: pendingReviewCount, description: 'Exceptions Only' },
    { id: 'reports', label: 'Reports & Exports', icon: 'table_chart', description: 'Ledger CSV & Summary' },
    { id: 'settings', label: 'Settings', icon: 'tune', description: 'Terms & Rules' },
    { id: 'account', label: 'Account & Security', icon: 'admin_panel_settings', description: 'Profile & Isolation' },
  ];

  // Normalized active tab for backward compatibility
  const normalizeTab = (tab) => {
    if (tab === 'overview') return 'dashboard';
    if (tab === 'upload-documents') return 'upload';
    if (tab === 'audit-results') return 'findings';
    if (tab === 'manual-review') return 'review';
    if (tab === 'reports-export') return 'reports';
    return tab;
  };

  const currentTab = normalizeTab(activeTab);

  return (
    <aside
      className="h-full w-full bg-[#0f172a] text-slate-200 flex flex-col justify-between border-r border-slate-800 transition-all duration-200 select-none"
    >
      <div className="flex flex-col">
        {/* Header / Brand */}
        <div className="h-16 px-4 flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold shadow-sm shrink-0">
              <span className="material-symbols-outlined text-[20px]">account_balance</span>
            </div>
            {!isCollapsed && (
              <div className="flex flex-col min-w-0 animate-in fade-in duration-150">
                <span className="font-semibold text-white tracking-tight leading-tight truncate text-sm">
                  Fee Auditor
                </span>
                <span className="text-[10px] text-slate-400 truncate uppercase tracking-wider font-mono">
                  Accounts &amp; Audit
                </span>
              </div>
            )}
          </div>
          {onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800 transition-colors shrink-0"
            >
              <span className="material-symbols-outlined text-[18px]">
                {isCollapsed ? 'chevron_right' : 'chevron_left'}
              </span>
            </button>
          )}
        </div>

        {/* Navigation links */}
        <nav className="flex flex-col p-2 space-y-1">
          {navItems.map((item) => {
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                title={isCollapsed ? `${item.label} — ${item.description}` : undefined}
                className={`flex items-center justify-between px-3 py-2.5 rounded-lg transition-all duration-150 text-left w-full group ${
                  isActive
                    ? 'bg-blue-600 text-white font-medium shadow-sm'
                    : 'text-slate-300 hover:bg-slate-800/80 hover:text-white'
                }`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span
                    className={`material-symbols-outlined text-[20px] shrink-0 ${
                      isActive ? 'text-white' : 'text-slate-400 group-hover:text-blue-400'
                    }`}
                  >
                    {item.icon}
                  </span>
                  {!isCollapsed && (
                    <div className="flex flex-col min-w-0 leading-tight">
                      <span className="text-xs font-medium truncate">{item.label}</span>
                      <span className={`text-[10px] truncate ${isActive ? 'text-blue-100' : 'text-slate-400'}`}>
                        {item.description}
                      </span>
                    </div>
                  )}
                </div>

                {item.badge > 0 && (
                  <span
                    className={`px-1.5 py-0.5 rounded-full font-mono text-[10px] font-bold shrink-0 ${
                      isActive
                        ? 'bg-white text-blue-700'
                        : 'bg-rose-500 text-white shadow-xs animate-pulse'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer: User Profile & Engine Status */}
      <div className="flex flex-col border-t border-slate-800 p-3 space-y-2 bg-[#090d16]">
        {!isCollapsed && (
          <div className="flex items-center justify-between px-2.5 py-1.5 bg-slate-900/80 border border-slate-800 rounded-md text-[11px]">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="h-2 w-2 rounded-full bg-emerald-400 shrink-0"></span>
              <span className="text-slate-300 truncate">V01–V05 Rules</span>
            </div>
            <span className="text-emerald-400 font-mono font-bold text-[10px]">ACTIVE</span>
          </div>
        )}

        {/* User Card */}
        <div
          onClick={() => (isAuthenticated ? onTabChange('account') : openAuth('login'))}
          className="flex items-center gap-2.5 p-2 rounded-lg bg-slate-900/60 hover:bg-slate-800/80 cursor-pointer border border-slate-800/80 transition-colors"
          title={isAuthenticated ? 'Open Account & Security' : 'Click to Sign In'}
        >
          <div className="w-8 h-8 rounded-full bg-blue-700 text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-sm">
            {user?.full_name ? user.full_name.slice(0, 2).toUpperCase() : 'AO'}
          </div>
          {!isCollapsed && (
            <div className="flex flex-col min-w-0 flex-1">
              <div className="text-xs text-white truncate font-medium flex items-center gap-1">
                <span>{user?.full_name || user?.identifier || 'Accounts Officer'}</span>
                {user?.is_verified && (
                  <span className="material-symbols-outlined text-[13px] text-emerald-400" title="Verified Auditor">
                    verified
                  </span>
                )}
              </div>
              <div className="text-[10px] text-slate-400 truncate font-mono">
                {isAuthenticated ? user?.email || user?.phone || 'Logged In' : 'Click to Sign In'}
              </div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
