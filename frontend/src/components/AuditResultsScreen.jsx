import React, { useState, useMemo } from 'react';
import SeverityBadge from './SeverityBadge';
import { downloadAuditCsv } from '../services/api';

export default function AuditResultsScreen({ documents = [], onSelectDoc, onRefresh }) {
  const [activeRuleTab, setActiveRuleTab] = useState('all');
  const [severityFilter, setSeverityFilter] = useState('all');

  // Flatten all validation flags from documents with document references
  const allFindings = useMemo(() => {
    const list = [];
    documents.forEach((doc) => {
      (doc.validation_flags || []).forEach((flag, fIdx) => {
        list.push({
          id: `${doc.id || doc.file_name}-${flag.rule_id}-${fIdx}`,
          docId: doc.id,
          fileName: doc.file_name,
          docType: doc.document_type,
          ruleId: flag.rule_id,
          ruleName: flag.rule_name,
          severity: flag.severity,
          fieldName: flag.field_name || '—',
          reason: flag.reason,
          expectedValue: flag.expected_value,
          actualValue: flag.actual_value,
          timestamp: flag.timestamp,
          originalDoc: doc,
        });
      });
    });
    return list;
  }, [documents]);

  // Tab counts
  const tabCounts = useMemo(() => {
    const counts = { all: allFindings.length, V01: 0, V02: 0, V03: 0, V04: 0, V05: 0 };
    allFindings.forEach((f) => {
      if (counts[f.ruleId] !== undefined) {
        counts[f.ruleId] += 1;
      }
    });
    return counts;
  }, [allFindings]);

  // Filtered findings based on active tab and severity
  const filteredFindings = useMemo(() => {
    return allFindings.filter((finding) => {
      // Rule tab filter
      if (activeRuleTab !== 'all' && finding.ruleId !== activeRuleTab) {
        return false;
      }

      // Severity filter
      if (severityFilter === 'errors' && !['CRITICAL', 'HIGH'].includes(finding.severity)) {
        return false;
      }
      if (severityFilter === 'warnings' && !['MEDIUM', 'WARNING', 'LOW'].includes(finding.severity)) {
        return false;
      }

      return true;
    });
  }, [allFindings, activeRuleTab, severityFilter]);

  const cleanCount = documents.filter((d) => d.audit_status === 'clean').length;
  const flaggedCount = documents.filter((d) => d.audit_status === 'flagged').length;
  const reviewCount = documents.filter((d) => d.manual_review_status === 'pending' && d.audit_status === 'flagged').length;

  const handleExport = async () => {
    try {
      await downloadAuditCsv();
    } catch (err) {
      alert(`Export failed: ${err.message}`);
    }
  };

  return (
    <div className="flex flex-col w-full pb-12">
      {/* Top Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-space-md py-space-md mb-space-lg">
        <div className="flex flex-col">
          <div className="flex items-center gap-space-xs mb-1">
            <span className="inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT bg-primary-container text-on-primary font-label-xs text-label-xs uppercase tracking-wider">
              Deterministic Engine
            </span>
            <span className="text-on-surface-variant font-label-xs text-label-xs">
              • Academic Term: 2026-08-01 to 2026-12-31
            </span>
          </div>
          <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight">Audit Results</h1>
          <p className="font-body-md text-body-md text-on-surface-variant mt-0.5">
            Review deterministic financial validation findings, discrepancy diagnostics, and rule evaluation logs.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-space-sm">
          <button
            onClick={onRefresh}
            className="flex items-center gap-1.5 px-3 h-9 bg-surface-container-low hover:bg-surface-container text-on-surface font-title-md text-body-md rounded-DEFAULT border border-surface-container-highest shadow-xs transition-all active:scale-[0.98]"
          >
            <span className="material-symbols-outlined text-[16px] text-secondary">cached</span>
            <span>Refresh Ledger</span>
          </button>
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 px-3.5 h-9 bg-primary-container hover:bg-primary text-on-primary font-title-md text-body-md rounded-DEFAULT shadow-sm transition-all active:scale-[0.98]"
          >
            <span className="material-symbols-outlined text-[16px]">file_download</span>
            <span>Export Findings CSV</span>
          </button>
        </div>
      </div>

      {/* KPI Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-space-md mb-space-xl">
        {/* Card 1: Clean */}
        <div className="bg-surface-container-lowest rounded-xl p-space-lg border border-surface-container-highest shadow-xs flex flex-col justify-between relative overflow-hidden group hover:shadow-sm transition-shadow">
          <div className="absolute top-0 left-0 right-0 h-1 bg-secondary"></div>
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="font-label-xs text-label-xs uppercase text-on-surface-variant font-semibold tracking-wider">
                Clean Documents
              </span>
              <div className="flex items-baseline gap-2 mt-2">
                <span className="font-display-lg text-display-lg font-bold text-primary">{cleanCount}</span>
                <span className="font-body-sm text-body-sm text-on-surface-variant font-medium">
                  of {documents.length} total
                </span>
              </div>
            </div>
            <div className="h-10 w-10 rounded-lg bg-secondary-container flex items-center justify-center text-on-secondary-container">
              <span className="material-symbols-outlined text-[22px]">verified_user</span>
            </div>
          </div>
          <div className="mt-4 pt-3 bg-surface-container-low -mx-space-lg -mb-space-lg px-space-lg py-2.5 flex items-center justify-between border-t border-surface-container-highest">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-DEFAULT bg-secondary-container text-on-secondary-container font-label-xs text-label-xs font-semibold">
              <span className="material-symbols-outlined text-[12px]">check_circle</span>
              <span>Validated &amp; Clear</span>
            </span>
            <span className="font-label-xs text-label-xs text-on-surface-variant">Zero exceptions</span>
          </div>
        </div>

        {/* Card 2: Flagged */}
        <div className="bg-surface-container-lowest rounded-xl p-space-lg border border-surface-container-highest shadow-xs flex flex-col justify-between relative overflow-hidden group hover:shadow-sm transition-shadow">
          <div className="absolute top-0 left-0 right-0 h-1 bg-error"></div>
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="font-label-xs text-label-xs uppercase text-on-surface-variant font-semibold tracking-wider">
                Flagged Documents
              </span>
              <div className="flex items-baseline gap-2 mt-2">
                <span className="font-display-lg text-display-lg font-bold text-error">{flaggedCount}</span>
                <span className="font-body-sm text-body-sm text-on-surface-variant font-medium">
                  requiring review
                </span>
              </div>
            </div>
            <div className="h-10 w-10 rounded-lg bg-error-container flex items-center justify-center text-on-error-container">
              <span className="material-symbols-outlined text-[22px]">warning</span>
            </div>
          </div>
          <div className="mt-4 pt-3 bg-surface-container-low -mx-space-lg -mb-space-lg px-space-lg py-2.5 flex items-center justify-between border-t border-surface-container-highest">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-DEFAULT bg-error-container text-on-error-container font-label-xs text-label-xs font-semibold">
              <span className="material-symbols-outlined text-[12px]">gavel</span>
              <span>{allFindings.length} Rule Flags</span>
            </span>
            <span className="font-label-xs text-label-xs text-error font-medium">Non-LLM Verified</span>
          </div>
        </div>

        {/* Card 3: Pending Review */}
        <div className="bg-surface-container-lowest rounded-xl p-space-lg border border-surface-container-highest shadow-xs flex flex-col justify-between relative overflow-hidden group hover:shadow-sm transition-shadow">
          <div className="absolute top-0 left-0 right-0 h-1 bg-[#B7791F]"></div>
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="font-label-xs text-label-xs uppercase text-on-surface-variant font-semibold tracking-wider">
                Pending Manual Review
              </span>
              <div className="flex items-baseline gap-2 mt-2">
                <span className="font-display-lg text-display-lg font-bold text-[#B7791F]">
                  {reviewCount}
                </span>
                <span className="font-body-sm text-body-sm text-on-surface-variant font-medium">
                  auditor action items
                </span>
              </div>
            </div>
            <div className="h-10 w-10 rounded-lg bg-[#FEF7EC] flex items-center justify-center text-[#B7791F]">
              <span className="material-symbols-outlined text-[22px]">pending_actions</span>
            </div>
          </div>
          <div className="mt-4 pt-3 bg-surface-container-low -mx-space-lg -mb-space-lg px-space-lg py-2.5 flex items-center justify-between border-t border-surface-container-highest">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-DEFAULT bg-[#FEF7EC] text-[#B7791F] font-label-xs text-label-xs font-semibold">
              <span className="material-symbols-outlined text-[12px]">help</span>
              <span>Review Queue</span>
            </span>
            <span className="font-label-xs text-label-xs text-on-surface-variant">Accounts Desk</span>
          </div>
        </div>
      </div>

      {/* Deterministic Validation Ledger Table */}
      <div className="bg-surface-container-lowest rounded-xl border border-surface-container-highest shadow-sm overflow-hidden mb-space-xl">
        <div className="px-space-lg pt-space-lg pb-space-sm bg-surface-container-low flex flex-col md:flex-row md:items-center justify-between gap-space-md border-b border-surface-container-highest">
          <div className="flex flex-col">
            <span className="font-title-md text-title-md text-primary">Deterministic Validation Ledger</span>
            <span className="font-body-sm text-xs text-on-surface-variant">
              Exact rule violations and warnings evaluated against institutional financial policies
            </span>
          </div>

          <div className="flex items-center gap-space-xs">
            <span className="font-label-xs text-label-xs uppercase text-on-surface-variant font-semibold mr-1">
              Severity:
            </span>
            <button
              onClick={() => setSeverityFilter('all')}
              className={`px-2.5 py-1 rounded-DEFAULT text-label-xs font-label-xs transition-colors ${
                severityFilter === 'all'
                  ? 'bg-surface-container-lowest text-on-surface font-semibold shadow-xs border border-surface-container-highest'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              All Severities
            </button>
            <button
              onClick={() => setSeverityFilter('errors')}
              className={`px-2.5 py-1 rounded-DEFAULT text-label-xs font-label-xs transition-colors ${
                severityFilter === 'errors'
                  ? 'bg-surface-container-lowest text-error font-semibold shadow-xs border border-surface-container-highest'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              Errors Only
            </button>
            <button
              onClick={() => setSeverityFilter('warnings')}
              className={`px-2.5 py-1 rounded-DEFAULT text-label-xs font-label-xs transition-colors ${
                severityFilter === 'warnings'
                  ? 'bg-surface-container-lowest text-[#B7791F] font-semibold shadow-xs border border-surface-container-highest'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              Warnings
            </button>
          </div>
        </div>

        {/* Rule Filter Tabs */}
        <div className="px-space-lg bg-surface-container-low overflow-x-auto border-b border-surface-container-highest">
          <div className="flex items-center gap-1 min-w-max pb-space-sm">
            <button
              onClick={() => setActiveRuleTab('all')}
              className={`px-3 py-1.5 rounded-DEFAULT font-label-md text-xs transition-colors ${
                activeRuleTab === 'all'
                  ? 'bg-primary-container text-on-primary font-semibold shadow-xs'
                  : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
              }`}
            >
              All Findings ({tabCounts.all})
            </button>
            <button
              onClick={() => setActiveRuleTab('V01')}
              className={`px-3 py-1.5 rounded-DEFAULT font-label-md text-xs transition-colors ${
                activeRuleTab === 'V01'
                  ? 'bg-primary-container text-on-primary font-semibold shadow-xs'
                  : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
              }`}
            >
              V01 Total Mismatch ({tabCounts.V01})
            </button>
            <button
              onClick={() => setActiveRuleTab('V02')}
              className={`px-3 py-1.5 rounded-DEFAULT font-label-md text-xs transition-colors ${
                activeRuleTab === 'V02'
                  ? 'bg-primary-container text-on-primary font-semibold shadow-xs'
                  : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
              }`}
            >
              V02 Missing Tax ID ({tabCounts.V02})
            </button>
            <button
              onClick={() => setActiveRuleTab('V03')}
              className={`px-3 py-1.5 rounded-DEFAULT font-label-md text-xs transition-colors ${
                activeRuleTab === 'V03'
                  ? 'bg-primary-container text-on-primary font-semibold shadow-xs'
                  : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
              }`}
            >
              V03 Duplicate Ingestion ({tabCounts.V03})
            </button>
            <button
              onClick={() => setActiveRuleTab('V04')}
              className={`px-3 py-1.5 rounded-DEFAULT font-label-md text-xs transition-colors ${
                activeRuleTab === 'V04'
                  ? 'bg-primary-container text-on-primary font-semibold shadow-xs'
                  : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
              }`}
            >
              V04 Outside Term ({tabCounts.V04})
            </button>
            <button
              onClick={() => setActiveRuleTab('V05')}
              className={`px-3 py-1.5 rounded-DEFAULT font-label-md text-xs transition-colors ${
                activeRuleTab === 'V05'
                  ? 'bg-primary-container text-on-primary font-semibold shadow-xs'
                  : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
              }`}
            >
              V05 Low Confidence ({tabCounts.V05})
            </button>
          </div>
        </div>

        {/* Findings Table */}
        <div className="overflow-x-auto w-full">
          <table className="w-full text-left border-collapse min-w-[900px]">
            <thead>
              <tr className="bg-surface-container-low font-label-xs text-label-xs uppercase text-on-surface-variant h-9 border-b border-surface-container-highest">
                <th className="py-2 px-space-md">Document</th>
                <th className="py-2 px-space-md">Rule ID &amp; Name</th>
                <th className="py-2 px-space-md">Severity</th>
                <th className="py-2 px-space-md">Target Field</th>
                <th className="py-2 px-space-md">Plain-Language Reason</th>
                <th className="py-2 px-space-md">Discrepancy</th>
                <th className="py-2 px-space-md text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container-highest font-body-sm text-body-sm text-on-surface">
              {filteredFindings.length === 0 ? (
                <tr>
                  <td colSpan="7" className="py-12 text-center text-on-surface-variant">
                    <span className="material-symbols-outlined text-[36px] text-outline mb-1 block">task_alt</span>
                    <span className="font-medium text-sm">No findings match the current criteria</span>
                  </td>
                </tr>
              ) : (
                filteredFindings.map((finding) => (
                  <tr
                    key={finding.id}
                    onClick={() => onSelectDoc(finding.originalDoc)}
                    className="hover:bg-surface-container-low transition-colors cursor-pointer group"
                  >
                    <td className="py-2.5 px-space-md font-data-mono text-xs text-primary font-medium flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-[16px] text-outline group-hover:text-primary">
                        {finding.docType === 'invoice' ? 'picture_as_pdf' : 'receipt_long'}
                      </span>
                      <span className="truncate max-w-[140px]" title={finding.fileName}>
                        {finding.fileName}
                      </span>
                    </td>
                    <td className="py-2.5 px-space-md font-data-mono text-xs font-semibold text-on-surface whitespace-nowrap">
                      {finding.ruleId} — {finding.ruleName}
                    </td>
                    <td className="py-2.5 px-space-md whitespace-nowrap">
                      <SeverityBadge severity={finding.severity} />
                    </td>
                    <td className="py-2.5 px-space-md font-data-mono text-xs text-on-surface-variant">
                      {finding.fieldName}
                    </td>
                    <td className="py-2.5 px-space-md text-xs text-on-surface max-w-sm">
                      {finding.reason}
                    </td>
                    <td className="py-2.5 px-space-md font-data-mono text-xs text-on-surface-variant whitespace-nowrap">
                      {finding.expectedValue && finding.actualValue ? (
                        <span>
                          Exp: <span className="font-semibold text-secondary">{finding.expectedValue}</span> | Act: <span className="font-semibold text-error">{finding.actualValue}</span>
                        </span>
                      ) : (
                        <span>—</span>
                      )}
                    </td>
                    <td className="py-2.5 px-space-md text-right whitespace-nowrap">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectDoc(finding.originalDoc);
                        }}
                        className="font-title-md text-[12px] text-primary hover:text-secondary inline-flex items-center gap-0.5"
                      >
                        Inspect <span className="material-symbols-outlined text-[13px]">arrow_forward</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="px-space-md py-2.5 bg-surface-container-low flex items-center justify-between font-label-xs text-label-xs text-on-surface-variant border-t border-surface-container-highest">
          <span>Showing {filteredFindings.length} active findings</span>
          <span className="font-data-mono text-data-mono">Status: Deterministic Audit Verification</span>
        </div>
      </div>
    </div>
  );
}

