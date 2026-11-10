import React, { useMemo } from 'react';
import StatusBadge from './StatusBadge';

export default function OverviewScreen({
  summary,
  documents = [],
  onSelectDoc,
  onNavigateTab,
}) {
  // Authoritative findings per rule from backend summary
  const ruleCounts = useMemo(() => {
    const v01 = summary?.v01_count ?? 0;
    const v02 = summary?.v02_count ?? 0;
    const v03 = summary?.v03_count ?? 0;
    const v04 = summary?.v04_count ?? 0;
    const v05 = summary?.v05_count ?? summary?.low_confidence_documents ?? 0;
    return {
      V01: v01,
      V02: v02,
      V03: v03,
      V04: v04,
      V05: v05,
      total: v01 + v02 + v03 + v04 + v05,
    };
  }, [summary]);

  // Total value audited
  const totalValueFormatted = useMemo(() => {
    const val = summary?.total_value || 0;
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(val);
  }, [summary?.total_value]);

  const totalDocs = summary?.total_documents ?? documents.length;
  const cleanDocs = summary?.clean_documents ?? documents.filter((d) => d.audit_status === 'clean').length;
  const flaggedDocs = summary?.flagged_documents ?? documents.filter((d) => d.audit_status === 'flagged').length;
  const reviewDocs = summary?.pending_review_documents ?? documents.filter((d) => d.audit_status !== 'clean' && (d.audit_status === 'flagged' || d.manual_review_status === 'pending')).length;

  const cleanRate = totalDocs > 0 ? Math.round((cleanDocs / totalDocs) * 100) : 0;

  return (
    <div className="flex flex-col w-full pb-margin-panel space-y-space-xl">
      {/* PAGE HEADER & TOP CONTROLS */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-space-md pt-space-xs">
        <div className="flex flex-col">
          <div className="flex items-center gap-space-sm">
            <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight">Overview</h1>
            <span className="inline-flex items-center px-2 py-0.5 rounded-DEFAULT bg-surface-container-high text-on-surface-variant font-label-xs text-label-xs uppercase tracking-wider">
              Audit Cycle Live
            </span>
          </div>
          <p className="font-body-md text-body-md text-on-surface-variant mt-0.5">
            Monitor document processing and deterministic financial validation for College Accounts Department.
          </p>
        </div>

        {/* Right Controls: Single Entry Point to Upload & Process */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 rounded-lg shadow-2xs text-xs text-slate-600">
            <span className="material-symbols-outlined text-[15px] text-blue-600">sync</span>
            <span className="text-[10px] uppercase font-bold text-slate-400">Audited Inflow:</span>
            <span className="font-mono text-slate-900 font-bold">
              {totalValueFormatted}
            </span>
          </div>

          <button
            onClick={() => onNavigateTab('upload')}
            className="h-9 px-3.5 bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs rounded-lg shadow-xs transition-colors flex items-center gap-1.5"
            title="Upload and process documents"
          >
            <span className="material-symbols-outlined text-[17px]">cloud_upload</span>
            <span>Upload &amp; Process</span>
          </button>

          <button
            onClick={() => onNavigateTab('reports')}
            className="h-9 px-3 bg-white hover:bg-slate-50 text-slate-700 font-medium text-xs rounded-lg border border-slate-300 shadow-2xs transition-colors flex items-center gap-1.5"
            title="View audit reports and export CSV"
          >
            <span className="material-symbols-outlined text-[17px] text-slate-500">table_chart</span>
            <span>Reports</span>
          </button>
        </div>
      </div>

      {/* PRIMARY SUMMARY METRIC PANELS (4 Cards) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-space-md">
        {/* Card 1: Total Documents */}
        <div className="bg-surface-container-lowest rounded-lg p-space-lg shadow-sm border border-surface-container-highest flex flex-col justify-between relative overflow-hidden">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="font-label-xs text-label-xs uppercase tracking-wider text-on-surface-variant font-semibold">
                Total Documents
              </span>
              <span className="font-display-lg text-display-lg text-primary mt-1">
                {totalDocs}
              </span>
            </div>
            <div className="w-9 h-9 rounded-DEFAULT bg-surface-container flex items-center justify-center text-primary">
              <span className="material-symbols-outlined text-[20px]">description</span>
            </div>
          </div>
          <div className="mt-space-md pt-space-xs flex items-center text-on-surface-variant font-body-sm text-body-sm">
            <span className="material-symbols-outlined text-[14px] mr-1 text-outline">calendar_month</span>
            <span>Ingested across fee receipts &amp; vendor invoices</span>
          </div>
        </div>

        {/* Card 2: Successfully Audited */}
        <div className="bg-surface-container-lowest rounded-lg p-space-lg shadow-sm border border-surface-container-highest flex flex-col justify-between relative overflow-hidden">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="font-label-xs text-label-xs uppercase tracking-wider text-on-surface-variant font-semibold">
                Successfully Audited
              </span>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="font-display-lg text-display-lg text-primary">
                  {cleanDocs}
                </span>
                <span className="inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT text-label-xs font-label-xs font-semibold bg-[#EBF5F0] text-[#287A52]">
                  {cleanRate}% clean rate
                </span>
              </div>
            </div>
            <div className="w-9 h-9 rounded-DEFAULT bg-[#EBF5F0] flex items-center justify-center text-[#287A52]">
              <span className="material-symbols-outlined text-[20px]">verified</span>
            </div>
          </div>
          <div className="mt-space-md pt-space-xs flex items-center justify-between text-on-surface-variant font-body-sm text-body-sm">
            <div className="w-full bg-surface-container-high rounded-full h-1.5 overflow-hidden mr-2">
              <div
                className="bg-[#287A52] h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${cleanRate}%` }}
              ></div>
            </div>
            <span className="font-data-mono text-data-mono text-[11px] text-[#287A52] shrink-0 font-semibold">
              {cleanDocs} / {totalDocs} PASSED
            </span>
          </div>
        </div>

        {/* Card 3: Flagged Documents */}
        <div className="bg-surface-container-lowest rounded-lg p-space-lg shadow-sm border border-surface-container-highest flex flex-col justify-between relative overflow-hidden">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="font-label-xs text-label-xs uppercase tracking-wider text-on-surface-variant font-semibold">
                Flagged Documents
              </span>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="font-display-lg text-display-lg text-[#B54747]">
                  {flaggedDocs}
                </span>
                <span className="inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT text-label-xs font-label-xs font-semibold bg-[#FBEAEA] text-[#B54747]">
                  Requires reconciliation
                </span>
              </div>
            </div>
            <div className="w-9 h-9 rounded-DEFAULT bg-[#FBEAEA] flex items-center justify-center text-[#B54747]">
              <span className="material-symbols-outlined text-[20px]">warning</span>
            </div>
          </div>
          <div className="mt-space-md pt-space-xs flex items-center text-on-surface-variant font-body-sm text-body-sm">
            <span className="material-symbols-outlined text-[14px] mr-1 text-[#B54747]">error_outline</span>
            <span>Tax mismatch, duplicate ref, or math error</span>
          </div>
        </div>

        {/* Card 4: Pending Manual Review */}
        <div className="bg-surface-container-lowest rounded-lg p-space-lg shadow-sm border border-surface-container-highest flex flex-col justify-between relative overflow-hidden">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="font-label-xs text-label-xs uppercase tracking-wider text-on-surface-variant font-semibold">
                Pending Manual Review
              </span>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="font-display-lg text-display-lg text-[#B7791F]">
                  {reviewDocs}
                </span>
                <span className="inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT text-label-xs font-label-xs font-semibold bg-[#FEF7EC] text-[#B7791F]">
                  Field conf. &lt; 85%
                </span>
              </div>
            </div>
            <div className="w-9 h-9 rounded-DEFAULT bg-[#FEF7EC] flex items-center justify-center text-[#B7791F]">
              <span className="material-symbols-outlined text-[20px]">rule</span>
            </div>
          </div>
          <div className="mt-space-md pt-space-xs flex items-center text-on-surface-variant font-body-sm text-body-sm">
            <span className="material-symbols-outlined text-[14px] mr-1 text-[#B7791F]">pending_actions</span>
            <span>Awaiting auditor sign-off on OCR variance</span>
          </div>
        </div>
      </div>

      {/* 12-COLUMN MAIN CONTENT GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-md">
        {/* LEFT 8-COLUMN: Recent Documents Table & Activity Trail */}
        <div className="lg:col-span-8 flex flex-col space-y-space-md min-w-0">
          {/* Recent Documents Table */}
          <div className="bg-surface-container-lowest rounded-lg shadow-sm border border-surface-container-highest overflow-hidden flex flex-col">
            <div className="px-space-lg py-3 flex flex-wrap items-center justify-between gap-space-sm bg-surface-container-lowest border-b border-surface-container-highest">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-primary">table_chart</span>
                <h2 className="font-title-md text-title-md text-primary">Recent Documents Ledger</h2>
                <span className="text-label-xs font-label-xs font-semibold bg-surface-container text-on-surface-variant px-2 py-0.5 rounded-DEFAULT">
                  {documents.length} Records
                </span>
              </div>
              <button
                onClick={() => onNavigateTab('documents')}
                className="h-7.5 px-2.5 bg-surface-container-low hover:bg-surface-container text-on-surface font-title-md text-[12px] rounded-DEFAULT flex items-center transition-colors"
              >
                View Full Ledger &rarr;
              </button>
            </div>

            {/* Table Viewport */}
            <div className="w-full overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-surface-container-low text-on-surface-variant font-label-xs text-label-xs uppercase tracking-wider h-8 select-none border-b border-surface-container-highest">
                    <th className="py-2 pl-space-lg pr-2 font-semibold">Document Name</th>
                    <th className="py-2 px-2 font-semibold">Vendor / Payee</th>
                    <th className="py-2 px-2 font-semibold">Invoice No.</th>
                    <th className="py-2 px-2 font-semibold">Date</th>
                    <th className="py-2 px-2 font-semibold text-right">Total (INR)</th>
                    <th className="py-2 px-2 font-semibold text-center">Audit Status</th>
                    <th className="py-2 pr-space-lg pl-2 font-semibold text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-container-highest font-body-sm text-body-sm text-on-surface">
                  {documents.length === 0 ? (
                    <tr>
                      <td colSpan="7" className="py-8 text-center text-on-surface-variant">
                        <div className="flex flex-col items-center justify-center space-y-2">
                          <span className="material-symbols-outlined text-[32px] text-outline">folder_open</span>
                          <span className="font-medium">No documents processed yet</span>
                          <button
                            onClick={() => onNavigateTab && onNavigateTab('upload')}
                            className="text-xs text-primary underline hover:text-secondary font-medium"
                          >
                            Upload documents to begin
                          </button>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    documents.slice(0, 6).map((doc) => {
                      const isInvoice = doc.document_type === 'invoice';
                      const formattedTotal = doc.total?.value
                        ? `₹${parseFloat(doc.total.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                        : '—';
                      return (
                        <tr
                          key={doc.id || doc.file_name}
                          onClick={() => onSelectDoc(doc)}
                          className="h-10 hover:bg-surface-container-low transition-colors group cursor-pointer"
                        >
                          <td className="py-2 pl-space-lg pr-2 font-data-mono text-data-mono text-primary font-medium flex items-center gap-1.5">
                            <span className="material-symbols-outlined text-[16px] text-outline group-hover:text-primary">
                              {isInvoice ? 'picture_as_pdf' : 'receipt_long'}
                            </span>
                            <span className="truncate max-w-[140px]" title={doc.file_name}>
                              {doc.file_name}
                            </span>
                          </td>
                          <td className="py-2 px-2 truncate max-w-[150px]" title={doc.vendor_name?.value || '—'}>
                            {doc.vendor_name?.value || '—'}
                          </td>
                          <td className="py-2 px-2 font-data-mono text-data-mono text-on-surface-variant truncate max-w-[120px]">
                            {doc.invoice_id?.value || '—'}
                          </td>
                          <td className="py-2 px-2 whitespace-nowrap text-on-surface-variant">
                            {doc.invoice_date?.value || '—'}
                          </td>
                          <td className="py-2 px-2 font-data-mono text-data-mono font-semibold text-primary text-right tnum">
                            {formattedTotal}
                          </td>
                          <td className="py-2 px-2 text-center whitespace-nowrap">
                            <StatusBadge status={doc.audit_status} highestSeverity={doc.highest_severity} />
                          </td>
                          <td className="py-2 pr-space-lg pl-2 text-right whitespace-nowrap">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onSelectDoc(doc);
                              }}
                              className="font-title-md text-[12px] text-primary hover:text-secondary inline-flex items-center gap-0.5"
                            >
                              Inspect <span className="material-symbols-outlined text-[13px]">arrow_forward</span>
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            <div className="px-space-lg py-2.5 bg-surface-container-low flex items-center justify-between font-label-xs text-label-xs text-on-surface-variant border-t border-surface-container-highest">
              <span>Showing {Math.min(documents.length, 6)} of {documents.length} documents in queue</span>
              <span className="font-data-mono text-data-mono">Ledger State: Fully Synchronized</span>
            </div>
          </div>

          {/* SECTION C: Processing Activity Stream */}
          <div className="bg-surface-container-lowest rounded-lg p-space-lg shadow-sm border border-surface-container-highest flex flex-col space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-surface-container-highest">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-secondary">history_edu</span>
                <h3 className="font-title-md text-title-md text-primary">Auditor Activity Trail &amp; Engine Logs</h3>
              </div>
              <span className="font-label-xs text-label-xs text-outline uppercase font-semibold">
                Strict Deterministic Trail
              </span>
            </div>

            <div className="flex flex-col space-y-2">
              {documents.slice(0, 3).map((doc, idx) => {
                const isClean = doc.audit_status === 'clean';
                const hasFlags = (doc.validation_flags || []).length > 0;
                return (
                  <div
                    key={doc.id || idx}
                    className="flex items-start gap-3 p-2.5 rounded-DEFAULT bg-surface-container-low hover:bg-surface-container transition-colors"
                  >
                    <div
                      className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
                        isClean
                          ? 'bg-[#EBF5F0] text-[#287A52]'
                          : 'bg-[#FBEAEA] text-[#B54747]'
                      }`}
                    >
                      <span className="material-symbols-outlined text-[14px]">
                        {isClean ? 'check' : 'priority_high'}
                      </span>
                    </div>
                    <div className="flex flex-col flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="font-data-mono text-data-mono text-primary font-semibold truncate max-w-[240px]">
                          {doc.file_name}
                        </span>
                        <span className="font-data-mono text-data-mono text-[11px] text-on-surface-variant">
                          {doc.created_at ? new Date(doc.created_at).toLocaleTimeString() : 'Synced'}
                        </span>
                      </div>
                      <p className="font-body-sm text-body-sm text-on-surface-variant mt-0.5">
                        {isClean
                          ? `Extracted with high confidence; verified against tax rules and mathematical parity.`
                          : `Flagged: ${doc.validation_flags?.[0]?.reason || 'Compliance flag triggered'}`}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* RIGHT 4-COLUMN: Audit Findings Breakdown */}
        <div className="lg:col-span-4 flex flex-col space-y-space-md">
          <div className="bg-surface-container-lowest rounded-lg p-space-lg shadow-sm border border-surface-container-highest flex flex-col">
            <div className="flex items-center justify-between pb-space-sm border-b border-surface-container-highest">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-[#B54747]">fact_check</span>
                <h3 className="font-title-md text-title-md text-primary">Audit Findings Breakdown</h3>
              </div>
              <span className="font-label-xs text-label-xs bg-[#FBEAEA] text-[#B54747] font-semibold px-2 py-0.5 rounded-DEFAULT">
                {ruleCounts.total} Active Flags
              </span>
            </div>

            <p className="font-body-sm text-body-sm text-on-surface-variant mt-2 mb-space-sm">
              Deterministic institutional rules evaluated against statutory financial policies:
            </p>

            {/* Rule List */}
            <div className="flex flex-col space-y-2">
              {/* V01 Total Mismatch */}
              <div className="p-2.5 rounded-DEFAULT bg-surface-container-low flex flex-col space-y-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="font-title-md text-[13px] text-on-surface font-semibold">V01: Total Mismatch</span>
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-[#FBEAEA] text-[#ba1a1a]">
                      CRITICAL
                    </span>
                  </div>
                  <span className="font-data-mono text-data-mono font-bold text-[#ba1a1a]">
                    {ruleCounts.V01}
                  </span>
                </div>
                <p className="font-body-sm text-[12px] text-on-surface-variant">
                  Line items sum + tax != total or ambiguous calculation semantics.
                </p>
              </div>

              {/* V02 Missing Tax Number */}
              <div className="p-2.5 rounded-DEFAULT bg-surface-container-low flex flex-col space-y-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="font-title-md text-[13px] text-on-surface font-semibold">V02: Missing Tax ID</span>
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-[#FEF7EC] text-[#B7791F]">
                      MEDIUM
                    </span>
                  </div>
                  <span className="font-data-mono text-data-mono font-bold text-[#B7791F]">
                    {ruleCounts.V02}
                  </span>
                </div>
                <p className="font-body-sm text-[12px] text-on-surface-variant">
                  Missing GSTIN on invoices (Receipts legally exempt).
                </p>
              </div>

              {/* V03 Duplicate Ingestion */}
              <div className="p-2.5 rounded-DEFAULT bg-surface-container-low flex flex-col space-y-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="font-title-md text-[13px] text-on-surface font-semibold">V03: Duplicate Ingestion</span>
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-[#FBEAEA] text-[#ba1a1a]">
                      CRITICAL
                    </span>
                  </div>
                  <span className="font-data-mono text-data-mono font-bold text-[#ba1a1a]">
                    {ruleCounts.V03}
                  </span>
                </div>
                <p className="font-body-sm text-[12px] text-on-surface-variant">
                  Exact SHA-256 binary match or normalized vendor + invoice ID duplicate.
                </p>
              </div>

              {/* V04 Outside Academic Term */}
              <div className="p-2.5 rounded-DEFAULT bg-surface-container-low flex flex-col space-y-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="font-title-md text-[13px] text-on-surface font-semibold">V04: Outside Term</span>
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-[#FEF7EC] text-[#B7791F]">
                      MEDIUM
                    </span>
                  </div>
                  <span className="font-data-mono text-data-mono font-bold text-[#B7791F]">
                    {ruleCounts.V04}
                  </span>
                </div>
                <p className="font-body-sm text-[12px] text-on-surface-variant">
                  Date falling outside configured term bounds (2026-08-01 to 2026-12-31).
                </p>
              </div>

              {/* V05 Low Confidence */}
              <div className="p-2.5 rounded-DEFAULT bg-surface-container-low flex flex-col space-y-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="font-title-md text-[13px] text-on-surface font-semibold">V05: Low Confidence</span>
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-[#EFF3F8] text-[#52677F]">
                      WARNING
                    </span>
                  </div>
                  <span className="font-data-mono text-data-mono font-bold text-[#52677F]">
                    {ruleCounts.V05}
                  </span>
                </div>
                <p className="font-body-sm text-[12px] text-on-surface-variant">
                  OCR confidence below 0.85 threshold on extracted fields.
                </p>
              </div>
            </div>

            <button
              onClick={() => onNavigateTab('audit-results')}
              className="mt-4 w-full py-2 bg-surface-container hover:bg-surface-container-high text-primary font-title-md text-xs rounded-DEFAULT transition-colors flex items-center justify-center gap-1"
            >
              <span>Explore Detailed Findings</span>
              <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

