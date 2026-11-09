import React from 'react';
import { Files, CheckCircle2, AlertOctagon, AlertTriangle, DollarSign } from 'lucide-react';

export default function SummaryCards({ summary }) {
  if (!summary) return null;

  return (
    <div className="metrics-grid">
      <div className="metric-card total">
        <div className="metric-header">
          <span className="metric-label">Total Documents</span>
          <div className="metric-icon-wrap">
            <Files size={18} />
          </div>
        </div>
        <div className="metric-value">{summary.total_documents}</div>
      </div>

      <div className="metric-card clean">
        <div className="metric-header">
          <span className="metric-label">Clean &amp; Compliant</span>
          <div className="metric-icon-wrap">
            <CheckCircle2 size={18} />
          </div>
        </div>
        <div className="metric-value">{summary.clean_documents}</div>
      </div>

      <div className="metric-card flagged">
        <div className="metric-header">
          <span className="metric-label">Flagged Exceptions</span>
          <div className="metric-icon-wrap">
            <AlertOctagon size={18} />
          </div>
        </div>
        <div className="metric-value">{summary.flagged_documents}</div>
      </div>

      <div className="metric-card warning">
        <div className="metric-header">
          <span className="metric-label">Low Confidence (&lt;85%)</span>
          <div className="metric-icon-wrap">
            <AlertTriangle size={18} />
          </div>
        </div>
        <div className="metric-value">{summary.low_confidence_documents}</div>
      </div>

      <div className="metric-card amount">
        <div className="metric-header">
          <span className="metric-label">Total Audited Value</span>
          <div className="metric-icon-wrap">
            <DollarSign size={18} />
          </div>
        </div>
        <div className="metric-value">
          ₹{Number(summary.total_value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
      </div>
    </div>
  );
}

