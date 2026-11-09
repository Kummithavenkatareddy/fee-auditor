import React from 'react';
import { AlertTriangle, AlertOctagon, Info, ShieldAlert } from 'lucide-react';

export default function RuleFlagsList({ flags }) {
  if (!flags || flags.length === 0) {
    return (
      <div style={{ padding: '12px 16px', background: '#ecfdf5', borderRadius: '8px', color: '#047857', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span>✓ No compliance or calculation flags detected. All deterministic audit rules passed.</span>
      </div>
    );
  }

  const getIcon = (severity) => {
    switch (severity) {
      case 'CRITICAL':
      case 'HIGH':
        return <AlertOctagon size={16} color="#e11d48" />;
      case 'MEDIUM':
        return <AlertTriangle size={16} color="#d97706" />;
      default:
        return <ShieldAlert size={16} color="#2563eb" />;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {flags.map((flag, idx) => (
        <div key={idx} className={`flag-card ${flag.severity}`}>
          <div className="flag-header">
            <div className="flag-title">
              {getIcon(flag.severity)}
              <span>[{flag.rule_id}] {flag.rule_name}</span>
            </div>
            <span
              className="badge"
              style={{
                backgroundColor: flag.severity === 'CRITICAL' ? '#ffe4e6' : flag.severity === 'MEDIUM' ? '#fef3c7' : '#eff6ff',
                color: flag.severity === 'CRITICAL' ? '#be123c' : flag.severity === 'MEDIUM' ? '#b45309' : '#1d4ed8',
              }}
            >
              {flag.severity}
            </span>
          </div>

          <div className="flag-reason">
            <strong>Reason:</strong> {flag.reason}
          </div>

          {(flag.expected_value || flag.actual_value) && (
            <div className="flag-vals">
              {flag.field_name && <span style={{ marginRight: '10px' }}><strong>Field:</strong> {flag.field_name}</span>}
              {flag.expected_value && <span style={{ marginRight: '10px' }}><strong>Expected:</strong> {flag.expected_value}</span>}
              {flag.actual_value && <span><strong>Actual:</strong> {flag.actual_value}</span>}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

