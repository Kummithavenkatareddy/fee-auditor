import React from 'react';

export default function StatusBadge({ status, highestSeverity = null }) {
  if (status === 'reviewed') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-[#EFF3F8] text-[#172b4d] border border-[#DCE5EE]">
        <span className="material-symbols-outlined text-[12px]">verified</span>
        <span>Auditor Reviewed</span>
      </span>
    );
  }

  if (status === 'clean') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-[#EBF5F0] text-[#287A52] border border-[#D1EADE]">
        <span className="material-symbols-outlined text-[12px]">check_circle</span>
        <span>Clean / Validated</span>
      </span>
    );
  }

  // Flagged
  const label = highestSeverity ? `Flagged (${highestSeverity})` : 'Flagged Discrepancy';
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-[#FBEAEA] text-[#B54747] border border-[#F6D0D0]">
      <span className="material-symbols-outlined text-[12px]">warning</span>
      <span>{label}</span>
    </span>
  );
}

