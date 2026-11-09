import React from 'react';

export default function ConfidenceBadge({ confidence, status }) {
  if (status === 'not_applicable') {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-surface-container text-on-surface-variant font-mono">
        N/A
      </span>
    );
  }

  if (status === 'missing' || confidence === null || confidence === undefined) {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#FBEAEA] text-[#B54747] font-mono">
        Missing
      </span>
    );
  }

  const score = typeof confidence === 'number' ? confidence : parseFloat(confidence);
  if (isNaN(score)) {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-surface-container text-on-surface-variant font-mono">
        —
      </span>
    );
  }

  const pct = Math.round(score * 100);

  if (score >= 0.90) {
    return (
      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#EBF5F0] text-[#287A52] font-mono">
        <span className="w-1.5 h-1.5 rounded-full bg-[#287A52]"></span>
        {pct}%
      </span>
    );
  }

  if (score >= 0.85) {
    return (
      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#EFF3F8] text-[#52677F] font-mono">
        <span className="w-1.5 h-1.5 rounded-full bg-[#52677F]"></span>
        {pct}%
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#FEF7EC] text-[#B7791F] font-mono">
      <span className="w-1.5 h-1.5 rounded-full bg-[#B7791F]"></span>
      {pct}% Low
    </span>
  );
}
