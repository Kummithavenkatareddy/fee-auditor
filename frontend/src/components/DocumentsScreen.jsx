import React, { useState, useMemo } from 'react';
import ConfidenceBadge from './ConfidenceBadge';
import StatusBadge from './StatusBadge';
import {
  downloadAuditCsv,
  deleteDocument,
  bulkDeleteDocuments,
  getDocumentFileUrl,
} from '../services/api';

export default function DocumentsScreen({ documents = [], onSelectDoc, onRefresh, onNavigateTab }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [docTypeFilter, setDocTypeFilter] = useState('all');
  const [confidenceFilter, setConfidenceFilter] = useState('all');
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [isDeleting, setIsDeleting] = useState(false);
  const [sortBy, setSortBy] = useState('date-desc'); // 'date-desc', 'date-asc', 'amount-desc', 'amount-asc', 'vendor'
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 15;

  // Filtered documents
  const filteredDocs = useMemo(() => {
    return documents.filter((doc) => {
      // Status filter
      if (statusFilter !== 'all' && doc.audit_status !== statusFilter) {
        return false;
      }

      // Doc type filter
      if (docTypeFilter !== 'all' && doc.document_type !== docTypeFilter) {
        return false;
      }

      // Confidence filter
      const totalConf = doc.total?.confidence;
      if (confidenceFilter === 'high' && (totalConf === null || totalConf < 0.90)) {
        return false;
      }
      if (confidenceFilter === 'acceptable' && (totalConf === null || totalConf < 0.85 || totalConf >= 0.90)) {
        return false;
      }
      if (confidenceFilter === 'low' && (totalConf === null || totalConf >= 0.85)) {
        return false;
      }

      // Search filter
      if (searchTerm.trim()) {
        const term = searchTerm.toLowerCase();
        const fname = (doc.file_name || '').toLowerCase();
        const vname = (doc.vendor_name?.value || '').toLowerCase();
        const inum = (doc.invoice_id?.value || '').toLowerCase();
        const taxid = (doc.vendor_tax_id?.value || '').toLowerCase();
        return fname.includes(term) || vname.includes(term) || inum.includes(term) || taxid.includes(term);
      }

      return true;
    });
  }, [documents, statusFilter, docTypeFilter, confidenceFilter, searchTerm]);

  // Sorted documents
  const sortedDocs = useMemo(() => {
    const list = [...filteredDocs];
    list.sort((a, b) => {
      if (sortBy === 'date-desc') {
        return (b.invoice_date?.value || b.created_at || '').localeCompare(a.invoice_date?.value || a.created_at || '');
      }
      if (sortBy === 'date-asc') {
        return (a.invoice_date?.value || a.created_at || '').localeCompare(b.invoice_date?.value || b.created_at || '');
      }
      if (sortBy === 'amount-desc') {
        return (parseFloat(b.total?.value || 0) || 0) - (parseFloat(a.total?.value || 0) || 0);
      }
      if (sortBy === 'amount-asc') {
        return (parseFloat(a.total?.value || 0) || 0) - (parseFloat(b.total?.value || 0) || 0);
      }
      if (sortBy === 'vendor') {
        return (a.vendor_name?.value || '').localeCompare(b.vendor_name?.value || '');
      }
      return 0;
    });
    return list;
  }, [filteredDocs, sortBy]);

  // Paginated documents
  const paginatedDocs = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sortedDocs.slice(start, start + pageSize);
  }, [sortedDocs, currentPage]);

  const totalPages = Math.ceil(sortedDocs.length / pageSize) || 1;

  // Total extracted inflow
  const totalInflow = useMemo(() => {
    const sum = filteredDocs.reduce((acc, doc) => {
      const val = parseFloat(doc.total?.value || 0);
      return acc + (isNaN(val) ? 0 : val);
    }, 0);
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(sum);
  }, [filteredDocs]);

  // Selection handlers
  const toggleSelectAll = () => {
    if (selectedIds.size === paginatedDocs.length && paginatedDocs.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(paginatedDocs.map((d) => d.id)));
    }
  };

  const toggleSelectDoc = (id) => {
    const updated = new Set(selectedIds);
    if (updated.has(id)) {
      updated.delete(id);
    } else {
      updated.add(id);
    }
    setSelectedIds(updated);
  };

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    if (!window.confirm(`Delete ${selectedIds.size} selected document(s) permanently?`)) return;

    setIsDeleting(true);
    try {
      await bulkDeleteDocuments(Array.from(selectedIds));
      setSelectedIds(new Set());
      if (onRefresh) onRefresh();
    } catch (err) {
      alert(`Bulk delete failed: ${err.message}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDeleteSingle = async (e, docId) => {
    e.stopPropagation();
    if (!window.confirm('Delete this document from library?')) return;
    try {
      await deleteDocument(docId);
      if (onRefresh) onRefresh();
    } catch (err) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  const clearFilters = () => {
    setSearchTerm('');
    setStatusFilter('all');
    setDocTypeFilter('all');
    setConfidenceFilter('all');
    setCurrentPage(1);
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
      {/* Top Context Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between py-space-md gap-space-md">
        <div className="flex flex-col space-y-1">
          <div className="flex items-center gap-space-sm">
            <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight">
              My Documents Library
            </h1>
            <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-xs">
              Persistent Storage
            </span>
          </div>
          <p className="font-body-md text-body-md text-on-surface-variant">
            Persistent fee receipts and vendor invoices extracted via Azure AI Document Intelligence.
          </p>
        </div>

        {/* Quick Telemetry & Summary Badges */}
        <div className="flex items-center gap-space-sm flex-wrap">
          <div className="flex items-center gap-2 bg-white border border-slate-200 px-4 py-2 rounded-lg shadow-2xs">
            <span className="text-[10px] uppercase font-bold text-slate-400">Audited Volume</span>
            <span className="text-sm font-bold text-slate-900 font-mono">
              {totalInflow}
            </span>
          </div>

          <button
            onClick={() => (onNavigateTab ? onNavigateTab('reports') : handleExport())}
            className="h-9 px-3 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors shadow-2xs"
            title="Open comprehensive reporting ledger"
          >
            <span className="material-symbols-outlined text-[16px] text-blue-600">table_chart</span>
            <span>Reports &amp; Exports</span>
          </button>
        </div>
      </div>

      {/* Operational Filter Strip */}
      <div className="mb-4 p-3 bg-white border border-slate-200 rounded-xl shadow-2xs flex flex-col xl:flex-row xl:items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5 flex-1">
          {/* Search Input */}
          <div className="relative min-w-[220px] flex-1 max-w-sm">
            <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-[16px] text-slate-400">
              search
            </span>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              placeholder="Search Vendor, Invoice #, GSTIN..."
              className="w-full h-8.5 bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-600 focus:bg-white transition-colors"
            />
          </div>

          {/* Filters */}
          <div className="flex items-center gap-2 flex-wrap">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="bg-slate-50 text-slate-700 text-xs py-1.5 px-2.5 rounded-lg border border-slate-200 focus:outline-none cursor-pointer"
            >
              <option value="all">Status: All</option>
              <option value="clean">Clean</option>
              <option value="flagged">Flagged</option>
              <option value="reviewed">Reviewed</option>
            </select>

            <select
              value={docTypeFilter}
              onChange={(e) => {
                setDocTypeFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="bg-slate-50 text-slate-700 text-xs py-1.5 px-2.5 rounded-lg border border-slate-200 focus:outline-none cursor-pointer"
            >
              <option value="all">Type: All</option>
              <option value="invoice">Invoice</option>
              <option value="receipt">Fee Receipt</option>
            </select>

            <select
              value={confidenceFilter}
              onChange={(e) => {
                setConfidenceFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="bg-slate-50 text-slate-700 text-xs py-1.5 px-2.5 rounded-lg border border-slate-200 focus:outline-none cursor-pointer"
            >
              <option value="all">Confidence: All</option>
              <option value="high">High (&ge;90%)</option>
              <option value="acceptable">Acceptable (85-89%)</option>
              <option value="low">Low (&lt;85%)</option>
            </select>

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="bg-slate-50 text-slate-700 text-xs py-1.5 px-2.5 rounded-lg border border-slate-200 focus:outline-none cursor-pointer font-medium"
            >
              <option value="date-desc">Sort: Date (Newest)</option>
              <option value="date-asc">Sort: Date (Oldest)</option>
              <option value="amount-desc">Sort: Amount (High to Low)</option>
              <option value="amount-asc">Sort: Amount (Low to High)</option>
              <option value="vendor">Sort: Vendor Name</option>
            </select>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0 self-end xl:self-auto">
          {selectedIds.size > 0 && (
            <button
              onClick={handleDeleteSelected}
              disabled={isDeleting}
              className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-medium flex items-center gap-1 transition-colors shadow-2xs"
            >
              <span className="material-symbols-outlined text-[15px]">delete</span>
              <span>Delete ({selectedIds.size})</span>
            </button>
          )}

          <button
            onClick={clearFilters}
            className="flex items-center gap-1 text-slate-600 hover:text-slate-900 text-xs px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 transition-colors"
          >
            <span className="material-symbols-outlined text-[14px]">refresh</span>
            <span>Reset</span>
          </button>
          <span className="font-mono text-xs text-slate-500">
            {sortedDocs.length} items
          </span>
        </div>
      </div>

      {/* Primary Auditing Ledger View */}
      <div className="w-full bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden flex flex-col">
        <div className="overflow-x-auto w-full">
          <table className="w-full text-left border-collapse min-w-[1050px]">
            <thead>
              <tr className="bg-slate-100 text-slate-600 font-semibold text-[11px] uppercase tracking-wider select-none border-b border-slate-200 h-9">
                <th className="py-2 px-3 w-8 text-center">
                  <input
                    type="checkbox"
                    checked={selectedIds.size === paginatedDocs.length && paginatedDocs.length > 0}
                    onChange={toggleSelectAll}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                  />
                </th>
                <th className="py-2 px-3">Document</th>
                <th className="py-2 px-3">Vendor Name</th>
                <th className="py-2 px-3">Doc #</th>
                <th className="py-2 px-3">Date</th>
                <th className="py-2 px-3">GSTIN / Tax ID</th>
                <th className="py-2 px-3 text-right">Subtotal</th>
                <th className="py-2 px-3 text-right">Tax</th>
                <th className="py-2 px-3 text-right">Total (INR)</th>
                <th className="py-2 px-3 text-center">Confidence</th>
                <th className="py-2 px-3 text-center">Status</th>
                <th className="py-2 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs text-slate-800">
              {paginatedDocs.length === 0 ? (
                <tr>
                  <td colSpan="12" className="py-12 text-center text-slate-400">
                    <span className="material-symbols-outlined text-[36px] text-slate-300 mb-1 block">filter_alt_off</span>
                    <span className="font-medium text-sm">No documents found matching current filter</span>
                  </td>
                </tr>
              ) : (
                paginatedDocs.map((doc) => {
                  const isInvoice = doc.document_type === 'invoice';
                  const formattedSubtotal = doc.subtotal?.value
                    ? `₹${parseFloat(doc.subtotal.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                    : '—';
                  const formattedTax = doc.tax?.value
                    ? `₹${parseFloat(doc.tax.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                    : '—';
                  const formattedTotal = doc.total?.value
                    ? `₹${parseFloat(doc.total.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                    : '—';
                  const isSelected = selectedIds.has(doc.id);

                  return (
                    <tr
                      key={doc.id || doc.file_name}
                      onClick={() => onSelectDoc(doc)}
                      className={`h-11 transition-colors group cursor-pointer ${
                        isSelected ? 'bg-blue-50/60' : 'hover:bg-slate-50'
                      }`}
                    >
                      <td
                        className="py-2 px-3 text-center"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectDoc(doc.id)}
                          className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                        />
                      </td>

                      <td className="py-2.5 px-3 font-mono text-xs text-blue-700 font-semibold flex items-center gap-1.5">
                        <span className="material-symbols-outlined text-[16px] text-slate-400 group-hover:text-blue-600">
                          {isInvoice ? 'description' : 'receipt_long'}
                        </span>
                        <span className="truncate max-w-[130px]" title={doc.file_name}>
                          {doc.file_name}
                        </span>
                      </td>

                      <td className="py-2.5 px-3 truncate max-w-[150px] font-medium" title={doc.vendor_name?.value || '—'}>
                        {doc.vendor_name?.value || '—'}
                      </td>

                      <td className="py-2.5 px-3 font-mono text-slate-600 truncate max-w-[110px]">
                        {doc.invoice_id?.value || '—'}
                      </td>

                      <td className="py-2.5 px-3 whitespace-nowrap text-slate-600 font-mono text-xs">
                        {doc.invoice_date?.value || '—'}
                      </td>

                      <td className="py-2.5 px-3 font-mono text-xs text-slate-600">
                        {doc.vendor_tax_id?.value ? (
                          <span className="font-medium text-slate-800">{doc.vendor_tax_id.value}</span>
                        ) : (
                          <span className="text-slate-400 italic">
                            {doc.vendor_tax_id?.status === 'not_applicable' ? 'Exempt' : 'Missing'}
                          </span>
                        )}
                      </td>

                      <td className="py-2.5 px-3 text-right font-mono text-xs text-slate-600">
                        {formattedSubtotal}
                      </td>

                      <td className="py-2.5 px-3 text-right font-mono text-xs text-slate-600">
                        {formattedTax}
                      </td>

                      <td className="py-2.5 px-3 text-right font-mono text-xs font-bold text-slate-900">
                        {formattedTotal}
                      </td>

                      <td className="py-2.5 px-3 text-center">
                        <ConfidenceBadge
                          confidence={doc.total?.confidence}
                          status={doc.total?.status}
                        />
                      </td>

                      <td className="py-2.5 px-3 text-center whitespace-nowrap">
                        <StatusBadge
                          status={doc.audit_status}
                          highestSeverity={doc.highest_severity}
                        />
                      </td>

                      <td className="py-2.5 px-3 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                          <a
                            href={getDocumentFileUrl(doc.id)}
                            download={doc.file_name}
                            className="p-1 rounded text-slate-400 hover:text-blue-600 hover:bg-slate-100"
                            title="Download Original"
                          >
                            <span className="material-symbols-outlined text-[16px]">download</span>
                          </a>

                          <button
                            onClick={(e) => handleDeleteSingle(e, doc.id)}
                            className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-slate-100"
                            title="Delete Document"
                          >
                            <span className="material-symbols-outlined text-[16px]">delete</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination & Ledger Footer */}
        <div className="px-4 py-3 bg-slate-50 flex items-center justify-between text-xs text-slate-500 border-t border-slate-200">
          <span>
            Showing {(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, sortedDocs.length)} of {sortedDocs.length} documents
          </span>

          <div className="flex items-center gap-1">
            <button
              onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
              disabled={currentPage === 1}
              className="p-1 rounded border border-slate-200 disabled:opacity-30 hover:bg-white text-slate-700"
            >
              <span className="material-symbols-outlined text-[16px]">chevron_left</span>
            </button>
            <span className="px-2 font-mono text-xs">
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(p + 1, totalPages))}
              disabled={currentPage === totalPages}
              className="p-1 rounded border border-slate-200 disabled:opacity-30 hover:bg-white text-slate-700"
            >
              <span className="material-symbols-outlined text-[16px]">chevron_right</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
