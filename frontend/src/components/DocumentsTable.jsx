import React, { useState } from 'react';
import { Eye, ShieldAlert, CheckCircle, AlertTriangle } from 'lucide-react';
import ConfidenceBadge from './ConfidenceBadge';

export default function DocumentsTable({ documents, onSelectDoc }) {
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');

  const filteredDocs = (documents || []).filter((doc) => {
    // Status filter
    if (filter === 'clean' && doc.audit_status !== 'clean') return false;
    if (filter === 'flagged' && doc.audit_status !== 'flagged') return false;
    if (filter === 'reviewed' && doc.audit_status !== 'reviewed') return false;

    // Search query
    if (search.trim()) {
      const q = search.toLowerCase();
      const matchFile = doc.file_name?.toLowerCase().includes(q);
      const matchVendor = doc.vendor_name?.value?.toLowerCase().includes(q);
      const matchInv = doc.invoice_id?.value?.toLowerCase().includes(q);
      return matchFile || matchVendor || matchInv;
    }
    return true;
  });

  return (
    <div className="table-card">
      <div className="table-toolbar">
        <div className="filter-tabs">
          <button
            type="button"
            className={`filter-tab ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All Documents ({documents?.length || 0})
          </button>
          <button
            type="button"
            className={`filter-tab ${filter === 'flagged' ? 'active' : ''}`}
            onClick={() => setFilter('flagged')}
          >
            Flagged ({documents?.filter((d) => d.audit_status === 'flagged').length || 0})
          </button>
          <button
            type="button"
            className={`filter-tab ${filter === 'clean' ? 'active' : ''}`}
            onClick={() => setFilter('clean')}
          >
            Clean ({documents?.filter((d) => d.audit_status === 'clean').length || 0})
          </button>
          <button
            type="button"
            className={`filter-tab ${filter === 'reviewed' ? 'active' : ''}`}
            onClick={() => setFilter('reviewed')}
          >
            Reviewed ({documents?.filter((d) => d.audit_status === 'reviewed').length || 0})
          </button>
        </div>

        <input
          type="text"
          className="search-input"
          placeholder="Search by vendor, invoice #, file name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Document</th>
              <th>Vendor</th>
              <th>Invoice # / Date</th>
              <th style={{ textAlign: 'right' }}>Total</th>
              <th>Compliance Flags</th>
              <th>Audit Status</th>
              <th>Review</th>
              <th style={{ textAlign: 'center' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredDocs.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '36px', color: '#94a3b8' }}>
                  No documents found matching the filter criteria.
                </td>
              </tr>
            ) : (
              filteredDocs.map((doc) => {
                const hasFlags = doc.validation_flags && doc.validation_flags.length > 0;
                return (
                  <tr key={doc.id}>
                    <td>
                      <div style={{ fontWeight: 600, color: '#0f172a' }}>{doc.file_name}</div>
                      <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{doc.model_used}</div>
                    </td>

                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ fontWeight: 500 }}>{doc.vendor_name?.value || '—'}</span>
                        <ConfidenceBadge confidence={doc.vendor_name?.confidence} status={doc.vendor_name?.status} />
                      </div>
                    </td>

                    <td>
                      <div>
                        <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.82rem', fontWeight: 600 }}>
                          {doc.invoice_id?.value || '—'}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                        {doc.invoice_date?.value || '—'}
                      </div>
                    </td>

                    <td style={{ textAlign: 'right' }}>
                      <div style={{ fontWeight: 700, color: '#1e293b' }}>
                        {doc.total?.value != null ? `₹${Number(doc.total.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—'}
                      </div>
                      <ConfidenceBadge confidence={doc.total?.confidence} status={doc.total?.status} />
                    </td>

                    <td>
                      {hasFlags ? (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                          {doc.validation_flags.map((f, i) => (
                            <span
                              key={i}
                              title={f.reason}
                              style={{
                                display: 'inline-block',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                fontSize: '0.72rem',
                                fontWeight: 700,
                                background: f.severity === 'CRITICAL' ? '#ffe4e6' : f.severity === 'MEDIUM' ? '#fef3c7' : '#eff6ff',
                                color: f.severity === 'CRITICAL' ? '#be123c' : f.severity === 'MEDIUM' ? '#b45309' : '#1d4ed8',
                                border: '1px solid rgba(0,0,0,0.06)',
                              }}
                            >
                              {f.rule_id}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span style={{ color: '#059669', fontSize: '0.78rem', fontWeight: 600 }}>
                          ✓ Compliant
                        </span>
                      )}
                    </td>

                    <td>
                      <span className={`badge badge-${doc.audit_status}`}>
                        {doc.audit_status.toUpperCase()}
                      </span>
                    </td>

                    <td>
                      <span className={`badge badge-${doc.manual_review_status || 'pending'}`}>
                        {(doc.manual_review_status || 'pending').toUpperCase()}
                      </span>
                    </td>

                    <td style={{ textAlign: 'center' }}>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => onSelectDoc(doc)}
                        title="Inspect extracted fields, confidence scores, and manual review"
                      >
                        <Eye size={14} /> Review
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

