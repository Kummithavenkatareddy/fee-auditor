import React, { useState, useMemo } from 'react';
import ConfidenceBadge from './ConfidenceBadge';
import SeverityBadge from './SeverityBadge';
import { updateManualReview, downloadAuditCsv } from '../services/api';

export default function ManualReviewScreen({ documents = [], onSelectDoc, onRefresh, onNavigateTab }) {
  const [filterType, setFilterType] = useState('all');
  const [actionMessage, setActionMessage] = useState(null);
  const [reviewNoteInputs, setReviewNoteInputs] = useState({});

  // Clean documents MUST be strictly excluded from Review Queue!
  // Only documents with audit_status === 'flagged', or having active validation flags,
  // or marked pending with compliance concerns appear here.
  const reviewQueueDocs = useMemo(() => {
    return documents.filter((doc) => {
      const flags = doc.validation_flags || [];
      const isClean = doc.audit_status === 'clean' && flags.length === 0;
      // Strictly exclude clean documents
      if (isClean) return false;
      return doc.audit_status === 'flagged' || doc.manual_review_status === 'pending';
    });
  }, [documents]);

  // Counts for chips
  const counts = useMemo(() => {
    let lowConf = 0;
    let missingTax = 0;
    let discrepancies = 0;

    reviewQueueDocs.forEach((doc) => {
      const flags = doc.validation_flags || [];
      if (flags.some((f) => f.rule_id === 'V05')) lowConf += 1;
      if (flags.some((f) => f.rule_id === 'V02')) missingTax += 1;
      if (flags.some((f) => ['V01', 'V03', 'V04'].includes(f.rule_id))) discrepancies += 1;
    });

    return { all: reviewQueueDocs.length, lowConf, missingTax, discrepancies };
  }, [reviewQueueDocs]);

  // Filtered queue
  const filteredQueue = useMemo(() => {
    return reviewQueueDocs.filter((doc) => {
      const flags = doc.validation_flags || [];
      if (filterType === 'low-conf') {
        return flags.some((f) => f.rule_id === 'V05');
      }
      if (filterType === 'missing-tax') {
        return flags.some((f) => f.rule_id === 'V02');
      }
      if (filterType === 'discrepancy') {
        return flags.some((f) => ['V01', 'V03', 'V04'].includes(f.rule_id));
      }
      return true;
    });
  }, [reviewQueueDocs, filterType]);

  const handleDecision = async (docId, decision) => {
    const note = reviewNoteInputs[docId]?.trim();
    if (!note && (decision === 'approved' || decision === 'rejected')) {
      setActionMessage({
        type: 'error',
        text: 'Auditor note / statutory justification is required before approving or rejecting.',
      });
      return;
    }

    try {
      await updateManualReview(docId, decision, note || `Auditor ${decision}`);
      setActionMessage({ type: 'success', text: `Document successfully marked as ${decision}.` });
      setReviewNoteInputs((prev) => ({ ...prev, [docId]: '' }));
      if (onRefresh) onRefresh();
      setTimeout(() => setActionMessage(null), 3500);
    } catch (err) {
      setActionMessage({ type: 'error', text: `Failed to update status: ${err.message}` });
    }
  };

  const handleExport = async () => {
    try {
      await downloadAuditCsv();
    } catch (err) {
      alert(`Export failed: ${err.message}`);
    }
  };

  return (
    <div className="flex flex-col w-full pb-12">
      {/* Top Header Block */}
      <div className="flex flex-col gap-4 mb-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex flex-col space-y-1">
            <div className="flex items-center gap-2 text-slate-500 text-xs uppercase tracking-wider font-semibold">
              <span className="inline-block w-2 h-2 rounded-full bg-rose-500 animate-pulse"></span>
              <span>Exceptions &amp; Discrepancies</span>
              <span>•</span>
              <span className="text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                Clean Documents Excluded ({documents.length - reviewQueueDocs.length} clean)
              </span>
            </div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Manual Review Queue
            </h1>
            <p className="text-xs text-slate-500">
              Documents requiring auditor intervention due to arithmetic mismatch, missing GSTIN, or out-of-term dates.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={onRefresh}
              className="h-9 px-3 bg-white hover:bg-slate-50 text-slate-700 rounded-lg border border-slate-300 text-xs font-medium flex items-center gap-1.5 transition-colors shadow-2xs"
            >
              <span className="material-symbols-outlined text-[16px]">sync</span>
              <span>Refresh Queue</span>
            </button>
            <button
              onClick={() => (onNavigateTab ? onNavigateTab('reports') : handleExport())}
              className="h-9 px-3 bg-white hover:bg-slate-50 text-slate-700 rounded-lg border border-slate-300 text-xs font-medium flex items-center gap-1.5 transition-colors shadow-2xs"
            >
              <span className="material-symbols-outlined text-[16px] text-blue-600">table_chart</span>
              <span>Reports &amp; Exports</span>
            </button>
          </div>
        </div>

        {/* Global Action Banner */}
        {actionMessage && (
          <div
            className={`p-3 rounded-lg text-xs flex items-center justify-between ${
              actionMessage.type === 'success'
                ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
                : 'bg-rose-50 border border-rose-200 text-rose-800'
            }`}
          >
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px]">
                {actionMessage.type === 'success' ? 'check_circle' : 'error'}
              </span>
              <span>{actionMessage.text}</span>
            </div>
            <button onClick={() => setActionMessage(null)}>
              <span className="material-symbols-outlined text-[14px]">close</span>
            </button>
          </div>
        )}

        {/* Filter Chips */}
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <button
            onClick={() => setFilterType('all')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
              filterType === 'all'
                ? 'bg-slate-900 text-white shadow-2xs'
                : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
            }`}
          >
            All Exceptions ({counts.all})
          </button>
          <button
            onClick={() => setFilterType('discrepancy')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
              filterType === 'discrepancy'
                ? 'bg-rose-600 text-white shadow-2xs'
                : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
            }`}
          >
            Calculation / Term Flags ({counts.discrepancies})
          </button>
          <button
            onClick={() => setFilterType('missing-tax')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
              filterType === 'missing-tax'
                ? 'bg-amber-600 text-white shadow-2xs'
                : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
            }`}
          >
            Missing GSTIN ({counts.missingTax})
          </button>
          <button
            onClick={() => setFilterType('low-conf')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
              filterType === 'low-conf'
                ? 'bg-blue-600 text-white shadow-2xs'
                : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
            }`}
          >
            Low OCR Confidence ({counts.lowConf})
          </button>
        </div>
      </div>

      {/* Review Cards Grid */}
      {filteredQueue.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-xs">
          <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto mb-3">
            <span className="material-symbols-outlined text-[28px]">done_all</span>
          </div>
          <h3 className="text-base font-bold text-slate-900">Review Queue is Clear</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
            No pending exceptions require verification under the current filter. All valid documents have been cleared.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredQueue.map((doc) => {
            const flags = doc.validation_flags || [];
            const formattedTotal = doc.total?.value
              ? `₹${parseFloat(doc.total.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
              : '—';
            const noteValue = reviewNoteInputs[doc.id] || '';

            return (
              <div
                key={doc.id}
                className="bg-white rounded-xl border border-slate-200 shadow-xs hover:border-slate-300 transition-colors p-5 space-y-4"
              >
                {/* Header Row */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-100 gap-2">
                  <div className="flex items-center gap-3">
                    <span className="material-symbols-outlined text-rose-600 text-[22px]">
                      warning
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-slate-900">{doc.file_name}</span>
                        <span className="font-mono text-xs text-slate-500">
                          ({doc.invoice_id?.value || 'No ID'})
                        </span>
                      </div>
                      <span className="text-xs text-slate-600 font-medium">
                        {doc.vendor_name?.value || 'Payee Unknown'}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 self-end sm:self-auto">
                    <span className="text-xs font-mono font-bold text-slate-900">
                      Total: {formattedTotal}
                    </span>
                    <button
                      onClick={() => onSelectDoc(doc)}
                      className="px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-xs text-blue-700 font-medium flex items-center gap-1 shadow-2xs"
                    >
                      <span>Open Workspace</span>
                      <span className="material-symbols-outlined text-[14px]">open_in_new</span>
                    </button>
                  </div>
                </div>

                {/* Flags Breakdown */}
                <div className="space-y-1.5">
                  <span className="text-[10px] font-bold uppercase text-slate-400 block tracking-wider">
                    Identified Exceptions ({flags.length})
                  </span>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                    {flags.map((flag, idx) => (
                      <div
                        key={idx}
                        className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex flex-col space-y-0.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-900">{flag.rule_id}: {flag.rule_name}</span>
                          <SeverityBadge severity={flag.severity} />
                        </div>
                        <p className="text-slate-600 text-[11px]">{flag.reason}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Reviewer Action Bar */}
                <div className="pt-2 border-t border-slate-100 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                  <input
                    type="text"
                    value={noteValue}
                    onChange={(e) =>
                      setReviewNoteInputs({ ...reviewNoteInputs, [doc.id]: e.target.value })
                    }
                    placeholder="Enter mandatory auditor justification note to approve or reject..."
                    className="flex-1 bg-slate-50 border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-600 focus:bg-white"
                  />

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => handleDecision(doc.id, 'approved')}
                      className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1 transition-colors shadow-2xs"
                    >
                      <span className="material-symbols-outlined text-[15px]">check</span>
                      <span>Approve</span>
                    </button>
                    <button
                      onClick={() => handleDecision(doc.id, 'rejected')}
                      className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1 transition-colors shadow-2xs"
                    >
                      <span className="material-symbols-outlined text-[15px]">close</span>
                      <span>Reject</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
