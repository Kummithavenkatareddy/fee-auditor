import React, { useState } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';

export default function AppShell({
  activeTab,
  onTabChange,
  pendingReviewCount = 0,
  searchValue = '',
  onSearchChange,
  academicTerm = 'Fall 2026',
  onAcademicTermChange,
  selectedDoc = null,
  onResetData,
  children,
}) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 antialiased font-sans">
      {/* Mobile Backdrop Overlay */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/60 backdrop-blur-xs md:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar: In standard flex-flow on desktop, overlay drawer on mobile */}
      <div
        className={`fixed inset-y-0 left-0 z-50 transform md:relative md:translate-x-0 transition-[width,transform] duration-200 ease-in-out ${
          isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        } ${isSidebarCollapsed ? 'w-[72px]' : 'w-60'} shrink-0 h-full`}
      >
        <Sidebar
          activeTab={activeTab}
          onTabChange={(tab) => {
            onTabChange(tab);
            setIsMobileMenuOpen(false);
          }}
          pendingReviewCount={pendingReviewCount}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        />
      </div>

      {/* Main Column: Header at top, scrollable main content below */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden bg-slate-50">
        <Header
          activeTab={activeTab}
          onTabChange={onTabChange}
          searchValue={searchValue}
          onSearchChange={onSearchChange}
          selectedDoc={selectedDoc}
          onResetData={onResetData}
          academicTerm={academicTerm}
          onAcademicTermChange={onAcademicTermChange}
          onToggleMobileMenu={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          isCollapsed={isSidebarCollapsed}
        />

        <main className={`flex-1 overflow-y-auto bg-slate-50 ${selectedDoc ? 'p-0' : 'px-6 py-5'}`}>
          <div className={selectedDoc ? 'w-full' : 'max-w-7xl mx-auto space-y-6'}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

