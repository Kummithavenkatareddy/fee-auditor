import React, { useState, useMemo } from 'react';
import { downloadAuditCsv } from '../services/api';
import StatusBadge from './StatusBadge';

export default function ReportsScreen({ documents = [] }) {
  const [statusFilter, setStatusFilter] = useState('all');
  const [docTypeFilter, setDocTypeFilter] = useState('all');
  const [isExporting, setIsExporting] = useState(false);
  const [exportSuccess, setExportSuccess] = useState(false);

  // Filtered documents for report preview
  const exportableDocs = useMemo(() => {
    return documents.filter((doc) => {
      if (statusFilter !== 'all' && doc.audit_status !== statusFilter) return false;
      if (docTypeFilter !== 'all' && doc.document_type !== docTypeFilter) return false;
      return true;
    });
  }, [documents, statusFilter, docTypeFilter]);

  // Total value audited in export batch
  const totalAuditedValue = useMemo(() => {
    const sum = exportableDocs.reduce((acc, d) => {
      const v = parseFloat(d.total?.value || 0);
      return acc + (isNaN(v) ? 0 : v);
    }, 0);
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(sum);
  }, [exportableDocs]);

  const handleDownloadCsv = async () => {
    setIsExporting(true);
    setExportSuccess(false);
    try {
      await downloadAuditCsv();
      setExportSuccess(true);
      setTimeout(() => setExportSuccess(false), 5000);
    } catch (err) {
      alert(`CSV Export Failed: ${err.message}`);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="flex flex-col w-full pb-16">
      {/* Top Meta Breadcrumb and Status Ribbon */}
      <div className="flex flex-wrap items-center justify-between gap-space-md py-space-md">
        <div className="flex items-center gap-space-sm text-body-sm font-body-sm text-on-surface-variant">
          <span className="font-data-mono text-data-mono text-outline">REF: REP-EXPT-2026-Q4</span>
          <span className="text-surface-container-highest">•</span>
          <span className="flex items-center gap-1 text-secondary font-medium">
            <span className="material-symbols-outlined text-[16px]">verified_user</span>
            Pandas Engine Export Verified
          </span>
        </div>
        <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-secondary-container text-on-secondary-container rounded-DEFAULT font-label-xs text-label-xs font-semibold shadow-xs">
          <span className="h-2 w-2 rounded-full bg-secondary"></span>
          Academic Term AY 2026-27 Active
        </div>
      </div>

      {/* Header Section */}
      <div className="bg-surface-container-lowest p-space-xl rounded-lg border border-surface-container-highest shadow-xs mb-space-lg flex flex-col md:flex-row md:items-end justify-between gap-space-lg">
        <div className="space-y-space-xs max-w-2xl">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-surface-container text-on-surface font-label-xs text-label-xs uppercase tracking-wider rounded-DEFAULT">
              Fiduciary Module
            </span>
            <span className="text-outline text-label-xs font-label-xs">
              Deterministic Ledger v2024-11-30
            </span>
          </div>
          <h1 className="text-headline-lg font-headline-lg text-primary tracking-tight">
            Reports &amp; CSV Export
          </h1>
          <p className="text-body-md font-body-md text-on-surface-variant leading-relaxed">
            Generate and export deterministic audit ledger data, compliance records, and CSV extracts with complete field-level confidence scores and validation flags.
          </p>
        </div>

        {/* Quick Ledger Stat Counters */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="bg-surface-container-low border border-surface-container-highest px-4 py-2.5 rounded-DEFAULT text-left">
            <div className="text-label-xs font-label-xs text-on-surface-variant uppercase">
              Exportable Batch
            </div>
            <div className="text-title-md font-title-md text-primary font-bold">
              {exportableDocs.length} Records
            </div>
          </div>
          <div className="bg-surface-container-low border border-surface-container-highest px-4 py-2.5 rounded-DEFAULT text-left">
            <div className="text-label-xs font-label-xs text-on-surface-variant uppercase">
              Audited Value
            </div>
            <div className="text-title-md font-title-md text-primary font-bold font-data-mono tnum">
              {totalAuditedValue}
            </div>
          </div>
        </div>
      </div>

      {/* Success Notification Banner */}
      {exportSuccess && (
        <div className="bg-secondary-container p-space-md rounded-DEFAULT shadow-xs mb-space-lg flex items-center justify-between border border-secondary-fixed-dim">
          <div className="flex items-center gap-space-md">
            <div className="w-8 h-8 rounded-DEFAULT bg-secondary text-on-secondary flex items-center justify-center shrink-0">
              <span className="material-symbols-outlined text-[18px]">cloud_done</span>
            </div>
            <div>
              <div className="text-body-md font-body-md text-on-secondary-container font-semibold">
                CSV downloaded successfully via Pandas engine!
              </div>
              <div className="text-body-sm font-body-sm text-on-secondary-container opacity-90 text-xs">
                Includes all document columns, field confidence scores, canonical decimal strings, and plain-language flag reasons.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start">
        {/* Left Filter Workspace */}
        <div className="lg:col-span-5 space-y-space-md">
          <div className="bg-surface-container-lowest p-space-lg rounded-lg border border-surface-container-highest shadow-xs">
            <div className="flex items-center justify-between pb-space-md mb-space-md border-b border-surface-container-highest">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[20px] text-primary">tune</span>
                <h2 className="text-title-md font-title-md text-primary">1. Export Parameters &amp; Scope</h2>
              </div>
              <span className="text-label-xs font-label-xs text-on-surface-variant uppercase tracking-wider">
                Config
              </span>
            </div>

            <div className="space-y-space-md">
              {/* Academic Term */}
              <div>
                <label className="block text-label-xs font-label-xs uppercase text-on-surface-variant mb-1.5 font-semibold">
                  Academic Term Window
                </label>
                <div className="p-2.5 rounded bg-surface-container-low text-xs text-on-surface font-mono border border-surface-container-highest">
                  2026-08-01 to 2026-12-31 (Fall 2026)
                </div>
              </div>

              {/* Document Type */}
              <div>
                <label className="block text-label-xs font-label-xs uppercase text-on-surface-variant mb-1.5 font-semibold">
                  Document Taxonomy
                </label>
                <select
                  value={docTypeFilter}
                  onChange={(e) => setDocTypeFilter(e.target.value)}
                  className="w-full h-[38px] bg-surface-container-low text-on-surface px-3 rounded-DEFAULT text-xs border border-surface-container-highest focus:outline-none"
                >
                  <option value="all">All Documents (Invoices &amp; Receipts)</option>
                  <option value="invoice">Vendor Invoices Only</option>
                  <option value="receipt">Fee Receipts Only</option>
                </select>
              </div>

              {/* Status Radio Pills */}
              <div className="pt-2">
                <label className="block text-label-xs font-label-xs uppercase text-on-surface-variant mb-2 font-semibold">
                  Verification State
                </label>
                <div className="flex flex-col space-y-2">
                  <label className="flex items-center gap-3 p-2.5 rounded-DEFAULT bg-surface-container-low cursor-pointer hover:bg-surface-container border border-surface-container-highest">
                    <input
                      type="radio"
                      name="audit_status"
                      value="all"
                      checked={statusFilter === 'all'}
                      onChange={() => setStatusFilter('all')}
                      className="h-4 w-4 accent-primary"
                    />
                    <span className="text-xs font-medium text-on-surface">Export All Documents ({documents.length})</span>
                  </label>
                  <label className="flex items-center gap-3 p-2.5 rounded-DEFAULT bg-surface-container-low cursor-pointer hover:bg-surface-container border border-surface-container-highest">
                    <input
                      type="radio"
                      name="audit_status"
                      value="clean"
                      checked={statusFilter === 'clean'}
                      onChange={() => setStatusFilter('clean')}
                      className="h-4 w-4 accent-primary"
                    />
                    <span className="text-xs font-medium text-[#287A52]">Clean Documents Only</span>
                  </label>
                  <label className="flex items-center gap-3 p-2.5 rounded-DEFAULT bg-surface-container-low cursor-pointer hover:bg-surface-container border border-surface-container-highest">
                    <input
                      type="radio"
                      name="audit_status"
                      value="flagged"
                      checked={statusFilter === 'flagged'}
                      onChange={() => setStatusFilter('flagged')}
                      className="h-4 w-4 accent-primary"
                    />
                    <span className="text-xs font-medium text-[#B54747]">Flagged Documents Only</span>
                  </label>
                </div>
              </div>

              {/* Primary Download Button */}
              <div className="pt-4 border-t border-surface-container-highest">
                <button
                  onClick={handleDownloadCsv}
                  disabled={isExporting}
                  className="w-full h-10 px-4 bg-primary text-on-primary hover:bg-primary-container disabled:opacity-50 rounded-DEFAULT font-title-md text-xs shadow-sm transition-all flex items-center justify-center gap-2"
                >
                  <span className="material-symbols-outlined text-[18px]">download</span>
                  <span>{isExporting ? 'Generating CSV...' : 'Download Full Audit CSV'}</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Right Preview Table */}
        <div className="lg:col-span-7 space-y-space-md">
          <div className="bg-surface-container-lowest p-space-lg rounded-lg border border-surface-container-highest shadow-xs">
            <div className="flex items-center justify-between pb-space-sm mb-space-sm border-b border-surface-container-highest">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[20px] text-primary">table_view</span>
                <h2 className="text-title-md font-title-md text-primary">2. Export Dataset Preview</h2>
              </div>
              <span className="text-label-xs font-label-xs text-on-surface-variant font-mono">
                {exportableDocs.length} Rows Ready
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse min-w-[500px]">
                <thead>
                  <tr className="bg-surface-container-low text-on-surface-variant font-label-xs text-label-xs uppercase h-8 border-b border-surface-container-highest">
                    <th className="px-3">File Name</th>
                    <th className="px-3">Vendor</th>
                    <th className="px-3 text-right">Total</th>
                    <th className="px-3 text-center">Status</th>
                    <th className="px-3 text-center">Flags</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-container-highest text-xs text-on-surface">
                  {exportableDocs.length === 0 ? (
                    <tr>
                      <td colSpan="5" className="py-8 text-center text-on-surface-variant">
                        No documents match selected export parameters
                      </td>
                    </tr>
                  ) : (
                    exportableDocs.map((doc, idx) => {
                      const totalStr = doc.total?.value
                        ? `₹${parseFloat(doc.total.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                        : '—';
                      return (
                        <tr key={idx} className="h-10 hover:bg-surface-container-low transition-colors">
                          <td className="px-3 font-mono truncate max-w-[140px]" title={doc.file_name}>
                            {doc.file_name}
                          </td>
                          <td className="px-3 truncate max-w-[140px]" title={doc.vendor_name?.value || '—'}>
                            {doc.vendor_name?.value || '—'}
                          </td>
                          <td className="px-3 text-right font-mono font-semibold tnum">
                            {totalStr}
                          </td>
                          <td className="px-3 text-center">
                            <StatusBadge status={doc.audit_status} />
                          </td>
                          <td className="px-3 text-center font-mono font-bold">
                            {(doc.validation_flags || []).length}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

