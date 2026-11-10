import React, { useState, useEffect, useCallback, useMemo } from 'react';
import AppShell from './components/AppShell';
import OverviewScreen from './components/OverviewScreen';
import DocumentsScreen from './components/DocumentsScreen';
import UploadScreen from './components/UploadScreen';
import AuditResultsScreen from './components/AuditResultsScreen';
import ManualReviewScreen from './components/ManualReviewScreen';
import ReportsScreen from './components/ReportsScreen';
import SettingsScreen from './components/SettingsScreen';
import AccountSecurityScreen from './components/AccountSecurityScreen';
import DocumentWorkspace from './components/DocumentWorkspace';
import LoginScreen from './components/LoginScreen';
import AuthModal from './components/AuthModal';
import { AuthProvider, useAuth } from './context/AuthContext';
import {
  fetchSummary,
  fetchDocuments,
  fetchDocument,
  resetDatabase,
} from './services/api';

function AppContent() {
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const [activeTab, setActiveTab] = useState('dashboard');
  const [searchValue, setSearchValue] = useState('');
  const [academicTerm, setAcademicTerm] = useState('Fall 2026');
  const [summary, setSummary] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load all user documents and summary when authenticated
  const loadData = useCallback(async () => {
    if (!isAuthenticated) {
      setDocuments([]);
      setSummary(null);
      setSelectedDoc(null);
      return;
    }
    try {
      setError(null);
      setDataLoading(true);
      const [sumData, docsData] = await Promise.all([
        fetchSummary().catch((err) => {
          console.warn('Summary fetch failed:', err.message);
          return null;
        }),
        fetchDocuments().catch((err) => {
          console.warn('Documents fetch failed:', err.message);
          return [];
        }),
      ]);
      setSummary(sumData);
      setDocuments(docsData || []);
    } catch (err) {
      setError(err.message || 'Failed to communicate with audit engine.');
    } finally {
      setDataLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      loadData();
    } else {
      // Clear all state when logged out
      setDocuments([]);
      setSummary(null);
      setSelectedDoc(null);
    }
  }, [isAuthenticated, loadData]);

  // Open full document detail in Document Workspace
  const handleSelectDoc = async (doc) => {
    if (!doc?.id) {
      setSelectedDoc(doc);
      return;
    }
    try {
      const fullDoc = await fetchDocument(doc.id);
      setSelectedDoc(fullDoc);
    } catch {
      setSelectedDoc(doc);
    }
  };

  // Re-fetch document when updated (review notes or revalidation)
  const handleDocUpdated = async () => {
    if (selectedDoc?.id) {
      try {
        const fullDoc = await fetchDocument(selectedDoc.id);
        setSelectedDoc(fullDoc);
      } catch (e) {
        console.warn('Failed to re-fetch selected document:', e);
      }
    }
    loadData();
  };

  // Reset database with user confirmation
  const handleResetData = async () => {
    if (window.confirm('Reset database? This will clear all ingested documents for clean testing.')) {
      try {
        await resetDatabase();
        await loadData();
      } catch (err) {
        setError(`Failed to reset: ${err.message}`);
      }
    }
  };

  // Pending review count for sidebar badge (clean documents strictly excluded!)
  const pendingReviewCount = useMemo(() => {
    if (summary && summary.pending_review_documents !== undefined) {
      return summary.pending_review_documents;
    }
    return documents.filter((d) => {
      const isClean = d.audit_status === 'clean' && (!d.validation_flags || d.validation_flags.length === 0);
      if (isClean) return false;
      return d.audit_status === 'flagged' || d.manual_review_status === 'pending';
    }).length;
  }, [summary, documents]);

  // Filtered documents by global search if active
  const displayedDocuments = useMemo(() => {
    if (!searchValue.trim()) return documents;
    const term = searchValue.toLowerCase();
    return documents.filter((d) => {
      const fname = (d.file_name || '').toLowerCase();
      const vname = (d.vendor_name?.value || '').toLowerCase();
      const inum = (d.invoice_id?.value || '').toLowerCase();
      const tax = (d.vendor_tax_id?.value || '').toLowerCase();
      return fname.includes(term) || vname.includes(term) || inum.includes(term) || tax.includes(term);
    });
  }, [documents, searchValue]);

  // Tab normalization
  const normalizedTab = useMemo(() => {
    if (activeTab === 'overview') return 'dashboard';
    if (activeTab === 'upload-documents') return 'upload';
    if (activeTab === 'audit-results') return 'findings';
    if (activeTab === 'manual-review') return 'review';
    if (activeTab === 'reports-export') return 'reports';
    return activeTab;
  }, [activeTab]);

  // 1. Initial Auth Loading State
  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex flex-col items-center justify-center text-slate-200">
        <div className="w-10 h-10 border-3 border-blue-500 border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-xs font-semibold tracking-wide text-slate-300">
          Verifying Institutional Auditor Credentials...
        </p>
      </div>
    );
  }

  // 2. Unauthenticated State: Institutional Login Gate (Zero Data Leakage)
  if (!isAuthenticated) {
    return (
      <>
        <LoginScreen onLoginSuccess={loadData} />
        <AuthModal />
      </>
    );
  }

  // 3. Authenticated State: AppShell with Flexbox Flow
  return (
    <>
      <AuthModal />
      <AppShell
        activeTab={normalizedTab}
        onTabChange={(tab) => {
          setSelectedDoc(null);
          setActiveTab(tab);
        }}
        pendingReviewCount={pendingReviewCount}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        academicTerm={academicTerm}
        onAcademicTermChange={setAcademicTerm}
        selectedDoc={selectedDoc}
        onResetData={handleResetData}
      >
        {/* Global Error Banner */}
        {error && (
          <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-rose-600">error</span>
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-rose-600 hover:opacity-80">
              <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
          </div>
        )}

        {/* Ingestion Loading Indicator */}
        {dataLoading && documents.length === 0 && (
          <div className="py-20 flex flex-col items-center justify-center text-slate-500">
            <div className="w-9 h-9 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mb-3"></div>
            <span className="text-xs font-semibold text-slate-700">Connecting to Audit Engine...</span>
          </div>
        )}

        {/* Selected Document Workspace View */}
        {selectedDoc ? (
          <DocumentWorkspace
            doc={selectedDoc}
            onClose={() => setSelectedDoc(null)}
            onUpdated={handleDocUpdated}
          />
        ) : (
          <>
            {/* 1. Dashboard View */}
            {normalizedTab === 'dashboard' && (
              <OverviewScreen
                summary={summary}
                documents={displayedDocuments}
                onSelectDoc={handleSelectDoc}
                onNavigateTab={setActiveTab}
              />
            )}

            {/* 2. Upload & Process View */}
            {normalizedTab === 'upload' && (
              <UploadScreen
                onUploadComplete={loadData}
                onSelectDoc={handleSelectDoc}
                onNavigateTab={setActiveTab}
              />
            )}

            {/* 3. My Documents View */}
            {normalizedTab === 'documents' && (
              <DocumentsScreen
                documents={displayedDocuments}
                onSelectDoc={handleSelectDoc}
                onRefresh={loadData}
                onNavigateTab={setActiveTab}
              />
            )}

            {/* 4. Audit Findings View */}
            {normalizedTab === 'findings' && (
              <AuditResultsScreen
                documents={displayedDocuments}
                onSelectDoc={handleSelectDoc}
                onRefresh={loadData}
              />
            )}

            {/* 5. Review Queue (Clean Excluded) */}
            {normalizedTab === 'review' && (
              <ManualReviewScreen
                documents={displayedDocuments}
                onSelectDoc={handleSelectDoc}
                onRefresh={loadData}
                onNavigateTab={setActiveTab}
              />
            )}

            {/* 6. Reports & Export View */}
            {normalizedTab === 'reports' && (
              <ReportsScreen documents={displayedDocuments} />
            )}

            {/* 7. Settings View */}
            {normalizedTab === 'settings' && (
              <SettingsScreen
                academicTerm={academicTerm}
                onAcademicTermChange={setAcademicTerm}
              />
            )}

            {/* 8. Account & Security View */}
            {normalizedTab === 'account' && (
              <AccountSecurityScreen onDataReset={loadData} />
            )}
          </>
        )}
      </AppShell>
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
