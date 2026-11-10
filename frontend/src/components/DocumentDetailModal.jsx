import React, { useState } from 'react';
import ConfidenceBadge from './ConfidenceBadge';
import SeverityBadge from './SeverityBadge';
import StatusBadge from './StatusBadge';
import { updateManualReview, revalidateDocument } from '../services/api';

export default function DocumentDetailModal({ doc, onClose, onUpdated }) {
  const [zoomLevel, setZoomLevel] = useState(100);
  const [rotation, setRotation] = useState(0);
  const [showJsonModal, setShowJsonModal] = useState(false);
  const [copiedJson, setCopiedJson] = useState(false);

  // Manual Review Form State
  const [reviewStatus, setReviewStatus] = useState(doc.manual_review_status || 'pending');
  const [reviewerNotes, setReviewerNotes] = useState(doc.manual_review_notes || '');
  const [isSavingReview, setIsSavingReview] = useState(false);
  const [reviewSavedSuccess, setReviewSavedSuccess] = useState(false);

  // Revalidation state
  const [isRevalidating, setIsRevalidating] = useState(false);
  const [revalidationMsg, setRevalidationMsg] = useState(null);

  if (!doc) return null;

  const isInvoice = doc.document_type === 'invoice';
  const totalConf = doc.total?.confidence;
  const flags = doc.validation_flags || [];
  const lineItems = doc.line_items || [];

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
    setIsSavingReview(true);
    setReviewSavedSuccess(false);
    try {
      await updateManualReview(doc.id, reviewStatus, reviewerNotes);
      setReviewSavedSuccess(true);
      setTimeout(() => setReviewSavedSuccess(false), 3000);
      if (onUpdated) onUpdated();
    } catch (err) {
      alert(`Failed to save manual decision: ${err.message}`);
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
    <div className="fixed inset-0 z-50 bg-primary/50 backdrop-blur-sm overflow-y-auto flex items-start justify-center p-2 sm:p-4 md:p-6 animate-fadeIn">
      <div className="bg-surface rounded-xl shadow-2xl max-w-7xl w-full my-auto overflow-hidden border border-surface-container-highest flex flex-col max-h-[96vh]">
        {/* Top Header & Action Banner */}
        <div className="px-space-lg py-3 bg-surface-container-lowest border-b border-surface-container-highest flex flex-col md:flex-row md:items-center justify-between gap-space-sm shrink-0">
          <div className="flex flex-col min-w-0">
            <div className="flex items-center gap-space-xs font-body-sm text-xs text-on-surface-variant mb-0.5">
              <span>Document Ledger</span>
              <span className="material-symbols-outlined text-[13px] text-outline">chevron_right</span>
              <span className="font-data-mono text-data-mono text-on-surface">{doc.file_name}</span>
              <span className="material-symbols-outlined text-[13px] text-outline">chevron_right</span>
              <span className="text-secondary font-semibold">Inspection &amp; Verification</span>
            </div>
            <div className="flex items-center gap-space-sm flex-wrap">
              <h1 className="font-title-md text-headline-sm text-primary font-bold tracking-tight truncate max-w-md">
                {doc.vendor_name?.value || 'Unknown Vendor'}
              </h1>
              <ConfidenceBadge confidence={totalConf} status={doc.total?.status} />
              <StatusBadge status={doc.audit_status} highestSeverity={doc.highest_severity} />
            </div>
          </div>

          {/* Action Bar */}
          <div className="flex items-center gap-space-xs sm:gap-space-sm flex-wrap shrink-0">
            <button
              onClick={() => setShowJsonModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-DEFAULT bg-surface-container-low text-on-surface hover:bg-surface-container border border-surface-container-highest transition-all text-xs font-label-md"
              title="Inspect raw Azure Document Intelligence JSON payload"
            >
              <span className="material-symbols-outlined text-[15px]">code</span>
              <span>Raw JSON</span>
            </button>

            <button
              onClick={handleRevalidate}
              disabled={isRevalidating}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-DEFAULT bg-surface-container-low text-on-surface hover:bg-surface-container border border-surface-container-highest transition-all text-xs font-label-md disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-[15px] text-secondary">cached</span>
              <span>{isRevalidating ? 'Revalidating...' : 'Re-validate'}</span>
            </button>

            <button
              onClick={onClose}
              className="h-8 w-8 flex items-center justify-center rounded-DEFAULT hover:bg-surface-container text-on-surface-variant hover:text-on-surface transition-colors"
              title="Close Inspection View"
            >
              <span className="material-symbols-outlined text-[20px]">close</span>
            </button>
          </div>
        </div>

        {/* Revalidation & Action Banners */}
        {revalidationMsg && (
          <div className="px-space-lg py-2 bg-secondary-container text-on-secondary-container text-xs flex items-center justify-between border-b border-secondary-fixed-dim">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px]">verified</span>
              <span>{revalidationMsg}</span>
            </div>
          </div>
        )}

        {/* Dual Workspace Grid */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-space-md p-space-md overflow-y-auto flex-1">
          {/* LEFT COLUMN: Document Canvas Viewport (5/12 on XL) */}
          <div className="xl:col-span-5 flex flex-col bg-surface-container-lowest rounded-xl border border-surface-container-highest shadow-xs overflow-hidden h-fit">
            {/* Viewer Controls */}
            <div className="h-10 px-space-md bg-surface-container-low flex items-center justify-between select-none border-b border-surface-container-highest">
              <div className="flex items-center gap-space-sm text-xs">
                <span className="inline-flex items-center gap-1 font-mono text-on-surface">
                  <span className="material-symbols-outlined text-[15px] text-secondary">description</span>
                  {doc.document_type === 'invoice' ? 'Tax Invoice' : 'Fee Receipt'}
                </span>
                <span className="h-3 w-px bg-surface-container-highest"></span>
                <span className="font-mono text-[10px] text-on-surface-variant uppercase">
                  SHA256: {doc.file_hash ? doc.file_hash.slice(0, 10) + '...' : 'Verified'}
                </span>
              </div>

              {/* Zoom buttons */}
              <div className="flex items-center gap-1">
                <button
                  onClick={handleZoomOut}
                  className="h-6 w-6 rounded hover:bg-surface-container flex items-center justify-center text-on-surface-variant"
                  title="Zoom Out"
                >
                  <span className="material-symbols-outlined text-[15px]">remove</span>
                </button>
                <span className="font-mono text-xs px-1.5 py-0.5 bg-surface-container-lowest rounded text-on-surface font-semibold">
                  {zoomLevel}%
                </span>
                <button
                  onClick={handleZoomIn}
                  className="h-6 w-6 rounded hover:bg-surface-container flex items-center justify-center text-on-surface-variant"
                  title="Zoom In"
                >
                  <span className="material-symbols-outlined text-[15px]">add</span>
                </button>
                <span className="h-3 w-px bg-surface-container-highest mx-0.5"></span>
                <button
                  onClick={handleFit}
                  className="h-6 px-1.5 rounded hover:bg-surface-container flex items-center gap-0.5 text-on-surface-variant text-[11px]"
                  title="Fit to Window"
                >
                  <span className="material-symbols-outlined text-[14px]">fit_screen</span>
                  <span>Fit</span>
                </button>
                <button
                  onClick={handleRotate}
                  className="h-6 w-6 rounded hover:bg-surface-container flex items-center justify-center text-on-surface-variant"
                  title="Rotate 90°"
                >
                  <span className="material-symbols-outlined text-[14px]">rotate_right</span>
                </button>
              </div>
            </div>

            {/* Document Rendered Paper Viewport */}
            <div className="p-4 bg-surface-container overflow-auto max-h-[700px] flex justify-center">
              <div
                style={{
                  transform: `scale(${zoomLevel / 100}) rotate(${rotation}deg)`,
                  transformOrigin: 'top center',
                  transition: 'transform 0.15s ease',
                }}
                className="w-full max-w-[500px] bg-white text-slate-800 shadow-md rounded p-6 relative font-body-md border border-slate-200"
              >
                {/* Institutional Received Stamp */}
                <div className="absolute top-4 right-4 border-2 border-secondary/40 rounded px-2.5 py-0.5 rotate-6 pointer-events-none select-none">
                  <div className="text-[8px] font-bold text-secondary tracking-widest uppercase text-center">
                    APEX INST TECH
                  </div>
                  <div className="text-[7px] font-mono text-secondary text-center">
                    ACCOUNTS RECD • {doc.invoice_date?.value || '2026-TERM'}
                  </div>
                </div>

                {/* Document Header */}
                <div className="border-b pb-3 mb-3">
                  <div className="text-xs uppercase tracking-wider text-slate-500 font-bold">
                    {isInvoice ? 'Tax Invoice / Bill of Supply' : 'Fee Receipt / Challan'}
                  </div>
                  <h2 className="text-base font-bold text-primary mt-0.5">
                    {doc.vendor_name?.value || 'Institutional Payee'}
                  </h2>
                  <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                    {doc.vendor_tax_id?.value ? `GSTIN: ${doc.vendor_tax_id.value}` : 'No GSTIN declared (Exempt)'}
                  </div>
                </div>

                {/* Metadata Row */}
                <div className="grid grid-cols-2 gap-2 bg-slate-50 p-2.5 rounded text-[11px] mb-3 border border-slate-100 font-mono">
                  <div>
                    <span className="text-slate-400 block text-[9px] uppercase">
                      {isInvoice ? 'Invoice No' : 'Receipt No'}
                    </span>
                    <span className="font-semibold text-slate-700">{doc.invoice_id?.value || '—'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[9px] uppercase">Document Date</span>
                    <span className="font-semibold text-slate-700">{doc.invoice_date?.value || '—'}</span>
                  </div>
                </div>

                {/* Line items mini-table */}
                <div className="mb-3">
                  <table className="w-full text-left text-[11px] border-collapse">
                    <thead>
                      <tr className="border-b text-slate-400 text-[9px] uppercase">
                        <th className="py-1">Description</th>
                        <th className="py-1 text-right">Qty</th>
                        <th className="py-1 text-right">Amount</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {lineItems.length === 0 ? (
                        <tr>
                          <td colSpan="3" className="py-2 text-slate-400 italic">
                            No discrete line items extracted
                          </td>
                        </tr>
                      ) : (
                        lineItems.map((item, idx) => (
                          <tr key={idx} className="h-6">
                            <td className="py-1 truncate max-w-[180px] font-medium text-slate-700">
                              {item.description || `Item #${idx + 1}`}
                            </td>
                            <td className="py-1 text-right font-mono text-slate-600">
                              {item.quantity ? parseFloat(item.quantity).toFixed(0) : '1'}
                            </td>
                            <td className="py-1 text-right font-mono font-semibold text-slate-900 tnum">
                              {item.amount ? `₹${parseFloat(item.amount).toFixed(2)}` : '—'}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Calculations summary */}
                <div className="border-t pt-2 space-y-1 text-right font-mono text-xs">
                  {doc.subtotal?.value && (
                    <div className="flex justify-between text-slate-500">
                      <span>Subtotal:</span>
                      <span className="tnum">₹{parseFloat(doc.subtotal.value).toFixed(2)}</span>
                    </div>
                  )}
                  {doc.tax?.value && (
                    <div className="flex justify-between text-slate-500">
                      <span>Tax / GST:</span>
                      <span className="tnum">₹{parseFloat(doc.tax.value).toFixed(2)}</span>
                    </div>
                  )}
                  <div className="flex justify-between font-bold text-sm text-primary pt-1 border-t border-slate-200">
                    <span>Total Amount:</span>
                    <span className="tnum">{formattedTotal}</span>
                  </div>
                </div>

                {/* Footer signatory note */}
                <div className="mt-6 pt-3 border-t border-slate-100 text-[9px] text-slate-400 flex justify-between items-end">
                  <span>Tamper-evident OCR verification payload</span>
                  <div className="text-right">
                    <span className="block border-t border-dotted border-slate-400 pt-0.5">Authorised Signatory</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="px-space-md py-2 bg-surface-container-low border-t border-surface-container-highest flex items-center justify-between text-[11px] text-on-surface-variant font-mono">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-secondary"></span>
                OCR Model: {doc.model_used}
              </span>
              <span>Extraction: {doc.extraction_status}</span>
            </div>
          </div>

          {/* RIGHT COLUMN: Extracted Data & Compliance Forms (7/12 on XL) */}
          <div className="xl:col-span-7 flex flex-col space-y-space-md">
            {/* Card 1: Vendor Information */}
            <div className="bg-surface-container-lowest rounded-xl p-space-md border border-surface-container-highest shadow-xs">
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-surface-container-highest">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary text-[18px]">storefront</span>
                  <h2 className="font-title-md text-title-md text-primary font-bold">1. Vendor Information</h2>
                </div>
                <ConfidenceBadge
                  confidence={doc.vendor_name?.confidence}
                  status={doc.vendor_name?.status}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-space-sm text-xs">
                <div>
                  <label className="text-label-xs uppercase text-on-surface-variant font-semibold block mb-0.5">
                    Vendor Legal Name
                  </label>
                  <div className="p-2 rounded bg-surface-container-low font-medium text-on-surface border border-surface-container-highest">
                    {doc.vendor_name?.value || <span className="text-outline italic">Missing</span>}
                  </div>
                </div>
                <div>
                  <label className="text-label-xs uppercase text-on-surface-variant font-semibold block mb-0.5">
                    Vendor GSTIN / Tax ID
                  </label>
                  <div className="p-2 rounded bg-surface-container-low font-mono text-on-surface border border-surface-container-highest">
                    {doc.vendor_tax_id?.value || (
                      <span className="text-outline italic">
                        {doc.vendor_tax_id?.status === 'not_applicable' ? 'Exempt (Receipt)' : 'Missing'}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Card 2: Invoice Metadata */}
            <div className="bg-surface-container-lowest rounded-xl p-space-md border border-surface-container-highest shadow-xs">
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-surface-container-highest">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary text-[18px]">receipt_long</span>
                  <h2 className="font-title-md text-title-md text-primary font-bold">2. Document Metadata</h2>
                </div>
                <span className="font-mono text-[11px] text-on-surface-variant">
                  Type: {doc.document_type}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-space-sm text-xs">
                <div>
                  <label className="text-label-xs uppercase text-on-surface-variant font-semibold block mb-0.5">
                    Identifier
                  </label>
                  <div className="p-2 rounded bg-surface-container-low font-mono text-on-surface border border-surface-container-highest truncate">
                    {doc.invoice_id?.value || '—'}
                  </div>
                </div>
                <div>
                  <label className="text-label-xs uppercase text-on-surface-variant font-semibold block mb-0.5">
                    Document Date
                  </label>
                  <div className="p-2 rounded bg-surface-container-low font-mono text-on-surface border border-surface-container-highest">
                    {doc.invoice_date?.value || '—'}
                  </div>
                </div>
                <div>
                  <label className="text-label-xs uppercase text-on-surface-variant font-semibold block mb-0.5">
                    Model Used
                  </label>
                  <div className="p-2 rounded bg-surface-container-low font-mono text-on-surface border border-surface-container-highest truncate">
                    {doc.model_used}
                  </div>
                </div>
              </div>
            </div>

            {/* Card 3: Financial Breakdown & Tax Reconciler (V01 Diagnostic) */}
            <div className="bg-surface-container-lowest rounded-xl p-space-md border border-surface-container-highest shadow-xs">
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-surface-container-highest">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary text-[18px]">calculate</span>
                  <h2 className="font-title-md text-title-md text-primary font-bold">
                    3. Financial Breakdown &amp; V01 Reconciler
                  </h2>
                </div>
                {doc.reconciliation?.status === 'RECONCILED' || (!flags.some((f) => f.rule_id === 'V01') && doc.reconciliation?.is_reconciled) ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-[#EBF5F0] text-[#287A52] border border-[#D1EADE]">
                    RECONCILED — NO V01 FLAG
                  </span>
                ) : doc.reconciliation?.status === 'MANUAL_REVIEW_REQUIRED' ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-[#FEF6E7] text-[#B76E00] border border-[#FDE3B5]">
                    MANUAL REVIEW REQUIRED
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-[#FBEAEA] text-[#ba1a1a] border border-[#ffdad6]">
                    V01 FLAGGED
                  </span>
                )}
              </div>

              {/* Amount strips */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-2 text-xs">
                <div className="p-2 bg-surface-container-low rounded border border-surface-container-highest">
                  <span className="text-[10px] uppercase text-on-surface-variant block">Subtotal</span>
                  <span className="font-mono font-bold text-on-surface tnum">
                    {doc.reconciliation?.extracted_subtotal ? `₹${parseFloat(doc.reconciliation.extracted_subtotal).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : formattedSubtotal}
                  </span>
                </div>
                {doc.cgst?.value && (
                  <div className="p-2 bg-surface-container-low rounded border border-surface-container-highest">
                    <span className="text-[10px] uppercase text-on-surface-variant block">CGST</span>
                    <span className="font-mono font-bold text-on-surface tnum">
                      ₹{parseFloat(doc.cgst.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                )}
                {doc.sgst?.value && (
                  <div className="p-2 bg-surface-container-low rounded border border-surface-container-highest">
                    <span className="text-[10px] uppercase text-on-surface-variant block">SGST</span>
                    <span className="font-mono font-bold text-on-surface tnum">
                      ₹{parseFloat(doc.sgst.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                )}
                <div className="p-2 bg-surface-container-low rounded border border-surface-container-highest">
                  <span className="text-[10px] uppercase text-on-surface-variant block">Tax / GST</span>
                  <span className="font-mono font-bold text-on-surface tnum">
                    {doc.reconciliation?.total_tax ? `₹${parseFloat(doc.reconciliation.total_tax).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : formattedTax}
                  </span>
                </div>
                <div className="p-2 bg-primary-container text-on-primary rounded">
                  <span className="text-[10px] uppercase text-primary-fixed block">Total</span>
                  <span className="font-mono font-bold text-on-primary tnum">{formattedTotal}</span>
                </div>
                <div className="p-2 bg-surface-container-low rounded border border-surface-container-highest">
                  <span className="text-[10px] uppercase text-on-surface-variant block">Line Items Sum</span>
                  <span className="font-mono font-bold text-secondary tnum">
                    {doc.reconciliation?.line_items_sum ? `₹${parseFloat(doc.reconciliation.line_items_sum).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : `₹${lineItems.reduce((acc, it) => acc + (parseFloat(it.amount || 0) || 0), 0).toFixed(2)}`}
                  </span>
                </div>
              </div>

              {doc.reconciliation?.explanation && (
                <div className="text-[11px] font-mono text-on-surface-variant mt-1">
                  Reconciliation: {doc.reconciliation.explanation}
                </div>
              )}
            </div>

            {/* Card 4: Extracted Line Items */}
            <div className="bg-surface-container-lowest rounded-xl p-space-md border border-surface-container-highest shadow-xs">
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-surface-container-highest">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary text-[18px]">list_alt</span>
                  <h2 className="font-title-md text-title-md text-primary font-bold">
                    4. Extracted Line Items ({lineItems.length})
                  </h2>
                </div>
              </div>

              <div className="overflow-x-auto max-h-48">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-surface-container text-on-surface-variant font-label-xs uppercase h-7 border-b border-surface-container-highest">
                      <th className="py-1 px-2">Description</th>
                      <th className="py-1 px-2 text-right">Qty</th>
                      <th className="py-1 px-2 text-right">Unit Price</th>
                      <th className="py-1 px-2 text-right">Amount</th>
                      <th className="py-1 px-2 text-center">Confidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-container-highest">
                    {lineItems.length === 0 ? (
                      <tr>
                        <td colSpan="5" className="py-4 text-center text-on-surface-variant italic">
                          No line items found
                        </td>
                      </tr>
                    ) : (
                      lineItems.map((item, idx) => (
                        <tr key={idx} className="h-8 hover:bg-surface-container-low">
                          <td className="py-1 px-2 font-medium truncate max-w-xs">{item.description || '—'}</td>
                          <td className="py-1 px-2 text-right font-mono">{item.quantity || '1.00'}</td>
                          <td className="py-1 px-2 text-right font-mono tnum">
                            {item.unit_price ? `₹${parseFloat(item.unit_price).toFixed(2)}` : '—'}
                          </td>
                          <td className="py-1 px-2 text-right font-mono font-bold text-primary tnum">
                            {item.amount ? `₹${parseFloat(item.amount).toFixed(2)}` : '—'}
                          </td>
                          <td className="py-1 px-2 text-center">
                            <ConfidenceBadge confidence={item.confidence} />
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Card 5: Active Compliance Validation Flags */}
            <div className="bg-surface-container-lowest rounded-xl p-space-md border border-surface-container-highest shadow-xs">
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-surface-container-highest">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-[#B54747] text-[18px]">fact_check</span>
                  <h2 className="font-title-md text-title-md text-primary font-bold">
                    5. Deterministic Validation Flags ({flags.length})
                  </h2>
                </div>
                <span className="text-xs font-mono text-on-surface-variant">Non-LLM Verified</span>
              </div>

              {flags.length === 0 ? (
                <div className="p-3 rounded bg-[#EBF5F0] border border-[#D1EADE] text-[#287A52] text-xs flex items-center gap-2">
                  <span className="material-symbols-outlined text-[16px]">verified</span>
                  <span className="font-semibold">All compliance checks passed with zero exceptions.</span>
                </div>
              ) : (
                <div className="flex flex-col space-y-2">
                  {flags.map((flag, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded bg-surface-container-low border border-surface-container-highest flex flex-col space-y-1 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <SeverityBadge severity={flag.severity} />
                          <span className="font-bold text-primary">
                            {flag.rule_id}: {flag.rule_name}
                          </span>
                        </div>
                        {flag.field_name && (
                          <span className="font-mono text-[10px] text-outline">
                            Field: {flag.field_name}
                          </span>
                        )}
                      </div>
                      <p className="text-on-surface">{flag.reason}</p>
                      {flag.expected_value && flag.actual_value && (
                        <div className="font-mono text-[11px] text-on-surface-variant pt-1 border-t border-surface-container-highest">
                          Expected: <span className="text-secondary font-semibold">{flag.expected_value}</span> • Actual: <span className="text-error font-semibold">{flag.actual_value}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Card 6: Duplicate Reference Information (if duplicate) */}
            {doc.is_duplicate && (
              <div className="bg-error-container/30 border border-error/20 rounded-xl p-space-md shadow-xs flex items-start gap-2 text-xs">
                <span className="material-symbols-outlined text-error text-[18px] shrink-0 mt-0.5">content_copy</span>
                <div className="flex flex-col space-y-0.5">
                  <span className="font-bold text-error">Duplicate Document Detected</span>
                  <p className="text-on-surface">
                    {doc.is_exact_duplicate
                      ? 'Exact SHA-256 binary hash matches a prior document in the repository.'
                      : 'Business key matches existing normalized vendor identity and invoice number.'}
                  </p>
                </div>
              </div>
            )}

            {/* Card 7: Manual Review Action & Overrides */}
            <div className="bg-surface-container-lowest rounded-xl p-space-md border border-surface-container-highest shadow-xs">
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-surface-container-highest">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary text-[18px]">rate_review</span>
                  <h2 className="font-title-md text-title-md text-primary font-bold">
                    6. Manual Auditor Review
                  </h2>
                </div>
                {reviewSavedSuccess && (
                  <span className="text-xs text-secondary font-semibold flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px]">check</span> Saved to Ledger
                  </span>
                )}
              </div>

              <div className="space-y-3 text-xs">
                <div className="flex items-center gap-3">
                  <label className="font-semibold text-on-surface">Review Decision:</label>
                  <select
                    value={reviewStatus}
                    onChange={(e) => setReviewStatus(e.target.value)}
                    className="bg-surface-container-low border border-surface-container-highest rounded px-2.5 py-1 text-on-surface font-medium focus:outline-none"
                  >
                    <option value="pending">Pending Review</option>
                    <option value="approved">Approve Override</option>
                    <option value="rejected">Reject Document</option>
                  </select>
                </div>

                <div>
                  <label className="font-semibold text-on-surface block mb-1">
                    Auditor Notes &amp; Justification:
                  </label>
                  <textarea
                    value={reviewerNotes}
                    onChange={(e) => setReviewerNotes(e.target.value)}
                    rows={2}
                    placeholder="Enter manual reconciliation notes, departmental references, or statutory override rationale..."
                    className="w-full bg-surface-container-low border border-surface-container-highest rounded p-2 text-on-surface focus:outline-none focus:bg-white text-xs"
                  />
                </div>

                <div className="flex justify-end pt-1">
                  <button
                    onClick={handleSaveReview}
                    disabled={isSavingReview}
                    className="px-4 py-1.5 bg-primary text-on-primary hover:bg-primary-container rounded font-label-md text-xs transition-colors flex items-center gap-1.5 disabled:opacity-50"
                  >
                    <span className="material-symbols-outlined text-[15px]">save</span>
                    <span>{isSavingReview ? 'Saving...' : 'Save Decision'}</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Institutional Integrity Note */}
            <div className="rounded-xl p-space-sm bg-surface-container-low flex items-start gap-space-sm text-on-surface-variant text-[11px] border border-surface-container-highest">
              <span className="material-symbols-outlined text-outline text-[16px] shrink-0 mt-0.5">policy</span>
              <p>
                <strong>Audit Integrity Notice:</strong> Auditor decisions are logged in SQLite separately from the raw Azure AI Document Intelligence payload. The original extraction remains immutable and tamper-evident.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Raw JSON Extraction Modal */}
      {showJsonModal && (
        <div className="fixed inset-0 z-50 bg-primary/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-container-lowest rounded-xl max-w-3xl w-full max-h-[85vh] flex flex-col shadow-2xl border border-surface-container-highest overflow-hidden">
            <div className="px-space-lg py-3 bg-surface-container-low flex items-center justify-between border-b border-surface-container-highest">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-secondary text-[20px]">data_object</span>
                <span className="font-title-md text-title-md text-primary">
                  Azure AI Document Intelligence: Raw Extraction Payload
                </span>
              </div>
              <button
                onClick={() => setShowJsonModal(false)}
                className="text-on-surface-variant hover:text-on-surface"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            <div className="p-space-lg overflow-y-auto font-mono text-xs bg-primary text-primary-fixed leading-relaxed flex-1 max-h-[600px]">
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

            <div className="px-space-lg py-space-sm bg-surface-container-low flex justify-between items-center border-t border-surface-container-highest">
              <span className="text-[11px] text-on-surface-variant font-mono">
                API Version: 2024-11-30 • Model: {doc.model_used}
              </span>
              <button
                onClick={handleCopyJson}
                className="px-3 py-1.5 bg-primary-container text-on-primary rounded text-xs font-label-md hover:bg-primary transition-colors flex items-center gap-1"
              >
                <span className="material-symbols-outlined text-[15px]">content_copy</span>
                <span>{copiedJson ? 'Copied to Clipboard!' : 'Copy Payload'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
