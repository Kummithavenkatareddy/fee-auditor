import React from 'react';

export default function SeverityBadge({ severity }) {
  const sev = (severity || 'INFO').toUpperCase();

  switch (sev) {
    case 'CRITICAL':
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#FBEAEA] text-[#ba1a1a] border border-[#ffdad6] uppercase tracking-wider font-mono">
          CRITICAL
        </span>
      );
    case 'HIGH':
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#FBEAEA] text-[#B54747] border border-[#ffdad6] uppercase tracking-wider font-mono">
          HIGH
        </span>
      );
    case 'MEDIUM':
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#FEF7EC] text-[#B7791F] border border-[#fde68a] uppercase tracking-wider font-mono">
          MEDIUM
        </span>
      );
    case 'WARNING':
    case 'LOW':
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#EFF3F8] text-[#52677F] border border-[#dde3eb] uppercase tracking-wider font-mono">
          {sev}
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-surface-container text-on-surface-variant font-mono">
          {sev}
        </span>
      );
  }
}

