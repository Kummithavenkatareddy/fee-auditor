import React, { useState } from 'react';
import ConfidenceBadge from './ConfidenceBadge';
import SeverityBadge from './SeverityBadge';
import StatusBadge from './StatusBadge';
import { updateManualReview, revalidateDocument, getDocumentFileUrl } from '../services/api';

export default function DocumentWorkspace({ doc, onClose, onUpdated }) {
  const [activePreviewTab, setActivePreviewTab] = useState('pdf'); // 'pdf' | 'paper'
  const [zoomLevel, setZoomLevel] = useState(100);
  const [rotation, setRotation] = useState(0);
  const [showJsonModal, setShowJsonModal] = useState(false);
  const [copiedJson, setCopiedJson] = useState(false);

  // Manual Review Form State
  const [reviewStatus, setReviewStatus] = useState(doc?.manual_review_status || 'pending');
  const [reviewerNotes, setReviewerNotes] = useState(doc?.manual_review_notes || '');
  const [isSavingReview, setIsSavingReview] = useState(false);
  const [reviewSavedSuccess, setReviewSavedSuccess] = useState(false);
  const [reviewError, setReviewError] = useState(null);

  // Revalidation state
  const [isRevalidating, setIsRevalidating] = useState(false);
  const [revalidationMsg, setRevalidationMsg] = useState(null);

  if (!doc) return null;

  const isInvoice = doc.document_type === 'invoice';
  const flags = doc.validation_flags || [];
  const lineItems = doc.line_items || [];
  const auditHistory = doc.audit_history || [];

  // Server-authoritative reconciliation breakdown
  const rec = doc.reconciliation;
  const hasV01Flag = flags.some((f) => f.rule_id === 'V01');
  const v01Flag = flags.find((f) => f.rule_id === 'V01');

  const lineItemsSum = lineItems.reduce((acc, it) => acc + (parseFloat(it.amount || 0) || 0), 0);
  const isReconciled = rec ? rec.is_reconciled : !hasV01Flag;
  const isMismatch = rec ? rec.status === 'MISMATCH' : hasV01Flag;
  const isManualReview = rec ? rec.status === 'MANUAL_REVIEW_REQUIRED' : false;

  const fileUrl = getDocumentFileUrl(doc.id);

  // Zoom handlers
  const handleZoomIn = () => setZoomLevel((z) => Math.min(z + 15, 180));
  const handleZoomOut = () => setZoomLevel((z) => Math.max(z - 15, 60));
  const handleFit = () => {
    setZoomLevel(100);
    setRotation(0);
  };
  const handleRotate = () => setRotation((r) => (r + 90) % 360);

  // Save manual review decision
  const handleSaveReview = async () => {
    setReviewError(null);
    if ((reviewStatus === 'approved' || reviewStatus === 'rejected') && !reviewerNotes.trim()) {
      setReviewError('Please provide auditor notes / rationale when updating review status.');
      return;
    }

    setIsSavingReview(true);
    setReviewSavedSuccess(false);
    try {
      await updateManualReview(doc.id, reviewStatus, reviewerNotes);
      setReviewSavedSuccess(true);
      setTimeout(() => setReviewSavedSuccess(false), 3000);
      if (onUpdated) onUpdated();
    } catch (err) {
      setReviewError(`Failed to save manual decision: ${err.message}`);
    } finally {
      setIsSavingReview(false);
    }
  };

  // Revalidate document
  const handleRevalidate = async () => {
    setIsRevalidating(true);
    setRevalidationMsg(null);
    try {
      await revalidateDocument(doc.id);
      setRevalidationMsg('Document successfully revalidated against deterministic rules.');
      setTimeout(() => setRevalidationMsg(null), 3000);
      if (onUpdated) onUpdated();
    } catch (err) {
      setRevalidationMsg(`Revalidation failed: ${err.message}`);
    } finally {
      setIsRevalidating(false);
    }
  };

  // Copy JSON payload
  const handleCopyJson = () => {
    const payload = doc.raw_azure_json || JSON.stringify(doc, null, 2);
    navigator.clipboard.writeText(payload);
    setCopiedJson(true);
    setTimeout(() => setCopiedJson(false), 2000);
  };

  const formattedSubtotal = doc.subtotal?.value
    ? `₹${parseFloat(doc.subtotal.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
    : '—';
  const formattedTax = doc.tax?.value
    ? `₹${parseFloat(doc.tax.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
    : '—';
  const formattedTotal = doc.total?.value
    ? `₹${parseFloat(doc.total.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
    : '—';

  return (
    <div className="w-full flex flex-col bg-slate-50 min-h-full pb-16 animate-in fade-in duration-150">
      {/* Top Document Action Toolbar — Normal Page Flow (Non-Sticky) */}
      <div className="w-full bg-white border-b border-slate-200 px-4 sm:px-6 py-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-2xs">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-lg bg-[#0f172a] text-white flex items-center justify-center font-bold text-sm shrink-0">
            <span className="material-symbols-outlined text-[20px]">
              {isInvoice ? 'receipt' : 'receipt_long'}
            </span>
          </div>
          <div className="flex flex-col min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-sm sm:text-base font-bold text-slate-900 truncate" title={doc.file_name}>
                {doc.file_name}
              </h1>
              <StatusBadge status={doc.audit_status} highestSeverity={doc.highest_severity} />
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200"
                title="Document passed Azure AI Content Safety pre-screening prior to Document Intelligence extraction"
              >
                <span className="material-symbols-outlined text-[13px] text-emerald-600">verified_user</span>
                <span>Content Safety: Verified Safe</span>
              </span>
            </div>
            <div className="flex items-center gap-2 sm:gap-3 text-xs text-slate-500 font-mono mt-0.5 flex-wrap">
              <span>Model: <strong className="text-slate-700">{doc.model_used}</strong></span>
              <span>•</span>
              <span>Type: <strong className="text-slate-700 capitalize">{doc.document_type}</strong></span>
              <span>•</span>
              <span>ID: <strong className="text-slate-700">{doc.id?.slice(0, 8)}...</strong></span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0 flex-wrap">
          <button
            onClick={handleRevalidate}
            disabled={isRevalidating}
            className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium flex items-center gap-1.5 transition-colors shadow-2xs"
            title="Re-run deterministic rules"
          >
            <span className={`material-symbols-outlined text-[16px] ${isRevalidating ? 'animate-spin' : ''}`}>
              refresh
            </span>
            <span>{isRevalidating ? 'Revalidating...' : 'Revalidate'}</span>
          </button>

          <button
            onClick={() => setShowJsonModal(true)}
            className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium flex items-center gap-1.5 transition-colors shadow-2xs"
            title="Inspect raw Azure extraction JSON"
          >
            <span className="material-symbols-outlined text-[16px]">data_object</span>
            <span>Azure JSON</span>
          </button>

          <a
            href={fileUrl}
            download={doc.file_name}
            className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium flex items-center gap-1.5 transition-colors shadow-2xs"
            title="Download original document file"
          >
            <span className="material-symbols-outlined text-[16px]">download</span>
            <span>Download Original</span>
          </a>

          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors ml-1"
              title="Close Workspace"
            >
              <span className="material-symbols-outlined text-[20px]">close</span>
            </button>
          )}
        </div>
      </div>

      {revalidationMsg && (
        <div className="mx-4 sm:mx-6 mt-4 p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-lg flex items-center gap-2">
          <span className="material-symbols-outlined text-[16px]">check_circle</span>
          <span>{revalidationMsg}</span>
        </div>
      )}

      {/* Main Responsive Grid Layout (approx 42% PDF Viewer / 58% Extraction on Desktop) */}
      <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-5 lg:gap-6 px-4 sm:px-6 py-5 flex-1 items-start">
        {/* LEFT PANE: Document Viewer & Controls (5/12 = ~42%) */}
        <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden flex flex-col">
          {/* Viewer Mode & Controls Header */}
          <div className="px-3 sm:px-4 py-2.5 bg-slate-100 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-1 bg-white p-0.5 rounded-md border border-slate-200">
              <button
                onClick={() => setActivePreviewTab('pdf')}
                className={`px-2.5 py-1 text-xs rounded font-medium transition-colors ${
                  activePreviewTab === 'pdf'
                    ? 'bg-blue-600 text-white shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                PDF Binary
              </button>
              <button
                onClick={() => setActivePreviewTab('paper')}
                className={`px-2.5 py-1 text-xs rounded font-medium transition-colors ${
                  activePreviewTab === 'paper'
                    ? 'bg-blue-600 text-white shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Auditor Canvas
              </button>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={handleZoomOut}
                className="h-7 w-7 rounded hover:bg-slate-200 flex items-center justify-center text-slate-600"
                title="Zoom Out"
              >
                <span className="material-symbols-outlined text-[16px]">remove</span>
              </button>
              <span className="font-mono text-xs px-1.5 py-0.5 font-semibold text-slate-700">
                {zoomLevel}%
              </span>
              <button
                onClick={handleZoomIn}
                className="h-7 w-7 rounded hover:bg-slate-200 flex items-center justify-center text-slate-600"
                title="Zoom In"
              >
                <span className="material-symbols-outlined text-[16px]">add</span>
              </button>
              <button
                onClick={handleFit}
                className="h-7 px-2 rounded hover:bg-slate-200 flex items-center gap-0.5 text-slate-600 text-xs font-medium"
                title="Fit Screen"
              >
                <span className="material-symbols-outlined text-[14px]">fit_screen</span>
                <span>Fit</span>
              </button>
              <button
                onClick={handleRotate}
                className="h-7 px-2 rounded hover:bg-slate-200 flex items-center gap-0.5 text-slate-600 text-xs font-medium"
                title="Rotate 90 degrees"
              >
                <span className="material-symbols-outlined text-[15px]">rotate_right</span>
                <span className="hidden sm:inline">Rotate</span>
              </button>
            </div>
          </div>

          {/* Viewer Viewport */}
          <div className="p-3 sm:p-4 bg-slate-200/70 h-[680px] lg:h-[780px] xl:h-[860px] flex items-center justify-center overflow-hidden">
            {activePreviewTab === 'pdf' ? (
              <div
                style={{
                  transform: `scale(${zoomLevel / 100}) rotate(${rotation}deg)`,
                  transformOrigin: 'center center',
                  transition: 'transform 0.15s ease',
                  width: '100%',
                  height: '100%',
                }}
                className="bg-white rounded shadow-md overflow-hidden border border-slate-300 flex items-center justify-center"
              >
                <iframe
                  src={fileUrl}
                  title={doc.file_name}
                  className="w-full h-full border-none"
                />
              </div>
            ) : (
              /* Auditor Paper Layout */
              <div
                style={{
                  transform: `scale(${zoomLevel / 100}) rotate(${rotation}deg)`,
                  transformOrigin: 'top center',
                  transition: 'transform 0.15s ease',
                }}
                className="w-full max-w-[460px] max-h-full overflow-y-auto bg-white text-slate-800 shadow-md rounded p-6 relative font-sans border border-slate-300 text-xs space-y-4"
              >
                {/* Stamp */}
                <div className="absolute top-4 right-4 border-2 border-emerald-600/40 rounded px-2 py-0.5 rotate-6 pointer-events-none select-none">
                  <div className="text-[8px] font-bold text-emerald-700 tracking-wider uppercase text-center">
                    ACCOUNTS VERIFIED
                  </div>
                  <div className="text-[7px] font-mono text-emerald-600 text-center">
                    {doc.invoice_date?.value || 'AY 2026-27'}
                  </div>
                </div>

                {/* Header */}
                <div className="border-b border-slate-200 pb-3">
                  <span className="text-[10px] uppercase font-bold text-slate-400">
                    {isInvoice ? 'Tax Invoice' : 'Receipt / Fee Challan'}
                  </span>
                  <h3 className="text-sm font-bold text-slate-900 mt-0.5">
                    {doc.vendor_name?.value || 'Payee / Institution'}
                  </h3>
                  <p className="text-[11px] font-mono text-slate-500">
                    GSTIN: {doc.vendor_tax_id?.value || 'Exempt / Not Stated'}
                  </p>
                </div>

                {/* Metadata */}
                <div className="grid grid-cols-2 gap-2 bg-slate-50 p-2 rounded border border-slate-200 font-mono text-[11px]">
                  <div>
                    <span className="block text-[9px] uppercase text-slate-400">Doc Number</span>
                    <span className="font-semibold text-slate-800">{doc.invoice_id?.value || '—'}</span>
                  </div>
                  <div>
                    <span className="block text-[9px] uppercase text-slate-400">Date</span>
                    <span className="font-semibold text-slate-800">{doc.invoice_date?.value || '—'}</span>
                  </div>
                </div>

                {/* Items */}
                <div className="border-t border-b border-slate-200 py-2">
                  <table className="w-full text-left text-[11px]">
                    <thead>
                      <tr className="text-[9px] uppercase text-slate-400 border-b border-slate-100">
                        <th className="pb-1">Item</th>
                        <th className="pb-1 text-right">Qty</th>
                        <th className="pb-1 text-right">Amount</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {lineItems.map((it, idx) => (
                        <tr key={idx} className="h-6">
                          <td className="py-1 truncate max-w-[160px] font-medium text-slate-800">
                            {it.description || `Item #${idx + 1}`}
                          </td>
                          <td className="py-1 text-right font-mono text-slate-600">
                            {it.quantity ? parseFloat(it.quantity).toFixed(0) : '1'}
                          </td>
                          <td className="py-1 text-right font-mono font-bold text-slate-900">
                            {it.amount ? `₹${parseFloat(it.amount).toFixed(2)}` : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Totals */}
                <div className="space-y-1 text-right font-mono text-xs">
                  {doc.subtotal?.value && (
                    <div className="flex justify-between text-slate-500">
                      <span>Subtotal:</span>
                      <span>₹{parseFloat(doc.subtotal.value).toFixed(2)}</span>
                    </div>
                  )}
                  {doc.tax?.value && (
                    <div className="flex justify-between text-slate-500">
                      <span>Tax / GST:</span>
                      <span>₹{parseFloat(doc.tax.value).toFixed(2)}</span>
                    </div>
                  )}
                  <div className="flex justify-between font-bold text-sm text-slate-900 pt-1 border-t border-slate-200">
                    <span>Total Amount:</span>
                    <span>{formattedTotal}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT PANE: Extracted Fields, Confidence, Reconciler, Flags, and Review (7/12 = ~58%) */}
        <div className="lg:col-span-7 flex flex-col space-y-5 min-w-0">
          {/* Section 1: Extracted Core Financial Fields & Confidence */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
            <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-3 flex items-center gap-2">
              <span className="material-symbols-outlined text-blue-600 text-[18px]">fact_check</span>
              Extracted Fields &amp; Confidence Scores
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-semibold uppercase text-slate-400">Vendor / Payee</span>
                  <ConfidenceBadge confidence={doc.vendor_name?.confidence} status={doc.vendor_name?.status} />
                </div>
                <div className="text-xs font-semibold text-slate-800 truncate">
                  {doc.vendor_name?.value || <span className="text-slate-400 italic">Missing</span>}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-semibold uppercase text-slate-400">Invoice / Receipt ID</span>
                  <ConfidenceBadge confidence={doc.invoice_id?.confidence} status={doc.invoice_id?.status} />
                </div>
                <div className="text-xs font-mono font-semibold text-slate-800 truncate">
                  {doc.invoice_id?.value || <span className="text-slate-400 italic">Missing</span>}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-semibold uppercase text-slate-400">Document Date</span>
                  <ConfidenceBadge confidence={doc.invoice_date?.confidence} status={doc.invoice_date?.status} />
                </div>
                <div className="text-xs font-mono font-semibold text-slate-800 truncate">
                  {doc.invoice_date?.value || <span className="text-slate-400 italic">Missing</span>}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-semibold uppercase text-slate-400">Vendor Tax ID (GSTIN)</span>
                  <ConfidenceBadge confidence={doc.vendor_tax_id?.confidence} status={doc.vendor_tax_id?.status} />
                </div>
                <div className="text-xs font-mono font-semibold text-slate-800 truncate">
                  {doc.vendor_tax_id?.value || (
                    <span className="text-slate-400 italic">
                      {doc.vendor_tax_id?.status === 'not_applicable' ? 'Exempt (Receipt)' : 'Missing'}
                    </span>
                  )}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-semibold uppercase text-slate-400">Subtotal</span>
                  <ConfidenceBadge confidence={doc.subtotal?.confidence} status={doc.subtotal?.status} />
                </div>
                <div className="text-xs font-mono font-semibold text-slate-800">
                  {formattedSubtotal}
                </div>
              </div>

              {doc.cgst?.value && (
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-semibold uppercase text-slate-400">CGST</span>
                    <ConfidenceBadge confidence={doc.cgst?.confidence} status={doc.cgst?.status} />
                  </div>
                  <div className="text-xs font-mono font-semibold text-slate-800">
                    ₹{parseFloat(doc.cgst.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </div>
                </div>
              )}

              {doc.sgst?.value && (
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-semibold uppercase text-slate-400">SGST</span>
                    <ConfidenceBadge confidence={doc.sgst?.confidence} status={doc.sgst?.status} />
                  </div>
                  <div className="text-xs font-mono font-semibold text-slate-800">
                    ₹{parseFloat(doc.sgst.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </div>
                </div>
              )}

              {doc.igst?.value && (
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-semibold uppercase text-slate-400">IGST</span>
                    <ConfidenceBadge confidence={doc.igst?.confidence} status={doc.igst?.status} />
                  </div>
                  <div className="text-xs font-mono font-semibold text-slate-800">
                    ₹{parseFloat(doc.igst.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </div>
                </div>
              )}

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-semibold uppercase text-slate-400">Total Tax / GST</span>
                  <ConfidenceBadge confidence={doc.tax?.confidence} status={doc.tax?.status} />
                </div>
                <div className="text-xs font-mono font-semibold text-slate-800">
                  {formattedTax}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-semibold uppercase text-blue-700">Total Amount</span>
                  <ConfidenceBadge confidence={doc.total?.confidence} status={doc.total?.status} />
                </div>
                <div className="text-sm font-mono font-bold text-blue-900">
                  {formattedTotal}
                </div>
              </div>
            </div>
          </div>

          {/* Section 2: GST-Aware V01 Financial Reconciliation Analysis */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-3 border-b border-slate-200 gap-2">
              <div>
                <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                  <span className="material-symbols-outlined text-blue-600 text-[18px]">calculate</span>
                  GST-Aware Financial Reconciliation (Rule V01)
                </h2>
                <span className="text-[11px] text-slate-500 font-sans mt-0.5 block">
                  Method: <strong className="text-slate-700 font-semibold">{rec?.calculation_type === 'tax_inclusive' ? 'Tax-Inclusive (GST Included)' : (rec?.calculation_type === 'tax_exclusive' ? 'Tax-Exclusive (Subtotal + GST)' : 'Ambiguous Structure')}</strong>
                </span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {isReconciled && !hasV01Flag ? (
                  <span className="px-2.5 py-1 rounded text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1.5 shadow-2xs">
                    <span className="material-symbols-outlined text-[14px]">check_circle</span>
                    RECONCILED — NO V01 FLAG
                  </span>
                ) : isManualReview ? (
                  <span className="px-2.5 py-1 rounded text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200 flex items-center gap-1.5 shadow-2xs">
                    <span className="material-symbols-outlined text-[14px]">help</span>
                    MANUAL REVIEW REQUIRED
                  </span>
                ) : (
                  <span className="px-2.5 py-1 rounded text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200 flex items-center gap-1.5 shadow-2xs">
                    <span className="material-symbols-outlined text-[14px]">warning</span>
                    RECONCILIATION MISMATCH
                  </span>
                )}
              </div>
            </div>

            {/* Authoritative Financial Reconciliation Metric Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-2.5 font-mono text-xs mb-3">
              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-[10px] uppercase text-slate-400 block mb-0.5">Line Items Sum</span>
                <span className="text-xs font-bold text-slate-800">
                  {rec?.line_items_sum ? `₹${parseFloat(rec.line_items_sum).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : (lineItems.length > 0 ? `₹${lineItemsSum.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—')}
                </span>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-[10px] uppercase text-slate-400 block mb-0.5">Extracted Subtotal</span>
                <span className="text-xs font-bold text-slate-800">
                  {rec?.extracted_subtotal ? `₹${parseFloat(rec.extracted_subtotal).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : formattedSubtotal}
                </span>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-[10px] uppercase text-slate-400 block mb-0.5">CGST</span>
                <span className="text-xs font-bold text-slate-800">
                  {rec?.cgst ? `₹${parseFloat(rec.cgst).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : (doc.cgst?.value ? `₹${parseFloat(doc.cgst.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—')}
                </span>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-[10px] uppercase text-slate-400 block mb-0.5">SGST</span>
                <span className="text-xs font-bold text-slate-800">
                  {rec?.sgst ? `₹${parseFloat(rec.sgst).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : (doc.sgst?.value ? `₹${parseFloat(doc.sgst.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—')}
                </span>
              </div>

              {((rec && rec.igst) || doc.igst?.value) && (
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                  <span className="text-[10px] uppercase text-slate-400 block mb-0.5">IGST</span>
                  <span className="text-xs font-bold text-slate-800">
                    ₹{parseFloat(rec?.igst || doc.igst.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
              )}

              {((rec && rec.other_tax) || doc.other_tax?.value) && (
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                  <span className="text-[10px] uppercase text-slate-400 block mb-0.5">Other Tax</span>
                  <span className="text-xs font-bold text-slate-800">
                    ₹{parseFloat(rec?.other_tax || doc.other_tax.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
              )}

              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-[10px] uppercase text-slate-400 block mb-0.5">Total Tax</span>
                <span className="text-xs font-bold text-slate-800">
                  {rec?.total_tax ? `₹${parseFloat(rec.total_tax).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : formattedTax}
                </span>
              </div>

              {((rec && rec.discounts) || doc.discounts?.value) && (
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                  <span className="text-[10px] uppercase text-slate-400 block mb-0.5">Discounts</span>
                  <span className="text-xs font-bold text-emerald-700">
                    -₹{parseFloat(rec?.discounts || doc.discounts.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
              )}

              {((rec && rec.additional_charges) || doc.additional_charges?.value) && (
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                  <span className="text-[10px] uppercase text-slate-400 block mb-0.5">Addl Charges</span>
                  <span className="text-xs font-bold text-slate-800">
                    +₹{parseFloat(rec?.additional_charges || doc.additional_charges.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
              )}

              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-[10px] uppercase text-slate-400 block mb-0.5">Expected Grand Total</span>
                <span className="text-xs font-bold text-blue-800">
                  {rec?.expected_grand_total ? `₹${parseFloat(rec.expected_grand_total).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : formattedTotal}
                </span>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-[10px] uppercase text-slate-400 block mb-0.5">Extracted Grand Total</span>
                <span className="text-xs font-bold text-slate-800">
                  {rec?.extracted_grand_total ? `₹${parseFloat(rec.extracted_grand_total).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : formattedTotal}
                </span>
              </div>

              <div className={`p-2.5 rounded-lg border ${!isReconciled ? 'bg-rose-50 border-rose-200 text-rose-800' : 'bg-emerald-50 border-emerald-200 text-emerald-800'}`}>
                <span className="text-[10px] uppercase block mb-0.5 font-semibold">Variance</span>
                <span className="text-xs font-bold">
                  {rec?.variance ? `₹${parseFloat(rec.variance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '₹0.00'}
                </span>
              </div>
            </div>

            {/* Reconciliation Explanation / Status Narrative */}
            {rec?.explanation && (
              <p className={`text-xs p-2.5 rounded border flex items-center gap-2 ${
                isReconciled && !hasV01Flag
                  ? 'bg-emerald-50/70 border-emerald-200 text-emerald-800'
                  : isManualReview
                  ? 'bg-amber-50/70 border-amber-200 text-amber-800'
                  : 'bg-rose-50/70 border-rose-200 text-rose-800'
              }`}>
                <span className="material-symbols-outlined text-[16px] shrink-0">
                  {isReconciled && !hasV01Flag ? 'check_circle' : isManualReview ? 'help' : 'error'}
                </span>
                <span>{rec.explanation}</span>
              </p>
            )}

            {v01Flag && (
              <div className="mt-2 text-xs text-rose-800 bg-rose-50 p-2.5 rounded border border-rose-200 flex items-start gap-2">
                <span className="material-symbols-outlined text-[16px] text-rose-600 mt-0.5 shrink-0">warning</span>
                <div>
                  <div className="font-semibold">{v01Flag.rule_name} (Severity: {v01Flag.severity})</div>
                  <div className="text-[11px] mt-0.5">{v01Flag.reason}</div>
                </div>
              </div>
            )}
          </div>

          {/* Section 3: Extracted Line Items Table */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
            <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-3 flex items-center gap-2">
              <span className="material-symbols-outlined text-blue-600 text-[18px]">list_alt</span>
              Line Items Detail ({lineItems.length})
            </h2>

            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full text-left border-collapse text-xs min-w-[520px]">
                <thead>
                  <tr className="bg-slate-100 text-slate-600 font-semibold uppercase text-[10px] border-b border-slate-200">
                    <th className="py-2 px-3">Description</th>
                    <th className="py-2 px-3 text-right">Qty</th>
                    <th className="py-2 px-3 text-right">Unit Price</th>
                    <th className="py-2 px-3 text-right">Amount</th>
                    <th className="py-2 px-3 text-center">Confidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {lineItems.length === 0 ? (
                    <tr>
                      <td colSpan="5" className="py-4 text-center text-slate-400 italic">
                        No line items found
                      </td>
                    </tr>
                  ) : (
                    lineItems.map((item, idx) => (
                      <tr key={idx} className="hover:bg-slate-50 transition-colors">
                        <td className="py-2 px-3 font-medium text-slate-800">{item.description || `Item #${idx + 1}`}</td>
                        <td className="py-2 px-3 text-right font-mono text-slate-600">{item.quantity || '1.00'}</td>
                        <td className="py-2 px-3 text-right font-mono text-slate-700">
                          {item.unit_price ? `₹${parseFloat(item.unit_price).toFixed(2)}` : '—'}
                        </td>
                        <td className="py-2 px-3 text-right font-mono font-bold text-slate-900">
                          {item.amount ? `₹${parseFloat(item.amount).toFixed(2)}` : '—'}
                        </td>
                        <td className="py-2 px-3 text-center">
                          <ConfidenceBadge confidence={item.confidence} />
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Section 4: Deterministic Validation Flags (V01–V05) */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
            <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-3 flex items-center gap-2">
              <span className="material-symbols-outlined text-rose-600 text-[18px]">warning</span>
              Audit Findings &amp; Validation Flags ({flags.length})
            </h2>

            {flags.length === 0 ? (
              <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-xs flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-emerald-600">verified</span>
                <span>Zero exceptions detected. All V01–V05 deterministic validation checks passed.</span>
              </div>
            ) : (
              <div className="space-y-2">
                {flags.map((flag, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg bg-slate-50 border border-slate-200 flex flex-col space-y-1 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <SeverityBadge severity={flag.severity} />
                        <span className="font-bold text-slate-900">{flag.rule_id}: {flag.rule_name}</span>
                      </div>
                      {flag.field_name && (
                        <span className="font-mono text-[10px] text-slate-400">
                          Field: {flag.field_name}
                        </span>
                      )}
                    </div>
                    <p className="text-slate-700 mt-1 break-words">{flag.reason}</p>
                    {flag.expected_value && flag.actual_value && (
                      <div className="font-mono text-[11px] text-slate-500 pt-1 border-t border-slate-200">
                        Expected: <span className="text-emerald-700 font-semibold">{flag.expected_value}</span> • Actual: <span className="text-rose-700 font-semibold">{flag.actual_value}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Section 5: Manual Auditor Review */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-200">
              <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                <span className="material-symbols-outlined text-blue-600 text-[18px]">rate_review</span>
                Manual Review Decision
              </h2>
              {reviewSavedSuccess && (
                <span className="text-xs text-emerald-700 font-semibold flex items-center gap-1">
                  <span className="material-symbols-outlined text-[15px]">check_circle</span>
                  Decision Recorded
                </span>
              )}
            </div>

            {reviewError && (
              <div className="mb-3 p-2.5 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-lg flex items-center gap-1.5">
                <span className="material-symbols-outlined text-[16px]">error</span>
                <span>{reviewError}</span>
              </div>
            )}

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Decision:</label>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="decision"
                      value="approved"
                      checked={reviewStatus === 'approved'}
                      onChange={(e) => setReviewStatus(e.target.value)}
                      className="text-emerald-600 focus:ring-emerald-500"
                    />
                    <span className="text-emerald-700 font-medium">Approve Override</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="decision"
                      value="rejected"
                      checked={reviewStatus === 'rejected'}
                      onChange={(e) => setReviewStatus(e.target.value)}
                      className="text-rose-600 focus:ring-rose-500"
                    />
                    <span className="text-rose-700 font-medium">Reject Document</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="decision"
                      value="pending"
                      checked={reviewStatus === 'pending'}
                      onChange={(e) => setReviewStatus(e.target.value)}
                      className="text-amber-600 focus:ring-amber-500"
                    />
                    <span className="text-slate-600">Pending</span>
                  </label>
                </div>
              </div>

              <div>
                <label className="font-semibold text-slate-700 block mb-1">
                  Auditor Notes &amp; Statutory Justification (Required for Approve/Reject):
                </label>
                <textarea
                  value={reviewerNotes}
                  onChange={(e) => setReviewerNotes(e.target.value)}
                  rows={2}
                  placeholder="Enter audit remarks, statutory reference, or override reason..."
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-600 focus:bg-white"
                />
              </div>

              <div className="flex justify-end pt-2">
                <button
                  onClick={handleSaveReview}
                  disabled={isSavingReview}
                  className="px-4 py-2 bg-[#0f172a] hover:bg-[#1e293b] text-white rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors disabled:opacity-50 shadow-sm"
                >
                  <span className="material-symbols-outlined text-[16px]">save</span>
                  <span>{isSavingReview ? 'Saving...' : 'Commit Review Decision'}</span>
                </button>
              </div>
            </div>
          </div>

          {/* Section 6: Audit History & Traceability */}
          {auditHistory.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
              <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-3 flex items-center gap-2">
                <span className="material-symbols-outlined text-slate-500 text-[18px]">history</span>
                Audit Trail &amp; Event History ({auditHistory.length})
              </h2>

              <div className="space-y-2">
                {auditHistory.map((ev, idx) => (
                  <div key={idx} className="p-2.5 rounded bg-slate-50 border border-slate-200 text-xs font-mono">
                    <div className="flex items-center justify-between text-slate-500 mb-0.5">
                      <span className="font-semibold text-slate-800 capitalize">{ev.event || 'Audit Event'}</span>
                      <span className="text-[10px]">{ev.timestamp ? new Date(ev.timestamp).toLocaleString() : ''}</span>
                    </div>
                    {ev.notes && <p className="text-slate-700 font-sans mt-1">Notes: {ev.notes}</p>}
                    {ev.new_status && (
                      <span className="text-[10px] text-blue-700 font-semibold block">Status updated to: {ev.new_status}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Raw JSON Modal */}
      {showJsonModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-3xl w-full max-h-[85vh] flex flex-col shadow-2xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 bg-slate-100 flex items-center justify-between border-b border-slate-200">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-blue-600 text-[20px]">data_object</span>
                <span className="font-bold text-slate-900 text-sm">
                  Azure AI Document Intelligence: Raw Extraction Payload
                </span>
              </div>
              <button
                onClick={() => setShowJsonModal(false)}
                className="text-slate-400 hover:text-slate-700"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            <div className="p-6 overflow-y-auto font-mono text-xs bg-slate-900 text-emerald-400 leading-relaxed flex-1 max-h-[600px]">
              <pre className="whitespace-pre-wrap break-all">
                {(() => {
                  try {
                    return JSON.stringify(JSON.parse(doc.raw_azure_json || '{}'), null, 2);
                  } catch {
                    return doc.raw_azure_json || JSON.stringify(doc, null, 2);
                  }
                })()}
              </pre>
            </div>

            <div className="px-6 py-3 bg-slate-50 flex justify-between items-center border-t border-slate-200">
              <span className="text-[11px] text-slate-500 font-mono">
                Model: {doc.model_used}
              </span>
              <button
                onClick={handleCopyJson}
                className="px-3 py-1.5 bg-[#0f172a] text-white rounded text-xs hover:bg-[#1e293b] transition-colors flex items-center gap-1"
              >
                <span className="material-symbols-outlined text-[15px]">content_copy</span>
                <span>{copiedJson ? 'Copied!' : 'Copy Payload'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

