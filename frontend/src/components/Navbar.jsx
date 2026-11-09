import React from 'react';
import { ShieldCheck, Download, RefreshCw, Trash2, CheckCircle2 } from 'lucide-react';
import { getExportCsvUrl, resetDatabase } from '../services/api';

export default function Navbar({ health, onDataChanged }) {
  const isOnline = health?.azure_configured;

  const handleReset = async () => {
    if (window.confirm('Are you sure you want to clear all audited documents and start fresh?')) {
      try {
        await resetDatabase();
        if (onDataChanged) onDataChanged();
      } catch (err) {
        alert('Reset failed: ' + err.message);
      }
    }
  };

  return (
    <nav className="navbar">
      <div className="brand-section">
        <div className="brand-icon">
          <ShieldCheck size={26} />
        </div>
        <div>
          <h1 className="brand-title">Fee Receipt &amp; Invoice Auditor</h1>
          <p className="brand-subtitle">
            Azure AI Document Intelligence (2024-11-30) • Prebuilt Models • Deterministic Rules (V01–V05)
          </p>
        </div>
      </div>

      <div className="nav-actions">
        {/* Azure Status Pill */}
        <span className={`status-pill ${isOnline ? 'online' : 'offline'}`}>
          <CheckCircle2 size={13} />
          {isOnline ? 'Azure AI Connected' : 'Azure AI Disconnected'}
        </span>

        {/* Academic Term Pill */}
        {health?.academic_term && (
          <span className="status-pill term">
            Term: {health.academic_term.start} → {health.academic_term.end}
          </span>
        )}

        {/* Confidence Threshold */}
        <span className="status-pill term" title="Configurable confidence threshold">
          Conf Threshold: {(Number(health?.confidence_threshold || 0.85) * 100).toFixed(0)}%
        </span>

        {/* Export CSV Button */}
        <a
          href={getExportCsvUrl()}
          download="fee_audit_results.csv"
          className="btn btn-primary btn-sm"
          style={{ textDecoration: 'none' }}
        >
          <Download size={14} /> Export Audit CSV
        </a>

        {/* Reset Database Button */}
        <button
          type="button"
          onClick={handleReset}
          className="btn btn-danger-outline btn-sm"
          title="Clear all stored documents"
        >
          <Trash2 size={14} /> Reset
        </button>
      </div>
    </nav>
  );
}

